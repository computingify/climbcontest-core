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

# ⚠️ Le demarrage, ecrit UNE fois. Chaque sonde en a besoin, et une sonde qui
# le recopierait de travers echouerait pour la mauvaise raison.
#
# « L'ecran d'accueil est-il parti ? » se pose en DEUX morceaux : la classe
# `.parti` declenche un fondu de 450 ms, apres quoi le noeud est RETIRE. Une
# sonde qui n'attend que la classe rate la fenetre sur une machine lente, et
# reste bloquee sur un element qui n'existe plus.
DEMARRAGE = """
    const parti = (doc) => {
      const a = doc && doc.getElementById("accueil");
      return doc && doc.readyState === "complete"
          && (!a || a.classList.contains("parti"));
    };
    await attendre("demarrage fini", () => parti(cadre.contentDocument));
    $("#ouvrirReglages").click();
    await attendre("reglages ouverts",
      () => $("#ecranReglages") && !$("#ecranReglages").hasAttribute("hidden"));

    // ⚠️ MESURER UNE PROPRIETE EN TRANSITION REND SA VALEUR DE DEPART.
    // `getComputedStyle` rend la valeur COURANTE de l'animation : lue dans la
    // milliseconde qui suit un clic, la glissiere est encore grise et sa
    // pastille encore a gauche, alors que la regle `:checked` s'applique deja
    // -- `querySelector` la trouve, et le style dit le contraire.
    //
    // On attend la FIN des animations, pas un delai : `getAnimations` rend []
    // quand il n'y en a pas (et sous `prefers-reduced-motion`), donc l'attente
    // vaut zero quand il n'y a rien a attendre.
    const pose = async (n) => {
      const a = n.getAnimations ? n.getAnimations({ subtree: true }) : [];
      await Promise.all(a.map((x) => x.finished.catch(() => {})));
    };
"""

SONDES = {}

SONDES["refusees"] = """
    // ⚠️ Attendre le BOUTON ne suffit pas : il est dans le gabarit des le
    // premier octet, alors que `ouvrirLesReglages()` lit `identite`, que le
    // demarrage asynchrone n'a pas encore posee. Cliquer trop tot leve, et
    // l'ecran ne s'ouvre jamais. `juge.js` marque la fin de son demarrage en
    // retirant l'ecran d'accueil : c'est ce signal-la qu'on attend, et non un
    // delai fixe. Le morceau est partage -- voir `DEMARRAGE`.
""" + DEMARRAGE + """
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


# --- Spec 042 ----------------------------------------------------------------

SONDES["demande"] = """
""" + DEMARRAGE + """
    // ⚠️ ALLER-RETOUR, et pas seulement aller. Une sonde qui verifierait
    // uniquement l'extinction passerait au vert avec une regle qui cacherait la
    // demande POUR TOUJOURS -- et le carton change de table deviendrait
    // inaccessible, ce qui est pire que le defaut qu'on corrige.
    const bouton = () => $("#btnScannerPoste");
    const style = (s) => vue().getComputedStyle($(s));
    const largeur = (s) => Math.round($(s).getBoundingClientRect().width);

    function mesurer(quand) {
      note(quand + "Classe", bouton().className);
      // L'APLAT, c'est ce qui fait la demande. Un lien n'en a pas.
      note(quand + "Aplat", style("#btnScannerPoste").backgroundColor
                            !== "rgba(0, 0, 0, 0)");
      note(quand + "Largeur", largeur("#btnScannerPoste"));
      note(quand + "Explication", style("#expliquerScanPoste").display);
      note(quand + "ExplicationHauteur",
           Math.round($("#expliquerScanPoste").getBoundingClientRect().height));
      // La seconde surface : le bloc de l'ecran d'accueil bouge AVEC.
      note(quand + "Accueil", style("#poste").display);
      // Le geste reste-t-il sous le doigt ?
      const r = bouton().getBoundingClientRect();
      const sous = vue().document.elementFromPoint(r.left + r.width / 2,
                                                   r.top + r.height / 2);
      note(quand + "SousLeDoigt", sous ? (sous.id || sous.tagName) : "rien");
    }

    mesurer("vide");

    // ⚠️ On attend `#nomPoste`, PAS le bouton : attendre l'effet qu'on mesure
    // ferait rendre un delai la ou on veut une mesure. L'en-tete est peuple par
    // une AUTRE fonction du meme ecouteur -- il prouve que le renommage a fait
    // son aller-retour dans IndexedDB, sans rien dire de ce qu'on teste.
    const champ = $("#nomTelephone");
    const taper = (v) => {
      champ.value = v;
      champ.dispatchEvent(new (vue().Event)("input", { bubbles: true }));
    };
    taper("Zone C");
    await attendre("nom range", () => $("#nomPoste").textContent === "Zone C");
    mesurer("nomme");

    taper("");
    await attendre("nom efface", () => $("#nomPoste").textContent === "");
    mesurer("revenu");
