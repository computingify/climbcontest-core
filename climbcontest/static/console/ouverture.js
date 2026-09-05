/**
 * L'écran d'ouverture — spec 044.
 *
 * Le plan de la salle comme surface de saisie : on touche une zone, elle
 * s'ouvre par-dessus, on y déclare ses voies.
 *
 * ⚠️ **Le plan n'est pas redessiné ici.** `resultats/plan.js` sait déjà décrire
 * un SVG à partir d'un document `plan_public()`, le monter et le décorer zone
 * par zone. Ce module l'appelle. Ce qui diffère est ce que la pastille COMPTE —
 * « complètes / déclarées » au lieu de « réussis / à faire » — et c'est un
 * argument de `decorer`, pas une deuxième implémentation.
 *
 * ⚠️ **Les identifiants sont préfixés `ouvreurs`.** Deux autres branches
 * travaillaient dans `admin.html` pendant l'écriture de ce lot : git fusionne
 * sans conflit deux fonctions du même nom ajoutées à des endroits différents,
 * et la seconde écrase la première en silence.
 */

import { confirmerParGeste } from "/static/console/confirmer.js";
import { decorer, decrire, monter, peutDessiner, tailleDuCompte }
  from "/static/resultats/plan.js";

/** Les six couleurs, dans l'ordre de `classement.COULEURS`. */
const COULEURS = [
  { nom: "Jaune", teinte: "#E8C33A" }, { nom: "Vert", teinte: "#3FA45B" },
  { nom: "Bleu", teinte: "#2E74C9" }, { nom: "Mauve", teinte: "#8250B4" },
  { nom: "Rouge", teinte: "#C93B32" }, { nom: "Noir", teinte: "#23262B" },
];

/** Le nuancier des couleurs de prises.
 *
 * Rien d'ordonné : c'est ce qu'on cherche des yeux sur le mur, ça n'entre dans
 * aucun calcul — contrairement aux six couleurs de difficulté, que le
 * classement lit.
 *
 * ⚠️ DES TEINTES DISTINCTES, PAS DES NUANCES. Adrien, le 05/09 : « il ne faut
 * pas qu'il y ait trop de choix, ce ne sont que des prises d'escalade ; donc
 * proposer 10 nuances de rouge n'est pas nécessaire, mais du rouge et du rose
 * oui ». Quinze teintes qu'on distingue à trois mètres et qu'on sait nommer —
 * pas un dégradé.
 */
const PRISES = [
  { nom: "Blanc", teinte: "#F2F0EA" }, { nom: "Gris", teinte: "#9AA0A6" },
  { nom: "Noir", teinte: "#23262B" }, { nom: "Beige", teinte: "#D9C4A0" },
  { nom: "Marron", teinte: "#7A5230" }, { nom: "Jaune", teinte: "#E8C33A" },
  { nom: "Fluo", teinte: "#C9F03A" }, { nom: "Orange", teinte: "#EE8A2E" },
  { nom: "Rouge", teinte: "#C93B32" }, { nom: "Rose", teinte: "#E8709F" },
  { nom: "Violet", teinte: "#7B4FC0" }, { nom: "Bleu", teinte: "#2E74C9" },
  { nom: "Turquoise", teinte: "#23A8B4" }, { nom: "Mint", teinte: "#8FD9B6" },
  { nom: "Vert", teinte: "#3FA45B" },
];

/* ⚠️ Les quinze sont RELEVÉES sur les trois classeurs archivés, pas inventées.
   Le club pose : Orange, Blanc, Vert, Rouge, Gris, Rose, Jaune, Noir, Violet,
   Bleu — et « Mint », une seule fois. Une couleur écrite une fois est une
   couleur qu'on doit pouvoir réécrire, donc elle est là.
   « Fuchsia » a sauté : le club n'en pose pas, et à côté de « Rose » c'était
   exactement la nuance de trop que la demande écarte. */

/** Celles qu'on voit sans rien demander. Le reste est derrière « Personnaliser ».
 *
 * ⚠️ Sept, et ce sont exactement celles d'avant le nuancier : l'écran de
 * tous les jours ne doit pas grandir parce qu'un choix rare est devenu
 * possible. */
const PRISES_COURANTES = ["Blanc", "Jaune", "Fluo", "Bleu", "Rouge", "Noir", "Gris"];

