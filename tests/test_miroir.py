"""Le miroir ne perd rien — ni au redémarrage, ni quand Google tombe.

Ces tests décrivent exactement les scénarios qui faisaient disparaître des
réussites dans la version précédente (risques R2 et R3).
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from climbcontest.contest import enregistrer_reussite
from climbcontest.extensions import db
from climbcontest.models import Success
from climbcontest.sheets.client import ErreurClasseur
from climbcontest.sheets.mirror import synchroniser


class ClasseurFictif:
    """Remplace l'API Google. Peut être configuré pour échouer."""

    def __init__(self, echoue=False):
        self.echoue = echoue
        self.ecrites: list[tuple[int, int]] = []
        self.appels = 0

    def marquer_reussites(self, couples):
        self.appels += 1
        if self.echoue:
            raise ErreurClasseur("API Google indisponible (simule)")
        self.ecrites.extend(couples)
        return len(couples)


@pytest.fixture()
def trois_reussites(app, jeu):
    p1, p2 = jeu["participants"][0], jeu["participants"][1]
    b1, b2 = jeu["blocs"][0], jeu["blocs"][1]
    enregistrer_reussite(p1, b1)
    enregistrer_reussite(p1, b2)
    enregistrer_reussite(p2, b1)
    return jeu


class TestSynchronisationNominale:
    def test_envoie_et_marque(self, app, trois_reussites):
        cl = ClasseurFictif()
        r = synchroniser(classeur=cl)
        assert r["envoyees"] == 3
        assert r["restantes"] == 0
        assert len(cl.ecrites) == 3
        assert Success.query.filter(Success.sheet_synced_at.is_(None)).count() == 0

    def test_adressage_dossard_et_numero(self, app, trois_reussites):
        """Le classeur attend (dossard, numéro de bloc), pas des identifiants
        internes : c'est ce couple qui donne la cellule."""
        cl = ClasseurFictif()
        synchroniser(classeur=cl)
        assert (1, 1) in cl.ecrites      # dossard 1, bloc n°1
        assert (2, 1) in cl.ecrites

    def test_rien_a_faire(self, app, jeu):
        cl = ClasseurFictif()
        assert synchroniser(classeur=cl)["envoyees"] == 0
        assert cl.appels == 0            # on n'appelle pas Google pour rien

    def test_ne_renvoie_pas_ce_qui_est_deja_synchronise(self, app, trois_reussites):
        cl = ClasseurFictif()
        synchroniser(classeur=cl)
        synchroniser(classeur=cl)
        assert len(cl.ecrites) == 3      # et non 6


class TestEchecDuClasseur:
    """Le scénario qui détruisait des données : risque R3."""

    def test_rien_n_est_marque_si_l_ecriture_echoue(self, app, trois_reussites):
        cl = ClasseurFictif(echoue=True)
        r = synchroniser(classeur=cl)
        assert r["envoyees"] == 0
        assert r["erreur"]
        # LE point : les trois réussites sont toujours là, non synchronisées.
        assert Success.query.filter(Success.sheet_synced_at.is_(None)).count() == 3

    def test_rattrapage_automatique(self, app, trois_reussites):
        """Classeur injoignable, puis rétabli : tout part, sans intervention."""
        casse = ClasseurFictif(echoue=True)
        for _ in range(3):
            synchroniser(classeur=casse)
        assert Success.query.filter(Success.sheet_synced_at.is_(None)).count() == 3

        repare = ClasseurFictif()
        r = synchroniser(classeur=repare)
        assert r["envoyees"] == 3
        assert Success.query.filter(Success.sheet_synced_at.is_(None)).count() == 0

    def test_le_service_continue_d_accepter_des_reussites(self, app, jeu, client):
        """Même classeur à terre, un juge doit pouvoir valider."""
        synchroniser(classeur=ClasseurFictif(echoue=True))
        r = client.post("/api/v2/contest/success", json={"bib": "1", "bloc": "ZJ6"})
        assert r.status_code == 201


