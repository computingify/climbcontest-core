# Architecture : 041 — La matière imprimée

## Où ça vit

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/templates/juge.html` | Le bloc `<style>` en ligne : quatre règles ajoutées, deux modifiées, les images-clés du souffle réécrites |
| `climbcontest/static/juge/couleurs.js` | `estLeNoir(nom)` — la question que le CSS ne peut pas poser |
| `climbcontest/static/juge/juge.js` | `redessiner()` pose la classe `encre` sur `#carteBloc` |
| `climbcontest/static/juge/sw.js` | `CACHE` passe en `v7` |
| `tests/js/couleurs.test.mjs` | Deux tests sur `estLeNoir` |

Aucun fichier n'est ajouté au service worker : la matière est du CSS **en
ligne** dans un gabarit que la coquille porte déjà.

## La décision qui structure tout : la matière est prise sur `--encre`

La maquette de la 035 écrivait `#17140F` en dur — c'était cohérent, elle
décrivait une direction **claire**. Mais la 039 a livré **deux thèmes**, et un
liseré presque noir sur l'ardoise ne se voit pas.

Tout est donc exprimé en `var(--encre)` et en `color-mix()` :

```css
#carteBloc.fait {
  background: color-mix(in srgb, var(--circuit) 13%, var(--carte-active));
  border-color: var(--encre); border-width: 2.5px;
}
```

Conséquence mesurée : le liseré vaut `rgb(23, 20, 15)` sur le papier et
`rgb(244, 243, 240)` sur l'ardoise. **Une seule règle, deux thèmes**, et aucune
duplication sous `@media (prefers-color-scheme: dark)`.

C'est la même discipline que la 039 : des **rôles**, pas des couleurs.

## Le circuit « Noir » : pourquoi il faut du JavaScript

Le CSS ne sait pas comparer deux couleurs. Or « Noir » est le seul circuit dont
`--circuit` vaut déjà `--encre` — sa carte teintée vire au gris, son liseré
disparaît dans l'aplat.

Il faut donc un marqueur, et le marqueur se déduit du **nom** :

```js
$("carteBloc").classList.toggle("encre", blocFait && estLeNoir(etat.couleurBloc));
```

⚠️ **Jamais de la valeur.** Écrire `couleurDeCircuit(nom) === NOIR.clair`
marcherait aujourd'hui et casserait **en silence** le jour où `NOIR.clair` et
l'encre du thème divergent d'un point : ce sont deux constantes distinctes, qui
ne sont égales que par coïncidence. Un test fige ce choix
(`le marqueur du Noir ne se déduit PAS d'une comparaison de couleurs`).

`estLeNoir` vit dans `couleurs.js` et non dans `juge.js` : c'est là que sont
déjà les règles de lecture du classeur — casse et espaces sans effet — et il
n'y en a qu'un jeu.

## Le souffle et l'ombre : une propriété pour deux besoins

`box-shadow` est **unique**. Le souffle de la spec 007 la réécrivait
entièrement à chaque image ; l'ombre imprimée disparaissait donc deux fois par
seconde.

Les images-clés reportent maintenant les **deux couches** de l'ombre dans les
deux étapes, et n'ajoutent la lueur du circuit qu'en **troisième** :

```css
0%, 100% { box-shadow: <arête>, <halo>, 0 0  6px <lueur du circuit>; }
50%      { box-shadow: <arête>, <halo>, 0 0 26px <lueur du circuit>; }
```

Ce qui pulse, c'est le **rayon de la troisième couche** — pas la présence de
l'ombre.

⚠️ Et parce qu'une animation bat toute règle ordinaire, `#envoyer:disabled`
remet explicitement `box-shadow: none`. La règle `animation` n'y court pas — le
sélecteur est `:not(:disabled)` — mais la remise à zéro est le filet : aucun
état ne doit garder l'ombre d'un bouton prêt.

## Ce qui n'a pas été fait, et pourquoi

- **Le rayon des cartes reste à 22 px.** La maquette de la direction A posait
  `--r: 20px` pour tout l'écran. Seul le bouton descend à 18 px, parce que son
  liseré le demande — un liseré sur un rayon trop large fait une gélule. Changer
  le rayon des cartes aurait déplacé de la géométrie sans qu'aucune décision
  d'Adrien ne le demande.
- **Aucune règle par couleur de circuit.** `color-mix()` sur `--circuit` traite
  les six d'un coup. La seule exception est « Noir », et elle est nommée.

## Comment ça a été vérifié

Le CSS ne se teste pas en Python. Il a été **mesuré au navigateur** : la page
réelle servie à 390 × 844, l'état posé comme le fait `redessiner()`, puis
`getComputedStyle` lu sur le bouton, la carte et la pastille — dans les deux
thèmes et sur deux circuits, plus le bouton désactivé. Le détail est dans le
plan.

Ce qui **ne se mesure pas** reste écrit noir sur blanc : l'éblouissement en
salle, la fatigue sur deux cents validations, et le « waouh ». Ceux-là se
jugent sur un vrai téléphone, un vrai jour.
