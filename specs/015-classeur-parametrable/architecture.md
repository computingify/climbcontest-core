# Architecture — spec 015

## 1. Vue d'ensemble

```
console  ──GET  /admin/classeur          ─→ etat()          ─→ base + dossier des secrets
   │     ──POST /admin/classeur/test     ─→ tester()        ─→ Google (LECTURE seule)
   │     ──POST /admin/classeur          ─→ relier()        ─→ base (+ Google si mode « nouvelle »)
   └─────  POST /admin/classeur/jeton    ─→ poser_jeton()   ─→ <secrets>/token.json

miroir   ── marquer_reussites() ─→ agrandir_si_besoin() ─→ values.batchUpdate
                                         ↑
                          spreadsheets.get (grille) puis, SEULEMENT si trop petit,
                          spreadsheets.batchUpdate(updateSheetProperties)
```

Rien de nouveau dans le modèle de données : `Competition.spreadsheet_id` existe
depuis la spec 002. **Aucune migration.**

## 2. Le client `sheets/client.py`

### Le jeton, trois formats, un ordre

```
<secrets>/token.json     ← nouveau, écrit par la console, format Credentials.to_json()
<secrets>/token.pickle   ← posé par scp, inchangé
<secrets>/token.base64   ← repli historique, inchangé
```