/** Deux couleurs au plus par prise — le même plafond que le serveur. */
const PRISES_MAXI = 2;

const teintePrise = (nom) => (PRISES.find((p) => p.nom === nom) || {}).teinte;

/** La pastille d'une prise. **UNE** pastille, jamais deux.
 *
 * ⚠️ C'est la correction du 05/09 : « pour ces double couleur, elles sont
 * vraiment sur la prise, donc il faut l'afficher dans une pastille, pas 2 ».
 * Une prise bicolore est **un objet** qu'on cherche des yeux sur le mur — pas
 * deux prises côte à côte. Deux pastilles racontaient deux prises.
 *
 * Une couleur à gauche, l'autre à droite, séparées par un **oblique à 45°**.
 *
 * ⚠️ Une coupe FRANCHE, et un filet dessus : deux teintes qui se fondent l'une
 * dans l'autre en font une troisième, et on chercherait sur le mur une couleur
 * qui n'existe pas. Le filet évite en plus qu'un blanc sur un jaune pâle
 * ressemble à une pastille unie.
 */
export function fondDePrises(teintes) {
  if (teintes.length < 2) return teintes[0] || "var(--surface3)";
  return `linear-gradient(135deg, ${teintes[0]} 0 calc(50% - 0.5px),`
       + ` var(--pastille-filet) calc(50% - 0.5px) calc(50% + 0.5px),`
       + ` ${teintes[1]} calc(50% + 0.5px) 100%)`;
}

function pastilleDePrises(noms, classe) {
  const n = el("i", { class: classe });
  n.style.background = fondDePrises(
    noms.map((x) => teintePrise(x) || "var(--surface3)"));
  if (noms.length > 1) n.classList.add("bicolore");
  return n;
}

const PROFILS = { dalle: "Dalle", vertical: "Vertical", incline: "Incliné",
                  devers: "Dévers", surplomb: "Surplomb", toit: "Toit" };

let etat = null;          // le dernier inventaire reçu
let zoneOuverte = null;   // la zone dont le tiroir est ouvert
let voieOuverte = null;   // la voie dont la fiche est ouverte

const $ = (id) => document.getElementById(id);

/* Le pont avec le script classique de la console : c'est lui qui porte la
   session et le rapport d'erreur. Un module ne peut pas l'importer — il n'est
   pas un module — donc on passe par la fenêtre, explicitement et une seule
   fois. */
const appeler = (chemin, options) => window.consoleAppeler(chemin, options);

function el(tag, attrs, texte) {
  const n = document.createElement(tag);
  for (const k in (attrs || {})) {
    if (k === "class") n.className = attrs[k];
    else n.setAttribute(k, String(attrs[k]));
  }
  if (texte !== undefined) n.textContent = texte;
  return n;
}

const teinteDe = (nom) => (COULEURS.find((c) => c.nom === nom) || {}).teinte;

/** Zone → le nombre de voies qu'elle porte.
 *
 * ⚠️ UN COMPTE, PAS UN AVANCEMENT, et c'est une correction du 05/09. La zone
 * portait « 3/5 » sur une pastille qui se remplissait de vert — la jauge de la
 * spec 036. Adrien : « les ouvreurs ne savent pas à l'avance ce qu'ils vont
 * ouvrir et où ». Il a raison, et c'est structurel : une jauge suppose un total
 * connu d'avance. Ici le dénominateur, c'est ce qui a été tapé jusqu'ici — il
 * grandit à chaque voie ajoutée. « 3/5 » se lisait « tu es à 60 % de la zone J »
 * alors que personne ne sait ce que vaut la zone J.
 *
 * Ce qui reste vrai, et qu'on garde : une voie DÉJÀ déclarée à laquelle il
 * manque une couleur ou une catégorie. Ça, ce n'est pas une prédiction, c'est
 * du travail sur quelque chose qui existe — et c'est le liseré ambre.
 */
export function comptesDeZones(zones) {
  const comptes = {};
  for (const lettre in zones) {
    if (zones[lettre].length) comptes[lettre] = zones[lettre].length;
  }
  return comptes;
}

/** Les zones où au moins une voie déclarée reste à compléter. */
export function zonesACompleter(zones) {
  return Object.keys(zones).filter(
    (z) => zones[z].some((v) => !v.complete)).sort();
}

