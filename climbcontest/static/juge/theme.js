/**
 * Le thème de l'application juge : celui du téléphone, ou celui que le juge a
 * choisi dans les Réglages (spec 040).
 *
 * La spec 039 avait posé le clair par défaut et **aucun réglage** : le système
 * décidait, point. Ce module ajoute la seule chose qui manquait — le juge dont
 * le téléphone dit le contraire de ce que la salle demande.
 *
 * ⚠️ **`localStorage` et non IndexedDB**, contrairement aux autres réglages.
 * Le thème doit être connu **avant la première peinture**, sinon l'application
 * s'ouvre dans le mauvais fond et bascule sous les yeux du juge à chaque
 * lancement. IndexedDB est asynchrone : il répond toujours trop tard. C'est le
 * même choix, pour la même raison, que le jeton (`CLE_RANGEMENT`).
 *
 * ⚠️ Le gabarit lit cette clé **en ligne dans son `<head>`**, avant de charger
 * le moindre module — c'est ce qui évite le clignotement. Le nom de la clé est
 * donc écrit à deux endroits, et `tests/test_theme_au_choix.py` refuse qu'ils
 * diffèrent.
 */

/** La clé du rangement. ⚠️ Écrite aussi dans le `<head>` de `juge.html`. */
export const CLE_THEME = "climbcontest-theme";

/** Les trois positions du réglage. `auto` = ce que le téléphone demande. */
export const CHOIX = ["auto", "clair", "sombre"];

/**
 * Le choix rangé, ou `auto` — y compris quand le rangement est refusé
 * (navigation privée) ou qu'il contient n'importe quoi.
 */
export function lireChoix(rangement = globalThis.localStorage) {
  let brut = null;
  try { brut = rangement.getItem(CLE_THEME); } catch { /* mode prive */ }
  return CHOIX.includes(brut) ? brut : "auto";
}

/** Range le choix. `auto` efface la clé : ne rien ranger, c'est suivre. */
export function ecrireChoix(choix, rangement = globalThis.localStorage) {
  const retenu = CHOIX.includes(choix) ? choix : "auto";
  try {
    if (retenu === "auto") rangement.removeItem(CLE_THEME);
    else rangement.setItem(CLE_THEME, retenu);
  } catch { /* mode prive : le theme retombe sur le systeme au prochain lancement */ }
  return retenu;
}

/**
 * Le thème réellement peint : `clair` ou `sombre`, jamais `auto`.
 *
 * Sert aux tests et à la barre du navigateur ; la cascade CSS, elle, n'a besoin
 * que de l'attribut.
 */
export function themeRendu(choix, sombreDemande) {
  if (choix === "clair" || choix === "sombre") return choix;
  return sombreDemande ? "sombre" : "clair";
}

/**
 * Pose le choix sur `<html>` et met la barre du navigateur d'accord.
 *
 * `auto` **retire** l'attribut : la requête media reprend la main, et le
 * défaut de la spec 039 est retrouvé à l'octet près.
 *
 * Appelée au démarrage **et** à chaque clic. Au démarrage elle repose ce que le
 * script en ligne du gabarit a déjà posé — c'est volontairement redondant sur
 * l'attribut, et c'est le seul moment où la barre du navigateur est accordée.
 */
export function appliquer(choix, document_ = globalThis.document) {
  const racine = document_.documentElement;
  if (choix === "clair" || choix === "sombre") racine.dataset.theme = choix;
  else delete racine.dataset.theme;
  peindreLaBarre(choix, document_);
  return choix;
}

/**
 * La barre du navigateur (`theme-color`).
 *
 * Les deux balises du gabarit portent chacune sa requête media : elles suivent
 * le TÉLÉPHONE, pas le réglage. Quand le juge impose un thème, on écrit donc la
 * même couleur dans les deux — quelle que soit celle qui l'emporte, elle est la
 * bonne. `auto` remet chacune sur la sienne.
 *
 * ⚠️ Sur un iPhone installé sur l'écran d'accueil, la barre d'état suit
 * `apple-mobile-web-app-status-bar-style`, figé au lancement : elle restera
 * accordée au système même si le juge impose l'autre thème. C'est écrit dans la
 * spec, section « ce que ça ne fait pas ».
 */
function peindreLaBarre(choix, document_) {
  const balises = [...document_.querySelectorAll('meta[name="theme-color"]')];
  const couleurs = {};
  for (const balise of balises) {
    // La couleur d'origine est mise de côté au premier passage : sans ça, une
    // bascule sombre → clair → sombre écraserait les deux balises avec la même
    // couleur et on ne saurait plus revenir.
    if (!balise.dataset.couleur) balise.dataset.couleur = balise.getAttribute("content");
    const theme = (balise.getAttribute("media") || "").includes("dark") ? "sombre" : "clair";
    couleurs[theme] = balise.dataset.couleur;
  }
  for (const balise of balises) {
    balise.setAttribute("content", choix === "auto"
      ? balise.dataset.couleur
      : couleurs[choix] || balise.dataset.couleur);
  }
}
