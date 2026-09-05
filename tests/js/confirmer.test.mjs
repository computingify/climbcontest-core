// Le geste de confirmation — specs 044 et 046.
//
// ⚠️ CE FICHIER EXISTE POUR UNE RAISON PRÉCISE, et elle a coûté une CI rouge :
// le choix entre le maintien et le glissement se fait sur `matchMedia`, et le
// chromium **sans souris** de la CI répond faux à
// `(hover: hover) and (pointer: fine)`. Un test de navigateur qui affirmait
// « à la souris, c'est le maintien » testait donc l'agent d'intégration, pas le
// code. La règle se vérifie ici, avec une fenêtre feinte : c'est une décision
// pure, elle n'a pas besoin d'un vrai navigateur.
import { test } from "node:test";
import assert from "node:assert/strict";

import { ANNEAU, BOUTON, EMPRISE, MAINTIEN_MS, MARGE, PISTE_MAXI, surface }
  from "../../climbcontest/static/console/confirmer.js";

/** Une fenêtre qui répond ce qu'on lui dit, et rien d'autre. */
const fenetre = (reponse) => ({ matchMedia: (q) => ({ matches: reponse(q) }) });

test("un pointeur fin qui survole : on MAINTIENT", () => {
  assert.equal(surface(fenetre(() => true)), "maintien");
});

test("un pointeur grossier : on GLISSE", () => {
  assert.equal(surface(fenetre(() => false)), "glissement");
});

test("le survol seul ne suffit pas", () => {
  // Un écran tactile qui simule le survol répond vrai à `hover` et faux à
  // `pointer: fine`. La requête exige les DEUX ; on vérifie qu'on ne la casse
  // pas en la coupant en morceaux.
  const q = "(hover: hover) and (pointer: fine)";
  assert.equal(surface(fenetre((x) => x === q)), "maintien");
  assert.equal(surface(fenetre((x) => x !== q)), "glissement");
});

test("sans matchMedia, on retombe sur le maintien", () => {
  // ⚠️ Le repli est le MAINTIEN et non le glissement : il s'opère à la souris
  // ET au clavier, alors qu'un glissement demande un pointeur. Un navigateur
  // qui ne sait pas dire ce qu'il a doit recevoir le geste qui marche partout.
  assert.equal(surface({}), "maintien");
});

test("les cotes du glissement sont celles de Sowel", () => {
  // Relevees dans `SlideToConfirm.tsx` (spec 146) : piste plafonnee a 260,
  // bouton 50, marge 4 -- donc une course de 202 px. Elles sont justifiees
  // la-bas : pleine largeur sur un telephone de 393 px, le geste part du coin
  // inferieur gauche, le point le plus loin du pouce.
  assert.equal(BOUTON, 50);
  assert.equal(MARGE, 4);
  assert.equal(EMPRISE, 58);
  assert.equal(PISTE_MAXI, 260);
  assert.equal(PISTE_MAXI - EMPRISE, 202);
});

test("le maintien dure deux secondes, et l'anneau fait le tour", () => {
  assert.equal(MAINTIEN_MS, 2000);
  // 2 x PI x 6, le rayon du cercle : le perimetre doit correspondre, sinon
  // l'anneau se remplit trop tot ou jamais completement.
  assert.ok(Math.abs(ANNEAU - 2 * Math.PI * 6) < 0.05);
});
