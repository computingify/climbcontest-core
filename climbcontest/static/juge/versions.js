/**
 * « Ce que j'ai vaut-il ce que le serveur a ? » — spec 030.
 *
 * Un module de décision, pas d'affichage : il ne touche ni au DOM ni au
 * stockage, donc il se teste sur Node sans navigateur. Même partage que
 * [politique.js] ou [catalogue.js] — `juge.js` ne fait que brancher des boutons.
 *
 * ⚠️ **Trois états, jamais deux.** `INCONNU` n'est pas un `A_JOUR` prudent :
 * c'est « je n'ai pas joint le serveur, je ne sais pas ». Un téléphone démarré
 * en mode avion est dans ce cas, et lui afficher « à jour » serait exactement
 * le mensonge que cette spec existe pour supprimer. La même règle que
 * `Catalogue.estDansLeCircuit`, où `null` est un troisième cas à part entière.
 *
 * ⚠️ **On compare par ÉGALITÉ, jamais par ordre.** Un numéro de catalogue
 * identifie un couple *(édition, état de son catalogue)*. Il saute — et il
 * saute pour toutes les éditions à la fois quand le plan du mur change. « Plus
 * grand » ne veut rien dire ici ; c'est d'ailleurs pour ça que le serveur
 * refuse un `304` à un client qui annonce un numéro supérieur au sien : il ne
 * vient pas du futur, il vient d'ailleurs.
 */

export const A_JOUR = "a-jour";
export const EN_RETARD = "en-retard";
export const INCONNU = "inconnu";

/**
 * @param local    ce que ce téléphone détient (numéro de catalogue, ou version)
 * @param serveur  ce que le serveur a annoncé, ou `null` si on ne l'a jamais joint
 */
export function verdict(local, serveur) {
  if (serveur === null || serveur === undefined || serveur === "") return INCONNU;
  if (local === null || local === undefined || local === "") return INCONNU;
  return local === serveur ? A_JOUR : EN_RETARD;
}

/**
 * « à l'instant », « il y a 12 min », « il y a 1 h 12 ».
 *
 * Rien de plus fin que la minute : à cette échelle, « il y a 12 s » et « à
 * l'instant » disent la même chose, et la seconde formulation ne demande pas
 * de lire un chiffre.
 */
export function ilYA(quandMs, maintenantMs = Date.now()) {
  if (!quandMs) return null;
  const secondes = Math.max(0, Math.round((maintenantMs - quandMs) / 1000));
  if (secondes < 60) return "à l'instant";
  const minutes = Math.floor(secondes / 60);
  if (minutes < 60) return `il y a ${minutes} min`;
  const heures = Math.floor(minutes / 60);
  return `il y a ${heures} h ${String(minutes % 60).padStart(2, "0")}`;
}

/**
 * Les deux lignes grises sous le numéro de catalogue.
 *
 * ⚠️ « Reçu » et « vérifié » sont deux choses différentes, et les confondre
 * ferait paraître décroché un téléphone parfaitement sain : un catalogue reçu
 * il y a deux heures et vérifié il y a deux minutes est le cas NORMAL — le
 * catalogue ne bouge presque jamais pendant une compétition, et le serveur
 * répond `304`. On ne mentionne « vérifié » que lorsqu'il apporte quelque
 * chose, c'est-à-dire quand la vérification est nettement postérieure.
 */
export function resumeDuCatalogue({ grimpeurs = 0, blocs = 0, recuMs = 0,
                                    vuMs = 0, maintenantMs = Date.now() } = {}) {
  const lignes = [];
  if (grimpeurs || blocs) {
    lignes.push(`${grimpeurs} grimpeur${grimpeurs > 1 ? "s" : ""} · ` +
                `${blocs} bloc${blocs > 1 ? "s" : ""}`);
  }
  const recu = ilYA(recuMs, maintenantMs);
  const vu = ilYA(vuMs, maintenantMs);
  if (recu && vu && vuMs - recuMs > 60_000) {
    lignes.push(`Reçu ${recu} · vérifié ${vu}`);
  } else if (recu) {
    lignes.push(`Reçu ${recu}`);
  }
  return lignes;
}
