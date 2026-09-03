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
// ⚠️ ET LA PASTILLE SE REMPLIT (03/09, deuxième passe). « Je veux que seulement
// le truc avec le nombre de blocs restant se remplisse de vert en fonction de
// l'avancement. » La barre verte À L'INTÉRIEUR du socle est la jauge ; le cadre
// de la zone, lui, garde son tout-ou-rien — il dit « terminée », et rien
// d'autre. Un premier essai avait fait l'inverse : c'était le CADRE qui se
// remplissait, épaissi et rogné dans le pan. Même phrase, autre lecture, et
// c'est celle-ci qui vaut — les deux rendus réels sont dans
// `maquettes/pastille.html`.
//
// ⚠️ LES CINQ RATIOS SONT CALCULÉS, pas choisis à l'œil, et ils se tiennent
// tous. Ce qu'on répartit, c'est la hauteur du pan :
//
//     le pan       2 × 0,833 × taille   demi-hauteur d'un pan de 15 unités,
//                                       rapportée à une lettre plafonnée à 9
//     le halo      2 × 0,48             0,36 de glyphe (capitale grasse,
//                                       `dominant-baseline: central`), plus la
//                                       moitié des 0,24 d'épaisseur du halo
//     la pastille  0,448                COMPTE_ECHELLE × PASTILLE_HAUTEUR
//     ------------------------------------------------------------------
//     il reste     0,258 × taille, soit TROIS AIRS DE 0,086
//
// Les trois airs sont ÉGAUX — au-dessus de la lettre, entre la lettre et la
// pastille, sous la pastille. C'est la position « E — l'équilibre », choisie
// par Adrien le 03/09 sur `maquettes/pastille.html`, et les deux ratios de
// place en découlent :
//
//     LETTRE_MONTEE   = 0,833 − 0,086 − 0,48  = 0,267
//     COMPTE_DESCENTE = 0,833 − 0,086 − 0,224 = 0,523
//
// ⚠️ CE QU'ON A RÉGLÉ LÀ, C'EST UN CHEVAUCHEMENT, PAS UN ESPACEMENT. La lettre
// restait au centroïde et la pastille descendait à 0,60 : le HALO de la lettre
// recouvrait la pastille de 0,104 × taille, près d'une unité de plan. « Là
// c'est trop proche » ne demandait donc pas de la place en plus, mais de
// séparer deux objets qui se touchaient. Descendre la pastille seule n'y
// pouvait rien — il ne restait que 0,009 × taille sous elle, un cinquième de
// pixel sur un téléphone. Toute la place libre était AU-DESSUS de la lettre, et
// c'est là qu'on l'a prise.
//
// Le chiffre, lui, ne change pas de corps : 0,40 × taille, comme avant.
// `tests/test_suivi.py` relit ces nombres et vérifie, pan par pan sur le plan
// réellement servi, que le halo ne sort pas par le haut et que la pastille ne
// sort ni par le bas ni par les côtés.
export const COMPTE_ECHELLE = 0.40;
export const COMPTE_DESCENTE = 0.523;
export const PASTILLE_HAUTEUR = 1.12;
/** La largeur du socle, en fraction de la taille de la LETTRE.
 *
 * ⚠️ 1,6 et non 1,0 : depuis que la pastille porte la jauge, il lui faut de la
 * longueur — un vert qui remplit un rond ne dit pas une proportion. Sur les
 * pans d'Annonay ça fait 14,4 unités pour 15 : elle mord donc de 0,5 unité
 * dans le cadre « terminée » de chaque côté, et lui passe devant. Vu sur pièce
 * et accepté le 03/09. */
export const PASTILLE_LARGEUR = 1.6;
/** De combien la LETTRE monte au-dessus de son centroïde, en fraction de son
 *  corps. C'est la place qu'on prend pour séparer la lettre de la pastille —
 *  voir le calcul des trois airs ci-dessus. */
export const LETTRE_MONTEE = 0.267;

/** L'épaisseur du halo de la LETTRE, en fraction de son corps.
 *
 * Le compteur ne l'a plus : la pastille remplace le halo, et le fait mieux. */
const HALO = 0.24;

/** La largeur d'un chiffre tabulaire, en fraction de son corps.
 *
 * Même famille de constante que `LARGEUR_CAPITALE` côté Python, et prise comme
 * elle sur le PIRE glyphe : elle sert à borner, pas à décrire. */
const LARGEUR_CHIFFRE = 0.58;

/** Ce que le libellé a le droit d'occuper DANS la pastille, en fraction de sa
 *  largeur. Le reste est la marge de part et d'autre du texte. */
const DEDANS = 0.86;