class TestRedemarrage:
    def test_les_reussites_en_attente_survivent(self, app, trois_reussites):
        """Risque R2 : la file en RAM disparaissait au redémarrage.

        Ici le travail à faire est une requête SQL — vider la session ne change
        rien.
        """
        db.session.expunge_all()
        assert Success.query.filter(Success.sheet_synced_at.is_(None)).count() == 3
        assert synchroniser(classeur=ClasseurFictif())["envoyees"] == 3


class TestLots:
    def test_respecte_la_taille_de_lot(self, app, jeu):
        p1, p2 = jeu["participants"][0], jeu["participants"][1]
        for b in jeu["blocs"]:
            enregistrer_reussite(p1, b)
            enregistrer_reussite(p2, b)

        cl = ClasseurFictif()
        r = synchroniser(taille_lot=2, classeur=cl)
        assert r["envoyees"] == 2
        assert r["restantes"] == 4

    def test_le_plus_ancien_d_abord(self, app, jeu):
        p = jeu["participants"][0]
        s1, _ = enregistrer_reussite(p, jeu["blocs"][0])
        s2, _ = enregistrer_reussite(p, jeu["blocs"][1])
        s1.horodatage = datetime.now() - timedelta(hours=1)
        db.session.commit()

        cl = ClasseurFictif()
        synchroniser(taille_lot=1, classeur=cl)
        assert cl.ecrites == [(p.dossard, jeu["blocs"][0].numero)]


class TestVerrou:
    def test_un_seul_synchronise_a_la_fois(self, app, trois_reussites):
        """Quatre workers gunicorn feraient sinon quatre fois la même écriture."""
        db.session.execute(
            text("INSERT INTO verrou (nom, detenu_par, pris_le) VALUES "
                 "('miroir_classeur', 'un-autre-worker', :p)"),
            {"p": datetime.now()},
        )
        db.session.commit()

        cl = ClasseurFictif()
        r = synchroniser(classeur=cl)
        assert r["ignoree"] is True
        assert cl.appels == 0

    def test_un_verrou_perime_est_repris(self, app, trois_reussites):
        """Un worker tué en plein travail ne doit pas bloquer la
        synchronisation jusqu'au prochain redémarrage complet."""
        db.session.execute(
            text("INSERT INTO verrou (nom, detenu_par, pris_le) VALUES "
                 "('miroir_classeur', 'worker-mort', :p)"),
            {"p": datetime.now() - timedelta(minutes=30)},
        )
        db.session.commit()

        r = synchroniser(classeur=ClasseurFictif())
        assert r["ignoree"] is False
        assert r["envoyees"] == 3


class TestParticipantSansDossard:
    def test_ignore_les_reussites_sans_dossard(self, app, jeu):
        """Sans dossard, pas de colonne dans le classeur : on n'essaie pas.

        La réussite reste en base et sera envoyée dès qu'un dossard sera
        attribué.
        """
        absent = jeu["participants"][2]
        enregistrer_reussite(absent, jeu["blocs"][0])
        cl = ClasseurFictif()
        assert synchroniser(classeur=cl)["envoyees"] == 0
        assert Success.query.filter(Success.sheet_synced_at.is_(None)).count() == 1


class JetonFactice:
    """Jeton picklable, defini au niveau du module pour que pickle l'accepte."""
    valid = True


