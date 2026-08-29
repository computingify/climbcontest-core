/**
 * Le rythme d'envoi et le verrou entre onglets (spec 007, IT2).
 *
 * Les constantes sont reprises A L'IDENTIQUE de l'Android, deliberement : deux
 * clients qui envoient au meme rythme font une charge previsible ; deux clients
 * qui divergent font une charge qu'on ne sait plus mesurer.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DELAI_MS, LOT_MAX, LOT_PLEIN, RETRAIT_MAX_MS,
  attenteApresEchec, doitEnvoyer, tailleLot,
} from "../../climbcontest/static/juge/politique.js";
import {
  DUREE_MS, bailNeuf, peutPrendre,
} from "../../climbcontest/static/juge/verrou.js";
import {
  Catalogue, PERIODE_MS, doitRafraichir,
} from "../../climbcontest/static/juge/catalogue.js";

// --- Le rythme --------------------------------------------------------------

test("les constantes sont celles de l'Android", () => {
  assert.equal(LOT_PLEIN, 5);
  assert.equal(DELAI_MS, 10_000);
  assert.equal(LOT_MAX, 50);
  assert.equal(RETRAIT_MAX_MS, 60_000);
});

test("rien en attente, rien a envoyer", () => {
  assert.equal(doitEnvoyer({ enAttente: 0, depuisDernierEnvoiMs: 99_999, echecs: 0 }), false);
});

test("le lot plein part sans attendre", () => {
  assert.equal(doitEnvoyer({ enAttente: 5, depuisDernierEnvoiMs: 0, echecs: 0 }), true);
});

test("un lot incomplet attend le delai", () => {
  assert.equal(doitEnvoyer({ enAttente: 1, depuisDernierEnvoiMs: 2_000, echecs: 0 }), false);
  assert.equal(doitEnvoyer({ enAttente: 1, depuisDernierEnvoiMs: 10_000, echecs: 0 }), true);
});

test("le retrait double, puis plafonne", () => {
  assert.equal(attenteApresEchec(0), 0);
  assert.equal(attenteApresEchec(1), 2_000);
  assert.equal(attenteApresEchec(2), 4_000);
  assert.equal(attenteApresEchec(3), 8_000);
  assert.equal(attenteApresEchec(20), RETRAIT_MAX_MS);
});

test("le retrait est respecte meme avec un lot plein", () => {
  assert.equal(doitEnvoyer({ enAttente: 50, depuisDernierEnvoiMs: 1_000, echecs: 1 }), false);
});

/**
 * « Tout envoyer maintenant » ignore le lot et le delai, mais PAS le retrait :
 * sinon appuyer en boucle sur un serveur eteint noierait le telephone.
 */
test("forcer ignore le delai mais pas le retrait", () => {
  assert.equal(doitEnvoyer({ enAttente: 1, depuisDernierEnvoiMs: 0, echecs: 0,
                             forcer: true }), true);
  assert.equal(doitEnvoyer({ enAttente: 1, depuisDernierEnvoiMs: 0, echecs: 3,
                             forcer: true }), false);
});

test("le lot ne depasse jamais ce que le serveur accepte", () => {
  assert.equal(tailleLot(3), 3);
  assert.equal(tailleLot(500), LOT_MAX);
});

// --- Le verrou entre onglets ------------------------------------------------

test("un bail libre se prend", () => {
  assert.equal(peutPrendre(null, "moi", 1000), true);
});

test("son propre bail se renouvelle", () => {
  assert.equal(peutPrendre({ proprietaire: "moi", jusqua: 5000 }, "moi", 1000), true);
});

test("le bail frais d'un autre ne se prend PAS", () => {
  // C'est tout l'objet : deux onglets ne doivent pas vider la file en double.
  assert.equal(peutPrendre({ proprietaire: "autre", jusqua: 5000 }, "moi", 1000), false);
});

/**
 * Un onglet ferme, un telephone en veille, un navigateur tue par iOS : le
 * detenteur meurt sans rendre son bail. Un verrou eternel bloquerait les envois
 * jusqu'au prochain redemarrage.
 */
test("le bail perime d'un autre se reprend", () => {
  assert.equal(peutPrendre({ proprietaire: "autre", jusqua: 1000 }, "moi", 1001), true);
});

test("un bail sans date se reprend", () => {
  assert.equal(peutPrendre({ proprietaire: "autre" }, "moi", 1000), true);
});

test("un bail neuf dure trente secondes", () => {
  assert.deepEqual(bailNeuf("moi", 1000), { proprietaire: "moi", jusqua: 1000 + DUREE_MS });
});

// --- Le catalogue -----------------------------------------------------------

const UN_CATALOGUE = new Catalogue({
  version: 3,
  participants: { "42": "Dupont Lea" },
  blocs: { ZJ6: "ZJ6" },
});

test("un grimpeur connu rend son nom", () => {
  assert.equal(UN_CATALOGUE.grimpeur("42"), "Dupont Lea");
});

test("les espaces autour d'un dossard sont ignores", () => {
  assert.equal(UN_CATALOGUE.grimpeur("  42 "), "Dupont Lea");
});

test("un tag de bloc est compare en majuscules", () => {
  // Un QR imprime peut porter « zj6 » quand la base dit « ZJ6 ».
  assert.equal(UN_CATALOGUE.bloc("zj6"), "ZJ6");
});

test("un inconnu rend null, pas une chaine vide", () => {
  assert.equal(UN_CATALOGUE.grimpeur("999"), null);
  assert.equal(UN_CATALOGUE.bloc("XX1"), null);
});

test("un catalogue abime donne un catalogue VIDE, sans lever", () => {
  for (const abime of [null, "pas un objet", 42, { version: "x" }]) {
    assert.equal(Catalogue.depuisJson(abime).estVide, true);
  }
});

test("un catalogue fait l'aller-retour par le stockage", () => {
  const relu = Catalogue.depuisJson(UN_CATALOGUE.versJson());
  assert.equal(relu.version, 3);
  assert.equal(relu.grimpeur("42"), "Dupont Lea");
});

test("un catalogue vide se rafraichit toujours", () => {
  assert.equal(doitRafraichir({ estVide: true, maintenantMs: 0, dernierMs: 0 }), true);
});

/**
 * La raison qui compte le jour J : « ce participant a ete inscrit il y a dix
 * minutes ». Le juge n'a rien a faire pour que ca se repare.
 */
test("un QR inconnu declenche un rafraichissement", () => {
  assert.equal(doitRafraichir({ estVide: false, qrInconnu: true,
                                maintenantMs: 0, dernierMs: 0 }), true);
});

test("une version serveur differente declenche un rafraichissement", () => {
  assert.equal(doitRafraichir({ estVide: false, versionServeur: 4, versionLocale: 3,
                                maintenantMs: 0, dernierMs: 0 }), true);
});

test("la meme version ne declenche rien", () => {
  assert.equal(doitRafraichir({ estVide: false, versionServeur: 3, versionLocale: 3,
                                maintenantMs: 1000, dernierMs: 1000 }), false);
});

test("le filet des cinq minutes", () => {
  assert.equal(doitRafraichir({ estVide: false, maintenantMs: PERIODE_MS - 1,
                                dernierMs: 0 }), false);
  assert.equal(doitRafraichir({ estVide: false, maintenantMs: PERIODE_MS,
                                dernierMs: 0 }), true);
});
