// Le mur à l'écran — spec 026.
//
// ⚠️ CE FICHIER EXISTE SURTOUT POUR UNE RAISON : `fiches.PLAN` a déjà changé
// de forme une fois (grille 8×7 → polygones, spec 028) et il rechangera. La
// page doit alors se DÉBRANCHER proprement, pas dessiner un plan qu'elle
// comprend à moitié — ce qui enverrait quelqu'un chercher un bloc au mauvais
// endroit. La moitié des tests ci-dessous maltraite donc le plan exprès.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  COMPTE_DESCENTE, COMPTE_ECHELLE, FORMATS_RENDUS, LETTRE_MONTEE,
  PASTILLE_HAUTEUR, PASTILLE_LARGEUR, decorer, decrire, monter, partFaite,
  peutDessiner, tailleDuCompte, zonesDe,
} from "../../climbcontest/static/resultats/plan.js";

/** Le groupe d'une zone dans une description : son PAN, celui qui porte la
 *  lettre. Depuis que le compteur est peint par-dessus les cadres, il n'est
 *  plus le seul nœud à porter `data-zone`. */
function panDecrit(dessin, zone) {
  return dessin.enfants.find((e) => e.attrs && e.attrs["data-zone"] === zone);
}

/** Une couche du dessin, par sa classe : « cadres-zone », « compteurs-zone ». */
function couche(dessin, classe) {
  return dessin.enfants.find((e) => e.attrs && e.attrs.class === classe);
}

/** Le groupe d'une zone dans la couche des compteurs. */
function compteurDecrit(dessin, zone) {
  return couche(dessin, "compteurs-zone").enfants
    .find((e) => e.attrs["data-zone"] === zone);
}

/** Le plan tel que `suivi.plan_public()` le rend. */
function plan(surcharges = {}) {
  return {
    format: "polygones/1",
    vue: [120, 150],
    cadrage: "-1.0 -1.0 122.0 152.0",
    contour: null,
    murs: [
      { zone: "Z", profil: "vertical", d: "100,15 115,15 115,30 100,30",
        etiquette: [107.5, 22.5], taille: 9 },
      { zone: "M", profil: "dalle", d: "0,100 15,100 15,115 0,115",
        etiquette: [7.5, 107.5], taille: 9 },
    ],
    reperes: [{ texte: "Escalier", x: 97, y: 52 }],
    ...surcharges,
  };
}

// --- Le garde-fou de format ------------------------------------------------

test("un plan bien formé se dessine", () => {
  assert.equal(peutDessiner(plan()), true);
  assert.notEqual(decrire(plan()), null);
});

test("un format inconnu ne se dessine PAS", () => {
  // Le cas qui compte : le serveur passe à « polygones/2 » sans que la page
  // suive. Mieux vaut pas de mur qu'un mur faux.
  assert.equal(peutDessiner(plan({ format: "polygones/2" })), false);
  assert.equal(decrire(plan({ format: "polygones/2" })), null);
});

test("l'ancienne grille 8×7 ne se dessine pas non plus", () => {
  // Ce que `PLAN` était avant la spec 028. Une page servie depuis un cache
  // pourrait la recevoir ; elle doit la refuser, pas l'interpréter de travers.
  const grille = { format: "grille/1", lignes: [[null, "D"], ["M", "K"]] };
  assert.equal(peutDessiner(grille), false);
  assert.equal(decrire(grille), null);
});

test("un plan sans format ne se dessine pas", () => {
  const sans = plan();
  delete sans.format;
  assert.equal(peutDessiner(sans), false);
});

test("ce qui n'est pas un plan ne fait pas tomber la page", () => {
  for (const rien of [null, undefined, "", 0, [], "polygones/1", { }]) {
    assert.equal(peutDessiner(rien), false, "pour " + JSON.stringify(rien));
    assert.equal(decrire(rien), null);
  }
});

test("plusieurs formats peuvent être acceptés le temps d'un déploiement", () => {
  // La page servie et l'API ne sont jamais mises à jour à la même seconde.
  assert.ok(Array.isArray(FORMATS_RENDUS));
  assert.ok(FORMATS_RENDUS.includes("polygones/1"));
});

// --- Un plan abîmé, mais pas mortellement ----------------------------------

