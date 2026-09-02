# 028 — Architecture

## Le changement de forme

`PLAN` passe d'un **tableau de lignes et de cases** à un **jeu de polygones**.

```python
PLAN = {
    "vue": (120, 150),                   # les unités du dessin
    "contour": ((x, y), ...) | None,
    "murs": ({"zone", "profil", "points", "etiquette"}, ...),
    "reperes": ({"texte", "point"}, ...),
}
```

Six profils **ordonnés** du moins au plus déversant : `dalle`, `vertical`,
`incline`, `devers`, `surplomb`, `toit`. L'ordre **est** l'information — la
trame se densifie et le gris fonce à mesure qu'on descend la liste.

## Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/fiches.py` | `PLAN`, `PROFILS`, `plan_pour()`, `taille_lettre()`, `_centroide()`, `_cadre()`, `zones_du_plan()`. `REPERE()` supprimé |
| `climbcontest/templates/dossards.html` | La grille CSS devient un SVG en ligne |
| `climbcontest/routes/admin.py` | La route passe `profils=` au gabarit |

## Les trois pièges, et pourquoi ils sont là

Ils ont tous été trouvés **en affichant**, jamais en lisant. C'est la raison
pour laquelle ce fichier existe : qu'ils ne soient pas redécouverts.

### Le cadrage se prend sur le `viewBox`, jamais sur les points

Sept des dix-sept murs d'Annonay touchent le bord du dessin — `L`, `M`, `N` à
gauche, `X` et `Y` en haut, `E` à droite. Un `viewBox="0 0 120 150"` rogne la
moitié de leur trait.

⚠️ Décaler les coordonnées pour faire de la place **maquillerait le relevé** pour
arranger un problème d'affichage. La marge vit dans `MARGE_PLAN` et n'entre que
dans `cadrage`.

### La lettre se calcule, et se borne par le PIRE glyphe

`taille_lettre()` part de la boîte du mur. La largeur d'une capitale est prise à
`LARGEUR_CAPITALE = 0.85`, **pas** à la moyenne de 0,62 : mesuré au navigateur,
onze combinaisons de deux caractères sur trente-neuf débordaient avec la
moyenne — « M », « N » et « W » la crèvent. Une moyenne ne borne rien.

### L'état vit dans l'aplat, le profil dans la trame

Une zone « sienne » est un aplat noir, qui mange la trame. On la repose **en
clair par-dessus** — sinon le grimpeur perd le profil précisément sur les zones
qui l'intéressent.

## Les motifs SVG, déclarés une seule fois

Un identifiant SVG vaut dans **tout le document**. 120 fiches × 6 profils × 2
variantes feraient 1 440 identifiants en double, et `url(#pl-devers)` résout sur
le premier trouvé. Les `<pattern>` sont donc déclarés une fois, dans un
`<svg width="0">` en tête de document, et référencés depuis les 120 SVG de fiche.

## Ce que le SVG expose

Chaque mur sort en `<polygon data-zone="J" data-profil="devers">`. Ce n'est pas
décoratif : c'est ce qui rend le rendu **vérifiable par un test** plutôt que par
l'œil, et c'est le crochet convenu avec la spec 026 pour l'affichage à l'écran.

## Ce qui reste hors de ce module

Le rendu du même plan **à l'écran** appartient à la spec 026, par décision
d'Adrien du 02/09 : « le rendu mur sera chez elle ». `fiches.py` n'expose donc
aucune teinte d'écran, et aucun partiel Jinja n'est livré pour la page publique.
