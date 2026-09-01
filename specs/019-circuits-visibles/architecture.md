# Spec 019 — Architecture

## 1. Modèle de données

Deux colonnes ajoutées, aucune table nouvelle. Le lien bloc ↔ circuit existe
déjà (`BlocCircuit`), et la dérivation catégorie → circuit aussi
(`Participant.circuit`).

```python
class Bloc:
    couleur        = Column(String(20))   # colonne F — difficulté (existant)
    couleur_prises = Column(String(20))   # colonne H — prises    (nouveau)

class Success:
    hors_circuit_force = Column(Boolean)  # nouveau, nullable
```

Les deux passent par `schema.COLONNES_AJOUTEES` — le mécanisme idempotent qui
lit `PRAGMA table_info` plutôt que de tenir un compteur. **Pas de fichier
`.sql`** : sur une base neuve, `create_all` a déjà créé la colonne et l'`ALTER`
échouerait sur « duplicate column ».

```python
COLONNES_AJOUTEES = {
    "success": {..., "hors_circuit_force": "BOOLEAN"},
    "bloc":    {"couleur_prises": "TEXT"},
}
```

`hors_circuit_force` est **nullable et sans défaut** : `NULL` veut dire « on ne
sait pas » — une réussite d'avant cette spec, une saisie manuelle, un import.
`False` veut dire « le téléphone a vérifié et c'était bon ». Les deux ne sont
pas la même chose et ne doivent pas se confondre dans la console.

## 2. Contrats

### `GET /admin/circuits` — nouveau, rôle `ORGANISATEUR`

```json
{
  "success": true,
  "circuits": [{"nom": "U13", "blocs": 36, "categories": ["U13 F", "U13 H"],
                "participants": 40}],
  "blocs": [{"tag": "ZJ6", "zone": "Z", "numero": 1,
             "couleur": "Jaune", "couleur_prises": "Bleu",
             "circuits": ["U11", "U13"],
             "categories": ["U11 F", "U11 H", "U13 F", "U13 H"]}],
  "anomalies": {
    "blocs_sans_circuit": ["DV21"],
    "circuits_sans_bloc": ["U17"],
    "categories_sans_circuit": ["U19 F"]
  }
}
```

Trois requêtes, pas plus — le même budget que `classement_service.charger()` :
les blocs, les liens `bloc_circuit` joints aux circuits, et les catégories
distinctes des participants.

`categories` d'un bloc = l'union des catégories de ses circuits. **Dérivées des
participants réels**, jamais inventées : on n'affiche pas « U13 F » si personne
ne l'est.

### `GET /api/v2/catalog` — **inchangé**

Il envoie déjà `participants[].categorie` et `blocs[].circuits`. Aucune version
d'API à faire bouger, aucun contrat à casser.

### `POST /api/v3/successes` — un champ facultatif de plus

```json
{"items": [{"ref": "a1b2c3", "bib": "42", "bloc": "ZJ6",
            "at": "…", "hors_circuit": true}]}
```

Facultatif, comme `appareil` : un téléphone qui ne l'envoie pas se comporte
exactement comme avant. Les routes `v2` ne bougent pas — l'application Android
gelée parle par elles.

### `GET /admin/reussites-tracees` — deux champs de plus

`hors_circuit_force` (ce que le juge a vu) et `hors_circuit` (ce qui est vrai
maintenant, calculé). Les deux, parce qu'ils divergent quand le classeur est
corrigé — et que c'est précisément ce qu'on veut voir.

## 3. Le catalogue local de la PWA

`static/juge/catalogue.js`, `FORMAT` **2 → 3**.

```js
// Avant : dossard → "Dupont Lea"        tag → "ZJ6"
// Après : dossard → {n: "Dupont Lea", c: "U13"}
//         tag     → {t: "ZJ6", k: "Jaune", c: ["U11","U13"]}
```

On garde le **circuit** (« U13 »), jamais la catégorie complète (« U13 F ») : la
remarque du fichier sur les données de mineurs entreposées sur vingt-cinq
téléphones reste valable, et le circuit suffit au test. Le genre n'apprend rien
à `estDansLeCircuit`.

```js
/** true · false · null (on ne sait pas — et alors on ne dit rien). */
estDansLeCircuit(dossard, tag)
```

`null` dès qu'un maillon manque : dossard inconnu, tag inconnu, participant sans
catégorie, bloc sans aucun circuit. Un avertissement qu'on ne sait pas justifier
apprend à ignorer les avertissements.

## 4. Le flux du garde-fou

```
scanner("bloc") ──► retenir() ──► redessiner()
                                     │
                        catalogue.estDansLeCircuit(etat.dossard, etat.bloc)
                                     │
          ┌──────────────┬───────────┴───────────┐
        true            null                   false
          │              │                       │
     rien à dire    rien à dire        carte en avertissement
                                       « Ce bloc est U15 · ce
                                         grimpeur est U13 »
                                       bouton « Envoyer quand même »
                                                 │
                                          envoyer() pose
                                          hors_circuit: true
                                          dans la file
```

Le test se refait dans `redessiner()` et **pas** une fois pour toutes dans
`retenir()` : le grimpeur peut être scanné **après** le bloc, et l'option
« garder le grimpeur entre deux blocs » enchaîne les blocs sans rescanner le
grimpeur. Un état dérivé recalculé à chaque rendu ne peut pas se désynchroniser.

`file.js` transporte le champ tel quel — la file est un tampon, elle ne juge
rien.

## 5. Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/models.py` | `Bloc.couleur_prises`, `Success.hors_circuit_force`, `to_dict()` |
| `climbcontest/schema.py` | deux entrées dans `COLONNES_AJOUTEES` |
| `climbcontest/sheets/importer.py` | `I_COULEUR_PRISES = 4`, lue et mise à jour |
| `climbcontest/cycle.py` | `_donnees_brutes()` archive les deux nouveaux champs |
| `climbcontest/contest.py` | `enregistrer_lot` accepte `hors_circuit` |
| `climbcontest/routes/admin.py` | `GET /admin/circuits` |
| `climbcontest/circuits.py` | **nouveau** — le calcul et les anomalies, sans Flask |
| `climbcontest/templates/admin.html` | vue « Circuits » et son entrée de navigation |
| `climbcontest/static/juge/catalogue.js` | `FORMAT` 3, `estDansLeCircuit` |
| `climbcontest/static/juge/juge.js` | avertissement, « Envoyer quand même » |
| `climbcontest/templates/juge.html` | le style de la carte en avertissement |

`circuits.py` est séparé de la route pour la même raison que `cycle.py` l'est de
`routes/admin.py` : le calcul des anomalies se teste sans client HTTP.
