# Spec 045 — architecture

## 1. Le principe : une seule porte

Le défaut qu'on ferme est revenu trois fois (spec.md §1) parce qu'à chaque fois
la règle était **à côté** du chemin d'écriture, et qu'il suffisait d'un chemin
qui ne l'appelait pas. La spec 008 a déjà réglé ça pour la casse en faisant
passer **toutes** les sources par `formatage` — classeur compris.

On ne construit donc pas une deuxième fonction à côté : `formatage.categorie()`
apprend à rattacher. Tout ce qui écrit une catégorie l'appelle déjà.

```
formulaire d'ajout ─┐
crayon (édition)   ─┤
« à trancher »     ─┼─→ formatage.categorie() ─→ base
import du classeur ─┤        │
barème (recalcul)  ─┘        └─ categories.OFFICIELLES (la liste FFME)
```

**Ce qui n'est pas dans ce schéma n'existe pas** : aucune vue, aucune route,
aucun outil n'écrit `Participant.categorie` sans passer par là. C'est vérifié
par une recherche, et le plan de test en fait un critère.

## 2. Les modules

### `climbcontest/categories.py` — la liste, à côté de la règle

Le module porte déjà « la règle des catégories d'âge, telle que la FFME la
publie ». Il gagne le **vocabulaire**, avec sa source :

```python
#: Les categories publiees par la federation. Regles d'acces et de
#: participation 2025-2026 (V3), §5.4, dans l'ordre du texte.
OFFICIELLES = ("U9", "U11", "U13", "U15", "U17", "U19", "U21",
               "Senior", "Veteran")

#: Les genres, dans l'ecriture des donnees reelles (fixtures/contest-nov2025).
GENRES = ("F", "H")

#: Les 18 libelles complets. C'est ce que propose la console, et rien d'autre.
LISTE = tuple(f"{c} {g}" for c in OFFICIELLES for g in GENRES)
```

