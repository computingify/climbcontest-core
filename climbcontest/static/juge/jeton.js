/**
 * Le jeton qui ouvre l'API, et rien d'autre.
 *
 * Adrien a tranché le 29/08 : « un juge n'a que l'application et il n'a pas
 * besoin de s'authentifier ». Aucun identifiant, aucun mot de passe. Le juge
 * reçoit un lien — QR affiché au mur, message dans le groupe des bénévoles —,
 * l'ouvre une fois, et n'a plus jamais rien à faire.
 *
 * ⚠️ **Le jeton voyage dans le FRAGMENT** (`#j=…`), jamais dans la requête
 * (`?j=…`). Un fragment n'est pas envoyé au serveur : il n'entre donc ni dans
 * les journaux d'accès de Caddy, ni dans ceux de gunicorn, ni dans un en-tête
 * `Referer` vers un tiers. Une adresse en `?j=` laisserait le secret en clair
 * dans trois fichiers de logs, sur trois machines.
 *
 * Ce que ça vaut, dit franchement : un lien se transfère et se photographie.
 * C'est exactement la protection de la clé dans l'APK Android — ni plus, ni
 * moins. Ça arrête un robot qui balaie Internet, pas quelqu'un qui veut fausser
 * la compétition.
 *
 * Aucun accès au DOM ni au réseau ici : ce module se teste sur Node.
 */

export const CLE_RANGEMENT = "climbcontest.jeton";

/**
 * Extrait le jeton d'un fragment d'adresse. `null` s'il n'y en a pas.
 *
 * Tolère `#j=abc`, `#j=abc&autre=1`, et l'absence de `#`.
 */
export function jetonDuFragment(fragment) {
  if (!fragment) return null;
  const params = new URLSearchParams(String(fragment).replace(/^#/, ""));
  const jeton = (params.get("j") || "").trim();
  return jeton || null;
}

/**
 * Décide du jeton à utiliser, et s'il faut l'écrire.
 *
 * La règle qui compte : **un fragment vide n'efface jamais un jeton rangé.**
 * Sans elle, ouvrir la PWA depuis l'écran d'accueil — donc sans fragment —
 * effacerait le jeton au premier lancement de la journée, et le juge se
 * retrouverait bloqué sans comprendre pourquoi.
 *
 * Un fragment présent l'emporte : c'est ainsi qu'on remplace un jeton révoqué,
 * en renvoyant simplement un nouveau lien.
 */
export function choisirJeton(fragment, jetonRange) {
  const nouveau = jetonDuFragment(fragment);
  if (nouveau) return { jeton: nouveau, aEcrire: nouveau !== jetonRange };
  return { jeton: jetonRange || null, aEcrire: false };
}
