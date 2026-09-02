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
  FORMATS_RENDUS, decorer, decrire, monter, peutDessiner, zonesDe,
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
    assert.deepEqual(g.enfants.map((e) => e.attrs.class), ["mur", "trame", "lettre"]);
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
  const lettres = zones[0].enfants.filter((e) => e.tag === "text");
  assert.deepEqual(lettres.map((l) => l.textContent), ["Z"]);
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
