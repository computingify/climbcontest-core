/**
 * La file hors ligne de la PWA juge (spec 007, IT2), sur Node.
 *
 * L'invariant protege ici est le seul qui compte, et c'est le meme que cote
 * Android : **une reussite ne quitte la file que si le serveur a STATUE sur
 * elle.** Reseau coupe, reponse partielle, 401, corps illisible -- dans tous ces
 * cas la file reste intacte.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { FileDeReussites, MagasinMemoire } from
  "../../climbcontest/static/juge/file.js";
import { Expediteur } from "../../climbcontest/static/juge/expediteur.js";

function uneFile() {
  return new FileDeReussites(new MagasinMemoire(), new MagasinMemoire());
}

const scan = (ref, bib = "1", bloc = "ZJ6") =>
  ({ ref, bib, bloc, at: "2026-11-08T10:00:00Z" });

test("une file neuve est vide", async () => {
  assert.equal(await uneFile().nombreEnAttente(), 0);
});

test("une reussite ajoutee attend", async () => {
  const file = uneFile();
  await file.ajouter(scan("a"));
  assert.equal(await file.nombreEnAttente(), 1);
});

test("l'ordre est celui ou le juge a valide", async () => {
  const file = uneFile();
  for (const r of ["a", "b", "c"]) await file.ajouter(scan(r));
  const enAttente = await file.enAttente();
  assert.deepEqual(enAttente.map((e) => e.valeur.ref), ["a", "b", "c"]);
});

test("le lot est plafonne", async () => {
  const file = uneFile();
  for (let i = 0; i < 10; i++) await file.ajouter(scan(`r${i}`));
  assert.equal((await file.prochainLot(3)).length, 3);
});

test("acquitter retire, et seulement ce qui est nomme", async () => {
  const file = uneFile();
  for (const r of ["a", "b", "c"]) await file.ajouter(scan(r));

  await file.acquitter(new Set(["a", "c"]));

  const restant = (await file.enAttente()).map((e) => e.valeur.ref);
  assert.deepEqual(restant, ["b"]);
});

test("acquitter une reference inconnue ne retire rien", async () => {
  const file = uneFile();
  await file.ajouter(scan("a"));
  await file.acquitter(new Set(["jamais-vue"]));
  assert.equal(await file.nombreEnAttente(), 1);
});

test("acquitter rien ne retire rien", async () => {
  const file = uneFile();
  await file.ajouter(scan("a"));
  await file.acquitter(new Set());
  assert.equal(await file.nombreEnAttente(), 1);
});

// --- Les refusees -----------------------------------------------------------

test("une refusee est mise de cote avec son motif", async () => {
  const file = uneFile();
  await file.mettreDeCote(scan("a"), "dossard inconnu");
  const mises = await file.refusees();
  assert.equal(mises.length, 1);
  assert.equal(mises[0].motif, "dossard inconnu");
});

test("renvoyer les refusees les remet en file, sous une nouvelle reference", async () => {
  const file = uneFile();
  await file.mettreDeCote(scan("a", "42", "ZV3"), "dossard inconnu");

  let n = 0;
  const reprises = await file.renvoyerLesRefusees(() => `neuve-${++n}`);

  assert.deepEqual(reprises, [{ ancienne: "a", nouvelle: "neuve-1" }]);
  const enFile = (await file.enAttente()).map((e) => e.valeur);
  assert.equal(enFile.length, 1);
  assert.equal(enFile[0].ref, "neuve-1");
  assert.equal(enFile[0].bib, "42");
  // Le motif du refus ne repart pas au serveur : ce n'est pas une donnee de
  // reussite, c'est ce que le SERVEUR avait repondu.
  assert.equal("motif" in enFile[0], false);
  assert.equal(await file.nombreRefusees(), 0);
});

test("renvoyer quand il n'y a rien ne fait rien", async () => {
  assert.deepEqual(await uneFile().renvoyerLesRefusees(() => "x"), []);
});

// --- L'expediteur, avec une API factice --------------------------------------

function fausseApi(reponses) {
  const envois = [];
  return {
    envois,
    async envoyerLot(items, appareil) {
      envois.push({ items, appareil });
      const r = Array.isArray(reponses) ? reponses.shift() : reponses;
      return { acquittees: new Set(r.acquittees || []), refusees: r.refusees || [],
               ok: r.ok !== false, code: r.code, message: r.message,
               catalogueVersion: r.catalogueVersion ?? null };
    },
  };
}

test("rien a envoyer : aucune requete", async () => {
  const api = fausseApi({ acquittees: [] });
  const bilan = await new Expediteur(uneFile(), api).tenter();
  assert.equal(bilan, null);
  assert.equal(api.envois.length, 0);
});

test("un envoi reussi vide la file", async () => {
  const file = uneFile();
  await file.ajouter(scan("a"));
  const api = fausseApi({ acquittees: ["a"] });

  const bilan = await new Expediteur(file, api).tenter();

  assert.equal(bilan.aReussi, true);
  assert.equal(await file.nombreEnAttente(), 0);
});

/**
 * LE test de cette iteration. Un serveur injoignable ne doit RIEN faire perdre.
 */
