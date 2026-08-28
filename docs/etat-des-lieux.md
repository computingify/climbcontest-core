# ClimbContest — état des lieux (28 août 2026)

Audit complet du code existant, réalisé avant toute modification. Aucun fichier
existant n'a été touché : ce document et le reste de `docs/` sont les seuls ajouts.

---

## 1. Inventaire — ce qui existe réellement

| Projet | Emplacement | Dépôt GitHub | Dernier commit | Rôle | Statut |
| --- | --- | --- | --- | --- | --- |
| **Backend contest** | `climbcontest-core/` | `computingify/climbcontest-core` | 10/03/2026 | API Flask + écriture Google Sheets | **Actif — en production** |
| **App juge Android** | `~/AndroidStudioProjects/ClimbContest` ⚠️ *hors workspace* | `computingify/ClimbContest` | 08/01/2026 | Scan QR + envoi | **Actif — Play Store v3.1.3** |
| Politique de confidentialité | `climbcontestConfidentiality/` | `computingify/climbcontestConfidentiality` | 12/2024 | Page HTML exigée par le Play Store | Actif (statique) |
| Prototype Flutter | `climbContestApp/` | non versionné | 03/2025 | Démo scanner, **aucun appel serveur** | **Mort** |
| Prototype iOS | `ClimbContestIos/` | non versionné | 12/2024 | `Hello, world!` SwiftUI | **Mort** |
| Badgeuse club | `climbBackEnd/` | `computingify/climbBackEnd` | 2024 | Présence aux séances, HelloAsso | **Hors sujet ClimbContest** |

Deux constats structurants :

1. **L'app Android n'est pas dans ce workspace.** Elle vit dans
   `~/AndroidStudioProjects/ClimbContest`. Toute évolution qui touche à la fois
   l'app et le backend se fait donc aujourd'hui dans deux dossiers sans lien.
2. **`climbBackEnd` n'a rien à voir avec la compétition.** C'est l'outil de
   pointage des séances du club (users, sessions, import CSV, intégration
   HelloAsso). Je le sors du périmètre ClimbContest — voir §9 pour un point de
   sécurité le concernant.

---

## 2. Le flux fonctionnel actuel

```
   Juge (Android)                Backend Flask (Render)              Google Sheets
   ─────────────                 ──────────────────────              ─────────────
1. scan QR grimpeur   ──POST──►  /climber/name  {id:"12"}
                      ◄─201───   {success, id:"Dupont Léa"}
2. scan QR bloc       ──POST──►  /bloc/name     {id:"AJ1"}
                      ◄─201───   {success, id:"AJ1"}
3. appui "Envoyer"    ──POST──►  /success  {bib:"12", bloc:"AJ1"}
                      ◄─201───   {success:true}
                                        │
                                        ▼
                                  file d'attente RAM
                                  (flush si 50 items
                                   ou 40 s écoulées)
                                        │
                                        └──batchUpdate──►  onglet "Import"
                                                            cellule = "A"
```

Au démarrage du serveur, le sens inverse : le backend lit deux onglets du
classeur (`Plan` et `Listes`) pour construire sa base SQLite locale
(grimpeurs + blocs).

**Le classeur Google est aujourd'hui le cerveau du système** : il contient la
liste des grimpeurs, le plan des blocs, le contenu des QR codes, l'affectation
bloc↔catégorie et surtout **toutes les formules de calcul du classement**. Le
backend n'est qu'un tampon entre les téléphones et le classeur.

---

## 3. Le backend en détail (branche `master`, celle qui tourne)

### 3.1 Endpoints

