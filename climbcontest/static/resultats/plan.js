/**
 * Le mur, à l'écran — spec 026.
 *
 * ⚠️ CE MODULE EST ÉCRIT POUR SURVIVRE À UN CHANGEMENT DE PLAN.
 *
 * `fiches.PLAN` a déjà changé de forme une fois : une grille de 8×7 cases est
 * devenue un jeu de polygones (spec 028). C'est un relevé de salle, pas une
 * constante mathématique — il rechangera. Trois règles en découlent, et elles
 * sont la raison d'être de ce fichier :
 *
 * 1. **On vérifie le format avant de dessiner.** Le serveur estampille ce
 *    qu'il envoie (`suivi.FORMAT_PLAN`) ; si la page ne connaît pas
 *    l'estampille, elle N'AFFICHE PAS le mur. Dessiner un plan qu'on ne
 *    comprend qu'à moitié enverrait quelqu'un chercher un bloc au mauvais
 *    endroit — c'est pire que de ne rien montrer.
 * 2. **Le dessin est décrit avant d'être monté.** `decrire()` ne rend que des
 *    objets ; `monter()` les traduit en SVG. Tout ce qui décide est donc
 *    testable sans navigateur, y compris le comportement sur un plan abîmé.
 * 3. **Le lien avec les blocs passe par `data-zone`, et par rien d'autre.** La
 *    page ne connaît ni la géométrie, ni le nombre de zones, ni leur
 *    disposition. Une lettre que le plan ne porte pas rend simplement son bloc
 *    non cliquable.
 *
 *   node --test "tests/js/*.test.mjs"
 */

import { classesDeZone, libelleCompte } from "./suivi.js";

const SVG = "http://www.w3.org/2000/svg";

/** Les formats que CE fichier sait dessiner.
 *
 * Un tableau et non une constante : le jour où le serveur passe à
 * « polygones/2 », on peut accepter les deux le temps d'un déploiement, où la
 * page servie et l'API ne sont jamais mises à jour à la même seconde. */
export const FORMATS_RENDUS = ["polygones/1"];

// --- Le compteur d'avancement, spec 036 --------------------------------------
//
// « 1/4 » se pose SOUS la lettre de la zone, SUR UNE PASTILLE — un socle
// arrondi qui le détache du remplissage de profil du pan. C'est la pose B de
// `specs/036-avancement-par-zone/maquettes/compteurs.html`, tranchée par
// Adrien le 03/09 : « j'aime beaucoup la pastille que tu mets là dans
// l'écran B ».
//
// Le compteur ne connaît de la salle que ce que la lettre en connaît :
// `etiquette` (le centroïde, seul point que le serveur garantit dans le pan) et
// `taille` (le corps de la lettre, que `fiches.taille_lettre` a déjà borné par
// la boîte du pan). Aucune géométrie n'est relue ici — c'est ce qui fait qu'un
// plan redessiné ne casse rien.
//
// ⚠️ LA PASTILLE SE DIMENSIONNE SUR LA LETTRE, JAMAIS SUR SON TEXTE. C'est
// tout le point : un socle calibré sur le libellé a une largeur que rien ne
// borne, et il sortait du pan — c'est ce qui avait fait écarter la pose B à la
// première maquette. Calibré sur `taille`, il hérite des bornes que le serveur
// a déjà posées sur la lettre. Un libellé long rétrécit DANS une pastille qui,
// elle, ne bouge pas : dix-sept pastilles identiques plutôt que dix-sept
// tailles.
//
// ⚠️ CES QUATRE RATIOS SONT CALCULÉS, pas choisis à l'œil. Avec
// `dominant-baseline: central`, une capitale grasse occupe ±0,36 de son corps.
// Le budget vertical de la pastille est donc ce qui reste ENTRE le bas du
// glyphe de la lettre (0,36 × taille) et le bas du pan (0,833 × taille, la
// demi-hauteur d'un pan de 15 unités rapportée à une lettre plafonnée à 9) :
// 0,473 × taille, et pas un centième de plus. La pastille en occupe
// 1,12 × 0,40 = 0,448, centrée à 0,60 :
//
//     haut = 0,60 − 0,224 = 0,376 ≥ 0,36    elle ne mord pas la lettre
//     bas  = 0,60 + 0,224 = 0,824 ≤ 0,833   elle ne sort pas du pan
//
// Le chiffre y perd 13 % de corps par rapport au chiffre nu de la première
// maquette (0,40 au lieu de 0,46) ; c'est le prix de la pastille, et il est
// chiffré. En échange il gagne un FOND au lieu d'un halo — un contour découpé
// sur la forme des glyphes, qui se battait avec les six aplats de profil.
// `tests/test_suivi.py` relit ces nombres et vérifie la pastille pan par pan
// sur le plan réellement servi.
export const COMPTE_ECHELLE = 0.40;
export const COMPTE_DESCENTE = 0.60;
export const PASTILLE_HAUTEUR = 1.12;
export const PASTILLE_LARGEUR = 1.0;

