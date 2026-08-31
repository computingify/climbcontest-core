# Plan — spec 015

## Étapes

- [x] **1. Le client** — `sheets/client.py` : lecture de `token.json` en tête de
      liste, réécriture après rafraîchissement, `metadonnees()`, `grille()`,
      `agrandir_si_besoin()`, `vider_matrice()`, injection de `feuilles` pour
      les tests, et l'appel d'agrandissement dans `marquer_reussites()`.
- [x] **2. Le module** — `sheets/parametrage.py` : `extraire_identifiant`,
      `etat`, `tester`, `relier` (trois modes), `poser_jeton`.
- [x] **3. Les routes** — quatre routes `ADMIN` dans `routes/admin.py`.
- [x] **4. La console** — vue « Classeur », ses trois cartes, son JavaScript.
- [x] **5. L'outil** — `tools/exporter_jeton.py`.
- [x] **6. Les tests** — les deux fichiers, tous les critères A1→A14.
- [x] **7. La documentation** — `classeur-google.md`, `runbook-competition.md`,
      `specs-index.md`, `CHANGELOG.md`.
- [x] **8. Vérification à l'écran** — la console pilotée pour de vrai, chaque
      carte capturée, sur un serveur local et une base jetable.

## Plan de test

Écrit avant l'implémentation. Aucun accès réseau : le service Google est
remplacé par un objet qui compte ce qu'on lui demande.

### `tests/test_client_classeur.py` — le classeur vu du client

| Scénario | Attendu | Critère |
| --- | --- | --- |
| Dossard 130 (colonne DA) sur une grille de 26 colonnes | `updateSheetProperties` appelé, `columnCount ≥ 133`, puis `values.batchUpdate` | A1 |
| Bloc n° 80 sur une grille de 50 lignes | `rowCount ≥ 81` | A2 |
| Dossard 5 sur une grille de 123 colonnes | **aucun** `updateSheetProperties` | A3 |
| Deux lots successifs qui tiennent tous deux | **une seule** lecture de grille (cache) | A3 |
| L'agrandissement échoue (Google refuse) | `ErreurClasseur`, **rien n'est écrit** | A1 |
| `vider_matrice()` avec 3 blocs et 12 dossards | plage effacée `Import!D2:O4`, jamais `A`, `B`, `C` ni la ligne 1 | A9 |
| `vider_matrice()` sur une matrice vide | aucun appel, renvoie 0 | A9 |
| `colonne(1) / (26) / (27) / (703)` | `A / Z / AA / AAA` | — |
| Dossier avec `token.json` **et** `token.pickle` | c'est le JSON qui est lu | A12 |
| Dossier sans aucun jeton | `etat_jeton()["present"] is False`, pas d'exception | A14 |

### `tests/test_classeur_parametrage.py` — le module et les routes

| Scénario | Attendu | Critère |
| --- | --- | --- |
| `https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0` | `<ID>` | A4 |
| `.../spreadsheets/d/<ID>` sans suffixe, et `<ID>` nu | `<ID>` | A4 |
| `https://exemple.fr/rien`, chaîne vide, `d/court` | `ErreurParametrage`, message qui dit quoi coller | A5 |
| `POST /admin/classeur` mode `relier` | 200, `comp.spreadsheet_id` changé, réussites intactes | A4 |
| `POST /admin/classeur` mode `rejouer` | 200, toutes les réussites `sheet_synced_at IS NULL` | A7 |
| Mode `reinitialiser` sans confirmation | 400, base **et** classeur intacts | A8 |
| Mode `reinitialiser` avec `EFFACER` | matrice vidée, réussites/participants/blocs supprimés, `catalogue_version` incrémentée | A9 |
| Mode `reinitialiser` sur une compétition `en_cours` | 409, rien touché | — |
| Mode `reinitialiser` quand Google refuse le vidage | 502, **la base n'a pas bougé** | A9 |
| Mode inconnu | 400 | — |
| `POST /admin/classeur/test` sur classeur fictif | titre, onglets manquants, taille de grille | A6 |
| `POST /admin/classeur/test` sans jeton | 502, message de Google, pas de 500 | A14 |
| Test avec un dossard au-delà de la largeur des formules | avertissement de capacité dans la réponse | A6 |
| `POST /admin/classeur/jeton` avec un JSON complet | 200, `<secrets>/token.json` en `0600`, ancien conservé en `.precedent` | A10 |
| Jeton sans `refresh_token`, JSON illisible, corps vide | 400, fichier en place **inchangé** | A11 |
| Les quatre routes en organisateur non-admin | 403 | A13 |
| Les quatre routes sans session | 401 | A13 |
| `GET /admin/classeur` sans compétition active | 200, `competition: null`, pas d'erreur | — |
| La console appelle `/admin/import/sheet` | présent dans le gabarit (test de contrat existant) | A15 |

### Non régression

| Suite | Attendu |
| --- | --- |
| `pytest` complet (597 tests) | vert, aucun test existant modifié pour passer |
| `tests/test_miroir.py` | inchangé : le faux classeur des tests du miroir n'a pas d'agrandissement à faire |
| `node --test tests/js` (124 tests) | vert — la vue « Classeur » ne touche pas au JavaScript du juge |

### À l'écran (étape 8)

| Écran | Ce qu'on vérifie |
| --- | --- |
| Vue « Classeur », sans classeur relié | dit « aucun classeur », n'affiche pas d'erreur |
| Après avoir collé un lien | l'identifiant est extrait, l'état se rafraîchit tout seul |
| Mode « nouvelle compétition » | le champ de confirmation apparaît, le bouton reste inerte sans `EFFACER` |
| Compte organisateur (non-admin) | l'entrée « Classeur » n'apparaît pas |
| Téléphone (largeur 390) | les trois cartes tiennent, rien ne déborde |
