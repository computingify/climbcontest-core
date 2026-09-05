# Spec 044 — Architecture

## 1. Le principe

**Un module pur, une couche de routes, un écran.** Le calcul — quelles voies,
quel rang, quelle renumérotation, quel refus — vit dans `climbcontest/ouverture.py`,
**sans Flask**, comme `circuits.py`, `cycle.py`, `fiches.py` et `suivi.py`. Il ne
parle qu'à la base : tout se teste sans client HTTP.

Rien n'est réinventé de ce qui existe :

| Ce dont l'écran a besoin | Ce qui le fournit déjà |
| --- | --- |
| la géométrie du mur | `suivi.plan_public()` — le même document que la page de résultats |
| le dessin SVG et les pastilles | `static/resultats/plan.js` — `decrire`, `monter`, `decorer` |
| les six couleurs et leur ordre | `classement.COULEURS` |
| le régime de l'écran | le réglage global de la [spec 045](../045-mode-sans-classeur/) |
| prévenir les téléphones | `contest.incrementer_tous_les_catalogues()` |
| le contrôle d'accès | `auth_session.exige_role` |

⚠️ **`suivi.FORMAT_PLAN` n'est pas incrémenté.** Ce lot ne change pas la *forme*
de `plan_public()` : il la **consomme**. Le numéro de format est le rendez-vous
entre le plan et les pages qui le dessinent ; le bouger sans raison ferait
refuser de dessiner à une page qui sait très bien le faire.

---

## 2. Le modèle

### 2.1 Deux colonnes sur `bloc`

```python
class Bloc(db.Model):
    ...
    # Le rang de la voie DANS SA COULEUR : « V7 » a numero_couleur = 7.
    # NULL tant qu'aucune couleur n'est choisie -- une voie sans couleur n'a
    # pas encore de place dans la salle.
    numero_couleur = Column(Integer)

    # D'ou vient ce bloc. Meme role que `Participant.source` : savoir ce qu'un
    # import a le droit d'ecraser.
    source = Column(String(20), nullable=False, default=SOURCE_CLASSEUR)
```

Les deux s'ajoutent par `schema.COLONNES_AJOUTEES["bloc"]` — le mécanisme
existe déjà pour `couleur_prises`, il regarde l'état réel de la table et
n'échoue ni sur une base neuve ni sur une base migrée.

```python
COLONNES_AJOUTEES["bloc"] = {
    "couleur_prises": "TEXT",
    "numero_couleur": "INTEGER",
    "source": "TEXT",
}
```

⚠️ `source` est déclarée `NOT NULL DEFAULT` côté modèle mais ajoutée en `TEXT`
nullable sur une table existante : `ALTER TABLE ADD COLUMN ... NOT NULL` sans
défaut est refusé par SQLite. Les lignes anciennes valent donc `NULL`, et le
code lit `bloc.source or SOURCE_CLASSEUR` — c'est la vérité, ces blocs viennent
tous du classeur.

### 2.2 Ce qui NE change pas

- **`tag` reste la clé métier et le contenu du QR.** Il est *calculé* à
  l'écriture (`zone + initiale + numero_couleur`) mais *stocké*, parce que c'est
  lui que le scan résout (`contest`), lui que l'étiquette imprime (spec 024) et
  lui que la contrainte `uq_bloc_tag` protège.
- **`numero` (colonne Y du classeur) reste un entier unique par édition.** En
  mode sans classeur, il devient un simple ordinal de création, `max + 1`, **jamais
  réattribué**. La renumérotation ne le touche pas : ce n'est pas le nom de la
  voie, et le faire bouger casserait le lien avec le classeur pour les éditions
  qui en ont un.

### 2.3 Le régime de l'écran

Aucune option propre à ce lot. L'écran lit le réglage **global** de la
spec 045 :

```python
from .reglages import mode_sans_classeur     # spec 045
ecriture_permise = mode_sans_classeur()
```

