/**
 * Le dialogue HTTP de la PWA juge (spec 007).
 *
 * L'invariant protege ici est le meme que cote Android, et c'est le seul qui
 * compte : **une reussite ne quitte la file que si le serveur a STATUE sur
 * elle.** Reseau coupe, reponse partielle, 401, corps illisible : dans tous ces
 * cas, rien n'est acquitte.
 *
 *   node --test "tests/js/*.test.mjs"
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { Api, ENTETE_CLE } from "../../climbcontest/static/juge/api.js";

/** Un `fetch` factice qui note ce qu'on lui demande. */
function faux(reponses) {
  const appels = [];
  const fetch = async (url, options) => {
    appels.push({ url, options });
    const r = Array.isArray(reponses) ? reponses.shift() : reponses;
    if (r instanceof Error) throw r;
    return {
      ok: r.code >= 200 && r.code < 300,
      status: r.code,
      // Les en-tetes de reponse : la version du serveur y voyage, sur le 200
      // comme sur le 304 (spec 030).
      headers: { get: (nom) => (r.entetes || {})[nom] ?? null },
      json: async () => {
        if (r.corps === undefined) throw new Error("pas de json");
        return r.corps;
      },
    };
  };
  return { fetch, appels };
}

test("le jeton part dans l'en-tete, sur toutes les requetes", async () => {
  const { fetch, appels } = faux({ code: 201, corps: { success: true, id: "Dupont" } });
  await new Api({ jeton: "secret", fetch }).verifierGrimpeur("42");
  assert.equal(appels[0].options.headers[ENTETE_CLE], "secret");
});

test("sans jeton, aucun en-tete n'est pose", async () => {
  // Un en-tete VIDE serait une cle fausse, donc un 401 -- alors que l'absence
  // reste acceptee par un serveur en mode tolere. Les deux different.
  const { fetch, appels } = faux({ code: 201, corps: { success: true, id: "x" } });
  await new Api({ jeton: null, fetch }).verifierGrimpeur("42");
  assert.equal(ENTETE_CLE in appels[0].options.headers, false);
});

test("un grimpeur connu rend son nom", async () => {
  const { fetch } = faux({ code: 201, corps: { success: true, id: "Dupont Lea" } });
  const r = await new Api({ jeton: "s", fetch }).verifierGrimpeur("42");
  assert.equal(r.ok, true);
  assert.equal(r.libelle, "Dupont Lea");
});

test("un refus metier n'est PAS un probleme reseau", async () => {
  // La distinction decide du message affiche : « rescanne » ou « va voir un
  // organisateur ». Se tromper envoie le juge chercher quelqu'un pour rien.
  const { fetch } = faux({ code: 400, corps: { success: false, message: "inconnu" } });
  const r = await new Api({ jeton: "s", fetch }).verifierGrimpeur("999");
  assert.equal(r.ok, false);
  assert.equal(r.reseau, false);
});

test("un 500 est un probleme reseau : le juge doit reessayer", async () => {
  const { fetch } = faux({ code: 500, corps: { success: false, message: "boum" } });
  const r = await new Api({ jeton: "s", fetch }).verifierGrimpeur("42");
  assert.equal(r.reseau, true);
});

test("un corps illisible n'est pas un refus metier", async () => {
  // C'est presque toujours une page HTML d'erreur : 502 d'un proxy, 503 d'un
  // serveur qui redemarre. Le juge doit reessayer, pas rescanner.
  const { fetch } = faux({ code: 502 });
  const r = await new Api({ jeton: "s", fetch }).verifierGrimpeur("42");
  assert.equal(r.ok, false);
  assert.equal(r.reseau, true);
});

test("le reseau coupe ne leve pas, il rend un echec reseau", async () => {
  const { fetch } = faux(new TypeError("Failed to fetch"));
  const r = await new Api({ jeton: "s", fetch }).verifierGrimpeur("42");
  assert.equal(r.ok, false);
  assert.equal(r.reseau, true);
});

// --- L'envoi par lots -------------------------------------------------------

const UN_LOT = [{ ref: "a", bib: "1", bloc: "ZJ6", at: "2026-11-08T10:00:00Z" }];