/** Les zones que le plan porte et qu'aucune voie n'occupe, et l'inverse.
 *
 * ⚠️ Une voie dans une zone que le plan ne dessine plus ne disparaît pas de
 * l'écran : elle remonte dans un bandeau. Même règle que `fiches`, qui ne fait
 * jamais disparaître un bloc en silence.
 */
export function horsPlan(zones, plan) {
  const dessinees = new Set((plan && plan.murs || []).map((m) => m.zone));
  return Object.keys(zones).filter((z) => z && !dessinees.has(z)).sort();
}

// --- Le plan ----------------------------------------------------------------

function dessinerPlan() {
  const hote = $("ouvreursPlan");
  hote.textContent = "";
  if (!peutDessiner(etat.plan)) {
    hote.appendChild(el("p", { class: "aide" },
      "Le plan de la salle n'est pas lisible : les voies restent modifiables "
      + "par la liste ci-dessous."));
    return;
  }
  const svg = monter(decrire(etat.plan), document);
  svg.addEventListener("click", (e) => {
    const groupe = e.target.closest("[data-zone]");
    if (groupe) ouvrirZone(groupe.getAttribute("data-zone"));
  });
  hote.appendChild(svg);
  decorerPlan();
}

function decorerPlan() {
  const svg = $("ouvreursPlan").querySelector("svg");
  if (!svg) return;
  const comptes = comptesDeZones(etat.zones);
  const etats = {};
  for (const lettre in comptes) etats[lettre] = "reste";   // allumée, point.

  // ⚠️ `decorer` est appelé SANS `comptes` : sa pastille écrit « faits/total »
  // et remplit une jauge de vert, ce qui est juste sur la fiche du grimpeur
  // (spec 036) et faux ici. On lui laisse les classes d'état, et on pose le
  // compte nous-mêmes juste après — `suivi.js` et `plan.js` restent intacts
  // pour la page de résultats, qui, elle, a bien un total connu.
  decorer(svg, etats, zoneOuverte);
  poserComptes(svg, comptes);
}

/** Le nombre de voies, dans la pastille — sans jauge. */
function poserComptes(svg, comptes) {
  const aCompleter = new Set(zonesACompleter(etat.zones));
  for (const n of svg.querySelectorAll("[data-zone]")) {
    const zone = n.getAttribute("data-zone");
    const combien = comptes[zone];
    n.classList.toggle("a-compte", !!combien);
    n.classList.toggle("ouvreurs-a-completer", aCompleter.has(zone));
    const chiffre = n.querySelector(".compte-zone");
    if (!chiffre) continue;
    chiffre.textContent = combien ? String(combien) : "";
    if (combien) {
      chiffre.setAttribute("font-size",
        tailleDuCompte(chiffre.getAttribute("data-corps"), String(combien)).toFixed(2));
    }
    // La jauge reste VIDE : elle n'a plus rien à mesurer.
    const jauge = n.querySelector(".remplit-compte");
    if (jauge) jauge.setAttribute("width", "0");
  }
}

// --- Le tiroir --------------------------------------------------------------

function fermerTiroir() {
  zoneOuverte = voieOuverte = null;
  $("ouvreursCorps").classList.remove("avec-tiroir", "avec-fiche");
  $("ouvreursTiroir").hidden = true;
  $("ouvreursVoile").hidden = true;
  decorerPlan();
}

function ouvrirZone(lettre) {
  zoneOuverte = lettre;
  voieOuverte = null;
  $("ouvreursCorps").classList.add("avec-tiroir");
  $("ouvreursCorps").classList.remove("avec-fiche");
  $("ouvreursVoile").hidden = false;
  $("ouvreursTiroir").hidden = false;
  dessinerTiroir();
  decorerPlan();
}

function murDe(lettre) {
  return (etat.plan && etat.plan.murs || []).find((m) => m.zone === lettre);
}