⚠️ **`Bloc.source` reste**, bien que le miroir n'en ait plus besoin. Elle sert
à deux choses qui, elles, existent : dire **d'où vient une voie** dans l'écran —
comme la spec 008 montre `Participant.source` en pastilles G / H / M — et
alimenter le **contrôle avant bascule** de la 045, qui doit pouvoir affirmer
« les 47 voies du classeur sont bien en base ».

### 2.4 Le rôle

```python
# comptes.py
OUVREUR = "ouvreur"
ROLES_CONNUS = frozenset({ADMIN, ORGANISATEUR, OUVREUR})
```

⚠️ `_verifier_qu_il_restera_un_admin` n'est pas touché : la protection porte sur
`admin`, et un ouvreur ne peut pas devenir le dernier administrateur par
accident.

---

## 3. `climbcontest/ouverture.py`

```python
INITIALES = {"Jaune": "J", "Vert": "V", "Bleu": "B",
             "Mauve": "M", "Rouge": "R", "Noir": "N"}
```

⚠️ **Construit à la main et vérifié par un test contre `classement.COULEURS`** :
les six initiales doivent être deux à deux distinctes, et couvrir exactement les
six couleurs. Une septième couleur ajoutée un jour sans initiale ferait des tags
en collision, et `uq_bloc_tag` transformerait une saisie ordinaire en erreur 500.

| Fonction | Ce qu'elle fait |
| --- | --- |
| `inventaire(comp)` | zones → voies, compteurs, répartition par couleur, zones hors plan. **Trois requêtes**, quel que soit le nombre de voies |
| `creer(comp, zone)` | une voie nue dans cette zone ; `numero = max + 1`, `source = console` |
| `modifier(comp, bloc, couleur, prises, circuits)` | applique, réattribue le rang si la couleur change, recalcule le `tag` |
| `supprimer(comp, bloc)` | refuse si la voie porte une réussite |
| `renumeroter(comp)` | la passe globale de F6 ; rend la liste des `(avant, après)` |
| `verifier_modifiable(comp, bloc=None)` | le garde-fou unique de F7, appelé par les quatre précédentes |

### 3.1 L'attribution d'un rang

```
rang = 1 + max(numero_couleur des voies de cette couleur dans l'edition)
```

Pas `count + 1` : après une suppression, `count + 1` rendrait un rang **déjà
pris** et la contrainte d'unicité du tag ferait échouer la saisie suivante. Le
`max` laisse des trous, et c'est précisément ce que « Renuméroter » sert à
refermer.

### 3.2 La renumérotation

```python
for couleur in COULEURS:                       # l'ordre de classement.COULEURS
    voies = [b for b in blocs if b.couleur == couleur]
    voies.sort(key=lambda b: (b.zone or "", b.numero_couleur or 0, b.id))
    for rang, b in enumerate(voies, start=1):
        b.numero_couleur = rang
        b.tag = f"{b.zone}{INITIALES[couleur]}{rang}"
```

Trois choses à ne pas rater :

1. **La clé de tri porte `id` en dernier.** Deux voies de même zone et même rang
   (cas possible sur des données importées) doivent sortir dans un ordre
   déterminé, sinon deux exécutions donnent deux résultats.
