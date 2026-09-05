"""L'écran Catégories : le tableau, les interrupteurs, le rattrapage — spec 045.

Le rattrapage (D6) est la seule opération de cette spec qui **change des
données déjà en base**. Elle en porte donc les garanties : l'aperçu ne touche à
rien, l'application incrémente le catalogue des juges, et ce qui n'a pas de
cible reste en place.
"""

import pytest

from climbcontest import categories, comptes
from climbcontest.extensions import db
from climbcontest.models import Participant

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, competition):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


def poser(comp, nom, categorie, dossard=None):
    p = Participant(competition_id=comp.id, nom=nom, categorie=categorie,
                    dossard=dossard)
    db.session.add(p)
    db.session.commit()
    return p


class TestLeTableau:
    """Un seul tableau depuis D5 : les années, les inscrits, les deux genres."""

    def test_neuf_lignes_meme_sur_une_edition_vide(self, connecte, competition):
        d = connecte.get("/admin/categories").get_json()
        assert [l["nom"] for l in d["tableau"]] == list(categories.OFFICIELLES)

    def test_les_annees_suivent_la_date_de_l_edition(self, connecte, competition):
        """Compétition du 15/11/2026 → saison 2026-2027 → référence 2027."""
        u13 = [l for l in connecte.get("/admin/categories").get_json()["tableau"]
               if l["nom"] == "U13"][0]
        assert (u13["annee_min"], u13["annee_max"]) == (2015, 2016)
        assert (u13["age_min"], u13["age_max"]) == (11, 12)

    def test_changer_la_date_decale_les_annees(self, connecte, competition):
        """« Que les années soient automatiquement mises à jour » — Adrien.

        Rien n'est figé en base : l'année de référence se relit à chaque
        ouverture de l'écran.
        """
        from datetime import date
        competition.date = date(2025, 11, 15)
        db.session.commit()
        u13 = [l for l in connecte.get("/admin/categories").get_json()["tableau"]
               if l["nom"] == "U13"][0]
        assert (u13["annee_min"], u13["annee_max"]) == (2014, 2015)

    def test_senior_et_veteran_n_ont_pas_d_annees(self, connecte, competition):
        """« U » veut dire under : ces deux-là n'en portent pas, et le barème
        ne les attribuera jamais tout seul."""
        par_nom = {l["nom"]: l for l in
                   connecte.get("/admin/categories").get_json()["tableau"]}
        for nom in ("Senior", "Veteran"):
            assert par_nom[nom]["hors_bareme"] is True
            assert par_nom[nom]["annee_min"] is None

    def test_les_inscrits_comptent_les_deux_genres(self, connecte, competition):
        poser(competition, "A", "U13 F")
        poser(competition, "B", "U13 H")
        poser(competition, "C", "U15 F")
        par_nom = {l["nom"]: l for l in
                   connecte.get("/admin/categories").get_json()["tableau"]}
        assert par_nom["U13"]["inscrits"] == 2
        assert par_nom["U15"]["inscrits"] == 1
        assert par_nom["U21"]["inscrits"] == 0

    def test_les_interrupteurs_disent_ce_qui_est_declare(self, connecte, competition):
        connecte.post("/admin/categories/declarees",
                      json={"categories": ["U13 F", "U15 H"]})
        par_nom = {l["nom"]: l for l in
                   connecte.get("/admin/categories").get_json()["tableau"]}
        assert par_nom["U13"]["declarees"] == {"F": True, "H": False}
        assert par_nom["U15"]["declarees"] == {"F": False, "H": True}
        assert par_nom["U9"]["declarees"] == {"F": False, "H": False}

    def test_les_annees_montrees_sont_celles_de_l_edition(self, connecte, competition):
        """⚠️ Deux barèmes se croisent, et on montre le bon.

        Une édition qui annonce U11 et U15 sans U13 donne à U15 les âges 11 à
        14 — « le plus petit Under l'emporte ». Montrer 13-14, ce que dit la
        fédération, annoncerait ce qui ne se produira pas.
        """
        connecte.post("/admin/categories/declarees",
                      json={"categories": ["U11 F", "U11 H", "U15 F", "U15 H"]})
        par_nom = {l["nom"]: l for l in
                   connecte.get("/admin/categories").get_json()["tableau"]}
        assert (par_nom["U15"]["age_min"], par_nom["U15"]["age_max"]) == (11, 14)
        # U13 est éteinte : elle montre ce qu'elle DEVIENDRAIT, en grisé.
        assert par_nom["U13"]["dans_le_bareme"] is False
        assert (par_nom["U13"]["age_min"], par_nom["U13"]["age_max"]) == (11, 12)


