"""L'ecran Reglages du juge ne montre que ce qui existe — dans un navigateur.

⚠️ **Le defaut que ce fichier ferme.** `.ligne { display: flex }` battait le
`[hidden] { display: none }` du navigateur : `#ligneRefus` restait affiche en
permanence. L'ecran Reglages annoncait donc « 0 refusees » suivi d'un bouton
« Renvoyer » bien bleu -- et sans son explication, elle correctement cachee,
puisque `.explication` ne pose aucun `display`. Un bouton qui ne fait rien, sur
le telephone d'un benevole, un jour de competition. Le toucher repondait
« Aucune reussite refusee ».

Aucun test ne pouvait le voir. `tests/js/` teste les modules, pas la page ;
`test_pwa_juge.py` lit le gabarit, et le gabarit disait la verite -- `hidden`
etait bien pose. C'est la CASCADE qui le defaisait, et seule une mesure du
`display` calcule en rend compte.

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

# `attendre`, `$`, `$$`, `vue()` et le renvoi du verdict viennent du preambule
# partage.
SONDE = """
    // ⚠️ Attendre le BOUTON ne suffit pas : il est dans le gabarit des le
    // premier octet, alors que `ouvrirLesReglages()` lit `identite`, que le
    // demarrage asynchrone n'a pas encore posee. Cliquer trop tot leve, et
    // l'ecran ne s'ouvre jamais. `juge.js` marque la fin de son demarrage en
    // retirant l'ecran d'accueil (`#accueil.parti`) : c'est ce signal-la qu'on
    // attend, et non un delai fixe.
    await attendre("demarrage fini",
      () => $("#accueil") && $("#accueil").classList.contains("parti"));
    $("#ouvrirReglages").click();
    await attendre("reglages ouverts",
      () => $("#ecranReglages") && !$("#ecranReglages").hasAttribute("hidden"));

    // La file est vide : c'est l'etat de depart, et l'etat normal.
    const ligne = $("#ligneRefus");
    note("hidden", ligne.hasAttribute("hidden"));

    // La MESURE qui compte : ce que le navigateur calcule, cascade appliquee.
    // `hasAttribute("hidden")` disait deja oui pendant que l'ecran affichait
    // la ligne.
    note("display", vue().getComputedStyle(ligne).display);
    note("hauteur", Math.round(ligne.getBoundingClientRect().height));

    // Et le geste : le bouton est-il sous le doigt ?
    const bouton = $("#renvoyerRefus");
    const r = bouton.getBoundingClientRect();
    note("boutonLargeur", Math.round(r.width));
    const sous = r.width > 0 ? vue().document.elementFromPoint(
      r.left + r.width / 2, r.top + r.height / 2) : null;
    note("sousLePoint", sous ? (sous.id || sous.tagName) : "rien");

    // ⚠️ Le contre-test, dans la meme sonde. Sans lui, une regle qui cacherait
    // la ligne POUR TOUJOURS passerait au vert -- et la file des refusees
    // deviendrait invisible, ce qui est bien pire que le bouton orphelin.
    ligne.hidden = false;
    await new Promise((r) => setTimeout(r, 150));
    note("displayQuandMontree", vue().getComputedStyle(ligne).display);
    note("largeurQuandMontree",
      Math.round($("#renvoyerRefus").getBoundingClientRect().width) > 0);

    // L'ecran principal est REMPLACE, pas doublonne dessous : c'est ce que
    // `main[hidden]` garantissait avant la regle globale.
    note("principalRemplace", $("#principal").getBoundingClientRect().height === 0);
"""


@pytest.fixture()
def serveur():
    """L'application et un vrai serveur. Aucune donnee : la file est vide.

    C'est exactement le cas qui montrait le bouton orphelin -- l'etat dans
    lequel un telephone passe la journee entiere quand tout se passe bien.
    """
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-juge-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import creer_app
    from climbcontest.config import Config

    class ConfigJuge(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "juge.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigJuge)
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


class TestLaLigneDesRefuseesNApparaitQueSiIlYEnA:

    def test_file_vide_aucun_bouton_renvoyer(self, serveur):
        url, verdict = serveur
        rendu = piloter(f"{url}/__harnais", verdict)
        assert rendu.startswith("OK "), rendu
        m = dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)

        assert m["hidden"] == "true", (
            "le script ne pose plus `hidden` sur la ligne des refusees")
        assert m["display"] == "none", (
            f"#ligneRefus est calcule en `display: {m['display']}` alors qu'il "
            "porte `hidden` : une regle d'auteur bat a nouveau le `[hidden]` du "
            "navigateur, et l'ecran Reglages affiche « 0 refusees » avec un "
            "bouton « Renvoyer » qui ne fait rien")
        assert m["hauteur"] == "0"
        assert m["boutonLargeur"] == "0"
        assert m["sousLePoint"] != "renvoyerRefus", (
            "le bouton « Renvoyer » est sous le doigt alors que rien n'est refuse")

        # Le contre-test : la ligne doit redevenir utilisable quand elle sert.
        assert m["displayQuandMontree"] == "flex", (
            "la ligne des refusees ne s'affiche plus quand on la montre : la "
            "file des refusees serait devenue invisible")
        assert m["largeurQuandMontree"] == "true"

        assert m["principalRemplace"] == "true", (
            "l'ecran principal reste sous les reglages au lieu d'etre remplace")
