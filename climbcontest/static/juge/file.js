/**
 * La file des réussites qui n'ont pas encore atteint le serveur.
 *
 * C'est la pièce qui change tout pour le juge : « Validé » s'affiche quand la
 * réussite est **sur le téléphone**, plus quand elle est sur le serveur. Le
 * stockage du téléphone est bien plus fiable qu'un wifi de salle avec 125
 * personnes dessus.
 *
 * **L'invariant, et il n'y en a qu'un qui compte : une réussite ne quitte la
 * file que si le serveur a explicitement statué sur elle.** Réseau coupé,
 * réponse partielle, 401, corps illisible — dans tous ces cas la file reste
 * intacte et l'envoi repartira. Réessayer est gratuit : le serveur est
 * idempotent sur le couple (grimpeur, bloc).
 *
 * ## Pourquoi c'est plus simple que côté Android
 *
 * `FileDeReussites.kt` tient un **second fichier d'acquittements**, et compacte
 * quand tout est acquitté. Ce détour existe parce qu'un fichier ne se réécrit
 * pas de façon atomique : une coupure au milieu perdrait des réussites déjà
 * validées.
 *
 * IndexedDB, lui, a des **transactions**. Supprimer les entrées acquittées est
 * atomique : soit toutes partent, soit aucune. Le fichier d'acquittements et le
 * compactage n'ont donc pas d'équivalent ici — ils répondaient à une contrainte
 * qui n'existe pas.
 *
 * Ce module ne connaît pas IndexedDB : il travaille sur un « magasin » abstrait.
 * C'est ce qui le rend testable sur Node avec un magasin en mémoire, sans
 * navigateur — le même partage que côté Android, où la logique se teste sans
 * émulateur.
 */

export class FileDeReussites {
  /**
   * @param magasin          les réussites en attente, clés auto-incrémentées
   * @param magasinRefusees  celles que le serveur a rejetées
   */
  constructor(magasin, magasinRefusees) {
    this.magasin = magasin;
    this.refusees_ = magasinRefusees;
  }

  /** Dépose une réussite. Elle y reste tant que le serveur n'a pas statué. */
  async ajouter(reussite) {
    return this.magasin.ajouter(reussite);
  }

  /** Ce qui n'est pas encore parti, dans l'ordre où le juge a validé. */
  async enAttente() {
    return this.magasin.tout();
  }

  async nombreEnAttente() {
    return (await this.magasin.tout()).length;
  }

  /** Le prochain lot, au plus [taille] éléments. */
  async prochainLot(taille) {
    return (await this.magasin.tout()).slice(0, Math.max(0, taille));
  }

  /**
   * Retire de la file les `ref` sur lesquelles le serveur a statué.
   *
   * « Statué » veut dire *enregistrée*, *déjà connue* ou *refusée* — les trois
   * sont définitifs. Une `ref` sur laquelle le serveur n'a **rien** dit n'est
   * pas passée ici : elle reste en file et repartira. Le défaut est de garder.
   */
  async acquitter(refs) {
    const voulues = refs instanceof Set ? refs : new Set(refs);
    if (!voulues.size) return 0;
    const aRetirer = (await this.magasin.tout())
      .filter((e) => voulues.has(e.valeur.ref))
      .map((e) => e.cle);
    if (aRetirer.length) await this.magasin.supprimer(aRetirer);
    return aRetirer.length;
  }

  /**
   * Met de côté ce que le serveur a refusé, **avant** de l'acquitter.
   *
   * L'ordre compte, et c'est le même que côté Android : on écrit d'abord dans
   * les refusées, on acquitte ensuite. Une coupure entre les deux laisse la
   * réussite dans la file principale — elle repartira, et sera refusée à
   * nouveau. C'est sans gravité. L'ordre inverse la perdrait.
   */
  async mettreDeCote(reussite, motif) {
    await this.refusees_.ajouter({ ...reussite, motif });
  }

  async refusees() {
    return (await this.refusees_.tout()).map((e) => e.valeur);
  }

  async nombreRefusees() {
    return (await this.refusees_.tout()).length;
  }

  /**
   * Remet les refusées dans la file, pour un nouvel essai.
   *
   * Le geste du juge après qu'un organisateur a ajouté le participant
   * manquant — le cas de loin le plus fréquent : « ce dossard n'existe pas
   * ENCORE ».
   *
   * ⚠️ Chacune repart sous une **nouvelle référence**. Côté Android c'était
   * obligatoire (l'ancienne figurait dans les acquittements). Ici la raison est
   * différente mais tient toujours : le serveur garde `ref_client`, et deux
   * tentatives distinctes doivent être distinguables dans la console.
   */
  async renvoyerLesRefusees(nouvelleRef) {
    const aRenvoyer = await this.refusees();
    if (!aRenvoyer.length) return [];
    const reprises = [];
    for (const refusee of aRenvoyer) {
      const { motif, ...reussite } = refusee;
      const neuve = nouvelleRef();
      await this.magasin.ajouter({ ...reussite, ref: neuve });
      reprises.push({ ancienne: refusee.ref, nouvelle: neuve });
    }
    await this.refusees_.vider();
    return reprises;
  }
}

/**
 * Un magasin en mémoire, pour les tests.
 *
 * Il vit ici et pas dans les tests : c'est la **définition** de ce qu'un
 * magasin doit faire. L'adaptateur IndexedDB doit se comporter comme lui, et
 * les deux se lisent côte à côte.
 */
export class MagasinMemoire {
  constructor() {
    this.entrees = new Map();
    this.prochaineCle = 1;
  }

  async ajouter(valeur) {
    const cle = this.prochaineCle++;
    this.entrees.set(cle, valeur);
    return cle;
  }

  async tout() {
    return [...this.entrees.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([cle, valeur]) => ({ cle, valeur }));
  }

  async remplacer(cle, valeur) {
    this.entrees.set(cle, valeur);
  }

  async supprimer(cles) {
    for (const cle of cles) this.entrees.delete(cle);
  }

  async vider() {
    this.entrees.clear();
  }
}
