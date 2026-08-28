"""Le classement servi par l'API, et son cache.

Le cache n'est pas un détail : le jour d'une compétition, ~60 spectateurs
rafraîchissent toutes les 15 s. Sans lui, chaque rafraîchissement relancerait le
calcul complet.
"""

import time

from climbcontest import classement_service
from climbcontest.contest import enregistrer_reussite
from climbcontest.extensions import db


class TestRouteClassement:
    def test_sans_authentification(self, client, jeu):
        """Les spectateurs n'ont pas de compte."""
        assert client.get("/api/public/classement").status_code == 200

    def test_contenu(self, client, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement").get_json()

        assert d["competition"]["nom"] == "Test 2026"
        assert d["calcule_le"] > 0
        groupes = {c["groupe"] for c in d["classements"]}
        assert "U11 F" in groupes and "U13 H" in groupes

    def test_les_lignes_portent_le_nom_et_le_club(self, client, jeu):
        """La page résultats doit pouvoir afficher autre chose qu'un numéro."""
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement?groupe=U11 F").get_json()
        ligne = d["classements"][0]["lignes"][0]
        assert ligne["nom"] == "Dupont Lea"
        assert ligne["club"] == "Les Lezards"
        assert ligne["score"] == 1000        # seule sur ce bloc dans sa categorie

    def test_un_seul_groupe(self, client, jeu):
        d = client.get("/api/public/classement?groupe=U11 F").get_json()
        assert len(d["classements"]) == 1
        assert d["classements"][0]["groupe"] == "U11 F"

    def test_groupe_inconnu(self, client, jeu):
        r = client.get("/api/public/classement?groupe=U99 X")
        assert r.status_code == 404
        assert "groupes" in r.get_json()      # on dit lesquels existent

    def test_sans_competition_active(self, client, app):
        assert client.get("/api/public/classement").status_code == 409

    def test_liste_des_groupes(self, client, jeu):
        d = client.get("/api/public/groupes").get_json()
        noms = {g["nom"] for g in d["groupes"]}
        assert {"U11 F", "U13 H"} <= noms
        assert all("type" in g and "participants" in g for g in d["groupes"])


class TestCache:
    def setup_method(self):
        classement_service.invalider()

    def test_deux_appels_rapproches_ne_calculent_qu_une_fois(self, app, jeu, monkeypatch):
        appels = {"n": 0}
        vrai = classement_service.calculer_tout

        def compter(*a, **k):
            appels["n"] += 1
            return vrai(*a, **k)

        monkeypatch.setattr(classement_service, "calculer_tout", compter)

        for _ in range(5):
            classement_service.classements(jeu["competition"])
        assert appels["n"] == 1, "le calcul doit etre mutualise"

    def test_forcer_recalcule(self, app, jeu, monkeypatch):
        appels = {"n": 0}
        vrai = classement_service.calculer_tout
        monkeypatch.setattr(classement_service, "calculer_tout",
                            lambda *a, **k: (appels.__setitem__("n", appels["n"] + 1),
                                             vrai(*a, **k))[1])
        classement_service.classements(jeu["competition"])
        classement_service.classements(jeu["competition"], forcer=True)
        assert appels["n"] == 2

    def test_invalider_force_le_recalcul(self, app, jeu):
        _, premier = classement_service.classements(jeu["competition"])
        classement_service.invalider(jeu["competition"].id)
        time.sleep(0.01)
        _, second = classement_service.classements(jeu["competition"])
        assert second > premier

    def test_une_nouvelle_reussite_apparait_apres_invalidation(self, app, jeu):
        """Le cas réel : un juge valide, la page doit finir par le montrer."""
        avant, _ = classement_service.classements(jeu["competition"])
        assert avant["U11 F"].lignes[0].score == 0

        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        classement_service.invalider(jeu["competition"].id)

        apres, _ = classement_service.classements(jeu["competition"])
        assert apres["U11 F"].lignes[0].score == 1000


class TestOptionCouleur:
    def setup_method(self):
        classement_service.invalider()

    def test_desactivee_par_defaut(self, app, jeu):
        assert classement_service.couleurs_requises(jeu["competition"]) == 0

    def test_lue_depuis_les_options_de_la_competition(self, app, jeu):
        """L'option est **par compétition**, pas globale : deux éditions
        peuvent avoir des règles différentes."""
        jeu["competition"].options = '{"validation_couleur": 2}'
        db.session.commit()
        assert classement_service.couleurs_requises(jeu["competition"]) == 2

    def test_options_illisibles_ne_font_pas_planter(self, app, jeu):
        jeu["competition"].options = "pas du json"
        db.session.commit()
        assert classement_service.couleurs_requises(jeu["competition"]) == 0

    def test_valeur_absurde_ignoree(self, app, jeu):
        jeu["competition"].options = '{"validation_couleur": "beaucoup"}'
        db.session.commit()
        assert classement_service.couleurs_requises(jeu["competition"]) == 0


class TestIsolationDesCompetitions:
    def test_les_classements_ne_se_melangent_pas(self, app, jeu):
        """La base est multi-compétition : une archive ne doit jamais polluer
        le classement du jour."""
        from climbcontest.models import Competition, Participant
        autre = Competition(nom="Archive 2025", active=False)
        db.session.add(autre)
        db.session.commit()
        db.session.add(Participant(competition_id=autre.id, nom="Ancien",
                                   categorie="U11 F", dossard=1))
        db.session.commit()

        classement_service.invalider()
        resultat, _ = classement_service.classements(jeu["competition"])
        dossards = {l.dossard for c in resultat.values() for l in c.lignes}
        noms = {l.participant_id for c in resultat.values() for l in c.lignes}
        anciens = {p.id for p in Participant.query.filter_by(competition_id=autre.id)}
        assert not (noms & anciens), "un participant d'une autre competition est apparu"
