// Le thème choisi par le juge — spec 040.
//
// Ce qui se décide vit dans `theme.js` et se teste ici, sous Node, sans
// navigateur : quel thème s'applique, ce qui est rangé, et ce qui est rendu à
// `<html>`. Ce que `juge.js` en fait — allumer une pastille, redessiner la
// teinte du circuit — se regarde ailleurs.
import { test } from "node:test";
import assert from "node:assert/strict";

import { CHOIX, CLE_THEME, appliquer, ecrireChoix, lireChoix, themeRendu }
  from "../../climbcontest/static/juge/theme.js";

/** Un rangement en mémoire, qui se comporte comme `localStorage`. */
function rangement(depart = {}) {
  const valeurs = { ...depart };
  return {
    getItem: (c) => (c in valeurs ? valeurs[c] : null),
    setItem: (c, v) => { valeurs[c] = String(v); },
    removeItem: (c) => { delete valeurs[c]; },
    valeurs,
  };
}

/** Un rangement qui REFUSE tout — la navigation privée de Safari. */
const refuse = {
  getItem() { throw new Error("refuse"); },
  setItem() { throw new Error("refuse"); },
  removeItem() { throw new Error("refuse"); },
};

/** Un `<html>` et ses deux balises `theme-color`, réduits à ce qu'on lit. */
function documentFactice() {
  const racine = { dataset: {} };
  const balise = (media, content) => ({
    dataset: {},
    attributs: { media, content },
    getAttribute(n) { return this.attributs[n] ?? null; },
    setAttribute(n, v) { this.attributs[n] = v; },
  });
  const metas = [balise("(prefers-color-scheme: light)", "#F3EEE3"),
                 balise("(prefers-color-scheme: dark)", "#15161B")];
  return {
    documentElement: racine,
    querySelectorAll: () => metas,
    metas,
  };
}

test("sans rien de rangé, le choix est « Système » — le défaut de la 039", () => {
  assert.equal(lireChoix(rangement()), "auto");
});

test("une valeur inconnue ne casse rien : elle vaut « Système »", () => {
  // Une clé écrite à la main, un ancien format, un octet abîmé : dans tous les
  // cas l'application s'ouvre, et elle s'ouvre sur le défaut.
  assert.equal(lireChoix(rangement({ [CLE_THEME]: "bleu" })), "auto");
  assert.equal(lireChoix(rangement({ [CLE_THEME]: "" })), "auto");
});

test("un rangement refusé rend « Système » au lieu de lever", () => {
  // Navigation privée : le thème ne se souvient pas, mais l'application marche.
  assert.equal(lireChoix(refuse), "auto");
  assert.equal(ecrireChoix("sombre", refuse), "sombre");
});

test("« Système » EFFACE la clé au lieu d'écrire « auto »", () => {
  // Ne rien ranger, c'est suivre. Une valeur écrite en dur figerait dans le
  // téléphone le défaut du jour où le juge a touché au réglage.
  const r = rangement({ [CLE_THEME]: "sombre" });
  assert.equal(ecrireChoix("auto", r), "auto");
  assert.equal(CLE_THEME in r.valeurs, false);
});

test("ce qui est rangé se relit à l'identique", () => {
  for (const choix of CHOIX) {
    const r = rangement();
    ecrireChoix(choix, r);
    assert.equal(lireChoix(r), choix);
  }
});

test("le thème rendu n'est jamais « auto »", () => {
  assert.equal(themeRendu("auto", true), "sombre");
  assert.equal(themeRendu("auto", false), "clair");
  // Un choix explicite gagne contre le téléphone, dans les DEUX sens : c'est
  // toute la spec.
  assert.equal(themeRendu("clair", true), "clair");
  assert.equal(themeRendu("sombre", false), "sombre");
});

test("appliquer pose l'attribut, « Système » le RETIRE", () => {
  const d = documentFactice();
  appliquer("sombre", d);
  assert.equal(d.documentElement.dataset.theme, "sombre");
  appliquer("clair", d);
  assert.equal(d.documentElement.dataset.theme, "clair");
  // ⚠️ Retirer, et pas poser « auto » : c'est l'ABSENCE d'attribut qui rend la
  // main à la requête media. Un attribut `data-theme="auto"` ne serait
  // reconnu par aucune règle et laisserait le thème forcé en place.
  appliquer("auto", d);
  assert.equal("theme" in d.documentElement.dataset, false);
});

test("la barre du navigateur suit le thème imposé, et se rend", () => {
  const d = documentFactice();
  const [claire, sombre] = d.metas;

  appliquer("sombre", d);
  assert.equal(claire.getAttribute("content"), "#15161B");
  assert.equal(sombre.getAttribute("content"), "#15161B");

  appliquer("clair", d);
  assert.equal(claire.getAttribute("content"), "#F3EEE3");
  assert.equal(sombre.getAttribute("content"), "#F3EEE3");

  // ⚠️ Le vrai piège : après deux bascules, chaque balise doit retrouver SA
  // couleur. Sans mémoire de la valeur d'origine, les deux resteraient sur la
  // dernière imposée et le téléphone ne déciderait plus jamais.
  appliquer("auto", d);
  assert.equal(claire.getAttribute("content"), "#F3EEE3");
  assert.equal(sombre.getAttribute("content"), "#15161B");
});
