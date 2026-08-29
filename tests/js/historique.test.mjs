/**
 * Le journal des scans et l'identite du telephone (spec 007, IT3).
 *
 * La garantie protegee ici est la meme que cote Android : **la purge a trente
 * jours ne peut pas perdre une reussite non envoyee**, parce que le journal
 * n'est pas la source de verite de l'envoi.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { FileDeReussites, MagasinMemoire } from
  "../../climbcontest/static/juge/file.js";
import {
  ETATS, Historique, RETENTION_JOURS, refCourte,
} from "../../climbcontest/static/juge/historique.js";
import {
  LONGUEUR_NOM, identiteCourante, nettoyerLeNom, renommer,
} from "../../climbcontest/static/juge/identite.js";

const JOUR = 24 * 60 * 60 * 1000;
const scan = (ref, bib = "42", at = "2026-11-08T10:00:00Z") =>
  ({ ref, bib, bloc: "ZV3", at });

function unJournal() {
  return new Historique(new MagasinMemoire());
}

test("un journal neuf est vide", async () => {
  assert.deepEqual(await unJournal().tous(), []);
});

test("un scan note apparait, en attente", async () => {
  const j = unJournal();
  await j.noter(scan("r1"));
  const tous = await j.tous();
  assert.equal(tous.length, 1);
  assert.equal(tous[0].etat, ETATS.enAttente);
  assert.equal(tous[0].bib, "42");
});

test("un scan acquitte ne fait qu'une seule entree", async () => {
  const j = unJournal();
  await j.noter(scan("r1"));
  await j.changerEtat("r1", ETATS.partie);
  const tous = await j.tous();
  assert.equal(tous.length, 1);
  assert.equal(tous[0].etat, ETATS.partie);
});

test("un refus garde son motif", async () => {
  const j = unJournal();
  await j.noter(scan("r1"));
  await j.changerEtat("r1", ETATS.refusee, "dossard inconnu");
  assert.equal((await j.tous())[0].motif, "dossard inconnu");
});

test("un refus puis un renvoi reussi laisse l'etat final ET le motif", async () => {
  const j = unJournal();
  await j.noter(scan("r1"));
  await j.changerEtat("r1", ETATS.refusee, "dossard inconnu");
  await j.changerEtat("r1", ETATS.partie);
  const tous = await j.tous();
  assert.equal(tous.length, 1);
  assert.equal(tous[0].etat, ETATS.partie);
  // Le motif reste consultable : c'est l'histoire du scan, pas son etat.
  assert.equal(tous[0].motif, "dossard inconnu");
});

test("changer l'etat ne fait pas remonter le scan dans la liste", async () => {
  const j = unJournal();
  await j.noter(scan("r1", "1"));
  await j.noter(scan("r2", "2"));
  await j.changerEtat("r1", ETATS.partie);
  assert.deepEqual((await j.tous()).map((s) => s.bib), ["1", "2"]);
});

test("un changement d'etat orphelin n'invente pas de scan", async () => {
  const j = unJournal();
  assert.equal(await j.changerEtat("jamais-vu", ETATS.partie), false);
  assert.deepEqual(await j.tous(), []);
});

test("nonArrives ne garde que ce qui n'a pas atteint le serveur", async () => {
  const j = unJournal();
  await j.noter(scan("r1", "1"));
  await j.noter(scan("r2", "2"));
  await j.noter(scan("r3", "3"));
  await j.changerEtat("r2", ETATS.partie);
  await j.changerEtat("r3", ETATS.refusee, "bloc inconnu");
  assert.deepEqual((await j.nonArrives()).map((s) => s.bib), ["1", "3"]);
});

// --- La reprise d'un refus --------------------------------------------------

test("une reprise garde une seule ligne, a sa place", async () => {
  const j = unJournal();
  await j.noter(scan("r1", "1"));
  await j.noter(scan("r2", "2"));
  await j.changerEtat("r1", ETATS.refusee, "dossard inconnu");

  await j.reprendre("r1", "r1-bis");

  const tous = await j.tous();
  assert.equal(tous.length, 2);
  assert.deepEqual(tous.map((s) => s.bib), ["1", "2"], "elle reste en premier");
  assert.equal(tous[0].ref, "r1-bis");
  assert.equal(tous[0].etat, ETATS.enAttente);
  assert.equal(tous[0].motif, "dossard inconnu");
});

test("apres une reprise, l'acquittement porte sur la nouvelle reference", async () => {
  const j = unJournal();
  await j.noter(scan("r1"));
  await j.reprendre("r1", "r1-bis");
  await j.changerEtat("r1-bis", ETATS.partie);
  assert.equal((await j.tous())[0].etat, ETATS.partie);
});

test("une reprise orpheline n'invente pas de scan", async () => {
  const j = unJournal();
  assert.equal(await j.reprendre("jamais-vu", "neuve"), false);
  assert.deepEqual(await j.tous(), []);
});

// --- La purge ---------------------------------------------------------------

const MAINTENANT = Date.parse("2026-11-09T10:00:00Z");

test("la purge efface ce qui a plus de trente jours", async () => {
  const j = unJournal();
  await j.noter(scan("vieux", "1", "2026-09-01T10:00:00Z"));
  await j.noter(scan("recent", "2", "2026-11-08T10:00:00Z"));

  assert.equal(await j.purger(MAINTENANT), 1);
  assert.deepEqual((await j.tous()).map((s) => s.bib), ["2"]);
});

test("la purge garde ce qui a exactement moins de trente jours", async () => {
  const j = unJournal();
  const limite = new Date(MAINTENANT - RETENTION_JOURS * JOUR + 1000).toISOString();
  await j.noter(scan("juste-avant", "1", limite));
  assert.equal(await j.purger(MAINTENANT), 0);
});

test("un scan dont l'heure est illisible n'est JAMAIS efface", async () => {
  const j = unJournal();
  await j.noter(scan("sans-date", "1", "pas une date"));
  await j.noter(scan("vieux", "2", "2026-01-01T10:00:00Z"));

  await j.purger(MAINTENANT);

  // On n'efface pas ce qu'on ne sait pas dater.
  assert.deepEqual((await j.tous()).map((s) => s.ref), ["sans-date"]);
});

test("la purge garde l'etat et le motif de ce qu'elle conserve", async () => {
  const j = unJournal();
  await j.noter(scan("r1", "1", "2026-11-08T10:00:00Z"));
  await j.changerEtat("r1", ETATS.refusee, "dossard inconnu");
  await j.noter(scan("vieux", "2", "2026-01-01T10:00:00Z"));

  await j.purger(MAINTENANT);

  const restant = (await j.tous())[0];
  assert.equal(restant.etat, ETATS.refusee);
  assert.equal(restant.motif, "dossard inconnu");
});

/**
 * LE test qui verrouille la garantie de la spec : la purge est une operation
 * sur une VUE, pas sur la source de verite de l'envoi. C'est la seule raison
 * pour laquelle un effacement automatique est acceptable.
 */
