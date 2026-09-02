# Spec 028 — Le plan du mur en polygones

> **Statut : soumise à la porte 2.** Écrite avant le code, cette fois.
> Demande d'Adrien du 02/09/2026 : « je voudrais qu'on retravaille le plan qui
> est sur les dossards, car il n'est pas très beau et ne représente pas
> vraiment la forme du mur », puis « je voudrais un truc où je puisse faire des
> formes plus triangulaires, peut-être même en symbolisant les surplombs et
> pans inclinés. Bref je veux un truc plus joli que de simples blocs en mode
> tableur. C'est tout l'intérêt de le faire nous-même : on peut avoir quelque
> chose de joli et plus représentatif. »

## 1. Ce qui ne va pas

Le plan imprimé sur chaque dossard est une **grille de 8 lignes × 7 cases**
(`fiches.PLAN`, spec 023). Chaque zone occupe une case, les repères « Escalier »
et « Haut » en occupent trois.

Une grille ne sait pas dire trois choses que le grimpeur a besoin de savoir :

1. **La forme réelle de la salle.** Les murs d'Annonay ne sont pas des carrés
   alignés. Une case ne peut être ni un triangle, ni un trapèze, ni une proue.
2. **Le profil d'un mur.** Dalle, vertical, dévers, surplomb, toit : la grille
   n'a aucun endroit où le mettre.
3. **Les proportions.** Une case fait la même taille qu'une autre, qu'elle
   représente cinq mètres de mur ou trente.

Conséquence mesurable : sur le relevé de mars 2026, la grille rangeait dix-sept
zones dans un damier qui ne ressemble à rien de ce qu'on voit en entrant.

## 2. Ce qu'on fait

### F1 — `PLAN` devient un jeu de polygones

```python
PLAN = {
    "vue": (120, 150),                   # les unités du dessin
    "contour": ((x, y), ...) | None,     # le pourtour de la salle, facultatif
    "murs": (
        {"zone": "J", "profil": "devers",
         "points": ((x, y), ...),        # polygone libre, 3 points ou plus
         "etiquette": (x, y) | None},    # où poser la lettre ; None = centroïde
        ...
    ),
    "reperes": ({"texte": "Escalier", "point": (x, y)}, ...),
)
```

Six profils, **ordonnés du moins au plus déversant** :
`dalle`, `vertical`, `incline`, `devers`, `surplomb`, `toit`.

⚠️ **La position de `incline` a été tranchée par Adrien lui-même**, en assignant
les profils à ses murs : il l'a placé **après** `vertical`, donc du côté qui
déverse. La question était réelle — « incliné » ne dit pas dans quel sens — et
une session parallèle avait fait l'hypothèse inverse.

`ZONES_DU_PLAN` reste dérivé de `PLAN`, jamais recopié. `numero()` et le repli
`hors_plan` ne changent pas.

### F2 — Le relevé d'Annonay

