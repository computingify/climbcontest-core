/**
 * Le geste qui confirme une action irrattrapable — specs 044 et 046.
 *
 * UN geste, DEUX surfaces :
 *
 *   souris / trackpad : on MAINTIENT deux secondes, avec anneau et décompte ;
 *   doigt             : on GLISSE le curseur jusqu'au bout.
 *
 * ⚠️ Aucune des deux moitiés n'est inventée ici. Le maintien est celui de la
 * console (`admin.html`, `button.detruire`, spec 032, 02/09) — qui remplaçait
 * déjà un mot à frapper au clavier, « sept caractères, sur un ordinateur posé
 * sur un coin de table dans une salle d'escalade ». Le glissement est celui de
 * Sowel (`SlideToConfirm.tsx`, spec 146), **cotes comprises**.
 *
 * ⚠️ UN SEUL MODULE, et c'est la moitié du travail. Deux copies du même geste
 * — une pour la renumérotation, une pour le débranchement — divergeraient en
 * une semaine. C'est la leçon de `cascade.py` et de son test miroir, qui existe
 * justement parce que deux implémentations d'une même règle avaient divergé.
 *
 * ⚠️ C'EST LE POINTEUR QUI DÉCIDE, PAS LA LARGEUR DE L'ÉCRAN. Un portable
 * tactile et un téléphone en paysage se rangeraient du mauvais côté d'une
 * simple largeur.
 */

/** Le temps qu'il faut TENIR. Repris tel quel de `admin.html`. */
export const MAINTIEN_MS = 2000;

/** Le périmètre de l'anneau : 2 × π × 6, le rayon du cercle. */
export const ANNEAU = 37.7;

/* Les cotes du glissement, mesurées à la main chez Sowel et justifiées
   là-bas : pleine largeur sur un téléphone de 393 px, le geste part du coin
   inférieur gauche — le point le plus loin du pouce de la main qui tient
   l'appareil, sur un contrôle fait pour être utilisé d'une seule main. */
export const BOUTON = 50;
export const MARGE = 4;
export const EMPRISE = BOUTON + MARGE * 2;        // 58
export const PISTE_MAXI = 260;                    // course utile : 202

/**
 * Quelle surface pour ce navigateur ?
 *
 * Exporté pour être testable : un test peut l'appeler avec une fenêtre feinte
 * plutôt que de simuler un appareil.
 */
export function surface(fenetre) {
  const f = fenetre || window;
  if (!f.matchMedia) return "maintien";
  return f.matchMedia("(hover: hover) and (pointer: fine)").matches
    ? "maintien" : "glissement";
}

function el(tag, attrs, texte) {
  const n = document.createElement(tag);
  for (const k in attrs) n.setAttribute(k, String(attrs[k]));
  if (texte !== undefined) n.textContent = texte;
  return n;
}

function svgEl(tag, attrs) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const k in attrs) n.setAttribute(k, String(attrs[k]));
  return n;
}

/**
 * Pose le geste de MAINTIEN sur un bouton **qui existe déjà**.
 *
 * ⚠️ C'est le point d'entrée bas niveau, et il existe pour une raison précise :
 * deux endroits du dépôt ont besoin du même geste sur un balisage différent.
 *
 * - `confirmerParGeste` **construit** son bouton (écran d'ouverture, spec 044) ;
 * - `dlgConfirmer` d'`admin.html` a le sien depuis la spec 032, avec son
 *   `<dialog>`, sa case « quand même » et son libellé calculé.
 *
 * Le second gardait sa propre copie de la mécanique — quatre-vingt-dix lignes
 * en double dans le même dépôt. Deux implémentations d'un même geste divergent :
 * c'est la leçon de `cascade.py` et de son test miroir.
 *
 * Le bouton doit porter `.remplissage` (la jauge) et `.anneau .part` (l'arc).
 * `mot` est l'élément qui porte le libellé — le `<span>` du bouton.
 *
 * Rend `{ annuler, reinitialiser }` :
 * - `annuler()` interrompt un maintien en cours, et ne fait rien sinon ;
 * - `reinitialiser()` remet tout à plat — geste, visuel, libellé — pour un
 *   bouton qu'on réutilise, ce qui est le cas d'un `<dialog>` qu'on rouvre.
 */
