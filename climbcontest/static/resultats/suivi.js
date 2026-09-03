/**
 * La fiche du grimpeur en direct — spec 026, la logique sans le DOM.
 *
 * Extrait du gabarit pour la même raison que `podium.js` : ce sont ces
 * fonctions qui décident de ce qu'un parent lit sur son téléphone, et une
 * logique qu'aucun test n'exécute est une logique dont on découvre les défauts
 * le jour de la compétition.
 *
 *   node --test "tests/js/*.test.mjs"
 */

/** Les trois états d'un bloc, tels que le serveur les envoie. */
export const GRIMPE = "grimpe";
export const CREDITE = "credite";
export const RESTE = "reste";

/** Les deux états d'une zone, pour ce grimpeur-là. */
export const FINIE = "finie";
export const A_FAIRE = "reste";

/** Un bloc compte comme fait s'il est grimpé OU crédité par la cascade.
 *
 * ⚠️ Les deux comptent pour le classement, et donc pour « cette zone est
 * terminée ». Ils ne se PEIGNENT pas pareil — plein contre hachuré — mais ils
 * pèsent pareil. Confondre les deux plans, c'est afficher « il te reste un
 * bloc » sur une zone où le grimpeur n'a plus rien à faire.
 */
export function estFait(etat) {
  return etat === GRIMPE || etat === CREDITE;
}

/** Tous les blocs de la fiche, à plat, dans l'ordre des groupes. */
export function tousLesBlocs(groupes) {
  const blocs = [];
  for (const groupe of groupes || []) {
    for (const bloc of groupe.blocs || []) blocs.push(bloc);
  }
  return blocs;
}

/** Les blocs du circuit qui se trouvent dans une zone donnée. */
export function blocsDeZone(groupes, zone) {
  return tousLesBlocs(groupes).filter((b) => b.zone === zone);
}

/**
 * Ce que le grimpeur a fait DANS CHAQUE ZONE : `{ M: { total, faits,
 * grimpes, credites }, ... }`.
 *
 * ⚠️ C'EST LA SEULE ADDITION DE CE FICHIER, et c'est voulu.
 *
 * Trois choses affichées ailleurs disent le même nombre : l'anneau vert « zone
 * terminée » sur le plan, le compteur du panneau (« 1 sur 2 ») et le compteur
 * posé sur la zone (« 1/2 », spec 036). Écrites en trois boucles, elles
 * finiraient par diverger — et la divergence serait silencieuse : le plan
 * afficherait « 3/4 » sur une zone cerclée de vert, ce qui ne se lit pas
 * comme « il y a un bloc crédité » mais comme « la page est cassée ». Elles
 * dérivent donc toutes d'ici.
 *
 * Une zone où le grimpeur n'a AUCUN bloc de son circuit est **absente** de la
 * table, elle ne vaut pas `{0, 0}` : l'absence est ce qui permet d'effacer les
 * zones qui ne le concernent pas, et ce qui empêche un « 0/0 » de se poser sur
 * la moitié du plan.
 *
 * `grimpes` et `credites` ne sont affichés nulle part aujourd'hui. Ils ne
 * coûtent rien à compter et ils sont la seule façon honnête de répondre, plus
 * tard, à « combien de ces blocs a-t-il vraiment grimpés ».
 */
export function comptesDesZones(groupes) {
  const comptes = {};
  for (const bloc of tousLesBlocs(groupes)) {
    if (!bloc.zone) continue;
    const compte = comptes[bloc.zone]
      || (comptes[bloc.zone] = { total: 0, faits: 0, grimpes: 0, credites: 0 });
    compte.total += 1;
    if (bloc.etat === GRIMPE) compte.grimpes += 1;
    if (bloc.etat === CREDITE) compte.credites += 1;
    if (estFait(bloc.etat)) compte.faits += 1;
  }
  return comptes;
}

/**
 * L'état de chaque zone POUR CE GRIMPEUR.
 *
 *   « finie »  — tous ses blocs de cette zone sont faits
 *   « reste »  — il lui en reste au moins un
 *   (absente)  — il n'a rien à y faire
 *
 * L'absence est une information à part entière : c'est elle qui permet
 * d'effacer les zones qui ne le concernent pas, au lieu de les peindre comme
 * les autres et de lui faire chercher son travail dans dix-sept cases.
 *
 * ⚠️ Déduit de `comptesDesZones`, et jamais recompté : c'est ce qui rend
 * impossible qu'une zone soit cerclée de vert sous un compteur qui dit « 3/4 ».
 */