test("un plan estampillé juste mais vide ne se dessine pas", () => {
  // Un cadre blanc que personne ne saurait interpréter est pire que rien.
  assert.equal(peutDessiner(plan({ murs: [] })), false);
  assert.equal(peutDessiner(plan({ murs: "pas un tableau" })), false);
});

test("un plan sans cadrage ne se dessine pas", () => {
  assert.equal(peutDessiner(plan({ cadrage: "" })), false);
  assert.equal(peutDessiner(plan({ cadrage: null })), false);
});

test("un mur abîmé est ignoré, les autres se dessinent", () => {
  // Un relevé auquel il manque une lettre doit montrer les autres zones
  // plutôt que rien.
  const abime = plan({ murs: [
    { zone: "", profil: "vertical", d: "0,0 1,0 1,1", etiquette: [0, 0], taille: 9 },
    { zone: "M", profil: "dalle", d: "sans virgule", etiquette: [0, 0], taille: 9 },
    { zone: "Z", profil: "vertical", d: "0,0 1,0 1,1", etiquette: [1, 1], taille: 9 },
  ] });
  assert.equal(peutDessiner(abime), true);
  assert.deepEqual([...zonesDe(abime)], ["Z"]);
});

test("un mur sans taille ni étiquette se dessine quand même", () => {
  const maigre = plan({ murs: [{ zone: "Z", d: "0,0 1,0 1,1" }] });
  const dessin = decrire(maigre);
  const groupe = dessin.enfants.find((e) => e.attrs && e.attrs["data-zone"] === "Z");
  assert.ok(groupe);
  const lettre = groupe.enfants.find((e) => e.tag === "text");
  assert.ok(Number(lettre.attrs["font-size"]) > 0);
  assert.equal(groupe.attrs["data-profil"], "vertical");   // repli
});

// --- Les zones, seul point de contact avec les blocs -----------------------

test("les zones se demandent AU PLAN, pas aux blocs", () => {
  assert.deepEqual([...zonesDe(plan())].sort(), ["M", "Z"]);
});

test("un plan qu'on ne sait pas dessiner ne porte aucune zone", () => {
  // C'est ce qui rend les blocs non cliquables au lieu d'ouvrir un mur vide.
  assert.equal(zonesDe(plan({ format: "polygones/9" })).size, 0);
  assert.equal(zonesDe(null).size, 0);
});

// --- La description du dessin ----------------------------------------------

test("chaque zone est un groupe qui porte sa lettre", () => {
  const dessin = decrire(plan());
  const groupes = dessin.enfants.filter((e) => e.attrs && e.attrs["data-zone"]);
  assert.equal(groupes.length, 2);
  for (const g of groupes) {
    assert.equal(g.tag, "g");
    assert.ok(g.attrs.style.includes("transform-origin"));
    assert.deepEqual(g.enfants.map((e) => e.attrs.class),
                     ["mur", "trame", "lettre"]);
  }
});

test("les cadres d'état sont une couche PEINTE APRÈS tous les murs", () => {
  // En SVG l'ordre de peinture est l'ordre du document, et il n'y a pas de
  // `z-index` : un cadre dessiné dans le groupe de sa zone se fait rogner sur
  // les arêtes qu'elle partage avec sa voisine — et le relevé d'Annonay en
  // partage beaucoup.
  const dessin = decrire(plan());
  const iCadres = dessin.enfants.findIndex(
    (e) => e.attrs && e.attrs.class === "cadres-zone");
  const iDernierMur = dessin.enfants.reduce(
    (max, e, i) => (e.attrs && e.attrs["data-zone"] ? i : max), -1);
  assert.ok(iCadres > iDernierMur, "les cadres doivent venir après les murs");
  assert.deepEqual(dessin.enfants[iCadres].enfants.map((e) => e.attrs["data-zone"]),
                   ["Z", "M"]);
});

test("le cadrage du dessin est celui que le serveur a calculé", () => {
  // La marge se prend sur le cadrage et JAMAIS sur les coordonnées : sept murs
  // d'Annonay touchent le bord du dessin.
  assert.equal(decrire(plan()).attrs.viewBox, "-1.0 -1.0 122.0 152.0");
});

