/**
 * Qui est ce téléphone.
 *
 * ⚠️ On identifie un **poste**, pas une personne. Les téléphones changent de
 * main dans la journée ; « Mur jaune » désigne un endroit de la salle. C'est la
 * même règle que côté Android et côté serveur, et elle doit le rester.
 */

export const LONGUEUR_NOM = 60;
const CLE = "identite";

export function nettoyerLeNom(brut) {
  const propre = String(brut ?? "").trim().slice(0, LONGUEUR_NOM);
  return propre || null;
}

function identifiantNeuf() {
  if (globalThis.crypto && globalThis.crypto.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `pwa-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/**
 * L'identité rangée, créée au premier appel.
 *
 * @param reglages  une table clé → valeur (`idb.js` en fournit une)
 */
export async function identiteCourante(reglages) {
  const lue = await reglages.lire(CLE);
  if (lue && typeof lue.id === "string" && lue.id) {
    return { id: lue.id, nom: lue.nom ?? null };
  }
  // Absente ou abîmée : une identité neuve. Refuser de démarrer parce qu'un
  // enregistrement est illisible serait un bien mauvais échange.
  const neuve = { id: identifiantNeuf(), nom: null };
  await reglages.ecrire(CLE, neuve);
  return neuve;
}

/** Renomme le téléphone. L'identifiant, lui, ne bouge pas. */
export async function renommer(reglages, nom) {
  const actuelle = await identiteCourante(reglages);
  const neuve = { id: actuelle.id, nom: nettoyerLeNom(nom) };
  await reglages.ecrire(CLE, neuve);
  return neuve;
}