test("un lot vide ne fait aucune requete", async () => {
  const { fetch, appels } = faux({ code: 200, corps: {} });
  await new Api({ jeton: "s", fetch }).envoyerLot([]);
  assert.equal(appels.length, 0);
});

test("une reussite enregistree est acquittee", async () => {
  const { fetch } = faux({ code: 200,
    corps: { resultats: [{ ref: "a", etat: "enregistree" }] } });
  const r = await new Api({ jeton: "s", fetch }).envoyerLot(UN_LOT);
  assert.equal(r.acquittees.has("a"), true);
  assert.equal(r.refusees.length, 0);
});

test("deja_connue est un succes, pas une erreur", async () => {
  // Double appui sur « Envoyer » : le serveur est idempotent, et ca ne doit
  // jamais ressembler a une panne.
  const { fetch } = faux({ code: 200,
    corps: { resultats: [{ ref: "a", etat: "deja_connue" }] } });
  const r = await new Api({ jeton: "s", fetch }).envoyerLot(UN_LOT);
  assert.equal(r.acquittees.has("a"), true);
});

test("une refusee est acquittee ET signalee", async () => {
  // Le serveur a STATUE : elle quitte la file. Mais le juge doit le savoir.
  const { fetch } = faux({ code: 200,
    corps: { resultats: [{ ref: "a", etat: "refusee", message: "dossard inconnu" }] } });
  const r = await new Api({ jeton: "s", fetch }).envoyerLot(UN_LOT);
  assert.equal(r.acquittees.has("a"), true);
  assert.deepEqual(r.refusees, [{ ref: "a", message: "dossard inconnu" }]);
});

test("un etat inconnu ne fait RIEN acquitter", async () => {
  // On ne sait pas ce qui s'est passe, donc on garde. Le defaut est de garder.
  const { fetch } = faux({ code: 200,
    corps: { resultats: [{ ref: "a", etat: "chose_nouvelle" }] } });
  const r = await new Api({ jeton: "s", fetch }).envoyerLot(UN_LOT);
  assert.equal(r.acquittees.size, 0);
});

test("une reponse partielle n'acquitte que ce qu'elle nomme", async () => {
  const lot = [...UN_LOT, { ref: "b", bib: "2", bloc: "ZJ7", at: "x" }];
  const { fetch } = faux({ code: 200,
    corps: { resultats: [{ ref: "a", etat: "enregistree" }] } });
  const r = await new Api({ jeton: "s", fetch }).envoyerLot(lot);
  assert.deepEqual([...r.acquittees], ["a"]);
});

test("un 401 n'acquitte RIEN : la file reste intacte", async () => {
  const { fetch } = faux({ code: 401, corps: { success: false } });
  const r = await new Api({ jeton: "mauvaise", fetch }).envoyerLot(UN_LOT);
  assert.equal(r.ok, false);
  assert.equal(r.acquittees.size, 0);
  assert.equal(r.code, 401);
});

test("le reseau coupe n'acquitte RIEN", async () => {
  const { fetch } = faux(new TypeError("Failed to fetch"));
  const r = await new Api({ jeton: "s", fetch }).envoyerLot(UN_LOT);
  assert.equal(r.acquittees.size, 0);
});

test("l'identite de l'appareil voyage avec le lot", async () => {
  const { fetch, appels } = faux({ code: 200, corps: { resultats: [] } });
  await new Api({ jeton: "s", fetch })
    .envoyerLot(UN_LOT, { id: "abc", nom: "Mur jaune" });
  const corps = JSON.parse(appels[0].options.body);
  assert.deepEqual(corps.appareil, { id: "abc", nom: "Mur jaune" });
});

test("sans identite, le corps n'a pas de champ appareil", async () => {
  const { fetch, appels } = faux({ code: 200, corps: { resultats: [] } });
  await new Api({ jeton: "s", fetch }).envoyerLot(UN_LOT);
  assert.equal("appareil" in JSON.parse(appels[0].options.body), false);
});

// --- Le catalogue -----------------------------------------------------------

test("le catalogue annonce la version connue", async () => {
  const { fetch, appels } = faux({ code: 304 });
  const r = await new Api({ jeton: "s", fetch }).telechargerCatalogue(7);
  assert.equal(appels[0].options.headers["If-None-Match"], '"7"');
  assert.equal(r.etat, "deja-a-jour");
});