test("un contour ne se dessine que s'il existe", () => {
  assert.equal(decrire(plan()).enfants.some((e) => e.attrs.class === "contour"), false);
  const avec = decrire(plan({ contour: "0,0 10,0 10,10" }));
  // Sous tous les murs : c'est le trait de la salle, pas un cadre d'état. Les
  // découpes, elles, ne peignent rien et peuvent le précéder.
  const iContour = avec.enfants.findIndex((e) => e.attrs.class === "contour");
  const iPremierMur = avec.enfants.findIndex((e) => e.attrs["data-zone"]);
  assert.ok(iContour >= 0 && iContour < iPremierMur);
});

test("les repères sont rendus, et un repère abîmé est sauté", () => {
  const dessin = decrire(plan({ reperes: [
    { texte: "Haut", x: 1, y: 2 }, { x: 3, y: 4 }, null,
  ] }));
  const textes = dessin.enfants.filter((e) => e.attrs.class === "repere-plan");
  assert.deepEqual(textes.map((t) => t.texte), ["Haut"]);
});

// --- Le montage, et la décoration ------------------------------------------

/** Le strict minimum de DOM dont `monter` et `decorer` ont besoin. */
function faireDocument() {
  function creer(tag) {
    const n = {
      tag, attributs: {}, enfants: [], textContent: undefined,
      classes: new Set(),
      setAttribute(c, v) { this.attributs[c] = v; },
      getAttribute(c) { return this.attributs[c] ?? null; },
      removeAttribute(c) { delete this.attributs[c]; },
      appendChild(e) { this.enfants.push(e); return e; },
      querySelectorAll(sel) {
        assert.equal(sel, "[data-zone]");
        const trouves = [];
        (function descendre(n) {
          if (n.attributs["data-zone"] !== undefined) trouves.push(n);
          n.enfants.forEach(descendre);
        })(this);
        return trouves;
      },
      /** Juste assez pour « .une-classe » : c'est tout ce que `decorer`
       *  demande, et un faux DOM qui en ferait plus mentirait sur ce dont le
       *  code a besoin. */
      querySelector(sel) {
        assert.ok(sel.startsWith("."), "le faux DOM ne sait chercher qu'une classe");
        const classe = sel.slice(1);
        let trouve = null;
        (function descendre(n) {
          if (trouve) return;
          if ((n.attributs.class || "").split(" ").includes(classe)) { trouve = n; return; }
          n.enfants.forEach(descendre);
        })(this);
        return trouve;
      },
    };
    n.classList = {
      add: (...c) => c.forEach((x) => n.classes.add(x)),
      remove: (...c) => c.forEach((x) => n.classes.delete(x)),
    };
    return n;
  }
  return { createElementNS: (_ns, tag) => creer(tag) };
}

test("le montage traduit la description sans rien décider", () => {
  const racine = monter(decrire(plan()), faireDocument());
  assert.equal(racine.tag, "svg");
  assert.equal(racine.attributs.viewBox, "-1.0 -1.0 122.0 152.0");
  const zones = racine.querySelectorAll("[data-zone]");
  // Par zone : le pan, son cadre, son compteur.
  assert.equal(zones.length, 6);
  const textes = zones[0].enfants.filter((e) => e.tag === "text");
  // Le pan ne porte que sa lettre ; le compteur vit une couche plus haut.
  assert.deepEqual(textes.map((l) => l.textContent), ["Z"]);
});

test("monter ce qui n'est pas décrit ne rend rien", () => {
  assert.equal(monter(null, faireDocument()), null);
});

test("décorer pose l'état sur toutes les formes d'une zone", () => {
  const racine = monter(decrire(plan()), faireDocument());
  const trouvee = decorer(racine, { Z: "finie", M: "reste" }, "M");
  assert.equal(trouvee, true);

  const par = {};
  for (const n of racine.querySelectorAll("[data-zone]")) {
    (par[n.getAttribute("data-zone")] ||= []).push([...n.classes]);
  }
  // Les TROIS formes d'une zone reçoivent le même état : le pan porte
  // l'opacité, le cadre porte le contour, le compteur porte le chiffre — et
  // tous rebondissent ensemble quand la zone est visée.
  assert.deepEqual(par.Z, [["z-finie"], ["z-finie"], ["z-finie"]]);
  assert.deepEqual(par.M, Array(3).fill(["z-reste", "visee"]));
});

