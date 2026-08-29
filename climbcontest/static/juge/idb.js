/**
 * IndexedDB, réduit aux quatre gestes dont la file a besoin.
 *
 * Isolé ici pour la même raison que `StockageFichier` côté Android : c'est ce
 * module qui décide si une réussite survit à une fermeture d'onglet. Le reste
 * est de la logique de liste, testée sur Node avec un magasin en mémoire.
 *
 * **IndexedDB et non `localStorage`.** `localStorage` est synchrone — il bloque
 * le fil pendant qu'on scanne —, plafonné à ~5 Mo, et surtout il ne sait pas
 * faire de transaction. Or l'invariant central de cette application est une
 * transaction : retirer de la file exactement les réussites que le serveur a
 * acquittées, toutes ou aucune.
 *
 * ⚠️ **iOS efface le stockage d'une PWA restée inutilisée** (sept jours pour un
 * site web ordinaire). Une PWA **installée sur l'écran d'accueil** échappe à
 * cette purge — c'est pour ça que le bandeau d'installation n'est pas
 * cosmétique. À vérifier sur un vrai iPhone : c'est le point du plan de test
 * qu'aucun émulateur ne couvre.
 */

const NOM = "climbcontest-juge";
const VERSION = 1;

export const MAGASINS = {
  file: "file",
  refusees: "refusees",
  historique: "historique",
  reglages: "reglages",
};

let ouverture = null;

/** Ouvre la base, une seule fois. */
export function ouvrir() {
  if (ouverture) return ouverture;
  ouverture = new Promise((resoudre, rejeter) => {
    const demande = indexedDB.open(NOM, VERSION);
    demande.onupgradeneeded = () => {
      const base = demande.result;
      // Clés auto-incrémentées : elles donnent l'ordre d'insertion, donc
      // l'ordre où le juge a validé. C'est celui dans lequel on envoie.
      for (const nom of [MAGASINS.file, MAGASINS.refusees, MAGASINS.historique]) {
        if (!base.objectStoreNames.contains(nom)) {
          base.createObjectStore(nom, { autoIncrement: true });
        }
      }
      if (!base.objectStoreNames.contains(MAGASINS.reglages)) {
        base.createObjectStore(MAGASINS.reglages);
      }
    };
    demande.onsuccess = () => resoudre(demande.result);
    demande.onerror = () => rejeter(demande.error);
    // Un autre onglet retient une version plus ancienne. On ne bloque pas
    // indéfiniment : mieux vaut échouer visiblement que rester muet.
    demande.onblocked = () => rejeter(new Error("base verrouillee par un autre onglet"));
  });
  return ouverture;
}

function transaction(base, nom, mode) {
  return base.transaction(nom, mode).objectStore(nom);
}

function attendre(demande) {
  return new Promise((resoudre, rejeter) => {
    demande.onsuccess = () => resoudre(demande.result);
    demande.onerror = () => rejeter(demande.error);
  });
}

/**
 * Un magasin de liste, qui se comporte comme `MagasinMemoire`.
 *
 * Les deux implémentations se lisent côte à côte, et c'est voulu : celle en
 * mémoire est la **définition** de ce que celle-ci doit faire.
 */
export class MagasinIdb {
  constructor(nom) {
    this.nom = nom;
  }

  async ajouter(valeur) {
    const base = await ouvrir();
    return attendre(transaction(base, this.nom, "readwrite").add(valeur));
  }

  async tout() {
    const base = await ouvrir();
    const magasin = transaction(base, this.nom, "readonly");
    const [cles, valeurs] = await Promise.all([
      attendre(magasin.getAllKeys()), attendre(magasin.getAll()),
    ]);
    return cles.map((cle, i) => ({ cle, valeur: valeurs[i] }));
  }

  /**
   * Supprime plusieurs clés **dans une seule transaction**.
   *
   * C'est ce que le fichier d'acquittements de l'Android remplaçait faute de
   * mieux : ici, soit toutes partent, soit aucune. Il n'y a pas d'état
   * intermédiaire où la moitié d'un lot aurait disparu.
   */
  async supprimer(cles) {
    if (!cles.length) return;
    const base = await ouvrir();
    const tx = base.transaction(this.nom, "readwrite");
    const magasin = tx.objectStore(this.nom);
    for (const cle of cles) magasin.delete(cle);
    await new Promise((resoudre, rejeter) => {
      tx.oncomplete = resoudre;
      tx.onerror = () => rejeter(tx.error);
      tx.onabort = () => rejeter(tx.error);
    });
  }

  async vider() {
    const base = await ouvrir();
    await attendre(transaction(base, this.nom, "readwrite").clear());
  }
}

/** Les réglages : une simple table clé → valeur. */
export const reglages = {
  async lire(cle) {
    const base = await ouvrir();
    return attendre(transaction(base, MAGASINS.reglages, "readonly").get(cle));
  },
  async ecrire(cle, valeur) {
    const base = await ouvrir();
    await attendre(
      transaction(base, MAGASINS.reglages, "readwrite").put(valeur, cle));
  },
};
