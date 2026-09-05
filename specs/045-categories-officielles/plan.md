# Spec 045 — plan

## Étapes

- [x] **1. La liste** — `categories.OFFICIELLES`, `GENRES`, `LISTE`, et le
      docstring du module réécrit : ce qui se déduit (les Under d'une édition),
      ce qui se cite (le vocabulaire).
- [x] **2. Le genre, une seule table** — `GENRES_CONNUS` et `genre_connu()`
      passent de `helloasso/correspondance.py` à `formatage.py`.
      `correspondance.py` les importe. Aucun changement de comportement.
- [x] **3. Le rattachement** — `formatage.rattacher()`, et `formatage.categorie()`
      qui l'appelle avant son repli. C'est l'étape qui porte la table de cas.
- [x] **4. Le repli du barème (D7)** — `bareme.unders()` retombe sur les neuf
      officielles quand les trois sources sont vides.
- [x] **5. Le rapport d'import (D4)** — `sheets/importer.py` signale une
      catégorie hors liste, sans rien refuser.
- [x] **6. Les routes** — `referentiels` rend `LISTE`, `categories` rend
      `hors_liste`, et `POST /admin/categories/rattacher` (aperçu + application).
- [x] **7. La console** — les trois listes déroulantes (dont `select.value`
      posé avant affichage, D9), la **fusion** du barème et des catégories
      déclarées en un seul tableau à interrupteurs (D5), la carte de
      rattrapage, la table d'accentuation.
- [x] **8. Le changelog** — section `[Non publié]`, et l'index des specs.

L'ordre n'est pas indifférent : 1→3 se testent **sans monter l'application**,
et c'est là que se joue la valeur de la spec. 7 ne commence qu'une fois la
maquette validée.

## Plan de test

### Le rattachement — `tests/test_categories_officielles.py`

| Ce qui arrive | Attendu | Ce que ça protège |
| --- | --- | --- |
| `u13 f`, `U13F`, `u13f`, `U13  F` | `U13 F` | casse et espace (déjà couvert, on ne le perd pas) |
| `13 F`, `13f`, `13-F` | `U13 F` | **le U manquant** — demande d'Adrien |
| `U 13 H`, `U13-H`, `U13/H`, `U13.H` | `U13 H` | séparateurs |
| `U13 M`, `u13m`, `U13 masculin`, `U13 garçon` | `U13 H` | **le « U13 M » de production** |
| `U13 fille`, `U13 féminin`, `U13 Femme`, `U13 girl` | `U13 F` | écritures du genre |
| `Homme U13`, `F U13` | `U13 H`, `U13 F` | ordre inversé |
| `sénior femme`, `SENIORS F`, `senior h` | `Senior F`, `Senior H` | accents, pluriel |
| `Vétéran 1 H`, `veteran 2 h`, `V1 F`, `v2 f` | `Veteran H`, `Veteran F` | la fusion D1 |
| `U9 f`, `U21 H` | `U9 F`, `U21 H` | les deux bouts de la liste |
| `U13` | `U13` | pas de genre : inchangé |
| `2016`, `U2016 F` | inchangé | **une année n'est pas une catégorie** |
| `U12 F`, `U10 H`, `U8 F` | inchangé | pas un Under officiel |
| `Poussin`, `Minime F`, `Benjamin H` | `POUSSIN`… | ancienne nomenclature : repli sur l'ancienne règle |
| `U13 F et U13 H` | inchangé | **deux genres : ambigu** |
| `U13 U15 F` | inchangé | deux âges : ambigu |
| `` , `None`, `   ` | `None` | le vide reste le vide |

| Module | Scénario | Attendu |
| --- | --- | --- |
| `categories` | `LISTE` a 18 entrées, dans l'ordre du §5.4 | les 10 alinéas écrits en toutes lettres dans le test, Vétérans fusionnés |
| `categories` | `LISTE` est **ASCII** | `"".join(LISTE).encode("ascii")` ne lève pas |
| `categories` | `under()` lit les nouvelles | `U9`→9, `U21`→21, `Senior`→None, `Veteran`→None |
| `formatage` | tout `LISTE` est un point fixe | `categorie(x) == x` pour les 18 |
| `formatage` | `genre_connu` inchangé | la table de `correspondance` rejouée telle quelle |

### Le barème — `tests/test_bareme.py` (complété)

| Scénario | Attendu |
| --- | --- |
| Édition sans participant, sans circuit, sans déclaration | 9 tranches, années tirées de `comp.date` (A13) |
| La même, date reculée d'un an | les 9 tranches décalées d'un an, sans autre changement |
| Édition qui déclare U11, U13, U15 | **3** tranches — le repli ne s'applique pas (D7) |
| Édition avec des inscrits U11/U13 seulement | 2 tranches, comme aujourd'hui |

### L'import — `tests/test_import_categories.py`

| Scénario | Attendu |
| --- | --- |
| Le classeur dit `u13m` | le participant porte `U13 H` (A8) |
| Le classeur dit `13 F` | `U13 F` |
| Le classeur dit `Poussin` | `POUSSIN` en base **et** une ligne dans le rapport (A9) |
| Le classeur dit `U13 M` sur un participant déjà rattaché à `U13 H` | rien ne bouge : la valeur écrite est déjà la bonne |
| Deux imports de suite | le rapport ne signale qu'une fois par ligne, pas deux |

### Les routes — `tests/test_categories_console.py`

| Scénario | Attendu |
| --- | --- |
| `GET /admin/referentiels` | `categories` = les 18, dans l'ordre |
| idem, base portant `U13 M` | `categories_hors_liste` = `["U13 M"]` |
| `GET /admin/categories` | `hors_liste` = `[{valeur, cible, inscrits}]` |
| `POST /categories/rattacher {"apercu": true}` | le tableau, **et la base inchangée** (A10) |
| `POST /categories/rattacher` | `U13 M` → `U13 H`, n° de catalogue **incrémenté** (A11) |
| idem, catégorie sans cible (`POUSSIN`) | laissée en place, comptée à part |
| `POST /categories/declarees {"categories": ["Poussin"]}` | 400, message lisible (A12) |
| `POST /categories/declarees {"categories": ["u13f"]}` | accepté, rangé `U13 F` |
| Sans session | 401 sur les trois |

### La page de résultats — `tests/test_categories_vides.py` (D8)

| Scénario | Attendu |
| --- | --- |
| Édition qui déclare 9 catégories, 3 inscrits en U13 F | `/api/public/classement` ne porte **que** `U13 F` et ses dérivés (A14) |
| Un inscrit arrive en U15 H | le groupe `U15 H` paraît **sans aucun geste** |
| `U13 F` masqué à la main, puis import | reste masqué (A15) — D8 ne démasque pas ce qu'un humain a caché |

### La console — `tests/test_navigateur_categories.py`

Un seul harnais, un seul parcours, une sonde qui relève tout (motif de
`test_navigateur_participants.py`).

| Mesure | Attendu |
| --- | --- |
| `optionsAjout` | 18 (A5) |
| `autreDansAjout` | absent (D2) |
| `optionsCrayon` | 18 (A6) |
| `crayonHorsListe` | la ligne `U13 M` ouverte reste sur `U13 M`, marquée (A7) |
| `interrupteurs` | 18 `role="switch"`, 9 lignes, dans le **même** tableau que les années |
| `ouvreSurCourante` | `#pCategorie` et le crayon portent leur valeur AVANT affichage (A16) |
| `carteHorsListe` | visible, une ligne `U13 M → U13 H` |
| `apercuAvantApres` | le tableau paraît **avant** que rien ne change |

### Ce que le code interdit — `tests/test_une_seule_porte.py`

| Scénario | Attendu |
| --- | --- |
| Recherche de `\.categorie\s*=` dans `climbcontest/` | chaque occurrence est soit dans `formatage`, soit une affectation dont la valeur vient de `formatage.categorie(...)` ou de `bareme` |

⚠️ Ce test-là est le seul qui empêche le défaut de revenir une **quatrième**
fois. Les autres vérifient que la règle est bonne ; celui-ci vérifie qu'aucun
chemin ne la contourne.

## Ce qui a été validé avant de coder

La **maquette** (`maquettes/index.html`), en deux tours. Le premier a rendu
trois arbitrages : des interrupteurs et non des cases, des listes qui s'ouvrent
sur la catégorie en cours, et **un seul tableau** au lieu de deux cartes. Porte
2 franchie le 05/09.

## Ce que le rendu réel a montré que la maquette ne montrait pas

Une édition qui n'annonce pas U9 donne à U11 « jusqu'à 10 ans » — « le plus
petit Under l'emporte ». U9, éteinte, continuait pourtant d'annoncer « jusqu'à
8 ans » juste au-dessus : deux tranches qui se chevauchent, sans que rien ne
dise laquelle s'applique. Les deux étaient vraies, et c'est bien le problème.
Toute ligne hors du barème de l'édition est désormais grisée, pas seulement
celles sans Under.
