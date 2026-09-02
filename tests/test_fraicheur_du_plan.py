"""Le mur redessiné ne peut plus rester invisible sur le téléphone d'un juge.

Le plan voyage **dans** le catalogue (spec 029, « Le catalogue »), et c'est
délibéré : servi par une route à part, un client garderait un mur périmé sans
aucun moyen de le savoir. Toute la protection tient donc au numéro de version —
et ce numéro appartenait à une compétition alors que le plan est **global**.

⚠️ **Deux propriétés se contredisent, et c'est là que vit le défaut.**

1. `/api/v2/catalog` décide son 304 par **égalité stricte** (correctif du
   30/08) : un client qui annonce un numéro venu d'ailleurs n'est pas à jour.
   Un numéro identifie donc un couple (édition, état de son catalogue), et deux
   éditions ne peuvent pas porter le même.
2. Le plan est global : le changer doit périmer le catalogue de **toutes** les
   éditions.

Un compteur unique partagé satisferait (2) et casserait (1). C'est pour ça que
la correction tire un numéro **neuf par édition** plutôt que d'en partager un.
"""
from datetime import date

import pytest

from climbcontest import plan_du_mur
from climbcontest.extensions import db
from climbcontest.models import Competition, EN_COURS

PLAN = {
    "vue": [100, 100],
    "murs": [{"zone": "Z", "profil": "dalle",
              "points": [[0, 0], [40, 0], [40, 40], [0, 40]]}],
    "reperes": [],
    "contour": None,
}
AUTRE_PLAN = {
    "vue": [100, 100],
    "murs": [{"zone": "D", "profil": "toit",
              "points": [[10, 10], [90, 10], [90, 50]]}],
    "reperes": [],
    "contour": None,
}


def editer(nom, active):
    comp = Competition(nom=nom, date=date(2026, 11, 15), statut=EN_COURS,
                       active=active, spreadsheet_id="fictif")
    db.session.add(comp)
    db.session.commit()
    return comp


@pytest.fixture()
def deux_editions(app):
    """Mars et novembre. Une seule est active à la fois, comme en vrai."""
    mars = editer("Mars 2026", False)
    novembre = editer("Novembre 2026", True)
    return mars, novembre


class TestUnPlanRedessineHorsSaison:
    """Le cas qui laissait un mur périmé sur un téléphone.

    On redessine le mur **entre** deux compétitions — le moment le plus naturel
    pour le faire — puis on rouvre la saison.
    """

    def test_sans_edition_active_les_versions_bougent_quand_meme(
            self, app, deux_editions):
        mars, novembre = deux_editions
        novembre.active = False
        db.session.commit()
        avant = (mars.catalogue_version, novembre.catalogue_version)

        plan_du_mur.ecrire(PLAN, par="chef")

        apres = (mars.catalogue_version, novembre.catalogue_version)
        assert apres[0] != avant[0] and apres[1] != avant[1], (
            "aucune edition n'a ete prevenue du changement de mur alors "
            "qu'aucune n'etait active : c'est le trou qu'on ferme")

    def test_le_telephone_reprend_le_catalogue_a_la_reouverture(
            self, client, app, deux_editions):
        """Le geste complet, vu du téléphone : il connaît la version N, le mur
        change pendant que tout est fermé, la saison rouvre — il doit
        retélécharger."""
        mars, novembre = deux_editions
        plan_du_mur.ecrire(PLAN, par="chef")
        connue = client.get("/api/v2/catalog").get_json()["version"]

        # On ferme, on redessine, on rouvre.
        novembre.active = False
        db.session.commit()
        plan_du_mur.ecrire(AUTRE_PLAN, par="chef")
        novembre.active = True
        db.session.commit()

        r = client.get(f"/api/v2/catalog?depuis={connue}")
        assert r.status_code == 200, (
            "304 apres un mur redessine hors saison : le juge garde l'ancien "
            "mur et rien ne le lui dit")
        assert {m["zone"] for m in r.get_json()["plan"]["murs"]} == {"D"}

    def test_par_l_etiquette_aussi(self, client, app, deux_editions):
        """`If-None-Match` est l'autre façon de dire « j'ai déjà la version N ».
        Les deux chemins mènent au même 304, donc les deux doivent se fermer."""
        novembre = deux_editions[1]
        plan_du_mur.ecrire(PLAN, par="chef")
        etiquette = client.get("/api/v2/catalog").headers["ETag"]

        novembre.active = False
        db.session.commit()
        plan_du_mur.ecrire(AUTRE_PLAN, par="chef")
        novembre.active = True
        db.session.commit()

        r = client.get("/api/v2/catalog", headers={"If-None-Match": etiquette})
        assert r.status_code == 200


