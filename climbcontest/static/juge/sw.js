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
// ⚠️ Le numero CHANGE des que la coquille change. Sans ca, les telephones
// gardent l'ancienne : `activate` ne supprime que les caches dont le nom
// differe. Passe a v3 le 02/09 -- ajout du logo de l'ecran d'accueil, puis a
// v4 le 03/09 -- ajout de `poste.js` (spec 034). Sans ce changement de nom, un
// iPhone deja installe garderait une coquille ou le module manque, et le
// bouton « Scanner le QR de mon poste » planterait au premier appui.
// v5 le 03/09, apres relecture -- le bouton de poste passe sur l'ecran
// d'accueil et `poste.js` compose desormais « Zone A ». Le fichier existe deja
// dans la coquille des telephones en v4 : sans changement de NOM, ils
// garderaient l'ancienne version du module et continueraient de se nommer
// « A » tout court.
// v6 le 03/09 (spec 039) -- l'application s'ouvre en CLAIR. La coquille porte
// le gabarit `/juge`, donc tout le CSS : sans changement de nom, un telephone
// deja installe rouvrirait l'ancienne page sombre et personne ne verrait le
// changement. `couleurs.js` change aussi (le circuit « Noir » depend du
// theme), et une coquille qui melangerait l'ancien CSS et le nouveau module
// afficherait de la craie sur du papier.
// v7 le 03/09 (spec 040) -- le juge peut imposer le theme depuis les
// Reglages. La coquille porte le gabarit (donc le script en ligne qui pose le
// theme avant la peinture) ET le nouveau module `theme.js` : sans changement
// de nom, un telephone deja installe rouvrirait une page sans le reglage, et
// le module manquerait a la coquille hors ligne.
// v8 le 03/09 (spec 030) -- la coquille gagne `versions.js`, et le gabarit
// `/juge` porte les deux nouvelles sections des Reglages. ⚠️ Ce numero est le
// SEUL endroit ou la fusion pouvait se tromper sans bruit : la liste
// `COQUILLE` fusionne ligne a ligne -- `theme.js` et `versions.js` s'y
// retrouvent tous les deux sans conflit -- mais le NOM du cache est une seule
// ligne, et git garde celle d'un des deux cotes. Reste a v7, et un telephone
// deja installe garde une coquille sans `versions.js` : les boutons des
// nouvelles sections plantent au premier appui, hors ligne.
// v9 le 04/09 (spec 041) -- la MATIERE imprimee : lisere d'encre et ombre du
// bouton. Tout est dans le CSS du gabarit `/juge`, que la coquille porte : sans
// changement de nom, un telephone deja installe rouvrirait l'ancienne feuille
// et ne verrait rien. Et `couleurs.js` gagne `estLeNoir`, que `juge.js` importe
// desormais : une coquille qui melangerait l'ancien module et le nouveau
// `juge.js` planterait au premier bloc scanne.
// v10 le 04/09 (spec 042) -- l'interrupteur des Reglages et le bouton de scan
// qui change d'habit vivent ENTIEREMENT dans le CSS et le gabarit `/juge`, que
// la coquille porte. Sans changement de nom, un telephone deja installe
// rouvrirait l'ancienne page : il verrait toujours sa case a cocher et la
// demande de scan sur un poste deja nomme, et rien ne dirait pourquoi.
const CACHE = "climbcontest-juge-v10";

/**
 * Ce qu'on garde pour pouvoir démarrer sans réseau.
 *
 * `jsqr.js` n'y est PAS : 250 ko qui ne servent qu'à Safari, et qui seront mis
 * en cache au premier scan sur les appareils qui en ont besoin. Les précharger
 * ferait payer à tout le monde ce dont seuls certains ont besoin.
 */
