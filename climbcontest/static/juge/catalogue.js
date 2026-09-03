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
export const FORMAT = 4;

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
   * ⚠️ Forme **4**. Chaque entrée est un objet, là où les formes 1 et 2
   * rangeaient des chaînes et une table de couleurs à côté :
   *
   *     participants : { "42": { n: "Dupont Lea", c: "U13 F" } }
   *     blocs        : { "ZJ6": { t: "ZJ6", k: "Jaune", c: ["U11","U13"] } }
   *
   * Les clés sont courtes parce que ce JSON est stocké tel quel sur le
   * téléphone, une fois par bloc et par grimpeur.
   *
   * ⚠️ `c` porte désormais la **catégorie complète** (« U13 F »), là où la
   * forme 3 ne gardait que le circuit (« U13 »). Le circuit s'en **déduit**
   * par `circuitDe()` — la même règle que `Participant.circuit` côté serveur —
   * donc la quantité de données stockées ne bouge pas ; ce qu'elles
   * contiennent, si.
   *
   * La forme 3 se justifiait par la minimisation : des données de mineurs
   * vivent sur vingt-cinq téléphones de bénévoles, et le genre n'apprenait
   * rien au test d'appartenance au circuit. Il apprend maintenant quelque
   * chose : Adrien a demandé (03/09, spec 033 R10) que la **catégorie**
   * s'affiche sur la carte du grimpeur, pour que le juge vérifie d'un coup
   * d'œil qu'il scanne le bon. Elle voyageait déjà sur le réseau — la route
   * sert `participant.to_dict()` en entier — elle n'était pas conservée.
   *
   * Ce commentaire dit la raison ET la date pour que personne ne « corrige »
   * une régression en revenant à la forme 3.
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

  /** La catégorie du grimpeur (« U13 F »), ou null.
   *
   *  C'est ce que le juge lit à droite de la carte : deux grimpeurs du même
   *  circuit peuvent porter des dossards voisins, et la catégorie est ce qui
   *  les distingue sur le papier posé devant lui. */
  categorie(dossard) {
    return this.parDossard.get(String(dossard ?? "").trim())?.c ?? null;
  }

  /** Le circuit du grimpeur (« U13 »), ou null.
   *
   *  DÉDUIT de la catégorie, jamais rangé à côté : deux champs qui disent la
   *  même chose finissent par se contredire. */
  circuitDuGrimpeur(dossard) {
    return circuitDe(this.categorie(dossard));
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
   * Ce qu'on continue de jeter : le club, l'identifiant, le numéro d'import.
   * La **catégorie**, elle, est gardée depuis la forme 4 — le juge doit la
   * lire pour vérifier qu'il scanne le bon grimpeur (spec 033, R10) — et le
   * circuit s'en déduit au lieu d'être rangé à côté.
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
      // déclenchera simplement aucun avertissement de circuit, et rien ne
      // s'affichera à droite de sa carte.
      const categorie = typeof p.categorie === "string" ? p.categorie.trim() : "";
      if (categorie) entree.c = categorie;
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
