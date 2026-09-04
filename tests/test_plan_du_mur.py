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

    def test_le_retour_a_la_console_mene_a_la_console(self, connecte_orga, client):
        """⚠️ Le lien pointait sur `/admin`, et rendait « Not Found ».

        `/admin` est le PREFIXE des routes JSON — `/admin/plan`,
        `/admin/classeur`, `/admin/dossards` — et aucune ne repond a la racine
        du prefixe. L'editeur du plan devenait un cul-de-sac : une fois dedans,
        le seul retour etait le bouton du navigateur. Signale par Adrien le
        02/09.

        On ne se contente pas de comparer la chaine : on DEMANDE l'adresse au
        serveur. C'est ce qui aurait attrape le defaut.
        """
        import re

        page = connecte_orga.get("/admin/plan").data.decode()
        liens = re.findall(r'<a class="faux-bouton" href="([^"]+)"', page)
        assert liens, "plus de lien de retour vers la console"
        for adresse in liens:
            assert client.get(adresse).status_code == 200, adresse

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


class TestLePlanVoyageAvecLeCatalogue:
    """⚠️ Adrien : « pourquoi tu ne pousses pas le plan sur l'application ou le
    navigateur [...] comme la base grimpeur avec un système d'update ? »

    La vraie raison de le faire n'est pas l'économie de requêtes : c'est que le
    plan devient **versionné**. Servi par une route à part, un client garderait
    un mur périmé sans aucun moyen de le savoir.
    """

    def test_le_catalogue_porte_le_plan(self, client, jeu):
        d = client.get("/api/v2/catalog").get_json()
        assert "plan" in d
        assert [m["zone"] for m in d["plan"]["murs"]][:2] == ["X", "Y"]

    def test_il_porte_le_plan_ENREGISTRE_pas_celui_d_usine(self, connecte_orga, jeu):
        connecte_orga.post("/admin/plan", json=_plan())
        d = connecte_orga.get("/api/v2/catalog").get_json()
        assert [m["zone"] for m in d["plan"]["murs"]] == ["A"]

    def test_enregistrer_un_plan_incremente_la_version(self, connecte_orga, jeu):
        avant = connecte_orga.get("/api/v2/catalog").get_json()["version"]
        connecte_orga.post("/admin/plan", json=_plan())
        apres = connecte_orga.get("/api/v2/catalog").get_json()["version"]
        assert apres > avant, "sans ca, les clients garderaient un mur perime"

    def test_un_client_a_jour_avant_le_changement_recoit_le_nouveau_plan(
            self, connecte_orga, jeu):
        """Le scenario complet : un telephone a la version N, on enregistre un
        plan, il redemande avec N -- il doit recevoir 200 et le nouveau mur, pas
        un 304."""
        version = connecte_orga.get("/api/v2/catalog").get_json()["version"]
        assert connecte_orga.get(f"/api/v2/catalog?depuis={version}").status_code == 304

        connecte_orga.post("/admin/plan", json=_plan())

        r = connecte_orga.get(f"/api/v2/catalog?depuis={version}")
        assert r.status_code == 200
        assert [m["zone"] for m in r.get_json()["plan"]["murs"]] == ["A"]

    def test_le_retour_a_l_usine_incremente_aussi(self, connecte_orga, jeu):
        connecte_orga.post("/admin/plan", json=_plan())
        avant = connecte_orga.get("/api/v2/catalog").get_json()["version"]
        connecte_orga.delete("/admin/plan")
        assert connecte_orga.get("/api/v2/catalog").get_json()["version"] > avant

    def test_le_304_fonctionne_toujours_quand_rien_ne_bouge(self, client, jeu):
        version = client.get("/api/v2/catalog").get_json()["version"]
        assert client.get(f"/api/v2/catalog?depuis={version}").status_code == 304

    def test_dessiner_hors_saison_ne_fait_pas_echouer(self, connecte_orga, app):
        """Aucune compétition active : il n'y a personne à prévenir, et
        dessiner le plan en janvier est parfaitement legitime."""
        r = connecte_orga.post("/admin/plan", json=_plan())
        assert r.status_code == 200
        assert [m["zone"] for m in fiches.plan_courant()["murs"]] == ["A"]