function dessinerTiroir() {
  const voies = etat.zones[zoneOuverte] || [];
  const mur = murDe(zoneOuverte);
  const completes = voies.filter((v) => v.complete).length;

  const titre = $("ouvreursTiroirTitre");
  // ⚠️ `textContent` effacerait le `<em>` qui vit dans ce titre : on ne
  // remplace que le premier noeud de texte.
  titre.firstChild.nodeValue = "Zone " + zoneOuverte + " ";
  const reste = voies.length - completes;
  $("ouvreursTiroirSous").textContent = [
    mur && PROFILS[mur.profil],
    voies.length ? voies.length + " voie" + (voies.length > 1 ? "s" : "")
                 : "aucune voie",
    reste ? reste + " à compléter" : null,
  ].filter(Boolean).join(" · ");

  const liste = $("ouvreursListe");
  liste.textContent = "";
  if (voieOuverte) {
    liste.appendChild(fiche(voieOuverte));
    $("ouvreursPied").hidden = true;
    $("ouvreursCorps").classList.add("avec-fiche");
    return;
  }
  $("ouvreursCorps").classList.remove("avec-fiche");
  $("ouvreursPied").hidden = !etat.ecriture;
  for (const voie of voies) liste.appendChild(ligne(voie));
  if (!voies.length) {
    liste.appendChild(el("p", { class: "aide" }, "Aucune voie déclarée ici."));
  }
}

function ligne(voie) {
  const n = el("div", { class: "ouvreurs-voie" + (voie.complete ? "" : " incomplete") });
  const pastille = el("span", { class: "ouvreurs-couleur" });
  if (voie.couleur) pastille.style.background = teinteDe(voie.couleur);
  else pastille.classList.add("vide");

  const quoi = el("span", { class: "ouvreurs-quoi" });
  quoi.appendChild(el("b", {}, voie.couleur || "couleur à choisir"));
  quoi.append(" · ");
  const prises = voie.couleurs_prises || [];
  if (prises.length) {
    quoi.append("prises ",
                pastilleDePrises(prises, "ouvreurs-rond-prise"),
                prises.join(" et "));
  } else {
    quoi.append("prises ?");
  }
  const cats = el("span", { class: "ouvreurs-cats" });
  if (voie.circuits.length) {
    for (const c of voie.circuits) cats.appendChild(el("span", { class: "ouvreurs-cat" }, c));
  } else {
    cats.appendChild(el("span", { class: "ouvreurs-cat" }, "aucune catégorie"));
  }
  // Le contenu RÉEL du QR, en chasse fixe : c'est ce que le juge scanne, et
  // c'est là qu'une faute de zone se voit.
  cats.appendChild(el("span", { class: "ouvreurs-qr" },
                      voie.nom ? "QR " + voie.tag : "sans n°"));
  quoi.appendChild(cats);

  n.append(pastille, el("span", { class: "ouvreurs-num" }, voie.nom || "—"), quoi,
           el("span", { class: "ouvreurs-etat " + (voie.complete ? "ok" : "reste") },
              voie.complete ? "✓" : "à compléter"));
  if (etat.ecriture) {
    n.tabIndex = 0;
    n.setAttribute("role", "button");
    n.addEventListener("click", () => { voieOuverte = voie; dessinerTiroir(); });
    n.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); n.click(); }
    });
  }
  return n;
}

function jetons(titre, valeurs, choisi, surChoix, teintes) {
  const bloc = el("div", {});
  bloc.appendChild(el("div", { class: "ouvreurs-rub" }, titre));
  const rangee = el("div", { class: "ouvreurs-jetons" });
  for (const v of valeurs) {
    const actif = Array.isArray(choisi) ? choisi.includes(v) : choisi === v;
    const j = el("button", { type: "button",
                             class: "ouvreurs-jeton" + (actif ? " choisi" : ""),
                             "aria-pressed": actif ? "true" : "false" });
    if (teintes) {
      const pastille = el("i", {});
      pastille.style.background = teinteDe(v);
      j.appendChild(pastille);
    }
    j.append(v);
    // Retoucher un jeton déjà choisi le RETIRE : c'est ainsi qu'on vide une
    // couleur ou qu'on décoche une catégorie, sans bouton « effacer ».
    j.addEventListener("click", () => surChoix(v, actif));
    rangee.appendChild(j);
  }
  bloc.appendChild(rangee);
  return bloc;
}

/** Les prises : les sept courantes, et le nuancier derrière un bouton.
 *
 * ⚠️ Une valeur DÉJÀ POSÉE est toujours montrée, même hors des courantes et
 * même absente du nuancier. Une couleur venue du classeur — le nuancier ne
 * connaît pas tous les mots qu'on a pu y taper — disparaîtrait sinon de
 * l'écran tout en restant en base : on la lirait sur l'étiquette imprimée sans
 * pouvoir la retrouver dans la console.
 */
