/**
 * L'écran du juge. Ce qui orchestre, et rien qui décide.
 *
 * Tout ce qui se décide vit ailleurs et se teste sur Node, sans navigateur :
 * [jeton.js], [api.js], [file.js], [expediteur.js], [politique.js],
 * [catalogue.js], [verrou.js]. Ici, on branche des boutons et on tient une
 * boucle. Le même partage que côté Android, où `DecisionEnvoi` et
 * `FileDeReussites` se testent sans émulateur.
 *
 * Depuis l'IT2 de la spec 007, le juge **n'attend plus le réseau** : un scan est
 * validé contre le catalogue local, et « Validé » s'affiche quand la réussite
 * est sur le téléphone.
 */
import { CLE_RANGEMENT, choisirJeton } from "./jeton.js";
import { Api } from "./api.js";
import { Catalogue, doitRafraichir } from "./catalogue.js";
import { Expediteur } from "./expediteur.js";
import { FileDeReussites } from "./file.js";
import { MAGASINS, MagasinIdb, reglages } from "./idb.js";
import { doitEnvoyer } from "./politique.js";
import { bailNeuf, identifiantDOnglet, peutPrendre } from "./verrou.js";
import { expliquerLErreurCamera, lireUnQr } from "./scan.js";

const $ = (id) => document.getElementById(id);
const CLE_CATALOGUE = "catalogue";
const CLE_BAIL = "bail-envoi";
const PERIODE_BOUCLE_MS = 1000;
const PERIODE_PRESENCE_MS = 30_000;

const etat = {
  dossard: null, grimpeur: null, bloc: null,
  envoiEnCours: false, enAttente: 0, refusees: 0,
};

let api = null;
let file = null;
let expediteur = null;
let catalogue = new Catalogue();
let annulation = null;
const moi = identifiantDOnglet();

let dernierEnvoiMs = 0;
let dernierCatalogueMs = 0;
let dernierContactMs = 0;
let versionServeurConnue = null;

// --- Le jeton ---------------------------------------------------------------

function installerLeJeton() {
  let range = null;
  try { range = localStorage.getItem(CLE_RANGEMENT); } catch { range = null; }

  const { jeton, aEcrire } = choisirJeton(location.hash, range);
  if (aEcrire) {
    try { localStorage.setItem(CLE_RANGEMENT, jeton); } catch { /* mode prive */ }
  }
  if (location.hash) {
    // On nettoie l'adresse : sans ça, le jeton reste visible dans la barre
    // d'adresse, dans l'historique, et dans la capture d'écran que quelqu'un
    // fera pour montrer l'application à un collègue.
    history.replaceState(null, "", location.pathname);
  }
  return jeton;
}

/**
 * Un nouveau lien ouvert alors que l'application tourne déjà.
 *
 * ⚠️ Constaté à l'écran, et ça n'avait rien d'évident : passer de `/juge` à
 * `/juge#j=autre` est une navigation **dans le même document**. Le navigateur
 * ne recharge rien, donc le module ne repart pas, donc le jeton n'était pas
 * remplacé. C'est exactement le geste qu'on fera si un jeton est révoqué en
 * pleine compétition.
 */
function surNouveauLien() {
  window.addEventListener("hashchange", () => {
    const jeton = installerLeJeton();
    if (!jeton) return;
    api.jeton = jeton;
    // Le retrait exponentiel repart de zéro. Après une série de refus, il peut
    // atteindre une minute ; or l'organisateur envoie un nouveau lien
    // PRÉCISÉMENT pour débloquer la situation. Faire attendre le juge une
    // minute de plus après ça n'aurait aucun sens — la cause des échecs vient
    // d'être traitée.
    expediteur.echecsConsecutifs = 0;
    dernierEnvoiMs = 0;
    dire("Nouveau lien pris en compte.", "ok");
    voyant("doute");
    rafraichirLeCatalogue();
    vider({ forcer: true });
  });
}

