"""Deconnecte, la console N'EST PAS LA — dans un vrai navigateur, sur un ecran.

⚠️ **Ce fichier existe pour un defaut qu'aucun autre test ne pouvait voir.**
La console partait bien `hidden` : le gabarit le disait, et un test qui lit le
HTML passait au vert. Elle s'affichait quand meme. La mise en grille des grands
ecrans pose `display: grid` sur `#console`, et une regle d'AUTEUR bat le
`[hidden] { display: none }` de la feuille du NAVIGATEUR -- l'origine auteur
l'emporte sur l'origine agent-utilisateur, quelle que soit la specificite.

Le resultat, sans session, sur tout ecran de 1080 px ou plus : le formulaire de
connexion en haut, et la console ENTIERE en dessous. Tiroir, liste des
participants, saisie de reussites, jeton du classeur, bouton d'effacement des
donnees -- tout visible, tout cliquable. Le serveur refusait chaque appel (401)
et rien n'etait vole ; mais la page invitait a agir, et un organisateur qui
clique dix fois sans rien comprendre le matin d'une competition, c'est le genre
de minute qu'on n'a pas.

**La largeur du cadre est le test.** A 390 px, aucune regle ne pose `display`
sur `#console` : le defaut n'existe pas, et une sonde en cadre telephone aurait
conclu que tout allait bien. On demande donc 1440 px, franchement au-dessus du
seuil de 1080.

Ce fichier se saute proprement s'il n'y a pas de navigateur, comme les autres
`test_navigateur_*.py`.
"""
import os
import shutil
import tempfile

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")

# Un ecran d'organisateur : un portable ouvert sur une table, le matin. Bien
# au-dessus du seuil de 1080 px ou la console passe en grille.
ECRAN = (1440, 900)

# `attendre`, `$`, `$$`, `vue()` et le renvoi du verdict viennent du preambule
# partage.
SONDE = """
    await attendre("connexion affichee",
      () => $("#connexion") && $("#connexion").offsetParent !== null);

    const console_ = $("#console");
    note("existe", !!console_);
    note("hidden", console_.hasAttribute("hidden"));
    note("inert", console_.hasAttribute("inert"));

    // La MESURE qui compte : ce que le navigateur calcule vraiment, une fois
    // toute la cascade appliquee. `hasAttribute("hidden")` disait deja oui
    // pendant que l'ecran montrait la console.
    note("display", vue().getComputedStyle(console_).display);
    note("hauteur", Math.round(console_.getBoundingClientRect().height));

    // Et la question de l'utilisateur, posee telle qu'il la pose : est-ce que
    // je peux cliquer dessus ? On vise le bouton « Ajouter » d'un participant,
    // au milieu de la console, et on demande au document QUI est sous ce
    // point. Rien ne doit repondre le bouton.
    const bouton = $("#btnAjouter");
    note("boutonExiste", !!bouton);
    const r = bouton.getBoundingClientRect();
    note("boutonLargeur", Math.round(r.width));
    const sous = vue().document.elementFromPoint(
      r.left + r.width / 2, r.top + r.height / 2);
    note("sousLePoint", sous ? (sous.id || sous.tagName) : "rien");

    // Le clavier est l'autre chemin : `Tab` ne doit jamais entrer dans un bloc
    // inerte. On demande la liste de ce qui est focalisable et on regarde si
    // quoi que ce soit prend le focus.
    bouton.focus();
    note("focusPris", vue().document.activeElement === bouton);
"""


@pytest.fixture()
def serveur():
    """L'application, un vrai serveur, et le harnais. AUCUNE session ouverte.

    C'est tout le sujet : on n'appelle pas `/admin/connexion`, on ne pose aucun
    cookie. La page doit se debrouiller pour ne rien montrer.
    """
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-console-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import creer_app
    from climbcontest.config import Config

    class ConfigConsole(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "console.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigConsole)
    # Une vraie cle : avec `dev-non-secret`, l'administration repond 503 et la
    # page se rabattrait sur la connexion pour la mauvaise raison.
    #
    # Posee APRES la fabrique, et non dans la classe de configuration : ecrite
    # la-bas, `gitleaks` y voit un secret en dur et refuse le commit. Le
    # garde-fou a raison de ne pas faire d'exception pour `tests/` -- c'est
    # aussi la que les secrets s'oublient. Meme idiome que
    # `test_comptes_et_session.py`.
    app.config["SECRET_KEY"] = "une-cle-de-test-suffisamment-longue"
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


class TestLaConsoleNApparaitPasSansSession:

    def test_rien_sous_le_formulaire_de_connexion(self, serveur):
        url, verdict = serveur
        rendu = piloter(f"{url}/__harnais", verdict, taille=ECRAN)
        assert rendu.startswith("OK "), rendu
        m = dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)

        assert m["existe"] == "true"
        assert m["hidden"] == "true", "la console ne part plus cachee"
        assert m["inert"] == "true", "la console ne part plus debranchee"

        # Le defaut, dans les termes ou il se mesure.
        assert m["display"] == "none", (
            f"#console est calcule en `display: {m['display']}` alors qu'il "
            "porte `hidden` : une regle d'auteur bat a nouveau le "
            "`[hidden]` du navigateur, et la console entiere s'affiche sous "
            "le formulaire de connexion")
        assert m["hauteur"] == "0", (
            f"la console occupe {m['hauteur']} px de haut sous la connexion")

        # Et le geste : rien a cliquer, rien a atteindre au clavier.
        assert m["boutonExiste"] == "true", (
            "le bouton temoin a disparu : la sonde ne demontre plus rien")
        assert m["boutonLargeur"] == "0"
        assert m["sousLePoint"] != "btnAjouter", (
            "un bouton de la console est cliquable sans session")
        assert m["focusPris"] == "false", (
            "le clavier entre encore dans la console : `inert` n'est plus pose")