test("décorer une zone que le plan ne porte pas le dit", () => {
  // C'est ce qui permet à la page de ne PAS ouvrir le mur plutôt que de
  // l'ouvrir sur rien.
  const racine = monter(decrire(plan()), faireDocument());
  assert.equal(decorer(racine, { Z: "finie" }, "INCONNUE"), false);
});

test("décorer efface l'état précédent avant de poser le nouveau", () => {
  // Sans le nettoyage, changer de zone laisserait deux zones visées.
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "finie", M: "reste" }, "Z");
  decorer(racine, { Z: "finie", M: "reste" }, "M");
  const visees = racine.querySelectorAll("[data-zone]")
    .filter((n) => n.classes.has("visee"))
    .map((n) => n.getAttribute("data-zone"));
  assert.deepEqual([...new Set(visees)], ["M"]);
});

test("décorer sans racine ne casse rien", () => {
  assert.equal(decorer(null, {}, "M"), false);
});

// --- L'avancement par zone — spec 036 --------------------------------------
//
// Ce que ces tests protègent : le chiffre posé sur une zone dit « blocs
// validés sur blocs de ton circuit dans cette zone ». Deux erreurs y seraient
// muettes et coûteuses — un compteur qui reste affiché sur la zone d'un autre
// grimpeur, et un « 0/0 » posé sur les onze zones où le grimpeur n'a rien à
// faire, qui l'enverrait chercher du travail là où il n'y en a pas.

/** Les comptes tels que `comptesDesZones` les rend. */
const COMPTES = {
  Z: { total: 4, faits: 1, grimpes: 1, credites: 0 },
  M: { total: 2, faits: 2, grimpes: 1, credites: 1 },
};

/** La géométrie de la pastille d'une zone, dans un plan monté. */
function socleMonte(racine, zone) {
  for (const n of racine.querySelectorAll("[data-zone]")) {
    if (n.getAttribute("data-zone") !== zone) continue;
    const socle = n.querySelector(".socle-compte");
    if (socle) {
      return ["x", "y", "width", "height", "rx"].map((c) => socle.attributs[c]);
    }
  }
  return null;
}

/** Le compteur d'une zone, dans un plan monté. */
function compteAffiche(racine, zone) {
  for (const n of racine.querySelectorAll("[data-zone]")) {
    if (n.getAttribute("data-zone") !== zone) continue;
    const chiffre = n.querySelector(".compte-zone");
    if (chiffre) return { texte: chiffre.textContent, classes: [...chiffre.classes],
                          zone: [...n.classes] };
  }
  return null;
}

test("chaque zone décrit son compteur, VIDE", () => {
  // Vide, parce que le dessin est le même pour tout le monde : le plan est
  // monté une fois par grimpeur, et c'est la décoration qui écrit le chiffre.
  const dessin = decrire(plan());
  const groupe = compteurDecrit(dessin, "Z");
  const compte = groupe.enfants.find((e) => e.attrs.class === "compte-zone");
  assert.equal(compte.texte, "");
  assert.equal(compte.attrs.x, 107.5);                       // l'axe de la lettre
  assert.equal(compte.attrs.y, 22.5 + 9 * COMPTE_DESCENTE);  // dessous
  assert.equal(Number(compte.attrs["data-corps"]), 9);       // le corps de la lettre
});

// --- La pastille — la pose B, tranchée par Adrien le 03/09 -----------------
//
// Ce que ces tests protègent : la pastille se dimensionne sur la LETTRE et
// jamais sur son texte. C'est la seule chose qui la borne — le serveur a déjà
// borné la lettre par la boîte du pan — et c'est précisément ce qui manquait à
// la première version, où le socle sortait du pan. Un socle qui se remettrait
// à suivre son libellé repasserait le bug sans qu'aucun autre test bronche.

/** La pastille d'une zone, dans une description. */
function socleDecrit(dessin, zone) {
  return compteurDecrit(dessin, zone).enfants
    .find((e) => e.attrs.class === "socle-compte");
}

