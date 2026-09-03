// Le garde-fou « ce bloc n'est pas dans son circuit » — spec 019.
//
// Il répond **hors ligne**, sur le téléphone, avant l'envoi. Ce que ces tests
// protègent, c'est surtout le troisième cas : `null` n'est pas un `false`
// déguisé. Un avertissement qu'on ne sait pas justifier apprend à ignorer les
// avertissements, et le seul moment où celui-ci compte, c'est le jour J.
import { test } from "node:test";
import assert from "node:assert/strict";

import { Catalogue, FORMAT } from "../../climbcontest/static/juge/catalogue.js";

/** Ce que le serveur envoie vraiment — `/api/v2/catalog`, inchangé. */
const REPONSE = {
  version: 12,
  participants: [
    { id: 1, dossard: 1, nom: "Dupont Lea", club: "Les Lezards", categorie: "U11 F" },
    { id: 2, dossard: 2, nom: "Martin Tom", club: "La Grimpe", categorie: "U17 H" },
    { id: 3, dossard: 3, nom: "Sans Categorie", club: null, categorie: null },
  ],
  blocs: [
    { id: 1, tag: "ZJ6", numero: 1, couleur: "Jaune", circuits: ["U11", "U13"] },
    { id: 2, tag: "DV21", numero: 2, couleur: "Noir", circuits: ["U17"] },
    { id: 3, tag: "MX9", numero: 3, couleur: "Vert", circuits: [] },
  ],
};

const CATALOGUE = Catalogue.depuisReponseServeur(REPONSE);

test("le circuit se dérive de la catégorie, comme côté serveur", () => {
  assert.equal(CATALOGUE.circuitDuGrimpeur(1), "U11");   // « U11 F » → « U11 »
  assert.equal(CATALOGUE.circuitDuGrimpeur(2), "U17");
});

test("la catégorie complète est entreposée depuis la forme 4", () => {
  // ⚠️ Ce test disait l'INVERSE jusqu'à la spec 033 (R10) : seul le circuit
  // était gardé, par minimisation — des données de mineurs vivent sur
  // vingt-cinq téléphones de bénévoles, et le genre n'apprenait rien au test
  // d'appartenance.
  //
  // Il apprend maintenant quelque chose : Adrien a demandé que la catégorie
  // s'affiche sur la carte du grimpeur, pour que le juge vérifie d'un coup
  // d'œil qu'il scanne le bon. Elle voyageait déjà sur le réseau ; elle est
  // désormais conservée. Le circuit, lui, n'est PLUS rangé : il se déduit.
  const range = JSON.stringify(CATALOGUE.versJson());
  assert.equal(range.includes("U11 F"), true);
  assert.equal(range.includes("U17 H"), true);
  // Une seule clé pour les deux : la quantité stockée ne croît pas.
  assert.equal(JSON.parse(range).participants["1"].c, "U11 F");
});

test("la catégorie est lisible, et absente quand le classeur ne la donne pas", () => {
  assert.equal(CATALOGUE.categorie(1), "U11 F");
  assert.equal(CATALOGUE.categorie(3), null);   // ligne sans catégorie (R5)
  assert.equal(CATALOGUE.categorie(99), null);  // dossard inconnu
});

test("la catégorie survit à l'aller-retour par le stockage", () => {
  const relu = Catalogue.depuisJson(CATALOGUE.versJson());
  assert.equal(relu.categorie(1), "U11 F");
  assert.equal(relu.circuitDuGrimpeur(1), "U11");
});

test("un bloc du circuit du grimpeur : rien à signaler", () => {
  assert.equal(CATALOGUE.estDansLeCircuit(1, "ZJ6"), true);
  assert.equal(CATALOGUE.estDansLeCircuit(2, "DV21"), true);
});

test("un bloc hors du circuit : c'est le cas qu'on veut voir", () => {
  // Le scénario d'Adrien, le 01/09 : un grimpeur, puis un bloc qu'il n'a pas
  // à faire. La réussite partait, et ne comptait pour rien.
  assert.equal(CATALOGUE.estDansLeCircuit(1, "DV21"), false);
  assert.equal(CATALOGUE.estDansLeCircuit(2, "ZJ6"), false);
});

