/**
 * Le dialogue HTTP avec le backend, et rien d'autre.
 *
 * Même découpage que côté Android (`ClimbContestApi.kt`), et pour la même
 * raison : ce module ne touche ni au DOM ni au stockage, donc il se teste avec
 * un `fetch` factice, sans navigateur.
 *
 * ⚠️ **La PWA parle exactement le même protocole que l'application Android.**
 * Aucune route n'a été ajoutée pour elle. Deux clients, un seul contrat — et les
 * tests de contrat existants côté serveur couvrent donc les deux.
 */

export const ENTETE_CLE = "X-Api-Key";

/**
 * Ce que le téléphone dit de lui en téléchargeant le catalogue (spec 030).
 *
 * ⚠️ Des **en-têtes**, et non des paramètres d'URL. Le nom d'un poste — « Mur
 * jaune » — n'a rien à faire dans le journal d'accès du proxy : la spec 014 a
 * justement dû y poser un filtre pour en retirer le jeton du juge. Un en-tête
 * n'y est pas journalisé.
 *
 * `encodeURIComponent` parce qu'un en-tête HTTP ne transporte pas sûrement les
 * accents, et que « Entrée » ou « Dévers » en portent. Le serveur décode ; un
 * décodage raté lui coûte le nom, jamais la requête.
 *
 * Tout est facultatif : sans annonce, la requête est **exactement** celle
 * d'avant la spec 030. C'est ce qui permet à l'application Android, qui n'en
 * envoie aucun, de continuer sans rien changer.
 */
function entetesDAnnonce(annonce) {
  if (!annonce || !annonce.id) return {};
  const entetes = { "X-Device-Id": annonce.id };
  if (annonce.nom) entetes["X-Device-Name"] = encodeURIComponent(annonce.nom);
  if (annonce.app) entetes["X-App-Version"] = annonce.app;
  return entetes;
}

export class Api {
  constructor({ jeton, fetch: fetchInjecte } = {}) {
    this.jeton = jeton || null;
    this._fetch = fetchInjecte || ((...a) => globalThis.fetch(...a));
  }

  _entetes(supplement) {
    const entetes = { "Content-Type": "application/json", ...(supplement || {}) };
    // Pas d'en-tête plutôt qu'un en-tête vide : un `X-Api-Key:` vide est une
    // clé FAUSSE pour le serveur, donc un 401, là où l'absence reste acceptée
    // en mode toléré. Les deux ne sont pas interchangeables.
    if (this.jeton) entetes[ENTETE_CLE] = this.jeton;
    return entetes;
  }

  /** Vérifie un QR de grimpeur. Rend `{ok, libelle, reseau, code}`. */
  verifierGrimpeur(dossard) {
    return this._poster("climber/name", { id: dossard });
  }

  /** Vérifie un QR de bloc. */
  verifierBloc(tag) {
    return this._poster("bloc/name", { id: tag });
  }

  async _poster(chemin, corps) {
    try {
      const r = await this._fetch(`/api/v2/contest/${chemin}`, {
        method: "POST",
        headers: this._entetes(),
        body: JSON.stringify(corps),
      });
      let json = null;
      try { json = await r.json(); } catch { json = null; }
      if (!json) {
        // Un corps illisible, c'est presque toujours une page d'erreur HTML :
        // 502 d'un proxy, 503 d'un serveur qui redémarre. Ce n'est PAS un refus
        // métier, et le juge doit réessayer.
        return { ok: false, reseau: true, code: r.status,
                 message: "Réponse illisible du serveur" };
      }
      if (r.ok && json.success) return { ok: true, libelle: json.id || "", code: r.status };
      return { ok: false, reseau: r.status >= 500, code: r.status,
               message: json.message || "Refusé par le serveur" };
    } catch (e) {
      // `fetch` ne lève que si la requête n'est pas partie : réseau coupé,
      // serveur injoignable. Jamais pour un 4xx.
      return { ok: false, reseau: true, code: 0, message: "Serveur injoignable" };
    }
  }

  /**
   * Envoie un lot de réussites.
   *
   * Rend les `ref` **acquittées** et les refus. Une `ref` absente des deux n'a
   * pas été traitée : l'appelant la garde. Le défaut est de garder — perdre une
   * réussite est le seul résultat inacceptable.
   */
  async envoyerLot(reussites, appareil) {
    if (!reussites.length) return { acquittees: new Set(), refusees: [], ok: true };
    const corps = { items: reussites };
    if (appareil && appareil.id) corps.appareil = appareil;

    try {
      const r = await this._fetch("/api/v3/successes", {
        method: "POST",
        headers: this._entetes(),
        body: JSON.stringify(corps),
      });
      if (!r.ok) {
        // 401, 409, 413... RIEN n'est acquitté : la file reste intacte.
        return { acquittees: new Set(), refusees: [], ok: false, code: r.status,
                 message: `Envoi refusé (${r.status})` };
      }
      const json = await r.json();
      const acquittees = new Set();
      const refusees = [];
      for (const item of json.resultats || []) {
        if (!item.ref) continue;
        // Les trois états sont DÉFINITIFS : la réussite quitte la file dans les
        // trois cas. Tout autre état : on ne sait pas, donc on garde.
        if (item.etat === "enregistree" || item.etat === "deja_connue") {
          acquittees.add(item.ref);
        } else if (item.etat === "refusee") {
          acquittees.add(item.ref);
          refusees.push({ ref: item.ref, message: item.message || "" });
        }
      }
      return { acquittees, refusees, ok: true,
               catalogueVersion: json.catalogue_version ?? null };
    } catch (e) {
      return { acquittees: new Set(), refusees: [], ok: false, code: 0,
               message: "Serveur injoignable" };
    }
  }

  /**
   * Le catalogue. `304` quand rien n'a bougé : ~150 octets.
   *
   * ⚠️ **`versionConnue` à `null` force un `200` complet**, et c'est le bouton
   * « Retélécharger maintenant » des réglages. C'est le SEUL moyen propre
   * d'obtenir un catalogue neuf : le serveur décide du `304` par égalité
   * stricte, et un client qui annoncerait un autre numéro pour le forcer ne
   * serait pas « en avance » à ses yeux — il viendrait d'ailleurs, d'une autre
   * compétition ou d'une base restaurée. Une requête nue ne pose pas la
   * question, donc ne peut pas recevoir un `304`.
   *
   * Rend aussi `serveur` : la version que le backend exécute, lue dans un
   * en-tête présent sur les DEUX branches. C'est ce qui permet aux réglages de
   * dire « ta coquille est en retard » sans appeler `/health`, que le proxy
   * ferme aux téléphones.
   */
  async telechargerCatalogue(versionConnue, annonce = null) {
    const entetes = this._entetes(entetesDAnnonce(annonce));
    delete entetes["Content-Type"];
    if (versionConnue) entetes["If-None-Match"] = `"${versionConnue}"`;
    try {
      const r = await this._fetch("/api/v2/catalog", { method: "GET", headers: entetes });
      // `?.` : les tests injectent un `fetch` factice sans objet `headers`, et
      // une version serveur inconnue est un cas prévu — pas une erreur.
      const serveur = r.headers?.get?.("X-Server-Version") || null;
      if (r.status === 304) return { etat: "deja-a-jour", serveur };
      if (!r.ok) return { etat: "echec", code: r.status, reseau: r.status >= 500, serveur };
      return { etat: "recu", catalogue: await r.json(), serveur };
    } catch (e) {
      return { etat: "echec", code: 0, reseau: true, serveur: null };
    }
  }
}
