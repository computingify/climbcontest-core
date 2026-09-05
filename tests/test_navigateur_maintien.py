"""Le geste de MAINTIEN de `dlgConfirmer`, dans un vrai navigateur.

⚠️ CE FICHIER EXISTE PARCE QUE CE CHEMIN N'EN AVAIT AUCUN. Le bouton à
maintenir garde une compétition entière d'un effacement accidentel depuis la
spec 032, et rien ne vérifiait qu'il MARCHE — seulement qu'il était dans le
gabarit. Sa mécanique vient d'être sortie du gabarit vers
`static/console/confirmer.js`, partagée avec l'écran d'ouverture (spec 044) :
un refactor sur un geste destructeur sans filet, c'est exactement ce qu'on ne
fait pas.

Ce qu'on vérifie ici, et qu'aucun test de route ne peut voir : relâcher trop
tôt n'efface rien, tenir deux secondes efface, et Échap pendant un maintien
tue le minuteur au lieu de le laisser aboutir sur une fenêtre fermée.
"""
import os
import shutil
import tempfile
from datetime import date

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")

ECRAN = (1280, 1200)
MDP = "un-mot-de-passe-assez-long"

ATTENDUES = [
    "dialogueOuvert", "libelleAnnonceLaDuree",
    "libellePendantLeMaintien", "boutonTenu", "relacheTropTot",
    "libelleRevenu", "apresEchap", "dialogueFerme", "tenuJusquAuBout",
    "effacementFait",
]

SONDE = r"""
    const doc = () => cadre.contentDocument;
    const visible = (el) => !!(el && el.offsetParent !== null);
    const dlg = () => $("#dlgConfirmer");
    const bouton = () => $("#dlgOk");
    // Un maintien REEL : `pointerdown`, on attend, `pointerup`. Cliquer ne
    // declenche rien -- c'est tout l'objet du geste.
    const tenir = (ms) => {
      bouton().dispatchEvent(new (vue().PointerEvent)("pointerdown", {bubbles: true}));
      return new Promise((f) => vue().setTimeout(f, ms));
    };
    const lacher = () =>
      bouton().dispatchEvent(new (vue().PointerEvent)("pointerup", {bubbles: true}));

    await attendre("formulaire de connexion", () => $("#identifiant") !== null);
    $("#identifiant").value = "chef";
    $("#motdepasse").value = "un-mot-de-passe-assez-long";
    $("#formConnexion").dispatchEvent(new (vue().Event)("submit", {cancelable: true}));
    await attendre("console ouverte", () => visible($("#console")));

    $('[data-vue="classeur"]').click();
    await attendre("ecran classeur", () => visible($("#vueClasseur")));

    // --- 1. La fenetre s'ouvre, et le bouton ANNONCE le geste ------------
    $("#btnEffacer").click();
    await attendre("dialogue ouvert", () => dlg().open);
    note("dialogueOuvert", dlg().open);
    note("libelleAnnonceLaDuree",
      $("#dlgOkMot").textContent.indexOf("Maintenir 2 s") === 0);

    // --- 2. Relacher trop tot n'efface RIEN ------------------------------
    await tenir(700);
    // ⚠️ LA MESURE QUI PROUVE QUE LE GESTE A DEMARRE. Sans elle, « rien ne
    // s'est passe » serait vrai aussi quand le bouton est desactive -- et le
    // test passerait sans avoir rien essaye. C'est arrive.
    note("libellePendantLeMaintien",
      $("#dlgOkMot").textContent.indexOf("Encore") === 0);
    note("boutonTenu", bouton().classList.contains("tenu"));
    lacher();
    await new Promise((f) => vue().setTimeout(f, 200));
    note("relacheTropTot", dlg().open);          // toujours ouverte
    note("libelleRevenu",
      $("#dlgOkMot").textContent.indexOf("Maintenir 2 s") === 0);

    // --- 3. Echap pendant un maintien tue le minuteur --------------------
    // ⚠️ Sans la remise a plat, le minuteur aboutissait sur une fenetre deja
    // fermee -- et refermait la suivante toute seule.
    await tenir(700);
    dlg().close("");
    await new Promise((f) => vue().setTimeout(f, 1800));
    note("apresEchap", dlg().open);              // toujours fermee
    note("dialogueFerme", !dlg().open);

    // --- 4. Tenu deux secondes : la fenetre se ferme et l'action part ----
    let envoye = null;
    const vraiFetch = vue().fetch;
    vue().fetch = function (chemin, options) {
      if (String(chemin).indexOf("/admin/donnees/effacer") !== -1) {
        envoye = String(chemin);
        return Promise.resolve(new (vue().Response)(
          JSON.stringify({success: true, message: "efface"}),
          {status: 200, headers: {"Content-Type": "application/json"}}));
      }
      return vraiFetch.apply(this, arguments);
    };

    $("#btnEffacer").click();
    await attendre("dialogue rouvert", () => dlg().open);
    await tenir(2400);
    lacher();
    await attendre("dialogue referme", () => !dlg().open);
    note("tenuJusquAuBout", !dlg().open);
    await attendre("effacement parti", () => envoye !== null);
    note("effacementFait", envoye !== null);
"""


