/**
 * Quand faut-il envoyer ? Décision pure, sans réseau ni horloge implicite.
 *
 * Reprise à l'identique de `PolitiqueEnvoi` côté Android — **les mêmes
 * constantes**, délibérément. Deux clients qui envoient au même rythme font une
 * charge prévisible ; deux clients qui divergent font une charge qu'on ne sait
 * plus mesurer, et les chiffres de la spec 003 (10 800 → 817 requêtes) ne
 * vaudraient plus rien.
 */

/** Au-delà, on part sans attendre. Cinq validations, c'est ~30 s de juge. */
export const LOT_PLEIN = 5;

/** Et si le lot ne se remplit pas, on part quand même au bout de ce délai. */
export const DELAI_MS = 10_000;

/** Le serveur refuse au-delà ; on reste en dessous. */
export const LOT_MAX = 50;

/** Premier délai d'attente après un échec, puis doublé à chaque fois. */
export const RETRAIT_INITIAL_MS = 2_000;

/** Plafond du retrait. Sans lui, un backend éteint une heure ferait attendre
 *  le premier renvoi une demi-heure après son retour. */
export const RETRAIT_MAX_MS = 60_000;

/** Combien de temps attendre après `echecs` échecs consécutifs. */
export function attenteApresEchec(echecs) {
  if (echecs <= 0) return 0;
  let attente = RETRAIT_INITIAL_MS;
  for (let i = 1; i < echecs; i++) attente = Math.min(attente * 2, RETRAIT_MAX_MS);
  return Math.min(attente, RETRAIT_MAX_MS);
}

/**
 * Faut-il tenter un envoi maintenant ?
 *
 * `forcer` correspond au bouton « tout envoyer maintenant » : il ignore le lot
 * et le délai, mais **pas** le retrait — sinon appuyer en boucle sur un serveur
 * éteint noierait le téléphone de requêtes.
 */
export function doitEnvoyer({ enAttente, depuisDernierEnvoiMs, echecs, forcer = false }) {
  if (enAttente <= 0) return false;
  if (depuisDernierEnvoiMs < attenteApresEchec(echecs)) return false;
  if (forcer) return true;
  return enAttente >= LOT_PLEIN || depuisDernierEnvoiMs >= DELAI_MS;
}

/** Taille du prochain lot. */
export function tailleLot(enAttente) {
  return Math.min(enAttente, LOT_MAX);
}