export function poserMaintien(bouton, options) {
  const o = options || {};
  const libelle = o.libelle || "Maintenir 2 s pour confirmer";
  const mot = o.mot || bouton.querySelector("span") || bouton;
  const jauge = bouton.querySelector(".remplissage");
  const part = bouton.querySelector(".anneau .part");
  let minuteur = null, decompte = null, parti = false;

  function remplir(vers) {
    const duree = vers ? (MAINTIEN_MS / 1000) + "s" : "0s";
    if (jauge) {
      jauge.style.transitionDuration = duree;
      jauge.style.width = vers ? "100%" : "0";
    }
    if (part) {
      part.style.transitionDuration = duree;
      // ⚠️ Le périmètre vient de la FEUILLE DE STYLE (`--anneau`) : un seul
      // endroit où il dépend du rayon du cercle. Écrit en dur ici, il
      // mentirait le jour où le rayon change.
      const perimetre = getComputedStyle(document.documentElement)
        .getPropertyValue("--anneau").trim() || String(ANNEAU);
      part.style.strokeDashoffset = vers ? "0" : perimetre;
    }
  }

  function demarrer(e) {
    if (parti || minuteur || bouton.disabled) return;
    if (e && e.type === "keydown") {
      // ⚠️ Entrée maintenue redéclenche `keydown` en rafale : sans ce garde le
      // minuteur repartirait à zéro cinquante fois et n'aboutirait jamais.
      if (e.repeat) return;
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
    }
    remplir(1);
    bouton.classList.add("tenu");
    // Le DÉCOMPTE dit combien de temps il reste, ce qu'une barre qui glisse ne
    // dit pas. C'est aussi la seule information qui survit à
    // `prefers-reduced-motion`, qui coupe l'animation.
    let reste = MAINTIEN_MS / 1000;
    mot.textContent = "Encore " + reste + " s…";
    decompte = setInterval(() => {
      reste -= 1;
      if (reste > 0) mot.textContent = "Encore " + reste + " s…";
    }, 1000);
    minuteur = setTimeout(aboutir, MAINTIEN_MS);
  }

  function annuler() {
    if (parti || !minuteur) return;
    clearTimeout(minuteur); clearInterval(decompte);
    minuteur = decompte = null;
    bouton.classList.remove("tenu");
    remplir(0);
    mot.textContent = libelle;
  }

  function aboutir() {
    clearInterval(decompte);
    minuteur = decompte = null;
    parti = true;
    bouton.classList.remove("tenu");
    // Désactivé AVANT d'appeler : deux maintiens très rapprochés ne doivent
    // produire qu'un seul envoi.
    bouton.disabled = true;
    if (o.surAbout) o.surAbout();
  }

  function reinitialiser() {
    // ⚠️ Échap pendant un maintien : la fenêtre se ferme, le minuteur doit
    // mourir avec elle — sinon il aboutit sur un dialogue déjà fermé.
    clearTimeout(minuteur); clearInterval(decompte);
    minuteur = decompte = null;
    parti = false;
    bouton.disabled = false;
    bouton.classList.remove("tenu");
    remplir(0);
    mot.textContent = libelle;
  }

  bouton.onpointerdown = demarrer;
  bouton.onpointerup = annuler;
  bouton.onpointerleave = annuler;          // curseur sorti = relâché
  bouton.onpointercancel = annuler;
  bouton.onkeydown = demarrer;
  bouton.onkeyup = annuler;
  bouton.onblur = annuler;
  remplir(0);
  mot.textContent = libelle;

  return { annuler, reinitialiser };
}

