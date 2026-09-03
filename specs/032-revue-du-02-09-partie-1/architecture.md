# 032 — Architecture

> Écrit après coup, comme la spec. Décrit ce qui **est**, pas ce qui était prévu.

## Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/fiches.py` | `mise_en_page_blocs`, `taille_case_mm`, `hauteur_ligne_mm`, `taille_numero_mm` — le calcul d'impression gagne son **axe horizontal**. `HAUTEUR_LIGNE_MM` et `HAUTEUR_LIGNE_SUP_MM` deviennent **déduites** ; `colonnes_qui_tiennent` devient une façade |
| `climbcontest/templates/dossards.html` | A4 paysage à 10 mm, feuille 276 × 186, `minmax(0, 1fr)`, `--case` servi par le serveur, `print-color-adjust` |
| `climbcontest/templates/etiquettes.html` | A4 portrait à 10 mm, feuille 188 × 272, QR 42 mm, texte agrandi, `--taille` servi par le serveur, `print-color-adjust` |
| `climbcontest/templates/admin.html` | `#blocRegleCascade`, l'intention `cascade.surMesure`, l'avertissement découplé, `celluleTeinte` sans texte, `.lu-seulement` |
| `climbcontest/templates/resultats.html` | `dessinerBarre` passe par `groupesVisibles()`, la rotation se réarme, le bouton ▶/⏸ sort du mode mur |
| `climbcontest/templates/plan.html` | `href="/admin"` → `href="/console"` |

Aucune route ajoutée, aucun schéma modifié, aucune migration. `GET /admin/dossards`
et `GET /admin/etiquettes` rendent le même HTML, mis en page différemment.

## Les quatre décisions structurantes

### 1. Une feuille d'impression doit être plus PETITE que la page

C'est la leçon de R8, et elle vaut d'être écrite parce que la version
précédente était *juste* sur le papier et fausse à l'impression.

La géométrie posait `margin: 6mm` et une feuille de 285 × 198 — la surface utile
exacte. Aucune tolérance. Or la zone réellement imprimable dépend du **pilote**
et du **papier**, pas du CSS, et le navigateur arrondit les millimètres en
pixels : mesure au navigateur, la feuille se rendait à **198,01 mm** dans une
page de 198. Un centième de millimètre suffit à déclencher la fragmentation.

Mesure, en imprimant la même planche avec une zone imprimable rognée :

```
                       6mm   8mm  10mm  12mm  14mm
fiches, avant   (20)    20    40    40    40    40
fiches, après   (20)    20    20    20    20    20
```

La feuille tient désormais dans 276 × 186 sur une page utile de 277 × 190,
posée à 10 mm des bords, et porte `break-inside: avoid` en **deuxième ligne de
défense** : si la zone imprimable était quand même trop courte, la feuille
entière partirait à la page suivante — une page perdue, jamais une rangée
coupée en deux.

⚠️ **Invariant à tenir, et il est testé** : `--feuille-hauteur` ≤ surface utile
− 2 mm, `--feuille-largeur` ≤ surface utile − 1 mm. Le test lit les nombres
dans le CSS rendu et refait le calcul ; il ne fige aucune valeur.

### 2. Le calcul d'impression gagne son axe horizontal

La spec 027 avait sorti le choix des colonnes du CSS, pour la **hauteur**. La
largeur, elle, restait à `1fr` — c'est-à-dire `minmax(auto, 1fr)`, une piste qui
ne descend **jamais** sous la largeur de son texte. Une grille trop serrée ne
rétrécit pas : elle **déborde**, silencieusement, par-dessus le plan du mur.

Les deux axes se décident maintenant **ensemble**, dans `mise_en_page_blocs` :

- peu de colonnes → cases larges, gros texte, mais **plus de lignes** ;
- petit texte → **lignes moins hautes**, donc plus de colonnes possibles.

On parcourt les colonnes du plus petit nombre au plus grand ; le premier couple
qui tient en hauteur est donc celui qui garde **le plus gros texte**. La
hauteur d'une ligne cesse d'être une constante et se déduit de la taille du
texte (`hauteur_ligne_mm`), sans quoi le calcul refuserait des mises en page qui
tiennent en vrai.

Même motif pour le numéro d'une étiquette (`taille_numero_mm`) : la colonne fait
42 mm, « J6 » y tient à 26 mm et « J32 » à 19. Le CSS ne sait pas compter les
caractères ; le serveur, si. Il les sert en `--case` et `--taille`, comme
`--cols` depuis la 027.

### 3. Les constantes restent MESURÉES, et le disent

Six nombres décrivent le CSS sans que rien ne puisse le vérifier :
`HAUTEUR_UTILE_MM`, `HAUTEUR_LIGNE_FIXE_MM`, `HAUTEUR_LIGNE_PAR_TAILLE`,
`LARGEUR_BLOCS_MM`, `CHASSE_CASE`, `CHASSE_NUMERO`.

Remesurés au navigateur le 02/09 sur le gabarit réel :

| Constante | Mesure |
| --- | --- |
| `HAUTEUR_UTILE_MM` | `.blocs` fait 56,62 mm, moins 3,65 de titre → **52,9** |
| `LARGEUR_BLOCS_MM` | **59,8** mm dans une fiche de 138 |
| `CHASSE_CASE` | 0,797 em mesuré → **0,82** arrondi prudemment |
| `CHASSE_NUMERO` | 0,705 em mesuré → **0,72** arrondi prudemment |

⚠️ La première version de `CHASSE_NUMERO` avait été **estimée** à 0,58 : « M40 »
débordait de neuf millimètres. C'est le même piège que la 027 avait déjà payé —
25 % d'erreur sur la hauteur d'une ligne. **On ne les estime pas.**

`HAUTEUR_LIGNE_MM` et `HAUTEUR_LIGNE_SUP_MM` survivent en tant que valeurs
**déduites** de la formule à la taille de référence : elles disent le coût d'une
ligne dans le cas ordinaire, et les tests de la 027 continuent de s'appuyer
dessus.

### 4. L'intention d'un réglage ne se déduit pas toujours de son état

R2 en est le cas d'école. La carte de la cascade déduisait le bouton coché des
phrases écrites, ce qui est propre — un seul état, pas de doublon qui mente.
Mais « je veux retoucher à la main les phrases du classeur » **n'est pas
observable dans les phrases** : elles sont, à cet instant, exactement celles du
classeur.

`cascade.surMesure` porte donc l'intention, et **elle seule**. Tout le reste
continue de se déduire des phrases — en particulier l'avertissement « le
classeur ne saura pas suivre », qui répond à une question sur les phrases. Les
deux ne doivent pas être confondus, et un test le garde explicitement.

## Ce qui reste dupliqué, et pourquoi c'est surveillé

Les nombres de la géométrie d'impression vivent **des deux côtés** : en
millimètres dans le CSS (`--fiche-largeur`, `--feuille-hauteur`…) et en
constantes Python (`LARGEUR_BLOCS_MM`, `HAUTEUR_UTILE_MM`…). C'est inévitable —
le serveur doit connaître la place dont dispose le CSS pour calculer une taille
de police — et c'est le seul endroit où l'accord peut se rompre sans que rien ne
casse : le texte se mettrait simplement à déborder de nouveau.

Deux garde-fous : `minmax(0, 1fr)` et `overflow: hidden` bornent le dégât à une
troncature dans la case, jamais à un débordement sur le plan ; et les tests de
format relisent les variables **dans le CSS rendu** pour vérifier l'invariant de
la feuille. L'accord des six constantes mesurées, lui, se **remesure au
navigateur** quand le gabarit change. Aucun test ne peut le faire.
