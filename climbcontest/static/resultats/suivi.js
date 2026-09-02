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
 * L'état de chaque zone POUR CE GRIMPEUR.
 *
 *   « finie »  — tous ses blocs de cette zone sont faits
 *   « reste »  — il lui en reste au moins un
 *   (absente)  — il n'a rien à y faire
 *
 * L'absence est une information à part entière : c'est elle qui permet
 * d'effacer les zones qui ne le concernent pas, au lieu de les peindre comme
 * les autres et de lui faire chercher son travail dans dix-sept cases.
 */
export function etatsDesZones(groupes) {
  const par = new Map();
  for (const bloc of tousLesBlocs(groupes)) {
    if (!bloc.zone) continue;
    const compte = par.get(bloc.zone) || { total: 0, faits: 0 };
    compte.total += 1;
    if (estFait(bloc.etat)) compte.faits += 1;
    par.set(bloc.zone, compte);
  }
  const etats = {};
  for (const [zone, compte] of par) {
    etats[zone] = compte.faits === compte.total ? FINIE : A_FAIRE;
  }
  return etats;
}

/** Combien de blocs faits sur combien, dans une zone. */
export function compteDeZone(groupes, zone) {
  const blocs = blocsDeZone(groupes, zone);
  return { total: blocs.length, faits: blocs.filter((b) => estFait(b.etat)).length };
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
