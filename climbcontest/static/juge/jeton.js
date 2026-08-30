/**
 * Le jeton qui ouvre l'API, et rien d'autre.
 *
 * Adrien a tranché le 29/08 : « un juge n'a que l'application et il n'a pas
 * besoin de s'authentifier ». Aucun identifiant, aucun mot de passe. Le juge
 * reçoit un lien — QR affiché au mur, message dans le groupe des bénévoles —,
 * l'ouvre une fois, et n'a plus jamais rien à faire.
 *
 * ⚠️ **Le jeton voyage dans la REQUÊTE** (`?j=…`) depuis la spec 014, et le
 * fragment (`#j=…`) reste accepté pour les liens déjà distribués.
 *
 * Ce n'était pas le choix initial, et le renversement se justifie. La spec 007
 * avait retenu le fragment parce qu'il n'est pas envoyé au serveur : il n'entre
 * ni dans les journaux de Caddy, ni dans ceux de gunicorn. Mais un fragment
 * n'est pas non plus transmis à `start_url` du manifeste — donc l'application
 * **installée** démarrait sans jeton, et ne pouvait le retrouver que dans son
 * stockage local. Sur iPhone, une application de l'écran d'accueil a son propre
 * stockage, séparé de Safari : elle démarrait vide, et affichait « cette
 * application a besoin du lien fourni par l'organisateur ».
 *
 * La requête, elle, est portée par `start_url` : l'application reçoit son jeton
 * dans son adresse à CHAQUE lancement, sur toutes les plateformes, sans plus
 * dépendre d'un stockage qui peut être cloisonné ou vidé.
 *
 * Le prix est celui qu'évitait le fragment : le jeton apparaît dans les
 * journaux. Il est payé côté proxy, par un filtre qui masque le paramètre `j`.
 *
 * Ce que ça vaut, dit franchement : un lien se transfère et se photographie.
 * C'est exactement la protection de la clé dans l'APK Android — ni plus, ni
 * moins. Ça arrête un robot qui balaie Internet, pas quelqu'un qui veut fausser
 * la compétition.
 *
 * Aucun accès au DOM ni au réseau ici : ce module se teste sur Node.
 */

export const CLE_RANGEMENT = "climbcontest.jeton";

/** Le paramètre `j`, quel que soit le morceau d'adresse qui le porte. */
function jetonDe(morceau, prefixe) {
  if (!morceau) return null;
  const params = new URLSearchParams(String(morceau).replace(prefixe, ""));
  const jeton = (params.get("j") || "").trim();
  return jeton || null;
}

/**
 * Extrait le jeton d'un fragment d'adresse. `null` s'il n'y en a pas.
 *
 * Tolère `#j=abc`, `#j=abc&autre=1`, et l'absence de `#`.
 */
export function jetonDuFragment(fragment) {
  return jetonDe(fragment, /^#/);
}

/**
 * Extrait le jeton de la requête. `null` s'il n'y en a pas.
 *
 * C'est ce que porte `start_url` du manifeste depuis la spec 014, donc la
 * source la plus fraîche à chaque lancement de l'application installée.
 */
export function jetonDeLaRequete(requete) {
  return jetonDe(requete, /^\?/);
}

/**
 * Décide du jeton à utiliser, et s'il faut l'écrire.
 *
 * Trois sources, dans cet ordre, et chacune a sa raison :
 *
 *   1. **la requête** — portée par `start_url`, donc présente à chaque
 *      lancement de l'application installée. C'est elle qui rend le jeton
 *      indépendant du stockage local ;
 *   2. **le fragment** — les liens déjà distribués et les installations déjà
 *      faites. Un ancien QR ne doit pas devenir un QR mort ;
 *   3. **le stockage** — le filet, quand l'adresse ne porte rien.
 *
 * La règle qui compte n'a pas changé : **une adresse sans jeton n'efface jamais
 * un jeton rangé.** Sans elle, un lancement sur `/juge` nu viderait le jeton et
 * bloquerait le juge, sans qu'il comprenne pourquoi.
 *
 * Un jeton présent dans l'adresse l'emporte : c'est ainsi qu'on remplace une
 * clé révoquée, en renvoyant simplement un nouveau lien.
 */
export function choisirJeton(requete, fragment, jetonRange) {
  const nouveau = jetonDeLaRequete(requete) || jetonDuFragment(fragment);
  if (nouveau) return { jeton: nouveau, aEcrire: nouveau !== jetonRange };
  return { jeton: jetonRange || null, aEcrire: false };
}


/**
 * Le jeton contenu dans une adresse complete, telle que la rend un scan de QR.
 *
 * Le filet de la spec 014 : si l'application demarre sans jeton -- une
 * installation faite avant cette spec, un stockage vide -- le juge rescanne le
 * QR de l'organisateur DEPUIS l'application, au lieu de rester bloque sur un
 * message. Ca ne remplace pas le correctif : ca evite l'impasse le jour J.
 *
 * Accepte les deux formes, `?j=` et `#j=`, pour la meme raison que
 * [choisirJeton] : un ancien QR ne doit pas devenir un QR mort.
 *
 * `null` si le texte n'est pas une adresse, ou n'en porte pas.
 */
export function jetonDUneAdresse(texte) {
  if (!texte) return null;
  let adresse;
  try {
    adresse = new URL(String(texte).trim());
  } catch {
    return null;                      // un QR de grimpeur ou de bloc, pas un lien
  }
  return jetonDeLaRequete(adresse.search) || jetonDuFragment(adresse.hash);
}