class TestOuLeJetonEstCherche:
    """Le jeton Google vit HORS des releases, comme les donnees.

    Constate en production le 28/08 : le miroir echouait toutes les 40 secondes
    sur « Aucun jeton Google » alors que `token.pickle` etait bien sur la VM.
    Le client le cherchait en chemin RELATIF, donc dans le repertoire de travail
    du service -- ou il n'a jamais ete. L'unite systemd definissait deja
    `CLIMBCONTEST_SECRETS_DIR` ; le code ne l'avait jamais lu.

    Consequence si personne ne l'avait vu : aucune reussite n'atteint le
    classeur le jour de la competition. Les donnees ne sont pas perdues -- elles
    restent en base, marquees non synchronisees -- mais le classeur reste vide.
    """

    def test_le_dossier_configure_est_regarde_en_premier(self, app, tmp_path, monkeypatch):
        from climbcontest.sheets.client import ClasseurGoogle

        app.config["DOSSIER_SECRETS"] = str(tmp_path)
        dossiers = ClasseurGoogle._dossiers_de_jeton()

        assert Path(dossiers[0]) == tmp_path

    def test_la_variable_d_environnement_est_prise_en_compte(self, app, tmp_path, monkeypatch):
        from climbcontest.sheets.client import ClasseurGoogle

        monkeypatch.setenv("CLIMBCONTEST_SECRETS_DIR", str(tmp_path))
        app.config["DOSSIER_SECRETS"] = None

        assert tmp_path in [Path(d) for d in ClasseurGoogle._dossiers_de_jeton()]

    def test_le_repertoire_courant_reste_un_repli(self, app):
        """Pour les outils lances a la main depuis la racine du depot."""
        from climbcontest.sheets.client import ClasseurGoogle

        assert Path.cwd() in [Path(d) for d in ClasseurGoogle._dossiers_de_jeton()]

    def test_un_jeton_pose_au_bon_endroit_est_trouve(self, app, tmp_path):
        """Le test qui aurait attrape le defaut."""
        import pickle
        from climbcontest.sheets.client import ClasseurGoogle

        # Un objet picklable trivial : ce qui est teste, c'est OU le fichier est
        # cherche, pas ce qu'il contient. `valid` suffit a court-circuiter le
        # rafraichissement.
        (tmp_path / "token.pickle").write_bytes(pickle.dumps(JetonFactice()))
        app.config["DOSSIER_SECRETS"] = str(tmp_path)

        creds = ClasseurGoogle._identifiants()

        assert creds is not None

    def test_le_message_d_erreur_dit_ou_il_a_cherche(self, app, tmp_path, monkeypatch):
        """Le message precedent citait « token.pickle » sans chemin.

        C'est exactement ce qui a masque le probleme : le fichier existait,
        mais ailleurs, et rien ne le disait.
        """
        from climbcontest.sheets.client import ClasseurGoogle, ErreurClasseur

        app.config["DOSSIER_SECRETS"] = str(tmp_path / "nulle-part")
        monkeypatch.delenv("CLIMBCONTEST_SECRETS_DIR", raising=False)
        # Sans ca, le repli sur le repertoire courant trouverait le VRAI jeton
        # de developpement, pose a la racine du depot -- et le test passerait
        # pour une raison qui n'a rien a voir avec ce qu'il verifie.
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ErreurClasseur) as e:
            ClasseurGoogle._identifiants()

        assert "nulle-part" in str(e.value), "le message doit citer les chemins essayes"


class TestCompetitionSansClasseur:
    """Entre la creation d'une competition et son parametrage, il n'y a pas
    encore de classeur. C'est normal -- et ca ne doit pas remplir le journal.

    Sans garde-fou, le miroir tentait l'ecriture toutes les 40 secondes et
    journalisait une erreur Google a chaque fois, sur chacun des quatre
    workers : six erreurs par minute pour une situation parfaitement normale.
    C'est ainsi qu'un journal devient illisible, et qu'on rate la vraie panne
    quand elle arrive.
    """

    def test_rien_n_est_tente_sans_classeur(self, app, jeu):
        jeu["competition"].spreadsheet_id = None
        db.session.commit()
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])

        def interdit(*a, **k):
            raise AssertionError("aucun appel Google ne doit avoir lieu")

        r = synchroniser(classeur=interdit)

        assert r["ignoree"] is True
        assert "classeur" in r["erreur"]

    def test_la_reussite_reste_en_attente(self, app, jeu):
        """Elle n'est surtout pas marquee synchronisee : rien n'est parti."""
        jeu["competition"].spreadsheet_id = "   "
        db.session.commit()
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])

        synchroniser()

        assert Success.query.filter(Success.sheet_synced_at.is_(None)).count() == 1

    def test_des_qu_un_classeur_est_relie_le_miroir_repart(self, app, jeu):
        jeu["competition"].spreadsheet_id = None
        db.session.commit()
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        assert synchroniser()["ignoree"] is True

        jeu["competition"].spreadsheet_id = "un-vrai-identifiant"
        db.session.commit()

        appels = []

        class Faux:
            def marquer_reussites(self, couples):
                appels.append(couples)
                return len(couples)

        r = synchroniser(classeur=Faux())

        assert appels, "le miroir doit repartir des qu'un classeur est relie"
        assert r["envoyees"] == 1
