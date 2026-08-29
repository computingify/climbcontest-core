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

/**
 * La forme sous laquelle on range le catalogue.
 *
 * ⚠️ Elle est **versionnée**, et ce n'est pas de la coquetterie. Une PWA se met
 * à jour toute seule : un téléphone peut donc recevoir un nouveau code tout en
 * gardant un catalogue rangé par l'ancien. Si la forme a changé entre les deux,
 * ce catalogue est illisible — et comme le serveur répond `304` tant que la
 * version ne bouge pas, il ne serait **jamais** remplacé. Le juge scannerait
 * dans le vide jusqu'à la prochaine compétition.
 *
 * Le marqueur force un rechargement complet quand la forme change. Il a été
 * ajouté après être tombé exactement dans ce piège en développant.
 */
export const FORMAT = 2;

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
      format: FORMAT,
      version: this.version,
      participants: Object.fromEntries(this.parDossard),
      blocs: Object.fromEntries(this.parTag),
    };
  }

  /** Relit un catalogue **rangé par nous**. Un contenu abîmé donne un vide. */
  static depuisJson(donnees) {
    if (!donnees || typeof donnees !== "object") return new Catalogue();
    // Rangé par une version antérieure du code : on ne sait pas le lire, et un
    // catalogue vide déclenche un rechargement complet. Mieux vaut retélécharger
    // 15 ko que scanner dans le vide.
    if (donnees.format !== FORMAT) return new Catalogue();
    const version = Number(donnees.version) || 0;
    const estUnDictionnaire = (v) =>
      v && typeof v === "object" && !Array.isArray(v);
    return new Catalogue({
      version,
      participants: estUnDictionnaire(donnees.participants) ? donnees.participants : {},
      blocs: estUnDictionnaire(donnees.blocs) ? donnees.blocs : {},
    });
  }

  /**
   * Lit la réponse du serveur, qui n'a **pas** la même forme que ce qu'on range.
   *
   * ⚠️ Le serveur envoie des TABLEAUX d'objets :
   *
   * ```json
   * { "version": 1,
   *   "participants": [{ "id": 1, "dossard": 1, "nom": "Dupont Lea", ... }],
   *   "blocs":        [{ "id": 1, "tag": "ZJ1", "couleur": "Jaune", ... }] }
   * ```
   *
   * Nous n'en gardons que deux tables de correspondance : dossard → nom et
   * tag → tag. Le reste — club, catégorie, couleur, circuits — ne sert pas au
   * geste du juge, et ne pas le garder évite d'entreposer des données de
   * mineurs sur vingt-cinq téléphones de bénévoles.
   *
   * J'avais d'abord écrit ce module en supposant que le serveur envoyait déjà
   * des dictionnaires. Résultat : le catalogue local ne correspondait jamais, et
   * **chaque scan repassait par le réseau** — exactement ce que cette
   * itération prétendait supprimer. Mes tests ne l'ont pas vu : ils vérifiaient
   * ma classe contre ma propre supposition. Seul un appel au vrai serveur l'a
   * montré.
   */
  static depuisReponseServeur(corps) {
    if (!corps || typeof corps !== "object") return new Catalogue();
    const participants = {};
    for (const p of Array.isArray(corps.participants) ? corps.participants : []) {
      if (!p || typeof p !== "object") continue;
      const dossard = p.dossard === null || p.dossard === undefined
        ? null : String(p.dossard).trim();
      const nom = typeof p.nom === "string" ? p.nom.trim() : "";
      // Un participant SANS dossard existe : il est inscrit, il n'a pas encore
      // son papier. Il n'a rien à faire dans une table indexée par dossard.
      if (dossard && nom) participants[dossard] = nom;
    }
    const blocs = {};
    for (const b of Array.isArray(corps.blocs) ? corps.blocs : []) {
      if (!b || typeof b !== "object") continue;
      const tag = typeof b.tag === "string" ? b.tag.trim() : "";
      if (tag) blocs[tag.toUpperCase()] = tag;
    }
    return new Catalogue({ version: Number(corps.version) || 0, participants, blocs });
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