/**
 * Le corps du compteur, pour ce libellé-là.
 *
 * « 1/4 » sort à sa taille pleine ; un libellé trop long rétrécit au lieu de
 * déborder. La borne est la largeur de la PASTILLE — c'est elle qui porte le
 * texte, et elle est elle-même bornée par la boîte du pan via `taille`.
 *
 * ⚠️ Depuis que la pastille fait 1,6 fois la lettre, « 12/15 » tient à sa
 * taille pleine alors qu'il rétrécissait avant : c'est le bénéfice direct de
 * l'élargissement, et c'est voulu — « repasse sa taille à celle d'origine »
 * (Adrien, 03/09). Le rétrécissement reste là pour les libellés qu'aucun
 * élargissement raisonnable ne ferait tenir.
 */
export function tailleDuCompte(taille, texte) {
  const corps = Number(taille) > 0 ? Number(taille) : 6;
  const n = Math.max(1, String(texte || "").length);
  return corps * Math.min(COMPTE_ECHELLE,
                          PASTILLE_LARGEUR * DEDANS / (LARGEUR_CHIFFRE * n));
}

/**
 * La part faite d'une zone, entre 0 et 1 — la longueur du vert dans la
 * pastille. Rend `null` quand il n'y a rien à remplir : une zone sans bloc du
 * circuit n'a pas de jauge, et c'est différent d'une jauge à zéro.
 */
export function partFaite(compte) {
  const total = Number(compte && compte.total);
  if (!(total > 0)) return null;
  const faits = Number(compte && compte.faits) || 0;
  return Math.max(0, Math.min(1, faits / total));
}

