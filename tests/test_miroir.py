"""Le miroir ne perd rien — ni au redémarrage, ni quand Google tombe.

Ces tests décrivent exactement les scénarios qui faisaient disparaître des
réussites dans la version précédente (risques R2 et R3).
"""

from datetime import datetime, timedelta

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
