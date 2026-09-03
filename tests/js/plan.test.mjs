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
  COMPTE_DESCENTE, COMPTE_ECHELLE, FORMATS_RENDUS, PASTILLE_HAUTEUR,
  PASTILLE_LARGEUR, decorer, decrire, monter,
  peutDessiner, tailleDuCompte, zonesDe,
} from "../../climbcontest/static/resultats/plan.js";

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
                     ["mur", "trame", "lettre", "socle-compte", "compte-zone"]);
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
  assert.equal(avec.enfants[0].attrs.class, "contour");
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
  // Deux groupes plus deux cadres.
  assert.equal(zones.length, 4);
  const textes = zones[0].enfants.filter((e) => e.tag === "text");
  // La lettre, puis le compteur — monté VIDE : c'est `decorer` qui l'écrit.
  assert.deepEqual(textes.map((l) => l.textContent), ["Z", ""]);
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
  // Le groupe ET son cadre reçoivent le même état : c'est le cadre qui porte
  // le contour, le groupe qui porte l'opacité.
  assert.deepEqual(par.Z, [["z-finie"], ["z-finie"]]);
  assert.deepEqual(par.M, [["z-reste", "visee"], ["z-reste", "visee"]]);
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
  const groupe = dessin.enfants.find((e) => e.attrs && e.attrs["data-zone"] === "Z");
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
  const groupe = dessin.enfants.find((e) => e.attrs && e.attrs["data-zone"] === zone);
  return groupe.enfants.find((e) => e.attrs.class === "socle-compte");
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

test("la pastille est peinte APRÈS la lettre et AVANT le chiffre", () => {
  // L'ordre du document EST l'ordre de peinture : un socle décrit après le
  // chiffre l'effacerait, décrit avant la lettre il ne couvrirait pas la queue
  // de son halo.
  const groupe = decrire(plan()).enfants
    .find((e) => e.attrs && e.attrs["data-zone"] === "Z");
  const classes = groupe.enfants.map((e) => e.attrs.class);
  assert.ok(classes.indexOf("socle-compte") > classes.indexOf("lettre"));
  assert.ok(classes.indexOf("socle-compte") < classes.indexOf("compte-zone"));
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
  const groupe = decrire(maigre).enfants
    .find((e) => e.attrs && e.attrs["data-zone"] === "Z");
  const compte = groupe.enfants.find((e) => e.attrs.class === "compte-zone");
  assert.ok(Number(compte.attrs["font-size"]) > 0);
});

test("décorer écrit le compteur de chaque zone du circuit", () => {
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste", M: "finie" }, null, COMPTES);
  assert.equal(compteAffiche(racine, "Z").texte, "1/4");
  assert.equal(compteAffiche(racine, "M").texte, "2/2");
});

test("une zone terminée porte son compteur dans le vert", () => {
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste", M: "finie" }, null, COMPTES);
  assert.equal(compteAffiche(racine, "M").classes.includes("compte-finie"), true);
  assert.equal(compteAffiche(racine, "Z").classes.includes("compte-finie"), false);
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
  assert.equal(compteAffiche(racine, "M").classes.includes("compte-finie"), false);
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
  // « 1/4 » sort à sa taille pleine, « 12/15 » rétrécit au lieu de déborder du
  // pan. La borne est la LARGEUR : le libellé ne dépasse jamais une fois la
  // taille de la lettre.
  assert.equal(tailleDuCompte(9, "1/4"), 9 * COMPTE_ECHELLE);
  assert.ok(tailleDuCompte(9, "12/15") < tailleDuCompte(9, "1/4"));
  assert.ok(tailleDuCompte(9, "12/15") * 0.58 * 5 <= 9 + 1e-9);
  assert.ok(tailleDuCompte(9, "100/120") * 0.58 * 7 <= 9 + 1e-9);
});

test("un compteur sans taille ni libellé reste un nombre positif", () => {
  for (const taille of [0, -3, null, undefined, "gros"]) {
    assert.ok(tailleDuCompte(taille, "1/4") > 0, "pour " + taille);
  }
  assert.ok(tailleDuCompte(9, "") > 0);
  assert.ok(tailleDuCompte(9, null) > 0);
});

test("le compteur est écrit APRÈS la lettre", () => {
  // En SVG l'ordre de peinture est l'ordre du document : la pastille et son
  // chiffre passent sur la lettre, jamais l'inverse.
  const groupe = decrire(plan()).enfants
    .find((e) => e.attrs && e.attrs["data-zone"] === "Z");
  const classes = groupe.enfants.map((e) => e.attrs.class);
  assert.ok(classes.indexOf("compte-zone") > classes.indexOf("lettre"));
});

test("le compteur ne porte plus de halo : la pastille le remplace", () => {
  // Un halo est un contour découpé sur la forme des glyphes ; il se battait
  // avec les six aplats de profil. La pastille est un FOND. Garder les deux
  // ferait un liseré clair autour de chaque chiffre, sur le socle clair.
  const groupe = decrire(plan()).enfants
    .find((e) => e.attrs && e.attrs["data-zone"] === "Z");
  const compte = groupe.enfants.find((e) => e.attrs.class === "compte-zone");
  assert.equal(compte.attrs["stroke-width"], undefined);
  const racine = monter(decrire(plan()), faireDocument());
  decorer(racine, { Z: "reste" }, null, COMPTES);
  for (const n of racine.querySelectorAll("[data-zone]")) {
    const c = n.querySelector(".compte-zone");
    if (c) assert.equal(c.attributs["stroke-width"], undefined);
  }
});
