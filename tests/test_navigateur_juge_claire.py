"""L'application juge s'ouvre en clair, et rien n'y devient invisible — spec 039.

⚠️ **Le defaut que ce fichier ferme.** Retourner un theme, c'est deplacer
quinze couleurs a la fois. Le risque n'est pas qu'une couleur soit laide : c'est
qu'un texte se retrouve a 1,9:1 sur son propre fond -- lisible sur l'ardoise,
invisible sur le papier -- et que personne ne s'en apercoive avant qu'un
benevole tienne le telephone en plein soleil.

Aucun test statique ne peut le voir. `test_pwa_claire.py` lit le gabarit et le
gabarit dit la verite : les deux jeux de couleurs sont bien la. C'est la
CASCADE qui decide de ce qui se pose sur quoi, et seul un vrai navigateur la
calcule -- avec les `color-mix`, les voiles semi-transparents et les variables
posees en ligne par `redessiner()`.

Ce que ce fichier mesure :

1. **Le fond est clair quand personne ne demande rien.** C'est la demande
   d'Adrien, mot pour mot, et c'est la seule chose qui la verifie vraiment.
2. **Le contraste calcule de dix-sept textes**, dans trois etats de l'ecran,
   contre leur fond EFFECTIF -- celui qu'on obtient en remontant les parents
   jusqu'a un fond opaque, voiles composes.

Ce fichier se saute proprement s'il n'y a pas de navigateur, comme les autres
`test_navigateur_*.py`.

⚠️ Le theme SOMBRE n'est pas mesure ici, et il faut le dire : le harnais lance
un chromium en ligne de commande, qui n'a pas de reglage systeme a offrir. Le
sombre est protege autrement -- par la structure, dans `test_pwa_claire.py`
(aucune couleur ne peut n'exister que dans un seul theme), et par l'oeil, sur
les seize captures de `specs/039-pwa-claire/maquettes/`. Pretendre le mesurer
ici donnerait une fausse assurance.
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
SONDE = r"""
    await attendre("demarrage fini", () => {
      const a = $("#accueil");
      return a === null || a.classList.contains("parti");
    });
    const doc = () => cadre.contentDocument;

    // ⚠️ Les TRANSITIONS d'abord. `.carte` a `transition: background .25s` :
    // mesurer juste apres avoir pose une classe rendrait la couleur d'AVANT,
    // et le test passerait au vert en mesurant l'ancien theme.
    const gel = doc().createElement("style");
    gel.textContent = "* { transition: none !important; animation: none !important }";
    doc().head.append(gel);

    // --- Les outils de mesure -------------------------------------------
    // `getComputedStyle` rend soit « rgb(a)(…) » soit « color(srgb …) » -- la
    // seconde forme des que la valeur vient d'un `color-mix`, ce qui est le cas
    // de tous les voiles. Les deux echelles ne sont pas les memes.
    function couleur(texte) {
      const n = (texte.match(/[\d.]+/g) || []).map(Number);
      if (texte.startsWith("color(")) {
        return [n[0] * 255, n[1] * 255, n[2] * 255, n.length > 3 ? n[3] : 1];
      }
      return [n[0], n[1], n[2], n.length > 3 ? n[3] : 1];
    }
    const poser = (dessus, dessous) => dessus.slice(0, 3).map(
      (c, i) => dessus[3] * c + (1 - dessus[3]) * dessous[i]);
    function fond(el) {
      // Le fond EFFECTIF : on remonte les parents jusqu'a un fond opaque, en
      // composant les voiles au passage. Un voile ambre a 30 % sur du papier
      // sable n'est ni l'un ni l'autre.
      const pile = [];
      for (let e = el; e; e = e.parentElement) {
        const c = couleur(vue().getComputedStyle(e).backgroundColor);
        if (c[3] > 0) pile.push(c);
        if (c[3] === 1) break;
      }
      // Le fond du `body` peut etre un degrade : sa couleur de base suffit,
      // c'est la plus sombre des deux extremites en clair.
      let bas = pile.length ? pile[pile.length - 1].slice(0, 3) : [255, 255, 255];
      for (let i = pile.length - 2; i >= 0; i--) bas = poser(pile[i], bas);
      return bas;
    }
    const lin = (v) => { v /= 255; return v <= .04045 ? v / 12.92
                                 : Math.pow((v + .055) / 1.055, 2.4); };
    const lum = (rgb) => .2126 * lin(rgb[0]) + .7152 * lin(rgb[1]) + .0722 * lin(rgb[2]);
    function contraste(el) {
      const f = fond(el);
      const t = poser(couleur(vue().getComputedStyle(el).color), f);
      const a = lum(t), b = lum(f);
      return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    }
    const mesurer = (nom, sel) => {
      const el = $(sel);
      if (!el) return note(nom, "absent");
      note(nom, contraste(el).toFixed(2));
    };

    // --- 1. Le fond est-il clair, sans que personne l'ait demande ? ------
    note("fondLuminance", lum(fond(doc().body)).toFixed(3));
    note("encreLuminance",
      lum(couleur(vue().getComputedStyle(doc().body).color)).toFixed(3));
    note("viseurNoir",
      vue().getComputedStyle($("#viseur")).backgroundColor.replace(/\s/g, ""));

    // --- 2. L'ecran au repos --------------------------------------------
    mesurer("reposValeurGrimpeur", "#valeurGrimpeur");
    mesurer("reposLibelleGrimpeur", "#carteGrimpeur .quoi");
    mesurer("reposLibelleBloc", "#carteBloc .quoi");
    mesurer("reposEnvoyerDesactive", "#envoyer");
    mesurer("reposAide", "#aide");
    mesurer("reposEffacer", "#effacer");

    // --- 3. Les deux cartes scannees, circuit Jaune ----------------------
    // Le jaune est le PIRE cas du theme clair : c'est la teinte la plus proche
    // du papier. Les valeurs sont celles de `couleurs.js`, dont la table est
    // testee a part (`tests/js/couleurs.test.mjs`).
    $("#carteGrimpeur").classList.add("fait");
    $("#valeurGrimpeur").textContent = "Bernard Camille";
    $("#valeurGrimpeur").classList.remove("attente");
    $("#detailGrimpeur").textContent = "n°41";
    $("#categorieGrimpeur").textContent = "U13 F";
    $("#categorieGrimpeur").hidden = false;
    $("#carteBloc").classList.add("fait");
    $("#valeurBloc").textContent = "ZJ1";
    $("#valeurBloc").classList.remove("attente");
    $("#detailBloc").textContent = "U13 · U15 — Jaune";
    doc().documentElement.style.setProperty("--circuit", "#F5B72E");
    doc().documentElement.style.setProperty("--encre-circuit", "#12140F");
    $("#envoyer").disabled = false;
    mesurer("jauneTag", "#valeurBloc");
    mesurer("jauneLibelleBloc", "#carteBloc .quoi");
    mesurer("jauneDetail", "#detailBloc");
    mesurer("jauneEnvoyer", "#envoyer");
    mesurer("jauneNomGrimpeur", "#valeurGrimpeur");
    mesurer("jauneCategorie", "#categorieGrimpeur");
    mesurer("jauneDossard", "#detailGrimpeur");

    // Le hors-circuit : le bandeau d'avertissement et son bouton force.
    $("#horsCircuit").hidden = false;
    $("#horsCircuit").innerHTML = "Ce bloc est <b>U17</b> — ce grimpeur est <b>U13</b>.";
    $("#envoyer").classList.add("force");
    mesurer("horsTexte", "#horsCircuit");
    mesurer("horsGras", "#horsCircuit b");
    mesurer("horsEnvoyerForce", "#envoyer");

    // Les pastilles de file, dans l'en-tete.
    $("#bandeFile").hidden = false;
    $("#compteurAttente").hidden = false;
    $("#compteurAttente").textContent = "3 en attente";
    $("#compteurRefus").hidden = false;
    $("#compteurRefus").textContent = "1 refusée";
    mesurer("pastilleAttente", "#compteurAttente");
    mesurer("pastilleRefus", "#compteurRefus");

    // --- 4. L'ecran Reglages --------------------------------------------
    $("#principal").hidden = true;
    $("#ecranReglages").hidden = false;
    $("#nomTelephone").value = "Mur jaune";
    $("#identifiantTelephone").textContent = "telephone 7f3a";
    mesurer("reglagesTitre", "#ecranReglages h2");
    mesurer("reglagesSection", "#ecranReglages .section > h3");
    mesurer("reglagesEtiquette", "#ecranReglages .bloc label");
    mesurer("reglagesChamp", "#nomTelephone");
    mesurer("reglagesExplication", "#ecranReglages .explication");
    mesurer("reglagesMono", "#identifiantTelephone");
    mesurer("reglagesAction", "#btnScannerPoste");
    mesurer("reglagesLien", "#voirMesScans");