test("la purge ne touche pas aux reussites qui attendent d'etre envoyees", async () => {
  const magasinFile = new MagasinMemoire();
  const file = new FileDeReussites(magasinFile, new MagasinMemoire());
  const j = unJournal();

  const vieille = scan("vieille", "7", "2026-01-01T10:00:00Z");
  await file.ajouter(vieille);
  await j.noter(vieille);

  await j.purger(MAINTENANT);

  // Le journal l'a oubliee -- c'est ce qu'on lui demande...
  assert.deepEqual(await j.tous(), []);
  // ...mais elle est toujours en file, et elle partira.
  assert.equal(await file.nombreEnAttente(), 1);
  assert.equal((await file.enAttente())[0].valeur.bib, "7");
});

test("la reference courte tient sur six caracteres", () => {
  assert.equal(refCourte("8f3c1d20-aaaa-bbbb"), "8f3c1d");
  assert.equal(refCourte(null), "");
});

// --- L'identite du telephone ------------------------------------------------

function faussesReglages() {
  const m = new Map();
  return { async lire(c) { return m.get(c); },
           async ecrire(c, v) { m.set(c, v); } };
}

test("le premier appel cree un identifiant", async () => {
  const r = faussesReglages();
  const i = await identiteCourante(r);
  assert.ok(i.id);
  assert.equal(i.nom, null);
});

test("l'appel suivant retrouve le MEME identifiant", async () => {
  // S'il changeait, la console afficherait vingt-cinq appareils au lieu d'un.
  const r = faussesReglages();
  const premier = (await identiteCourante(r)).id;
  assert.equal((await identiteCourante(r)).id, premier);
});

test("un enregistrement abime donne un identifiant neuf, sans lever", async () => {
  const r = faussesReglages();
  await r.ecrire("identite", { nom: "sans identifiant" });
  assert.ok((await identiteCourante(r)).id);
});

test("renommer ne change pas l'identifiant", async () => {
  const r = faussesReglages();
  const avant = (await identiteCourante(r)).id;
  await renommer(r, "Mur jaune");
  const apres = await identiteCourante(r);
  assert.equal(apres.id, avant);
  assert.equal(apres.nom, "Mur jaune");
});

test("un nom vide ou blanc revient a ne pas en avoir", async () => {
  const r = faussesReglages();
  await renommer(r, "Mur jaune");
  await renommer(r, "   ");
  assert.equal((await identiteCourante(r)).nom, null);
});

test("un nom trop long est coupe, jamais refuse", () => {
  assert.equal(nettoyerLeNom("x".repeat(200)).length, LONGUEUR_NOM);
});

test("deux telephones n'ont pas le meme identifiant", async () => {
  const a = await identiteCourante(faussesReglages());
  const b = await identiteCourante(faussesReglages());
  assert.notEqual(a.id, b.id);
});