// --- Le voyant --------------------------------------------------------------

function voyant(quoi) {
  const svg = $("voyant");
  svg.classList.remove("ok", "ko", "doute");
  svg.classList.add(quoi);
  svg.setAttribute("aria-label", {
    ok: "Serveur joignable", ko: "Serveur injoignable",
    doute: "Connexion en cours",
  }[quoi]);
}

// --- Les messages -----------------------------------------------------------

let effacementDuMessage = null;

function dire(texte, genre) {
  const m = $("message");
  m.textContent = texte;
  m.className = genre || "";
  m.hidden = false;
  clearTimeout(effacementDuMessage);
  // Un refus reste affiché : le juge doit avoir le temps de le lire, et souvent
  // d'aller voir un organisateur. Un succès s'efface tout seul.
  if (genre === "ok") effacementDuMessage = setTimeout(() => { m.hidden = true; }, 3000);
}

// --- L'écran ----------------------------------------------------------------

function redessiner() {
  const grimpeurFait = etat.dossard !== null;
  const blocFait = etat.bloc !== null;

  $("carteGrimpeur").classList.toggle("fait", grimpeurFait);
  $("valeurGrimpeur").textContent = etat.grimpeur || etat.dossard || "À scanner";
  $("valeurGrimpeur").classList.toggle("attente", !grimpeurFait);
  $("detailGrimpeur").textContent = grimpeurFait && etat.grimpeur ? `n°${etat.dossard}` : "";

  $("carteBloc").classList.toggle("fait", blocFait);
  $("valeurBloc").textContent = etat.bloc || "À scanner";
  $("valeurBloc").classList.toggle("attente", !blocFait);

  const pret = grimpeurFait && blocFait && !etat.envoiEnCours;
  $("envoyer").disabled = !pret;
  $("aide").hidden = pret;

  // La file ne s'affiche que quand elle a quelque chose à dire.
  const bande = $("bandeFile");
  bande.hidden = etat.enAttente === 0 && etat.refusees === 0;
  $("compteurAttente").hidden = etat.enAttente === 0;
  $("compteurAttente").textContent = `${etat.enAttente} en attente`;
  $("compteurRefus").hidden = etat.refusees === 0;
  $("compteurRefus").textContent =
    etat.refusees === 1 ? "1 refusée" : `${etat.refusees} refusées`;
}

async function rafraichirLesCompteurs() {
  etat.enAttente = await file.nombreEnAttente();
  etat.refusees = await file.nombreRefusees();
  redessiner();
}

function effacer() {
  etat.dossard = etat.grimpeur = etat.bloc = null;
  redessiner();
}

// --- Scanner ----------------------------------------------------------------

async function scanner(quoi) {
  annulation = new AbortController();
  $("consigne").textContent = quoi === "grimpeur"
    ? "Vise le QR du grimpeur" : "Vise le QR du bloc";
  $("viseur").hidden = false;

  let code = null;
  try {
    code = await lireUnQr($("flux"), annulation.signal);
  } catch (e) {
    dire(expliquerLErreurCamera(e), "erreur");
    return;
  } finally {
    $("viseur").hidden = true;
  }
  if (!code) return;                     // annulé par le juge

  // Le catalogue local d'abord : ~100 ns au lieu de ~200 ms, et SANS réseau.
  const local = quoi === "grimpeur" ? catalogue.grimpeur(code) : catalogue.bloc(code);
  if (local !== null) {
    retenir(quoi, code, local);
    return;
  }

  // Inconnu localement. Ça veut presque toujours dire « ce participant a été
  // inscrit il y a dix minutes » : on demande au serveur, et on note qu'on a du
  // retard. Le juge n'a rien à faire pour que ça se répare.
  const verdict = quoi === "grimpeur"
    ? await api.verifierGrimpeur(code) : await api.verifierBloc(code);
  rafraichirLeCatalogue();

  if (verdict.ok) {
    voyant("ok");
    retenir(quoi, code, verdict.libelle || null);
    return;
  }
  if (verdict.reseau) {
    // « Identifiant incorrect, recommencez » sur une simple coupure réseau
    // enverrait le juge chercher un organisateur pour un QR parfaitement
    // valide. C'est la leçon apprise côté Android.
    voyant("ko");
    dire("Serveur injoignable. Rescanne, le code est peut-être bon.", "attention");
  } else {
    dire(`${quoi === "grimpeur" ? "Dossard" : "Bloc"} inconnu. ` +
         "Rescanne, ou va voir un organisateur.", "erreur");
  }
}