function jetonsPrises(voie) {
  const posees = voie.couleurs_prises || [];
  const visibles = PRISES_COURANTES.slice();
  for (const p of posees) if (visibles.indexOf(p) === -1) visibles.push(p);
  const plein = posees.length >= PRISES_MAXI;

  const bloc = el("div", {});
  const rub = el("div", { class: "ouvreurs-rub" }, "Couleur des prises");
  // ⚠️ L'APERÇU DE LA PRISE, en UNE pastille. Les jetons ci-dessous sont un
  // sélecteur : deux d'entre eux s'allument, et deux jetons allumés racontent
  // deux prises. Celle-ci dit ce qu'on a réellement posé sur le mur — un objet,
  // deux couleurs, séparées par un oblique à 45°.
  if (posees.length) {
    rub.appendChild(pastilleDePrises(posees, "ouvreurs-apercu-prise"));
    // Le NOM ne prend pas les capitales de la rubrique : « BLANC ET FLUO »
    // crie, et ce n'est pas un titre, c'est une valeur.
    rub.appendChild(el("span", { class: "ouvreurs-valeur-prise" },
                       posees.join(" et ")));
  }
  bloc.appendChild(rub);
  const rangee = el("div", { class: "ouvreurs-jetons" });

  const poser = (nom) => {
    const actif = posees.indexOf(nom) !== -1;
    // ⚠️ Quand deux couleurs sont posées, les autres deviennent INERTES au
    // lieu d'en remplacer une au hasard. Un troisième appui qui chasse
    // silencieusement l'une des deux fait disparaître un choix sans dire
    // lequel ; mieux vaut un geste de plus et savoir ce qu'on retire.
    const inerte = plein && !actif;
    const j = el("button", { type: "button",
                             class: "ouvreurs-jeton" + (actif ? " choisi" : "")
                                    + (inerte ? " inerte" : ""),
                             "aria-pressed": actif ? "true" : "false" });
    if (inerte) j.disabled = true;
    const rond = el("i", {});
    rond.style.background = teintePrise(nom) || "var(--surface3)";
    j.appendChild(rond);
    j.append(nom);
    j.addEventListener("click", () => {
      const suite = actif ? posees.filter((p) => p !== nom)
                          : posees.concat([nom]);
      envoyer(voie, { couleur_prises: suite });
    });
    return j;
  };
  for (const nom of visibles) rangee.appendChild(poser(nom));

  const plus = el("button", { type: "button", class: "ouvreurs-jeton",
                              "aria-expanded": "false" }, "Personnaliser…");
  const nuancier = el("div", { class: "ouvreurs-jetons ouvreurs-nuancier",
                               hidden: "hidden" });
  for (const p of PRISES) {
    if (visibles.indexOf(p.nom) !== -1) continue;
    nuancier.appendChild(poser(p.nom));
  }
  plus.addEventListener("click", () => {
    nuancier.hidden = !nuancier.hidden;
    plus.setAttribute("aria-expanded", nuancier.hidden ? "false" : "true");
  });
  rangee.appendChild(plus);

  bloc.append(rangee, nuancier);
  // Une prise BICOLORE est une prise à deux couleurs, pas deux prises : on le
  // dit là où le geste se fait, pas dans une aide qu'on ne lit pas.
  bloc.appendChild(el("p", { class: "ouvreurs-note-prises" },
    plein ? "Deux couleurs : c'est le maximum. Retires-en une pour changer."
          : "Une prise bicolore ? Choisis une seconde couleur."));
  return bloc;
}

