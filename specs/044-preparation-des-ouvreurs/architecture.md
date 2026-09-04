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
| les options d'édition | `cycle.lire_options` / `cycle.ecrire_options` |
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
  mode `console`, il devient un simple ordinal de création, `max + 1`, **jamais
  réattribué**. La renumérotation ne le touche pas : ce n'est pas le nom de la
  voie, et le faire bouger casserait le lien avec le classeur pour les éditions
  qui en ont un.

### 2.3 L'option d'édition

```python
# competition.options, via cycle.lire_options / ecrire_options
{"source_blocs": "classeur" | "console"}   # defaut : "classeur"
```

`ecrire_options` fusionne et n'écrase jamais les clés qu'il ne touche pas — la
cascade et l'affichage cohabitent dans le même document JSON.

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
| `GET /admin/ouverture` | `OUVREUR, ORGANISATEUR` | l'état complet : compétition, source, plan, circuits, voies par zone, compteurs |
| `POST /admin/ouverture/voies` | `OUVREUR, ORGANISATEUR` | crée une voie dans une zone |
| `POST /admin/ouverture/voies/<id>` | `OUVREUR, ORGANISATEUR` | couleur, prises, catégories |
| `DELETE /admin/ouverture/voies/<id>` | `OUVREUR, ORGANISATEUR` | supprime |
| `POST /admin/ouverture/renumeroter` | `OUVREUR, ORGANISATEUR` | la passe globale ; `?apercu=1` rend les `(avant, après)` **sans écrire** |
| `POST /admin/ouverture/circuits` | `OUVREUR, ORGANISATEUR` | crée une catégorie |
| `DELETE /admin/ouverture/circuits/<id>` | `OUVREUR, ORGANISATEUR` | supprime si elle ne porte aucune voie |
| `POST /admin/competition/source-blocs` | `ORGANISATEUR` | l'interrupteur de F1 |

⚠️ **`exige_role(OUVREUR, ORGANISATEUR)` et non `exige_role(OUVREUR)`.** Le
décorateur accorde l'accès à `admin` **ou** à l'un des rôles nommés : un
organisateur non nommé serait refusé sur l'écran qu'il contrôle.

⚠️ **`?apercu=1` sur la renumérotation n'est pas un confort** : c'est ce qui
alimente l'écran de confirmation. Le calculer côté client obligerait à recopier
la règle de tri dans le navigateur — deux implémentations de la même règle
divergent, c'est la leçon de `cascade.py` et de son test miroir.

### 4.1 Ce qui change dans l'import

`sheets/importer.importer()` reçoit un garde en tête d'`importer_blocs` :

```python
if lire_options(comp).get("source_blocs") == "console":
    rapport.avertissements.append(
        "Blocs non importes : cette edition prend ses voies dans la console.")
    return
```

Les participants continuent d'être importés. ⚠️ Le message part dans
`avertissements` et pas dans `ignores` : rien n'a été perdu, c'est un choix qui
s'applique.

### 4.2 Ce qui change dans le miroir

Le filtre partagé `mirror._envoyables()` gagne **une clause**, et rien d'autre :

```python
.filter(or_(Bloc.source.is_(None), Bloc.source != SOURCE_CONSOLE))
```

⚠️ `Bloc.source.is_(None)` **fait partie de la clause**. Les blocs d'avant ce lot
valent `NULL` — ils viennent tous du classeur, et un `!=` seul les exclurait
tous : en SQL, `NULL != 'console'` ne vaut pas vrai. Le miroir s'arrêterait net
sur toutes les éditions existantes, et le compteur d'attente resterait figé.

⚠️ **Une seule et même requête pour l'envoi et pour le compteur.** C'est la
leçon du 03/09 : `/health` comptait 714 réussites en attente que le miroir ne
pouvait pas envoyer. `_envoyables` reste le point unique, et
`contest.reussites_en_attente` continue de l'appeler.

Ce qui ne partira jamais se compte **à part**, par une fonction nommée :

```python
def non_reportables(competition_id: int) -> int:
    """Les reussites qui portent une voie creee dans la console.

    Elles n'ont pas d'adresse dans l'onglet `Import` : leur `numero` est un
    ordinal interne, pas un numero de ligne. Les compter avec les autres ferait
    afficher une attente qui ne se resorberait jamais ; ne pas les compter du
    tout les rendrait invisibles. On les compte, et on les nomme.
    """
```

Ce chiffre s'affiche à côté de l'interrupteur, dans la vue Général.

⚠️ **`modifier()` ne touche jamais `source`.** Une voie importée que l'on relit
garde `source = classeur` et son `numero` : elle reste reportable. Seul
`creer()` pose `source = console`. C'est la ligne qui décide si le miroir
survit à une édition simplement relue par un ouvreur.

⚠️ **`renumeroter()` ne touche pas `numero` non plus** (architecture §2.2). Le
tag d'un bloc importé peut donc différer de ce que dit l'onglet `Plan` du
classeur : sans conséquence, puisque `Import` est adressé par **ligne**, jamais
par tag.

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

### 5.3 Le repliement du plan

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
| `climbcontest/routes/admin.py` | 8 routes, une section |
| `climbcontest/sheets/importer.py` | le garde de 4.1 |
| `climbcontest/sheets/mirror.py` | la sortie de 4.2 |
| `climbcontest/templates/admin.html` | la vue `vueOuvreurs` et son entrée de tiroir |
| `climbcontest/static/console/ouverture.js` | **nouveau** — l'écran, en module, testable |
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