class TestLesQuatreCheminsDeCoordonneesSontBornes:
    """⚠️ Seuls les points de MUR étaient bornés. L'étiquette, le point d'un
    repère et le contour ne voyaient que « c'est un nombre ».

    Le contour hors vue est atteignable par le RECOLLAGE, que la spec 029 §3
    documente comme le chemin de retour arrière : il partait tel quel dans le
    catalogue, où un rendu à l'échelle écrase toute la salle en un point.
    """

    def test_une_etiquette_hors_de_la_vue(self):
        with pytest.raises(plan_du_mur.PlanInvalide, match="étiquette"):
            plan_du_mur.valider(_plan(murs=[{
                "zone": "A", "profil": "vertical",
                "points": [[0, 0], [10, 0], [10, 10]], "etiquette": [500, 500]}]))

    def test_un_repere_hors_de_la_vue(self):
        with pytest.raises(plan_du_mur.PlanInvalide, match="Sortie"):
            plan_du_mur.valider(_plan(reperes=[{"texte": "Sortie",
                                                "point": [99999, 0]}]))

    def test_un_contour_hors_de_la_vue(self):
        with pytest.raises(plan_du_mur.PlanInvalide, match="contour"):
            plan_du_mur.valider(_plan(contour=[[0, 0], [99999, 0], [0, 88888]]))

    def test_un_contour_de_quatre_cents_points(self):
        with pytest.raises(plan_du_mur.PlanInvalide, match="maximum"):
            plan_du_mur.valider(_plan(contour=[[1, 1]] * 400))


class TestLeNonFiniNeDoitJamaisPasser:
    """⚠️ Le cas le plus grave trouvé en relecture, et il ne touche PAS que le
    plan.

    `json.loads` accepte `NaN` et `Infinity` par défaut, `json.dumps` les
    réécrit tels quels. Un seul `NaN` rendait le CATALOGUE ENTIER illisible
    pour un analyseur strict : le téléphone du juge ne perdait pas le plan, il
    perdait la synchronisation des participants, des blocs et des circuits —
    en silence.
    """

    @pytest.mark.parametrize("valeur", [float("nan"), float("inf"), float("-inf")])
    def test_dans_un_point_de_mur(self, valeur):
        with pytest.raises(plan_du_mur.PlanInvalide):
            plan_du_mur.valider(_plan(murs=[{
                "zone": "A", "profil": "vertical",
                "points": [[0, 0], [valeur, 0], [10, 10]], "etiquette": None}]))

    def test_dans_une_etiquette(self):
        with pytest.raises(plan_du_mur.PlanInvalide):
            plan_du_mur.valider(_plan(murs=[{
                "zone": "A", "profil": "vertical",
                "points": [[0, 0], [10, 0], [10, 10]],
                "etiquette": [float("nan"), 1]}]))

    def test_le_catalogue_reste_lisible_par_un_analyseur_strict(self, connecte_orga, jeu):
        """Le test qui compte : ce n'est pas le plan qu'on protège, c'est tout
        ce qui voyage avec lui."""
        connecte_orga.post("/admin/plan", json=_plan())
        brut = connecte_orga.get("/api/v2/catalog").data.decode()

        def refuse(constante):
            raise AssertionError(f"le catalogue porte « {constante} » : "
                                 "un analyseur strict le rejettera en entier")

        json.loads(brut, parse_constant=refuse)


class TestLesBornesAnnonceesParLaSpec:
    """Chaque ligne du tableau F5 de la spec 029, éprouvée."""

    def test_plus_de_cinquante_reperes(self):
        un = {"texte": "R", "point": [1, 1]}
        with pytest.raises(plan_du_mur.PlanInvalide, match="maximum"):
            plan_du_mur.valider(_plan(reperes=[un] * (plan_du_mur.REPERES_MAXI + 1)))

    def test_plus_de_soixante_points_sur_un_mur(self):
        with pytest.raises(plan_du_mur.PlanInvalide, match="points"):
            plan_du_mur.valider(_plan(murs=[{
                "zone": "A", "profil": "vertical",
                "points": [[1, 1]] * (plan_du_mur.POINTS_MAXI + 1),
                "etiquette": None}]))

    def test_un_texte_de_repere_trop_long_est_tronque(self):
        propre = plan_du_mur.valider(_plan(reperes=[
            {"texte": "S" * 80, "point": [1, 1]}]))
        assert len(propre["reperes"][0]["texte"]) == plan_du_mur.TEXTE_MAXI

    def test_un_document_trop_gros_repond_413(self, connecte_orga, app):
        """⚠️ La spec promet 413, pas 400 — et le contrôle doit venir AVANT
        l'analyse : le vérifier après `valider()` faisait construire quatre
        cent mille tuples avant de refuser."""
        enorme = _plan(reperes=[{"texte": "S", "point": [1, 1]}] * 20000)
        r = connecte_orga.post("/admin/plan", json=enorme)
        assert r.status_code == 413


