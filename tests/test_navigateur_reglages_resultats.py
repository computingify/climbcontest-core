"""Deux réglages de la page de résultats — dans un vrai navigateur.

Les deux défauts signalés par Adrien le 02/09 vivent dans le JavaScript de la
page, et un test qui chercherait une chaîne dans le HTML passerait au vert le
jour où quelqu'un déplacerait la garde ailleurs sans la faire marcher. Ceux-là
sont dans `test_page_resultats.py`, et ils tiennent le mécanisme. Ce fichier
tient le RÉSULTAT.

| Ce qu'on pilote | Le défaut |
| --- | --- |
| éteindre un scratch dans la console | « je rafraîchis, rien ne se passe » |
| passer la compétition « En cours » | l'écran projeté restait figé |

Le premier : `groupesVisibles()` filtrait bien, mais `dessinerBarre()` lisait la
charge BRUTE dès qu'on n'était pas en mode mur. La pastille du scratch éteint
restait dans la barre, et son classement à un doigt.

Le second : `programmerRotation` était armée UNE FOIS, 1,2 s après le
chargement. Un mur allumé avant la compétition n'avait alors aucun classement,
la fonction sortait sans rien reprogrammer, et passer la compétition « En
cours » ne la réveillait pas.

⚠️ Ce fichier se saute proprement s'il n'y a pas de navigateur, comme
`test_navigateur_fiche.py` et `test_navigateur_rejeu_archive.py`.
"""
import os
import shutil
import tempfile

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")


def _classement(groupe, type_, circuit=None):
    return {
        "groupe": groupe, "type": type_, "circuit": circuit,
        "lignes": [
            {"participant_id": i, "rang": i, "score": 900 - i * 10, "blocs": 5,
             "credites": 0, "dossard": i, "nom": "Grimpeur %d" % i,
             "club": "Club", "categorie": "U11 F"}
            for i in range(1, 4)
        ],
    }


# Trois scratchs et deux categories : de quoi voir DISPARAITRE quelque chose.
TOUS = [
    _classement("Scratch", "scratch"),
    _classement("U11", "circuit", "U11"),
    _classement("U11 F", "categorie", "U11"),
    _classement("U11 H", "categorie", "U11"),
]
MASQUES = ["Scratch", "U11"]


def _charge(classements, masques):
    return {
        "competition": {"id": 1, "nom": "Test", "statut": "en_cours",
                        "groupes_masques": masques},
        "calcule_le": 0, "age_s": 0.0, "reussites": 12,
        "classements": classements,
    }


# --- Le pilote : ce que la page doit montrer ---------------------------------

SONDE_MASQUE = """
    await attendre("la barre", () => $$("#barre button").length > 0);
    const chips = $$("#barre button").map((b) => b.dataset.groupe);
    note("barre", chips.join(","));
    note("combien", chips.length);
"""

SONDE_ROTATION = """
    // Au depart : aucun classement, la competition n'a pas commence.
    await attendre("page prete", () => !!$("#barre"));
    note("depart", $$("#barre button").length);

    // Les classements arrivent -- c'est le passage « En cours ». La page les
    // relit toute seule ; on n'y touche pas.
    await attendre("classements", () => $$("#barre button").length >= 2, 40000);
    const groupeA = $$("#barre button[aria-current='true']")[0].dataset.groupe;
    note("groupeA", groupeA);

    // Et maintenant, SANS AUCUN CLIC, l'ecran doit passer au suivant.
    await attendre("rotation",
      () => { const b = $$("#barre button[aria-current='true']")[0];
              return b && b.dataset.groupe !== groupeA; }, 30000);
    note("groupeB", $$("#barre button[aria-current='true']")[0].dataset.groupe);
"""