"""

# Le seuil de chaque texte, et POURQUOI il est celui-la. WCAG 2.1 : 4,5:1 pour
# du texte courant, 3:1 des 24 px ou des 18,7 px en gras.
#
# ⚠️ Les seuils a 3 ne sont pas des passe-droits : ce sont des textes de 1,85 a
# 1,9 rem en graisse 800 (le tag du bloc, « ENVOYER »), ou des libelles
# volontairement en retrait sur une etape qu'on ne peut pas encore remplir.
SEUILS = {
    "reposValeurGrimpeur": 4.5,
    "reposLibelleGrimpeur": 4.5,    # l'etape ACTIVE : elle passe a `--encre`
    "reposLibelleBloc": 3.0,        # l'etape pas encore atteignable, en retrait
    "reposEnvoyerDesactive": 3.0,   # 1,9 rem, graisse 800
    "reposAide": 4.5,
    "reposEffacer": 4.5,
    "jauneTag": 3.0,                # 1,85 rem, graisse 800, sur l'aplat exact
    "jauneLibelleBloc": 4.5,        # la teinte ECRITE, tiree vers l'encre
    "jauneDetail": 4.5,
    "jauneEnvoyer": 3.0,            # 1,9 rem, graisse 800
    "jauneNomGrimpeur": 4.5,
    "jauneCategorie": 4.5,
    "jauneDossard": 4.5,
    "horsTexte": 4.5,
    "horsGras": 4.5,
    "horsEnvoyerForce": 3.0,
    "pastilleAttente": 4.5,
    "pastilleRefus": 4.5,
    "reglagesTitre": 4.5,
    "reglagesSection": 4.5,
    "reglagesEtiquette": 4.5,
    "reglagesChamp": 4.5,
    "reglagesExplication": 4.5,
    "reglagesMono": 4.5,
    "reglagesAction": 4.5,
    "reglagesLien": 4.5,
}


@pytest.fixture()
def serveur():
    """L'application et un vrai serveur, sans aucune donnee.

    C'est l'etat dans lequel un juge ouvre l'application avant que
    l'organisateur lui ait donne son lien -- et le theme, lui, doit deja etre
    bon.
    """
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-clair-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import creer_app
    from climbcontest.config import Config

    class ConfigClaire(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "clair.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigClaire)
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
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestElleSOuvreEnClair:
    """« pour l'application PWA je voudrais que par defaut elle s'ouvre en
    claire » (Adrien, 03/09). Le navigateur ne demande rien : c'est le defaut
    du gabarit qu'on lit.
    """

    def test_le_fond_est_clair(self, mesures):
        fond = float(mesures["fondLuminance"])
        assert fond > 0.5, (
            f"le fond calcule a une luminance de {fond} : l'application s'ouvre "
            "en sombre alors que rien ne l'a demande")

    def test_l_encre_est_sombre(self, mesures):
        encre = float(mesures["encreLuminance"])
        assert encre < 0.1, (
            f"l'encre a une luminance de {encre} : elle est restee claire, donc "
            "posee sur un fond clair")

    def test_le_viseur_reste_noir(self, mesures):
        """L'image de la camera ne suit pas le theme : un cadre clair autour
        d'un flux video fait fermer l'iris du capteur."""
        assert mesures["viseurNoir"] == "rgb(0,0,0)"


class TestRienNEstInvisibleSurLePapier:
    """Les dix-sept textes, un a un. Un echec ici nomme l'element ET son
    rapport : c'est ce qui permet de corriger la couleur, pas de la chercher.
    """

    @pytest.mark.parametrize("quoi", sorted(SEUILS))
    def test_le_contraste_tient(self, mesures, quoi):
        assert quoi in mesures, f"la sonde n'a pas mesure {quoi}"
        assert mesures[quoi] != "absent", (
            f"{quoi} : l'element a disparu du gabarit, la mesure ne veut plus "
            "rien dire")
        mesure = float(mesures[quoi])
        assert mesure >= SEUILS[quoi], (
            f"{quoi} se lit a {mesure}:1 sur son fond effectif, sous le seuil "
            f"de {SEUILS[quoi]}:1")

    def test_toutes_les_mesures_sont_la(self, mesures):
        """Un contre-test : une sonde qui echouerait a mi-parcours rendrait un
        verdict PARTIEL, et les tests ci-dessus passeraient sur ce qu'elle a eu
        le temps de mesurer."""
        manquantes = sorted(set(SEUILS) - set(mesures))
        assert not manquantes, manquantes