Fourni par Adrien le 02/09, dessiné avec la planche de dessin — qui vivait
alors dans `tools/plan-du-mur/`, et que la **spec 029** a déplacée dans la
console. Ce relevé compte **17 murs**,
6 profils utilisés, **3 repères** (« Escalier », « Haut », et « Bas » qui
n'existait pas dans la grille), **pas de contour**.

### F3 — Le dossard rend un SVG, sobre

Le gabarit remplace sa grille CSS par un SVG en ligne. **Le dossard reste en
noir et blanc** — Adrien : « seule la partie sur dossard doit rester sobre ».

Le profil se lit à la **trame**, jamais à la couleur : la fiche s'imprime à
l'encre noire, et la couleur y serait perdue. La trame se densifie et le gris
fonce à mesure que le mur déverse — deux variables redondantes sur un seul axe
ordonné, une seule règle à apprendre.

⚠️ **Trois pièges mesurés pendant la conception**, tous dans le rendu :

- **Le cadrage.** Sept des murs d'Adrien touchent le bord du dessin. Un
  `viewBox="0 0 120 150"` rogne la moitié de leur trait. Il faut une marge :
  `viewBox="-1 -1 122 152"`. La marge se prend sur le `viewBox`, **jamais sur
  les coordonnées** — décaler les points, ce serait maquiller le relevé.
- **La taille de la lettre.** Mesurée : à 9 unités fixes, aucune des 17 zones
  ne déborde, mais la marge n'est que de **0,25 unité**. Une zone à deux
  caractères la crève. La taille se calcule donc depuis la boîte du mur, avec un
  plancher à 3,5 unités (1,06 mm sur la colonne de 37 mm).
- **L'état contre le profil.** Une zone « sienne » est un aplat noir, qui mange
  la trame — donc le grimpeur perd le profil **sur les zones qui l'intéressent**.
  La trame est reposée en clair par-dessus l'aplat.

### F4 — `plan_pour(zones)`

```python
def plan_pour(zones: set[str]) -> dict:
    """{vue, contour, murs: [{zone, profil, points, etiquette, sienne}], reperes}"""
```

Pas de paramètre `visee` : la session qui construit la fiche en direct
(spec 026) n'en a plus besoin, elle pose ses états elle-même.

## 3. Périmètre

**Exclu, à dessein — et c'est une décision d'Adrien du 02/09** : **le rendu du
mur à l'écran**. « Le rendu mur sera chez elle. » La page de résultats et la
fiche en direct dessinent leur propre SVG, avec leurs couleurs, dans le cadre de
la spec 026. Cette spec-ci ne livre donc **aucun** partiel Jinja pour l'écran,
et `fiches.py` n'expose aucune teinte.

Les palettes d'écran mises au point ici — l'échelle froid → chaud qui bascule
quand le mur passe la verticale — ont été transmises à cette session. Elle en
fait ce qu'elle veut.

**Exclu aussi** : le plan par compétition. `PLAN` reste une **constante**. Le
club a un mur ; le jour où il en aura deux, ce sera une autre spec.

## 4. Critères d'acceptation

- [ ] **A1** — `PLAN` porte le relevé d'Adrien : 17 murs, 3 repères, pas de
  contour.
- [ ] **A2** — `ZONES_DU_PLAN` est dérivé de `PLAN` et vaut les 17 lettres.
- [ ] **A3** — `plan_pour(zones)` marque `sienne` sur les bons murs et sur eux
  seuls.
- [ ] **A4** — Le dossard rend un SVG ; **aucune** des 17 lettres ne déborde de
  son mur, mesuré dans le navigateur, halo compris.
- [ ] **A5** — Une zone nommée sur deux ou trois caractères ne déborde pas non
  plus.
- [ ] **A6** — Aucun trait n'est rogné par le bord du dessin.
- [ ] **A7** — Une zone « sienne » garde sa trame de profil lisible.
- [ ] **A8** — Un bloc dans une zone absente du plan alimente `hors_plan`.
- [ ] **A9** — Le dossard n'utilise **aucune couleur porteuse de sens** :
  sa palette est faite de gris chauds (`#EFECE6` … `#8D8473`), qui deviennent
  une échelle de gris à l'impression noir et blanc. Le critère disait
  « aucune couleur », ce qui est faux au sens strict — ces gris sont
  chromatiques. Ce qui compte, et qui est tenu : **rien de ce que le
  dossard doit dire ne dépend de la teinte**.
- [ ] **A10** — Les 120 fiches tiennent toujours sur 20 feuilles : le SVG ne
  change pas la hauteur utile.
- [ ] **A11** — Aucune ressource extérieure dans la page.

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| `contour` à `None` | Le plan se rend sans pourtour |
| Mur à 3 points (triangle) | Rendu normal ; la lettre va au centroïde |
| Polygone concave | `etiquette` explicite si le centroïde tombe dehors |
| Profil inconnu dans la donnée | Repli sur `vertical`, pas d'erreur |
| Zone sans lettre (`""`) | Le mur se dessine, sans lettre |
| Deux murs superposés | Les deux se dessinent ; c'est au relevé d'être juste |
| `PLAN` vide | La colonne « Le mur » disparaît, la fiche garde sa mise en page |
| Bloc en zone « Q », hors plan | « Hors plan : zone Q. » sous le dessin |
