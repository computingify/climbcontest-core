/**
 * L'écran du juge. Ce qui orchestre, et rien qui décide.
 *
 * Tout ce qui se décide vit ailleurs et se teste sur Node : [jeton.js] pour le
 * jeton, [api.js] pour le dialogue HTTP, [scan.js] pour la lecture du QR. Ici,
 * on branche des boutons.
 *
 * ⚠️ IT1 de la spec 007 : l'envoi part **directement**. La file d'attente
 * persistante arrive en IT2 — d'ici là, cette PWA a besoin du réseau au moment
 * d'envoyer, contrairement à l'application Android. C'est dit à l'écran.
 */
import { CLE_RANGEMENT, choisirJeton } from "./jeton.js";
import { Api } from "./api.js";
import { expliquerLErreurCamera, lireUnQr } from "./scan.js";

const $ = (id) => document.getElementById(id);

const etat = { dossard: null, grimpeur: null, bloc: null, envoiEnCours: false };
let api = null;
let annulation = null;

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
 * remplacé.
 *
 * C'est exactement le geste qu'on fera si un jeton est révoqué en pleine
 * compétition : envoyer un nouveau lien aux juges. Sans ce branchement, ceux
 * qui ont déjà l'application ouverte l'auraient ouvert pour rien.
 */
function surNouveauLien() {
  window.addEventListener("hashchange", () => {
    const jeton = installerLeJeton();
    api = new Api({ jeton });
    if (jeton) {
      dire("Nouveau lien pris en compte.", "ok");
      voyant("doute");
      verifierLaPresence();
    }
  });
}

// --- Le voyant de connexion -------------------------------------------------

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
  // Un refus reste affiché : le juge doit avoir le temps de le lire, et
  // souvent d'aller voir un organisateur. Un succès s'efface tout seul.
  if (genre === "ok") effacementDuMessage = setTimeout(() => { m.hidden = true; }, 3000);
}

// --- L'écran ----------------------------------------------------------------

function redessiner() {
  const grimpeurFait = etat.dossard !== null;
  const blocFait = etat.bloc !== null;

  $("carteGrimpeur").classList.toggle("fait", grimpeurFait);
  $("valeurGrimpeur").textContent = etat.grimpeur || etat.dossard || "À scanner";
  $("valeurGrimpeur").classList.toggle("attente", !grimpeurFait);
  // Le dossard en second, quand on a le nom : c'est le nom que le juge lit pour
  // confirmer qu'il a scanné la bonne personne.
  $("detailGrimpeur").textContent = grimpeurFait && etat.grimpeur ? `n°${etat.dossard}` : "";

  $("carteBloc").classList.toggle("fait", blocFait);
  $("valeurBloc").textContent = etat.bloc || "À scanner";
  $("valeurBloc").classList.toggle("attente", !blocFait);

  const pret = grimpeurFait && blocFait && !etat.envoiEnCours;
  $("envoyer").disabled = !pret;
  $("aide").hidden = pret;
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

  const verdict = quoi === "grimpeur"
    ? await api.verifierGrimpeur(code)
    : await api.verifierBloc(code);

  if (verdict.ok) {
    voyant("ok");
    if (quoi === "grimpeur") { etat.dossard = code; etat.grimpeur = verdict.libelle || null; }
    else { etat.bloc = verdict.libelle || code; }
    redessiner();
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

// --- Envoyer ----------------------------------------------------------------

async function envoyer() {
  if (etat.dossard === null || etat.bloc === null || etat.envoiEnCours) return;
  etat.envoiEnCours = true;
  redessiner();

  const ref = (crypto.randomUUID && crypto.randomUUID()) ||
              String(Date.now()) + Math.random().toString(16).slice(2);
  const resultat = await api.envoyerLot(
    [{ ref, bib: etat.dossard, bloc: etat.bloc, at: new Date().toISOString() }],
  );

  etat.envoiEnCours = false;

  if (resultat.ok && resultat.acquittees.has(ref)) {
    const refus = resultat.refusees.find((r) => r.ref === ref);
    if (refus) {
      voyant("ok");
      dire(refus.message || "Réussite refusée par le serveur.", "erreur");
      redessiner();
      return;
    }
    voyant("ok");
    dire("Validé", "ok");
    effacer();
    return;
  }

  // L'écran ne se vide QUE sur un succès confirmé. Effacer après un échec
  // perdrait la réussite sans que personne ne s'en aperçoive.
  voyant("ko");
  dire(resultat.message || "Envoi impossible. Réessaie.", "erreur");
  redessiner();
}

// --- Démarrage --------------------------------------------------------------

function proposerLInstallation() {
  const installee = window.matchMedia("(display-mode: standalone)").matches ||
                    window.navigator.standalone === true;
  // On ne le propose qu'aux iPhone : ailleurs, le navigateur le propose seul,
  // et un bandeau de plus n'apprendrait rien.
  const iOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  $("installer").hidden = installee || !iOS;
}

async function verifierLaPresence() {
  // Le catalogue plutôt que /health : `/health` est fermé depuis Internet, et
  // les téléphones des juges sont sur le wifi de la salle. Le sondage dirait
  // « injoignable » en permanence pendant que tout fonctionne — la leçon
  // apprise côté Android le 29/08.
  const r = await api.telechargerCatalogue(null);
  voyant(r.etat === "echec" ? "ko" : "ok");
}

function demarrer() {
  const jeton = installerLeJeton();
  api = new Api({ jeton });

  if (!jeton) {
    dire("Cette application a besoin du lien fourni par l'organisateur.", "attention");
  }

  $("carteGrimpeur").addEventListener("click", () => scanner("grimpeur"));
  $("carteBloc").addEventListener("click", () => scanner("bloc"));
  $("envoyer").addEventListener("click", envoyer);
  $("effacer").addEventListener("click", effacer);
  $("annulerScan").addEventListener("click", () => annulation && annulation.abort());

  surNouveauLien();
  proposerLInstallation();
  redessiner();
  verifierLaPresence();

  // Le voyant ne vit qu'au premier plan : en arrière-plan personne ne le
  // regarde, et un voyant figé vaut moins que pas de voyant. Au retour, on
  // repart de « je vérifie » plutôt que d'afficher l'état d'avant la veille.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      voyant("doute");
      verifierLaPresence();
    }
  });
}

demarrer();
