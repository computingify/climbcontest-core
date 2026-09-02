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

import { classesDeZone } from "./suivi.js";

const SVG = "http://www.w3.org/2000/svg";

/** Les formats que CE fichier sait dessiner.
 *
 * Un tableau et non une constante : le jour où le serveur passe à
 * « polygones/2 », on peut accepter les deux le temps d'un déploiement, où la
 * page servie et l'API ne sont jamais mises à jour à la même seconde. */
export const FORMATS_RENDUS = ["polygones/1"];

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
                                "stroke-width": (taille * 0.24).toFixed(2) },
          texte: mur.zone },
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
 * Pose l'état du grimpeur sur un plan déjà monté.
 *
 * La page ne DESSINE pas le mur ici, elle le DÉCORE : elle cherche
 * `[data-zone]`, remplace ses classes d'état, et ne sait rien d'autre. C'est ce
 * qui fait qu'un changement de forme du plan ne la touche pas.
 *
 * Rend `true` si la zone visée existe dans ce plan — c'est-à-dire s'il y avait
 * bien quelque chose à montrer.
 */
export function decorer(racine, etats, visee) {
  let trouvee = false;
  if (!racine) return false;
  for (const n of racine.querySelectorAll("[data-zone]")) {
    const zone = n.getAttribute("data-zone");
    n.classList.remove("z-rien", "z-reste", "z-finie", "visee");
    for (const classe of classesDeZone(zone, etats || {}, visee)) {
      n.classList.add(classe);
    }
    if (zone && zone === visee) trouvee = true;
  }
  return trouvee;
}
