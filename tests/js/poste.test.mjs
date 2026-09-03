/**
 * Le QR de poste (spec 034), teste sur Node.
 *
 * Ce fichier tient la seule chose qui peut casser en silence : le decodage.
 * Un renommage SILENCIEUX est le defaut a eviter -- le juge ne verrait rien,
 * et la console afficherait « ZJ6 » en face de tous ses envois de la journee.
 * Chaque refus est donc teste, et chaque refus a SON message.
 *
 *   node --test "tests/js/*.test.mjs"
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { PREFIXE_POSTE, expliquerLeQrRefuse, nomDePoste, texteDuQrDePoste } from
  "../../climbcontest/static/juge/poste.js";
import { LONGUEUR_NOM } from "../../climbcontest/static/juge/identite.js";

// --- Ce qui est accepte -------------------------------------------------------

test("un QR de poste rend le nom de la zone", () => {
  assert.equal(nomDePoste("CCPOSTE:Zone C"), "Zone C");
});

test("le prefixe se lit sans tenir compte de la casse", () => {
  // Un QR refait a la main ne doit pas devenir un QR mort.
  assert.equal(nomDePoste("ccposte:Zone C"), "Zone C");
  assert.equal(nomDePoste("CcPoStE:Zone C"), "Zone C");
});

test("le nom est nettoye comme la saisie au clavier", () => {
  assert.equal(nomDePoste("CCPOSTE:  Mur jaune  "), "Mur jaune");
});

test("un nom trop long est coupe a la meme longueur que le champ", () => {
  const long = "Z".repeat(LONGUEUR_NOM + 20);
  assert.equal(nomDePoste("CCPOSTE:" + long).length, LONGUEUR_NOM);
});

test("les accents et les apostrophes passent tels quels", () => {
  assert.equal(nomDePoste("CCPOSTE:Zone a l’ombre"), "Zone a l’ombre");
  assert.equal(nomDePoste("CCPOSTE:Dévers"), "Dévers");
});

test("un QR entoure d'espaces reste lisible", () => {
  assert.equal(nomDePoste("  CCPOSTE:Zone C  "), "Zone C");
});

// --- Ce qui est refuse --------------------------------------------------------

test("un prefixe sans nom ne renomme rien", () => {
  // ⚠️ Le cas qui compte : un renommage a vide EFFACE un nom deja regle.
  assert.equal(nomDePoste("CCPOSTE:"), null);
  assert.equal(nomDePoste("CCPOSTE:   "), null);
});

test("un QR de bloc n'est pas un QR de poste", () => {
  assert.equal(nomDePoste("ZJ6"), null);
  assert.equal(nomDePoste("DV21"), null);
});

test("un dossard n'est pas un QR de poste", () => {
  assert.equal(nomDePoste("42"), null);
  assert.equal(nomDePoste("1"), null);
});

test("le lien de l'organisateur n'est pas un QR de poste", () => {
  assert.equal(nomDePoste("https://climbcontest.example/juge?j=abc123"), null);
  assert.equal(nomDePoste("https://climbcontest.example/juge#j=abc123"), null);
});

test("rien du tout n'est pas un QR de poste", () => {
  assert.equal(nomDePoste(""), null);
  assert.equal(nomDePoste(null), null);
  assert.equal(nomDePoste(undefined), null);
});

test("le prefixe doit etre en TETE, pas quelque part dedans", () => {
  assert.equal(nomDePoste("PASCCPOSTE:Zone C"), null);
  assert.equal(nomDePoste("Zone C CCPOSTE:x"), null);
});

// --- L'ecriture, et l'aller-retour --------------------------------------------

test("le texte a encoder porte le prefixe en majuscules", () => {
  assert.equal(texteDuQrDePoste("C"), "CCPOSTE:C");
  assert.equal(PREFIXE_POSTE, "CCPOSTE:");
});

test("ce qu'on ecrit est ce qu'on relit", () => {
  for (const zone of ["C", "Zone C", "Mur jaune", "Dévers", "Z-12", "Toit n°2"]) {
    assert.equal(nomDePoste(texteDuQrDePoste(zone)), zone,
                 `aller-retour casse pour « ${zone} »`);
  }
});

// --- Les messages de refus ----------------------------------------------------
//
// ⚠️ Trois messages, pas un. « QR invalide » enverrait le juge chercher un
// organisateur dans les trois cas, alors qu'il tient parfois le BON QR au
// mauvais endroit.

test("un QR de bloc renvoie au carton pose sur la table", () => {
  const message = expliquerLeQrRefuse("ZJ6");
  assert.match(message, /posé sur ta table/);
  assert.doesNotMatch(message, /organisateur/);
});

test("le lien de l'organisateur est nomme pour ce qu'il est", () => {
  const message = expliquerLeQrRefuse("https://climbcontest.example/juge?j=abc");
  assert.match(message, /organisateur/);
  assert.doesNotMatch(message, /posé sur ta table/);
});

test("un QR de poste sans nom dit que c'est le CARTON qui cloche", () => {
  const message = expliquerLeQrRefuse("CCPOSTE:");
  assert.match(message, /aucun nom de zone/);
  assert.match(message, /organisateur/);
});

test("aucun message ne laisse le juge sans geste", () => {
  for (const texte of ["ZJ6", "42", "", "CCPOSTE:",
                       "https://climbcontest.example/juge?j=abc"]) {
    assert.ok(expliquerLeQrRefuse(texte).length > 30,
              `message trop court pour « ${texte} »`);
  }
});
