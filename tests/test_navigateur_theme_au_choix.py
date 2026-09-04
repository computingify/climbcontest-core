"""Le juge impose le theme, et ca tient au relancement — spec 040.

⚠️ **Le defaut que ce fichier ferme.** Un reglage de theme se casse toujours au
meme endroit : il marche au clic, et il est perdu -- ou pire, appliqué trop tard
-- au lancement suivant. Le clic, lui, ne prouve presque rien : c'est
`document.documentElement.dataset.theme` pose par un module qui vient de
tourner. Ce qui doit etre verifie, c'est le RELANCEMENT : la page se recharge,
le script en ligne du `<head>` relit le rangement, et le bon jeu de couleurs
s'applique avant que quoi que ce soit d'autre ne tourne.

Trois choses sont mesurees dans un vrai navigateur, cascade appliquee :

1. **Le clic change le theme** — le navigateur ne demande rien (chromium sans
   reglage systeme rend `prefers-color-scheme: light`), et « Sombre » lui
   impose l'autre jeu. C'est le sens meme de la spec.
2. **Le choix survit au relancement**, avec sa pastille allumee.
3. **« Systeme » rend la main** : la cle disparait du rangement, l'attribut
   disparait de `<html>`, et le defaut de la spec 039 revient.

Ce fichier se saute proprement s'il n'y a pas de navigateur, comme les autres
`test_navigateur_*.py`.

⚠️ Ce qui n'est PAS mesure ici : l'absence de clignotement au demarrage. Elle
tient a ce que le script soit EN LIGNE et AVANT les modules, ce qu'un test
statique lit mieux qu'un navigateur -- `test_theme_au_choix.py`, classe
`TestLeThemeEstPoseAvantLaPeinture`.
"""
import os
import shutil
import tempfile

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")

FOND_CLAIR = "#F3EEE3"
FOND_SOMBRE = "#15161B"

SONDE = r"""
    const doc = () => cadre.contentDocument;
    const attendreLApplication = (quoi) => attendre(quoi, () => {
      const a = $("#accueil");
      return a === null || a.classList.contains("parti");
    });
    const jeton = () => vue().getComputedStyle(doc().documentElement)
                            .getPropertyValue("--fond").trim();
    const range = () => String(vue().localStorage.getItem("climbcontest-theme"));
    const attribut = () => doc().documentElement.dataset.theme || "absent";
    // Une pastille par choix, et une seule allumee : `aria-pressed` est ce que
    // le lecteur d'ecran annonce, donc c'est lui qu'on lit.
    const allumee = () => ($$('#choixTheme [aria-pressed="true"]')
                           .map((b) => b.dataset.choix).join(",") || "aucune");
    async function ouvrirLesReglages() {
      $("#ouvrirReglages").click();
      await attendre("ecran reglages", () => !$("#ecranReglages").hidden);
    }

    await attendreLApplication("demarrage fini");

    // --- 1. Le point de depart : personne n'a rien demande ---------------
    note("systemeSombre", vue().matchMedia("(prefers-color-scheme: dark)").matches);
    note("departFond", jeton());
    note("departAttribut", attribut());
    note("departRange", range());
    await ouvrirLesReglages();
    note("departAllumee", allumee());

    // --- 2. Le juge impose le sombre ------------------------------------
    $('#choixTheme [data-choix="sombre"]').click();
    note("clicFond", jeton());
    note("clicAttribut", attribut());
    note("clicRange", range());
    note("clicAllumee", allumee());
    // La barre du navigateur suit, sinon l'application est sombre sous un
    // bandeau couleur papier.
    note("clicBarreClaire",
      doc().querySelector('meta[name="theme-color"][media*="light"]')
           .getAttribute("content"));

    // --- 3. Le relancement, le seul moment qui compte vraiment ----------
    vue().location.reload();
    await attendre("rechargement", () => {
      const d = cadre.contentDocument, f = cadre.contentWindow;
      return d && f && f.location.href !== "about:blank"
          && d.readyState === "complete" && $("#choixTheme") !== null;
    });
    await attendreLApplication("demarrage fini apres relance");
    note("relanceFond", jeton());
    note("relanceAttribut", attribut());
    note("relanceBarreClaire",
      doc().querySelector('meta[name="theme-color"][media*="light"]')
           .getAttribute("content"));
    await ouvrirLesReglages();
    note("relanceAllumee", allumee());

    // --- 4. « Systeme » rend la main ------------------------------------
    $('#choixTheme [data-choix="auto"]').click();
    note("autoFond", jeton());
    note("autoAttribut", attribut());
    note("autoRange", range());
    note("autoAllumee", allumee());
"""


