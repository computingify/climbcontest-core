/**
 * Le jeton de la PWA juge (specs 007 et 014), teste sur Node.
 *
 * La logique qui compte est extraite dans des modules sans `document` ni
 * `fetch`, exactement comme `DecisionEnvoi` et `FileDeReussites` cote Android :
 * ce qui decide doit se tester sans navigateur, sinon ca ne se teste pas.
 *
 *   node --test tests/js/
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { choisirJeton, jetonDeLaRequete, jetonDuFragment } from
  "../../climbcontest/static/juge/jeton.js";

// --- L'extraction ------------------------------------------------------------

test("un fragment porte le jeton", () => {
  assert.equal(jetonDuFragment("#j=abc123"), "abc123");
});

test("le fragment peut porter autre chose a cote", () => {
  assert.equal(jetonDuFragment("#j=abc123&autre=1"), "abc123");
});

test("pas de fragment, pas de jeton", () => {
  assert.equal(jetonDuFragment(""), null);
  assert.equal(jetonDuFragment(undefined), null);
  assert.equal(jetonDuFragment("#"), null);
  assert.equal(jetonDuFragment("#autre=1"), null);
});

test("un jeton entoure d'espaces est nettoye", () => {
  assert.equal(jetonDuFragment("#j=%20abc%20"), "abc");
});

test("un jeton vide vaut absence de jeton", () => {
  assert.equal(jetonDuFragment("#j="), null);
});

test("une requete porte le jeton (spec 014)", () => {
  assert.equal(jetonDeLaRequete("?j=abc123"), "abc123");
  assert.equal(jetonDeLaRequete("?autre=1&j=abc123"), "abc123");
});

test("pas de requete, pas de jeton", () => {
  assert.equal(jetonDeLaRequete(""), null);
  assert.equal(jetonDeLaRequete(undefined), null);
  assert.equal(jetonDeLaRequete("?"), null);
  assert.equal(jetonDeLaRequete("?j="), null);
  assert.equal(jetonDeLaRequete("?autre=1"), null);
});

// --- Le choix ----------------------------------------------------------------
//
// La table du plan de la spec 014. Chaque ligne porte le cas reel qui l'a fait
// ecrire ; la quatrieme est celle du defaut corrige.

test("la requete fournit le jeton : le cas de start_url", () => {
  assert.deepEqual(choisirJeton("?j=abc", "", null),
                   { jeton: "abc", aEcrire: true });
});

test("le fragment reste accepte : les liens deja distribues", () => {
  assert.deepEqual(choisirJeton("", "#j=abc", null),
                   { jeton: "abc", aEcrire: true });
});

test("la requete prime sur le fragment", () => {
  assert.deepEqual(choisirJeton("?j=requete", "#j=fragment", null),
                   { jeton: "requete", aEcrire: true });
});

/**
 * La regle qui compte, et le cas de tous les jours.
 *
 * Ouvrir la PWA depuis l'ecran d'accueil se fait sans rien dans l'adresse quand
 * l'installation date d'avant la spec 014 : si cette absence effacait le jeton
 * range, le juge serait bloque au premier lancement de la journee, sans
 * comprendre pourquoi.
 */
test("ouvrir sans rien garde le jeton deja range", () => {
  assert.deepEqual(choisirJeton("", "", "deja-la"),
                   { jeton: "deja-la", aEcrire: false });
});

test("une requete vide n'efface pas le jeton range", () => {
  assert.deepEqual(choisirJeton("?j=", "", "deja-la"),
                   { jeton: "deja-la", aEcrire: false });
});

test("un fragment vide n'efface pas non plus", () => {
  assert.deepEqual(choisirJeton("", "#j=", "deja-la"),
                   { jeton: "deja-la", aEcrire: false });
});

test("un nouveau lien remplace le jeton, pour remplacer une cle revoquee", () => {
  assert.deepEqual(choisirJeton("?j=neuf", "", "vieux"),
                   { jeton: "neuf", aEcrire: true });
});

test("le meme lien reouvert n'ecrit pas pour rien", () => {
  assert.deepEqual(choisirJeton("?j=pareil", "", "pareil"),
                   { jeton: "pareil", aEcrire: false });
});

test("sans rien, on n'a pas de jeton", () => {
  assert.deepEqual(choisirJeton("", "", null), { jeton: null, aEcrire: false });
});