test("un bloc partagé par deux circuits appartient aux deux", () => {
  // Le cas NORMAL : 36 blocs sur 67 en novembre 2025. Le test est une
  // appartenance, jamais une égalité.
  const c = Catalogue.depuisReponseServeur({
    version: 1,
    participants: [{ dossard: 5, nom: "X", categorie: "U13 H" }],
    blocs: [{ tag: "ZJ6", circuits: ["U11", "U13"] }],
  });
  assert.equal(c.estDansLeCircuit(5, "ZJ6"), true);
});

test("la casse d'un QR imprimé ne change rien", () => {
  assert.equal(CATALOGUE.estDansLeCircuit(1, "zj6"), true);
  assert.equal(CATALOGUE.estDansLeCircuit(1, "  Dv21 "), false);
});

// --- Les quatre façons de ne pas savoir -------------------------------------

test("un dossard inconnu : null, pas false", () => {
  assert.equal(CATALOGUE.estDansLeCircuit(999, "ZJ6"), null);
});

test("un tag inconnu : null", () => {
  assert.equal(CATALOGUE.estDansLeCircuit(1, "XX1"), null);
});

test("un participant sans catégorie : null", () => {
  // Le classeur en produit (risque R5) et l'import les garde exprès. Il
  // scanne normalement, sans jamais déclencher d'avertissement.
  assert.equal(CATALOGUE.estDansLeCircuit(3, "ZJ6"), null);
  assert.equal(CATALOGUE.grimpeur(3), "Sans Categorie");
});

test("un bloc rattaché à aucun circuit : null", () => {
  // L'anomalie du 01/09 — 37 blocs orphelins. On ne sait pas qui doit le
  // faire : on se tait, on ne crie pas au loup sur chaque scan.
  assert.equal(CATALOGUE.estDansLeCircuit(1, "MX9"), null);
  assert.equal(CATALOGUE.bloc("MX9"), "MX9");   // il reste scannable
});

test("les entrées abîmées ne lèvent jamais", () => {
  for (const [d, t] of [[null, null], [undefined, "ZJ6"], [1, undefined],
                        [{}, []], [1, 42]]) {
    assert.equal(CATALOGUE.estDansLeCircuit(d, t), null);
  }
});

// --- Le rangement -----------------------------------------------------------

test("le circuit survit à l'aller-retour par le stockage", () => {
  const relu = Catalogue.depuisJson(CATALOGUE.versJson());
  assert.equal(relu.estDansLeCircuit(1, "ZJ6"), true);
  assert.equal(relu.estDansLeCircuit(1, "DV21"), false);
  assert.equal(relu.couleurDuBloc("ZJ6"), "Jaune");
  assert.equal(relu.grimpeur(1), "Dupont Lea");
});

test("le format est bien la quatrième forme", () => {
  assert.equal(FORMAT, 4);
  assert.equal(CATALOGUE.versJson().format, 4);
});

test("un catalogue de la forme 3 force un rechargement", () => {
  // ⚠️ C'est TOUT l'intérêt du marqueur. Un téléphone peut recevoir le
  // nouveau code en gardant un catalogue rangé par l'ancien — et le serveur
  // répondant 304 tant que la version ne bouge pas, il ne serait jamais
  // remplacé. Ici le `c` d'un participant voudrait dire « circuit » alors que
  // le code y lit une catégorie : le juge verrait « U11 » là où on annonce
  // une catégorie, sans que rien ne le signale.
  const vieux = Catalogue.depuisJson({
    format: 3, version: 12,
    participants: { 1: { n: "Dupont Lea", c: "U11" } },
    blocs: { ZJ6: { t: "ZJ6", k: "Jaune", c: ["U11"] } },
  });
  assert.equal(vieux.estVide, true);
});

test("les circuits du bloc sont lisibles pour l'affichage", () => {
  assert.deepEqual(CATALOGUE.circuitsDuBloc("ZJ6"), ["U11", "U13"]);
  assert.deepEqual(CATALOGUE.circuitsDuBloc("MX9"), []);
  assert.equal(CATALOGUE.circuitsDuBloc("XX1"), null);   // inconnu ≠ orphelin
});