⚠️ **Le docstring du module dit aujourd'hui « Rien n'est codé en dur ».** Il
faut le réécrire, pas le contourner — c'est un revirement, et le dépôt les
écrit (voir l'en-tête de `formatage.py`, « changement de doctrine assumé »). Le
texte à poser : *les **Under d'une édition** continuent de se déduire, parce
qu'une compétition ne fait pas grimper toutes les catégories ; le **vocabulaire**,
lui, est publié par la fédération et se cite.*

`unders_de`, `circuit`, `bareme`, `annees_attendues` ne changent pas d'une
ligne.

### `climbcontest/formatage.py` — le rattachement

```python
def categorie(texte):
    """« u13f », « 13 F », « U13 M » -> « U13 F », « U13 H ». Spec 045."""
    reduit = _vide(texte)
    if reduit is None:
        return None
    return rattacher(reduit) or _GENRE_COLLE.sub(r" \1", reduit.upper())
```

Le repli est **l'ancienne règle, intacte** : ce qu'on ne reconnaît pas ressort
comme avant (D4). Aucun appelant ne change.

`rattacher()` en cinq temps, sur du texte sans accent et en minuscules, les
séparateurs `-_/.,` ramenés à l'espace :

| # | Ce qu'on cherche | Comment |
| --- | --- | --- |
| 1 | découper | jetons séparés par des espaces, `u13f` → `u13f` reste un jeton |
| 2 | le Under | `^u?\s*(\d{1,2})$` sur un jeton, ou collé au genre `^u?(\d{1,2})([fhm])$` |
| 3 | l'adulte | `senior(s)?` → `Senior` ; `veteran(s)?\s*[12]?`, `v1`, `v2` → `Veteran` |
| 4 | le genre | le jeton restant est cherché dans `GENRES_CONNUS` |
| 5 | trancher | **un** âge et **un** genre, sans conflit → `f"{age} {genre}"`, sinon `None` |

**Trois gardes, chacune contre une erreur réelle :**

- `\d{1,2}` et non `\d+` : `2016` est une **année**, jamais une catégorie. Sans
  cette borne, une colonne décalée d'une case dans le classeur rangerait tout le
  monde en « U2016 ».
- Le Under doit être dans `OFFICIELLES` : `U12 F` n'existe pas, on ne l'invente
  pas.
- Deux âges ou deux genres différents dans la même chaîne → `None`. « U13 F et
  U13 H » est une **entête de tableau**, pas une catégorie.

### `GENRES_CONNUS` — une table, pas deux

La table des écritures du genre existe déjà, dans
`helloasso/correspondance.py` : `{"fille": "F", "m": "H", "garcon": "H", …}`.
Elle **déménage dans `formatage.py`**, avec `genre_connu()`, et
`correspondance.py` l'importe.

C'est la leçon écrite en toutes lettres au bas de `formatage.py` : *« si la
mise en forme et la comparaison sont dans deux modules, elles dérivent — l'une
gagne une règle que l'autre n'a pas, et le doublon revient par la porte qu'on
n'a pas refermée. »* Une deuxième table du genre serait exactement ça.

Le sens de la dépendance compte : `categories.py` reste **pur** (ni base, ni
Flask, ni import de `formatage`), et c'est `formatage` qui importe la liste.
L'inverse ferait un cycle.

### `climbcontest/bareme.py` — le repli de D7

```python
def unders(comp) -> list[int]:
    ...
    trouves = categories.unders_de(des_participants + des_circuits + declarees)
    # D7 : une edition neuve n'a aucune des trois sources. Le barème serait
    # vide, donc l'ecran Categories aussi. On retombe sur la liste officielle.
    return trouves or categories.unders_de(categories.OFFICIELLES)
```

Une seule ligne, et **seulement sur le vide** — voir l'avertissement de D7.

### `climbcontest/sheets/importer.py` — le signalement de D4

L'import appelle déjà `formatage.categorie`. Il gagne trois lignes : quand la
valeur écrite n'est **pas** dans `categories.LISTE`, le rapport le dit, avec le
numéro de ligne, comme il le fait déjà pour une catégorie absente.

```
⚠ Listes L34 : « POUSSIN » n'est pas une categorie FFME (importee telle quelle)
```

### `climbcontest/routes/admin.py` — deux routes

| Route | Ce qu'elle fait |
| --- | --- |
| `GET /admin/referentiels` | `categories` ne se déduit plus des participants : c'est `categories.LISTE`. Les valeurs **hors liste encore portées** sont rendues à part, dans `categories_hors_liste`, pour l'exception de D2 |
| `GET /admin/categories` | gagne `hors_liste` : `[{"valeur": "U13 M", "cible": "U13 H", "inscrits": 1}, …]` |
| `POST /admin/categories/rattacher` | `{"apercu": true}` rend le tableau sans rien changer ; sans `apercu`, applique, incrémente le catalogue, invalide le classement |

`POST /admin/categories/declarees` ne change pas de forme : elle passe déjà par
`formatage.categorie`, donc elle **refuse déjà** ce qui n'est pas officiel une
fois D3 en place. Un contrôle explicite est ajouté pour rendre le refus lisible
plutôt que silencieux (A12).

Le rattachement réutilise le motif d'`appliquer_bareme` : mêmes garanties,
mêmes appels (`incrementer_catalogue`, `classement_service.invalider`). ⚠️ Sans
`incrementer_catalogue`, les vingt-cinq téléphones gardent l'ancienne catégorie
pour toute la compétition.

### `climbcontest/templates/admin.html` — quatre points de saisie

| Endroit | Aujourd'hui | Demain |
| --- | --- | --- |
| `#pCategorie` (ajout) | `remplir(…, d.categories, …, avecAutre=true)` | les 18, `avecAutre=false` |
| `ligneEditable` (crayon) | `listeQuiCree(categoriesVues(), …)` | `listeOfficielle(p.categorie)` |
| « à trancher » (HelloAsso) | `listeQuiCree(categoriesVues(), …)` | `listeOfficielle(i.categorie)` |
| `#categoriesDeclarees` | champ texte, virgules | **fusionné** dans le tableau du barème : 2 colonnes d'interrupteurs |

`#filtreCategorie` **ne change pas** : il se déduit des données et doit
continuer de montrer « U13 M » tant que quelqu'un le porte, sinon la ligne à
corriger devient introuvable (spec.md §7).

`listeOfficielle(courante)` construit un `<select>` des 18, **plus la valeur
courante si elle est hors liste**, marquée « (hors liste) » — l'exception de D2,
et la seule. Elle finit par `select.value = courante` : c'est cette ligne qui
fait ouvrir le panneau sur la catégorie en cours (D9), et sans elle le
navigateur ouvre sur la première option.

Le tableau du barème gagne deux colonnes d'interrupteurs (D5) et **deux lignes**,
`Senior` et `Veteran`, que `bareme()` ne produit pas — elles n'ont pas de Under.
Elles se construisent à côté des tranches, avec leur compte d'inscrits, sur fond
grisé. `hors_de_portee()` fournit déjà ce comptage.

L'affichage accentué vit ici, en JavaScript, où les accents sont admis :

```js
// « Senior » en base et en JSON (pas d'accent dans les litteraux Python),
// « Sénior » a l'ecran. La table est ici, cote affichage, et nulle part ailleurs.
var ACCENTUE = { "Senior": "Sénior", "Veteran": "Vétéran" };
```

## 3. Ce qui n'est pas touché

`models.py` (aucune colonne), `classement.py`, `classement_service.py`,
`cycle.py` (`groupes_masques` reste le choix d'un humain), l'app juge, le
classeur Google. **Aucune migration de schéma** : une catégorie est du texte,
et le rattrapage de D6 est une écriture de données, pas une migration.

## 4. Les risques, et ce qui les rend visibles

| Risque | Ce qui le rend impossible ou visible |
| --- | --- |
| Un chemin d'écriture oublié | A15 : un test cherche `Participant.categorie =` hors du passage par `formatage` |
| `U13 M` revient au prochain import | D3 rattache **dans la porte d'entrée** : l'import lit « U13 M » et écrit « U13 H » |
| Le `<select>` change une catégorie en silence | D2, exception : la valeur courante reste dans sa propre liste, marquée |
| Les téléphones gardent l'ancienne catégorie | `incrementer_catalogue` après le rattachement, comme le barème |
| Deux tables du genre qui dérivent | Une seule table, dans `formatage.py`, importée par `correspondance.py` |
| Sept classements vides sur le mur | A14 : la charge publique se construit à partir des participants, et un test le dit |
