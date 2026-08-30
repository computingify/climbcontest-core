// Les couleurs de circuit côté PWA — le miroir exact de CouleursTest.kt.
// La couleur porte de l'information : elle se teste comme du métier.
import { test } from "node:test";
import assert from "node:assert/strict";

import { couleurDeCircuit, encreSur } from "../../climbcontest/static/juge/couleurs.js";
import { Catalogue } from "../../climbcontest/static/juge/catalogue.js";

test("les six circuits du club sont reconnus", () => {
  for (const nom of ["Jaune", "Vert", "Bleu", "Mauve", "Rouge", "Noir"]) {
    assert.notEqual(couleurDeCircuit(nom), null, nom);
  }
});

test("la casse et les espaces du classeur ne changent rien", () => {
  assert.equal(couleurDeCircuit("  JAUNE "), couleurDeCircuit("jaune"));
  assert.equal(couleurDeCircuit("violet"), couleurDeCircuit("Mauve"));
});

test("un circuit inconnu rend null, jamais une erreur", () => {
  assert.equal(couleurDeCircuit("turquoise"), null);
  assert.equal(couleurDeCircuit(""), null);
  assert.equal(couleurDeCircuit(null), null);
  assert.equal(couleurDeCircuit(42), null);
});

test("le circuit noir n'est PAS rendu en noir", () => {
  // Un aplat noir sur un fond presque noir ne se voit pas : le juge ne
  // saurait pas s'il a scanné. « Noir » est rendu en craie.
  const craie = couleurDeCircuit("Noir");
  assert.equal(encreSur(craie), "#12140F");   // encre SOMBRE : le fond est clair
});

test("l'encre est sombre sur jaune, claire sur mauve", () => {
  assert.equal(encreSur(couleurDeCircuit("Jaune")), "#12140F");
  assert.equal(encreSur(couleurDeCircuit("Mauve")), "#F7F9FC");
});

test("le catalogue capte la couleur envoyée par le serveur", () => {
  const c = Catalogue.depuisReponseServeur({
    version: 3,
    participants: [{ dossard: 1, nom: "Dupont Lea" }],
    blocs: [{ tag: "ZJ1", couleur: "Jaune" }, { tag: "ZV2" }],
  });
  assert.equal(c.couleurDuBloc("zj1"), "Jaune");   // insensible a la casse
  assert.equal(c.couleurDuBloc("ZV2"), null);      // pas de couleur : pas d'erreur
});

test("la couleur survit à l'aller-retour versJson/depuisJson", () => {
  const avant = Catalogue.depuisReponseServeur({
    version: 3, participants: [], blocs: [{ tag: "ZJ1", couleur: "Jaune" }],
  });
  const apres = Catalogue.depuisJson(avant.versJson());
  assert.equal(apres.couleurDuBloc("ZJ1"), "Jaune");
});

test("un catalogue rangé AVANT les couleurs reste utilisable", () => {
  // Le format d'hier, tel qu'il dort déjà sur les téléphones : pas de champ
  // `couleurs`. Il ne doit être ni jeté ni cassé.
  const c = Catalogue.depuisJson({
    format: 2, version: 2,
    participants: { 1: "Dupont Lea" }, blocs: { ZJ1: "ZJ1" },
  });
  assert.equal(c.bloc("ZJ1"), "ZJ1");
  assert.equal(c.couleurDuBloc("ZJ1"), null);
});
