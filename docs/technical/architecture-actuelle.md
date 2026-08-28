# Architecture actuelle (as-is)

Référence technique de ce qui tourne aujourd'hui, branche `master` de
`climbcontest-core` + app Android `v3.1.4`. Ce document décrit l'existant, pas
la cible — la cible se construira spec par spec dans `specs/`.

Pour l'analyse critique de cette architecture, voir
[etat-des-lieux.md](../etat-des-lieux.md).

---

## Vue d'ensemble

```
┌────────────────────┐
│  App juge Android  │  Kotlin + Compose + ML Kit
│  (n exemplaires)   │  OkHttp, URL en dur
└─────────┬──────────┘
          │ HTTPS, 3 POST par validation
          ▼
┌────────────────────────────────────────────┐
│  Flask (gunicorn) — Render / Raspberry Pi  │
│                                            │
│  routes  ──►  SQLite (Climber, Bloc)       │  base reconstruite
│    │                                       │  à chaque démarrage
│    └──►  queue.Queue (RAM)                 │
│              │                             │
│              ▼                             │
│         worker thread                      │
│         flush : 50 items | 40 s            │
└──────────────┬─────────────────────────────┘
               │ Sheets API v4 : values.batchUpdate
               ▼
   ┌───────────────────────────────┐
   │  Google Sheets (le cerveau)   │
   │                               │
   │  Listes  : grimpeurs          │──┐
   │  Plan    : blocs + QR codes   │──┤ lus au démarrage
   │  Import  : matrice réussites  │◄─┘ écrit en continu
   │  …       : formules classement│
   └───────────────────────────────┘
```

---

## Backend

### Fichiers

| Fichier | Rôle |
| --- | --- |
| `main.py` | App Flask, routes, worker thread, file d'attente |
| `models.py` | `Climber`, `Bloc` (SQLAlchemy) |
| `google_sheets.py` | Auth OAuth, `batchUpdate`, `values.get`, conversion n° → colonne |
| `google_sheets_reader.py` | `populate_climbers()`, `populate_bloc()` |
| `gunicorn_config.py` | Hook `on_starting` → `db.create_all()` |
| `render.yaml` | Déploiement Render |
| `deployement/` | Scripts Raspberry Pi (systemd, certbot), `requirements.txt` |
| `templates/`, `static/` | Page juge web (`/`) et page de test (`/test`) |
| `tests/` | Scripts de charge (⚠ pointés sur la prod) |

### Cycle de vie d'un process

1. Import de `main.py` → `db.drop_all()` + `db.create_all()`
2. `sync_data_from_google_sheet()` → lecture `Plan` puis `Listes`
3. Première requête → `@app.before_request` démarre le worker thread s'il est
   mort ou absent (contournement du `fork()` de gunicorn)
4. Le worker tourne jusqu'à l'arrêt du process

### Modèle de données

```python
Climber(id PK, name UNIQUE NOT NULL, bib UNIQUE NOT NULL, club, category)
Bloc(id PK, tag UNIQUE NOT NULL, number UNIQUE NOT NULL)
```

`tag` = le contenu du QR code du bloc (`AJ1`, `ZJ24`…).
`number` = le numéro de la ligne du bloc dans l'onglet `Import`.
`bib` = le contenu du QR code du grimpeur.

Aucune table de réussites.

### Contrat d'API

Toutes les routes sont en `POST` avec `Content-Type: application/json`, sauf
mention contraire. Le code HTTP de succès est **201** (y compris pour de simples
vérifications), et **400** couvre indistinctement « données manquantes »,
« inconnu » et « erreur interne ».

```http
POST /api/v2/contest/climber/name
{"id": "12"}
→ 201 {"success": true, "message": "...", "id": "Dupont Léa"}
→ 400 {"success": false, "message": "Unregistered climber bib = 12"}

POST /api/v2/contest/bloc/name
{"id": "AJ1"}
→ 201 {"success": true, "message": "...", "id": "AJ1"}

POST /api/v2/contest/success
{"bib": "12", "bloc": "AJ1"}
→ 201 {"success": true, "message": "Well done"}

GET /api/v2/contest/options       → {"climbers": [...], "blocs": [...]}
GET /api/v2/contest/worker-status → {"worker_alive", "queue_size", "queue_empty"}
```

