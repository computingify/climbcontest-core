/**
 * Le jeton de la PWA juge (spec 007), teste sur Node.
 *
 * La logique qui compte est extraite dans des modules sans `document` ni
 * `fetch`, exactement comme `DecisionEnvoi` et `FileDeReussites` cote Android :
 * ce qui decide doit se tester sans navigateur, sinon ca ne se teste pas.
 *
 *   node --test tests/js/
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { choisirJeton, jetonDuFragment } from
  "../../climbcontest/static/juge/jeton.js";

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

test("le lien fournit le jeton la premiere fois", () => {
  assert.deepEqual(choisirJeton("#j=abc", null),
                   { jeton: "abc", aEcrire: true });
});

/**
 * La regle qui compte. Ouvrir la PWA depuis l'ecran d'accueil se fait SANS
 * fragment : si l'absence effacait le jeton range, le juge serait bloque au
 * premier lancement de la journee, sans comprendre pourquoi.
 */
test("ouvrir sans fragment garde le jeton deja range", () => {
  assert.deepEqual(choisirJeton("", "deja-la"),
                   { jeton: "deja-la", aEcrire: false });
});

test("un fragment vide n'efface pas non plus", () => {
  assert.deepEqual(choisirJeton("#j=", "deja-la"),
                   { jeton: "deja-la", aEcrire: false });
});

test("un nouveau lien remplace le jeton, pour remplacer une cle revoquee", () => {
  assert.deepEqual(choisirJeton("#j=neuf", "vieux"),
                   { jeton: "neuf", aEcrire: true });
});

test("le meme lien reouvert n'ecrit pas pour rien", () => {
  assert.deepEqual(choisirJeton("#j=pareil", "pareil"),
                   { jeton: "pareil", aEcrire: false });
});

test("sans rien, on n'a pas de jeton", () => {
  assert.deepEqual(choisirJeton("", null), { jeton: null, aEcrire: false });
});