/** L'épaisseur du halo de la LETTRE, en fraction de son corps.
 *
 * Le compteur ne l'a plus : la pastille remplace le halo, et le fait mieux. */
const HALO = 0.24;

/** La largeur d'un chiffre tabulaire, en fraction de son corps.
 *
 * Même famille de constante que `LARGEUR_CAPITALE` côté Python, et prise comme
 * elle sur le PIRE glyphe : elle sert à borner, pas à décrire. */
const LARGEUR_CHIFFRE = 0.58;

/**
 * Le corps du compteur, pour ce libellé-là.
 *
 * « 1/4 » sort à sa taille pleine ; « 12/15 » rétrécit au lieu de déborder. La
 * borne est la largeur : le libellé ne dépasse jamais une fois `taille`, ce qui
 * le garde dans le pan puisque `taille ≤ 0,94 × largeur` du pan.
 */
export function tailleDuCompte(taille, texte) {
  const corps = Number(taille) > 0 ? Number(taille) : 6;
  const n = Math.max(1, String(texte || "").length);
  return corps * Math.min(COMPTE_ECHELLE, 1 / (LARGEUR_CHIFFRE * n));
}

/** Un mur exploitable : une lettre pour le relier, une forme pour le dessiner. */
function murValide(mur) {
  return !!mur && typeof mur.zone === "string" && mur.zone !== ""
      && typeof mur.d === "string" && mur.d.includes(",");
}

/**
 * Le plan est-il de la forme qu'on sait rendre ?
 *
 * On ne se contente pas de l'estampille : un plan estampillé juste mais vidé
 * de ses murs donnerait un cadre blanc, que personne ne saurait interpréter.
 */
export function peutDessiner(plan) {
  if (!plan || typeof plan !== "object") return false;
  if (FORMATS_RENDUS.indexOf(plan.format) < 0) return false;
  if (typeof plan.cadrage !== "string" || plan.cadrage === "") return false;
  if (!Array.isArray(plan.murs)) return false;
  return plan.murs.some(murValide);
}

/** Les lettres de zone que ce plan porte réellement.
 *
 * C'est ce que la page interroge pour savoir si un bloc peut ouvrir le mur.
 * Elle le demande AU PLAN, jamais aux données des blocs : c'est le plan qui
 * sait ce qu'il sait dessiner. */
export function zonesDe(plan) {
  if (!peutDessiner(plan)) return new Set();
  return new Set(plan.murs.filter(murValide).map((m) => m.zone));
}

/**
 * Le dessin, décrit et pas encore monté : `{ tag, attrs, enfants }`.
 *
 * Rend `null` si le plan n'est pas rendable — la page n'a alors rien à
 * afficher, et c'est un état normal, pas une panne.
 *
 * ⚠️ Les murs abîmés sont IGNORÉS un par un, pas fatals. Un relevé auquel il
 * manque une lettre doit montrer les seize autres zones plutôt que rien.
 */
