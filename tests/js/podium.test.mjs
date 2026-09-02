/**
 * Le podium de la page de résultats (specs 020, 027).
 *
 * Ces deux fonctions décident seules de ce que le vidéoprojecteur montre à la
 * remise des prix, et RIEN ne les exécutait jusqu'ici. Les deux défauts
 * couverts ci-dessous étaient invisibles à la lecture.
 *
 *   node --test "tests/js/*.test.mjs"
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { selectionDuPodium, marchesDuPodium, MAXI_SUR_LE_PODIUM }
  from "../../climbcontest/static/resultats/podium.js";

/** Un classement : `[rang, score]` par grimpeur. */
const classement = (...paires) =>
  paires.map(([rang, score], i) => ({ rang, score, nom: "G" + i }));

const formes = (marches) =>
  marches.map((m) => (m.vide ? "vide" : m.lignes.length));

test("un classement ordinaire donne trois marches pleines", () => {
  const { podium, tete } = selectionDuPodium(classement([1, 90], [2, 80], [3, 70]), true);
  assert.equal(podium, true);
  assert.deepEqual(formes(marchesDuPodium(tete, podium)), [1, 1, 1]);
});

test("une categorie a un seul grimpeur garde ses trois marches", () => {
  const { podium, tete } = selectionDuPodium(classement([1, 90]), true);
  assert.deepEqual(formes(marchesDuPodium(tete, podium)), [1, "vide", "vide"]);
});

test("une categorie a deux grimpeurs aussi", () => {
  const { podium, tete } = selectionDuPodium(classement([1, 90], [2, 80]), true);
  assert.deepEqual(formes(marchesDuPodium(tete, podium)), [1, 1, "vide"]);
});

test("personne n'a marque : trois marches vides, aucun nom", () => {
  const { podium, tete } = selectionDuPodium(classement([1, 0], [1, 0], [1, 0]), true);
  assert.equal(tete.length, 0);
  assert.deepEqual(formes(marchesDuPodium(tete, podium)), ["vide", "vide", "vide"]);
});

test("⚠️ deux premiers ex aequo : il n'y a PAS de deuxieme marche en attente", () => {
  // Le classement saute le rang 2 -- personne ne sera jamais deuxieme. Une
  // marche en pointille aurait annonce « pas encore decide » au public.
  const { podium, tete } = selectionDuPodium(classement([1, 90], [1, 90], [3, 70]), true);
  const marches = marchesDuPodium(tete, podium);
  assert.deepEqual(marches.map((m) => m.rang), [1, 3]);
  assert.ok(!marches.some((m) => m.vide), "aucune marche ne doit etre en attente");
});

test("⚠️ trois premiers ex aequo : une seule marche, aucune fantome", () => {
  const { podium, tete } = selectionDuPodium(classement([1, 90], [1, 90], [1, 90]), true);
  const marches = marchesDuPodium(tete, podium);
  assert.deepEqual(marches.map((m) => m.rang), [1]);
  assert.ok(!marches.some((m) => m.vide));
});

test("deux deuxiemes ex aequo laissent le rang 1 libre, pas le rang 3", () => {
  const { podium, tete } = selectionDuPodium(classement([2, 80], [2, 80]), true);
  const marches = marchesDuPodium(tete, podium);
  assert.deepEqual(marches.map((m) => m.rang), [1, 2]);
  assert.equal(marches[0].vide, true);
});

test("⚠️ au-dela de six ex aequo le podium est MASQUE, pas vide", () => {
  // Le vider donnait trois marches en pointille : le rendu exact d'une
  // categorie ou personne n'a marque. Deux situations opposees, un seul dessin.
  const sept = classement(...Array.from({ length: 7 }, () => [1, 90]));
  const { podium, tete } = selectionDuPodium(sept, true);
  assert.equal(podium, false, "le podium doit disparaitre au profit du tableau");
  assert.equal(tete.length, 0);
});

test("six ex aequo passent encore", () => {
  const six = classement(...Array.from({ length: MAXI_SUR_LE_PODIUM }, () => [1, 90]));
  const { podium, tete } = selectionDuPodium(six, true);
  assert.equal(podium, true);
  assert.deepEqual(formes(marchesDuPodium(tete, podium)), [6]);
});

test("un grimpeur a zero point ne monte sur aucune marche", () => {
  const { tete } = selectionDuPodium(classement([1, 90], [2, 0], [3, 0]), true);
  assert.deepEqual(tete.map((l) => l.score), [90]);
});

test("sans podium demande, rien n'est construit", () => {
  const { podium, tete } = selectionDuPodium(classement([1, 90], [2, 80]), false);
  assert.equal(podium, false);
  assert.deepEqual(marchesDuPodium(tete, podium), []);
});

test("les rangs au-dela de trois ne montent pas", () => {
  const { tete } = selectionDuPodium(classement([1, 90], [4, 60], [5, 50]), true);
  assert.deepEqual(tete.map((l) => l.rang), [1]);
});