function retenir(quoi, code, libelle) {
  if (quoi === "grimpeur") { etat.dossard = code; etat.grimpeur = libelle; }
  else { etat.bloc = libelle || code; }
  redessiner();
}

// --- Envoyer ----------------------------------------------------------------

/**
 * Dépose la réussite sur le téléphone, et rend la main **immédiatement**.
 *
 * « Validé » s'affiche quand la réussite est dans IndexedDB, pas quand elle est
 * sur le serveur. C'est tout l'objet de cette itération : le juge n'attend plus
 * le réseau, et le réseau redevient ce qu'il aurait toujours dû être — un détail
 * d'acheminement.
 */
async function envoyer() {
  if (etat.dossard === null || etat.bloc === null || etat.envoiEnCours) return;
  etat.envoiEnCours = true;
  redessiner();

  try {
    await file.ajouter({
      ref: nouvelleRef(),
      bib: etat.dossard,
      bloc: etat.bloc,
      at: new Date().toISOString(),
    });
    dire("Validé", "ok");
    etat.envoiEnCours = false;
    effacer();
  } catch (e) {
    // Stockage plein, mode privé, base inaccessible. On ne dit surtout pas
    // « Validé » : ce serait mentir au juge.
    etat.envoiEnCours = false;
    dire("Impossible d'enregistrer sur ce téléphone. Préviens un organisateur.",
         "erreur");
    redessiner();
    return;
  }

  await rafraichirLesCompteurs();
  vider();                               // on tente tout de suite, sans attendre
}

