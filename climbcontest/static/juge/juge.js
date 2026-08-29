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
import { ETATS, Historique, refCourte } from "./historique.js";
import { identiteCourante, renommer } from "./identite.js";
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
  garderGrimpeur: false, seulementNonArrives: false,
};

let api = null;
let file = null;
let expediteur = null;
let catalogue = new Catalogue();
let historique = null;
let identite = { id: null, nom: null };
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

  const reussite = {
    ref: nouvelleRef(), bib: etat.dossard, bloc: etat.bloc,
    at: new Date().toISOString(),
  };
  try {
    // L'ordre compte : la file d'abord. Elle porte la réussite ; le journal
    // n'en garde qu'une trace. Si l'écriture du journal échouait, on perdrait
    // une ligne d'historique, pas une réussite.
    await file.ajouter(reussite);
    await historique.noter(reussite).catch(() => {});
    dire("Validé", "ok");
    etat.envoiEnCours = false;
    // « Garder le grimpeur entre deux blocs » : seul le bloc repart à zéro,
    // pour enchaîner les blocs d'un même grimpeur sans le rescanner.
    if (etat.garderGrimpeur) { etat.bloc = null; redessiner(); } else effacer();
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
  // Le journal apprend le sort de chaque référence. Un refus l'emporte sur
  // l'acquittement qui l'accompagne : une refusée est AUSSI acquittée — le
  // serveur a statué — et afficher « arrivé » serait le contraire de la vérité.
  if (bilan.acquittees) {
    const refus = new Map((bilan.refusees || []).map((r) => [r.ref, r.message]));
    for (const ref of bilan.acquittees) {
      await historique.changerEtat(
        ref, refus.has(ref) ? ETATS.refusee : ETATS.partie, refus.get(ref),
      ).catch(() => {});
    }
  }
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
    catalogue = Catalogue.depuisReponseServeur(r.catalogue);
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

// --- Les écrans secondaires -------------------------------------------------

function montrer(id) {
  for (const ecran of document.querySelectorAll(".ecran")) {
    ecran.hidden = ecran.id !== id;
  }
  $("principal").hidden = id !== null;
  // La bande de file appartient a l'ecran principal : elle n'a rien a faire
  // au-dessus des reglages, qui disent deja la meme chose en plus complet.
  $("bandeFile").hidden = id !== null ||
    (etat.enAttente === 0 && etat.refusees === 0);
}

async function ouvrirLesReglages() {
  $("nomTelephone").value = identite.nom || "";
  $("identifiantTelephone").textContent =
    `Identifiant : ${String(identite.id || "").slice(0, 8)}`;
  $("garderGrimpeur").checked = etat.garderGrimpeur;
  $("adresseServeur").textContent = location.origin;
  await rafraichirLesReglages();
  montrer("ecranReglages");
}

async function rafraichirLesReglages() {
  const enAttente = await file.nombreEnAttente();
  const refusees = await file.nombreRefusees();

  $("etatFile").textContent = enAttente > 0
    ? `${enAttente} en attente` : "Tout est déjà envoyé";
  $("toutEnvoyer").disabled = enAttente === 0;

  $("ligneRefus").hidden = refusees === 0;
  $("expliquerRefus").hidden = refusees === 0;
  $("etatRefus").textContent = refusees === 1 ? "1 refusée" : `${refusees} refusées`;

  const voyantClasses = [...$("voyant").classList];
  $("etatServeur").textContent = voyantClasses.includes("ok") ? "Serveur joignable"
    : voyantClasses.includes("ko") ? "Serveur injoignable" : "Connexion en cours";
}

/**
 * Les réussites refusées, remises en file.
 *
 * Le geste du juge une fois qu'un organisateur a ajouté le participant
 * manquant — le cas de loin le plus fréquent : « ce dossard n'existe pas
 * ENCORE ». Sans ce bouton, ces réussites seraient perdues.
 */
async function renvoyerLesRefusees() {
  const reprises = await expediteur.renvoyerLesRefusees(nouvelleRef);
  for (const { ancienne, nouvelle } of reprises) {
    await historique.reprendre(ancienne, nouvelle).catch(() => {});
  }
  dire(reprises.length
    ? "Réussites refusées remises en file" : "Aucune réussite refusée", "ok");
  // Le retrait repart de zéro : la cause du refus vient d'être traitée.
  expediteur.echecsConsecutifs = 0;
  dernierEnvoiMs = 0;
  await vider({ forcer: true });
  await rafraichirLesCompteurs();
  await rafraichirLesReglages();
}

async function ouvrirMesScans() {
  await dessinerLesScans();
  montrer("ecranScans");
}

async function dessinerLesScans() {
  const tous = await historique.tous();
  const nonArrives = tous.filter((s) => s.etat !== ETATS.partie).length;

  $("compteScans").textContent =
    tous.length === 1 ? "1 scan" : `${tous.length} scans`;
  const bouton = $("filtreNonArrives");
  bouton.textContent = `Pas arrivés (${nonArrives})`;
  bouton.classList.toggle("actif", etat.seulementNonArrives);

  const affiches = (etat.seulementNonArrives
    ? tous.filter((s) => s.etat !== ETATS.partie) : tous).slice().reverse();

  const liste = $("listeScans");
  liste.textContent = "";
  if (!affiches.length) {
    const vide = document.createElement("p");
    vide.className = "vide";
    // Jamais une page blanche : on dit ce qui va s'y passer.
    vide.textContent = etat.seulementNonArrives
      ? "Tout est arrivé sur le serveur."
      : "Aucun scan pour l'instant. Les réussites que vous validez apparaîtront "
        + "ici, avec leur état.";
    liste.appendChild(vide);
    return;
  }
  for (const scan of affiches) liste.appendChild(ligneDeScan(scan));
}

function ligneDeScan(scan) {
  const [couleur, libelle] = scan.etat === ETATS.partie
    ? ["var(--fait)", "Arrivé"]
    : scan.etat === ETATS.refusee ? ["var(--alerte)", "Refusé"]
                                  : ["var(--attention)", "En attente"];

  const ligne = document.createElement("div");
  ligne.className = "scan";

  const point = document.createElement("span");
  point.className = "point";
  point.style.background = couleur;
  ligne.appendChild(point);

  const qui = document.createElement("div");
  qui.className = "qui";
  const nom = document.createElement("div");
  nom.className = "nom";
  // Le nom vient du catalogue COURANT : un scan d'une compétition passée
  // n'en a plus, et montre son dossard. Le journal, lui, n'en garde aucun.
  nom.textContent = catalogue.grimpeur(scan.bib) || `Dossard ${scan.bib}`;
  qui.appendChild(nom);
  const ou = document.createElement("div");
  ou.className = "ou";
  ou.textContent = `${scan.bloc} · ${heureLocale(scan.at)}`;
  qui.appendChild(ou);
  if (scan.motif && scan.etat === ETATS.refusee) {
    const motif = document.createElement("div");
    motif.className = "motif";
    // Le motif dit quoi faire : « dossard inconnu » veut dire « demande à
    // l'organisateur de l'ajouter ».
    motif.textContent = scan.motif;
    qui.appendChild(motif);
  }
  ligne.appendChild(qui);

  const droite = document.createElement("div");
  const etatTexte = document.createElement("div");
  etatTexte.className = "etat";
  etatTexte.style.color = couleur;
  etatTexte.textContent = libelle;
  droite.appendChild(etatTexte);
  const ref = document.createElement("div");
  ref.className = "mono";
  // La référence courte : ce que le juge lit à voix haute quand l'organisateur
  // la cherche dans la console.
  ref.textContent = refCourte(scan.ref);
  droite.appendChild(ref);
  ligne.appendChild(droite);

  return ligne;
}

/**
 * « 2026-11-08T09:42:03Z » devient « 10:42 ».
 *
 * ⚠️ L'heure est stockée en UTC — c'est ce que le serveur attend. La couper à
 * la main donnerait 09:42 à un juge qui a scanné à 10:42 : en novembre, la
 * France est à UTC+1.
 */
function heureLocale(iso) {
  const quand = new Date(iso);
  return Number.isNaN(quand.getTime())
    ? iso
    : quand.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
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
  historique = new Historique(new MagasinIdb(MAGASINS.historique));
  expediteur = new Expediteur(file, api, { identite: () => identite });

  if (!jeton) {
    dire("Cette application a besoin du lien fourni par l'organisateur.", "attention");
  }

  try {
    catalogue = Catalogue.depuisJson(await reglages.lire(CLE_CATALOGUE));
    identite = await identiteCourante(reglages);
    etat.garderGrimpeur = (await reglages.lire("garder-grimpeur")) === true;
    // Au démarrage, une fois : ce qui a plus de trente jours s'en va. Ne touche
    // jamais à la file, donc ne peut pas perdre une réussite.
    await historique.purger();
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
  $("bandeFile").addEventListener("click", ouvrirLesReglages);

  $("ouvrirReglages").addEventListener("click", ouvrirLesReglages);
  for (const bouton of document.querySelectorAll("[data-ferme]")) {
    bouton.addEventListener("click", () => montrer(null));
  }
  $("voirMesScans").addEventListener("click", ouvrirMesScans);
  $("filtreNonArrives").addEventListener("click", () => {
    etat.seulementNonArrives = !etat.seulementNonArrives;
    dessinerLesScans();
  });
  $("nomTelephone").addEventListener("input", async (e) => {
    identite = await renommer(reglages, e.target.value);
  });
  $("garderGrimpeur").addEventListener("change", async (e) => {
    etat.garderGrimpeur = e.target.checked;
    await reglages.ecrire("garder-grimpeur", etat.garderGrimpeur);
  });
  $("toutEnvoyer").addEventListener("click", async () => {
    // Le bouton ne contourne pas le retrait exponentiel : appuyer en boucle sur
    // un serveur éteint ne servirait à rien.
    await vider({ forcer: true });
    await rafraichirLesReglages();
  });
  $("renvoyerRefus").addEventListener("click", renvoyerLesRefusees);

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
