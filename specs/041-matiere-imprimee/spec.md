# Spec 041 — La matière imprimée de l'application juge

> **Suite directe de la [spec 035](../035-refonte-pwa-juge/).** La 035 a livré
> quatre directions et posé cinq questions ; Adrien a tranché « **A — Plein
> Jour** » le 03/09. La [spec 039](../039-pwa-claire/) en a implémenté la
> **palette** — papier sable, encre presque noire. Cette spec en implémente la
> **matière**, et referme la 035.

## 1. Le fait générateur

La 039 le dit elle-même, dans son § 1 :

> « La structure de l'écran ne bouge pas, aucune des quatre directions n'est
> adoptée. La 035 reste ouverte sur la mise en page. »

Ce qui restait, ce n'était pas une mise en page — la 039 n'a touché à aucune
géométrie et il n'y avait rien à déplacer. C'était la **matière** : ce qui
sépare une couleur posée d'une étiquette imprimée. La direction A la décrivait
en une phrase, § 4 de la 035 :

> « la couleur du circuit posée en aplat cerclé d'un liseré d'encre — la matière
> des étiquettes de blocs collées au mur (spec 024). Le bouton a une ombre
> franche de 5 px : il a l'air d'être posé sur la page. »

Aucune de ces deux phrases n'était dans le code. C'est tout l'objet de la spec.

## 2. La méthode, et pourquoi elle a compté ici

Adrien, en cours de session : « **si tu touches à la UX je veux que tu me fasses
d'abord un rendu html que je te valide avant d'implémenter** ». Deux tours
d'aperçu ont eu lieu **avant la première ligne de CSS** :

1. `maquettes/index.html` — l'écran avant / après, trois états, deux thèmes.
2. `maquettes/reglages.html` — les cinq ombres et les trois traitements du
   « Noir », après ses deux réserves.

⚠️ **Les captures ne sont pas des redessins.** Elles viennent du vrai
`climbcontest/templates/juge.html` servi tel quel, avec son CSS et sa police,
dans un navigateur réglé à 390 × 844 ; la colonne « après » est la même page
avec une feuille injectée par-dessus. C'est la leçon de la spec 036 : une
maquette redessinée ne prouve rien, elle ne fait que confirmer la lecture de
celui qui l'a dessinée.

Cette méthode a **changé le résultat trois fois** — § 5.

## 3. Ce que la spec livre

| # | Geste | Où |
| --- | --- | --- |
| G1 | La **carte du bloc** scanné prend un aplat dilué de son circuit (13 %) et un **liseré d'encre** de 2,5 px | `juge.html` |
| G2 | La **pastille** du bloc est cerclée d'un liseré d'encre de 2 px — l'étiquette du mur, exactement | `juge.html` |
| G3 | Le bouton **Envoyer** prend un liseré d'encre et une ombre **courte puis floue** | `juge.html` |
| G4 | Le bouton **désactivé** passe en trait **pointillé** : un emplacement qui attend, pas une surface | `juge.html` |
| G5 | Le circuit **« Noir »** garde sa carte en **papier** | `juge.html` + `juge.js` + `couleurs.js` |

Et, sans quoi rien de tout cela n'arrive sur les téléphones : la **coquille du
service worker passe en v7**.

## 4. Ce que l'écran devait continuer à faire

Les huit contraintes C1→C8 de la 035, § 2. Deux ont demandé un vrai travail.

| # | Contrainte | Ce que la matière en fait |
| --- | --- | --- |
| C1 | **La couleur porte de l'information** | Renforcée : la couleur du circuit passe d'un trait à un **aplat**. La carte se lit désormais à deux mètres, ce qui était l'argument de la direction A |
| C2 | **Aucune dépendance extérieure** | Inchangé : quatre règles dans le `<style>` en ligne, aucun fichier ajouté |
| C3 | **Tenu à une main** | Aucune géométrie ne change. Le rayon du bouton passe de 22 à 18 px ; sa surface, non |
| C4 | **Lisible dans une salle** | Le liseré d'encre **augmente** le contraste des bords. Rien ne s'éclaircit |
| C5 | **« Effacer » ne pèse jamais autant qu'« Envoyer »** | L'écart se creuse : « Envoyer » gagne un liseré et une ombre, « Effacer » reste un texte nu |
| C6 | **Le voyant reste barré** | Pas touché |
| C7 | **On n'empêche jamais l'envoi** | Pas touché. Le bandeau hors-circuit et « Envoyer quand même » gardent leur jaune d'attention |
| C8 | **L'identité est celle du club** | Inchangée : la matière est prise sur `--encre`, pas sur une couleur nouvelle |

## 5. Les trois choses que seul un rendu pouvait montrer

Aucune des trois n'était visible à la relecture du code ni dans la maquette de
la 035. Elles justifient à elles seules la méthode du § 2.

### 5.1 Le souffle effaçait l'ombre

`#envoyer:not(:disabled)` porte une pulsation lente depuis la spec 007 — la
parité avec l'Android. Elle anime `box-shadow`, qui est une propriété
**unique** : la pulsation la réécrivait entièrement à chaque image, et l'ombre
imprimée disparaissait deux fois par seconde. Les images-clés reportent donc
les deux couches de l'ombre et n'ajoutent la lueur du circuit qu'en troisième.

**C'est la seule vraie couture entre la direction A et l'existant**, et la
maquette de la 035 ne pouvait pas la voir : elle n'avait pas de souffle.

### 5.2 Le liseré en dur ne survivait pas au thème sombre