| Méthode | Route | Corps | Réponse | Usage |
| --- | --- | --- | --- | --- |
| POST | `/api/v2/contest/climber/name` | `{"id": "<bib>"}` | `201 {success, id:<nom>}` | Valider un QR grimpeur |
| POST | `/api/v2/contest/bloc/name` | `{"id": "<tag>"}` | `201 {success, id:<tag>}` | Valider un QR bloc |
| POST | `/api/v2/contest/success` | `{"bib", "bloc"}` | `201 {success:true}` | Enregistrer une réussite |
| GET | `/api/v2/contest/options` | — | `{climbers[], blocs[]}` | Remplir la page de test |
| GET | `/api/v2/contest/worker-status` | — | `{worker_alive, queue_size}` | Diagnostic |
| GET | `/`, `/test` | — | HTML | Page juge web, page de test |

Aucune authentification, sur aucune route. L'URL publique suffit pour écrire
dans le classeur de la compétition.

### 3.2 Modèle de données (SQLite, `instance/database.db`)

`master` ne connaît que deux tables :

```python
Climber(id, name UNIQUE, bib UNIQUE, club, category)
Bloc(id, tag UNIQUE, number UNIQUE)
```

**Il n'existe aucune table `Success`.** Une réussite n'est jamais persistée
côté serveur : elle transite par une file d'attente en RAM puis part dans le
classeur. Conséquence directe : *aucun classement ne peut être calculé côté
backend aujourd'hui*, et une réussite perdue en route est perdue définitivement.

### 3.3 Le worker d'écriture Google Sheets

`main.py` fait tourner un thread qui dépile la file :

- déclenchement si **50 items** accumulés **ou** **40 s** écoulées ;
- déduplication par `set()` sur le couple `(bib, numéro de bloc)` ;
- un seul `values.batchUpdate` pour tout le lot ;
- adressage de la cellule : `colonne = bib + 3`, `ligne = numéro_bloc + 1`,
  valeur écrite = la lettre `"A"`.

C'est un bon design (il a résolu le problème de quota Google), mais il repose
entièrement sur la mémoire d'un processus — voir les risques en §6.

### 3.4 Lecture du classeur au démarrage

| Onglet | Plage | Ce qui en est extrait |
| --- | --- | --- |
| `Plan` | `D29:Y` | `tag = colonne D + colonne T`, `numéro = dernière colonne` |
| `Listes` | `F2:K` | nom, dossard, club, catégorie |

Le contenu des QR codes est donc bien **généré depuis le classeur** : le tag
d'un bloc est la concaténation de la lettre de zone et de son numéro dans la
zone (`AJ1`, `ZJ24`, `MV11`…), et le dossard du grimpeur sert de QR nominatif.

### 3.5 Déploiement

- **Production** : Render (`climbcontestserver.onrender.com`), `render.yaml`,
  gunicorn, plan gratuit. *Au moment de l'audit, aucune réponse HTTP obtenue en
  60 s depuis ma machine — à confirmer avec toi (instance en veille, suspendue,
  ou supprimée ?).*
- **Historique** : Raspberry Pi + systemd + gunicorn `-w 6` + certificat
  auto-signé (`deployement/deploy_app.sh`, `deploy_RPi.sh` vers `192.168.0.156`).
- Le jeton Google (`token.pickle` / `token.base64`) doit être fabriqué sur une
  machine avec navigateur puis copié — procédure documentée dans le README.

---

## 4. L'application juge Android

`~/AndroidStudioProjects/ClimbContest` — Kotlin + Jetpack Compose, `minSdk 29`,
`compileSdk 36`, version **3.1.4** (`versionCode 15`), AGP 8.13.2, Kotlin 2.3.0.

| Fichier | Rôle |
| --- | --- |
| `MainActivity.kt` | UI Compose (3 gros boutons), pilotage du scanner ML Kit |
| `MainViewModel.kt` | État : `climberId/Name`, `blocId/Name`, mode auto-évaluation |
| `Server.kt` | OkHttp, 3 appels REST, URL en dur |
| `SettingsScreen.kt` | Version + interrupteur « mode auto évaluation » |

Points notables :