Dans chacun des dossiers de `_dossiers_de_jeton()` (config, variable
d'environnement, répertoire courant), dans cet ordre.

`token.json` est **du JSON**, pas un pickle : le charger n'exécute rien. C'est
la raison d'être du format ici, et c'est ce qui permet à la console de
l'accepter (§ 6 de la spec).

Un jeton rafraîchi est **réécrit** dans `token.json` (écriture atomique,
`0600`) quand c'est de là qu'il vient. Un échec de réécriture est journalisé,
jamais fatal : le jeton en mémoire est valide, la synchronisation continue.

### Nouvelles méthodes

| Méthode | Appel Google | Rôle |
| --- | --- | --- |
| `metadonnees()` | `spreadsheets.get` (lecture) | titre + onglets + grilles, mis en cache |
| `grille(onglet)` | idem, cache | `(sheetId, lignes, colonnes)` |
| `agrandir_si_besoin(onglet, lignes, colonnes)` | `spreadsheets.batchUpdate` **si et seulement si** trop petit | élargit, avec une marge |
| `vider_matrice()` | `values.clear` | efface les « A » de `Import`, jamais les en-têtes |
| `etat_jeton()` (fonction de module) | aucun | ce que la console affiche |

`marquer_reussites()` calcule `max(dossard) + 3` et `max(numéro) + 1`, appelle
`agrandir_si_besoin("Import", …)`, puis écrit comme avant. Un lot qui tient
dans la grille ne coûte **qu'un seul appel de plus au premier lot** (la lecture
de la grille, mise en cache pour la vie de l'objet), et zéro ensuite.

**La marge : 5 lignes / 5 colonnes de rab.** Sans elle, dix inscriptions à chaud
d'affilée donneraient dix agrandissements. Avec, le cas normal en fait un.

**`vider_matrice()` borne la plage sur le contenu réel** : lignes portant un
numéro de bloc en colonne A, colonnes portant un dossard en ligne 1. La plage
effacée commence en `D2` — la ligne 1 (dossards), les colonnes A à C (numéro,
tag) et l'horodatage `D103` restent intacts.

### Injection pour les tests

`ClasseurGoogle(identifiant, feuilles=…)` : quand `feuilles` est fourni, il
remplace `service.spreadsheets()`. C'est la couture qui permet de tester
l'agrandissement sans réseau — la suite n'a toujours **aucune** dépendance
Google (les paquets `google-*` ne sont même pas installés dans le venv de dev).

## 3. Le module `sheets/parametrage.py`

Toute la logique métier, testable sans Flask ni Google.

```python
extraire_identifiant(texte) -> str        # URL complète, /d/<id>/, ou identifiant nu
etat(comp) -> dict                        # ce que la console affiche
tester(identifiant, classeur=None) -> dict
relier(comp, identifiant, mode, confirmation, classeur=None) -> dict
poser_jeton(texte) -> dict                # valide le JSON, écrit <secrets>/token.json
```

### `extraire_identifiant`

Accepte, dans l'ordre : `https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0`,
`.../d/<ID>`, `<ID>` nu. Un identifiant Google fait 20 caractères ou plus dans
`[A-Za-z0-9_-]`. Tout le reste lève `ErreurParametrage` avec un message qui dit
**quoi coller** — pas « identifiant invalide ».

### Les trois modes de `relier`

| `mode` | Ce qui est fait, dans cet ordre |
| --- | --- |
| `relier` | `comp.spreadsheet_id = <id>` |
| `rejouer` | idem, puis `UPDATE success SET sheet_synced_at = NULL` pour la compétition |
| `reinitialiser` | vérifie `confirmation == "EFFACER"` et `statut != en_cours`, vide la matrice `Import` du **nouveau** classeur, supprime réussites / participants / blocs / circuits de la compétition, puis relie et incrémente `catalogue_version` |

`reinitialiser` vide le classeur **avant** de toucher la base : si Google
refuse, rien n'a été détruit côté serveur. L'ordre inverse laisserait une base
vide et un classeur plein, c'est-à-dire le pire des deux.

`catalogue_version` est incrémentée par `prochaine_version_catalogue()` : les
téléphones doivent retélécharger un catalogue vidé, sinon ils continueraient
d'afficher les grimpeurs de l'édition précédente (le correctif du 30/08).

### `poser_jeton`

1. `json.loads` — un JSON illisible est refusé.
2. Clés exigées : `refresh_token`, `client_id`, `client_secret`. Sans
   `refresh_token`, le jeton meurt dans l'heure : le refuser tout de suite vaut
   mieux qu'une panne le lendemain.
3. Écriture atomique dans `<secrets>/token.json` : fichier temporaire dans le
   même dossier, `chmod 0600`, `os.replace`.
4. L'ancien fichier est conservé en `token.json.precedent` — un jeton écrasé par
   erreur se rattrape sans SSH.

## 4. Les routes (`routes/admin.py`)

| Route | Rôle exigé | Corps | Réponses |
| --- | --- | --- | --- |
| `GET /admin/classeur` | `ADMIN` | — | 200 état |
| `POST /admin/classeur/test` | `ADMIN` | `{lien?}` | 200 rapport, 502 si Google refuse |
| `POST /admin/classeur` | `ADMIN` | `{lien, mode, confirmation?}` | 200, 400 (lien/mode/confirmation), 409 (compétition en cours), 502 |
| `POST /admin/classeur/jeton` | `ADMIN` | `{jeton}` | 200 état du jeton, 400 |

**`ADMIN` et pas `ORGANISATEUR`** : ces quatre routes décident *où vont les
données* et *avec quelle identité Google*. L'import, lui, reste organisateur —
il ne fait que relire.

Chaque changement est journalisé avec l'identifiant du compte, l'identifiant du
classeur (l'ancien et le nouveau) et le mode. Le jeton n'est **jamais** écrit
dans le journal, ni renvoyé par une route.

## 5. La console (`templates/admin.html`)

Une entrée de navigation **« Classeur »** dans le groupe « Administration »,
avant « Réglages », visible seulement pour un administrateur (comme le bloc
« Comptes » : le serveur refuse de toute façon, masquer évite d'offrir un
bouton qui ne marche pas).

Trois cartes :

1. **Où vont les réussites** — compétition active, classeur relié (lien
   cliquable), état du jeton, réussites en attente. Bouton « Tester l'accès »
   qui affiche le titre du classeur, les onglets manquants s'il y en a, la
   taille de la grille `Import` et **l'avertissement de capacité** quand le plus
   grand dossard attribué dépasse la largeur prévue par les formules.
2. **Relier un classeur** — champ « lien », trois modes en boutons radio, champ
   de confirmation qui n'apparaît qu'en mode « nouvelle compétition ».
3. **Jeton Google** — zone de texte pour le JSON, et le rappel de la commande
   qui le produit (`python3 tools/exporter_jeton.py`).

## 6. `tools/exporter_jeton.py`

Vingt lignes, sur le Mac, hors du serveur : lit `token.pickle` (ou
`token.base64`), écrit le JSON de `Credentials.to_json()` sur la sortie
standard. C'est ce texte qu'on colle dans la console.

## 7. Fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/sheets/client.py` | jeton JSON, grille, agrandissement, vidage, injection |
| `climbcontest/sheets/parametrage.py` | **nouveau** — la logique de la spec |
| `climbcontest/routes/admin.py` | quatre routes |
| `climbcontest/templates/admin.html` | vue « Classeur » + son JavaScript |
| `tools/exporter_jeton.py` | **nouveau** |
| `tests/test_classeur_parametrage.py` | **nouveau** |
| `tests/test_client_classeur.py` | **nouveau** |
| `docs/technical/classeur-google.md` | § agrandissement, § jeton |
| `docs/runbook-competition.md` | le geste « changer de classeur » |
| `docs/specs-index.md`, `CHANGELOG.md` | tenue à jour |
