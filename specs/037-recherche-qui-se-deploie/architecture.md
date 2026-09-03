# Architecture — spec 037

Rien n'est implémenté tant que la variante n'est pas choisie. Ce document dit
**où le code ira** et **ce qui ne bougera pas**, pour que la décision se prenne
en connaissant son prix.

## 1. Ce qui existe déjà, et qu'on ne refait pas

La spec 033 a posé toutes les pièces :

- `#masquerRecherche` est un bouton **dessiné** (SVG, `currentColor`), plus un
  glyphe de texte ;
- `basculerRecherche(masquee)` tient l'état, la classe `body.sans-recherche`,
  `aria-pressed` et l'étiquette ;
- le choix « la recherche est-elle disponible » est mémorisé dans
  `CLE_AFFICHAGE`, à côté de l'état lecture/pause ;
- la recherche part **masquée**.

⚠️ **Deux états, pas un.** Il faut les garder distincts, sinon on mélangera vite
« le champ est-il déployé » (un geste, jamais mémorisé) et « la recherche est-elle
offerte » (un réglage, mémorisé). La spec 020 avait posé le second ; la 037
n'ajoute que le premier.

## 2. Fichiers touchés, quand le code viendra

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/templates/resultats.html` | L'ordre des deux boutons dans `<header>`, le balisage du champ (il entre dans la rangée des commandes), les règles de transition, et l'ouverture/fermeture dans `basculerRecherche` |
| `tests/test_page_resultats.py` | L'ordre des boutons, `aria-expanded`, le champ hors de l'ordre de tabulation quand il est fermé |
| `tests/test_navigateur_reglages_resultats.py` | Le geste complet, dans un vrai navigateur |

Aucun fichier Python, aucune route, aucune migration : c'est de la page.

## 3. Le point technique qui coûtera, quelle que soit la variante

Le champ est aujourd'hui **hors de l'en-tête** — il vit entre `#barre` et
`<main>`. Les trois variantes le font entrer **dans la rangée des commandes**.
Trois conséquences :

1. **La largeur du champ n'est plus celle de la page** mais celle qui reste sur
   la rangée. C'est exactement le compromis que les verdicts de la maquette
   chiffrent.
2. **Le point de rupture de 680 px devient structurant** : au-dessus, la rangée
   des commandes est au bout d'une ligne pleine. D'où la question ouverte du
   §5 de la spec.
3. **`display: none` ne peut plus servir à masquer le champ** : on n'anime pas
   depuis `display: none`. Il faudra une largeur (V1, V2), un `clip-path` (V3)
   ou une grille `0fr → 1fr` (V4) — et, dans tous les cas, `inert` ou
   `visibility` pour le sortir de l'ordre de tabulation quand il est fermé.
   ⚠️ Un champ animé mais toujours focusable est un piège classique : le Tab
   part dedans alors que rien ne se voit.

## 4. Ce qui ne doit pas casser

| | |
| --- | --- |
| Le mode `?mur` | Aucune commande, aucune recherche — inchangé |
| La recherche traverse **tous** les classements | Un parent ne connaît pas la catégorie de son enfant |
| Masquer vide le filtre | Une liste filtrée sans champ visible est indéchiffrable |
| Le réglage mémorisé | Il survit au rechargement, comme l'état lecture/pause |