function fiche(voie) {
  const n = el("div", { class: "ouvreurs-fiche" });
  n.appendChild(jetons("Couleur de difficulté", COULEURS.map((c) => c.nom),
    voie.couleur,
    (v, actif) => envoyer(voie, { couleur: actif ? null : v }), true));
  n.appendChild(jetonsPrises(voie));
  n.appendChild(jetons("Catégories", etat.circuits.map((c) => c.nom), voie.circuits,
    (v, actif) => {
      const suite = actif ? voie.circuits.filter((c) => c !== v)
                          : voie.circuits.concat([v]);
      envoyer(voie, { circuits: suite });
    }));

  const dit = el("p", { class: "ouvreurs-attribue" });
  if (voie.nom) {
    dit.append("Numéro attribué : ");
    dit.appendChild(el("b", {}, voie.nom));
    dit.append(" — le premier libre en " + voie.couleur + ". Le QR portera ");
    dit.appendChild(el("b", {}, voie.tag));
    dit.append(".");
  } else {
    dit.className = "aide";
    dit.textContent = "Le numéro s'attribuera dès qu'une couleur sera choisie.";
  }
  n.appendChild(dit);

  const actions = el("div", { class: "ouvreurs-actions" });
  const retour = el("button", { type: "button", class: "secondaire" },
                    "← Retour à la zone");
  retour.addEventListener("click", () => { voieOuverte = null; dessinerTiroir(); });
  actions.appendChild(retour);

  // ⚠️ Bouton ORDINAIRE, pas le geste de confirmation : supprimer une voie se
  // rattrape, et elle est déjà refusée dès qu'une réussite existe. Le maintien
  // est réservé à ce qui ne se rattrape pas -- la règle est dans `admin.html`.
  if (!voie.reussites) {
    const jeter = el("button", { type: "button", class: "ouvreurs-danger" },
                     "Supprimer");
    jeter.addEventListener("click", () => {
      appeler("/admin/ouverture/voies/" + voie.id, { methode: "DELETE" })
        .then((r) => { if (r) { voieOuverte = null; poser(r); } });
    });
    actions.appendChild(jeter);
  } else {
    actions.appendChild(el("span", { class: "aide" },
      voie.reussites + " réussite(s) : cette voie ne se modifie plus."));
  }
  n.appendChild(actions);
  return n;
}

function envoyer(voie, corps) {
  appeler("/admin/ouverture/voies/" + voie.id, { methode: "POST", corps })
    .then((r) => {
      if (!r) return;
      poser(r);
      // La fiche reste ouverte sur la MÊME voie, rechargée : sans ça, chaque
      // jeton refermerait l'écran qu'on est en train de remplir.
      const voies = etat.zones[zoneOuverte] || [];
      voieOuverte = voies.find((v) => v.id === voie.id) || null;
      dessinerTiroir();
    });
}

// --- Le résumé et la renumérotation -----------------------------------------

function dessinerResume() {
  const t = etat.totaux;
  const r = $("ouvreursResume");
  r.textContent = "";
  r.appendChild(el("b", {}, t.voies + " voies"));
  r.append(" sur " + t.zones_saisies + " zones");
  if (t.a_completer) {
    r.append(" · ");
    r.appendChild(el("span", { class: "reste" }, t.a_completer + " à compléter"));
  } else if (t.voies) {
    r.append(" · ");
    r.appendChild(el("span", { class: "fini" }, "tout est complet"));
  }

  const barres = $("ouvreursRepartition");
  barres.textContent = "";
  const haut = Math.max(1, ...COULEURS.map((c) => t.par_couleur[c.nom] || 0));
  for (const c of COULEURS) {
    const combien = t.par_couleur[c.nom] || 0;
    const col = el("div", { class: "ouvreurs-col" });
    const tige = el("div", { class: "ouvreurs-tige" });
    const barre = el("i", {});
    barre.style.background = c.teinte;
    barre.style.height = Math.round(100 * combien / haut) + "%";
    tige.appendChild(barre);
    col.append(tige, el("b", {}, String(combien)), el("span", {}, c.nom));
    barres.appendChild(col);
  }

  const restantes = Object.keys(etat.zones).sort().filter((z) => {
    const v = etat.zones[z];
    return v.length && v.some((x) => !x.complete);
  });
  const bande = $("ouvreursRestantes");
  bande.textContent = "";
  bande.hidden = !restantes.length;
  if (restantes.length) {
    bande.append("À compléter : ");
    for (const z of restantes) {
      const p = el("button", { type: "button", class: "ouvreurs-puce" }, z);
      p.addEventListener("click", () => ouvrirZone(z));
      bande.appendChild(p);
    }
  }

  const dehors = horsPlan(etat.zones, etat.plan);
  const alerte = $("ouvreursHorsPlan");
  alerte.hidden = !dehors.length;
  if (dehors.length) {
    alerte.textContent = "Des voies sont déclarées dans des zones que le plan "
      + "ne dessine pas : " + dehors.join(", ") + ". Elles ne sont pas perdues.";
  }
}