2. **Les tags s'écrivent en deux temps** — d'abord une valeur temporaire, puis
   la définitive — sinon `uq_bloc_tag` claque en cours de route sur une
   permutation (`JV3` prend la place de `JV2` qui n'est pas encore libérée).
   C'est le piège classique de toute renumérotation sous contrainte d'unicité.
3. **Une voie sans couleur n'est pas touchée.** Elle n'a pas de rang à recevoir.

---

## 4. Les routes

Toutes dans `climbcontest/routes/admin.py`, sous un commentaire de section
`# --- L'ouverture (spec 044) ---`, **placé après la section « Le plan de la
salle »** — c'est là que le lecteur ira les chercher.

| Route | Rôle exigé | Ce qu'elle fait |
| --- | --- | --- |
| `GET /admin/ouverture` | `OUVREUR, ORGANISATEUR` | l'état complet : compétition, régime, plan, circuits, voies par zone, compteurs |
| `POST /admin/ouverture/voies` | `OUVREUR, ORGANISATEUR` | crée une voie dans une zone |
| `POST /admin/ouverture/voies/<id>` | `OUVREUR, ORGANISATEUR` | couleur, prises, catégories |
| `DELETE /admin/ouverture/voies/<id>` | `OUVREUR, ORGANISATEUR` | supprime |
| `POST /admin/ouverture/renumeroter` | `OUVREUR, ORGANISATEUR` | la passe globale ; `?apercu=1` rend les `(avant, après)` **sans écrire** |
| `POST /admin/ouverture/circuits` | `OUVREUR, ORGANISATEUR` | crée une catégorie |
| `DELETE /admin/ouverture/circuits/<id>` | `OUVREUR, ORGANISATEUR` | supprime si elle ne porte aucune voie |

⚠️ **`exige_role(OUVREUR, ORGANISATEUR)` et non `exige_role(OUVREUR)`.** Le
décorateur accorde l'accès à `admin` **ou** à l'un des rôles nommés : un
organisateur non nommé serait refusé sur l'écran qu'il contrôle.

⚠️ **`?apercu=1` sur la renumérotation n'est pas un confort** : c'est ce qui
alimente l'écran de confirmation. Le calculer côté client obligerait à recopier
la règle de tri dans le navigateur — deux implémentations de la même règle
divergent, c'est la leçon de `cascade.py` et de son test miroir.

### 4.1 Ce qui change dans l'import

**Rien.** L'import du classeur n'est pas modifié par ce lot : c'est la spec 045
qui l'éteint, en bloc et pour toutes ses plages, quand le mode est allumé. Un
garde partiel posé ici ferait doublon avec celui-là — et deux gardes qui disent
la même chose finissent par ne plus la dire pareil.

### 4.2 Ce qui change dans le miroir

**Rien non plus**, et pour la même raison. Voir spec 044 §F9 : le cas des
réussites sans adresse dans l'onglet `Import` ne peut pas se produire, puisque
les deux régimes de l'écran s'excluent.

---

## 5. L'écran

### 5.1 Une vue de plus dans `admin.html`

⚠️ **Trois précautions contre une collision silencieuse avec les branches en
cours** (la 008 « import HelloAsso » ajoute trois vues au même fichier ; la 043
ajoute une colonne à Participants). Git fusionne sans conflit deux vues
ajoutées à des endroits différents, et le défaut n'apparaît qu'à l'écran :

1. **Tout est préfixé `ouvreurs`** — `vueOuvreurs`, `navOuvreurs`,
   `ouvreursDessiner`, `ouvreursEtat`, `#ouvreursPlan`, `#ouvreursTiroir`.
2. **La `<section class="vue">` s'insère DANS le bloc des vues**, jamais entre
   deux : une carte glissée hors de toute vue s'affiche sur *tous* les écrans,
   et aucun test ne le voit.
3. **Fusion à blanc avant le merge du second** — `git merge --no-commit --no-ff`,
   les deux suites lancées ensemble, **et la console ouverte dans un
   navigateur**. C'est la seule façon d'attraper ce type de collision.

### 5.2 Le plan, réutilisé et non recopié

Le module `static/resultats/plan.js` est déjà pur et déjà testé : il décrit un
SVG à partir d'un document `plan_public()`, le monte, et le décore zone par
zone. L'écran d'ouverture l'importe **tel quel**.

Deux différences, et elles sont dans la décoration, pas dans le dessin :

| | Fiche du grimpeur (036) | Ouverture (044) |
| --- | --- | --- |
| ce que compte la pastille | `{faits, total}` = réussis / blocs du circuit | `{faits, total}` = **complètes / déclarées** |
| l'état de la zone | `z-reste` / `z-finie` | `z-saisie` / cadre vert si tout est complet |

⚠️ `decorer` prend déjà `comptes` en paramètre : **rien à modifier dans
`plan.js`**. Ce sont les classes d'état qui diffèrent, et elles sont posées par
l'appelant.

### 5.3 Le geste de confirmation : UN composant, deux surfaces

`climbcontest/static/console/confirmer.js` — **nouveau**, et partagé avec la
spec 045.

```js
export function confirmerParGeste(hote, {libelle, libelleGlisse, surAbout});
```

| Média | Rendu | Cotes |
| --- | --- | --- |
| `(hover: hover) and (pointer: fine)` | le bouton à **maintenir** | `MAINTIEN_MS = 2000`, anneau `--anneau: 37.7`, jauge et décompte |
| sinon | le **glissement** | piste 260 × 58 plafonnée et **centrée**, bouton 50, marge 4, course 202 |

⚠️ **Aucune des deux moitiés n'est inventée.** Le maintien est celui
d'`admin.html` (spec 032) ; le glissement est celui de Sowel
(`SlideToConfirm.tsx`, spec 146), **cotes comprises**. Les 260 px plafonnés et
centrés y sont justifiés : pleine largeur sur un téléphone de 393 px, le geste
part du coin inférieur gauche, le point le plus loin du pouce.

⚠️ **Trois détails d'implémentation qui ne sont pas cosmétiques**, chacun payé
une fois dans les deux sources :

1. `touch-action: none` sur le bouton à maintenir. Sans lui, maintenir le doigt
   fait défiler la page, `pointerleave` annule, et le bouton devient intenable
   sur téléphone.
2. `e.repeat` gardé sur `keydown`. Entrée maintenue se répète en rafale : sans
   le garde, le minuteur repart à zéro cinquante fois et n'aboutit jamais.
3. `setPointerCapture` sur le curseur de glissement, et
   `drag.max > 0` avant de conclure : sur une piste dégénérée, le premier
   mouvement validerait tout seul.

### 5.4 Le repliement du plan

Quand le tiroir s'ouvre sur téléphone, la zone de plan passe de `flex: 1` à une
hauteur fixe (32 %, 18 % pour la fiche d'une voie). Le SVG se remet à l'échelle
tout seul — `preserveAspectRatio` par défaut — et la zone visée garde son
anneau. Sur grand écran (≥ 1080 px), le tiroir s'ancre à droite, le plan reste
entier, et **aucun voile ne l'éteint** : c'est la seule vue d'ensemble.

### 5.4 Le masquage par rôle

Le même mécanisme que `#navClasseur` et `#navGeneral`, à l'envers : pour un
compte qui porte **uniquement** `ouvreur`, toutes les entrées du tiroir sont
masquées sauf `navOuvreurs`, et la vue initiale est `ouvreurs`.

⚠️ C'est un confort d'affichage. La barrière est `exige_role`, côté serveur, et
c'est elle que les tests vérifient.

---

## 6. Les fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/ouverture.py` | **nouveau** — tout le calcul |
| `climbcontest/models.py` | 2 colonnes sur `Bloc` |
| `climbcontest/schema.py` | `COLONNES_AJOUTEES["bloc"]` |
| `climbcontest/comptes.py` | le rôle `OUVREUR` |
| `climbcontest/routes/admin.py` | 7 routes, une section |
| `climbcontest/templates/admin.html` | la vue `vueOuvreurs` et son entrée de tiroir |
| `climbcontest/static/console/ouverture.js` | **nouveau** — l'écran, en module, testable |
| `climbcontest/static/console/confirmer.js` | **nouveau** — le geste, partagé avec la 045 |
| `tests/test_ouverture.py` | **nouveau** |
| `tests/test_admin_ouverture.py` | **nouveau** — les routes et les rôles |
| `docs/specs-index.md`, `CHANGELOG.md` | l'index et la section `[Non publié]` |

⚠️ `static/console/ouverture.js` est un **fichier neuf**, volontairement : mettre
mille lignes de plus dans `admin.html` (4 849 aujourd'hui) c'est garantir le
conflit avec les deux branches en cours. Un module importé se relit, se teste, et
ne se fusionne pas à l'aveugle.

---

## 7. Le budget de requêtes

`inventaire(comp)` : **trois requêtes**, quel que soit le nombre de voies —
les blocs, leurs liens de circuit, les circuits. C'est le même budget que
`circuits.inventaire()` et `fiches._blocs_par_circuit()`, et il est tenu par un
test, comme celui du plan sur la planche de dossards.
