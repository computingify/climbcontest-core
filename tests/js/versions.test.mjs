/**
 * Le verdict « ce que j'ai vaut-il ce que le serveur a ? » — spec 030.
 *
 * Ce que ces tests protègent, c'est le TROISIÈME état. `INCONNU` n'est pas un
 * `A_JOUR` prudent : un téléphone qui n'a jamais joint le serveur ne doit
 * afficher aucun verdict. Dire « à jour » sans le savoir est exactement le
 * mensonge que cette spec existe pour supprimer — et c'est l'état d'un
 * téléphone démarré en mode avion, donc pas un cas d'école.
 *
 *   node --test "tests/js/*.test.mjs"
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  A_JOUR, EN_RETARD, INCONNU, ilYA, resumeDuCatalogue, verdict,
} from "../../climbcontest/static/juge/versions.js";

test("les deux numéros collent : à jour", () => {
  assert.equal(verdict(42, 42), A_JOUR);
  assert.equal(verdict("v0.16.0", "v0.16.0"), A_JOUR);
});

test("les deux numéros diffèrent : en retard", () => {
  assert.equal(verdict(39, 42), EN_RETARD);
  assert.equal(verdict("v0.15.0", "v0.16.0"), EN_RETARD);
});

test("serveur jamais joint : AUCUN verdict, surtout pas « à jour »", () => {
  assert.equal(verdict(42, null), INCONNU);
  assert.equal(verdict("v0.16.0", undefined), INCONNU);
  assert.equal(verdict("v0.16.0", ""), INCONNU);
});

test("rien en local : aucun verdict non plus", () => {
  // Une application fraîchement installée, avant le premier catalogue.
  assert.equal(verdict(null, 42), INCONNU);
});

test("un numéro PLUS GRAND que celui du serveur n'est pas « à jour »", () => {
  // Il ne vient pas du futur : il vient d'ailleurs — d'une autre compétition,
  // ou d'une base restaurée. Le serveur applique la même règle et lui refuse
  // délibérément un 304. Comparer par ordre inverserait ce verdict.
  assert.equal(verdict(99, 42), EN_RETARD);
});

test("l'âge se dit en clair", () => {
  const t = 1_000_000_000_000;
  assert.equal(ilYA(t, t + 12_000), "à l'instant");
  assert.equal(ilYA(t, t + 3 * 60_000), "il y a 3 min");
  assert.equal(ilYA(t, t + 72 * 60_000), "il y a 1 h 12");
  assert.equal(ilYA(0, t), null, "jamais reçu : rien à dire");
});

test("« reçu » et « vérifié » ne se confondent pas", () => {
  const maintenant = 1_000_000_000_000;
  const lignes = resumeDuCatalogue({
    grimpeurs: 98, blocs: 67,
    recuMs: maintenant - 72 * 60_000,     // les données datent d'une heure
    vuMs: maintenant - 2 * 60_000,        // mais on a vérifié il y a 2 min
    maintenantMs: maintenant,
  });
  assert.equal(lignes[0], "98 grimpeurs · 67 blocs");
  assert.equal(lignes[1], "Reçu il y a 1 h 12 · vérifié il y a 2 min",
               "un catalogue vieux mais vérifié est SAIN : c'est le cas normal");
});

test("reçu et vérifié au même moment : une seule mention", () => {
  const maintenant = 1_000_000_000_000;
  const lignes = resumeDuCatalogue({
    grimpeurs: 1, blocs: 1, recuMs: maintenant - 120_000,
    vuMs: maintenant - 119_000, maintenantMs: maintenant,
  });
  assert.equal(lignes[1], "Reçu il y a 2 min");
});

test("catalogue vide : aucune ligne inventée", () => {
  assert.deepEqual(resumeDuCatalogue({}), []);
});