export function decrire(plan) {
  if (!peutDessiner(plan)) return null;

  const enfants = [];

  if (typeof plan.contour === "string" && plan.contour.includes(",")) {
    enfants.push({ tag: "polygon", attrs: { class: "contour", points: plan.contour } });
  }

  const murs = plan.murs.filter(murValide);

  for (const mur of murs) {
    const [x, y] = Array.isArray(mur.etiquette) ? mur.etiquette : [0, 0];
    const taille = Number(mur.taille) > 0 ? Number(mur.taille) : 6;
    // Le corps d'un compteur de trois caractères : celui de « 1/4 », le cas
    // courant. `decorer` le refait quand le libellé est plus long.
    const corps = tailleDuCompte(taille, "0/0");
    // ⚠️ La pastille se calcule sur le corps NOMINAL, pas sur `corps` : un
    // libellé long rétrécit le chiffre, il ne doit pas rétrécir son socle.
    // Sans ça, deux zones voisines porteraient deux pastilles de tailles
    // différentes pour dire la même chose.
    const hPastille = taille * COMPTE_ECHELLE * PASTILLE_HAUTEUR;
    const lPastille = taille * PASTILLE_LARGEUR;
    const cy = y + taille * COMPTE_DESCENTE;
    enfants.push({
      tag: "g",
      // `data-zone` sur le GROUPE et non sur le polygone : l'état efface la
      // zone ENTIÈRE — forme, trame et lettre. Une opacité posée sur le seul
      // polygone laisserait sa lettre en pleine lumière sur un mur éteint.
      attrs: { "data-zone": mur.zone, "data-profil": mur.profil || "vertical",
               // Le fragment déclare son propre centre de rotation : la page
               // anime sans avoir à mesurer quoi que ce soit.
               style: "transform-origin:" + x + "px " + y + "px" },
      enfants: [
        { tag: "polygon", attrs: { class: "mur", points: mur.d } },
        { tag: "polygon", attrs: { class: "trame", points: mur.d } },
        { tag: "text", attrs: { class: "lettre", x, y, "font-size": taille,
                                "stroke-width": (taille * HALO).toFixed(2) },
          texte: mur.zone },
        // Le compteur d'avancement est DÉCRIT VIDE et rempli par `decorer` :
        // il dépend du grimpeur, et ce dessin-ci est le même pour tout le
        // monde. C'est aussi ce qui le rend « en direct » sans rien
        // reconstruire — une réussite qui arrive pendant qu'on regarde le plan
        // ne repasse que par la décoration.
        // La pastille est DÉCRITE POUR TOUTES LES ZONES et cachée par le CSS
        // sur celles qui ne portent pas de compteur (`:not(.a-compte)`). Sa
        // géométrie ne dépend que du pan, donc elle ne change jamais : la
        // décrire une fois évite de créer et détruire un nœud à chaque
        // repeinture, exactement comme pour le chiffre.
        { tag: "rect", attrs: { class: "socle-compte",
                                x: (x - lPastille / 2).toFixed(2),
                                y: (cy - hPastille / 2).toFixed(2),
                                width: lPastille.toFixed(2),
                                height: hPastille.toFixed(2),
                                rx: (hPastille / 2).toFixed(2) } },
        // `data-corps` porte le corps de la LETTRE, seule chose dont
        // `decorer` a besoin pour redimensionner le chiffre selon sa longueur
        // sans jamais relire la géométrie du pan.
        { tag: "text", attrs: { class: "compte-zone", x, y: cy,
                                "data-corps": taille,
                                "font-size": corps.toFixed(2) },
          texte: "" },
      ],
    });
  }

  // ⚠️ LES CADRES D'ÉTAT SONT UNE COUCHE À PART, peinte après tous les murs.
  // En SVG l'ordre de peinture est l'ordre du document, et il n'y a pas de
  // `z-index` : un cadre dessiné dans le groupe de sa zone se fait rogner sur
  // les arêtes qu'elle PARTAGE avec sa voisine — et le relevé d'Annonay en
  // partage beaucoup, les murs s'y touchent bord à bord.
  enfants.push({
    tag: "g",
    attrs: { class: "cadres-zone" },
    enfants: murs.map((mur) => ({
      tag: "polygon",
      attrs: { class: "cadre-zone", points: mur.d, "data-zone": mur.zone },
    })),
  });

  for (const repere of plan.reperes || []) {
    if (!repere || typeof repere.texte !== "string") continue;
    enfants.push({
      tag: "text",
      attrs: { class: "repere-plan", x: repere.x, y: repere.y },
      texte: repere.texte,
    });
  }

  return {
    tag: "svg",
    attrs: { class: "plan", viewBox: plan.cadrage, role: "img",
             "aria-label": "Plan du mur" },
    enfants,
  };
}

