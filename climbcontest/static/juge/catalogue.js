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
export const FORMAT = 3;

/** « U13 F » → « U13 ». La même règle que `Participant.circuit`, côté serveur. */
function circuitDe(categorie) {
  if (typeof categorie !== "string") return null;
  const valeur = categorie.trim();
  if (!valeur) return null;
  const espace = valeur.lastIndexOf(" ");
  return espace === -1 ? valeur : valeur.slice(0, espace);
}

export class Catalogue {
  /**
   * ⚠️ Forme **3**. Chaque entrée est un objet, là où les formes 1 et 2
   * rangeaient des chaînes et une table de couleurs à côté :
   *
   *     participants : { "42": { n: "Dupont Lea", c: "U13" } }
   *     blocs        : { "ZJ6": { t: "ZJ6", k: "Jaune", c: ["U11","U13"] } }
   *
   * Les clés sont courtes parce que ce JSON est stocké tel quel sur le
   * téléphone, une fois par bloc et par grimpeur.
   *
   * On garde le **circuit** (« U13 »), jamais la catégorie complète
   * (« U13 F ») : la remarque de `depuisReponseServeur` sur les données de
   * mineurs entreposées sur vingt-cinq téléphones de bénévoles reste valable,
   * et le genre n'apprend rien au test d'appartenance.
   */
  constructor({ version = 0, participants = {}, blocs = {} } = {}) {
    this.version = version;
    this.parDossard = new Map(Object.entries(participants));
    this.parTag = new Map(
      Object.entries(blocs).map(([tag, bloc]) => [tag.toUpperCase(), bloc]),
    );
  }

  get estVide() {
    return this.parDossard.size === 0 && this.parTag.size === 0;
  }

  /** Le nom du grimpeur, ou `null`. C'est ce que le juge lit pour confirmer. */
  grimpeur(dossard) {
    return this.parDossard.get(String(dossard ?? "").trim())?.n ?? null;
  }

  /** Le circuit du grimpeur (« U13 »), ou null. */
  circuitDuGrimpeur(dossard) {
    return this.parDossard.get(String(dossard ?? "").trim())?.c ?? null;
  }

  /** La couleur de difficulté d'un bloc, ou null — jamais une erreur. */
  couleurDuBloc(tag) {
    if (typeof tag !== "string") return null;
    return this.parTag.get(tag.trim().toUpperCase())?.k ?? null;
  }

  /** Les circuits auxquels ce bloc appartient, ou `null` s'il est inconnu. */
  circuitsDuBloc(tag) {
    const bloc = this.parTag.get(String(tag ?? "").trim().toUpperCase());
    if (!bloc) return null;
    return Array.isArray(bloc.c) ? bloc.c : [];
  }

  bloc(tag) {
    return this.parTag.get(String(tag ?? "").trim().toUpperCase())?.t ?? null;
  }

  /**
   * Ce grimpeur a-t-il ce bloc à faire ? `true`, `false`, ou **`null`**.
   *
   * `null` veut dire « je ne sais pas », et c'est un troisième cas à part
   * entière, jamais un `false` déguisé : dossard inconnu, tag inconnu,
   * participant sans catégorie, bloc rattaché à aucun circuit. Dans tous ces
   * cas l'application **se tait**. Un avertissement qu'on ne sait pas
   * justifier apprend à ignorer les avertissements — et le seul moment où
   * celui-ci compte, c'est le jour J.
   */
  estDansLeCircuit(dossard, tag) {
    const circuit = this.circuitDuGrimpeur(dossard);
    if (!circuit) return null;
    const circuits = this.circuitsDuBloc(tag);
    if (!circuits || !circuits.length) return null;
    return circuits.includes(circuit);
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
   * Nous n'en gardons que ce qui sert au geste du juge : le nom (le seul
   * contrôle humain avant de valider), la couleur de difficulté (elle donne sa
   * teinte à l'écran), et depuis la spec 019 le **circuit** de part et d'autre
   * — c'est ce qui permet de dire « ce bloc n'est pas dans son circuit »
   * **sans réseau**, avant l'envoi.
   *
   * Ce qu'on continue de jeter : le club, l'identifiant, le numéro d'import,
   * et surtout la **catégorie complète** (« U13 F »). On n'en garde que le
   * circuit (« U13 ») : le genre n'apprend rien au test d'appartenance, et
   * n'entrepose pas une donnée de plus sur les vingt-cinq téléphones de
   * bénévoles.
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
      if (!dossard || !nom) continue;
      const entree = { n: nom };
      // Facultatif : le classeur produit des lignes sans catégorie (risque R5)
      // et l'import les garde exprès. Le grimpeur reste scannable ; il ne
      // déclenchera simplement aucun avertissement de circuit.
      const circuit = circuitDe(p.categorie);
      if (circuit) entree.c = circuit;
      participants[dossard] = entree;
    }
    const blocs = {};
    for (const b of Array.isArray(corps.blocs) ? corps.blocs : []) {
      if (!b || typeof b !== "object") continue;
      const tag = typeof b.tag === "string" ? b.tag.trim() : "";
      if (!tag) continue;
      const entree = { t: tag };
      if (typeof b.couleur === "string" && b.couleur.trim()) {
        entree.k = b.couleur.trim();
      }
      // Un bloc rattaché à aucun circuit reste scannable : c'est une anomalie
      // du classeur, pas une raison de refuser une réussite. Il ne déclenchera
      // aucun avertissement — on ne sait pas qui doit le faire.
      if (Array.isArray(b.circuits) && b.circuits.length) {
        entree.c = b.circuits.filter((c) => typeof c === "string" && c.trim())
                             .map((c) => c.trim());
      }
      blocs[tag.toUpperCase()] = entree;
    }
    return new Catalogue({ version: Number(corps.version) || 0, participants,
                           blocs });
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