- Scanner = **ML Kit `GmsBarcodeScanner`** (module Google Play installé à la
  demande) — pas de gestion de permission caméra à faire, mais dépendance forte
  aux Google Play Services.
- Le mode « auto évaluation » ne remet à zéro que le bloc et garde le grimpeur :
  pratique quand un même grimpeur enchaîne, mais non documenté.
- Les libellés français sont dans `res/values/strings_fr.xml` — c'est-à-dire
  dans la config **par défaut**, pas dans `values-fr/`. Ça marche (l'app est
  monolingue) mais le nommage laisse croire à une localisation qui n'existe pas.
- `AnnonayEscaladeLogo/`, `app/release/app-release.aab` : les artefacts de
  publication sont dans le dépôt.

---

## 5. Le trésor caché : les branches non mergées

`climbcontest-core` a **7 branches**, dont une qui change tout :

### `feature/ResultAlgorithm` — le classement déjà implémenté

Cette branche contient une refonte complète du backend **jamais déployée** :

- packaging propre en application factory (`climb_contest/`, `wsgi.py`,
  blueprint, `extensions.py`) ;
- **le modèle de données complet** : `Success` (avec timestamp), `Ranking`,
  table d'association `climber_category_bloc`, colonnes `score`,
  `category_rank`, `scratch_rank` sur `Climber` ;
- **l'algorithme de classement** (`results/processor.py`) ;
- une **page de résultats live** en Vue 3 (`/results`) avec podium et animation
  de montée/descente, rafraîchie toutes les 15 s ;
- une vraie suite **pytest** (`conftest.py`, `test_models`, `test_routes`,
  `test_processor`, `test_database_handler`) ;
- support **PostgreSQL** via `DATABASE_URL`.

**L'algorithme de la branche** est proche du bon, mais incomplet. La règle
réelle du classeur, désormais décodée et validée sur 1003 réussites réelles, est
documentée dans [technical/classeur-google.md](technical/classeur-google.md).
Trois écarts à corriger avant de reprendre cette branche :

1. elle ne filtre pas les réussites par **circuit** — sans ce filtre, 17
   grimpeurs sur 98 obtiennent un score trop élevé ;