"""

SONDES["interrupteur"] = """
""" + DEMARRAGE + """
    const label = $("label.bascule");
    const case_ = $("#garderGrimpeur");
    const glissiere = $(".glissiere");
    const cs = (n, pseudo) => vue().getComputedStyle(n, pseudo);
    const pastille = () => cs(glissiere, "::after").transform;

    // ⚠️ LA mesure de cette sonde. `.bloc label { display: block }` a la MEME
    // specificite que `label.bascule` : c'est l'ordre dans le fichier qui
    // tranche, et rien dans le CSS ne dit qu'il compte.
    note("labelDisplay", cs(label).display);
    note("labelTaille", Math.round(parseFloat(cs(label).fontSize)));

    // La case NATIVE est conservee, invisible : le clavier et le lecteur
    // d'ecran gardent tout.
    note("caseLargeur", Math.round(case_.getBoundingClientRect().width));
    note("caseOpacite", cs(case_).opacity);
    note("caseRole", case_.getAttribute("role"));
    note("caseDansLeLabel", label.contains(case_));

    const g = glissiere.getBoundingClientRect();
    const l = label.getBoundingClientRect();
    note("glissiereLargeur", Math.round(g.width));
    note("glissiereHauteur", Math.round(g.height));
    // A DROITE de la ligne, comme dans tous les reglages de telephone.
    note("glissiereADroite", g.left > l.left + l.width / 2);
    // Sous le pouce : c'est elle qu'on touche, pas la case invisible.
    const sous = vue().document.elementFromPoint(g.left + g.width / 2,
                                                 g.top + g.height / 2);
    note("sousLeDoigt", sous ? (sous.className || sous.tagName) : "rien");

    note("eteintCoche", case_.checked);
    note("eteintPastille", pastille());
    note("eteintFond", cs(glissiere).backgroundColor);

    glissiere.click();
    await attendre("interrupteur allume", () => case_.checked === true);
    await pose(glissiere);
    note("allumeCoche", case_.checked);
    note("allumePastille", pastille());
    note("allumeFond", cs(glissiere).backgroundColor);
