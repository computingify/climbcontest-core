"""La fiche du grimpeur DANS UN NAVIGATEUR — spec 026, bout en bout.

Les autres tests de cette spec vérifient chacun une moitié : le serveur rend le
bon JSON (`test_suivi.py`), et la logique de la page décide juste
(`tests/js/suivi.test.mjs`, `plan.test.mjs`). Entre les deux il reste le
**branchement** — le clic sur une ligne, la feuille qui glisse, le dièse, le
bouton retour — et c'est précisément là que vivent les défauts qu'on ne voit
qu'à l'usage. Deux ont déjà été payés sur la maquette : une transition qui
jouait le retour avant l'aller, et une règle CSS qui rendait toute la page
traversante au clic.

⚠️ **Ce fichier se saute proprement s'il n'y a pas de navigateur** — un test qui
échoue faute d'outil apprend à ignorer les échecs. Il ne se saute PAS sur la CI :
l'image `ubuntu-latest` fournit `/usr/bin/chromium`, donc il y tourne pour de
vrai. Poser `CLIMBCONTEST_CHROME` force un binaire précis.

Le harnais est servi par l'application elle-même, sur une route qui n'existe
que dans ce processus : le pilote doit être en MÊME ORIGINE que la page pour
pouvoir la piloter, et on ne veut d'aucun crochet de test dans le code livré.
"""
import os
import shutil
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

# La decouverte du navigateur vient du harnais partage. Elle y a ete recopiee
# depuis ici -- c'est cette version-la qui cherchait les binaires Playwright par
# motif au lieu d'un numero de build fige. Le module partage est aussi ce qui
# declenche la CHAUFFE : un fichier qui redecouvrait chromium dans son coin
# payait les sept secondes du premier lancement sans que personne ne le sache.
from tests.navigateur import (                                    # noqa: E402
    CHROME, piloter as _piloter_partage, port_libre)

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")


# La page relit ses donnees toutes les quinze secondes en usage reel. L'etape
# 7 attend ce battement -- c'est SON SUJET : une fiche ouverte doit se mettre a
# jour toute seule. Elle l'attendait pour de vrai : quinze secondes de CI, et
# le premier rouge des qu'un runner charge en mettait seize. `?periode=` regle
# ce battement, comme `?rotation=` regle deja le defilement de l'ecran de la
# salle. Le battement reste le sujet du test ; seule sa valeur change.
REGLAGE = "/?periode=0.3"

