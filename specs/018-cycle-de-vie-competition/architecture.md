# Architecture — spec 018

## 1. Vue d'ensemble

```
console ─┬─ POST /admin/classeur/test          ─→ parametrage.tester(…, ecriture=True)
         │                                        └→ Google : get, update, get, clear
         │
         ├─ POST /admin/import/sheet           ─→ importer.lire_tout()   (RÉSEAU d'abord)
         │      {mode, confirmation}              puis, si mode=remplacer :
         │                                          cycle.effacer_donnees()
         │                                        puis importer.importer(lecture=…)
         │
         ├─ POST /admin/competition/statut     ─→ cycle.regler_statut()
         │      {statut}
         │
         ├─ POST /admin/donnees/effacer        ─→ cycle.effacer_donnees()   (base seule)
         │      {confirmation, forcer}
         │
         ├─ POST /admin/archives               ─→ cycle.archiver()  ─→ table `archive`
         ├─ GET  /admin/archives               ─→ cycle.lister()    (sans lire `contenu`)
         ├─ GET  /admin/archives/<id>/classement  ← ce que consomme la page de résultats
         ├─ GET  /admin/archives/<id>/fichier     ← téléchargement, JSON daté
         └─ DELETE /admin/archives/<id>        ─→ ADMIN + confirmation

page     ── GET /console/archives/<id>/resultats ─→ render_template("resultats.html",
                                                       source="/admin/archives/<id>/classement")
```

Un seul changement de modèle : **une table**. Aucune migration SQL —
`db.create_all()` crée les tables absentes, y compris sur une base existante
(`schema.py`, § « create_all ne touche pas aux tables existantes »).

## 2. Le modèle — la table `archive`

```python
class Archive(db.Model):
    __tablename__ = "archive"

    id             = Column(Integer, primary_key=True)
    competition_id = Column(Integer, nullable=False)   # ⚠️ PAS de ForeignKey
    nom            = Column(String(120), nullable=False)
    date           = Column(Date, nullable=False)
    format         = Column(Integer, nullable=False, default=1)
    cree_le        = Column(DateTime, nullable=False, default=func.now())
    cree_par       = Column(String(80))

    # Recopiés pour que la LISTE n'ait jamais à désérialiser `contenu` (A23).
    participants   = Column(Integer, nullable=False, default=0)
    blocs          = Column(Integer, nullable=False, default=0)
    reussites      = Column(Integer, nullable=False, default=0)

    contenu        = Column(Text, nullable=False)      # le JSON complet
```

