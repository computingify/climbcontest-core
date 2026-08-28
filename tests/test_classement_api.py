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

    def test_la_reponse_ne_divulgue_rien_d_autre(self, client, jeu):
        """Les noms sont publics — ils sont sur les dossards et annonces au micro.

        Le reste ne l'est pas. Ces pages sont ouvertes a tout Internet et
        portent des donnees de MINEURS : chaque champ qui sort doit avoir une
        raison d'etre affiche.
        """
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement").get_json()

        # « blocs » est un COMPTE de blocs reussis, pas la liste des blocs.
        autorises = {"participant_id", "dossard", "nom", "club", "categorie",
                     "score", "rang", "blocs"}
        for classement in d["classements"]:
            for ligne in classement["lignes"]:
                surplus = set(ligne) - autorises
                assert not surplus, f"champ non prevu dans la reponse publique : {surplus}"
                assert isinstance(ligne["blocs"], int), "un compte, pas une liste"

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

    def test_le_cache_expire_au_bout_de_la_fraicheur(self, app, jeu, monkeypatch):
        """Sans expiration, un spectateur verrait le classement de 9 h a 17 h.

        On raccourcit la duree plutot que d'attendre cinq secondes : le test
        doit rester rapide, mais c'est bien le MECANISME d'expiration qu'il
        exerce, pas un appel force.
        """
        monkeypatch.setattr(classement_service, "FRAICHEUR_S", 0.05)
        appels = {"n": 0}
        vrai = classement_service.calculer_tout

        def compter(*a, **k):
            appels["n"] += 1
            return vrai(*a, **k)

        monkeypatch.setattr(classement_service, "calculer_tout", compter)

        classement_service.classements(jeu["competition"])
        classement_service.classements(jeu["competition"])
        assert appels["n"] == 1, "deux appels rapproches : un seul calcul"

        time.sleep(0.08)
        classement_service.classements(jeu["competition"])
        assert appels["n"] == 2, "passe la fraicheur, il faut recalculer"

    def test_une_reussite_arrivee_pendant_la_fraicheur_apparait_ensuite(self, app, jeu, monkeypatch):
        """Jamais un classement a moitie a jour : soit l'ancien, soit le nouveau.

        Le calcul repart toujours de la base — il n'y a pas d'etat incremental a
        desynchroniser. La reussite arrivee entre-temps est donc simplement
        prise au calcul suivant, entiere.
        """
        monkeypatch.setattr(classement_service, "FRAICHEUR_S", 0.05)

        def score(dossard=1):
            tous, _ = classement_service.classements(jeu["competition"])
            ligne = next(l for l in tous["U11 F"].lignes if l.dossard == dossard)
            return ligne.score

        assert score() == 0, "aucune reussite au depart"

        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        assert score() == 0, "pendant la fraicheur, l'ancien resultat tient"

        time.sleep(0.08)
        assert score() == 1000, "au calcul suivant, la reussite est prise"

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


class TestSourceDesReussites:
    def test_une_reussite_saisie_a_la_main_compte_comme_un_scan(self, app, jeu):
        """La saisie manuelle existe parce qu'un QR peut etre illisible.

        Si le classement ignorait ces reussites, le grimpeur serait penalise
        pour un probleme d'impression — et personne ne le verrait, puisque la
        reussite EST bien en base.
        """
        from climbcontest.models import SOURCE_MANUEL, SOURCE_SCAN

        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0],
                             source=SOURCE_MANUEL)
        enregistrer_reussite(jeu["participants"][1], jeu["blocs"][0],
                             source=SOURCE_SCAN)

        tous, _ = classement_service.classements(jeu["competition"])

        manuel = next(l for l in tous["U11 F"].lignes
                      if l.participant_id == jeu["participants"][0].id)
        scan = next(l for l in tous["U13 H"].lignes
                    if l.participant_id == jeu["participants"][1].id)
        assert manuel.score > 0, "une reussite manuelle doit rapporter"
        assert manuel.blocs_reussis == 1
        # Chacun est seul sur ce bloc DANS SON GROUPE : meme valeur des deux
        # cotes, ce qui isole exactement la variable « source ».
        assert manuel.score == scan.score


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