2. son classement « scratch » est global, alors que celui du classeur est **par
   circuit** (filles et garçons de la même tranche d'âge ensemble) ;
3. elle ignore la validation par couleur et la saisie manuelle, deux mécanismes
   présents dans le classeur.

Les autres branches (`feature/FillLocalBdWithGSheet`, `feature/UnitTest`,
`feature/TryUT`, `tmp`) sont des étapes intermédiaires de la même exploration,
sans valeur propre. `bugfix/MissingSuccess` est déjà mergée dans `master`.

**La base locale `instance/database.db` est d'ailleurs au format de cette
branche** (tables `success`, `ranking`, `climber_category_bloc` remplies avec
120 grimpeurs, 53 blocs, 196 lignes de classement) : la branche a bien tourné
pour de vrai, elle n'a simplement jamais été mergée.

---

## 6. Anomalies et risques

Classés par gravité. Les lignes marquées **🔴** peuvent faire perdre des
résultats un jour de compétition.

### 🔴 R1 — La base est effacée à chaque démarrage de *chaque* worker

`main.py` exécute `db.drop_all()` puis `db.create_all()` **au niveau module**,
donc à chaque import. Gunicorn importe le module dans chaque worker : avec
`-w 6` (script de déploiement Raspberry Pi), six processus effacent tour à tour
la même base SQLite pendant que les autres l'interrogent. Si un worker redémarre
en pleine compétition, il repart d'une base vide et relit tout le classeur.
Symptôme côté juge : « grimpeur inconnu » aléatoire.

### 🔴 R2 — Les réussites vivent uniquement en RAM

Jusqu'à 50 réussites (ou 40 s de trafic) attendent dans une `queue.Queue` non
persistée. Redémarrage, crash, mise en veille Render → le lot est perdu, sans
trace ni alerte. Sur le plan gratuit Render, l'instance s'endort après 15 min
d'inactivité : c'est un scénario réaliste entre deux vagues de scan.

### 🔴 R3 — Un échec d'écriture Google est avalé en silence

`GoogleSheet.update_google_sheet()` attrape ses propres exceptions, imprime le
message et renvoie `False`. Le worker, lui, ignore la valeur de retour et vide
son lot dans tous les cas. Une erreur réseau ou un quota Google dépassé = 50
réussites effacées sans que personne ne le sache.

### 🔴 R4 — Aucune trace locale des réussites

Corollaire de R2/R3 : il n'existe aucun journal côté serveur. Impossible de
rejouer, de recompter, d'auditer une contestation, ni de reconstruire le
classement si le classeur est abîmé.

### 🟠 R5 — Import de grimpeurs silencieusement partiel

`populate_climbers` n'accepte une ligne que si `len(line) == 6` exactement. Or
Google Sheets **tronque les cellules vides de fin** : un grimpeur sans club ou
sans catégorie renvoie une ligne de 4 ou 5 éléments et **est ignoré sans
message**. Ajoute à ça `name UNIQUE` : deux homonymes dans deux clubs
différents font échouer le commit de tout l'import.

### 🟠 R6 — Numéro de bloc potentiellement faux

`populate_bloc` accepte les lignes de `len >= 17` et prend `line[-1]` comme
numéro de bloc. Pour une ligne complète (22 colonnes) `line[-1]` est bien la
colonne Y ; pour une ligne tronquée à 17 colonnes, `line[-1] == line[16]`,
c'est-à-dire **le numéro de la zone, pas le numéro de résultat**. Le bloc est
alors créé avec un mauvais numéro → les réussites atterrissent sur la mauvaise
ligne du classeur.

### 🟠 R7 — Appel Google Sheets dans le chemin de requête

Quand un dossard est inconnu, `check_climber` relit tout l'onglet `Listes` en
plein traitement HTTP. Un QR code étranger scanné en boucle (un spectateur, un
badge du club) déclenche autant de lectures Google, allonge le temps de réponse
et grignote le quota. Et comme la fonction n'ajoute que les noms absents, une
**correction** faite dans le classeur (dossard changé, catégorie corrigée) n'est
jamais reprise.

### 🟠 R8 — Aucune authentification

Les trois routes d'écriture sont ouvertes. Qui connaît l'URL peut injecter des
réussites arbitraires dans le classeur de la compétition.

### 🟠 R9 — Pas de file d'attente hors-ligne côté app

Si le réseau tombe (salle en sous-sol, 4G saturée un jour de compétition),
l'app affiche un toast d'erreur et le juge doit refaire la manipulation. Chaque
scan a besoin du réseau **avant** de pouvoir continuer.

### 🟡 R10 — Vérification du nom d'hôte TLS désactivée

`Server.kt` : `hostnameVerifier { _, _ -> true }`. Héritage de l'époque du
certificat auto-signé du Raspberry Pi, inutile depuis le passage à Render, et
qui ouvre la porte à une interception sur un réseau hostile.

### 🟡 R11 — Les « tests » tapent en production

`tests/test_*.py` sont des scripts de charge pointés sur
`https://climbcontestserver.onrender.com`, avec 99 clients simulés qui
**écrivent réellement** dans le classeur de la compétition. Les lancer par
inadvertance pollue les données réelles.

### 🟡 R12 — Pas de dédoublonnage durable des réussites

Le `set()` du worker ne déduplique que dans un même lot. Deux appuis sur
« Envoyer », ou deux juges qui valident le même passage, produisent deux envois.
Aujourd'hui c'est sans conséquence (on réécrit la même lettre `A` dans la même
cellule), **mais ça deviendra un bug de classement** dès qu'on comptera les
réussites côté serveur : la branche `ResultAlgorithm` n'a aucune contrainte
d'unicité sur `(climber_id, bloc_id)` et compterait le doublon deux fois.

### 🟡 R13 — `climbBackEnd` : secrets en clair dans un dépôt public

Le `README.md` de la badgeuse contient l'identifiant, le **secret client** et
des jetons HelloAsso (environnement sandbox). Même en sandbox, à révoquer.

---

## 7. Volume de données échangé — mesure et cible

C'est ta première demande, alors chiffrons-la.

### Aujourd'hui

| | Par validation |
| --- | --- |
| Requêtes HTTP | **3** (grimpeur, bloc, envoi) |
| Octets utiles | ~60 o de corps cumulé |
| Octets réels (en-têtes HTTP + TLS) | ~2 à 2,5 ko |
| Aller-retours réseau bloquants pour le juge | **3** |

Sur une compétition à ~3 600 validations : ~8 Mo et surtout **~10 800
aller-retours**. Le problème n'est pas le débit — c'est le nombre de
round-trips, chacun avec la latence de Render, chacun capable d'échouer, et
chacun bloquant le juge devant son téléphone.

### Cible proposée

| | Par validation |
| --- | --- |
| Requêtes HTTP | **0** pour les scans, ~0,1 pour l'envoi (lot de 10) |
| Octets réels | ~30 o par réussite dans un lot |
| Aller-retours bloquants | **0** |

Le principe : l'app télécharge **une fois** au démarrage le catalogue complet
(120 grimpeurs + 53 blocs + affectation bloc↔catégorie ≈ **6 à 10 ko
compressés**), valide les QR codes **en local** (instantané, sans réseau), et
envoie les réussites **par lots, en arrière-plan, avec file d'attente
persistante et clé d'idempotence**.

Gain : ~30× moins de requêtes, scan instantané, et surtout **l'app continue de
fonctionner quand le réseau tombe**. C'est le même geste qui règle R9 et une
partie de R2.

### Mesuré le 28/08, après implémentation

`tools/mesurer_volume.py`, contre la VM 110, sur 200 validations réelles
extrapolées à 3 600 :

| | v2 (aujourd'hui) | v3 (mesuré) |
| --- | --- | --- |
| Requêtes HTTP | 10 800 | **817** |
| Octets sur le fil | 4,53 Mo | **696 ko** |
| Allers-retours **bloquants** | 10 800 | **0** |

**L'estimation de ~30× était trop optimiste : le gain réel est de 13× sur les
requêtes et 6,5× sur le volume.** L'écart vient d'un lot de 5 (et non 10), et du
coût réel d'une réussite sur le fil — ~180 octets une fois les en-têtes amortis,
pas 30.

Le chiffre qui compte n'est aucun des deux. C'est **10 800 → 0** : le nombre de
fois où un juge attendait devant son téléphone.

---

## 8. Une VM à la maison, est-ce que ça suit ?

Oui, très largement. Ordre de grandeur d'une compétition :

| Grandeur | Valeur |
| --- | --- |
| Grimpeurs | ~120 |
| Blocs | ~53 |
| Réussites totales sur la journée | ~2 000 à 3 600 |
| Débit moyen | ~15 réussites/min |
| Pointe réaliste (10 juges qui valident en même temps) | ~60 req/min |
| Taille de la base en fin de compétition | < 1 Mo |

Un Raspberry Pi encaissait déjà ça. Une VM sur le Proxmox tient sans y penser —
le facteur limitant n'est pas le CPU, c'est **le réseau** :

- il faut une exposition HTTPS stable (ce qui rejoint ton chantier
  `domotique.adn-dev.fr`) ;
- **si ta connexion maison tombe, ou celle de la salle, la compétition
  s'arrête.** D'où l'importance du mode hors-ligne de §7 ;
- une variante à considérer : faire tourner le backend **sur place**, sur un
  mini-PC en réseau local à la salle, avec réplication vers la maison. À
  arbitrer ensemble.

Le vrai sujet de la page résultats spectateurs, ce n'est pas la charge non plus
(quelques centaines de rafraîchissements par minute au pire), c'est le fait
d'exposer ta ligne domestique à un public. Un cache court + un reverse proxy
suffisent, mais ça se conçoit.

---

## 9. Ce que je propose de sortir du périmètre

- **`climbContestApp/` (Flutter)** — 180 lignes de démo scanner sans aucun appel
  serveur. Ton intuition est juste : à supprimer.
- **`ClimbContestIos/`** — un `Hello, world!` SwiftUI de décembre 2024. À
  supprimer aussi ; l'iPhone sera traité autrement (voir la feuille de route).
- **`climbBackEnd/`** — projet différent (badgeuse du club). À garder, mais dans
  son coin, avec juste la révocation des secrets HelloAsso à faire.

---

## 10. Ce que je ne sais pas encore — questions pour toi

Ce sont les seuls points qui me bloquent pour écrire les specs. Le reste, j'ai
tout ce qu'il faut.

1. ~~**Le classeur Google.**~~ **Résolu** — accès en lecture obtenu, les trois
   éditions sont analysées et l'algorithme est reproduit à l'identique. Voir
   [technical/classeur-google.md](technical/classeur-google.md).
2. ~~**La règle de classement exacte.**~~ **Résolue** — y compris les ex æquo
   (même rang, aucun départage sportif). Restent deux mécanismes optionnels à
   trancher : la **validation par couleur** (réussir 100 % de deux couleurs plus
   dures valide les couleurs plus faciles) et la **saisie manuelle** de secours.
   Aucun des deux n'était actif en novembre 2025.
3. **Le format de compétition.** Les éditions passées vont de U10 à U17 selon
   les années. Y a-t-il des tours de finale (l'onglet `Finales` existe mais est
   vide) ? Le nombre de catégories change-t-il à chaque édition ?
4. **Le classement scratch** : affiché aux spectateurs, ou seulement interne ?
5. **Render.** Le service répond-il encore ? Veux-tu qu'on garde Render en
   secours le temps de basculer sur la VM ?
6. **Le dépôt.** Aujourd'hui : 3 dépôts GitHub + une app hors workspace. Je
   propose un **monorepo** `climbcontest` (backend + apps + docs + specs), parce
   qu'une évolution touche presque toujours l'app *et* le backend. C'est une
   décision qui t'appartient — je n'ai rien déplacé.
7. **Prochaine échéance.** Y a-t-il une compétition prévue, et quand ? Ça change
   l'ordre des chantiers : si c'est proche, on sécurise l'existant avant tout.

---

## 10 bis. Le gel de repli

Réalisé le 28 août 2026, sur ta demande : tags `V2.1.1` (backend) et `V3.1.4`
(app), *bundles* git hors-ligne, APK installable, secrets Google, et export
intégral des trois classeurs. Procédure de retour arrière complète dans
[plan-de-repli.md](plan-de-repli.md).

Une seule action reste de ton côté : **copier `archive/gel-2026-08/secrets/` hors
de ce Mac**. C'est la seule partie du gel qui n'est redondée nulle part.

---

## 11. Synthèse en cinq lignes

Le système marche et a tourné en vraie compétition, mais il repose sur trois
fragilités : **la base est effacée à chaque démarrage**, **les réussites ne sont
écrites nulle part côté serveur**, et **une erreur Google Sheets détruit un lot
en silence**. Le classement que tu veux pour la page live est
désormais **entièrement spécifié et validé** : l'algorithme du classeur reproduit
196 scores et rangs réels sur 196. Et la bonne réponse à « minimiser
les données échangées » n'est pas de compresser les requêtes : c'est de
n'en faire aucune pendant les scans.