**Pas de clé étrangère vers `competition`, et c'est le point central de cette
table.** Une archive doit survivre à l'effacement de ce qu'elle décrit — c'est
sa seule raison d'être. Une `ForeignKey` avec `PRAGMA foreign_keys=ON`
(la base l'active) ferait exactement l'inverse : elle empêcherait la suppression,
ou l'emporterait en cascade. `competition_id` reste un entier de traçabilité,
jamais une contrainte.

**Pas d'index.** Une dizaine de lignes par décennie, lues par `ORDER BY cree_le
DESC`. La clé primaire suffit.

### Le contenu, format 1

```json
{
  "format": 1,
  "cree_le": "2026-11-15T18:42:03",
  "cree_par": "adrien",
  "competition": {"id": 3, "nom": "…", "date": "2026-11-15",
                  "statut": "terminee", "spreadsheet_id": "1ilQ…"},
  "compteurs": {"participants": 196, "blocs": 50, "circuits": 4, "reussites": 3120},
  "classement": { … la réponse de /api/public/classement, VERBATIM … },
  "donnees": {"participants": [...], "blocs": [...],
              "circuits": [...], "reussites": [...]}
}
```

Deux couches, et chacune a son emploi :

- **`classement`** est la réponse de `/api/public/classement` telle quelle. La
  route de rejeu la ressert **sans rien recalculer** : la consultation d'une
  archive ne dépend donc ni du moteur de classement d'aujourd'hui, ni de celui
  de dans trois ans. C'est ce qui rend le critère A24 trivial et A27 solide.
- **`donnees`** est la matière brute — participants, blocs, circuits, réussites.
  Elle ne sert à rien tout de suite. Elle sert le jour où on veut recalculer un
  classement avec la règle des finales (spec 009 pressentie), extraire une
  fixture pour `verify_ranking.py`, ou simplement répondre à « combien de blocs
  a fait untel en 2026 ». Sans elle, l'archive serait une capture d'écran.

Le numéro de `format` est là pour qu'une archive écrite aujourd'hui puisse être
**reconnue et refusée proprement** demain, plutôt que de faire tomber la page de
résultats sur une clé manquante.

**Taille mesurée** (01/09, 196 grimpeurs / 50 blocs / 3 031 réussites) :
**701 Ko**, dont 576 Ko de `donnees` et 124 Ko de `classement`, produite en
44 ms. C'est ce chiffre-là qui rend `with_entities` obligatoire dans `lister()`
et non facultatif.

## 3. Le module `climbcontest/cycle.py` — nouveau

Toute la logique du cycle de vie, testable sans Flask ni Google. Il ne fait
aucun appel réseau : c'est ce qui le distingue de `sheets/parametrage.py`.

```python
regler_statut(comp, statut: str) -> None
effacer_donnees(comp, confirmation: str, forcer: bool = False) -> dict
archiver(comp, par: str) -> Archive
lister() -> list[dict]             # sans jamais lire `contenu`
classement_archive(archive) -> dict
supprimer(archive) -> None
```

### `regler_statut(comp, statut)`

Quinze lignes : la valeur est dans `(PREPARATION, EN_COURS, TERMINEE)` ou c'est
une `ErreurMetier`. Rien d'autre — le statut ne déclenche aucun effet de bord,
c'est ce qui le rend sûr à corriger à tout moment (§ 2.1 de la spec).

La garde et son forçage vivent **dans `cycle.py`**, pas dans les routes :

```python
def _garde_en_cours(comp, forcer: bool) -> None:
    if comp.statut == EN_COURS and not forcer:
        raise ErreurMetier("La competition est marquee EN COURS. …", code=409)
```

`effacer_donnees()` l'appelle, et `parametrage.relier(mode=reinitialiser)`
l'appelle aussi — c'est ce qui donne le critère A36 sans dupliquer la règle. La
garde écrite en double dans deux routes finirait par diverger : elle a déjà
existé une fois, à la spec 015, et c'est la seule copie qu'on garde.

⚠️ **L'ordre est confirmation d'abord, forçage ensuite.** `effacer_donnees()`
vérifie le mot `EFFACER` avant de regarder `forcer` : une case cochée sans le
mot frappé donne 400, jamais 200 (A35).

### `effacer_donnees(comp)`

Reprend **exactement** `parametrage._vider_la_base()`, qui fait déjà le bon
travail dans le bon ordre (réaffectations d'abord — elles portent une clé
étrangère vers les participants —, puis suppression par objet pour que les
cascades ORM emportent réussites et liens bloc↔circuit). La fonction **déménage**
de `parametrage.py` vers `cycle.py` ; `parametrage.relier()` l'importe de là.
Une seule implémentation, deux appelants.

S'y ajoutent les deux gestes que `relier()` faisait de son côté et qui font
partie de l'effacement, pas du changement de classeur :

```python
comp.catalogue_version = prochaine_version_catalogue()   # A17
classement_service.invalider(comp.id)                    # A18
```

Sur le second, soyons exact : le cache de `classement_service` expire de
lui-même au bout de `FRAICHEUR_S = 5.0` secondes. Sans invalidation explicite,
l'effacement laisse donc la page de résultats afficher l'ancien classement
**pendant cinq secondes au plus** — c'est cosmétique, pas une panne. On appelle
quand même `invalider()`, pour deux raisons : le retour visuel immédiat après
avoir cliqué « Effacer » (cinq secondes à regarder un classement qu'on vient de
supprimer, c'est cinq secondes à se demander si le bouton a marché), et parce
que le critère A18 devient sinon un test qui dépend de l'horloge.

À noter au passage, sans l'élargir en chantier : `invalider()` existe depuis la
spec 004 et **n'est appelée nulle part**. Sa docstring annonce pourtant
« import du classeur, saisie manuelle, réaffectation de dossard ». `cycle.py`
en sera le premier appelant réel. Brancher les trois autres est un `fix(ranking)`
d'une ligne chacun, hors périmètre de cette spec — signalé ici pour qu'il ne se
reperde pas.

### `archiver(comp, par)`

```
1. classements(comp, forcer=True)   ← on fige un calcul FRAIS, jamais le cache
2. la charge utile de /api/public/classement, construite par la même fonction
3. les données brutes, trois requêtes
4. une ligne `archive` + comp.statut = TERMINEE, dans UNE transaction
```

Le `forcer=True` du premier point n'est pas cosmétique : archiver un cache
vieux de cinq minutes fige un classement qui ignore les dernières réussites,
et une archive fausse ne se répare pas.

**L'enrichissement des lignes (nom, club, catégorie) est aujourd'hui écrit dans
`routes/public.py`**, dans le corps de la vue. Il en sort pour devenir
`classement_service.charge_publique(comp)`, appelée par les deux : la route
publique et l'archivage. Sans ça, les deux formats divergeraient au premier
changement — et la page de résultats, qui consomme les deux, casserait sur
l'archive uniquement.

## 4. Le test d'écriture — `sheets/client.py` et `sheets/parametrage.py`

Une méthode de plus sur `ClasseurGoogle` :

```python
def essai_ecriture(self, onglet: str = ONGLET_IMPORT) -> dict:
    """Écrit puis efface la dernière cellule de la grille. Rapport, jamais
    d'exception : c'est un diagnostic, pas une opération."""
```

Elle rend un dictionnaire et **ne lève rien** — un test dont l'échec est la
réponse attendue ne doit pas s'exprimer par une exception :

```python
{"tentee": True, "cellule": "DP1000", "ecriture": False, "restauree": None,
 "message": "…ce que Google a dit…"}
```

| Cas | `tentee` | `ecriture` | `restauree` |
| --- | --- | --- | --- |
| Tout va bien | `True` | `True` | `True` |
| Cellule témoin non vide (A3) | `False` | `None` | `None` |
| Google refuse l'écriture (A2) | `True` | `False` | `None` |
| Relecture différente de ce qu'on a écrit | `True` | `False` | tentée quand même |
| L'effacement échoue (A4) | `True` | `True` | `False` |

Les plages protégées viennent de `metadonnees()`, en ajoutant
`protectedRanges` au `fields` de l'appel `spreadsheets.get` déjà fait — **zéro
requête de plus**.

`parametrage.tester(identifiant, comp, ecriture=False)` gagne un drapeau. Le
rapport gagne une clé `ecriture` et des avertissements. La console appelle avec
`ecriture: true` quand on presse « Tester l'accès en écriture » — un bouton
distinct de « Tester l'accès », parce que l'un écrit et l'autre pas, et que ça
doit se voir avant de cliquer.

## 5. L'import — `sheets/importer.py`

La lecture se sépare de l'écriture, pour que le remplacement puisse lire avant
d'effacer (A10) :

```python
@dataclass
class Lecture:
    plan: list[list]      # Plan!D28:Y
    listes: list[list]    # Listes!F2:K

def lire_tout(classeur) -> Lecture          # RÉSEAU, et rien d'autre
def importer(comp, classeur=None, lecture=None) -> Rapport
```

`importer()` sans `lecture` se comporte comme aujourd'hui (il lit lui-même) :
les tests existants de `test_import.py` passent inchangés, ce qui est le critère
A7. `importer_blocs` et `importer_participants` prennent les lignes en paramètre
au lieu d'appeler `classeur.lire()` — même code, une indirection en moins.

La route orchestre :

```python
lecture = lire_tout(cl)                     # si ça casse ici : 502, base intacte
if mode == REMPLACER:
    exiger_confirmation(corps)              # 400 avant tout appel réseau
    effets = cycle.effacer_donnees(comp)
rapport = importer(comp, lecture=lecture)
```

⚠️ **La confirmation se vérifie avant l'appel réseau**, pas entre la lecture et
l'effacement : refuser après avoir fait travailler Google pour rien serait
gratuit, et surtout ça ferait dépendre un 400 d'un aller-retour qui peut
échouer.

## 6. Les routes — `routes/admin.py`

| Route | Rôle | Ce qu'elle fait |
| --- | --- | --- |
| `POST /admin/classeur/test` | `ADMIN` | + champ `ecriture: true` dans le corps |
| `POST /admin/import/sheet` | voir ci-dessous | + champs `mode`, `confirmation` |
| `POST /admin/competition/statut` | `ORGANISATEUR` | `{statut: "preparation\|en_cours\|terminee"}` |
| `POST /admin/donnees/effacer` | `ADMIN` | `{confirmation: "EFFACER", forcer: false}` |
| `POST /admin/archives` | `ADMIN` | archive la compétition active |
| `GET /admin/archives` | `ORGANISATEUR` | la liste |
| `GET /admin/archives/<id>/classement` | `ORGANISATEUR` | le classement figé |
| `GET /admin/archives/<id>/fichier` | `ORGANISATEUR` | téléchargement |
| `DELETE /admin/archives/<id>` | `ADMIN` | + confirmation |

**`POST /admin/import/sheet` porte deux rôles selon le mode**, et c'est le seul
endroit du produit où c'est le cas. `ORGANISATEUR` pour la mise à jour (elle ne
détruit rien, c'est le geste du samedi matin) ; `ADMIN` pour le remplacement (il
efface). Le décorateur `@exige_role(ORGANISATEUR)` reste sur la route, et le
mode remplacement vérifie `ADMIN` dans le corps de la vue — ce qui donne un 403
explicite plutôt qu'une route dupliquée.

`GET /console/archives/<id>/resultats` va dans `routes/pages.py`, derrière la
session, comme `/console`.

## 7. La page de résultats — `templates/resultats.html`

Un seul `fetch` dans tout le fichier (ligne 693). Il devient paramétrable :

```html
<body data-source="{{ source }}" data-archive="{{ archive_nom or '' }}">
```

```js
var SOURCE  = document.body.dataset.source || "/api/public/classement";
var ARCHIVE = document.body.dataset.archive || null;
```

- `/` → `source = "/api/public/classement"`, comportement inchangé, y compris
  `?mur`, `?sombre`, `?rotation=30` ;
- `/console/archives/<id>/resultats` → `source = "/admin/archives/<id>/classement"`.

En mode archive : le minuteur de rafraîchissement n'est **pas armé** (A26), et
le bandeau affiche « Archive du <date> » là où il affiche l'âge du calcul. Le
reste — podium, colonnes, scratchs, rotation, favoris — ne change pas d'une
ligne. Le mode mur reste atteignable : revoir une édition passée sur le
vidéoprojecteur pendant que la salle se remplit est exactement l'usage.

## 8. La console — `templates/admin.html`

Deux entrées de tiroir, après « Classeur » :

```
Participants · Réussites · Téléphones · Classeur · Compétition · Archives · Réglages
```

| Vue | Cartes |
| --- | --- |
| **Compétition** | *État de l'édition* (trois boutons) · *Importer le classeur* (deux modes en boutons radio) · *Archiver l'édition* · *Effacer les données* (bordure rouge) |
| **Archives** | Un tableau, la plus récente en tête, trois boutons par ligne |

La fenêtre de confirmation est un `<dialog>` natif — pas de bibliothèque, pas de
faux modal en `position: fixed` : `showModal()` donne le focus piégé, la touche
Échap et le voile, gratuitement et correctement. Elle affiche les compteurs
réels lus à l'ouverture (jamais ceux du dernier chargement de page), la ligne
« cette édition n'a jamais été archivée » le cas échéant, la case « Effacer quand
même » quand la compétition est `en_cours`, et un bouton qui ne s'arme qu'une
fois `EFFACER` frappé — **et la case cochée s'il y a lieu**.

Le même `<dialog>` sert au remplacement complet et à la suppression d'une
archive, avec un texte différent : trois destructions, une seule mécanique de
confirmation à relire.

Comme pour « Classeur », les entrées de tiroir réservées aux administrateurs
sont masquées côté client (`etat.moi.roles`) **et** refusées côté serveur. Le
masquage est du confort ; c'est le 403 qui protège.

## 9. Fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/models.py` | + `Archive` |
| `climbcontest/cycle.py` | **nouveau** — statut, garde, effacer, archiver, lister, supprimer |
| `climbcontest/contest.py` | l'import inutilisé de `EN_COURS` s'en va |
| `climbcontest/classement_service.py` | + `charge_publique(comp)`, extraite de la route |
| `climbcontest/sheets/client.py` | + `essai_ecriture()`, + `protectedRanges` dans `fields` |
| `climbcontest/sheets/parametrage.py` | `tester(…, ecriture)` ; `_vider_la_base` déménage |
| `climbcontest/sheets/importer.py` | + `Lecture`, `lire_tout()`, `importer(lecture=…)` |
| `climbcontest/routes/admin.py` | + 7 routes, + les modes d’import, + le forçage |
| `climbcontest/routes/public.py` | la vue appelle `charge_publique` |
| `climbcontest/routes/pages.py` | + la page de rejeu, + `source` sur `/` |
| `climbcontest/templates/admin.html` | + 2 vues, + le `<dialog>` |
| `climbcontest/templates/resultats.html` | source paramétrable, mode archive |
| `tests/test_cycle_competition.py` | **nouveau** — A8→A23, A27→A38 |
| `tests/test_client_classeur.py` | + A1→A5 |
| `tests/test_page_resultats.py` | + A24, A26 |
| `docs/technical/classeur-google.md`, `docs/specs-index.md`, `CHANGELOG.md` | documentation |

**Aucune migration.** `db.create_all()` crée `archive` au premier démarrage,
sur une base neuve comme sur celle de production.