# --- Le pilote : ce qu'un doigt ferait, dans l'ordre -------------------------
#
# Il écrit son verdict dans le titre du document, que `--dump-dom` nous rend.
# Chaque étape est nommée : un échec dit OÙ il s'est arrêté, pas seulement
# qu'il s'est arrêté.
PILOTE = r"""
const etapes = [];
const note = (n, v) => etapes.push(n + "=" + v);
function attendre(quoi, cond, ms = 8000) {
  return new Promise((ok, ko) => {
    const t0 = Date.now();
    (function boucle() {
      let r; try { r = cond(); } catch (e) { r = false; }
      if (r) return ok(r);
      if (Date.now() - t0 > ms) return ko(new Error("delai sur " + quoi));
      setTimeout(boucle, 50);
    })();
  });
}
/** ⚠️ Le verdict REMONTE PAR LE RESEAU, il n'est plus lu dans le titre.
 *
 * Il l'etait, avec `--dump-dom --virtual-time-budget`. Ca marche avec le shell
 * headless de Playwright et PAS avec le chromium complet de la CI : le temps
 * virtuel n'y accelere rien, la page ne rend jamais la main, et le processus
 * expire au bout de quatre minutes sans rien dire. Un `fetch` ne depend
 * d'aucune de ces subtilites. */
function rendre(verdict) {
  return fetch("/__verdict?v=" + encodeURIComponent(verdict)).catch(() => {});
}

(async function () {
  try {
    const cadre = document.getElementById("page");
    await attendre("chargement", () => cadre.contentDocument
      && cadre.contentDocument.querySelectorAll(".ligne[data-participant]").length > 0);
    const doc = cadre.contentDocument;
    const vue = cadre.contentWindow;
    const $ = (s) => doc.querySelector(s);
    const $$ = (s) => [...doc.querySelectorAll(s)];

    note("lignes", $$(".ligne[data-participant]").length);

    // 1. Un clic sur la ligne ouvre la fiche, et l'adresse le dit.
    $('.ligne[data-participant="' + CIBLE + '"]').click();
    await attendre("fiche", () => $(".sf-feuille .sf-case"));
    note("diese", vue.location.hash);
    note("cases", $$(".sf-feuille .sf-case").length);
    note("grimpes", $$(".sf-case.grimpe").length);
    note("restes", $$(".sf-case.reste").length);

    // 2. Le clic atteint VRAIMENT la case. ⚠️ Cette mesure se fait AVANT de
    //    naviguer : une fois au mur, la fiche est translatee hors champ et
    //    `elementFromPoint` ne repond plus rien d'utile. `.click()` ne teste
    //    pas le pointage — il appelle le gestionnaire — et c'est exactement ce
    //    qu'une regle `pointer-events` mal placee casse sans rien casser
    //    d'autre : la page s'affiche parfaitement et n'attrape plus rien.
    const bloc = $("button.sf-case.reste");
    bloc.scrollIntoView({ block: "center" });
    const r = bloc.getBoundingClientRect();
    const sous = doc.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    note("pointage", sous && bloc.contains(sous) ? "atteint" : "bloque");

    // 3. Un bloc restant ouvre le mur sur SA zone, et le mur est dessine.
    note("blocZone", bloc.querySelector(".z").textContent);
    bloc.click();
    await attendre("mur", () => $(".sf-pile.au-mur") && $(".sf-feuille svg.plan"));
    note("diese2", vue.location.hash);
    // ⚠️ `svg.plan >` : ON COMPTE LES PANS. Depuis la spec 036, une zone a
    //    DEUX groupes -- son pan, et le compteur, qui vit une couche plus haut
    //    pour passer devant le cadre. Sans le `>`, chaque zone compterait deux
    //    fois.
    note("zones", $$(".sf-feuille svg.plan > g[data-zone]").length);
    note("visee", $$(".sf-feuille svg.plan > g[data-zone].visee").length);
    note("finies", $$(".sf-feuille .cadre-zone.z-finie").length);
    note("effacees", $$(".sf-feuille svg.plan > g[data-zone].z-rien").length);
    // Le compteur de la zone visee rebondit AVEC son pan : il porte la meme
    // classe, et c'est ce qui lui donne le meme mouvement.
    note("viseeCompteur",
      $$(".sf-feuille .compteurs-zone g[data-zone].visee").length);

    // 3 bis. La legende des profils — spec 033, R11.
    //
    // ⚠️ ON MESURE LA COULEUR CALCULEE, pas la presence de la pastille. Les
    //     six teintes etaient declarees sur `.plan` ; la legende en est un
    //     FRERE, pas un descendant, et une variable CSS ne descend que dans
    //     son sous-arbre. Les pastilles sortaient BLANCHES — un test de
    //     balisage aurait ete vert.
    const profils = $$(".sf-legende .pf");
    note("profils", profils.length);
    note("profilPeint", profils.length
      ? vue.getComputedStyle(profils[0]).backgroundColor : "(aucune)");
    note("reperes", $$(".sf-legende .repere").length);
    // 3 bis. L'avancement par zone (spec 036) : chaque zone du circuit porte
    //        « faits/total », et les autres ne portent RIEN.
    const compteurDe = (racine, z) => [...racine.querySelectorAll(
      ".sf-feuille .compteurs-zone g[data-zone]")]
      .find((n) => n.getAttribute("data-zone") === z);
    const compteDe = (racine, z) => {
      const g = compteurDe(racine, z);
      const c = g && g.querySelector(".compte-zone");
      if (!c) return "(absent)";
      return c.textContent || "(vide)";
    };
    note("compteZ", compteDe(doc, "Z"));
    note("compteA", compteDe(doc, "A"));
    note("compteM", compteDe(doc, "M"));
    note("compteD", compteDe(doc, "D"));
    note("compteurs", $$(".sf-feuille .compte-zone")
      .filter((n) => n.textContent).length);
    // La PASTILLE (spec 036, pose B) : elle n'est peinte que sous un
    // compteur. ⚠️ ON MESURE LE `display` CALCULE, pas la presence du noeud :
    // le socle est decrit pour TOUTES les zones et retire par le CSS
    // (`:not(.a-compte)`). Un test de balisage serait vert avec dix-sept
    // socles blancs poses sur des zones ou le grimpeur n'a rien a faire.
    const socleDe = (z) => {
      const g = compteurDe(doc, z);
      const s = g && g.querySelector(".socle-compte");
      return s ? vue.getComputedStyle(s).display : "(absent)";
    };
    note("socleZ", socleDe("Z"));
    note("socleD", socleDe("D"));
    const socleBoite = (() => {
      const g = compteurDe(doc, "Z");
      const s = g.querySelector(".socle-compte");
      const t = g.querySelector(".compte-zone");
      const a = s.getBoundingClientRect(), b = t.getBoundingClientRect();
      const corps = parseFloat(vue.getComputedStyle(t).fontSize);
      // ⚠️ ON NE COMPARE PAS LES DEUX BOITES. La boite d'un `<text>` SVG est
      // sa LIGNE, pas son encre : elle porte les jambages d'une police entiere
      // et depasse le socle par le haut et par le bas sans qu'un seul pixel de
      // chiffre en sorte. Ce qu'on verifie, c'est ce qui compte vraiment : le
      // socle est plus large que le texte, les deux sont CONCENTRIQUES, et le
      // socle est plus haut que l'encre d'une capitale (0,72 du corps).
      const centre = (r) => [(r.left + r.right) / 2, (r.top + r.bottom) / 2];
      const [xs, ys] = centre(a), [xt, yt] = centre(b);
      return (a.left <= b.left + 0.5 && a.right >= b.right - 0.5
              && Math.abs(xs - xt) <= 0.5 && Math.abs(ys - yt) <= 1.0
              && a.height >= 0.72 * corps)
        ? "porte" : "decale";
    })();
    note("socleBoite", socleBoite);

    // 3 ter. LA PASTILLE SE REMPLIT (spec 036, 03/09). Ce qui ne se voit QUE
    //        dans un vrai navigateur : que la regle CSS attrape bien la barre
    //        verte, que la decoupe est posee -- sans elle le vert deborderait
    //        du socle -- et qu'elle est peinte APRES le cadre de la zone.
    const jaugeDe = (z) => {
      const g = compteurDe(doc, z);
      const j = g && g.querySelector(".remplit-compte");
      if (!j) return "(absente)";
      const plein = parseFloat(j.getAttribute("data-plein"));
      // La part, en centiemes -- une valeur sans espace, le verdict est
      // decoupe sur les espaces.
      return Math.round(100 * parseFloat(j.getAttribute("width")) / plein) + "%";
    };
    note("jaugeZ", jaugeDe("Z"));
    note("jaugeA", jaugeDe("A"));
    note("jaugeM", jaugeDe("M"));
    note("jaugeD", jaugeDe("D"));
    const jaugeZ = compteurDe(doc, "Z").querySelector(".remplit-compte");
    const styleJauge = vue.getComputedStyle(jaugeZ);
    note("jaugeDecoupe", styleJauge.clipPath === "none" ? "aucune" : "posee");
    note("jaugePeinte", styleJauge.fill.replace(/ /g, ""));
    // Le vert ne doit pas depasser du socle : meme boite, a la largeur pres.
    const boiteJauge = (() => {
      const s = compteurDe(doc, "Z").querySelector(".socle-compte");
      const a = s.getBoundingClientRect(), b = jaugeZ.getBoundingClientRect();
      return (b.left >= a.left - 0.5 && b.right <= a.right + 0.5
              && b.top >= a.top - 0.5 && b.bottom <= a.bottom + 0.5)
        ? "dedans" : "deborde";
    })();
    note("jaugeBoite", boiteJauge);
    // ⚠️ L'ORDRE DE PEINTURE : les compteurs APRES les cadres. En SVG c'est
    // l'ordre du document, et rien d'autre ne le dit.
    const plan = $(".sf-feuille svg.plan");
    const iCouche = (c) => [...plan.children].indexOf(plan.querySelector("." + c));
    note("compteurDevant",
      iCouche("compteurs-zone") > iCouche("cadres-zone") ? "oui" : "non");
    // Le cadre de la zone, lui, n'a pas bouge : tout-ou-rien, a son epaisseur
    // d'avant. C'est la moitie de la demande du 03/09.
    const cadreZ = $$(".sf-feuille .cadre-zone")
      .find((n) => n.getAttribute("data-zone") === "Z");
    note("cadreTrait", parseFloat(vue.getComputedStyle(cadreZ).strokeWidth).toFixed(1));
    note("cadreRempli", cadreZ.getAttribute("stroke-dasharray") || "(plein)");

    // 4. Changer de zone REMPLACE l'entree : un seul retour ramene a la fiche.
    const autre = $$(".sf-feuille g[data-zone]")
      .find((n) => n.getAttribute("data-zone") !== bloc.querySelector(".z").textContent);
    const nom = autre.getAttribute("data-zone");
    autre.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await attendre("zone2", () => vue.location.hash.includes("z=" + nom));
    note("titreZone", $(".sf-mur-tete b").textContent.trim());

    vue.history.back();
    await attendre("retour1", () => !vue.location.hash.includes("z="));
    await attendre("fiche2", () => !$(".sf-pile.au-mur"));
    note("retour1", "fiche");

    vue.history.back();
    await attendre("retour2", () => !$(".sf-feuille"));
    note("retour2", "ferme");
    note("diese3", vue.location.hash || "(vide)");

    // 5. Arriver DIRECTEMENT sur une adresse partagee ouvre la fiche par-dessus
    //    le classement, et non a sa place.
    vue.location.hash = "#g=" + CIBLE;
    await attendre("fiche3", () => $(".sf-feuille .sf-case"));
    note("partage", $$(".ligne[data-participant]").length > 0 ? "classement+fiche" : "fiche seule");

    // 6. ⚠️ UNE ARRIVEE DIRECTE sur un lien partage — document neuf, diese
    //    present des le chargement, donc AUCUNE entree d'historique a remonter.
    //    `history.back()` y est un no-op : la croix, Echap et le voile
    //    devenaient inertes, la feuille restait ouverte pour toujours et
    //    `overflow: hidden` figeait le classement derriere. Seul un
    //    rechargement s'en sortait.
    cadre.src = REGLAGE + "#g=" + CIBLE;
    await attendre("chargement direct", () => cadre.contentDocument
      && cadre.contentDocument.querySelector(".sf-feuille .sf-case"));
    const doc2 = cadre.contentDocument, vue2 = cadre.contentWindow;
    note("directOuverte", "oui");
    doc2.querySelector(".sf-tete .sf-rond").click();
    await attendre("fermeture directe", () => !doc2.querySelector(".sf-feuille"));
    note("directFermee", "oui");
    note("directDefilement", doc2.body.style.overflow || "(rendu)");
    note("directDiese", vue2.location.hash || "(vide)");

    // 7. La fiche se rafraichit AU MEME BATTEMENT que le classement. Elle est
    //    restee figee, pendant que la ligne derriere elle affichait deja un
    //    bloc de plus : la page se contredisait elle-meme.
    doc2.querySelector('.ligne[data-participant="' + CIBLE + '"]').click();
    await attendre("fiche rafraichie", () => doc2.querySelector(".sf-feuille .sf-case"));
    const avant = doc2.querySelectorAll(".sf-case.grimpe").length;
    await fetch("/__reussite/" + CIBLE);
    await attendre("bloc passe au vert",
      () => doc2.querySelectorAll(".sf-case.grimpe").length > avant);
    note("avantReussite", avant);
    note("apresReussite", doc2.querySelectorAll(".sf-case.grimpe").length);

    // 8. Et le COMPTEUR DU PLAN suit la meme reussite. Le mur n'est pas
    //    remonte entre-temps -- il est monte une fois par grimpeur -- donc si
    //    le chiffre bougeait avec le dessin et non avec la decoration, il
    //    resterait a « 1/2 » sous une zone qui vient d'etre terminee.
    const caseA = [...doc2.querySelectorAll("button.sf-case")]
      .find((n) => n.querySelector(".z").textContent === "A");
    caseA.click();
    await attendre("mur du direct", () => doc2.querySelector(".sf-pile.au-mur")
      && doc2.querySelector(".sf-feuille svg.plan"));
    note("compteApres", compteDe(doc2, "A"));
    // La pastille est remplie par la meme decoration que le chiffre : elle se
    // complete au meme battement.
    note("jaugeApres", (() => {
      const g = [...doc2.querySelectorAll(".sf-feuille .compteurs-zone g[data-zone]")]
        .find((n) => n.getAttribute("data-zone") === "A");
      const j = g.querySelector(".remplit-compte");
      return Math.round(100 * parseFloat(j.getAttribute("width"))
                        / parseFloat(j.getAttribute("data-plein"))) + "%";
    })());

    await rendre("OK " + etapes.join(" "));
  } catch (e) {
    await rendre("ECHEC " + etapes.join(" ") + " || " + e.message);
  }
})();
"""


