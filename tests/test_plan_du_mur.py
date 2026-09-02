"""Le plan de la salle se dessine depuis la console (spec 029).

⚠️ Le plan a CHANGÉ DE NATURE. Tant qu'il était une constante Python, il était
du code : relu en revue, impossible à casser depuis un navigateur. Depuis qu'il
se dessine dans la console, c'est de la donnée saisie — et elle est rendue en
SVG sur un papier que cent vingt personnes reçoivent.

D'où le poids donné ici à la validation et au repli.
"""

import json

import pytest

from climbcontest import comptes, fiches, plan_du_mur
from climbcontest.extensions import db
from climbcontest.models import Reglage

MDP = "un-mot-de-passe-de-test"


@pytest.fixture()
def connecte_orga(client, app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


def _plan(**remplace):
    base = {
        "vue": [100, 100],
        "contour": None,
        "murs": [{"zone": "A", "profil": "devers",
                  "points": [[0, 0], [20, 0], [20, 20], [0, 20]],
                  "etiquette": None}],
        "reperes": [{"texte": "Escalier", "point": [50, 50]}],
    }
    base.update(remplace)
    return base


class TestLaConstanteDevientLeDefaut:

    def test_sans_rien_enregistre_c_est_le_plan_d_usine(self, app):
        assert fiches.plan_courant() is fiches.PLAN

    def test_un_plan_enregistre_prend_la_main(self, app):
        plan_du_mur.ecrire(_plan())
        courant = fiches.plan_courant()
        assert courant is not fiches.PLAN
        assert [m["zone"] for m in courant["murs"]] == ["A"]

    def test_les_zones_hors_plan_suivent_le_plan_courant(self, app):
        """Sinon « hors plan » mentirait : il nommerait des zones dessinées, et
        tairait celles qui ne le sont plus."""
        plan_du_mur.ecrire(_plan())
        assert fiches.zones_du_plan() == {"A"}

    def test_effacer_revient_a_l_usine(self, app):
        plan_du_mur.ecrire(_plan())
        assert plan_du_mur.effacer() is True
        assert fiches.plan_courant() is fiches.PLAN

    def test_effacer_sans_rien_ne_ment_pas(self, app):
        assert plan_du_mur.effacer() is False


class TestUneLigneAbimeeNeCassePasUneImpression:
    """⚠️ Une lecture ne peut pas échouer : l'appelant est en train d'imprimer
    des dossards, la veille au soir."""

    def test_un_json_tronque_retombe_sur_l_usine(self, app, caplog):
        db.session.add(Reglage(cle=plan_du_mur.CLE, valeur='{"vue": [100,'))
        db.session.commit()
        assert fiches.plan_courant() is fiches.PLAN

    def test_un_document_valide_json_mais_absurde_aussi(self, app):
        db.session.add(Reglage(cle=plan_du_mur.CLE, valeur='{"vue": "grand"}'))
        db.session.commit()
        assert fiches.plan_courant() is fiches.PLAN

    def test_le_repli_est_journalise(self, app, caplog):
        db.session.add(Reglage(cle=plan_du_mur.CLE, valeur="pas du json"))
        db.session.commit()
        with caplog.at_level("ERROR"):
            fiches.plan_courant()
        assert "plan" in caplog.text.lower()


class TestLaValidationRefuseCeQuiDoitLEtre:

    def test_un_mur_hors_de_la_vue(self):
        mauvais = _plan(murs=[{"zone": "B", "profil": "vertical",
                               "points": [[0, 0], [200, 0], [200, 20]],
                               "etiquette": None}])
        with pytest.raises(plan_du_mur.PlanInvalide) as e:
            plan_du_mur.valider(mauvais)
        assert "zone B" in str(e.value), "le message doit NOMMER le mur fautif"

    def test_un_polygone_a_deux_points(self):
        with pytest.raises(plan_du_mur.PlanInvalide, match="points"):
            plan_du_mur.valider(_plan(murs=[{"zone": "C", "profil": "vertical",
                                             "points": [[0, 0], [10, 0]],
                                             "etiquette": None}]))

    def test_une_vue_absurde(self):
        with pytest.raises(plan_du_mur.PlanInvalide, match="vue"):
            plan_du_mur.valider(_plan(vue=[5, 5]))
        with pytest.raises(plan_du_mur.PlanInvalide, match="vue"):
            plan_du_mur.valider(_plan(vue=[100, 9000]))

    def test_trop_de_murs(self):
        un = {"zone": "A", "profil": "vertical",
              "points": [[0, 0], [10, 0], [10, 10]], "etiquette": None}
        with pytest.raises(plan_du_mur.PlanInvalide, match="maximum"):
            plan_du_mur.valider(_plan(murs=[un] * (plan_du_mur.MURS_MAXI + 1)))

    def test_une_coordonnee_qui_n_est_pas_un_nombre(self):
        with pytest.raises(plan_du_mur.PlanInvalide):
            plan_du_mur.valider(_plan(murs=[{"zone": "A", "profil": "vertical",
                                             "points": [[0, 0], ["dix", 0], [10, 10]],
                                             "etiquette": None}]))

    def test_un_booleen_n_est_pas_une_coordonnee(self):
        """`isinstance(True, int)` vaut vrai en Python : sans garde explicite,
        `True` passerait pour la coordonnée 1."""
        with pytest.raises(plan_du_mur.PlanInvalide):
            plan_du_mur.valider(_plan(murs=[{"zone": "A", "profil": "vertical",
                                             "points": [[0, 0], [True, 0], [10, 10]],
                                             "etiquette": None}]))


class TestCeQuiEstReparableEstRepare:
    """Un plan par ailleurs bon ne doit pas être perdu pour un mot."""

    def test_un_profil_inconnu_se_replie_sur_vertical(self):
        propre = plan_du_mur.valider(
            _plan(murs=[{"zone": "A", "profil": "trampoline",
                         "points": [[0, 0], [10, 0], [10, 10]], "etiquette": None}]))
        assert propre["murs"][0]["profil"] == "vertical"

    def test_une_zone_trop_longue_est_tronquee(self):
        propre = plan_du_mur.valider(
            _plan(murs=[{"zone": "ABCDEF", "profil": "vertical",
                         "points": [[0, 0], [10, 0], [10, 10]], "etiquette": None}]))
        assert propre["murs"][0]["zone"] == "ABC"

    def test_la_zone_est_mise_en_capitales(self):
        propre = plan_du_mur.valider(
            _plan(murs=[{"zone": " j ", "profil": "vertical",
                         "points": [[0, 0], [10, 0], [10, 10]], "etiquette": None}]))
        assert propre["murs"][0]["zone"] == "J"

    def test_un_repere_sans_mot_disparait(self):
        propre = plan_du_mur.valider(_plan(reperes=[{"texte": "  ", "point": [1, 1]}]))
        assert propre["reperes"] == ()

    def test_un_plan_sans_aucun_mur_est_accepte(self):
        """La colonne « Le mur » disparaît du dossard, c'est tout."""
        assert plan_du_mur.valider(_plan(murs=[]))["murs"] == ()


class TestLaRouteDeLaConsole:

    def test_anonyme_ne_voit_rien(self, client, app):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/plan").status_code == 401
        assert client.post("/admin/plan", json=_plan()).status_code == 401
        assert client.delete("/admin/plan").status_code == 401

    def test_la_page_se_rend(self, connecte_orga):
        r = connecte_orga.get("/admin/plan")
        assert r.status_code == 200
        page = r.data.decode()
        assert "PLAN_DU_SERVEUR" in page
        assert "Enregistrer dans ClimbContest" in page

    def test_la_page_n_appelle_rien_a_l_exterieur(self, connecte_orga):
        """La règle du dépôt : on imprime parfois la veille au soir, sans
        réseau. Une police Google suffirait à casser la page."""
        page = connecte_orga.get("/admin/plan").data.decode()
        assert "http://" not in page.replace("http://www.w3.org/2000/svg", "")
        assert "https://" not in page

    def test_enregistrer_puis_relire(self, connecte_orga, app):
        r = connecte_orga.post("/admin/plan", json=_plan())
        assert r.status_code == 200
        d = r.get_json()
        assert d["murs"] == 1 and d["reperes"] == 1
        assert [m["zone"] for m in fiches.plan_courant()["murs"]] == ["A"]

    def test_un_plan_refuse_ne_touche_a_rien(self, connecte_orga, app):
        connecte_orga.post("/admin/plan", json=_plan())
        mauvais = _plan(murs=[{"zone": "Z", "profil": "vertical",
                               "points": [[0, 0], [999, 0], [999, 9]],
                               "etiquette": None}])
        r = connecte_orga.post("/admin/plan", json=mauvais)
        assert r.status_code == 400
        assert "zone Z" in r.get_json()["message"]
        # l'ancien plan est intact
        assert [m["zone"] for m in fiches.plan_courant()["murs"]] == ["A"]

    def test_le_retour_a_l_usine(self, connecte_orga, app):
        connecte_orga.post("/admin/plan", json=_plan())
        assert connecte_orga.delete("/admin/plan").status_code == 200
        assert fiches.plan_courant() is fiches.PLAN

    def test_qui_a_enregistre_est_trace(self, connecte_orga, app):
        connecte_orga.post("/admin/plan", json=_plan())
        assert db.session.get(Reglage, plan_du_mur.CLE).modifie_par == "orga"


class TestLeDossardSuitLePlanEnregistre:
    """Le tour complet : dessiner, enregistrer, imprimer — sans toucher au code."""

    def test_le_dossard_porte_le_nouveau_plan(self, connecte_orga, jeu):
        connecte_orga.post("/admin/plan", json=_plan(
            murs=[{"zone": "Q", "profil": "toit",
                   "points": [[0, 0], [30, 0], [30, 30], [0, 30]],
                   "etiquette": None}]))
        page = connecte_orga.get("/admin/dossards").data.decode()
        assert 'data-zone="Q"' in page
        assert 'data-zone="X"' not in page, "l'ancien plan ne doit plus apparaitre"
