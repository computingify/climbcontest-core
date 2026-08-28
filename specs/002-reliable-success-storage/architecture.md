# Architecture : 002 — La base devient la source de vérité

## 1. Le modèle

```
Competition ─┬─< Participant ─┬─< Success >─┬─ Bloc >─< BlocCircuit >── Circuit
             │                              │
             ├─< Circuit                    └── unique (participant_id, bloc_id)
             ├─< Bloc
             └─── options (validation par couleur, …)

Utilisateur >─< UtilisateurRole
```

### `Competition`

| Colonne | Type | Rôle |
| --- | --- | --- |
| `id` | PK | |
| `nom` | texte | « U11 U15 Mars 2026 » |
| `date` | date | une compétition dure **une journée** |
| `spreadsheet_id` | texte | le classeur associé — **plus jamais en dur dans le code** |
| `statut` | énum | `preparation` · `en_cours` · `terminee` |
| `active` | bool | une seule à la fois (Q3) |
| `catalogue_version` | entier | incrémenté à chaque changement de participant ou de bloc |
| `options` | JSON | `validation_couleur`, sa variante, etc. (spec 004) |

Le `spreadsheet_id` en base est ce qui supprime le geste le plus oublié du
[plan de repli](../../docs/plan-de-repli.md) : changer une constante et
redéployer.

### `Participant` — l'identité est stable, le dossard ne l'est pas

| Colonne | Contrainte | Pourquoi |
| --- | --- | --- |
| `id` | PK | **c'est l'identité**, elle ne change jamais |
| `competition_id` | FK | |
| `nom`, `prenom` | | séparés, comme dans le classeur |
| `club`, `categorie` | nullable | une ligne incomplète ne doit pas être rejetée (R5) |
| `dossard` | entier **nullable**, unique **par compétition** | un inscrit absent peut ne pas en avoir, ou le perdre |
| `present` | bool | savoir qui est venu |
| `source` | énum | `classeur` · `manuel` · `helloasso` (spec 008) |

Trois écarts avec le modèle actuel, tous nécessaires :

1. **`nom` n'est plus unique.** Deux homonymes dans deux clubs différents font
   aujourd'hui échouer tout l'import (R5). Le classeur, lui, prévoit le cas —
   colonnes `Erreur` et `A si doublon autorisé`.
2. **`dossard` est nullable.** Un inscrit qui ne vient pas peut céder son
   dossard : il reste en base, sans dossard.
3. **`dossard` est unique par compétition**, pas globalement — la base est
   multi-compétition.

### `Bloc` et `Circuit`