def _semer(app, cible):
    """Une compétition minuscule mais complète : une zone terminée, une autre
    entamée, une troisième où le grimpeur n'a rien à faire."""
    from climbcontest.extensions import db
    from climbcontest.models import (
        Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant, Success)

    with app.app_context():
        db.create_all()
        comp = Competition(nom="Demo", date=date.today(), statut=EN_COURS, active=True)
        db.session.add(comp)
        db.session.flush()
        circuit = Circuit(competition_id=comp.id, nom="U13")
        db.session.add(circuit)
        db.session.flush()

        # Zone Z : entierement reussie. Zone A : entamee. Zone M : rien.
        plan = [("ZJ1", "Z", "Jaune", True), ("ZV4", "Z", "Vert", True),
                ("AJ1", "A", "Jaune", True), ("AR12", "A", "Rouge", False),
                ("MM10", "M", "Mauve", False)]
        blocs = []
        for i, (tag, zone, couleur, _) in enumerate(plan, 1):
            b = Bloc(competition_id=comp.id, tag=tag, numero=i, zone=zone,
                     couleur=couleur)
            db.session.add(b)
            db.session.flush()
            db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=circuit.id))
            blocs.append(b)

        grimpeurs = []
        for i in range(1, 4):
            p = Participant(competition_id=comp.id, nom=f"Nom{i}", prenom=f"P{i}",
                            club="Club", categorie="U13 F", dossard=i, present=True)
            db.session.add(p)
            grimpeurs.append(p)
        db.session.flush()

        for b, (_, _, _, reussi) in zip(blocs, plan):
            if reussi:
                db.session.add(Success(participant_id=grimpeurs[0].id, bloc_id=b.id))
        db.session.add(Success(participant_id=grimpeurs[1].id, bloc_id=blocs[0].id))
        db.session.commit()
        cible.append(grimpeurs[0].id)