function nouvelleRef() {
  return (crypto.randomUUID && crypto.randomUUID()) ||
         `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// --- La boucle de fond ------------------------------------------------------

/**
 * Un seul onglet envoie à la fois.
 *
 * Un juge peut avoir la PWA installée **et** un onglet Safari sur la même
 * adresse ; les deux partagent le même IndexedDB. Sans ce bail, les deux
 * liraient le même lot et le second supprimerait ce que le premier vient de
 * traiter.
 */
async function prendreLeBail() {
  const maintenant = Date.now();
  const bail = await reglages.lire(CLE_BAIL);
  if (!peutPrendre(bail, moi, maintenant)) return false;
  await reglages.ecrire(CLE_BAIL, bailNeuf(moi, maintenant));
  return true;
}

async function vider({ forcer = false } = {}) {
  const enAttente = await file.nombreEnAttente();
  if (!doitEnvoyer({ enAttente, depuisDernierEnvoiMs: Date.now() - dernierEnvoiMs,
                     echecs: expediteur.echecsConsecutifs, forcer })) {
    return;
  }
  if (!(await prendreLeBail())) return;

  dernierEnvoiMs = Date.now();
  const bilan = await expediteur.tenter();
  if (!bilan) return;

  dernierContactMs = Date.now();
  voyant(bilan.aReussi ? "ok" : "ko");
  if (bilan.catalogueVersion !== null) versionServeurConnue = bilan.catalogueVersion;
  if (bilan.refusees && bilan.refusees.length) {
    dire(bilan.refusees[0].message ||
         "Une réussite a été refusée. Va voir un organisateur.", "erreur");
  }
  await rafraichirLesCompteurs();
}

async function rafraichirLeCatalogue() {
  dernierCatalogueMs = Date.now();
  dernierContactMs = Date.now();
  const r = await api.telechargerCatalogue(catalogue.version || null);
  if (r.etat === "recu") {
    catalogue = Catalogue.depuisJson(r.catalogue);
    versionServeurConnue = catalogue.version;
    await reglages.ecrire(CLE_CATALOGUE, catalogue.versJson());
    voyant("ok");
  } else if (r.etat === "deja-a-jour") {
    versionServeurConnue = catalogue.version;
    voyant("ok");
  } else {
    // Tout échec éteint le voyant, réseau ou non : un 401 sur un jeton révoqué
    // veut dire que rien ne passera. Afficher « tout va bien » serait un
    // mensonge.
    voyant("ko");
  }
}

/**
 * Le sondage de présence, toutes les trente secondes et **au premier plan
 * seulement**.
 *
 * ⚠️ Il passe par le catalogue et non par `/health` : Caddy ferme `/health` à
 * tout ce qui n'est pas le LAN de la maison, et les téléphones des juges sont
 * sur le wifi de la salle. Le sondage aurait dit « injoignable » en permanence
 * pendant que tout fonctionnait — la leçon apprise côté Android.
 */
async function boucle() {
  if (document.visibilityState !== "visible") return;

  await vider();

  const maintenant = Date.now();
  const doitCatalogue = doitRafraichir({
    estVide: catalogue.estVide, versionServeur: versionServeurConnue,
    versionLocale: catalogue.version, maintenantMs: maintenant,
    dernierMs: dernierCatalogueMs,
  });
  const doitSonder =
    maintenant - Math.max(dernierContactMs, dernierEnvoiMs) >= PERIODE_PRESENCE_MS;

  if (doitCatalogue || doitSonder) await rafraichirLeCatalogue();
}

// --- Démarrage --------------------------------------------------------------

function proposerLInstallation() {
  const installee = window.matchMedia("(display-mode: standalone)").matches ||
                    window.navigator.standalone === true;
  // On ne le propose qu'aux iPhone : ailleurs le navigateur le propose seul.
  // Et ce n'est pas cosmétique — iOS efface le stockage d'une PWA NON installée
  // restée inutilisée, ce qui emporterait la file.
  const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  $("installer").hidden = installee || !iOS;
}

async function demarrer() {
  const jeton = installerLeJeton();
  api = new Api({ jeton });
  file = new FileDeReussites(new MagasinIdb(MAGASINS.file),
                             new MagasinIdb(MAGASINS.refusees));
  expediteur = new Expediteur(file, api);

  if (!jeton) {
    dire("Cette application a besoin du lien fourni par l'organisateur.", "attention");
  }

  try {
    catalogue = Catalogue.depuisJson(await reglages.lire(CLE_CATALOGUE));
  } catch (e) {
    // Base inaccessible : on continue avec un catalogue vide. Chaque scan
    // passera par le réseau — dégradé, mais utilisable.
    dire("Stockage local indisponible : les scans passeront par le réseau.",
         "attention");
  }

  $("carteGrimpeur").addEventListener("click", () => scanner("grimpeur"));
  $("carteBloc").addEventListener("click", () => scanner("bloc"));
  $("envoyer").addEventListener("click", envoyer);
  $("effacer").addEventListener("click", effacer);
  $("annulerScan").addEventListener("click", () => annulation && annulation.abort());
  $("bandeFile").addEventListener("click", () => vider({ forcer: true }));

  surNouveauLien();
  proposerLInstallation();
  await rafraichirLesCompteurs();
  redessiner();

  // Le voyant ne vit qu'au premier plan : en arrière-plan personne ne le
  // regarde, et un voyant figé vaut moins que pas de voyant. Au retour, on
  // repart de « je vérifie » plutôt que d'afficher l'état d'avant la veille.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      voyant("doute");
      rafraichirLeCatalogue();
    }
  });

  await rafraichirLeCatalogue();
  setInterval(boucle, PERIODE_BOUCLE_MS);
}

demarrer();