class TestCeQuiEstDeclare:
    def test_l_officiel_est_accepte(self, connecte, competition):
        r = connecte.post("/admin/categories/declarees",
                          json={"categories": ["U13 F", "U13 H"]})
        assert r.status_code == 200
        assert r.get_json()["categories"] == ["U13 F", "U13 H"]

    def test_une_ecriture_de_travers_est_rattachee(self, connecte, competition):
        r = connecte.post("/admin/categories/declarees",
                          json={"categories": ["u13f", " 13 h "]})
        assert r.get_json()["categories"] == ["U13 F", "U13 H"]

    def test_l_inconnue_est_refusee_et_le_dit(self, connecte, competition):
        """Sans ce refus, « Poussin » serait rangé « POUSSIN », n'apporterait
        aucun Under au barème, et ne dirait pas pourquoi."""
        r = connecte.post("/admin/categories/declarees",
                          json={"categories": ["U13 F", "Poussin"]})
        assert r.status_code == 400
        assert "Poussin" in r.get_json()["message"]

    def test_le_refus_n_ecrit_rien(self, connecte, competition):
        connecte.post("/admin/categories/declarees", json={"categories": ["U13 F"]})
        connecte.post("/admin/categories/declarees",
                      json={"categories": ["U15 F", "Poussin"]})
        d = connecte.get("/admin/categories").get_json()
        assert d["declarees"] == ["U13 F"]


class TestLeRattrapage:
    """D6 : le « U13 M » du 30/08, corrigé d'un clic devant son aperçu."""

    def test_ce_qui_est_hors_liste_est_montre_avec_sa_cible(self, connecte, competition):
        poser(competition, "Seul", "U13 M", dossard=1)
        poser(competition, "Autre", "U13 H", dossard=2)
        d = connecte.get("/admin/categories").get_json()
        assert d["hors_liste"] == [
            {"valeur": "U13 M", "cible": "U13 H", "inscrits": 1}]

    def test_rien_a_rattraper_rend_une_liste_vide(self, connecte, competition):
        poser(competition, "A", "U13 H")
        assert connecte.get("/admin/categories").get_json()["hors_liste"] == []

    def test_sans_cible_la_ligne_est_montree_quand_meme(self, connecte, competition):
        """On ne choisit pas à la place de quelqu'un ce que « Poussin »
        voulait dire — mais on ne le cache pas non plus."""
        poser(competition, "A", "POUSSIN")
        assert connecte.get("/admin/categories").get_json()["hors_liste"] == [
            {"valeur": "POUSSIN", "cible": None, "inscrits": 1}]

    def test_l_apercu_ne_change_rien(self, connecte, competition):
        p = poser(competition, "Seul", "U13 M")
        avant = competition.catalogue_version
        r = connecte.post("/admin/categories/rattacher", json={"apercu": True})
        assert r.get_json()["hors_liste"][0]["cible"] == "U13 H"
        db.session.refresh(p)
        assert p.categorie == "U13 M"
        assert competition.catalogue_version == avant

    def test_appliquer_rattache(self, connecte, competition):
        p = poser(competition, "Seul", "U13 M")
        r = connecte.post("/admin/categories/rattacher", json={})
        assert r.get_json()["rattaches"] == 1
        db.session.refresh(p)
        assert p.categorie == "U13 H"

    def test_appliquer_incremente_le_catalogue(self, connecte, competition):
        """⚠️ Sans ça, les vingt-cinq téléphones gardent l'ancienne catégorie
        pour toute la compétition : elle voyage dans le catalogue."""
        poser(competition, "Seul", "U13 M")
        avant = competition.catalogue_version
        connecte.post("/admin/categories/rattacher", json={})
        db.session.refresh(competition)
        assert competition.catalogue_version > avant

    def test_ce_qui_n_a_pas_de_cible_reste_en_place(self, connecte, competition):
        rattachable = poser(competition, "A", "U13 M")
        garde = poser(competition, "B", "POUSSIN")
        r = connecte.post("/admin/categories/rattacher", json={})
        assert r.get_json()["rattaches"] == 1
        db.session.refresh(rattachable)
        db.session.refresh(garde)
        assert rattachable.categorie == "U13 H"
        assert garde.categorie == "POUSSIN"
        # Et il reste visible : la carte ne disparaît pas tant qu'il est là.
        assert r.get_json()["hors_liste"] == [
            {"valeur": "POUSSIN", "cible": None, "inscrits": 1}]

    def test_rattacher_deux_fois_ne_fait_rien_la_seconde(self, connecte, competition):
        poser(competition, "Seul", "U13 M")
        connecte.post("/admin/categories/rattacher", json={})
        assert connecte.post("/admin/categories/rattacher",
                             json={}).get_json()["rattaches"] == 0

    def test_tous_ceux_qui_portent_la_valeur_bougent(self, connecte, competition):
        for i in range(3):
            poser(competition, f"P{i}", "U13 M", dossard=i + 1)
        assert connecte.post("/admin/categories/rattacher",
                             json={}).get_json()["rattaches"] == 3


class TestCEstFerme:
    def test_sans_session(self, client_sans_cle, app, competition):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        for route in ("/admin/categories", "/admin/categories/rattacher"):
            methode = (client_sans_cle.get if route.endswith("categories")
                       else client_sans_cle.post)
            assert methode(route).status_code == 401