La maquette écrivait `border: 2px solid #17140F`. Repris tel quel, le liseré
serait devenu **invisible** sur l'ardoise de la 039 — un trait presque noir sur
un fond presque noir. Pris sur `var(--encre)`, il devient de la **craie** sur
l'ardoise : un seul jeu de règles habille les deux thèmes.

### 5.3 Le circuit « Noir » avalait son propre liseré

C'est le seul circuit dont la teinte **est** l'encre du thème (spec 039). Sa
carte teintée à 13 % virait au **gris** quand toutes les autres sont teintées de
leur couleur, et le liseré de sa pastille se confondait avec l'aplat.

Montré sur un aperçu dédié, avec trois traitements. Adrien a choisi **N2** : sur
le seul « Noir », la carte reste du papier et le liseré s'efface — l'aplat noir
porte seul la couleur du circuit.

⚠️ Une quatrième variante a été capturée puis **écartée de la planche** : le
liseré d'encre sur l'aplat noir. Elle est **indiscernable** de N2 — un contour
noir autour d'un aplat noir ne se voit pas plus qu'un contour blanc. Elle a été
remplacée par une teinte à 6 %, qui, elle, se distingue.

### 5.4 La fusion avec la spec 040 a ressuscité une variable morte

Découvert **après coup**, et c'est le point le plus instructif du lot.

La 041 avait supprimé `--trait-circuit`, devenue sans lecteur une fois la carte
du bloc cerclée d'encre. La [spec 040](../040-theme-au-choix/), partie d'un
master antérieur, a recopié le bloc sombre pour en faire
`:root[data-theme="sombre"]` — **avec la variable dedans**.

Git a gardé les deux gestes et **n'a signalé aucun conflit** : la suppression
dans deux blocs, la copie dans un troisième. La variable est donc revenue dans
**un bloc sur trois**, où elle ne se lit plus comme un oubli mais comme un
réglage propre au thème imposé.

Une variable qui survit à son dernier lecteur ne dort pas : elle **ment**. La
prochaine lecture croit que le bord de la carte suit le circuit, change la
valeur, et ne voit rien bouger.

⚠️ Le piège n'est pas seulement réparé, il est rendu **détectable** :
`tests/test_matiere_imprimee.py` échoue désormais dès qu'une variable déclarée
dans la feuille du gabarit n'a plus aucun `var()` qui la lise. Vérifié en
réintroduisant le défaut : le test tombe, et il nomme la variable.

## 6. Le réglage qu'Adrien a rouvert

La direction A demandait « une ombre franche de 5 px ». Implémentée telle
quelle et montrée, elle a reçu : « **je trouve que ton ombre noir est trop
franche, un truc plus doux serait le bienvenue** ».

Cinq ombres lui ont été proposées sur le vrai écran, dont **celle qu'il venait
de refuser, gardée comme témoin** — sans elle, « plus doux » ne se compare à
rien. Il a choisi **S3 — courte, puis floue** : une arête de 3 px à 26 % d'encre
posée sur un halo de 20 px à 50 %.

L'ombre franche de la 035 n'est donc **pas** ce qui a été livré, et c'est
délibéré : la spec 035 décrivait une intention, le rendu a tranché la valeur.

## 7. Critères d'acceptation

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A1 | La carte du bloc scanné porte un aplat de son circuit et un liseré d'encre | Mesuré au navigateur : `background` et `border-top-width` du `#carteBloc.fait` |
| A2 | La pastille du bloc porte un liseré de 2 px | Mesuré : `border-top-color` de `.valeur` |
| A3 | Le bouton actif porte le liseré et l'ombre S3 | Mesuré : `box-shadow` à deux couches, `border-top-width` à 2 px |
| A4 | Le bouton désactivé n'a **aucune** ombre et un trait pointillé | Mesuré : `box-shadow: none`, `border-top-style: dashed` |
| A5 | Le souffle **conserve** l'ombre à chaque image | Relecture des images-clés : les deux couches sont dans les deux étapes |
| A6 | Toute la matière tient dans les **deux thèmes** | Les mêmes mesures sous `colorScheme: light` et `dark` |
| A7 | Sur « Noir », la carte reste du papier dans les deux thèmes | Mesuré : `background` du `#carteBloc.fait.encre` vaut `--carte-active` |
| A8 | « Noir » se reconnaît par son **nom**, jamais par sa valeur | `tests/js/couleurs.test.mjs` |
| A9 | Les téléphones déjà installés reçoivent la nouvelle feuille | `CACHE` passe à `climbcontest-juge-v7` |
| A10 | Aucune donnée personnelle dans les captures | Relecture : « Alix Ferrand », nom inventé |
| A11 | La matière suit le thème **imposé** par la spec 040, pas seulement celui du système | Mesuré sur les **six** croisements système × réglage × circuit |
| A12 | Aucune variable CSS déclarée sans lecteur | `tests/test_matiere_imprimee.py`, vérifié en réintroduisant le défaut |
| A13 | Le souffle ne peut plus effacer l'ombre | Idem : le test tombe si une étape cesse de la reporter |

## 8. Hors périmètre

- **L'app juge Android.** D5 de la 035 est tranchée : elle **ne suit pas**, et
  elle va être supprimée. La parité de `couleurs.js` était déjà rompue par la
  039, qui l'écrit.
- **La géométrie de l'écran.** La direction A ne changeait pas l'architecture —
  c'était la direction D. Aucune carte ne bouge, aucun texte ne change.
- **Le vocabulaire.** Aucun libellé n'est ajouté, retiré ni renommé.
- **La console et la page de résultats.** Elles ont leurs propres specs.