@pytest.fixture()
def serveur():
    """L'application, un vrai serveur, et des sources qui n'existent qu'ici."""
    from flask import Response, jsonify, render_template, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-reglages-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import creer_app
    from climbcontest.config import Config
    from climbcontest.extensions import db

    class ConfigReglages(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "r.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigReglages)
    with app.app_context():
        db.create_all()
    verdict = {"texte": None}
    appels = {"tardif": 0}

    @app.get("/__charge")
    def charge():
        return jsonify(_charge(TOUS, MASQUES))

    @app.get("/__tardif")
    def tardif():
        """Vide d'abord, puis complet : la competition qui passe « En cours ».

        On compte les appels plutot que de regarder l'horloge : la page relit
        toutes les quinze secondes, et c'est CE rythme-la qu'on veut suivre.
        """
        appels["tardif"] += 1
        if appels["tardif"] <= 1:
            return jsonify(_charge([], []))
        return jsonify(_charge(TOUS, []))

    @app.get("/__vue")
    def vue():
        from climbcontest.suivi import plan_public
        return render_template("resultats.html", plan=plan_public(),
                               source=request.args.get("source", "/__charge"))

    @app.post("/__verdict")
    def poser():
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    @app.get("/__harnais")
    def harnais():
        src = request.args.get("src", "/__vue")
        sonde = SONDE_ROTATION if request.args.get("quoi") == "rotation" \
            else SONDE_MASQUE
        return Response(page_harnais(src, sonde), mimetype="text/html")

    url, arreter = servir(app)
    try:
        yield url, verdict, appels
    finally:
        arreter()
        shutil.rmtree(dossier, ignore_errors=True)


def _mesures(rendu):
    assert rendu.startswith("OK "), rendu
    return dict(m.split("=", 1) for m in rendu[3:].split(" ") if "=" in m)


class TestUnClassementEteintDisparaitVRAIMENT:
    """« Si je retire des scratchs de l'affichage de la page résultat et que je
    rafraîchis la page résultat, rien ne se passe. » — Adrien, 02/09."""

    def test_la_barre_du_telephone_ne_montre_plus_le_scratch_eteint(self, serveur):
        url, verdict, _ = serveur
        # HORS mode mur : c'est la page ordinaire qui avait le defaut.
        rendu = piloter(f"{url}/__harnais?src=/__vue", verdict)
        mesures = _mesures(rendu)
        chips = mesures["barre"].split(",")
        for eteint in MASQUES:
            assert eteint not in chips, (eteint, chips)
        # Et ce qui reste est bien la : masquer ne doit pas vider la page.
        assert "U11 F" in mesures["barre"].replace("_", " ")
        assert mesures["combien"] == "2"


class TestLeMurSeMetAJouerToutSeul:
    """« Si je passe la compétition à En cours, je m'attends à ce que la page
    de résultats se mette en play pour passer d'un podium à l'autre. »

    L'écran de la salle est allumé AVANT la compétition. Il n'avait alors aucun
    classement à montrer, et la rotation renonçait pour de bon.
    """

    def test_la_rotation_demarre_quand_les_classements_arrivent(self, serveur):
        url, verdict, appels = serveur
        # `rotation=1` : une seconde par catégorie au lieu de dix. Le paramètre
        # existe déjà pour régler l'écran de la salle ; on ne l'invente pas
        # pour le test.
        rendu = piloter(
            f"{url}/__harnais?quoi=rotation&src=/__vue%3Fsource=/__tardif%26mur%26rotation=1",
            verdict, secondes=90)
        mesures = _mesures(rendu)
        # Au chargement, le mur n'avait RIEN a montrer : c'est la situation qui
        # faisait renoncer la rotation pour de bon.
        assert mesures["depart"] == "0", mesures
        # Puis l'ecran a change de categorie, sans qu'on ait touche a rien.
        assert mesures["groupeA"] != mesures["groupeB"], mesures
        # La page a bien RELU la source : sans ça, on aurait testé une page qui
        # avait tout dès le départ.
        assert appels["tardif"] >= 2, appels