@pytest.fixture()
def serveur():
    """L'application, un vrai serveur HTTP, et une route de harnais.

    La route `/__harnais` n'existe QUE dans ce processus de test : le pilote
    doit être en même origine que la page pour la piloter, et on ne veut aucun
    crochet de test dans le code livré.
    """
    from flask import Response

    # ⚠️ UNE CONFIGURATION EXPLICITE, et non une variable d'environnement.
    # `climbcontest.config` lit l'environnement A SON IMPORT, et `conftest.py`
    # l'importe des la collecte : une variable posee dans cette fixture arrive
    # trop tard. Le test ecrivait donc dans `instance/climbcontest.db` et
    # relisait les donnees de l'execution precedente — trois participants de
    # plus a chaque fois, et une cible introuvable.
    dossier = tempfile.mkdtemp(prefix="climbcontest-nav-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import creer_app
    from climbcontest.config import Config

    class ConfigNavigateur(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "nav.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigNavigateur)
    cible = []
    _semer(app, cible)

    @app.get("/__reussite/<int:pid>")
    def __reussite(pid):
        """Enregistre une reussite pendant que le navigateur regarde.

        Comme le ferait un juge : c'est le seul moyen de verifier qu'une fiche
        OUVERTE se met a jour toute seule.
        """
        from climbcontest.classement_service import invalider
        from climbcontest.extensions import db as base
        from climbcontest.models import Bloc, Success
        bloc = Bloc.query.filter_by(tag="AR12").first()
        base.session.add(Success(participant_id=pid, bloc_id=bloc.id))
        base.session.commit()
        invalider()
        return {"ok": True}

    verdict = {}

    @app.get("/__verdict")
    def __verdict():
        from flask import request as requete
        verdict["texte"] = requete.args.get("v", "")
        return {"ok": True}

    @app.get("/__harnais")
    def harnais():
        return Response(
            "<!doctype html><meta charset=utf-8><title>en cours</title>"
            f"<iframe id=page src='{REGLAGE}' "
            f"style='width:900px;height:1400px;border:0'></iframe>"
            f"<script>const CIBLE = {cible[0]}; "
            f"const REGLAGE = {REGLAGE!r};</script>"
            f"<script>{PILOTE}</script>",
            mimetype="text/html")

    # ⚠️ `make_server` et non `app.run` : il faut pouvoir ARRETER ce serveur.
    # Lance dans un fil demon, il survivait au test et gardait son port ; le
    # test E2E qui demarre un vrai gunicorn juste apres echouait alors une fois
    # sur deux, sans rapport apparent avec cette spec.
    from werkzeug.serving import make_server

    port = port_libre()
    serveur = make_server("127.0.0.1", port, app, threaded=True)
    # `poll_interval` vaut **0,5 s** par defaut, et c'est le temps que
    # `shutdown()` passe a attendre que la boucle regarde son drapeau. Une
    # attente d'horloge logee dans le teardown, ou personne ne lit les durees.
    fil = threading.Thread(target=serveur.serve_forever, args=(0.02,),
                           daemon=True)
    fil.start()

    import urllib.request
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        serveur.shutdown()
        pytest.fail("le serveur de test n'a pas demarre")

    try:
        yield f"http://127.0.0.1:{port}", cible[0], verdict
    finally:
        serveur.shutdown()
        fil.join(timeout=10)
        shutil.rmtree(dossier, ignore_errors=True)


def piloter(url: str, verdict: dict, secondes: int = 150) -> str:
    """Le pilote PARTAGE, avec la fenetre que veut ce harnais.

    ⚠️ Ce fichier portait sa propre copie de `piloter` : elle lancait un
    chromium a elle, avec son profil jetable et son menage. La copie n'etait pas
    un doublon inoffensif -- c'etait un SEPTIEME demarrage de navigateur, et
    surtout un endroit de plus ou les corrections du harnais (le masque du
    verdict, la fenetre, la mort du navigateur) devaient etre repayees. Le
    module partage le dit en toutes lettres depuis le debut : ce qu'on met en
    commun, ce sont des corrections, pas de la factorisation.

    Le cadre de ce harnais fait 900x1400 ; on garde la meme marge qu'avant, donc
    une fenetre de 1000x1500.
    """
    return _piloter_partage(url + "/__harnais", verdict, secondes=secondes,
                            taille=(960, 1380))


class TestDansUnVraiNavigateur:

    def test_le_parcours_complet(self, serveur):
        """Le geste entier, de la ligne du classement au retour arriere.

        Un seul test et non dix : chaque etape depend de la precedente, et dix
        tests relanceraient dix navigateurs pour rejouer le meme debut.
        Le verdict nomme l'etape ou il s'arrete.
        """
        url, cible, boite = serveur
        verdict = piloter(url, boite)
        assert verdict.startswith("OK "), verdict

        mesures = dict(m.split("=", 1) for m in verdict[3:].split(" ") if "=" in m)

        # La fiche s'ouvre, et l'adresse la porte.
        assert mesures["diese"] == f"#g={cible}"
        assert mesures["cases"] == "5"          # les cinq blocs du circuit
        assert mesures["grimpes"] == "3"
        assert mesures["restes"] == "2"

        # Le mur s'ouvre sur la zone du bloc touche, et la porte dans l'adresse.
        assert mesures["diese2"].startswith(f"#g={cible}&z=")
        # Le plan porte TOUTES les zones de la salle, pas seulement celles du
        # grimpeur : c'est un plan, pas un resume de sa fiche.
        from climbcontest.fiches import PLAN
        assert int(mesures["zones"]) == len([m for m in PLAN["murs"] if m["zone"]])
        assert mesures["visee"] == "1"          # une seule zone est visee
        assert int(mesures["finies"]) == 1      # la zone Z, et elle seule
        # Les zones ou il n'a rien a faire s'effacent : ici, toutes sauf trois.
        assert int(mesures["effacees"]) == int(mesures["zones"]) - 3

        # L'avancement par zone : « faits/total » des blocs de SON circuit.
        assert mesures["compteZ"] == "2/2"      # terminee
        assert mesures["compteA"] == "1/2"      # entamee
        assert mesures["compteM"] == "0/1"      # intacte : le zero se dit
        # Une zone sans bloc de son circuit ne porte AUCUN chiffre. Un « 0/0 »
        # l'enverrait chercher du travail la ou il n'y en a pas.
        assert mesures["compteD"] == "(vide)"
        assert mesures["compteurs"] == "3"

        # La pastille de la pose B : peinte sous les zones qui comptent, RETIREE
        # ailleurs. Un socle sur une zone sans bloc serait un fond blanc pose
        # pour ne rien porter.
        # ⚠️ `display` d'un `<rect>` SVG vaut « inline », pas « block » : ce
        # qu'on verifie est qu'il n'est pas RETIRE, pas qu'il vaut une valeur
        # particuliere.
        assert mesures["socleZ"] != "none"
        assert mesures["socleD"] == "none"
        # Et le chiffre est bien DANS son socle, pas a cote.
        assert mesures["socleBoite"] == "porte"

        # LA PASTILLE SE REMPLIT (spec 036, 03/09). Les memes trois zones que
        # les compteurs, et les memes nombres : les deux lectures derivent du
        # meme compte, elles ne peuvent pas se contredire.
        assert mesures["jaugeZ"] == "100%"      # 2 sur 2 : la pastille pleine
        assert mesures["jaugeA"] == "50%"       # 1 sur 2 : la moitie
        assert mesures["jaugeM"] == "0%"        # 0 sur 1 : rien de vert...
        # ... mais la pastille, elle, est bien la : c'est ce qui distingue
        # « 0/1 » de « aucun bloc ici », ou il n'y a pas de pastille du tout.
        assert mesures["socleZ"] != "none"
        assert mesures["jaugeD"] == "(absente)" or mesures["socleD"] == "none"
        # Le vert est DECOUPE dans la forme du socle : c'est ce qui lui donne
        # son bout droit et l'empeche de deborder du fond qui le porte.
        assert mesures["jaugeDecoupe"] == "posee"
        assert mesures["jaugeBoite"] == "dedans"
        # Et il est bien peint : une regle qui n'attraperait pas la barre
        # laisserait un rectangle noir par defaut, ou rien du tout.
        assert mesures["jaugePeinte"] not in ("none", "rgb(0,0,0)"), \
            mesures["jaugePeinte"]
        # ⚠️ LE COMPTEUR PASSE DEVANT LE CADRE : la pastille fait 14,4 unites
        # dans un pan de 15, elle croise donc le cadre « terminee ». Dessous,
        # elle se ferait couper a ses deux extremites.
        assert mesures["compteurDevant"] == "oui"
        # Le compteur porte la meme classe que son pan : il rebondit avec lui.
        assert mesures["viseeCompteur"] == "1"
        # ⚠️ ET LE CADRE N'A PAS BOUGE. C'est la moitie de la demande du 03/09 :
        # « repasse la taille du cadre vert de reussite totale a sa taille
        # d'avant ». Tout-ou-rien, 1,6, et aucun remplissage.
        assert mesures["cadreTrait"] == "1.6"
        assert mesures["cadreRempli"] == "(plein)"

        # Le clic atteint VRAIMENT la case : c'est ce qu'une regle
        # `pointer-events` mal placee casse, sans rien casser d'autre.
        assert mesures["pointage"] == "atteint"

        # Un seul retour ramene a la fiche, un second ferme.
        assert mesures["retour1"] == "fiche"
        assert mesures["retour2"] == "ferme"
        assert mesures["diese3"] == "(vide)"

        # Une adresse partagee ouvre la fiche PAR-DESSUS le classement.
        assert mesures["partage"] == "classement+fiche"

        # Et une arrivee DIRECTE sur ce lien se referme : sans entree
        # d'historique a remonter, la feuille restait ouverte pour toujours et
        # le classement derriere restait fige.
        assert mesures["directOuverte"] == "oui"
        assert mesures["directFermee"] == "oui"
        assert mesures["directDefilement"] == "(rendu)"
        assert mesures["directDiese"] == "(vide)"

        # La fiche ouverte suit les reussites qui arrivent.
        assert int(mesures["apresReussite"]) == int(mesures["avantReussite"]) + 1

        # La legende dit les profils du plan courant — spec 033, R11.
        # « On a perdu la legende des couleurs qui donnent l'inclinaison du mur
        # et tout ce bazar-la. J'aimerais que tu me le remettes. » (Adrien)
        from climbcontest.fiches import PROFILS
        utilises = {m["profil"] for m in PLAN["murs"] if m["zone"]}
        attendus = len([p for p in PROFILS if p["cle"] in utilises])
        assert int(mesures["profils"]) == attendus, (
            "la legende doit nommer les profils que le plan utilise, "
            "et seulement eux")
        # « zone terminee » plus un repere par profil.
        assert int(mesures["reperes"]) == attendus + 1

        # ⚠️ LA COULEUR, pas la pastille. Les teintes vivaient sur `.plan` :
        # la legende, qui en est un frere, sortait toute blanche.
        peinte = mesures["profilPeint"]
        assert peinte not in ("rgba(0,_0,_0,_0)", "transparent", "(aucune)"), peinte
        assert peinte != "rgb(255,_255,_255)", peinte
        # Et le compteur du plan avec elle : la zone A passe de « 1/2 » a
        # « 2/2 » sans que le mur soit remonte.
        assert mesures["compteApres"] == "2/2"
        # Et la pastille s'est remplie au meme battement : les deux lectures
        # bougent ensemble, parce qu'elles derivent du meme compte.
        assert mesures["jaugeApres"] == "100%"