---

## Correspondance avec le classeur Google

`SPREADSHEET_ID = 1h3e8QUSXnCJLSYSFyB8X92cppDubeDx0yi8mn3NSh5s` (édition
décembre 2025). Deux IDs précédents sont conservés en commentaire dans
`google_sheets.py`.

### Lecture — onglet `Plan`, plage `D29:Y`

Une ligne = un bloc. Colonnes utilisées :

| Index (0-based) | Colonne | Contenu |
| --- | --- | --- |
| `0` | D | Lettre de zone (`A`, `Z`, `M`…) |
| `5` à `13` | I → Q | Colonnes de catégories (branche `ResultAlgorithm` uniquement) |
| `16` | T | Numéro du bloc dans sa zone |
| `-1` | Y | Numéro du bloc dans l'onglet `Import` |

`tag = ligne[0] + ligne[16]` → `"Z"` + `"J6"` = `ZJ6`.

⚠ La branche `master` lit à partir de la ligne **29** ; la branche
`ResultAlgorithm` lit à partir de la ligne **28** parce qu'elle utilise la
première ligne comme en-tête de catégories.

### Lecture — onglet `Listes`, plage `F2:K`

| Index | Colonne | Contenu |
| --- | --- | --- |
| `0` | F | Nom complet |
| `1` | G | Dossard |
| `4` | J | Club |
| `5` | K | Catégorie (`U11 F`, `U15 H`…) |

### Écriture — onglet `Import`

Matrice grimpeurs × blocs. Pour une réussite `(bib, numéro_bloc)` :

```
colonne = number_to_excel_column(bib + 3)
ligne   = numéro_bloc + 1
valeur  = "A"
```

Un lot est envoyé en un seul `values.batchUpdate` avec
`valueInputOption: "RAW"`.

---

## Application Android

```
MainActivity ──► MainViewModel (StateFlow) ──► Compose UI
     │
     ├──► GmsBarcodeScanner (ML Kit, module Play installé à la demande)
     │
     └──► Server ──► OkHttp ──► https://climbcontestserver.onrender.com
```

Les deux constantes qui décrivaient ce paragraphe **n'existent plus**, retirées
ensemble :

- ~~`RUN_LOCAL_SERVER = 0` → prod ; `= 1` → `https://10.0.2.2`.~~ L'adresse vient
  maintenant de `BuildConfig.SERVER_URL`, choisie par le type de build et
  surchargeable par `-PserverUrl=` (debug) ou `-PreleaseServerUrl=` (release,
  qui exige du https). Plus besoin de recompiler pour changer de serveur.
- ~~`RUN_ON_EMULATOR = 1` → génère des valeurs aléatoires au lieu de scanner.~~
  La constante valait `0` — donc du code mort — et les valeurs qu'elle
  produisait n'existaient dans aucun jeu de données (dossard tiré dans `1..39`,
  tag de bloc forcé à `"Z1"`). Le scan aurait échoué à tous les coups.
- Le mode « auto évaluation » (`MainViewModel.autoEval`) conserve le grimpeur
  après un envoi réussi et ne réinitialise que le bloc.

---

## Déploiement

### Render (production actuelle)

```yaml
startCommand: gunicorn main:app --bind 0.0.0.0:$PORT \
  --capture-output --enable-stdio-inheritance \
  --access-logfile - --error-logfile -
```

Détection prod/dev par la présence de la variable `PORT` : en prod, pas de SSL
côté Flask (Render termine le TLS), `DEBUG=False`.

### Raspberry Pi (historique)

`deployement/deploy_app.sh` : venv, systemd
(`climb_constest_server_app.service`), gunicorn `-w 6` avec certificat
auto-signé `security/cert.pem`, timer certbot. `deploy_RPi.sh` pousse la mise à
jour en SSH vers `192.168.0.156`.

### Secrets

| Fichier | Contenu | Versionné ? |
| --- | --- | --- |
| `credentials.json` | Client OAuth Google | non (gitignore) |
| `token.pickle` | Jeton OAuth (généré sur machine avec navigateur) | non |
| `token.base64` | Même jeton, encodé pour Render | non |
| `security/*.pem` | Certificat auto-signé | non |

Procédure de fabrication du jeton : voir le `README.md` du serveur.
