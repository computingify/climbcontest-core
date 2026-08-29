/**
 * Le catalogue local : qui est inscrit, quels blocs existent.
 *
 * C'est lui qui rend le scan instantané et **sans réseau**. Un aller-retour de
 * ~200 ms par scan devient une consultation de table de hachage.
 *
 * Reprend `Catalogue.kt` à l'identique, y compris ses tolérances : un dossard
 * est comparé tel quel après nettoyage des espaces, un tag de bloc est comparé
 * en MAJUSCULES — un QR imprimé peut porter « zj6 » quand la base dit « ZJ6 ».
 */

export class Catalogue {
  constructor({ version = 0, participants = {}, blocs = {} } = {}) {
    this.version = version;
    this.parDossard = new Map(Object.entries(participants));
    this.parTag = new Map(
      Object.entries(blocs).map(([tag, libelle]) => [tag.toUpperCase(), libelle]),
    );
  }

  get estVide() {
    return this.parDossard.size === 0 && this.parTag.size === 0;
  }

  /** Le nom du grimpeur, ou `null`. C'est ce que le juge lit pour confirmer. */
  grimpeur(dossard) {
    return this.parDossard.get(String(dossard ?? "").trim()) ?? null;
  }

  bloc(tag) {
    return this.parTag.get(String(tag ?? "").trim().toUpperCase()) ?? null;
  }

  versJson() {
    return {
      version: this.version,
      participants: Object.fromEntries(this.parDossard),
      blocs: Object.fromEntries(this.parTag),
    };
  }

  /** Relit un catalogue rangé. Un contenu abîmé donne un catalogue VIDE. */
  static depuisJson(donnees) {
    if (!donnees || typeof donnees !== "object") return new Catalogue();
    const version = Number(donnees.version) || 0;
    const participants = donnees.participants && typeof donnees.participants === "object"
      ? donnees.participants : {};
    const blocs = donnees.blocs && typeof donnees.blocs === "object" ? donnees.blocs : {};
    return new Catalogue({ version, participants, blocs });
  }
}

/** Le filet : au-delà, on rafraîchit même si rien ne l'a demandé. */
export const PERIODE_MS = 5 * 60 * 1000;

/**
 * Faut-il retélécharger le catalogue ?
 *
 * Quatre raisons, et la troisième est celle qui compte le jour J : un QR
 * inconnu veut presque toujours dire « ce participant a été inscrit il y a dix
 * minutes ». Le juge n'a rien à faire pour que ça se répare.
 */
export function doitRafraichir({ estVide, qrInconnu = false, versionServeur = null,
                                 versionLocale = 0, maintenantMs, dernierMs }) {
  if (estVide) return true;
  if (qrInconnu) return true;
  if (versionServeur !== null && versionServeur !== versionLocale) return true;
  return maintenantMs - dernierMs >= PERIODE_MS;
}