const COQUILLE = [
  "/juge",
  // ⚠️ Le manifeste N'EST PAS ici, et c'est voulu (spec 014) : il varie selon
  // le jeton. Mis en cache sous une URL fixe, il servirait le manifeste d'un
  // autre jeton -- ou un manifeste nu a une application qui en attend un
  // porteur. Il n'est lu qu'a l'installation et a la mise a jour, jamais
  // pendant une competition : le mettre hors ligne n'apporte rien.
  "/static/juge/juge.js",
  // L'ecran d'accueil doit s'afficher hors ligne aussi.
  "/static/juge/logo-club.png",
  "/static/juge/api.js",
  "/static/juge/jeton.js",
  "/static/juge/scan.js",
  "/static/juge/file.js",
  "/static/juge/idb.js",
  "/static/juge/catalogue.js",
  // ⚠️ `juge.js` l'IMPORTE : absent de la coquille, l'application ne demarrerait
  // pas hors ligne. Toute ajout de module doit passer par cette liste.
  "/static/juge/versions.js",
  "/static/juge/couleurs.js",
  "/static/juge/archivo.ttf",
  "/static/juge/expediteur.js",
  "/static/juge/politique.js",
  "/static/juge/verrou.js",
  "/static/juge/historique.js",
  "/static/juge/identite.js",
  "/static/juge/poste.js",
  "/static/juge/theme.js",
  "/static/juge/icone-192.png",
  // ⚠️ `icone-512.png` n'y est PAS, volontairement : le manifeste ne la lit
  // qu'a l'installation, en ligne. La mettre dans la coquille ferait
  // telecharger 100 ko a chaque changement de version pour une image que
  // l'application n'affiche jamais.
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

// ⚠️ AVANT D'AJOUTER UN ECOUTEUR `sync` OU `periodicsync` ICI -- vider la file
// en arriere-plan est une evolution naturelle pour une application hors ligne,
// et elle casserait un detecteur situe a l'autre bout du systeme.
//
// La console repere un cache pose devant `/api/v2/catalog` en croisant deux
// signaux : des lots qui arrivent, et des annonces qui n'arrivent plus
// (`contest._annonce_perdue`). Ce croisement n'est valable que parce
// qu'AUCUN lot ne part hors du premier plan : la boucle de `juge.js` teste
// `visibilityState`, et les autres chemins d'envoi sont des gestes du juge.
//
// Un envoi en arriere-plan romprait ce lien : des lots partiraient sans
// annonce, et la console accuserait un cache sur un telephone en veille
// parfaitement sain. Si on ajoute cette synchronisation, il faut rendre
// l'annonce solidaire de l'envoi -- ou changer le detecteur, en connaissance
// de cause.
self.addEventListener("activate", (evenement) => {
  evenement.waitUntil(
    caches.keys()
      .then((noms) => Promise.all(
        noms.filter((nom) => nom !== CACHE).map((nom) => caches.delete(nom)),
      ))
      .then(() => self.clients.claim()),
  );
});

/**
 * « Mettre a jour et redemarrer », demande par l'ecran des reglages (spec 030).
 *
 * ⚠️ **On ne vide RIEN avant d'avoir recu.** Un `caches.delete` suivi d'un
 * telechargement qui echoue laisserait le telephone sans application hors
 * ligne -- exactement la panne que ce fichier existe pour empecher. Chaque
 * fichier n'est remplace que quand sa version fraiche est arrivee ; sans
 * reseau, rien ne bouge et la coquille precedente reste servie.
 *
 * `cache: "reload"` court-circuite le cache HTTP du navigateur : sans lui, on
 * remettrait dans le cache du service worker la meme reponse que celle qu'on
 * cherche a remplacer.
 */
self.addEventListener("message", (evenement) => {
  const message = evenement.data;
  if (!message || message.type !== "rafraichir-la-coquille") return;
  evenement.waitUntil(rafraichirLaCoquille().then((bilan) => {
    // On repond sur le port fourni par la page : elle attend ce bilan pour
    // decider si elle recharge. Sans reponse, elle ne recharge pas.
    if (evenement.ports && evenement.ports[0]) {
      evenement.ports[0].postMessage(bilan);
    }
  }));
});

async function rafraichirLaCoquille() {
  const cache = await caches.open(CACHE);
  let remplaces = 0;
  let echecs = 0;
  await Promise.all(COQUILLE.map(async (url) => {
    try {
      const reponse = await fetch(url, { cache: "reload" });
      if (reponse && reponse.ok) {
        await cache.put(url, reponse.clone());
        remplaces += 1;
      } else {
        echecs += 1;
      }
    } catch {
      echecs += 1;
    }
  }));
  return { remplaces, echecs };
}

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