export function etatsDesZones(groupes) {
  const etats = {};
  for (const [zone, compte] of Object.entries(comptesDesZones(groupes))) {
    etats[zone] = compte.faits === compte.total ? FINIE : A_FAIRE;
  }
  return etats;
}

/** Combien de blocs faits sur combien, dans une zone.
 *
 * Une zone sans bloc du circuit rend un compte À ZÉRO plutôt que rien : c'est
 * ce dont le panneau a besoin pour écrire « aucun bloc de ton circuit dans
 * cette zone ». Le PLAN, lui, veut l'absence, et la lit dans
 * `comptesDesZones`. */
export function compteDeZone(groupes, zone) {
  return comptesDesZones(groupes)[zone]
    || { total: 0, faits: 0, grimpes: 0, credites: 0 };
}

/**
 * Le compteur d'une zone, tel qu'il s'écrit sur le plan : « 1/4 ».
 *
 * La notation n'est pas inventée ici : la fiche l'écrit déjà en tête de chaque
 * groupe de couleur. Le plan reprend celle de l'écran qui l'ouvre.
 *
 * Rend `""` quand il n'y a rien à dire — pas de compte, ou aucun bloc du
 * circuit dans cette zone. « 0/4 » se dit (le zéro est une information),
 * « 0/0 » ne se dit pas (l'absence en est une autre).
 */
export function libelleCompte(compte) {
  if (!compte || !compte.total) return "";
  return compte.faits + "/" + compte.total;
}

/**
 * Les classes à poser sur une zone du plan.
 *
 * La DÉCISION est ici, pure et testée ; la pose est une boucle de cinq lignes
 * dans `plan.js`. C'est ce qui permet de vérifier la hiérarchie d'affichage
 * sans navigateur.
 *
 * ⚠️ La zone visée l'emporte sur « terminée ». Arriver depuis un bloc doit
 * rester le geste le plus lisible : c'est celui qu'on vient de faire.
 */
export function classesDeZone(zone, etats, visee) {
  const classes = ["z-" + (etats[zone] || "rien")];
  if (zone && zone === visee) classes.push("visee");
  return classes;
}

// --- L'adresse, et donc le retour arrière -----------------------------------
//
// ⚠️ Le DIÈSE, jamais un paramètre. Il ne part pas au serveur : la racine est
// mise en cache 5 s par Caddy, et `?g=42` créerait une entrée de cache par
// grimpeur et par zone pour un HTML rigoureusement identique. Il laisse aussi
// `?mur`, `?sombre` et la route de rejeu d'archive intacts.

/**
 * « #g=42&z=M » → { grimpeur: 42, zone: "M", mur: true }.
 *
 * ⚠️ `mur` est PORTÉ PAR L'ADRESSE, et pas par une variable de la page. Il l'a
 * été, et ça créait une course : la page posait « je suis au mur » avant
 * d'écrire le dièse, et tout rendu qui tombait entre les deux montrait le mur
 * sans zone visée. L'historique est la seule source de vérité — un drapeau
 * gardé à côté finit toujours par le contredire.
 *
 * `#g=42&z=` — un `z` vide — c'est le mur SANS zone choisie : ce qu'ouvre le
 * bouton « Le mur » de la fiche.
 *
 * Tolérant : ce qu'on ne comprend pas devient `null`, jamais une exception.
 */
export function lireDiese(diese) {
  const vide = { grimpeur: null, zone: null, mur: false };
  if (typeof diese !== "string") return vide;
  const params = new URLSearchParams(diese.replace(/^#/, ""));

  const brut = params.get("g");
  const grimpeur = /^\d+$/.test(brut || "") ? Number(brut) : null;
  if (grimpeur === null) return vide;

  // Une zone sans grimpeur n'a pas de sens : le mur s'ouvre DEPUIS une fiche.
  const zone = params.get("z");
  return { grimpeur, zone: zone || null, mur: params.has("z") };
}

/** L'inverse. Rend "" quand il n'y a rien à écrire, pour que la page puisse
 *  nettoyer l'adresse plutôt que d'y laisser un dièse vide. */
export function ecrireDiese({ grimpeur = null, zone = null, mur = false } = {}) {
  if (grimpeur === null || grimpeur === undefined) return "";
  if (zone) return "#g=" + grimpeur + "&z=" + zone;
  return "#g=" + grimpeur + (mur ? "&z=" : "");
}
