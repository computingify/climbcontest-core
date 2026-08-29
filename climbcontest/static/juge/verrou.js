/**
 * Un seul onglet envoie à la fois.
 *
 * Le problème est réel et propre au web : un juge peut avoir la PWA installée
 * **et** un onglet Safari ouvert sur la même adresse. Les deux partagent le même
 * IndexedDB. Sans verrou, les deux liraient le même lot, l'enverraient tous les
 * deux, et le second supprimerait des entrées que le premier venait de traiter.
 *
 * Le serveur absorberait les doublons — il est idempotent — mais la file, elle,
 * se croirait vidée pendant qu'une réussite y reste. C'est exactement le genre
 * de perte silencieuse que toute cette architecture cherche à rendre impossible.
 *
 * **Un bail, pas un verrou** : le détenteur peut mourir sans le rendre — onglet
 * fermé, téléphone en veille, navigateur tué par iOS. Un verrou éternel bloquerait
 * les envois jusqu'au prochain redémarrage. Le bail se reprend donc après
 * [DUREE_MS] sans renouvellement. Le même raisonnement que le verrou de schéma
 * côté serveur, et pour la même raison.
 *
 * Ce module est pur : on lui donne l'heure et le bail actuel, il décide.
 */

/** Au-delà, le bail est considéré abandonné. */
export const DUREE_MS = 30_000;

/**
 * Peut-on prendre ou garder le bail ?
 *
 * @param bail     `{proprietaire, jusqua}` ou `null`
 * @param moi      identifiant de cet onglet
 * @param maintenant  horloge, en millisecondes
 */
export function peutPrendre(bail, moi, maintenant) {
  if (!bail || !bail.proprietaire) return true;
  // Le nôtre : on le renouvelle, personne d'autre n'a à être consulté.
  if (bail.proprietaire === moi) return true;
  // Celui d'un autre, périmé : il est mort sans le rendre.
  return !(typeof bail.jusqua === "number") || bail.jusqua <= maintenant;
}

/** Le bail à écrire quand on le prend. */
export function bailNeuf(moi, maintenant) {
  return { proprietaire: moi, jusqua: maintenant + DUREE_MS };
}

/** Un identifiant d'onglet, le temps de la session. */
export function identifiantDOnglet() {
  if (globalThis.crypto && globalThis.crypto.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `onglet-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