/** La description, montée en vrai SVG. Dix lignes, aucune décision. */
export function monter(description, doc) {
  if (!description) return null;
  const n = doc.createElementNS(SVG, description.tag);
  for (const [cle, valeur] of Object.entries(description.attrs || {})) {
    n.setAttribute(cle, String(valeur));
  }
  if (description.texte !== undefined) n.textContent = description.texte;
  for (const enfant of description.enfants || []) {
    const monte = monter(enfant, doc);
    if (monte) n.appendChild(monte);
  }
  return n;
}

/**
 * Pose l'état du grimpeur sur un plan déjà monté, et son avancement.
 *
 * La page ne DESSINE pas le mur ici, elle le DÉCORE : elle cherche
 * `[data-zone]`, remplace ses classes d'état, écrit le compteur de la zone, et
 * ne sait rien d'autre. C'est ce qui fait qu'un changement de forme du plan ne
 * la touche pas.
 *
 * `comptes` est ce que rend `comptesDesZones` — omis, aucun compteur ne
 * s'affiche, et c'est un état normal : le mur reste exactement ce qu'il était
 * avant la spec 036.
 *
 * Rend `true` si la zone visée existe dans ce plan — c'est-à-dire s'il y avait
 * bien quelque chose à montrer.
 */
export function decorer(racine, etats, visee, comptes) {
  let trouvee = false;
  if (!racine) return false;
  for (const n of racine.querySelectorAll("[data-zone]")) {
    const zone = n.getAttribute("data-zone");
    n.classList.remove("z-rien", "z-reste", "z-finie", "visee", "a-compte");
    for (const classe of classesDeZone(zone, etats || {}, visee)) {
      n.classList.add(classe);
    }
    // ⚠️ Le compteur se REMET À ZÉRO à chaque passage, comme les classes. Le
    // dessin PERSISTE tant qu'on regarde le même grimpeur, et c'est ce qui rend
    // la fiche « en direct » : si un bloc quitte son circuit entre deux
    // rafraîchissements, le chiffre de sa zone doit disparaître, pas rester
    // posé sur une zone où il n'a plus rien à faire.
    const compte = (comptes || {})[zone];
    const texte = libelleCompte(compte);
    const chiffre = n.querySelector(".compte-zone");
    if (chiffre) {
      chiffre.textContent = texte;
      chiffre.classList.remove("compte-finie");
      if (texte) {
        n.classList.add("a-compte");
        if (compte.faits === compte.total) chiffre.classList.add("compte-finie");
        // Le corps suit la longueur : « 10/12 » rétrécit au lieu de déborder.
        // La PASTILLE, elle, ne bouge pas — c'est le chiffre qui rentre dans
        // le socle, jamais le socle qui s'étire pour le chiffre.
        const corps = tailleDuCompte(chiffre.getAttribute("data-corps"), texte);
        chiffre.setAttribute("font-size", corps.toFixed(2));
      }
    }
    if (zone && zone === visee) trouvee = true;
  }
  return trouvee;
}
