/**
 * Vide la file vers le serveur, sans jamais rien perdre.
 *
 * Ne contient ni minuteur ni accès au DOM : `tenter()` est appelée par
 * quelqu'un d'autre. C'est ce qui la rend testable de bout en bout sur Node,
 * avec une API factice — exactement comme `Expediteur.kt` côté Android.
 *
 * **L'invariant** : une réussite ne quitte la file que si le serveur a
 * explicitement statué sur elle.
 */
import { LOT_MAX, tailleLot } from "./politique.js";

export class Expediteur {
  constructor(file, api, { identite = () => null } = {}) {
    this.file = file;
    this.api = api;
    this.identite = identite;
    this.echecsConsecutifs = 0;
  }

  /** Tente un envoi. Rend `null` s'il n'y avait rien à envoyer. */
  async tenter() {
    const enAttente = await this.file.nombreEnAttente();
    if (enAttente === 0) return null;

    const lot = await this.file.prochainLot(tailleLot(enAttente));
    const resultat = await this.api.envoyerLot(
      lot.map((e) => e.valeur), this.identite(),
    );

    if (!resultat.ok) {
      this.echecsConsecutifs++;
      return {
        envoyees: 0, refusees: [], aReussi: false,
        restantes: await this.file.nombreEnAttente(),
        misesDeCote: await this.file.nombreRefusees(),
        message: resultat.message, code: resultat.code,
      };
    }

    this.echecsConsecutifs = 0;

    // On met de côté AVANT d'acquitter. Une coupure entre les deux laisse la
    // réussite dans la file principale : elle repartira et sera refusée à
    // nouveau, ce qui est sans gravité. L'ordre inverse la perdrait.
    if (resultat.refusees.length) {
      const parRef = new Map(lot.map((e) => [e.valeur.ref, e.valeur]));
      for (const refus of resultat.refusees) {
        const reussite = parRef.get(refus.ref);
        if (reussite) await this.file.mettreDeCote(reussite, refus.message);
      }
    }
    await this.file.acquitter(resultat.acquittees);

    return {
      envoyees: resultat.acquittees.size - resultat.refusees.length,
      refusees: resultat.refusees,
      acquittees: resultat.acquittees,
      aReussi: true,
      restantes: await this.file.nombreEnAttente(),
      misesDeCote: await this.file.nombreRefusees(),
      catalogueVersion: resultat.catalogueVersion ?? null,
    };
  }

  /** Le geste du juge une fois l'organisateur passé : renvoyer les refusées. */
  async renvoyerLesRefusees(nouvelleRef) {
    return this.file.renvoyerLesRefusees(nouvelleRef);
  }
}

export { LOT_MAX };