/** Le préfixe des découpes de pastille. Une par zone, nommée par sa lettre. */
const DECOUPE = "plan-socle-";

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
  const murs = plan.murs.filter(murValide);

  /** La boîte de la pastille d'un mur. Une seule source pour les trois nœuds
   *  qui en dépendent — le socle, sa découpe et la barre qui le remplit —
   *  parce que trois calculs de la même boîte finiraient par diverger. */
  const boiteDuSocle = (mur) => {
    const [x, y] = Array.isArray(mur.etiquette) ? mur.etiquette : [0, 0];
    const taille = Number(mur.taille) > 0 ? Number(mur.taille) : 6;
    // ⚠️ La pastille se calcule sur le corps NOMINAL de la lettre, jamais sur
    // le corps réduit d'un libellé long : c'est le chiffre qui rentre dans le
    // socle, pas le socle qui s'étire pour le chiffre. Sans ça, deux zones
    // voisines porteraient deux pastilles de tailles différentes pour dire la
    // même chose.
    const hauteur = taille * COMPTE_ECHELLE * PASTILLE_HAUTEUR;
    const largeur = taille * PASTILLE_LARGEUR;
    const cy = y + taille * COMPTE_DESCENTE;
    return { x: Number((x - largeur / 2).toFixed(2)),
             y: Number((cy - hauteur / 2).toFixed(2)),
             width: Number(largeur.toFixed(2)),
             height: Number(hauteur.toFixed(2)),
             rx: Number((hauteur / 2).toFixed(2)), cx: x, cy };
  };

  // LES DÉCOUPES DE PASTILLE, une par zone. C'est elles qui donnent au vert son
  // BOUT DROIT : la barre est un rectangle franc, découpé dans la forme du
  // socle, donc elle en épouse le bord arrondi à gauche et se coupe net à
  // droite. Un rectangle arrondi de son côté ferait une petite pastille DANS la
  // grande — on lirait deux objets au lieu d'un niveau. Choisi sur pièce le
  // 03/09 (`maquettes/pastille.html`).
  enfants.push({
    tag: "defs",
    attrs: {},
    enfants: murs.map((mur) => {
      const socle = boiteDuSocle(mur);
      return {
        tag: "clipPath",
        attrs: { id: DECOUPE + mur.zone },
        enfants: [{ tag: "rect", attrs: { x: socle.x, y: socle.y,
                                          width: socle.width,
                                          height: socle.height, rx: socle.rx } }],
      };
    }),
  });

  if (typeof plan.contour === "string" && plan.contour.includes(",")) {
    enfants.push({ tag: "polygon", attrs: { class: "contour", points: plan.contour } });
  }

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
        // ⚠️ LA LETTRE NE S'ÉCRIT PLUS SUR SON CENTROÏDE : elle monte de
        // `LETTRE_MONTEE`. C'est ce qui fait la place entre son halo et la
        // pastille — la place n'existait pas en dessous. Le centroïde reste la
        // référence de tout le monde, personne ne le recalcule.
        { tag: "text", attrs: { class: "lettre", x,
                                y: Number((y - taille * LETTRE_MONTEE).toFixed(2)),
                                "font-size": taille,
                                "stroke-width": (taille * HALO).toFixed(2) },
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

  // ⚠️ LES COMPTEURS SONT UNE COUCHE ENCORE AU-DESSUS, et c'est la pastille de
  // 1,6 qui l'impose : large de 14,4 unités dans un pan de 15, elle croise le
  // cadre « terminée » de 0,5 unité de chaque côté. Peinte dessous, elle se
  // ferait couper par lui aux deux endroits qu'on lit — ses extrémités. Elle
  // passe donc devant, et c'est le cadre qui porte l'encoche : un décor
  // constant, présent sur toutes les zones comptées, plutôt qu'un chiffre
  // rogné.
  //
  // Le groupe reprend le `data-zone` ET le centre de rotation de son pan : il
  // reçoit les mêmes classes d'état, et rebondit avec lui.
  enfants.push({
    tag: "g",
    attrs: { class: "compteurs-zone" },
    enfants: murs.map((mur) => {
      const [x, y] = Array.isArray(mur.etiquette) ? mur.etiquette : [0, 0];
      const taille = Number(mur.taille) > 0 ? Number(mur.taille) : 6;
      const socle = boiteDuSocle(mur);
      // Le corps d'un compteur de trois caractères : celui de « 1/4 », le cas
      // courant. `decorer` le refait quand le libellé est plus long.
      const corps = tailleDuCompte(taille, "0/0");
      return {
        tag: "g",
        attrs: { "data-zone": mur.zone,
                 style: "transform-origin:" + x + "px " + y + "px" },
        enfants: [
          // La pastille est DÉCRITE POUR TOUTES LES ZONES et cachée par le CSS
          // sur celles qui ne portent pas de compteur (`:not(.a-compte)`). Sa
          // géométrie ne dépend que du pan, donc elle ne change jamais : la
          // décrire une fois évite de créer et détruire un nœud à chaque
          // repeinture, exactement comme pour le chiffre.
          { tag: "rect", attrs: { class: "socle-compte", x: socle.x, y: socle.y,
                                  width: socle.width, height: socle.height,
                                  rx: socle.rx } },
          // LA JAUGE. Décrite VIDE — largeur nulle — et remplie par `decorer` :
          // elle dépend du grimpeur, et ce dessin-ci est le même pour tout le
          // monde. `data-plein` porte la largeur du socle, seule chose dont
          // `decorer` a besoin pour en peindre une fraction sans jamais relire
          // une géométrie.
          { tag: "rect", attrs: { class: "remplit-compte", x: socle.x, y: socle.y,
                                  width: 0, height: socle.height,
                                  "data-plein": socle.width,
                                  "clip-path": "url(#" + DECOUPE + mur.zone + ")" } },
          // Le compteur est DÉCRIT VIDE et rempli par `decorer`, pour la même
          // raison. C'est aussi ce qui le rend « en direct » sans rien
          // reconstruire — une réussite qui arrive pendant qu'on regarde le
          // plan ne repasse que par la décoration.
          //
          // `data-corps` porte le corps de la LETTRE, seule chose dont
          // `decorer` a besoin pour redimensionner le chiffre selon sa longueur
          // sans jamais relire la géométrie du pan.
          { tag: "text", attrs: { class: "compte-zone", x, y: socle.cy,
                                  "data-corps": taille,
                                  "font-size": corps.toFixed(2) },
            texte: "" },
        ],
      };
    }),
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
 * s'affiche et aucune pastille ne se remplit, et c'est un état normal : le mur
 * reste exactement ce qu'il était avant la spec 036.
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
    // ⚠️ `a-compte` se pose sur TOUTES les formes de la zone, et pas seulement
    // sur celle qui porte le chiffre : c'est cette classe qui allume la
    // pastille. Une zone comptée s'allume d'un bloc, ou pas du tout.
    if (texte) n.classList.add("a-compte");

    const chiffre = n.querySelector(".compte-zone");
    if (chiffre) {
      chiffre.textContent = texte;
      if (texte) {
        // Le corps suit la longueur : un libellé très long rétrécit au lieu de
        // déborder. La PASTILLE, elle, ne bouge pas — c'est le chiffre qui
        // rentre dans le socle, jamais le socle qui s'étire pour le chiffre.
        const corps = tailleDuCompte(chiffre.getAttribute("data-corps"), texte);
        chiffre.setAttribute("font-size", corps.toFixed(2));
      }
    }

    // LA JAUGE : la pastille se remplit de vert à hauteur de l'avancement.
    // ⚠️ Elle se REMET À ZÉRO à chaque passage, comme le chiffre. Le dessin
    // PERSISTE tant qu'on regarde le même grimpeur, et c'est ce qui rend la
    // fiche « en direct » : sans remise à zéro, la pastille d'un grimpeur
    // resterait à moitié pleine sur la fiche du suivant.
    const jauge = n.querySelector(".remplit-compte");
    if (jauge) {
      const part = partFaite(compte);
      const plein = Number(jauge.getAttribute("data-plein")) || 0;
      jauge.setAttribute("width", (part === null ? 0 : part * plein).toFixed(2));
    }
    if (zone && zone === visee) trouvee = true;
  }
  return trouvee;
}
