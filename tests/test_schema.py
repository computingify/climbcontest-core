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

    def test_un_seul_de_deux_voleurs_gagne(self, app):
        """Deux workers qui repèrent le même orphelin ne doivent pas migrer à deux."""
        _poser_verrou("mort:999", age=schema.VERROU_TTL + timedelta(seconds=1))
        premier = schema._prendre_verrou()
        second = schema._prendre_verrou()
        assert premier is True
        assert second is False, "le second voleur doit échouer sur la clé primaire"


class TestAttente:
    """Un worker sans le verrou ne doit pas servir avant que le schéma existe."""

    def test_rend_la_main_des_que_le_verrou_tombe(self, app):
        schema._table_verrou()
        schema._attendre_liberation()      # aucun verrou : retour immédiat

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
