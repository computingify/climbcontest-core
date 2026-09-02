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
import { CLE_RANGEMENT, choisirJeton, jetonDUneAdresse } from "./jeton.js";
import { Api } from "./api.js";
import { Catalogue, doitRafraichir } from "./catalogue.js";
import { couleurDeCircuit, encreSur } from "./couleurs.js";
import { Expediteur } from "./expediteur.js";
import { FileDeReussites } from "./file.js";
import { ETATS, Historique, refCourte } from "./historique.js";
import { identiteCourante, renommer } from "./identite.js";
import { MAGASINS, MagasinIdb, reglages } from "./idb.js";
import { doitEnvoyer } from "./politique.js";
import { bailNeuf, identifiantDOnglet, peutPrendre } from "./verrou.js";
import { A_JOUR, EN_RETARD, resumeDuCatalogue, verdict } from "./versions.js";
import { expliquerLErreurCamera, lireUnQr } from "./scan.js";

const $ = (id) => document.getElementById(id);
const CLE_CATALOGUE = "catalogue";
const CLE_BAIL = "bail-envoi";
// Deux dates, et il en faut deux : « reçu » dit quand les données ont changé,
// « vérifié » quand on a demandé au serveur. Un catalogue reçu il y a deux
// heures et vérifié il y a deux minutes est parfaitement sain — les confondre
// ferait croire à un téléphone décroché.
const CLE_CATALOGUE_RECU = "catalogue-recu-le";
const CLE_CATALOGUE_VU = "catalogue-vu-le";
const PERIODE_BOUCLE_MS = 1000;
const PERIODE_PRESENCE_MS = 30_000;