test("chaque zone décrit sa pastille, centrée sur l'axe de la lettre", () => {
  const socle = socleDecrit(decrire(plan()), "Z");
  const h = 9 * COMPTE_ECHELLE * PASTILLE_HAUTEUR;
  const l = 9 * PASTILLE_LARGEUR;
  assert.equal(Number(socle.attrs.width), Number(l.toFixed(2)));
  assert.equal(Number(socle.attrs.height), Number(h.toFixed(2)));
  // Centrée en x sur l'axe de la lettre, en y sur la descente du compteur.
  assert.equal(Number(socle.attrs.x) + Number(socle.attrs.width) / 2, 107.5);
  const cy = 22.5 + 9 * COMPTE_DESCENTE;
  assert.ok(Math.abs(Number(socle.attrs.y) + h / 2 - cy) < 0.01);
  // Un stade, pas un rectangle : le rayon vaut la demi-hauteur.
  assert.equal(Number(socle.attrs.rx), Number((h / 2).toFixed(2)));
});

test("dans la pastille : le socle, puis le vert, puis le chiffre", () => {
  // L'ordre du document EST l'ordre de peinture. Le vert décrit après le
  // chiffre le recouvrirait ; décrit avant le socle, il serait invisible.
  const classes = compteurDecrit(decrire(plan()), "Z").enfants
    .map((e) => e.attrs.class);
  assert.deepEqual(classes, ["socle-compte", "remplit-compte", "compte-zone"]);
});

test("la pastille ne bouge PAS quand le libellé s'allonge", () => {
  // ⚠️ LE TEST QUI PROTÈGE LA POSE B. Un socle calibré sur son texte a une
  // largeur que rien ne borne : c'est ce qui le faisait sortir du pan à la
  // première maquette. Ici « 10/12 » rétrécit le CHIFFRE et laisse le socle
  // exactement où il est.
  const racine = monter(decrire(plan()), faireDocument());
  const avant = socleMonte(racine, "Z");
  decorer(racine, { Z: "reste" }, null, { Z: { total: 12, faits: 10 } });
  assert.deepEqual(socleMonte(racine, "Z"), avant);
  // Et le chiffre, lui, a bien rétréci.
  const chiffre = compteAffiche(racine, "Z");
  assert.equal(chiffre.texte, "10/12");
});

test("le chiffre le plus large tient DANS la pastille", () => {
  // « 1/4 » est le pire cas en largeur : les libellés plus longs rétrécissent.
  // 3 caractères au pire glyphe tabulaire (0,58 du corps) contre la largeur du
  // socle. Sans cette marge, le chiffre déborderait du fond censé le porter.
  const largeurTexte = 3 * 0.58 * tailleDuCompte(9, "1/4");
  assert.ok(largeurTexte <= 9 * PASTILLE_LARGEUR,
            largeurTexte + " ne tient pas dans " + 9 * PASTILLE_LARGEUR);
});

test("un mur sans taille décrit quand même un compteur lisible", () => {
  // Même repli que la lettre : 6. Un compteur de taille nulle serait invisible
  // sans que rien ne le dise.
  const maigre = plan({ murs: [{ zone: "Z", d: "0,0 1,0 1,1" }] });
  const compte = compteurDecrit(decrire(maigre), "Z").enfants
    .find((e) => e.attrs.class === "compte-zone");
  assert.ok(Number(compte.attrs["font-size"]) > 0);
});

test("décorer écrit le compteur de chaque zone du circuit", () => {
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste", M: "finie" }, null, COMPTES);
  assert.equal(compteAffiche(racine, "Z").texte, "1/4");
  assert.equal(compteAffiche(racine, "M").texte, "2/2");
});

test("une zone terminée a sa pastille PLEINE, et son chiffre reste à l'encre", () => {
  // ⚠️ Le chiffre virait au vert quand la pastille était un fond neutre. Sur
  // une pastille pleine de vert, vert sur vert ne se lit pas : c'est le
  // remplissage qui dit « terminée », et le chiffre reste lisible.
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste", M: "finie" }, null, COMPTES);
  assert.equal(compteAffiche(racine, "M").classes.includes("compte-finie"), false);
  assert.equal(Number(jaugeMontee(racine, "M").getAttribute("width")),
               Number(jaugeMontee(racine, "M").getAttribute("data-plein")));
});

test("une zone SANS bloc du circuit ne porte aucun compteur", () => {
  // Pas de « 0/0 » : l'absence est l'information. Un chiffre sur une zone
  // effacée enverrait chercher du travail là où il n'y en a pas.
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste" }, null, { Z: COMPTES.Z });
  const m = compteAffiche(racine, "M");
  assert.equal(m.texte, "");
  assert.equal(m.zone.includes("a-compte"), false);
  assert.equal(compteAffiche(racine, "Z").zone.includes("a-compte"), true);
});