test("un envoi rate laisse la file INTACTE", async () => {
  const file = uneFile();
  for (const r of ["a", "b"]) await file.ajouter(scan(r));
  const api = fausseApi({ ok: false, code: 0, message: "Serveur injoignable" });

  const expediteur = new Expediteur(file, api);
  const bilan = await expediteur.tenter();

  assert.equal(bilan.aReussi, false);
  assert.equal(await file.nombreEnAttente(), 2);
  assert.equal(expediteur.echecsConsecutifs, 1);
});

test("un 401 ne fait rien perdre non plus", async () => {
  const file = uneFile();
  await file.ajouter(scan("a"));
  const api = fausseApi({ ok: false, code: 401, message: "Cle d'API requise" });

  await new Expediteur(file, api).tenter();

  assert.equal(await file.nombreEnAttente(), 1);
});

test("une reponse partielle ne retire que ce qui est acquitte", async () => {
  const file = uneFile();
  for (const r of ["a", "b", "c"]) await file.ajouter(scan(r));
  const api = fausseApi({ acquittees: ["a", "c"] });

  await new Expediteur(file, api).tenter();

  const restant = (await file.enAttente()).map((e) => e.valeur.ref);
  assert.deepEqual(restant, ["b"]);
});

test("une refusee quitte la file MAIS est mise de cote", async () => {
  const file = uneFile();
  await file.ajouter(scan("a"));
  const api = fausseApi({ acquittees: ["a"],
                          refusees: [{ ref: "a", message: "dossard inconnu" }] });

  const bilan = await new Expediteur(file, api).tenter();

  assert.equal(await file.nombreEnAttente(), 0);
  assert.equal(await file.nombreRefusees(), 1);
  assert.equal(bilan.envoyees, 0, "une refusee n'est pas une envoyee");
  assert.equal((await file.refusees())[0].motif, "dossard inconnu");
});

test("les echecs consecutifs repartent de zero apres un succes", async () => {
  const file = uneFile();
  await file.ajouter(scan("a"));
  const api = fausseApi([{ ok: false, code: 0 }, { acquittees: ["a"] }]);
  const expediteur = new Expediteur(file, api);

  await expediteur.tenter();
  assert.equal(expediteur.echecsConsecutifs, 1);
  await expediteur.tenter();
  assert.equal(expediteur.echecsConsecutifs, 0);
});

test("l'identite de l'appareil est relue a CHAQUE lot", async () => {
  // Le juge peut renommer son telephone en pleine competition : le nom
  // enregistre cote serveur doit etre celui du moment de l'envoi.
  const file = uneFile();
  await file.ajouter(scan("a"));
  await file.ajouter(scan("b"));
  const api = fausseApi([{ acquittees: ["a"] }, { acquittees: ["b"] }]);
  let nom = "Mur jaune";
  const expediteur = new Expediteur(file, api, { identite: () => ({ id: "x", nom }) });

  await expediteur.tenter();
  nom = "Mur vert";
  await expediteur.tenter();

  assert.equal(api.envois[0].appareil.nom, "Mur jaune");
  assert.equal(api.envois[1].appareil.nom, "Mur vert");
});
