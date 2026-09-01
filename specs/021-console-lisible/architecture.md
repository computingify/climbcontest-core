# Architecture — 021 console-lisible

## Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/templates/admin.html` | Style (jetons de couleur, media queries), structure (fenêtre de confirmation, ossature du tiroir), script (`confirmer()`, `ouvrirTiroir()`) |
| `climbcontest/cycle.py` | **Un docstring et un message d'erreur** rendus faux par F3. Aucun changement de comportement |
| `tests/test_console_lisible.py` | Nouveau : ce qu'un test Python peut honnêtement vérifier du gabarit |

Aucun modèle, aucune migration, aucune route, aucun contrat JSON.

⚠️ Le script de `admin.html` est **en ligne dans le gabarit** : il n'est pas
importable, et `tests/js/` ne teste que les modules de la PWA juge. Le
comportement du tiroir, du maintien et des couleurs se vérifie donc au
navigateur — c'est la même honnêteté qu'en tête de `test_page_resultats.py`.
Extraire ce script dans `static/` pour le tester serait une bonne idée, et une
autre spec.

## Les couleurs : deux jeux, un seul vocabulaire

Le style ne connaît que des **rôles**, jamais une couleur :

```css
:root {
  color-scheme: light dark;
  --fond: #FBFAF8;  --surface: #FFFFFF;  --surface2: #F4F1EB;  --surface3: #E9E4DA;
  --trait: #DDD7CB;
  --encre: #1B1A17;  --encre2: #5C574C;  --encre3: #8A8375;
  --accent: #B5761C;          /* aplats, bordures d'état */
  --accent-texte: #8A5A0F;    /* texte et liens sur --fond/--surface */
  --sur-accent: #FFFFFF;      /* ce qu'on écrit SUR --accent */
  --ok: #2E7D4F;  --alerte: #B3392A;  --attention: #9A6B0B;
  --ombre: 0 10px 30px rgba(27, 26, 23, .10);
}
@media (prefers-color-scheme: dark) {
  :root {
    --fond: #14130F;  --surface: #1D1B16;  --surface2: #26241D;  --surface3: #322F26;
    --trait: #3A3628;
    --encre: #F2EFE8;  --encre2: #B0AA9B;  --encre3: #7C766A;
    --accent: #E0A94A;  --accent-texte: #E8BC70;  --sur-accent: #1B1A17;
    --ok: #6FC08A;  --alerte: #F08A78;  --attention: #E5B44A;
    --ombre: 0 18px 48px rgba(0, 0, 0, .5);
  }
}
```

`--sur-accent` est la variable qui manquait : le bouton d'action écrivait
`#17111f` en dur, une valeur qui n'a de sens que sur le mauve. Elle bascule avec
le thème.

Deux endroits écrivent aujourd'hui une couleur en dur dans le **script** —
`montrerConnexion()` (`background: var(--carte2)`, une variable qui n'existe
même pas) et `peindreRapport()` (`border-left: var(--attention)`). Le premier est
un bug de copie ; les deux passent par les rôles.

La barre du haut utilise `rgba(13,15,20,.86)` en dur pour son fond translucide.
Elle passe à `color-mix(in srgb, var(--fond) 86%, transparent)`.

## Le tiroir épinglé : une media query, pas du JavaScript

L'ossature devient une grille à partir du seuil. Rien à recalculer :

```css
@media (min-width: 1080px) {
  #console { display: grid; grid-template-columns: var(--tiroir) 1fr; }
  .barre   { grid-column: 1 / -1; }
  .tiroir  { position: sticky; top: var(--barre); transform: none;
             height: calc(100vh - var(--barre)); box-shadow: none; }
  .voile, .burger { display: none; }
}
```

Le script garde une seule connaissance du seuil, pour **la seule décision qui
n'est pas de la mise en page** — refermer ou non après un clic :

```js
var LARGE = window.matchMedia("(min-width: 1080px)");
function tiroirEpingle() { return LARGE.matches; }
```

`ouvrirTiroir(false)` devient sans effet quand le tiroir est épinglé, et la
touche Échap ne l'appelle plus dans ce cas. Aucun écouteur `resize` : `matchMedia`
est interrogé au moment du clic, jamais mis en cache.

## Le bouton à maintenir

Un seul bouton concerné : `#dlgOk`, dans la fenêtre partagée. Le champ `#dlgMot`
et son `<label>` sont supprimés du HTML.

```
┌─ mécanique ────────────────────────────────────────────────┐
│ démarrer()   pointerdown | keydown(Enter|Space, sans repeat)│
│              → jauge lancée, libellé « Maintiens… »        │
│ annuler()    pointerup | pointerleave | pointercancel        │
│              | keyup | blur  → jauge vidée, libellé rendu   │
│ aboutir()    setTimeout(2000) → bouton désactivé, promesse   │
│              résolue avec {confirmation: "EFFACER", forcer}  │
└────────────────────────────────────────────────────────────┘
```

- La jauge est un `<i>` en `position: absolute` sous le libellé
  (`z-index: -1` dans un `isolation: isolate`), dont la `width` passe de 0 à
  100 % par transition — aucune image, aucune bibliothèque. Sa **durée est posée
  par le script** (`MAINTIEN_MS`), pour qu'il n'y ait qu'un endroit où lire
  « deux secondes ». La vider est instantané : sinon elle redescendrait en deux
  secondes après un relâchement et un second maintien repartirait d'un état
  menteur.
- Sous `prefers-reduced-motion`, la jauge n'est **pas affichée** ; le libellé
  « Maintiens… » porte seul l'information, et **le délai ne change pas**.
- `touch-action: none` sur le bouton : sans lui, maintenir le doigt fait défiler
  la page sous le bouton et le `pointerleave` annule le geste — le bouton
  devient intenable sur téléphone.
- `aria-describedby` pointe une phrase invisible : « Maintiens le bouton deux
  secondes pour confirmer. »
- Le bouton reste `disabled` tant que la case « Effacer quand même » n'est pas
  cochée quand elle est visible — la garde de la spec 018, inchangée.

`confirmer()` garde **exactement** sa signature et sa promesse
(`{confirmation, forcer}`) : ses trois appelants ne bougent pas.

## Ce que le serveur voit

Rien de nouveau. La console envoie `confirmation: "EFFACER"` comme aujourd'hui,
une fois le maintien abouti.

```
POST /admin/effacer        {"confirmation": "EFFACER", "forcer": false}
POST /admin/import/sheet   {"mode": "remplacer", "confirmation": "EFFACER"}
POST /admin/archives/<id>  (DELETE) {"confirmation": "EFFACER"}
POST /admin/classeur       {"lien": …, "mode": "reinitialiser", "confirmation": "EFFACER"}
```

`cycle.MOT_DE_CONFIRMATION` reste `"EFFACER"`. Ce qui change est ce que le code
**dit** de lui : le docstring de `exiger_confirmation()` et le message d'erreur
parlent d'un mot « frappé à la main » — ils décriront un marqueur envoyé par la
console au terme de sa fenêtre de confirmation, qui protège contre un appel
direct de la route.