"""

SONDES["persistance"] = """
""" + DEMARRAGE + """
    // Le reglage doit survivre a une FERMETURE de l'application, pas seulement
    // a un aller-retour d'ecran : rouvrir les Reglages relit `etat`, qui est en
    // memoire. Seul un rechargement prouve qu'IndexedDB a bien ete ecrit.
    $(".glissiere").click();
    await attendre("interrupteur allume", () => $("#garderGrimpeur").checked);
    note("avant", $("#garderGrimpeur").checked);

    // ⚠️ Un marqueur sur le document COURANT. Sans lui, l'attente ci-dessous
    // retombe sur l'ancien document -- il est encore la, deja demarre, et la
    // condition est vraie avant meme que le rechargement commence.
    vue().document.documentElement.dataset.tour = "1";
    vue().location.reload();
    await attendre("page rechargee", () => {
      const doc = cadre.contentDocument;
      return doc && doc.documentElement && !doc.documentElement.dataset.tour
          && parti(doc);
    });
    $("#ouvrirReglages").click();
    await attendre("reglages rouverts",
      () => $("#ecranReglages") && !$("#ecranReglages").hasAttribute("hidden"));
    await pose($(".glissiere"));
    note("apres", $("#garderGrimpeur").checked);
    note("apresPastille",
         vue().getComputedStyle($(".glissiere"), "::after").transform);
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
        # Une sonde par test. Les entasser dans une seule fonction, c'est ce
        # qui a produit un conflit entre deux PR sur `test_navigateur_fiche.py`
        # (spec 038) -- et un verdict de quarante mesures ou plus personne ne
        # voit laquelle a lache.
        sonde = SONDES[request.args.get("sonde", "refusees")]
        return Response(page_harnais("/juge", sonde), mimetype="text/html")

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


def _mesures(rendu):
    """Le verdict, en table. `note` remplace les espaces par des `_`."""
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestLaDemandeDeScanSEteintQuandLeTelephoneEstNomme:
    """« Si le juge set manuellement le nom de son téléphone il faut retirer la
    demande de scan du qrcode de paramétrage. » — Adrien, 03/09 (spec 042).

    Ce qui s'en va, c'est la DEMANDE — l'aplat bleu pleine largeur et son
    explication. Le GESTE reste, en lien discret : un téléphone change parfois
    de table en cours de journée, et il faut pouvoir rescanner sans vider le
    champ d'abord.
    """

    def test_la_demande_s_eteint_et_se_rallume(self, serveur):
        url, verdict = serveur
        m = _mesures(piloter(f"{url}/__harnais?sonde=demande", verdict))

        # 1. Téléphone sans nom : la demande est là, entière.
        assert m["videClasse"] == "action_pleine", m["videClasse"]
        assert m["videAplat"] == "true", (
            "le bouton de scan n'a plus d'aplat sur un téléphone SANS nom : "
            "la demande ne se voit plus au moment où elle sert")
        assert int(m["videLargeur"]) > 300, (
            f"le bouton fait {m['videLargeur']} px de large au lieu de toute "
            "la carte : `.action.pleine` ne s'applique plus")
        assert m["videExplication"] == "block"
        assert int(m["videExplicationHauteur"]) > 0
        assert m["videAccueil"] != "none", (
            "le bloc de l'écran d'accueil est éteint alors que le téléphone "
            "n'a pas de nom")

        # 2. Un nom tapé à la main : la demande s'en va, le geste reste.
        assert m["nommeClasse"] == "lien", m["nommeClasse"]
        assert m["nommeAplat"] == "false", (
            "l'aplat bleu est toujours là sur un téléphone nommé : c'est "
            "exactement la demande qu'on voulait retirer")
        assert int(m["nommeLargeur"]) < 300, (
            f"le lien fait encore {m['nommeLargeur']} px de large : un "
            "`width: 100%` survit au changement d'habit")
        assert m["nommeExplication"] == "none"
        assert m["nommeExplicationHauteur"] == "0", (
            "l'explication du carton reste sous le lien : elle demande un geste "
            "qui n'est plus demandé")
        assert m["nommeAccueil"] == "none", (
            "les deux surfaces ont divergé : la demande est éteinte dans les "
            "Réglages et allumée sur l'écran d'accueil")
        assert m["nommeSousLeDoigt"] == "btnScannerPoste", (
            f"le geste n'est plus atteignable : {m['nommeSousLeDoigt']} est "
            "sous le doigt à la place du lien")

        # 3. ⚠️ LE RETOUR. Sans lui, une règle qui cacherait la demande POUR
        # TOUJOURS passerait au vert — et le carton changé de table deviendrait
        # inaccessible, ce qui est pire que le défaut qu'on corrige.
        assert m["revenuClasse"] == "action_pleine", (
            "le champ vidé ne ramène pas la demande : un juge qui efface le "
            "nom de son poste n'a plus aucun moyen de le rescanner")
        assert m["revenuAplat"] == "true"
        assert int(m["revenuLargeur"]) > 300
        assert m["revenuExplication"] == "block"
        assert m["revenuAccueil"] != "none"