test("un catalogue recu est rendu", async () => {
  const { fetch } = faux({ code: 200, corps: { version: 3, participants: {}, blocs: {} } });
  const r = await new Api({ jeton: "s", fetch }).telechargerCatalogue(null);
  assert.equal(r.etat, "recu");
  assert.equal(r.catalogue.version, 3);
});

test("un catalogue refuse est un echec, pas un catalogue vide", async () => {
  const { fetch } = faux({ code: 401 });
  const r = await new Api({ jeton: "mauvaise", fetch }).telechargerCatalogue(null);
  assert.equal(r.etat, "echec");
  assert.equal(r.code, 401);
});

// --- L'annonce du telephone, et la version du serveur (spec 030) ------------

const ANNONCE = { id: "abc-123", nom: "Entrée du mur", app: "v0.16.0" };

test("le telephone s'annonce sur la requete de catalogue", async () => {
  const { fetch, appels } = faux({ code: 304 });
  await new Api({ jeton: "s", fetch }).telechargerCatalogue(7, ANNONCE);
  const entetes = appels[0].options.headers;
  assert.equal(entetes["X-Device-Id"], "abc-123");
  assert.equal(entetes["X-App-Version"], "v0.16.0");
  // Percent-encode : un en-tete HTTP ne transporte pas surement les accents.
  assert.equal(entetes["X-Device-Name"], "Entr%C3%A9e%20du%20mur");
});

test("sans annonce, aucun de ces en-tetes -- le contrat d'avant la spec 030",
     async () => {
  const { fetch, appels } = faux({ code: 304 });
  await new Api({ jeton: "s", fetch }).telechargerCatalogue(7);
  const entetes = appels[0].options.headers;
  for (const nom of ["X-Device-Id", "X-Device-Name", "X-App-Version"]) {
    assert.equal(nom in entetes, false,
                 `${nom} ne doit pas etre envoye : l'app Android n'en envoie aucun`);
  }
});

test("FORCER le catalogue : requete nue, aucun If-None-Match", async () => {
  // ⚠️ Le bouton « Reteldecharger maintenant ». Le serveur decide du 304 par
  // egalite stricte : annoncer un autre numero pour le forcer ne marcherait
  // pas, il refuse deliberement ce raccourci. Une requete NUE est le seul
  // moyen propre d'obtenir un 200.
  const { fetch, appels } = faux({ code: 200, corps: { version: 9 } });
  await new Api({ jeton: "s", fetch }).telechargerCatalogue(null, ANNONCE);
  assert.equal("If-None-Match" in appels[0].options.headers, false);
  assert.equal(appels[0].url.includes("depuis"), false);
});

test("la version du serveur remonte sur le 304 -- le cas majoritaire", async () => {
  const { fetch } = faux({ code: 304, entetes: { "X-Server-Version": "v0.16.0" } });
  const r = await new Api({ jeton: "s", fetch }).telechargerCatalogue(7, ANNONCE);
  assert.equal(r.etat, "deja-a-jour");
  assert.equal(r.serveur, "v0.16.0");
});

test("la version du serveur remonte aussi sur le 200", async () => {
  const { fetch } = faux({ code: 200, corps: { version: 3 },
                           entetes: { "X-Server-Version": "v0.16.0" } });
  const r = await new Api({ jeton: "s", fetch }).telechargerCatalogue(null);
  assert.equal(r.serveur, "v0.16.0");
});

test("reseau coupe : aucune version, aucune exception", async () => {
  const { fetch } = faux(new Error("hors ligne"));
  const r = await new Api({ jeton: "s", fetch }).telechargerCatalogue(7, ANNONCE);
  assert.equal(r.etat, "echec");
  assert.equal(r.serveur, null);
});

test("la version voyage aussi avec les lots -- la redondance de F8", async () => {
  const { fetch, appels } = faux({ code: 200, corps: { resultats: [] } });
  await new Api({ jeton: "s", fetch }).envoyerLot(UN_LOT, ANNONCE);
  assert.equal(JSON.parse(appels[0].options.body).appareil.app, "v0.16.0");
});