class TestLesRolesEtLesReparationsSontVisibles:

    def test_un_role_insuffisant_est_refuse(self, client, app):
        """A2 ne testait que l'anonyme.

        ⚠️ Le dépôt n'a que deux rôles, et `organisateur` est le plus bas :
        le 403 n'est atteignable que par un compte SANS rôle — celui qu'on a
        créé puis dont on a retiré les droits. C'est exactement le cas que
        `test_audit_novembre` protège pour le réimport, et il vaut ici aussi :
        dessiner le mur réécrit ce que cent vingt dossards vont porter.
        """
        from climbcontest.comptes import _hacher as hacher

        from climbcontest.models import Utilisateur

        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        # Fabriqué EN BASE : l'API de comptes refuse un compte sans rôle
        # (« ne sert à rien »), et c'est précisément pour ça que ce test est de
        # la défense en profondeur — même un compte apparu par un chemin
        # imprévu ne doit pas pouvoir redessiner le mur.
        db.session.add(Utilisateur(identifiant="sans_droit",
                                   mot_de_passe_hache=hacher(MDP),
                                   actif=True))
        db.session.commit()
        client.post("/admin/connexion", json={"identifiant": "sans_droit",
                                              "mot_de_passe": MDP})
        assert client.get("/admin/plan").status_code == 403
        assert client.post("/admin/plan", json=_plan()).status_code == 403
        assert client.delete("/admin/plan").status_code == 403

    def test_l_enregistrement_renvoie_le_plan_TEL_QU_IL_A_ETE_RANGE(
            self, connecte_orga, app):
        """⚠️ Le serveur répare en silence. La page affirmait ensuite « le plan
        enregistré est celui affiché » : recoller « abcd » laissait « abcd » à
        l'écran quand le dossard imprimait « ABC »."""
        r = connecte_orga.post("/admin/plan", json=_plan(murs=[{
            "zone": "abcd", "profil": "trampoline",
            "points": [[0, 0], [10, 0], [10, 10]], "etiquette": None}]))
        assert r.status_code == 200
        rendu = r.get_json()["plan"]
        assert rendu["murs"][0]["zone"] == "ABC"
        assert rendu["murs"][0]["profil"] == "vertical"

    def test_le_retour_a_l_usine_renvoie_le_plan_d_usine(self, connecte_orga, app):
        """Sans ça, la page réaffichait le plan qu'elle venait de supprimer."""
        connecte_orga.post("/admin/plan", json=_plan())
        rendu = connecte_orga.delete("/admin/plan").get_json()["plan"]
        assert len(rendu["murs"]) == len(fiches.PLAN["murs"])


class TestUnPlanVideNeLaissePasUnCadreVide:
    """Les deux specs le demandent (028 §5, 029 §5) et la colonne se rendait
    quand même : trente-sept millimètres de titre et de filet, sans un trait
    dedans, sur cent vingt fiches."""

    def test_la_colonne_disparait(self, connecte_orga, jeu):
        connecte_orga.post("/admin/plan", json=_plan(murs=[], reperes=[]))
        page = connecte_orga.get("/admin/dossards").data.decode()
        assert 'class="mur"' not in page
        assert "Le mur" not in page

    def test_elle_reste_des_qu_il_y_a_quelque_chose_a_montrer(
            self, connecte_orga, jeu):
        connecte_orga.post("/admin/plan", json=_plan(murs=[]))
        page = connecte_orga.get("/admin/dossards").data.decode()
        assert 'class="mur"' in page, "un repère seul mérite encore le plan"