@pytest.fixture(scope="module")
def serveur():
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-maintien-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import comptes, creer_app
    from climbcontest.config import Config
    from climbcontest.extensions import db
    from climbcontest.models import Competition, PREPARATION

    class ConfigConsole(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "console.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigConsole)
    app.config["SECRET_KEY"] = "une-cle-de-test-suffisamment-longue"

    with app.app_context():
        comptes.creer("chef", MDP, [comptes.ADMIN])
        db.session.add(Competition(nom="Bloc Party 2026", date=date(2026, 11, 15),
                                   statut=PREPARATION, active=True))
        db.session.commit()

    verdict = {"texte": None}

    @app.post("/__verdict")
    def poser():
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    @app.get("/__harnais")
    def harnais():
        return Response(page_harnais("/console", SONDE, taille=ECRAN),
                        mimetype="text/html")

    url, arreter = servir(app)
    try:
        yield url, verdict
    finally:
        arreter()
        shutil.rmtree(dossier, ignore_errors=True)


@pytest.fixture(scope="module")
def mesures(serveur):
    url, verdict = serveur
    rendu = piloter(f"{url}/__harnais", verdict)
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestLeReleveEstComplet:
    def test_aucune_mesure_ne_manque(self, mesures):
        manquantes = [nom for nom in ATTENDUES if nom not in mesures]
        assert not manquantes, f"la sonde s'est arretee : {manquantes}"


class TestLeBoutonAnnonceLeGeste:
    def test_la_fenetre_s_ouvre(self, mesures):
        assert mesures["dialogueOuvert"] == "true"

    def test_le_libelle_porte_l_instruction(self, mesures):
        """L'instruction est sur le BOUTON, pas seulement dans l'aide au-dessus :
        c'est le bouton qu'on regarde."""
        assert mesures["libelleAnnonceLaDuree"] == "true"


class TestRelacherTropTot:
    def test_le_geste_a_bien_demarre(self, mesures):
        """⚠️ Sans cette mesure, « rien ne s'est passe » serait vrai aussi
        quand le bouton est DESACTIVE -- et le test passerait sans avoir rien
        essaye. C'est exactement ce qui est arrive a la premiere ecriture, sur
        une competition en cours ou la case « quand meme » verrouille le
        bouton."""
        assert mesures["libellePendantLeMaintien"] == "true"
        assert mesures["boutonTenu"] == "true"

    def test_rien_ne_se_passe(self, mesures):
        """C'est tout l'objet du geste : une pression accidentelle n'efface pas
        une competition."""
        assert mesures["relacheTropTot"] == "true"

    def test_le_libelle_revient(self, mesures):
        """Sinon le bouton resterait sur « Encore 1 s… » et le geste suivant
        repartirait d'un etat menteur."""
        assert mesures["libelleRevenu"] == "true"


class TestEchapPendantUnMaintien:
    def test_le_minuteur_meurt_avec_la_fenetre(self, mesures):
        """⚠️ Sans la remise a plat, le minuteur aboutissait sur un dialogue
        deja ferme -- et refermait le suivant tout seul, deux secondes apres."""
        assert mesures["apresEchap"] == "false"
        assert mesures["dialogueFerme"] == "true"


class TestTenuJusquAuBout:
    def test_la_fenetre_se_ferme(self, mesures):
        assert mesures["tenuJusquAuBout"] == "true"

    def test_l_effacement_part_vraiment(self, mesures):
        """Le geste ne fait pas que fermer une fenetre : il declenche l'action."""
        assert mesures["effacementFait"] == "true"
