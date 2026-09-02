// La fiche du grimpeur en direct — spec 026, la logique sans le DOM.
//
// Ce que ces tests protègent : ce qu'un parent lit sur son téléphone. Deux
// erreurs y seraient invisibles à la lecture et coûteuses le jour J — compter
// un bloc crédité comme non fait (« il te reste un bloc » sur une zone
// terminée), et perdre le retour arrière sur une adresse mal formée.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  A_FAIRE, CREDITE, FINIE, GRIMPE, RESTE,
  blocsDeZone, classesDeZone, compteDeZone, ecrireDiese, estFait,
  etatsDesZones, lireDiese, tousLesBlocs,
} from "../../climbcontest/static/resultats/suivi.js";

/** Une fiche comme le serveur la rend. */
const GROUPES = [
  { couleur: "Jaune", blocs: [
    { tag: "ZJ1", zone: "Z", numero: "J1", etat: GRIMPE },
    { tag: "BJ2", zone: "B", numero: "J2", etat: CREDITE },
  ] },
  { couleur: "Vert", blocs: [
    { tag: "ZV4", zone: "Z", numero: "V4", etat: GRIMPE },
    { tag: "MV5", zone: "M", numero: "V5", etat: RESTE },
  ] },
];

test("un bloc crédité compte comme fait", () => {
  // Il ne se PEINT pas comme un bloc grimpé — plein contre hachuré — mais il
  // pèse pareil au classement. Confondre les deux plans afficherait « il te
  // reste un bloc » sur une zone où le grimpeur n'a plus rien à faire.
  assert.equal(estFait(GRIMPE), true);
  assert.equal(estFait(CREDITE), true);
  assert.equal(estFait(RESTE), false);
});

test("les blocs se lisent à plat, dans l'ordre des groupes", () => {
  assert.deepEqual(tousLesBlocs(GROUPES).map((b) => b.tag),
                   ["ZJ1", "BJ2", "ZV4", "MV5"]);
});

test("une fiche vide ne casse rien", () => {
  assert.deepEqual(tousLesBlocs([]), []);
  assert.deepEqual(tousLesBlocs(undefined), []);
  assert.deepEqual(etatsDesZones([]), {});
});

test("un groupe sans blocs ne casse rien", () => {
  assert.deepEqual(tousLesBlocs([{ couleur: "Noir" }]), []);
});

test("l'état d'une zone : terminée quand tout est fait", () => {
  const etats = etatsDesZones(GROUPES);
  assert.equal(etats.Z, FINIE);      // ZJ1 et ZV4, grimpés
  assert.equal(etats.B, FINIE);      // BJ2, crédité — il compte
  assert.equal(etats.M, A_FAIRE);    // MV5, à faire
});

test("une zone où le grimpeur n'a rien à faire est ABSENTE, pas vide", () => {
  // L'absence est ce qui permet d'effacer les zones qui ne le concernent pas.
  // Une valeur « rien » forcerait chaque appelant à la distinguer de « reste ».
  const etats = etatsDesZones(GROUPES);
  assert.equal("X" in etats, false);
  assert.equal(etats.X, undefined);
});

test("un bloc sans zone n'invente pas de zone", () => {
  const etats = etatsDesZones([{ couleur: "Noir", blocs: [
    { tag: "??", zone: null, etat: RESTE },
  ] }]);
  assert.deepEqual(etats, {});
});

test("les blocs d'une zone, et son compte", () => {
  assert.deepEqual(blocsDeZone(GROUPES, "Z").map((b) => b.tag), ["ZJ1", "ZV4"]);
  assert.deepEqual(compteDeZone(GROUPES, "Z"), { total: 2, faits: 2 });
  assert.deepEqual(compteDeZone(GROUPES, "M"), { total: 1, faits: 0 });
  assert.deepEqual(compteDeZone(GROUPES, "X"), { total: 0, faits: 0 });
});

test("les classes d'une zone suivent son état", () => {
  const etats = etatsDesZones(GROUPES);
  assert.deepEqual(classesDeZone("Z", etats, null), ["z-finie"]);
  assert.deepEqual(classesDeZone("M", etats, null), ["z-reste"]);
  assert.deepEqual(classesDeZone("X", etats, null), ["z-rien"]);
});

test("la zone visée l'emporte sur son état, sans l'effacer", () => {
  // Arriver depuis un bloc doit rester le geste le plus lisible : c'est celui
  // qu'on vient de faire. Mais l'état reste posé — la feuille de style décide
  // lequel des deux prend le dessus, pas ce module.
  const etats = etatsDesZones(GROUPES);
  assert.deepEqual(classesDeZone("Z", etats, "Z"), ["z-finie", "visee"]);
  assert.deepEqual(classesDeZone("X", etats, "X"), ["z-rien", "visee"]);
});

// --- L'adresse, et donc le retour arrière ----------------------------------

test("le dièse porte le grimpeur, et la zone quand il y en a une", () => {
  assert.deepEqual(lireDiese("#g=42"), { grimpeur: 42, zone: null, mur: false });
  assert.deepEqual(lireDiese("#g=42&z=M"), { grimpeur: 42, zone: "M", mur: true });
  assert.deepEqual(lireDiese("g=42&z=M"), { grimpeur: 42, zone: "M", mur: true });
});

test("un `z` vide, c'est le mur SANS zone choisie", () => {
  // ⚠️ « Je suis au mur » est porté par l'ADRESSE et pas par une variable de
  // la page. Un drapeau garde a cote se posait avant l'ecriture du diese, et
  // tout rendu tombant entre les deux montrait le mur sans zone visee.
  assert.deepEqual(lireDiese("#g=42&z="), { grimpeur: 42, zone: null, mur: true });
  assert.equal(ecrireDiese({ grimpeur: 42, mur: true }), "#g=42&z=");
  assert.equal(ecrireDiese({ grimpeur: 42, zone: "M", mur: true }), "#g=42&z=M");
});

test("un dièse qu'on ne comprend pas rend un état vide, jamais une exception", () => {
  // La page l'applique APRÈS son premier rendu : un dièse abîmé doit laisser
  // le classement affiché, pas faire tomber la page.
  for (const diese of ["", "#", "#autre=1", "#g=", "#g=abc", "#g=-1", "#g=4.2",
                       null, undefined, 42, {}]) {
    assert.deepEqual(lireDiese(diese), { grimpeur: null, zone: null, mur: false },
                     "pour " + JSON.stringify(diese));
  }
});

test("une zone sans grimpeur ne veut rien dire", () => {
  // Le mur s'ouvre DEPUIS une fiche : une zone seule n'a personne à situer.
  assert.deepEqual(lireDiese("#z=M"), { grimpeur: null, zone: null, mur: false });
});

test("écrire puis relire rend la même chose", () => {
  for (const etat of [{ grimpeur: 42, zone: null, mur: false },
                      { grimpeur: 42, zone: null, mur: true },
                      { grimpeur: 42, zone: "M", mur: true },
                      { grimpeur: 7, zone: "Z", mur: true }]) {
    assert.deepEqual(lireDiese(ecrireDiese(etat)), etat);
  }
});

test("sans grimpeur, l'adresse se nettoie au lieu de garder un dièse vide", () => {
  assert.equal(ecrireDiese({}), "");
  assert.equal(ecrireDiese({ grimpeur: null, zone: "M" }), "");
  assert.equal(ecrireDiese(), "");
});
