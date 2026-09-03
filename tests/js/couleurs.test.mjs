// Les couleurs de circuit côté PWA — le miroir exact de CouleursTest.kt.
// La couleur porte de l'information : elle se teste comme du métier.
import { test } from "node:test";
import assert from "node:assert/strict";

import { CIRCUITS, NOIR, couleurDeCircuit, encreSur, enSombre }
  from "../../climbcontest/static/juge/couleurs.js";
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

test("le circuit « Noir » prend l'encre du thème — spec 039", () => {
  // La craie n'était pas un choix de couleur : c'était une rustine du fond
  // sombre. Un aplat noir sur un fond presque noir ne se voit pas — mais sur
  // du papier sable, la craie ne se voit pas davantage.
  assert.equal(couleurDeCircuit("Noir", false), NOIR.clair);
  assert.equal(couleurDeCircuit("Noir", true), NOIR.sombre);
  // Et dans les deux cas, l'aplat reçoit une encre qui se lit dessus.
  assert.equal(encreSur(NOIR.clair), "#F7F9FC");  // encre CLAIRE sur l'aplat sombre
  assert.equal(encreSur(NOIR.sombre), "#12140F"); // encre SOMBRE sur la craie
});

test("hors navigateur, le thème est CLAIR — le défaut de l'application", () => {
  // ⚠️ Node n'a pas de `matchMedia`. La réponse ne doit pas être une valeur de
  // repli arbitraire : c'est le thème par défaut de la PWA, et il est clair.
  assert.equal(enSombre(), false);
  assert.equal(couleurDeCircuit("Noir"), NOIR.clair);
});

test("les cinq autres circuits ne dépendent PAS du thème", () => {
  // La parité avec l'Android tient sur ce qui porte de l'information : cinq
  // teintes identiques au point près, dans les deux thèmes. « Noir » est la
  // seule exception, et elle est écrite.
  for (const nom of ["Jaune", "Vert", "Bleu", "Mauve", "Rouge"]) {
    assert.equal(couleurDeCircuit(nom, false), couleurDeCircuit(nom, true), nom);
  }
});

test("la table des couleurs ne dit pas autre chose que le noir du thème clair", () => {
  // Deux sources pour la même valeur finiraient par diverger : `CIRCUITS.noir`
  // EST `NOIR.clair`.
  assert.equal(CIRCUITS.noir, NOIR.clair);
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

test("un catalogue rangé sans couleur reste utilisable", () => {
  // Un bloc dont le classeur ne donne pas la difficulté : il doit rester
  // scannable, l'écran garde simplement sa teinte neutre.
  const c = Catalogue.depuisJson({
    format: 4, version: 2,
    participants: { 1: { n: "Dupont Lea" } }, blocs: { ZJ1: { t: "ZJ1" } },
  });
  assert.equal(c.bloc("ZJ1"), "ZJ1");
  assert.equal(c.couleurDuBloc("ZJ1"), null);
});

test("le format 2, qui dort sur les téléphones, force un rechargement", () => {
  // La forme a changé à la spec 019 : chaque entrée est un objet, plus une
  // chaîne. Un catalogue de l'ancienne forme est ILLISIBLE — et comme le
  // serveur répond 304 tant que la version ne bouge pas, il ne serait JAMAIS
  // remplacé. Le marqueur de format existe exactement pour ça.
  const c = Catalogue.depuisJson({
    format: 2, version: 2,
    participants: { 1: "Dupont Lea" }, blocs: { ZJ1: "ZJ1" },
  });
  assert.equal(c.estVide, true);
});