function ouvrirRenumerotation() {
  appeler("/admin/ouverture/renumeroter?apercu=1", { methode: "POST" })
    .then((r) => {
      if (!r) return;
      const boite = $("ouvreursDlgRenum");
      $("ouvreursRenumTitre").textContent =
        "Renuméroter les " + etat.totaux.voies + " voies ?";
      const avert = $("ouvreursRenumAvert");
      avert.textContent = "";
      if (r.combien) {
        avert.appendChild(el("b", {}, r.combien + " voies changent de numéro."));
        avert.append(" Leur QR change avec — les étiquettes déjà collées sur le "
                     + "mur ne seront plus valables et sont à réimprimer.");
      } else {
        avert.textContent = "Aucun numéro ne change : la numérotation est déjà "
          + "celle-là.";
      }

      const table = $("ouvreursRenumTable");
      table.textContent = "";
      for (const c of r.changements.slice(0, 8)) {
        const tr = el("tr", {});
        tr.append(el("td", { class: "zone" }, c.zone), el("td", {}, c.avant),
                  el("td", { class: "fleche" }, "→"), el("td", {}, c.apres));
        table.appendChild(tr);
      }
      if (r.changements.length > 8) {
        const tr = el("tr", {});
        tr.append(el("td", { class: "zone" }, "…"), el("td", {}, "…"),
                  el("td", {}, ""), el("td", {}, "…"));
        table.appendChild(tr);
      }

      // ⚠️ Le geste est reconstruit à chaque ouverture : un geste déjà abouti
      // reste désactivé, et le réutiliser rendrait le bouton inerte.
      confirmerParGeste($("ouvreursRenumGeste"), {
        libelle: "Maintenir 2 s pour renuméroter",
        libelleGlisse: "Glisser pour renuméroter",
        surAbout: () => {
          appeler("/admin/ouverture/renumeroter", { methode: "POST" })
            .then((rep) => { if (rep) { boite.close(); poser(rep); } });
        },
      });
      boite.showModal();
    });
}

// --- Entrée -----------------------------------------------------------------

function poser(reponse) {
  etat = reponse;
  dessinerResume();
  dessinerPlan();
  $("ouvreursLectureSeule").hidden = etat.ecriture;
  $("ouvreursRenumeroter").disabled = !etat.ecriture || !etat.totaux.voies;
  if (zoneOuverte && etat.zones[zoneOuverte]) dessinerTiroir();
  else if (zoneOuverte) fermerTiroir();
}

export function charger() {
  return appeler("/admin/ouverture").then((r) => { if (r) poser(r); });
}

function brancher() {
  $("ouvreursFermerTiroir").addEventListener("click", fermerTiroir);
  $("ouvreursVoile").addEventListener("click", fermerTiroir);
  $("ouvreursAjouter").addEventListener("click", () => {
    appeler("/admin/ouverture/voies", { methode: "POST", corps: { zone: zoneOuverte } })
      .then((r) => {
        if (!r) return;
        poser(r);
        const voies = etat.zones[zoneOuverte] || [];
        voieOuverte = voies.find((v) => v.id === r.id) || null;
        dessinerTiroir();
      });
  });
  $("ouvreursRenumeroter").addEventListener("click", ouvrirRenumerotation);
  $("ouvreursAjouterCategorie").addEventListener("click", () => {
    const nom = ($("ouvreursNouvelleCategorie").value || "").trim();
    if (!nom) return;
    appeler("/admin/ouverture/circuits", { methode: "POST", corps: { nom } })
      .then((r) => { if (r) { $("ouvreursNouvelleCategorie").value = ""; poser(r); } });
  });
}

brancher();
window.ouvreursEcran = { charger };

/* ⚠️ Le geste, expose a la console.
 *
 * La carte du mode sans classeur (spec 045) vit dans le script CLASSIQUE
 * d'`admin.html`, qui ne peut pas importer un module. Plutot que d'ajouter un
 * second <script type="module"> pour une seule fonction, ce module -- qui
 * l'importe deja -- la pose sur la fenetre. Un seul pont, au meme endroit que
 * l'autre. */
window.confirmerParGeste = confirmerParGeste;
