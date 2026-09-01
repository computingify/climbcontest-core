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
  Catalogue, FORMAT, PERIODE_MS, doitRafraichir,
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
  participants: { "42": { n: "Dupont Lea", c: "U13" } },
  blocs: { ZJ6: { t: "ZJ6", c: ["U13"] } },
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

// --- La forme REELLE de la reponse du serveur -------------------------------
//
// ⚠️ Ces tests manquaient, et leur absence a coute cher : j'avais ecrit le
// module en SUPPOSANT que le serveur envoyait des dictionnaires. Il envoie des
// TABLEAUX d'objets. Le catalogue local ne correspondait donc jamais, et chaque
// scan repassait par le reseau -- exactement ce que l'iteration pretendait
// supprimer. Les tests d'alors verifiaient ma classe contre ma propre
// supposition ; seul un appel au vrai serveur l'a montre.

const REPONSE_SERVEUR = {
  version: 7,
  competition: { id: 1, nom: "Test" },
  circuits: ["U11", "U13"],
  participants: [
    { id: 1, dossard: 1, nom: "Lecomte Elsa", club: "La Grimpe", categorie: "U13 H" },
    { id: 2, dossard: 42, nom: "Dupont Lea", club: "Roc", categorie: "U15 F" },
  ],
  blocs: [
    { id: 1, tag: "ZJ1", couleur: "Jaune", numero: 1, circuits: ["U13"] },
    { id: 2, tag: "ZV3", couleur: "Vert", numero: 3, circuits: ["U15"] },
  ],
};

test("la reponse du serveur donne dossard -> nom", () => {
  const c = Catalogue.depuisReponseServeur(REPONSE_SERVEUR);
  assert.equal(c.grimpeur("42"), "Dupont Lea");
  assert.equal(c.grimpeur(42), "Dupont Lea", "un dossard numerique aussi");
});

test("la reponse du serveur donne tag -> tag", () => {
  const c = Catalogue.depuisReponseServeur(REPONSE_SERVEUR);
  assert.equal(c.bloc("ZV3"), "ZV3");
  assert.equal(c.bloc("zv3"), "ZV3", "un QR peut porter des minuscules");
});

test("la version du serveur est reprise", () => {
  assert.equal(Catalogue.depuisReponseServeur(REPONSE_SERVEUR).version, 7);
});

test("un participant SANS dossard n'entre pas dans la table", () => {
  // Il existe : il est inscrit, il n'a pas encore son papier. Mais il n'a rien
  // a faire dans une table indexee par dossard.
  const c = Catalogue.depuisReponseServeur({
    version: 1, participants: [{ id: 9, dossard: null, nom: "Sans Dossard" }], blocs: [],
  });
  assert.equal(c.estVide, true);
});

test("une reponse abimee donne un catalogue VIDE, sans lever", () => {
  for (const abime of [null, "texte", 42, {}, { participants: "pas un tableau" },
                       { participants: [null, 42, {}] }]) {
    assert.equal(Catalogue.depuisReponseServeur(abime).estVide, true);
  }
});

test("le catalogue du serveur se range puis se relit a l'identique", () => {
  // Le format RANGE n'est pas celui du serveur : deux dictionnaires, pas deux
  // tableaux. C'est cet aller-retour-la qui doit tenir.
  const duServeur = Catalogue.depuisReponseServeur(REPONSE_SERVEUR);
  const relu = Catalogue.depuisJson(duServeur.versJson());
  assert.equal(relu.version, 7);
  assert.equal(relu.grimpeur("42"), "Dupont Lea");
  assert.equal(relu.bloc("zj1"), "ZJ1");
});

test("un catalogue range par une version anterieure est ignore", () => {
  // ⚠️ Une PWA se met a jour toute seule : un telephone peut recevoir un
  // nouveau code en gardant un catalogue range par l'ancien. Comme le serveur
  // repond 304 tant que la version ne bouge pas, il ne serait JAMAIS remplace
  // -- et le juge scannerait dans le vide jusqu'a la competition suivante.
  const ancien = { version: 3, participants: { "42": "Dupont" }, blocs: {} };
  assert.equal(Catalogue.depuisJson(ancien).estVide, true,
               "sans marqueur de format, on repart de zero");
});

test("le marqueur de format voyage avec le catalogue range", () => {
  const range = Catalogue.depuisReponseServeur(REPONSE_SERVEUR).versJson();
  assert.equal(range.format, FORMAT);
});

test("un tableau relu comme un dictionnaire ne fait pas de degats", () => {
  // Si un jour quelqu'un range la reponse brute par erreur, on veut un
  // catalogue vide -- pas des entrees « 0 » -> [object Object].
  assert.equal(Catalogue.depuisJson(REPONSE_SERVEUR).estVide, true);
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
