/**
 * Le service worker : il ne fait qu'UNE chose, servir l'application hors ligne.
 *
 * ⚠️ **Il ne touche jamais à `/api/`.** Un service worker qui rejouerait un
 * `POST` créerait des doublons ; l'idempotence du serveur les absorberait, mais
 * la file du téléphone se croirait vidée pendant qu'une réussite y reste. La
 * file est gérée par l'application, dans IndexedDB, et elle seule décide de ce
 * qui part. Le cache ne doit jamais avoir d'avis là-dessus.
 *
 * ## La stratégie, et ce qu'elle coûte
 *
 * **Servir depuis le cache, et rafraîchir derrière** (*stale-while-revalidate*).
 * L'application s'ouvre instantanément et sans réseau ; la version fraîche est
 * téléchargée en arrière-plan et prend effet **au lancement suivant**.
 *
 * Ce délai est assumé, et c'est un choix de sécurité : recharger la page toute
 * seule parce qu'une nouvelle version est arrivée couperait un juge en plein
 * geste. Un correctif publié la veille est donc pris le matin ; un correctif
 * publié PENDANT la compétition demande de fermer et rouvrir l'application.
 * C'est écrit dans le runbook.
 */

// v2 : la refonte visuelle (Archivo, couleurs de circuit). Changer ce nom
// est ce qui fait qu'un iPhone deja installe jette l'ancienne coquille.
const CACHE = "climbcontest-juge-v2";

/**
 * Ce qu'on garde pour pouvoir démarrer sans réseau.
 *
 * `jsqr.js` n'y est PAS : 250 ko qui ne servent qu'à Safari, et qui seront mis
 * en cache au premier scan sur les appareils qui en ont besoin. Les précharger
 * ferait payer à tout le monde ce dont seuls certains ont besoin.
 */
const COQUILLE = [
  "/juge",
  "/juge/manifest.webmanifest",
  "/static/juge/juge.js",
  "/static/juge/api.js",
  "/static/juge/jeton.js",
  "/static/juge/scan.js",
  "/static/juge/file.js",
  "/static/juge/idb.js",
  "/static/juge/catalogue.js",
  "/static/juge/couleurs.js",
  "/static/juge/archivo.ttf",
  "/static/juge/expediteur.js",
  "/static/juge/politique.js",
  "/static/juge/verrou.js",
  "/static/juge/historique.js",
  "/static/juge/identite.js",
  "/static/juge/icone-192.png",
];

self.addEventListener("install", (evenement) => {
  evenement.waitUntil(
    caches.open(CACHE)
      // `addAll` échoue en bloc si UN fichier manque. On ajoute donc un par un :
      // mieux vaut une coquille incomplète qu'un service worker qui ne
      // s'installe pas du tout et laisse l'application sans hors-ligne.
      .then((cache) => Promise.all(
        COQUILLE.map((url) => cache.add(url).catch(() => null)),
      ))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (evenement) => {
  evenement.waitUntil(
    caches.keys()
      .then((noms) => Promise.all(
        noms.filter((nom) => nom !== CACHE).map((nom) => caches.delete(nom)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (evenement) => {
  const requete = evenement.request;
  if (requete.method !== "GET") return;

  const url = new URL(requete.url);
  // Ni les appels API, ni ce qui vient d'ailleurs. On ne se met pas entre
  // l'application et le serveur.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  evenement.respondWith(servir(requete, url));
});

async function servir(requete, url) {
  const cache = await caches.open(CACHE);
  // Une navigation vers `/juge?v=quelquechose` doit retrouver l'entrée `/juge` :
  // sinon un lien avec un paramètre ne serait jamais servi hors ligne.
  const cle = requete.mode === "navigate" ? "/juge" : requete;

  const enCache = await cache.match(cle);
  const duReseau = fetch(requete)
    .then((reponse) => {
      // On ne met en cache que ce qui a vraiment été servi. Une page d'erreur
      // mise en cache resterait servie hors ligne, indéfiniment.
      if (reponse && reponse.ok) cache.put(cle, reponse.clone());
      return reponse;
    })
    .catch(() => null);

  // Le cache d'abord : l'application s'ouvre instantanément, et le
  // rafraîchissement continue derrière pour le lancement suivant.
  if (enCache) return enCache;

  const reponse = await duReseau;
  if (reponse) return reponse;

  // Ni cache ni réseau. Pour une navigation, on répond quand même quelque
  // chose de lisible plutôt que l'écran d'erreur du navigateur.
  if (requete.mode === "navigate") {
    return new Response(
      "<!doctype html><meta charset=utf-8>" +
      "<body style='background:#0E1116;color:#EEF1F5;font-family:system-ui;" +
      "padding:2rem;line-height:1.6'>" +
      "<h1>Application pas encore installée</h1>" +
      "<p>Ouvre-la une première fois avec du réseau : elle fonctionnera " +
      "ensuite sans connexion.</p>",
      { headers: { "Content-Type": "text/html; charset=utf-8" }, status: 503 },
    );
  }
  return Response.error();
}