class TestLInterrupteurEstUnInterrupteur:
    """« Toutes les coches pour le paramétrage que tu trouves tu les remplaces
    par un interrupteur comme dans toutes les applications mobiles. » — Adrien,
    03/09 (spec 042).

    ⚠️ Ce test mesure le style CALCULÉ. `.bloc label { display: block }` a la
    même spécificité que `label.bascule` : c'est l'ordre dans le fichier qui
    tranche, et rien dans le CSS ne dit qu'il compte. Un test qui relirait le
    gabarit verrait les deux règles et ne saurait pas laquelle gagne — c'est
    exactement ce qui avait laissé `#ligneRefus` visible en permanence.
    """

    def test_la_case_est_habillee_et_reste_une_case(self, serveur):
        url, verdict = serveur
        m = _mesures(piloter(f"{url}/__harnais?sonde=interrupteur", verdict))

        assert m["labelDisplay"] == "flex", (
            f"le label de l'interrupteur est calculé en `display: "
            f"{m['labelDisplay']}` : `.bloc label {{ display: block }}` a repris "
            "la main, le libellé et la glissière sont l'un sous l'autre")
        assert int(m["labelTaille"]) >= 15, (
            f"le libellé est écrit en {m['labelTaille']} px : c'est la taille "
            "des étiquettes de champ de `.bloc label`, pas celle d'un réglage")

        # La case NATIVE, conservée sous le visuel.
        assert m["caseDansLeLabel"] == "true"
        assert m["caseLargeur"] == "0"
        assert m["caseOpacite"] == "0"
        assert m["caseRole"] == "switch", (
            "sans `role=switch`, le lecteur d'écran annonce « case à cocher, "
            "cochée » là où l'écran montre un interrupteur")

        # Les cotes d'iOS et d'Android, et la place qu'on y attend.
        assert m["glissiereLargeur"] == "51", m["glissiereLargeur"]
        assert m["glissiereHauteur"] == "31", m["glissiereHauteur"]
        assert m["glissiereADroite"] == "true"
        assert "glissiere" in m["sousLeDoigt"], (
            f"{m['sousLeDoigt']} est sous le doigt à la place de la glissière")

        # Et il bascule vraiment.
        assert m["eteintCoche"] == "false"
        assert m["allumeCoche"] == "true"
        assert m["eteintPastille"] == "none", (
            "la pastille est déjà déplacée alors que le réglage est éteint")
        assert "20" in m["allumePastille"], (
            f"la pastille ne bouge pas quand on allume : {m['allumePastille']} "
            "— `input:checked + .glissiere` ne trouve plus son frère adjacent")
        assert m["eteintFond"] != m["allumeFond"], (
            "la glissière garde la même couleur allumée et éteinte : on ne "
            "peut plus lire l'état à un mètre")


class TestLeReglageSurvitAUneFermeture:
    """Rouvrir l'écran relit `etat`, qui est en mémoire. Seul un rechargement
    prouve qu'IndexedDB a bien été écrit — et c'est le cas réel : un juge ferme
    l'application et la rouvre le lendemain matin."""

    def test_l_interrupteur_est_retrouve_apres_rechargement(self, serveur):
        url, verdict = serveur
        m = _mesures(piloter(f"{url}/__harnais?sonde=persistance", verdict))
        assert m["avant"] == "true"
        assert m["apres"] == "true", (
            "le réglage est perdu au rechargement : l'habit a changé mais le "
            "rangement ne suit plus")
        assert "20" in m["apresPastille"], (
            "le réglage est bien rangé mais l'interrupteur s'affiche éteint : "
            "`ouvrirLesReglages` repose `checked`, la glissière ne suit pas")