test("un compteur ne survit pas à la décoration suivante", () => {
  // ⚠️ Le DESSIN PERSISTE d'une repeinture à l'autre — c'est ce qui permet la
  // transition, et ce qui rend la fiche « en direct ». Sans remise à zéro, un
  // bloc qui quitte le circuit entre deux rafraîchissements laisserait son
  // « 1/4 » posé sur une zone où le grimpeur n'a plus rien à faire.
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste", M: "finie" }, null, COMPTES);
  decorer(racine, { M: "reste" }, null, { M: { total: 3, faits: 0 } });
  assert.equal(compteAffiche(racine, "Z").texte, "");
  assert.equal(compteAffiche(racine, "Z").zone.includes("a-compte"), false);
  assert.equal(compteAffiche(racine, "M").texte, "0/3");
});

test("décorer sans comptes laisse le mur exactement comme avant", () => {
  // Le quatrième argument est optionnel : un appelant qui ne le passe pas doit
  // obtenir le mur de la spec 026, pas une exception.
  const racine = monter(decrire(plan()), faireDocument());
  assert.equal(decorer(racine, { Z: "finie" }, "Z"), true);
  assert.equal(compteAffiche(racine, "Z").texte, "");
});

test("un compte pour une zone que le plan ne porte pas est ignoré", () => {
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { QQQ: "reste" }, null, { QQQ: { total: 2, faits: 1 } });
  assert.equal(compteAffiche(racine, "Z").texte, "");
});

test("le corps du compteur rétrécit avec la longueur du libellé", () => {
  // ⚠️ LA BORNE EST LA PASTILLE, et elle fait 1,6 fois la lettre : « 12/15 »
  // tient donc à sa taille pleine, alors qu'il rétrécissait quand le socle
  // faisait une fois la lettre. C'est le bénéfice direct de l'élargissement —
  // « repasse sa taille à celle d'origine » (Adrien, 03/09).
  assert.equal(tailleDuCompte(9, "1/4"), 9 * COMPTE_ECHELLE);
  assert.equal(tailleDuCompte(9, "12/15"), 9 * COMPTE_ECHELLE);
  // Un libellé qu'aucun élargissement raisonnable ne ferait tenir, lui,
  // rétrécit toujours au lieu de déborder.
  assert.ok(tailleDuCompte(9, "100/120") < tailleDuCompte(9, "1/4"));
  assert.ok(tailleDuCompte(9, "100/120") * 0.58 * 7 <= 9 * PASTILLE_LARGEUR + 1e-9);
});

test("un compteur sans taille ni libellé reste un nombre positif", () => {
  for (const taille of [0, -3, null, undefined, "gros"]) {
    assert.ok(tailleDuCompte(taille, "1/4") > 0, "pour " + taille);
  }
  assert.ok(tailleDuCompte(9, "") > 0);
  assert.ok(tailleDuCompte(9, null) > 0);
});

test("les compteurs sont écrits APRÈS les cadres, donc après tout", () => {
  // ⚠️ CE QUE CET ORDRE PROTÈGE : la pastille fait 1,6 fois la lettre, donc
  // 14,4 unités dans un pan de 15 — elle croise le cadre « terminée » de 0,5
  // unité de chaque côté. Peinte dessous, elle se ferait couper par lui à ses
  // deux extrémités, là où le vert dit justement où il s'arrête.
  const dessin = decrire(plan());
  const iCadres = dessin.enfants.findIndex((e) => e.attrs.class === "cadres-zone");
  const iCompteurs = dessin.enfants.findIndex(
    (e) => e.attrs.class === "compteurs-zone");
  assert.ok(iCadres >= 0 && iCompteurs > iCadres);
});

test("le compteur ne porte plus de halo : la pastille le remplace", () => {
  // Un halo est un contour découpé sur la forme des glyphes ; il se battait
  // avec les six aplats de profil. La pastille est un FOND. Garder les deux
  // ferait un liseré clair autour de chaque chiffre, sur le socle clair.
  const compte = compteurDecrit(decrire(plan()), "Z").enfants
    .find((e) => e.attrs.class === "compte-zone");
  assert.equal(compte.attrs["stroke-width"], undefined);
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste" }, null, COMPTES);
  for (const n of racine.querySelectorAll("[data-zone]")) {
    const c = n.querySelector(".compte-zone");
    if (c) assert.equal(c.attributs["stroke-width"], undefined);
  }
});

