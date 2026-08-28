# CLAUDE.md

Point d'entrée pour toute session Claude Code sur ClimbContest. **Premier
fichier à lire.** Il est volontairement court : le détail est dans `docs/` et
`specs/`.

## Où trouver le contexte

| Tu veux savoir… | Lis ceci |
| --- | --- |
| Ce qui existe, ce qui marche, ce qui est cassé | [docs/etat-des-lieux.md](docs/etat-des-lieux.md) |
| Comment le système est construit aujourd'hui | [docs/technical/architecture-actuelle.md](docs/technical/architecture-actuelle.md) |
| **La mécanique du classeur Google et l'algorithme de classement** | [docs/technical/classeur-google.md](docs/technical/classeur-google.md) |
| Revenir à la version 2025-2026 en cas de pépin | [docs/plan-de-repli.md](docs/plan-de-repli.md) |
| **Ce que le terrain impose** (participants à chaud, HelloAsso, format) | [docs/contraintes-metier.md](docs/contraintes-metier.md) |
| Ce qu'on veut construire et dans quel ordre | [docs/roadmap.md](docs/roadmap.md) |
| Comment on travaille (spec → plan → code) | [docs/workflow.md](docs/workflow.md) |
| Comment les dépôts sont organisés | [docs/preparation-depots.md](docs/preparation-depots.md) |
| La liste des specs | [docs/specs-index.md](docs/specs-index.md) |
| Le détail d'une évolution | `specs/XXX-nom/{spec,architecture,plan}.md` |

## Le projet en un paragraphe

ClimbContest outille les compétitions de bloc du club d'escalade d'Annonay.
Chaque grimpeur porte un **QR code nominatif** (son dossard), chaque bloc porte
un **QR code de voie**. Un juge, sur son téléphone, scanne le grimpeur puis le
bloc réussi, appuie sur « Envoyer », et la réussite part vers un backend Flask
qui la reporte dans un **classeur Google Sheets**. Ce classeur est aujourd'hui
le cerveau du système : il génère le contenu des QR codes, tient la liste des
grimpeurs et des blocs, et calcule le classement par ses formules. L'objectif à
terme est de ramener cette mécanique côté backend pour afficher un classement
en direct.

## Où est le code

| Composant | Chemin | Dépôt |
| --- | --- | --- |
| **Dépôt pivot** : backend + docs + specs + tools | `climbcontest-core/` | `computingify/climbcontest-core` |
| App juge Android | `climbcontest-android/` | `computingify/ClimbContest` |
| Politique de confidentialité | `climbcontestConfidentiality/` | `computingify/climbcontestConfidentiality` |
| Badgeuse du club (**hors périmètre**) | `climbBackEnd/` | `computingify/climbBackEnd` |
| Prototypes morts (**à supprimer**) | `climbContestApp/`, `ClimbContestIos/` | — |

Ce dossier racine **n'est pas un dépôt git** : chaque sous-projet a le sien.
**Pas de monorepo** — la décision et son argumentaire sont dans
[docs/preparation-depots.md](docs/preparation-depots.md). `climbcontest-core`
est le dépôt **pivot** : il porte le backend *et* `docs/`, `specs/`, `tools/`,
`fixtures/`, sur le modèle de `sowel-core`.

⚠ Les deux dépôts ClimbContest sont **publics**. Bénéfice : l'agent de
déploiement n'a besoin d'aucun jeton. Contrepartie stricte : **aucun secret ne
peut jamais y être committé**.

## Règles non négociables

1. **Pas de code sans spec validée.** Voir [docs/workflow.md](docs/workflow.md).
   Les portes 2 (spec approuvée) et 7 (merge approuvé) appartiennent à Adrien.
2. **Les scripts de `tools/load/` écrivent réellement** dans le classeur de la
   compétition. Ils refusent de démarrer sans `CLIMBCONTEST_LOAD_URL` explicite ;
   ne jamais leur donner l'adresse de production.
3. **Ne jamais écrire dans le classeur Google** hors d'un environnement de test
   explicitement dédié. Le classeur est la mémoire de la compétition. Pour le
   lire, `tools/dump_sheet.py` (lecture seule) — voir
   [docs/technical/classeur-google.md](docs/technical/classeur-google.md).
4. **Ne jamais commiter de secret** : `credentials.json`, `token.pickle`,
   `token.base64`, `security/*.pem` sont ignorés par git, ça doit le rester.
5. **Jamais de commit direct sur `master`.** Branche + PR.
6. Pas de ligne `Co-Authored-By` dans les messages de commit.
7. **Ne jamais committer de données personnelles.** Les classeurs contiennent des
   noms de mineurs. `archive/` et les dumps bruts restent hors git.
8. **Ne pas toucher au gel de repli** (`archive/gel-2026-08/`, tags `V2.1.1` et
   `V3.1.4`) : c'est le retour arrière garanti pour la compétition à venir.

## Conventions

- **Langue** : specs et documentation en français ; code, identifiants, commits
  et branches en anglais.
- **Backend** : Python 3.13 sur la VM, Flask, SQLAlchemy. Dépendances dans
  `requirements.txt` à la racine.
- **Android** : Kotlin, Jetpack Compose, Material 3, OkHttp, ML Kit.
- **Branches** : `feat/`, `fix/`, `refactor/`, `docs/`.
- **Commits** : conventionnels. Portées : `api`, `sheets`, `db`, `ranking`,
  `android`, `web`, `deploy`, `docs`.

## Commandes utiles

```bash
# Publier une release (tag -> CI -> la VM tire toute seule)
./scripts/release.sh 0.2.0

# Sur la VM 110
ssh adrien@192.168.0.32 'journalctl -t climbcontest-deploy -f'   # suivre un déploiement
ssh adrien@192.168.0.32 'sudo climbcontest-rollback --list'      # releases installées
ssh adrien@192.168.0.32 'sudo climbcontest-rollback'             # revenir en arrière

# Allumer / éteindre la VM (elle est éteinte hors compétition)
ssh root@192.168.0.21 'qm start 110'
ssh root@192.168.0.21 'qm shutdown 110'

# Vérifier qu'un moteur de classement reproduit le classeur
python3 tools/verify_ranking.py fixtures/contest-nov2025.json

# Android
cd ../climbcontest-android && ./gradlew assembleDebug
```

## En cas de doute

1. Lire [docs/etat-des-lieux.md](docs/etat-des-lieux.md) — l'anomalie est
   peut-être déjà répertoriée (R1…R13).
2. Vérifier dans [docs/specs-index.md](docs/specs-index.md) si une spec couvre
   déjà le sujet.
3. Chercher un motif existant dans le code avant d'en inventer un.
4. **Demander à Adrien** si le besoin n'est pas clair — ne jamais supposer.
