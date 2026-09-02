# 027 — Architecture

> Écrit après coup, comme la spec. Décrit ce qui EST, pas ce qui était prévu.

## Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/fiches.py` | `hauteur_mm`, `colonnes_qui_tiennent`, `en_feuilles` — le calcul d'impression passe du CSS au Python. `par_zone()` et le drapeau `coupure` **supprimés** |
| `climbcontest/routes/admin.py` | `page_dossards` / `page_etiquettes` passent `feuilles=` et `total=` ; l'ordre des classements vient de `classement_service.ordre` |
| `climbcontest/templates/dossards.html` | A4 paysage, six fiches, pagination serveur |
| `climbcontest/templates/etiquettes.html` | Huit par A4, plus de saut par zone |
| `climbcontest/templates/admin.html` | Bouton à maintenir, import enchaîné, pastilles de couleur, aides allégées |
| `climbcontest/templates/resultats.html` | Podium toujours affiché ; script converti en **module** |
| `climbcontest/static/resultats/podium.js` | **Nouveau** — la logique du podium, extraite pour être testable |
| `climbcontest/templates/juge.html`, `static/juge/juge.js`, `static/juge/sw.js` | Écran d'accueil, fond réchauffé, cache v3 |

## Les trois décisions structurantes

### 1. Le calcul d'impression quitte le CSS

`auto-fit` choisit ses colonnes d'après la **largeur** disponible, sans rien
savoir de la **hauteur** que ça produira. C'est la cause du chevauchement : dès
qu'un groupe de couleur passait sur deux lignes, la fiche débordait sur sa
voisine.

Le nombre de colonnes est donc calculé en Python, à partir de quatre constantes
**mesurées dans le navigateur** (`HAUTEUR_UTILE_MM`, `HAUTEUR_LIGNE_MM`,
`HAUTEUR_LIGNE_SUP_MM`, `MARGE_GROUPE_MM`).

⚠️ **Aucun test ne peut vérifier que ces quatre nombres décrivent encore le
CSS.** Les tests vérifient la cohérence du *calcul* — monotonie, coût d'une
ligne, coût d'une marge. L'accord avec la feuille de style se remesure au
navigateur quand le gabarit change.

### 2. La pagination quitte le CSS aussi

Une grille dont les éléments portent `break-inside: avoid` est fragmentée « au
mieux » par le navigateur, qui n'a aucune obligation de respecter un nombre
d'éléments par page. `en_feuilles()` découpe explicitement, et le saut de page
porte sur la **feuille**, jamais sur un élément de grille.

### 3. La logique du podium quitte le gabarit

Elle décidait seule de ce que le vidéoprojecteur montre à la remise des prix, et
**rien ne l'exécutait**. Deux défauts y vivaient. Elle est extraite dans
`static/resultats/podium.js` et testée par `tests/js/podium.test.mjs` — le même
motif que les modules de l'application juge.

Conséquence : `resultats.html` porte désormais `<script type="module">`. Sans
risque : la page n'a aucun gestionnaire en ligne et le script suit déjà tout le
balisage.

## Contrats

Aucune route ajoutée, aucun schéma modifié, aucune migration. `GET /admin/dossards`
et `GET /admin/etiquettes` rendent le même HTML, paginé différemment.

## Ce qui reste dupliqué, et pourquoi c'est surveillé

`MAXI_SUR_LE_PODIUM` (JavaScript) et les paliers `.groupe.cN` (CSS) doivent
s'accorder. C'est le seul endroit où l'accord peut se rompre sans que rien ne
casse — un septième ex æquo tomberait sur une marche sans style. Un test lit la
constante dans le module et vérifie les paliers du gabarit.