// --- La pastille qui se remplit — spec 036, 03/09 --------------------------
//
// Ce que ces tests protègent : le vert DANS la pastille dit la part faite. Deux
// erreurs y seraient muettes et coûteuses — un vert qui reste peint sur la
// fiche du grimpeur suivant, et un vert qui déborde du socle censé le porter.

/** La barre de remplissage d'une zone, dans un plan monté. */
function jaugeMontee(racine, zone) {
  for (const n of racine.querySelectorAll("[data-zone]")) {
    if (n.getAttribute("data-zone") !== zone) continue;
    const jauge = n.querySelector(".remplit-compte");
    if (jauge) return jauge;
  }
  return null;
}

test("la part faite se dit entre 0 et 1, et pas au-delà", () => {
  assert.equal(partFaite({ total: 4, faits: 1 }), 0.25);
  assert.equal(partFaite({ total: 4, faits: 0 }), 0);
  assert.equal(partFaite({ total: 4, faits: 4 }), 1);
  // Un compte incohérent ne doit pas peindre au-delà du socle.
  assert.equal(partFaite({ total: 2, faits: 7 }), 1);
  assert.equal(partFaite({ total: 2, faits: -3 }), 0);
});

test("une zone sans bloc du circuit n'a PAS de jauge, pas une jauge à zéro", () => {
  assert.equal(partFaite(undefined), null);
  assert.equal(partFaite({ total: 0, faits: 0 }), null);
  assert.equal(partFaite({}), null);
});

test("la jauge est décrite VIDE, découpée dans la forme du socle", () => {
  // ⚠️ LE BOUT DROIT. Le vert est un rectangle franc découpé dans le socle : il
  // épouse son bord arrondi à gauche et se coupe net à droite, ce qui se lit
  // comme un niveau. Arrondi de son côté, il ferait une petite pastille dans la
  // grande — deux objets au lieu d'un.
  const dessin = decrire(plan());
  const socle = socleDecrit(dessin, "Z");
  const jauge = compteurDecrit(dessin, "Z").enfants
    .find((e) => e.attrs.class === "remplit-compte");
  assert.equal(jauge.attrs.width, 0);
  assert.equal(jauge.attrs["clip-path"], "url(#plan-socle-Z)");
  assert.equal(jauge.attrs.rx, undefined);
  // Elle part du bord gauche du socle, et en a exactement la hauteur.
  assert.equal(jauge.attrs.x, socle.attrs.x);
  assert.equal(jauge.attrs.y, socle.attrs.y);
  assert.equal(jauge.attrs.height, socle.attrs.height);
  // `data-plein` est la seule chose dont `decorer` a besoin : la largeur du
  // socle, pour en peindre une fraction sans relire une géométrie.
  assert.equal(jauge.attrs["data-plein"], socle.attrs.width);
});

test("la découpe reprend la forme du socle, arrondi compris", () => {
  const dessin = decrire(plan());
  const socle = socleDecrit(dessin, "Z");
  const defs = dessin.enfants.find((e) => e.tag === "defs");
  const decoupe = defs.enfants.find((e) => e.attrs.id === "plan-socle-Z");
  assert.equal(decoupe.enfants[0].tag, "rect");
  for (const c of ["x", "y", "width", "height", "rx"]) {
    assert.equal(decoupe.enfants[0].attrs[c], socle.attrs[c], "sur " + c);
  }
});

test("décorer remplit la pastille à hauteur de l'avancement", () => {
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste", M: "finie" }, null, COMPTES);
  const plein = Number(jaugeMontee(racine, "Z").getAttribute("data-plein"));
  // Z est à 1/4 : le quart du socle.
  assert.equal(Number(jaugeMontee(racine, "Z").getAttribute("width")),
               Number((plein * 0.25).toFixed(2)));
  // M est à 2/2 : le socle entier.
  assert.equal(Number(jaugeMontee(racine, "M").getAttribute("width")),
               Number(jaugeMontee(racine, "M").getAttribute("data-plein")));
});