const etat = {
  dossard: null, grimpeur: null, bloc: null, horsCircuit: false,
  // La couleur du circuit du bloc scanné (« Jaune », « Vert »…) : c'est elle
  // qui teinte l'écran. `null` = teinte neutre.
  couleurBloc: null,
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
// Deux « versions serveur » qui n'ont rien à voir, d'où deux noms distincts :
// `versionServeurConnue` est le numéro du CATALOGUE, `versionAppServeur` est le
// tag git du backend.
let versionAppServeur = null;
let catalogueRecuMs = 0;
let catalogueVuMs = 0;

/**
 * La version de la coquille que ce téléphone exécute.
 *
 * ⚠️ Lue dans la PAGE, pas demandée au serveur. Le service worker sert la
 * coquille depuis son cache : demander la version au serveur afficherait celle
 * qui est disponible, pas celle qui tourne — et dirait « à jour » à un
 * téléphone en retard, ce qui est précisément la panne à supprimer.
 */
const VERSION_APP = (
  document.querySelector('meta[name="climbcontest-version"]')?.content || ""
).trim() || null;

// --- Le jeton ---------------------------------------------------------------

function installerLeJeton() {
  let range = null;
  try { range = localStorage.getItem(CLE_RANGEMENT); } catch { range = null; }

  const { jeton, aEcrire } = choisirJeton(location.search, location.hash, range);
  if (aEcrire) {
    try { localStorage.setItem(CLE_RANGEMENT, jeton); } catch { /* mode prive */ }
  }
  if (location.hash) {
    // Le FRAGMENT est nettoyé : sans ça, le jeton reste visible dans la barre
    // d'adresse, dans l'historique, et dans la capture d'écran que quelqu'un
    // fera pour montrer l'application à un collègue.
    //
    // ⚠️ La REQUÊTE, elle, est conservée — `location.search` est recollé.
    // C'est le point qui décide si la solution marche partout (spec 014).
    // Deux générations d'iOS coexistent : au-delà de 16.4 le manifeste et son
    // `start_url` font foi, mais en deçà c'est **l'adresse affichée au moment
    // du « Sur l'écran d'accueil »** qui est retenue. La nettoyer ferait naître
    // ces installations-là sans jeton — précisément le défaut qu'on corrige.
    //
    // Ce que ça expose est mesuré : une fois installée, l'application est en
    // `display: standalone`, donc sans barre d'adresse. Et le jeton est de
    // toute façon affiché au mur en QR.
    history.replaceState(null, "", location.pathname + location.search);
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

/** Un fragment en gras. `textContent`, jamais `innerHTML` : ces noms
 *  viennent du classeur et sont saisis a la main. */
function gras(texte) {
  const b = document.createElement("b");
  b.textContent = texte || "?";
  return b;
}

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
  // ⚠️ Ce detail disait « Circuit Jaune ». C'etait FAUX : « Jaune » est une
  // couleur de DIFFICULTE, pas un circuit -- le circuit, c'est « U13 ». La
  // confusion venait de ce qu'aucun circuit reel n'etait disponible sur le
  // telephone avant la spec 019. Maintenant qu'ils le sont, on dit les deux, et
  // chacun sous son vrai nom.
  const circuitsDuBloc = blocFait ? (catalogue.circuitsDuBloc(etat.bloc) || []) : [];
  $("detailBloc").textContent = !blocFait ? ""
    : [circuitsDuBloc.join(" · "), etat.couleurBloc].filter(Boolean).join(" — ");

  // La couleur du circuit prend l'écran dès que le bloc est scanné — le même
  // principe que sur Android. Deux variables CSS suffisent : la teinte, et
  // l'encre lisible dessus (jaune et craie demandent de l'encre sombre).
  const teinte = blocFait ? couleurDeCircuit(etat.couleurBloc) : null;
  const racine = document.documentElement.style;
  if (teinte) {
    racine.setProperty("--circuit", teinte);
    racine.setProperty("--encre-circuit", encreSur(teinte));
  } else {
    racine.removeProperty("--circuit");
    racine.removeProperty("--encre-circuit");
  }

  // Le garde-fou de la spec 019, recalcule ICI et pas dans `retenir()` : le
  // grimpeur peut etre scanne APRES le bloc, et l'option « garder le grimpeur
  // entre deux blocs » enchaine les blocs sans le rescanner. Un etat derive
  // recalcule a chaque rendu ne peut pas se desynchroniser.
  //
  // `null` — dossard inconnu, tag inconnu, participant sans categorie, bloc
  // rattache a aucun circuit — veut dire « je ne sais pas », et on se TAIT. Un
  // avertissement qu'on ne sait pas justifier apprend a ignorer les
  // avertissements.
  etat.horsCircuit = grimpeurFait && blocFait
    && catalogue.estDansLeCircuit(etat.dossard, etat.bloc) === false;

  const avertissement = $("horsCircuit");
  avertissement.hidden = !etat.horsCircuit;
  if (etat.horsCircuit) {
    const duBloc = catalogue.circuitsDuBloc(etat.bloc) || [];
    const duGrimpeur = catalogue.circuitDuGrimpeur(etat.dossard);
    avertissement.replaceChildren();
    avertissement.append(
      "Ce bloc est ", gras(duBloc.join(" · ")),
      " — ce grimpeur est ", gras(duGrimpeur), ".",
      document.createElement("br"),
      "La réussite ne comptera pas dans son classement.",
    );
  }

  const pret = grimpeurFait && blocFait && !etat.envoiEnCours;
  $("envoyer").disabled = !pret;
  // On n'empeche JAMAIS l'envoi : le classeur peut etre faux, et un juge
  // bloque en pleine competition n'a aucun recours. Le bouton dit seulement ce
  // qu'il fait vraiment.
  $("envoyer").textContent = etat.horsCircuit ? "Envoyer quand même" : "Envoyer";
  $("envoyer").classList.toggle("force", etat.horsCircuit);
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
  etat.couleurBloc = null;
  etat.horsCircuit = false;
  redessiner();
}

// --- Se relier, quand l'automatique n'a pas marche --------------------------

/**
 * Le juge rescanne le QR affiche au mur, depuis l'application.
 *
 * Le cas vise : une installation faite AVANT la spec 014 garde un `start_url`
 * sans jeton, et son stockage peut etre vide. L'automatique ne peut rien pour
 * elle ; ce bouton, si.
 *
 * On recharge a l'adresse complete plutot que de poser le jeton et continuer :
 * tout ce qui a demarre sans jeton -- l'expediteur, le catalogue -- repart
 * ainsi d'un etat propre, sans qu'on ait a y penser un par un.
 */
async function relier() {
  annulation = new AbortController();
  $("consigne").textContent = "Vise le QR affiché par l’organisateur";
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
  if (!code) return;                       // annulé par le juge

  const jeton = jetonDUneAdresse(code);
  if (!jeton) {
    // Un QR de grimpeur ou de bloc ne dit pas la meme chose qu'un QR illisible.
    dire("Ce QR n’est pas le lien de l’organisateur. C’est celui affiché au " +
         "mur pour installer l’application.", "erreur");
    return;
  }
  try { localStorage.setItem(CLE_RANGEMENT, jeton); } catch { /* mode prive */ }
  location.replace(code);
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
  else {
    etat.bloc = libelle || code;
    // La couleur du circuit : c'est elle qui donne sa couleur à l'écran,
    // comme sur Android. `null` pour un bloc inconnu du catalogue — l'écran
    // reste alors sur sa teinte neutre.
    etat.couleurBloc = catalogue.couleurDuBloc(code);
  }
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
  // Ce que le juge a VU au moment d'appuyer. Le serveur, lui, recalculera le
  // statut courant a la lecture : corriger le classeur doit faire disparaitre
  // l'anomalie, pas la figer.
  if (etat.horsCircuit) reussite.hors_circuit = true;
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
    if (etat.garderGrimpeur) {
      etat.bloc = null; etat.couleurBloc = null; redessiner();
    } else effacer();
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

/**
 * Ce que le téléphone dit de lui au serveur, sur la requête qu'il fait déjà.
 *
 * Pas une requête de plus : écran allumé, le catalogue se rafraîchit toutes
 * les trente secondes de toute façon (`PERIODE_PRESENCE_MS`). C'est ce qui permet à la console de dire quel téléphone est
 * en retard sans qu'on aille les lire un par un — y compris le matin, avant la
 * première réussite envoyée.
 */
function annonceDeCeTelephone() {
  if (!identite || !identite.id) return null;
  return { id: identite.id, nom: identite.nom, app: VERSION_APP };
}

/**
 * @param forcer  vrai = requête NUE, sans `If-None-Match`, donc un `200`
 *                complet. C'est le bouton « Retélécharger maintenant », et
 *                c'est le seul moyen propre de forcer : le serveur décide du
 *                `304` par égalité stricte et refuse délibérément tout
 *                raccourci qui consisterait à annoncer un autre numéro.
 */
async function rafraichirLeCatalogue({ forcer = false } = {}) {
  dernierCatalogueMs = Date.now();
  dernierContactMs = Date.now();
  const r = await api.telechargerCatalogue(
    forcer ? null : (catalogue.version || null), annonceDeCeTelephone());
  if (r.serveur) versionAppServeur = r.serveur;
  if (r.etat === "recu") {
    catalogue = Catalogue.depuisReponseServeur(r.catalogue);
    versionServeurConnue = catalogue.version;
    await reglages.ecrire(CLE_CATALOGUE, catalogue.versJson());
    catalogueRecuMs = catalogueVuMs = Date.now();
    await reglages.ecrire(CLE_CATALOGUE_RECU, catalogueRecuMs).catch(() => {});
    await reglages.ecrire(CLE_CATALOGUE_VU, catalogueVuMs).catch(() => {});
    voyant("ok");
  } else if (r.etat === "deja-a-jour") {
    versionServeurConnue = catalogue.version;
    catalogueVuMs = Date.now();
    await reglages.ecrire(CLE_CATALOGUE_VU, catalogueVuMs).catch(() => {});
    voyant("ok");
  } else {
    // Tout échec éteint le voyant, réseau ou non : un 401 sur un jeton révoqué
    // veut dire que rien ne passera. Afficher « tout va bien » serait un
    // mensonge.
    voyant("ko");
  }
  return r;
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

  dessinerLesVersions();
}

function poserLeVerdict(id, etatVerdict, texte) {
  const bloc = $(id);
  // INCONNU n'affiche RIEN : ni « à jour », ni « en retard ». On ne prononce
  // pas un verdict qu'on n'a pas les moyens de rendre.
  bloc.hidden = etatVerdict !== A_JOUR && etatVerdict !== EN_RETARD;
  if (bloc.hidden) return;
  bloc.classList.toggle("ok", etatVerdict === A_JOUR);
  bloc.classList.toggle("att", etatVerdict === EN_RETARD);
  bloc.querySelector("span").textContent = texte;
}

/**
 * Les deux sections « Catalogue » et « Application » (spec 030).
 *
 * ⚠️ **Trois états, pas deux.** Tant qu'on n'a jamais joint le serveur, on
 * n'affiche AUCUN verdict — ni « à jour », ni « en retard ». Dire « à jour »
 * sans le savoir est le mensonge exact que cet écran existe pour supprimer, et
 * un téléphone qui démarre en mode avion est dans ce cas.
 *
 * ⚠️ **Comparaison par ÉGALITÉ, jamais par ordre.** Le numéro de catalogue
 * identifie un couple (édition, état de son catalogue) : il saute, et il saute
 * pour toutes les éditions à la fois quand le mur change. « Plus grand » ne
 * veut rien dire ; « différent » veut dire « pas les mêmes données ».
 */
function dessinerLesVersions() {
  const local = catalogue.version || null;
  $("versionCatalogue").textContent = local ? `n° ${local}` : "aucun";

  poserLeVerdict(
    "verdictCatalogue", verdict(local, versionServeurConnue),
    local === versionServeurConnue
      ? "Identique au serveur"
      : `Le serveur en est au n° ${versionServeurConnue}`);

  // `textContent` ligne par ligne plutôt qu'un `innerHTML` : rien de ce qui
  // s'affiche ici ne vient du serveur, mais un jour quelque chose en viendra.
  const resume = $("contenuCatalogue");
  resume.textContent = "";
  const lignes = resumeDuCatalogue({
    grimpeurs: catalogue.parDossard.size, blocs: catalogue.parTag.size,
    recuMs: catalogueRecuMs, vuMs: catalogueVuMs,
  });
  lignes.forEach((ligne, i) => {
    if (i) resume.appendChild(document.createElement("br"));
    resume.appendChild(document.createTextNode(ligne));
  });

  $("versionApp").textContent = VERSION_APP || "inconnue";
  const etatApp = verdict(VERSION_APP, versionAppServeur);
  const enRetard = etatApp === EN_RETARD;
  poserLeVerdict("verdictApp", etatApp,
                 enRetard ? `Le serveur sert ${versionAppServeur}` : "À jour");
  // Le bouton n'existe que s'il y a quelque chose à réparer : offrir en
  // permanence un « mettre à jour » invite à s'en servir pendant un scan, pour
  // rien.
  $("majApplication").hidden = !enRetard;
  $("expliquerMaj").hidden = !enRetard;
  $("forcerCatalogue").classList.toggle(
    "calme", versionServeurConnue === null || local === versionServeurConnue);
}

/** Le bouton « Retélécharger maintenant ». */
async function forcerLeCatalogue() {
  const bouton = $("forcerCatalogue");
  bouton.disabled = true;
  bouton.textContent = "Téléchargement…";
  try {
    const r = await rafraichirLeCatalogue({ forcer: true });
    if (r && r.etat === "recu") {
      dire(`Catalogue n° ${catalogue.version} reçu — ` +
           `${catalogue.parDossard.size} grimpeurs, ${catalogue.parTag.size} blocs.`,
           "ok");
    } else {
      // Hors ligne, le téléphone GARDE ce qu'il a : c'est la promesse de
      // l'application, et ce bouton ne doit pas la trahir.
      dire("Serveur injoignable — le téléphone garde le catalogue qu'il a.",
           "attention");
    }
  } finally {
    bouton.disabled = false;
    bouton.textContent = "Retélécharger maintenant";
    dessinerLesVersions();
  }
}

/**
 * Le bouton « Mettre à jour et redémarrer ».
 *
 * Il demande au service worker de retélécharger la coquille, puis recharge la
 * page. Le service worker ne remplace un fichier qu'APRÈS l'avoir reçu : sans
 * réseau, rien ne bouge et l'application reste utilisable hors ligne.
 *
 * ⚠️ Un scan en cours serait perdu par le rechargement. On refuse alors, en
 * disant pourquoi — plutôt que de demander une confirmation qu'un juge pressé
 * accepterait sans lire. La file d'attente, elle, est en IndexedDB : elle
 * survit au rechargement, toujours.
 */
async function mettreAJourLApplication() {
  if (etat.dossard || etat.bloc) {
    dire("Termine ou efface le scan en cours avant de mettre à jour.",
         "attention");
    return;
  }
  const bouton = $("majApplication");
  bouton.disabled = true;
  bouton.textContent = "Mise à jour…";
  try {
    const registre = "serviceWorker" in navigator
      ? await navigator.serviceWorker.getRegistration("/juge") : null;
    if (!registre || !navigator.serviceWorker.controller) {
      dire("Cette application n'est pas installée hors ligne : ferme-la et " +
           "rouvre-la pour prendre la nouvelle version.", "attention");
      return;
    }
    // D'abord le service worker lui-même : c'est lui qui porte la liste des
    // fichiers de la coquille, et elle a pu changer avec la version.
    await registre.update().catch(() => {});
    const bilan = await demanderAuServiceWorker(
      { type: "rafraichir-la-coquille" });
    if (bilan && bilan.remplaces > 0) {
      dire("Nouvelle version reçue — redémarrage.", "ok");
      // Court délai : le message doit avoir le temps de s'afficher.
      setTimeout(() => location.reload(), 700);
      return;
    }
    dire("Rien n'a pu être téléchargé — l'application reste comme elle est.",
         "attention");
  } finally {
    bouton.disabled = false;
    bouton.textContent = "Mettre à jour et redémarrer";
  }
}

/** Un aller-retour avec le service worker, avec un délai de garde. */
function demanderAuServiceWorker(message, delaiMs = 20_000) {
  return new Promise((resoudre) => {
    let canal;
    try {
      canal = new MessageChannel();
    } catch {
      resoudre(null);
      return;
    }
    // Sans ce minuteur, un service worker qui ne répond pas laisserait le
    // bouton bloqué sur « Mise à jour… » pour toujours.
    const minuteur = setTimeout(() => resoudre(null), delaiMs);
    canal.port1.onmessage = (e) => { clearTimeout(minuteur); resoudre(e.data); };
    try {
      navigator.serviceWorker.controller.postMessage(message, [canal.port2]);
    } catch {
      clearTimeout(minuteur);
      resoudre(null);
    }
  });
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

// L'invite d'installation de Chrome Android, si le navigateur nous la donne.
// On la RETIENT au lieu de la laisser partir : le bandeau devient alors un
// vrai bouton qui ouvre l'invite native — un geste au lieu de trois.
let inviteInstallation = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  inviteInstallation = e;
  proposerLInstallation();
});

function proposerLInstallation() {
  const installee = window.matchMedia("(display-mode: standalone)").matches ||
                    window.navigator.standalone === true;
  // iPhone ET Android (audit du 30/08 — le bandeau ne visait qu'iOS, un
  // bénévole Android n'avait aucune indication). Installer n'est pas
  // cosmétique : un navigateur efface le stockage d'un site peu visité, ce
  // qui emporterait la file ; une PWA installée est protégée.
  const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const android = /Android/.test(navigator.userAgent);
  const bandeau = $("installer");
  bandeau.hidden = installee || !(iOS || android);
  if (bandeau.hidden) return;

  if (inviteInstallation) {
    // Chrome Android nous laisse déclencher l'invite : le bandeau devient
    // un bouton.
    bandeau.textContent = "Installer l'application sur ce téléphone — un appui suffit.";
    bandeau.style.cursor = "pointer";
    bandeau.onclick = async () => {
      const invite = inviteInstallation;
      inviteInstallation = null;
      invite.prompt();
      const choix = await invite.userChoice;
      if (choix.outcome === "accepted") bandeau.hidden = true;
    };
  } else if (android) {
    bandeau.textContent = "Ajoute cette page à ton écran d'accueil (menu ⋮ → " +
      "« Ajouter à l'écran d'accueil ») : elle s'ouvrira comme une application, " +
      "et gardera tes scans même sans réseau.";
  }
  // Sur iOS, le texte du bandeau écrit dans la page convient tel quel.
}

async function demarrer() {
  const jeton = installerLeJeton();
  api = new Api({ jeton });
  file = new FileDeReussites(new MagasinIdb(MAGASINS.file),
                             new MagasinIdb(MAGASINS.refusees));
  historique = new Historique(new MagasinIdb(MAGASINS.historique));
  // ⚠️ La version voyage AUSSI avec les lots, et c'est délibérément redondant
  // (spec 030, F8) : l'annonce normale passe par un `GET`, qu'un cache posé un
  // jour devant `/api/v2/catalog` absorberait sans que rien ne le dise. Un
  // `POST` n'est jamais mis en cache — tant que des réussites partent, la
  // console sait au moins quelle version tourne sur ce téléphone.
  expediteur = new Expediteur(file, api, {
    identite: () => ({ ...identite, app: VERSION_APP }),
  });

  if (!jeton) {
    dire("Cette application a besoin du lien fourni par l'organisateur.", "attention");
    // Et on donne le geste qui repare, plutot que de laisser sur un constat.
    $("relier").hidden = false;
  }

  $("btnRelier").addEventListener("click", relier);

  try {
    catalogue = Catalogue.depuisJson(await reglages.lire(CLE_CATALOGUE));
    identite = await identiteCourante(reglages);
    etat.garderGrimpeur = (await reglages.lire("garder-grimpeur")) === true;
    // Les deux dates survivent au redémarrage : « reçu il y a 1 h » reste vrai
    // après avoir fermé et rouvert l'application.
    catalogueRecuMs = Number(await reglages.lire(CLE_CATALOGUE_RECU)) || 0;
    catalogueVuMs = Number(await reglages.lire(CLE_CATALOGUE_VU)) || 0;
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
  $("forcerCatalogue").addEventListener("click", forcerLeCatalogue);
  $("majApplication").addEventListener("click", mettreAJourLApplication);

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
  enregistrerLeServiceWorker();
}

/**
 * Ce qui rend l'application utilisable sans réseau.
 *
 * Enregistré **après** le démarrage : un échec ici ne doit jamais empêcher
 * l'application de fonctionner. Un juge dont le navigateur refuse les service
 * workers — mode privé, réglage d'entreprise — doit pouvoir travailler quand
 * même, simplement sans le hors-ligne.
 */
function enregistrerLeServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/juge/sw.js", { scope: "/juge" })
    .catch(() => { /* pas de hors-ligne, mais l'application marche */ });
}

// ⚠️ `finally`, pas `then` : `demarrer()` sort tot quand il n'y a pas de jeton,
// et peut echouer. Dans les trois cas l'ecran d'accueil doit s'effacer -- un
// logo bloque sur un ecran est pire qu'une application qui affiche son
// probleme.
demarrer().finally(() => {
  window.dispatchEvent(new Event("climbcontest:pret"));
});