/** Le bouton à maintenir, construit puis armé. Rend `{ noeud, detruire }`. */
function monterMaintien(libelle, surAbout) {
  const bouton = el("button", { type: "button", class: "detruire" });
  const jauge = el("i", { class: "remplissage", "aria-hidden": "true" });
  const anneau = svgEl("svg", { class: "anneau", viewBox: "0 0 16 16",
                                "aria-hidden": "true" });
  anneau.appendChild(svgEl("circle", { class: "fond", cx: 8, cy: 8, r: 6 }));
  const part = svgEl("circle", { class: "part", cx: 8, cy: 8, r: 6 });
  anneau.appendChild(part);
  const mot = el("span", {}, libelle);
  bouton.append(jauge, anneau, mot);

  const geste = poserMaintien(bouton, { libelle, mot, surAbout });
  return { noeud: bouton, detruire: geste.annuler };
}

/** Le glissement. Rend `{ noeud, detruire }`. */
function monterGlissement(libelle, surAbout) {
  const piste = el("div", { class: "glisse" });
  const jauge = el("div", { class: "glisse-jauge" });
  const mot = el("div", { class: "glisse-mot" }, libelle);
  const curseur = el("div", { class: "glisse-bouton", role: "button",
                              tabindex: "0", "aria-label": libelle }, "›");
  piste.append(jauge, mot, curseur);

  let x = 0, drag = null, fini = false;

  const course = () => Math.max(0, piste.clientWidth - EMPRISE);

  function poser(v, anime) {
    x = v;
    const t = anime ? "left .2s, width .2s" : "none";
    curseur.style.transition = t;
    jauge.style.transition = t;
    curseur.style.left = (MARGE + x) + "px";
    jauge.style.width = (BOUTON + x) + "px";
  }

  function aboutir() {
    if (fini) return;
    fini = true; drag = null;
    poser(course(), true);
    piste.classList.add("fini");
    curseur.textContent = "✓";
    surAbout();
  }

  curseur.addEventListener("pointerdown", (e) => {
    if (fini) return;
    // Garde le suivi du geste même quand le doigt sort de l'élément.
    if (curseur.setPointerCapture) curseur.setPointerCapture(e.pointerId);
    drag = { depart: e.clientX - x, max: course() };
  });
  curseur.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const nx = Math.max(0, Math.min(drag.max, e.clientX - drag.depart));
    poser(nx, false);
    // ⚠️ `drag.max > 0` : sur une piste dégénérée — trop étroite, ou pas encore
    // mise en page — le premier mouvement validerait tout seul.
    if (drag.max > 0 && nx >= drag.max - 1) aboutir();
  });

  function relacher() {
    if (!drag || fini) return;
    const max = drag.max;
    drag = null;
    if (x < max - 1) poser(0, true);        // retour au départ
  }
  curseur.addEventListener("pointerup", relacher);
  curseur.addEventListener("pointercancel", relacher);

  // ⚠️ LE CLAVIER NE DOIT PAS TOMBER DU CÔTÉ DU GLISSEMENT. Un glissement ne
  // s'opère pas au clavier ; sur un appareil à pointeur grossier muni d'un
  // clavier, le geste deviendrait inatteignable. Le curseur accepte donc AUSSI
  // le maintien sur Entrée — même durée, même annulation.
  let minuteur = null;
  curseur.addEventListener("keydown", (e) => {
    if (fini || minuteur || e.repeat) return;
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    piste.classList.add("tenu");
    minuteur = setTimeout(() => { minuteur = null; aboutir(); }, MAINTIEN_MS);
  });
  const lacher = () => {
    if (!minuteur) return;
    clearTimeout(minuteur); minuteur = null;
    piste.classList.remove("tenu");
  };
  curseur.addEventListener("keyup", lacher);
  curseur.addEventListener("blur", lacher);

  poser(0, false);
  return { noeud: piste, detruire: lacher };
}

/**
 * Pose le geste dans `hote`, et appelle `surAbout` quand il aboutit.
 *
 * `hote` est VIDÉ : c'est un emplacement dédié, pas un conteneur partagé.
 */
export function confirmerParGeste(hote, options) {
  const o = options || {};
  const monte = surface() === "maintien"
    ? monterMaintien(o.libelle || "Maintenir 2 s pour confirmer", o.surAbout)
    : monterGlissement(o.libelleGlisse || o.libelle || "Glisser pour confirmer",
                       o.surAbout);
  hote.textContent = "";
  hote.appendChild(monte.noeud);
  return monte;
}
