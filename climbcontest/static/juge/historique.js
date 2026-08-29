/**
 * Le journal de **tous** les scans, celui qu'on relit après coup.
 *
 * [FileDeReussites] répond à « qu'est-ce qui n'est pas encore parti ? » et se
 * vide au fur et à mesure. Ce journal-ci répond à une autre question — « qu'est-ce
 * que j'ai scanné, et est-ce arrivé ? » — et ne se vide donc jamais tout seul.
 *
 * Sans lui, un téléphone qui a tout envoyé n'a plus rien à montrer, et le juge
 * qui dit « je l'ai envoyée » ne peut rien prouver.
 *
 * ## Plus simple que côté Android, pour la même raison que la file
 *
 * `HistoriqueScans.kt` écrit une ligne par **évènement** et relit tout en
 * appliquant « la dernière ligne gagne ». Ce détour existe parce qu'un fichier
 * ne se réécrit pas de façon atomique.
 *
 * IndexedDB a des transactions : une entrée par scan, mise à jour en place.
 * Le rejeu d'évènements n'a pas d'équivalent ici.
 *
 * **Aucun nom de grimpeur n'est écrit ici.** Seulement le dossard et le tag du
 * bloc — ce que le juge a scanné. Le nom se retrouve dans le catalogue courant à
 * l'affichage. Trente jours de noms de mineurs sur vingt-cinq téléphones de
 * bénévoles ne serviraient à rien qu'on ne sache déjà faire autrement.
 */

export const ETATS = { enAttente: "en_attente", partie: "partie", refusee: "refusee" };

/** Décision d'Adrien du 29/08, la même que côté Android. */
export const RETENTION_JOURS = 30;

const JOUR_MS = 24 * 60 * 60 * 1000;

export class Historique {
  constructor(magasin) {
    this.magasin = magasin;
  }

  /** Note un scan qui vient d'être validé par le juge. */
  async noter({ ref, bib, bloc, at }) {
    await this.magasin.ajouter({ ref, bib, bloc, at, etat: ETATS.enAttente });
  }

  /** Note le sort d'un scan : le serveur a tranché. */
  async changerEtat(ref, etat, motif) {
    const entree = (await this.magasin.tout()).find((e) => e.valeur.ref === ref);
    if (!entree) return false;          // rien à mettre à jour, et on n'invente pas
    await this.magasin.remplacer(entree.cle, {
      ...entree.valeur, etat, motif: motif ?? entree.valeur.motif,
    });
    return true;
  }

  /**
   * Une réussite refusée repart sous une **nouvelle** référence.
   *
   * Le journal n'a pas à montrer deux lignes : c'est **un seul scan**, tenté
   * deux fois. L'entrée change de référence, garde sa place dans la liste et son
   * motif de refus.
   */
  async reprendre(ancienneRef, nouvelleRef) {
    const entree = (await this.magasin.tout())
      .find((e) => e.valeur.ref === ancienneRef);
    if (!entree) return false;
    await this.magasin.remplacer(entree.cle, {
      ...entree.valeur, ref: nouvelleRef, etat: ETATS.enAttente,
    });
    return true;
  }

  /** Tous les scans, du plus ancien au plus récent. */
  async tous() {
    return (await this.magasin.tout()).map((e) => e.valeur);
  }

  /** Ce qui n'a pas atteint le serveur : en attente ou refusé. */
  async nonArrives() {
    return (await this.tous()).filter((s) => s.etat !== ETATS.partie);
  }

  /**
   * Efface ce qui a plus de [RETENTION_JOURS] jours.
   *
   * Un scan dont l'heure est illisible est **gardé** : on n'efface pas ce qu'on
   * ne sait pas dater.
   *
   * ⚠️ Ne touche **jamais** à la file d'envoi. C'est ce qui rend cette purge
   * sans danger : une réussite non envoyée survit, quel que soit son âge.
   */
  async purger(maintenant = Date.now()) {
    const limite = maintenant - RETENTION_JOURS * JOUR_MS;
    const aJeter = (await this.magasin.tout())
      .filter((e) => {
        const quand = Date.parse(e.valeur.at);
        return Number.isFinite(quand) && quand < limite;
      })
      .map((e) => e.cle);
    if (aJeter.length) await this.magasin.supprimer(aJeter);
    return aJeter.length;
  }
}

/** Les six premiers caractères : de quoi lire une référence à voix haute. */
export function refCourte(ref) {
  return String(ref || "").slice(0, 6);
}