class TestLesNumerosRestentPropresAChaqueEdition:
    """⚠️ La contrainte que la correction ne doit pas casser.

    Prévenir toutes les éditions ne doit pas revenir à leur donner le **même**
    numéro : le 304 se décide par égalité stricte, et un numéro partagé ferait
    répondre « rien de neuf » à un téléphone qui vient de changer d'édition et
    qui a besoin d'une autre liste de participants.
    """

    def test_deux_editions_ne_portent_jamais_le_meme_numero(
            self, app, deux_editions):
        mars, novembre = deux_editions
        plan_du_mur.ecrire(PLAN, par="chef")
        assert mars.catalogue_version != novembre.catalogue_version

        plan_du_mur.ecrire(AUTRE_PLAN, par="chef")
        assert mars.catalogue_version != novembre.catalogue_version

    def test_changer_d_edition_active_ne_rend_jamais_304(
            self, client, app, deux_editions):
        """Le téléphone a le catalogue de novembre ; on bascule sur mars. Il
        doit retélécharger — les participants ne sont pas les mêmes."""
        mars, novembre = deux_editions
        plan_du_mur.ecrire(PLAN, par="chef")
        connue = client.get("/api/v2/catalog").get_json()["version"]

        novembre.active = False
        mars.active = True
        db.session.commit()

        r = client.get(f"/api/v2/catalog?depuis={connue}")
        assert r.status_code == 200, (
            "304 en changeant d'edition active : le juge scannerait avec la "
            "liste de participants de l'autre competition")

    def test_les_numeros_ne_reculent_jamais(self, app, deux_editions):
        """L'horloge est commune et monotone : un numéro déjà servi ne revient
        pas. Sans ça, un client pourrait retrouver un numéro qu'il connaît et
        se croire à jour sur un catalogue qui a changé deux fois."""
        mars, novembre = deux_editions
        vus = set()
        for plan in (PLAN, AUTRE_PLAN, PLAN, AUTRE_PLAN):
            plan_du_mur.ecrire(plan, par="chef")
            couple = (mars.catalogue_version, novembre.catalogue_version)
            assert not (set(couple) & vus), (
                "un numero deja servi est reapparu : " + repr(couple))
            vus |= set(couple)


class TestEffacerLePlanPrevientAussi:
    """La sortie de secours de la spec 029 F4 — le geste qu'on fait **en
    compétition** quand un dessin part de travers. C'est là que rater la
    fraîcheur coûte le plus cher."""

    def test_revenir_au_plan_d_usine_perime_les_catalogues(
            self, client, app, deux_editions):
        plan_du_mur.ecrire(PLAN, par="chef")
        connue = client.get("/api/v2/catalog").get_json()["version"]

        assert plan_du_mur.effacer() is True

        r = client.get(f"/api/v2/catalog?depuis={connue}")
        assert r.status_code == 200
        from climbcontest.fiches import PLAN as USINE
        assert ({m["zone"] for m in r.get_json()["plan"]["murs"] if m["zone"]}
                == {m["zone"] for m in USINE["murs"] if m["zone"]})

    def test_un_effacement_sans_plan_enregistre_ne_previent_personne(
            self, app, deux_editions):
        """Rien n'a changé : personne n'a à retélécharger. Une version qui
        bouge sans raison ferait retélécharger soixante téléphones pour rien."""
        mars, novembre = deux_editions
        avant = (mars.catalogue_version, novembre.catalogue_version)
        assert plan_du_mur.effacer() is False
        assert (mars.catalogue_version, novembre.catalogue_version) == avant


class TestSansAucuneEdition:
    """Une base toute neuve : le plan s'enregistre, et ça ne lève pas.

    C'est le cas du premier démarrage, et il n'a personne à prévenir — la route
    du catalogue refuse déjà de servir sans compétition active.
    """

    def test_enregistrer_un_plan_ne_leve_pas(self, app):
        propre = plan_du_mur.ecrire(PLAN, par="chef")
        assert [m["zone"] for m in propre["murs"]] == ["Z"]
        assert plan_du_mur.lire() is not None
