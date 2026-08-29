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

  /** Le catalogue. `304` quand rien n'a bougé : ~150 octets. */
  async telechargerCatalogue(versionConnue) {
    const entetes = this._entetes();
    delete entetes["Content-Type"];
    if (versionConnue) entetes["If-None-Match"] = `"${versionConnue}"`;
    try {
      const r = await this._fetch("/api/v2/catalog", { method: "GET", headers: entetes });
      if (r.status === 304) return { etat: "deja-a-jour" };
      if (!r.ok) return { etat: "echec", code: r.status, reseau: r.status >= 500 };
      return { etat: "recu", catalogue: await r.json() };
    } catch (e) {
      return { etat: "echec", code: 0, reseau: true };
    }
  }
}
