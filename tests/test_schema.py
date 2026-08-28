"""Tests de la préparation du schéma et de son verrou.

Ce qui est protégé ici : que le démarrage crée le schéma **une fois**, ne
détruise jamais rien, et ne se bloque pas définitivement si un processus meurt
au mauvais moment.

Le risque R1 — la base effacée à chaque import par `db.drop_all()` — a été
corrigé en spec 001. Ces tests empêchent une rechute et couvrent le cas que
personne n'avait vu : un verrou orphelin qui empêche **toutes** les migrations
futures, en silence.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from climbcontest import schema
from climbcontest.extensions import db
from climbcontest.models import Competition, EN_COURS


def _verrou():
    return db.session.execute(
        text("SELECT detenu_par, pris_le FROM verrou WHERE nom = 'schema'")
    ).fetchone()


def _poser_verrou(detenu_par: str, age: timedelta) -> None:
    schema._table_verrou()
    db.session.execute(
        text("INSERT INTO verrou (nom, detenu_par, pris_le) VALUES (:n, :d, :p)"),
        {"n": "schema", "d": detenu_par, "p": datetime.now() - age},
    )
    db.session.commit()


class TestPreparation:

    def test_est_idempotente(self, app):
        """Quatre workers appellent la même chose : rien ne doit casser."""
        for _ in range(4):
            schema.preparer_schema()
        # Les tables sont toujours là et utilisables.
        db.session.add(Competition(nom="X", date=datetime.now().date(),
                                   statut=EN_COURS, active=True))
        db.session.commit()
        assert Competition.query.count() == 1

    def test_ne_detruit_jamais_les_donnees(self, app, competition):
        """Le coeur du risque R1 : un redémarrage ne doit rien effacer."""
        avant = Competition.query.count()
        schema.preparer_schema()
        schema.preparer_schema()
        assert Competition.query.count() == avant

    def test_libere_le_verrou_en_sortant(self, app):
        schema.preparer_schema()
        assert _verrou() is None, "le verrou doit être rendu"

    def test_libere_le_verrou_meme_si_ca_echoue(self, app, monkeypatch):
        """Sinon la première panne bloquerait tous les démarrages suivants."""
        monkeypatch.setattr(schema, "_table_migrations",
                            lambda: (_ for _ in ()).throw(RuntimeError("disque plein")))
        with pytest.raises(RuntimeError):
            schema.preparer_schema()
        assert _verrou() is None


class TestVerrouOrphelin:
    """Le cas qui rendait la panne invisible.

    Un processus tué entre la prise et la libération — OOM killer, coupure de
    courant, `systemctl kill` — laissait la ligne en base. Tous les démarrages
    suivants voyaient un verrou pris, renonçaient, et **journalisaient qu'un
    autre s'en chargeait**. Aucune migration ne serait plus jamais jouée.
    """

    def test_un_verrou_recent_est_respecte(self, app):
        _poser_verrou("autre-worker:999", age=timedelta(seconds=1))
        assert schema._prendre_verrou() is False
        assert _verrou()[0] == "autre-worker:999", "on n'a pas volé un verrou vivant"

    def test_un_verrou_perime_est_repris(self, app):
        _poser_verrou("mort:999", age=schema.VERROU_TTL + timedelta(seconds=1))
        assert schema._prendre_verrou() is True
        assert _verrou()[0] == schema._identite(), "le verrou doit nous appartenir"

    def test_les_migrations_repartent_apres_un_orphelin(self, app):
        """La conséquence concrète : le schéma redevient préparable."""
        _poser_verrou("mort:999", age=schema.VERROU_TTL + timedelta(seconds=1))
        schema.preparer_schema()
        assert _verrou() is None
        db.session.add(Competition(nom="Reprise", date=datetime.now().date(),
                                   statut=EN_COURS, active=True))
        db.session.commit()

    def test_une_date_illisible_ne_fait_pas_planter(self, app):
        """Une ligne corrompue ne doit pas empêcher le serveur de démarrer."""
        schema._table_verrou()
        db.session.execute(
            text("INSERT INTO verrou (nom, detenu_par, pris_le) VALUES ('schema', 'x', 'n/a')"))
        db.session.commit()
        assert schema._prendre_verrou() is False   # prudent : on ne vole pas au hasard

    def test_un_seul_de_deux_voleurs_gagne(self, app, monkeypatch):
        """Deux workers qui repèrent le même orphelin ne doivent pas migrer à deux.

        Le piège de ce test : appeler `_prendre_verrou()` deux fois de suite ne
        le vérifie **pas**. Le second voit le verrou tout frais du premier et
        renonce sur la branche « verrou récent » — il n'atteint jamais le vol.
        Le test resterait vert avec un arbitrage entièrement cassé.

        On reproduit donc la vraie course : B a lu l'orphelin **avant** que A ne
        le vole, et part le voler sur cette lecture périmée. C'est bien
        `_prendre_verrou()` — le code de production — qui exécute le vol.
        """
        _poser_verrou("mort:999", age=schema.VERROU_TTL + timedelta(seconds=1))
        vu_par_b = _verrou()                 # la lecture périmée de B

        monkeypatch.setattr(schema, "_identite", lambda: "workerA:1")
        assert schema._prendre_verrou() is True, "le premier voleur doit gagner"

        monkeypatch.setattr(schema, "_identite", lambda: "workerB:2")
        monkeypatch.setattr(schema, "_verrou_courant", lambda: vu_par_b)

        assert schema._prendre_verrou() is False, "B ne doit pas voler le verrou de A"
        monkeypatch.undo()
        assert _verrou()[0] == "workerA:1", "le verrou de A ne doit pas avoir bouge"

    def test_un_voleur_ne_supprime_pas_le_verrou_frais_d_un_autre(self, app, monkeypatch):
        """`_identite()` vaut `hostname:pid`, et un PID se recycle.

        Gunicorn peut attribuer à un worker vivant le PID exact du processus
        mort. Si le `WHERE` du vol ne portait que sur `detenu_par` — ce que le
        commentaire du code affirmait avant qu'on ne le vérifie — ce worker
        supprimerait le verrou **frais** de celui qui vient de voler, et deux
        préparations tourneraient en parallèle. C'est la date qui l'empêche.
        """
        _poser_verrou("host:26781", age=schema.VERROU_TTL + timedelta(seconds=1))
        vu_par_b = _verrou()                 # la lecture périmée de B

        # A hérite du PID du mort : il vole, et réinsère sous la MÊME identité,
        # avec une date fraîche. C'est ce détail qui rend le cas dangereux.
        monkeypatch.setattr(schema, "_identite", lambda: "host:26781")
        assert schema._prendre_verrou() is True
        date_de_a = _verrou()[1]

        monkeypatch.setattr(schema, "_identite", lambda: "workerB:2")
        monkeypatch.setattr(schema, "_verrou_courant", lambda: vu_par_b)

        assert schema._prendre_verrou() is False, \
            "sans la date dans le WHERE, B effacerait le verrou frais de A et gagnerait"
        monkeypatch.undo()
        assert _verrou() is not None, "le verrou de A ne doit pas avoir disparu"
        assert (_verrou()[0], _verrou()[1]) == ("host:26781", date_de_a)

    def test_on_ne_rend_que_son_propre_verrou(self, app, monkeypatch):
        """Un détenteur lent mais vivant ne doit pas effacer le verrou de son voleur.

        Sinon un troisième processus le prend, deux préparations tournent en
        même temps, et un quatrième — en attente — voit la ligne disparaître et
        conclut que le schéma est prêt. C'est le symptôme R1, par un autre
        chemin que celui qu'on vient de boucher.
        """
        monkeypatch.setattr(schema, "_identite", lambda: "lent:111")
        schema._table_verrou()
        assert schema._essayer_de_prendre() is True

        # Son verrou est volé pendant qu'il travaille encore.
        db.session.execute(text("DELETE FROM verrou WHERE detenu_par = 'lent:111'"))
        db.session.commit()
        monkeypatch.setattr(schema, "_identite", lambda: "voleur:222")
        assert schema._essayer_de_prendre() is True

        # Le lent termine et rend « son » verrou.
        monkeypatch.setattr(schema, "_identite", lambda: "lent:111")
        schema._rendre_verrou()

        assert _verrou() is not None, "le verrou du voleur ne doit pas avoir disparu"
        assert _verrou()[0] == "voleur:222"

class TestSonde:
    """`/health` doit avouer quand la base est inutilisable.

    C'est cette sonde qui a laisse l'agent de deploiement valider un serveur ou
    chaque scan renvoyait 500 : l'exception etait avalee, `reussites_en_attente`
    valait `null`, et le statut restait « ok ». Sa porte de deploiement est
    `curl /health` puis comparaison du champ `version` — les deux passaient.
    """

    def test_ok_quand_la_base_repond(self, client, competition):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"

    def test_degraded_503_quand_la_base_est_inutilisable(self, client, app):
        db.session.execute(text("DROP TABLE IF EXISTS success"))
        db.session.commit()

        r = client.get("/health")

        assert r.status_code == 503, "un retour arriere doit se declencher, pas passer inapercu"
        d = r.get_json()
        assert d["status"] == "degraded"
        assert "base" in d, "la sonde doit dire ce qui ne va pas"
        assert d["version"], "la version reste lisible : l'agent en a besoin pour son diagnostic"


class TestAttente:
    """Un worker sans le verrou ne doit pas servir avant que le schéma existe."""

    def test_retour_immediat_si_personne_ne_detient_le_verrou(self, app):
        schema._table_verrou()
        schema._attendre_liberation()

    def test_rend_la_main_des_que_le_verrou_disparait(self, app, monkeypatch):
        """Le cas utile : la ligne est là, puis un autre processus la retire.

        La version précédente de ce test appelait `_attendre_liberation()` sur
        une table vide — il n'y avait donc aucune libération à observer, et il
        serait resté vert même si la boucle ne relisait jamais la base.
        """
        appels = {"n": 0}
        vrai = schema._verrou_courant

        def verrou_qui_tombe():
            appels["n"] += 1
            return ("autre:1", datetime.now()) if appels["n"] < 4 else None

        monkeypatch.setattr(schema, "_verrou_courant", verrou_qui_tombe)
        schema._attendre_liberation()

        assert appels["n"] >= 4, "la boucle doit relire la base jusqu'a la liberation"

    def test_renonce_au_bout_du_delai_plutot_que_de_bloquer(self, app, monkeypatch):
        """Mieux vaut servir avec un doute que ne jamais démarrer.

        Si l'attente était infinie, un verrou coincé transformerait un démarrage
        raté en VM qui ne répond plus du tout — bien pire un dimanche matin.
        """
        monkeypatch.setattr(schema, "ATTENTE_MAX", timedelta(seconds=0.2))
        _poser_verrou("autre:1", age=timedelta(seconds=0))
        debut = datetime.now()
        schema._attendre_liberation()
        ecoule = (datetime.now() - debut).total_seconds()
        assert 0.15 < ecoule < 3, f"a attendu {ecoule:.2f} s"