| Table | Contenu |
| --- | --- |
| `Circuit` | `U11`, `U13`, `U15` — une tranche d'âge, filles et garçons ensemble |
| `Bloc` | `tag` (le QR), `numero` (ligne dans l'onglet `Import`), `zone`, `couleur`, uniques par compétition |
| `BlocCircuit` | quels blocs comptent pour quel circuit |

Une catégorie (`U13 F`) appartient à un circuit (`U13`). C'est ce lien qui rend
possible le filtre du classement — celui dont l'absence gonflait le score de
17 grimpeurs sur 98 (voir [classeur-google.md](../../docs/technical/classeur-google.md)).

### `Success` — le cœur de la spec

| Colonne | Rôle |
| --- | --- |
| `id` | PK |
| `participant_id`, `bloc_id` | **UNIQUE ensemble** — c'est ce qui rend l'envoi idempotent |
| `horodatage` | quand |
| `source` | `scan` · `manuel` (spec 005) |
| `sheet_synced_at` | **nullable** — `NULL` = pas encore dans le classeur |

`sheet_synced_at` est ce qui remplace la file en RAM. Une réussite non
synchronisée est une ligne en base, pas un élément volatil : elle survit à un
redémarrage, à un crash, à une panne de Google.

### `Utilisateur` et `UtilisateurRole`

Posés maintenant, vides, pour éviter une migration en spec 005. Modèle guestFlow :
mot de passe haché, rôles en table de jointure, plusieurs rôles par personne.

## 2. Le classeur devient un miroir

### Avant — ce qui perdait des données

```
succès → queue.Queue (RAM) → worker → batchUpdate
                                          ↓
                              erreur ? le lot est vidé quand même
```

### Après

```
succès → base (sheet_synced_at = NULL) → réponse au juge
                    ↑
          worker : SELECT ... WHERE sheet_synced_at IS NULL
                    ↓
              batchUpdate
                    ↓
          succès ? UPDATE sheet_synced_at = now()
          échec  ? on ne touche à rien → retenté au cycle suivant
```

Trois propriétés que l'ancien n'avait pas :

- **rien n'est perdu à un redémarrage** — le travail à faire est en base ;
- **un échec Google est rattrapé tout seul**, sans intervention ;
- **on sait à tout moment ce qui n'est pas encore parti** : une requête SQL, et
  un compteur exposé dans `/health`.

Le travailleur tourne dans **un seul** processus, pas quatre. Verrou consultatif
en base (`sheet_sync` sur une table de verrous) : le premier worker gunicorn qui
l'obtient fait le travail, les autres passent leur tour.

## 3. Fin du `drop_all()`

`main.py` exécute aujourd'hui `db.drop_all()` **au niveau module**, donc à chaque
import — donc dans chacun des 4 workers gunicorn de la spec 001.

Remplacé par :

- création du schéma **si absent**, au démarrage, sous le même verrou ;
- migrations numérotées dans `migrations/`, jouées en séquence, idempotentes ;
- **jamais** de destruction, sous aucun prétexte.

Réinitialiser une compétition devient une action explicite de la console
d'administration, pas un effet de bord du démarrage.

## 4. L'import du classeur

`POST /admin/import/sheet` — sur commande, jamais dans le chemin d'une requête
juge (R7).

| Aujourd'hui | Après |
| --- | --- |
| Ligne acceptée seulement si exactement 6 colonnes → grimpeur **ignoré sans message** (R5) | ligne acceptée dès que nom et dossard sont là, le reste est facultatif |
| `line[-1]` comme numéro de bloc → faux sur une ligne courte (R6) | position **explicite** de la colonne, ligne trop courte = rejetée et signalée |
| Aucun retour | rapport : créés / mis à jour / ignorés, avec le motif ligne par ligne |
| Déclenché par un scan inconnu | jamais |

L'import est **idempotent** : le rejouer ne duplique rien et reprend les
corrections faites dans le classeur.

## 5. Le catalogue versionné

`Competition.catalogue_version` s'incrémente à chaque changement de participant
ou de bloc.

```http
GET /api/v2/catalog              → { version, participants[], blocs[], circuits[] }
GET /api/v2/catalog?depuis=41    → { version, changements: {...} }   ou 304
```

C'est ce qui permettra à l'application juge (spec 003) de valider les scans
**hors ligne** tout en récupérant en cours de compétition un participant ajouté à
14 h — le besoin des [contraintes métier §1](../../docs/contraintes-metier.md).

Taille : 98 participants + 67 blocs ≈ **6 à 8 ko compressés**. Un delta, quelques
centaines d'octets.

## 6. Les routes

### Inchangées — l'application `v3.1.4` doit continuer de marcher

`POST /climber/name`, `POST /bloc/name`, `POST /success` gardent **exactement**
leur contrat. Ce qui change est interne :

- `/success` écrit en base avant de répondre ;
- un dossard inconnu ne déclenche plus de lecture Google ;
- un doublon renvoie `201` sans créer de seconde ligne.

### Nouvelles

| Route | Protection | Rôle |
| --- | --- | --- |
| `GET /api/v2/catalog` | clé d'API | catalogue complet ou delta |
| `GET /health` | LAN | état + **nombre de réussites non synchronisées** |
| `POST /admin/import/sheet` | session | réimport sur commande |
| `GET /admin/import/rapport` | session | dernier rapport d'import |

### La clé d'API — le point délicat

L'application déployée n'envoie **aucune** clé. La rendre obligatoire la casse.

Proposition (Q1) : **mode « toléré »** — une clé valide est acceptée, une clé
absente est acceptée mais **journalisée et comptée**, une clé **invalide** est
refusée. On mesure ainsi la bascule, et on passe en mode strict par une variable
d'environnement le jour où la spec 003 est déployée.

## 7. Fichiers

| Fichier | Action |
| --- | --- |
| `climbcontest/__init__.py` | fabrique d'application |
| `climbcontest/models.py` | le modèle ci-dessus |
| `climbcontest/db.py` | session, verrou consultatif, migrations |
| `climbcontest/routes/{contest,catalog,admin}.py` | routes |
| `climbcontest/sheets/{client,importer,mirror}.py` | lecture, import, miroir |
| `climbcontest/auth.py` | clé d'API (mode toléré) |
| `migrations/001_initial.sql` | schéma |
| `wsgi.py` | pointe sur la fabrique |
| `main.py`, `models.py`, `google_sheets*.py` | **supprimés** — remplacés |
| `tests/` | pytest, base en mémoire |
