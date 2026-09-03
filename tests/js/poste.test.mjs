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

import { MOT_ZONE, PREFIXE_POSTE, expliquerLeQrRefuse, libelleDuPoste,
         nomDePoste, texteDuQrDePoste } from
  "../../climbcontest/static/juge/poste.js";
import { LONGUEUR_NOM } from "../../climbcontest/static/juge/identite.js";

// --- Ce qui est accepte -------------------------------------------------------

test("le QR ne porte que la lettre, l'application compose « Zone A »", () => {
  // ⚠️ La retouche du 03/09. Adrien : « dans le nom qu'on envoie a la console,
  // je veux que ce soit "zone" et la lettre de la zone ». Le QR, lui, ne bouge
  // pas : il reste minimal, donc plus lisible, et le libelle peut changer sans
  // reimprimer dix-sept affiches.
  assert.equal(nomDePoste("CCPOSTE:A"), "Zone A");
  assert.equal(nomDePoste("CCPOSTE:C"), "Zone C");
});

test("le prefixe se lit sans tenir compte de la casse", () => {
  // Un QR refait a la main ne doit pas devenir un QR mort.
  assert.equal(nomDePoste("ccposte:C"), "Zone C");
  assert.equal(nomDePoste("CcPoStE:C"), "Zone C");
});

test("le nom est nettoye comme la saisie au clavier", () => {
  assert.equal(nomDePoste("CCPOSTE:  Mur jaune  "), "Zone Mur jaune");
});

test("une zone qui se nomme deja « Zone … » n'est pas prefixee deux fois", () => {
  // Rien dans le plan n'interdit d'appeler un mur « Zone Nord ». « Zone Zone
  // Nord » aurait l'air casse dans la console -- et sur un carton deja
  // imprime par une version anterieure, qui portait le nom complet.
  assert.equal(nomDePoste("CCPOSTE:Zone C"), "Zone C");
  assert.equal(nomDePoste("CCPOSTE:zone nord"), "zone nord");
});

test("un nom trop long est coupe a la meme longueur que le champ", () => {
  const long = "Z".repeat(LONGUEUR_NOM + 20);
  assert.equal(nomDePoste("CCPOSTE:" + long).length, LONGUEUR_NOM);
});

test("les accents et les apostrophes passent tels quels", () => {
  assert.equal(nomDePoste("CCPOSTE:a l’ombre"), "Zone a l’ombre");
  assert.equal(nomDePoste("CCPOSTE:Dévers"), "Zone Dévers");
});

test("un QR entoure d'espaces reste lisible", () => {
  assert.equal(nomDePoste("  CCPOSTE:C  "), "Zone C");
});

test("le mot compose est celui de la constante", () => {
  // ⚠️ Il est ecrit DEUX fois : ici et dans `fiches.MOT_ZONE`, qui l'imprime
  // en petit au-dessus de la lettre sur le carton. Un test Python compare les
  // deux (`tests/test_postes.py::TestLePrefixePartage`).
  assert.equal(MOT_ZONE, "Zone");
  assert.equal(libelleDuPoste("A"), `${MOT_ZONE} A`);
});

test("une zone vide ne compose aucun libelle", () => {
  // ⚠️ Sinon « Zone » tout court remplacerait un nom deja regle.
  assert.equal(libelleDuPoste(""), null);
  assert.equal(libelleDuPoste("   "), null);
  assert.equal(libelleDuPoste(null), null);
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
  assert.equal(nomDePoste("PASCCPOSTE:C"), null);
  assert.equal(nomDePoste("Zone C CCPOSTE:x"), null);
});

// --- L'ecriture, et l'aller-retour --------------------------------------------

test("le texte a encoder porte le prefixe en majuscules", () => {
  assert.equal(texteDuQrDePoste("C"), "CCPOSTE:C");
  assert.equal(PREFIXE_POSTE, "CCPOSTE:");
});

test("ce qu'on ecrit est ce qu'on relit, compose", () => {
  for (const zone of ["C", "AB", "Dévers", "Z-12", "Toit n°2"]) {
    assert.equal(nomDePoste(texteDuQrDePoste(zone)), `${MOT_ZONE} ${zone}`,
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