@pytest.fixture()
def serveur():
    """L'application juge, sans cle d'API ni classeur — comme la spec 039."""
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-theme-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import creer_app
    from climbcontest.config import Config

    class ConfigTheme(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "theme.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigTheme)
    verdict = {"texte": None}

    @app.post("/__verdict")
    def poser():
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    @app.get("/__harnais")
    def harnais():
        return Response(page_harnais("/juge", SONDE), mimetype="text/html")

    url, arreter = servir(app)
    try:
        yield url, verdict
    finally:
        arreter()
        shutil.rmtree(dossier, ignore_errors=True)


@pytest.fixture()
def mesures(serveur):
    url, verdict = serveur
    rendu = piloter(f"{url}/__harnais", verdict)
    assert rendu.startswith("OK "), rendu
    m = dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)
    if m.get("systemeSombre") == "true":
        pytest.skip("le navigateur du harnais demande le sombre : la mesure "
                    "porterait sur l'autre sens que celui qu'on veut prouver")
    return m


class TestLeDepartNeChangePas:
    """La spec 039 reste vraie tant que personne n'a touche au reglage."""

    def test_l_application_s_ouvre_toujours_en_clair(self, mesures):
        assert mesures["departFond"] == FOND_CLAIR

    def test_aucun_attribut_n_est_pose(self, mesures):
        """L'attribut absent, c'est la requete media qui decide — le defaut de
        la 039 a l'octet pres, et pas une imitation posee par un script."""
        assert mesures["departAttribut"] == "absent"
        assert mesures["departRange"] == "null"

    def test_la_position_de_depart_est_systeme(self, mesures):
        assert mesures["departAllumee"] == "auto"


class TestLeJugeImposeLeSombre:
    """« un bouton pour changer le mode sombre vers claire et inversement »."""

    def test_le_theme_bascule_au_clic(self, mesures):
        assert mesures["clicFond"] == FOND_SOMBRE, (
            "le navigateur demande le clair et le juge a demande le sombre : "
            "c'est le juge qui doit gagner")

    def test_le_choix_est_range(self, mesures):
        assert mesures["clicAttribut"] == "sombre"
        assert mesures["clicRange"] == "sombre"

    def test_une_seule_pastille_est_allumee(self, mesures):
        assert mesures["clicAllumee"] == "sombre"

    def test_la_barre_du_navigateur_suit(self, mesures):
        """Les deux balises portent leur requete media : sans les accorder, un
        telephone en clair garderait un bandeau couleur papier au-dessus d'une
        application sombre."""
        assert mesures["clicBarreClaire"] == FOND_SOMBRE


class TestLeChoixSurvitAuRelancement:
    """Le vrai test. Un theme qui ne survit pas au relancement n'existe pas :
    le juge le repose chaque matin, ou l'application clignote sous ses yeux."""

    def test_l_application_rouvre_dans_le_theme_choisi(self, mesures):
        assert mesures["relanceFond"] == FOND_SOMBRE
        assert mesures["relanceAttribut"] == "sombre"

    def test_les_reglages_montrent_le_choix_retenu(self, mesures):
        assert mesures["relanceAllumee"] == "sombre"

    def test_la_barre_du_navigateur_survit_elle_aussi(self, mesures):
        """Le piege : l'attribut est pose par le script en ligne, la barre ne
        l'est pas -- elle suit ses requetes media. Sans un rappel au demarrage,
        l'application rouvre sombre sous un bandeau couleur papier."""
        assert mesures["relanceBarreClaire"] == FOND_SOMBRE


class TestSystemeRendLaMain:
    """La raison d'etre de la troisieme pastille : un interrupteur a deux
    positions ne sait pas revenir a « suis le telephone »."""

    def test_le_defaut_revient(self, mesures):
        assert mesures["autoFond"] == FOND_CLAIR
        assert mesures["autoAttribut"] == "absent"

    def test_la_cle_disparait_du_rangement(self, mesures):
        """Ne rien ranger, c'est suivre : une valeur `auto` ecrite en dur
        durcirait le defaut du jour dans le telephone."""
        assert mesures["autoRange"] == "null"

    def test_la_pastille_systeme_est_allumee(self, mesures):
        assert mesures["autoAllumee"] == "auto"