test("une zone à 0/4 a une pastille, et un vert de largeur nulle", () => {
  // Le zéro se dit : la pastille est là, avec « 0/4 » dessus, et rien de vert.
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste" }, null, { Z: { total: 4, faits: 0 } });
  assert.equal(compteAffiche(racine, "Z").texte, "0/4");
  assert.equal(Number(jaugeMontee(racine, "Z").getAttribute("width")), 0);
});

test("un vert ne survit pas à la décoration suivante", () => {
  // ⚠️ Le DESSIN PERSISTE d'une repeinture à l'autre. Sans remise à zéro, la
  // pastille d'un grimpeur resterait à moitié pleine sur la fiche du suivant.
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste", M: "finie" }, null, COMPTES);
  decorer(racine, { M: "reste" }, null, { M: { total: 4, faits: 1 } });
  assert.equal(Number(jaugeMontee(racine, "Z").getAttribute("width")), 0);
  const plein = Number(jaugeMontee(racine, "M").getAttribute("data-plein"));
  assert.equal(Number(jaugeMontee(racine, "M").getAttribute("width")),
               Number((plein * 0.25).toFixed(2)));
});

test("décorer sans comptes ne remplit aucune pastille", () => {
  // Le mur de la spec 026, intact : ni chiffre, ni vert.
  const racine = monter(decrire(plan()), faireDocument());
  assert.equal(decorer(racine, { Z: "finie" }, "Z"), true);
  assert.equal(compteAffiche(racine, "Z").texte, "");
  assert.equal(Number(jaugeMontee(racine, "Z").getAttribute("width")), 0);
});

test("la pastille et son vert s'allument ensemble, ou pas du tout", () => {
  // `a-compte` est ce que le CSS regarde pour peindre le socle ET son vert.
  // Posée sur le seul compteur, elle laisserait un socle vide sur les zones où
  // le grimpeur n'a rien à faire.
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste" }, null, { Z: { total: 4, faits: 0 } });
  const comptees = racine.querySelectorAll("[data-zone]")
    .filter((n) => n.classes.has("a-compte"))
    .map((n) => n.getAttribute("data-zone"));
  assert.deepEqual(comptees, ["Z", "Z", "Z"]);
});

// --- La lettre a monté — la position « E », choisie le 03/09 ---------------

test("la lettre monte au-dessus de son centroïde", () => {
  // ⚠️ CE QUE CE TEST PROTÈGE : c'est la seule place disponible. Sous la
  // pastille il ne restait que 0,009 × taille, et le halo de la lettre
  // recouvrait la pastille de 0,104. « Là c'est trop proche » demandait de
  // séparer deux objets qui se touchaient, pas d'ajouter de la place en bas.
  const lettre = panDecrit(decrire(plan()), "Z").enfants
    .find((e) => e.attrs.class === "lettre");
  assert.equal(lettre.attrs.x, 107.5);                 // l'axe ne bouge pas
  assert.equal(Number(lettre.attrs.y), Number((22.5 - 9 * LETTRE_MONTEE).toFixed(2)));
  assert.ok(LETTRE_MONTEE > 0);
});

test("les trois airs du pan sont égaux — la position « E »", () => {
  // Le calcul qui fixe LETTRE_MONTEE et COMPTE_DESCENTE, réécrit ici : si
  // quelqu'un touche un ratio, c'est cette égalité-là qui doit se rediscuter,
  // et pas se casser en silence.
  const DEMI_PAN = 15 / 2 / 9;             // un pan de 15 pour une lettre de 9
  const HALO_LETTRE = 0.36 + 0.24 / 2;     // glyphe + demi-épaisseur du halo
  const DEMI_SOCLE = COMPTE_ECHELLE * PASTILLE_HAUTEUR / 2;

  const haut = DEMI_PAN - (HALO_LETTRE + LETTRE_MONTEE);
  const entre = (COMPTE_DESCENTE - DEMI_SOCLE) - (HALO_LETTRE - LETTRE_MONTEE);
  const bas = DEMI_PAN - (COMPTE_DESCENTE + DEMI_SOCLE);
  for (const [nom, air] of [["haut", haut], ["entre", entre], ["bas", bas]]) {
    assert.ok(Math.abs(air - 0.086) < 0.002, nom + " vaut " + air.toFixed(4));
  }
});
