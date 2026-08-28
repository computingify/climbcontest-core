# Organisation des dépôts

> ✅ **Fait le 28 août 2026.** Ce document décrit l'organisation retenue et les
> décisions qui y ont mené. Le journal de ce qui a été exécuté est en fin de page.

---

## Le constat

### Le point de départ : rien n'était versionné

`CLAUDE.md`, `docs/`, `specs/`, `tools/`, `fixtures/` vivent à la racine de
`annonayEscalade`, **qui n'est pas un dépôt git**. L'audit, les specs, la
mécanique du classeur décodée, le jeu de test à 196/196 : tout ça n'existe que
sur ce Mac.

C'est exactement le problème qu'on vient de corriger pour le code avec le gel de
repli. Il faut le corriger pour la documentation.

### L'état des deux dépôts

| | `climbcontest-core` (ex-`climbContestServer`) | `ClimbContest` (Android) |
| --- | --- | --- |
| Visibilité | **PUBLIC** | **PUBLIC** |
| Branche par défaut | `master` | `main` |
| Branches | **7** au départ, **2** après ménage | propre |
| Étiquettes | à jour depuis le gel (`V2.1.1` local) | à jour (`V3.1.4`) |
| Emplacement local | `annonayEscalade/climbcontest-core/` | `annonayEscalade/climbcontest-android/` |

---

## Ce que je recommande : pas de monorepo

Je l'avais proposé dans la feuille de route (décision D3). **Après avoir regardé
tes autres projets, je change d'avis.**

### Pourquoi

1. **Tout ton écosystème est un dépôt par livrable**, chacun avec son
   `CHANGELOG.md` et son `release.sh` : guestFlow, solioMap, chaque plugin Sowel.
   Un monorepo serait l'exception, pas la règle.
2. **La spec 001 construit une chaîne de release déclenchée par les étiquettes
   `vX.Y.Z`.** Dans un monorepo contenant aussi l'app Android, il faudrait des
   préfixes d'étiquette et des filtres de chemin — de la complexité ajoutée à
   précisément la pièce qu'on construit en premier.
3. **Les étiquettes entreraient en collision** : l'app Android en a déjà 13
   (`V3.1.2`, `V3.1.3`, `V3.1.4`…), le backend en a 6.
4. **Sowel montre le bon modèle** : `sowel-core` porte `specs/` et `docs/` pour
   des fonctionnalités qui vivent dans d'autres dépôts. Ça marche.

### Le modèle retenu : un dépôt pivot

```
computingify/climbcontest-core           ← le pivot
├── CLAUDE.md                            point d'entrée agent
├── CHANGELOG.md                         (spec 001)
├── docs/                                état des lieux, contraintes, classeur…
├── specs/                               001, 002, 003…
├── tools/                               dump_sheet, verify_ranking…
├── fixtures/                            jeu de test nov 2025 (anonymisé)
├── climb_contest/ ou src/               le backend
├── deployment/                          service systemd, install.sh (spec 001)
└── .github/workflows/release.yml        (spec 001)

computingify/ClimbContest                ← l'app Android, inchangée
```

Les specs couvrent aussi l'app Android et la future PWA, même si leur code vit
ailleurs. C'est exactement ce que fait `sowel-core`.

---

## Ce qu'il faut faire — le nécessaire

| # | Action | Pourquoi |
| --- | --- | --- |
| **P1** | Déplacer `CLAUDE.md`, `docs/`, `specs/`, `tools/`, `fixtures/` dans le dépôt pivot et committer | Le travail n'est nulle part |
| **P2** | Compléter le `.gitignore` : `archive/`, `*.db`, `dump_*.json`, `*.bundle` | Éviter de committer des données personnelles ou des secrets |
| **P3** | Sortir les scripts de charge de `tests/` vers `tools/load/`, et les repointer sur une cible de recette | Risque R11 : ils écrivent dans le vrai classeur |
| **P4** | Supprimer les 5 branches mortes, **garder `feature/ResultAlgorithm`** | Elle est la matière première de la spec 004 |
| **P5** | Pousser l'étiquette `V2.1.1` créée lors du gel | Elle n'existe qu'en local |

### Détail P4 — les branches

| Branche | Sort |
| --- | --- |
| `feature/ResultAlgorithm` | **conservée** — matière de la spec 004 |
| `bugfix/MissingSuccess` | supprimée — déjà fusionnée dans `master` |
| `feature/FillLocalBdWithGSheet` | supprimée — étape intermédiaire, reprise dans `ResultAlgorithm` |
| `feature/UnitTest`, `feature/TryUT` | supprimées — deux essais de la même exploration |
| `tmp` | supprimée |

Rien n'est perdu : les *bundles* du gel de repli contiennent **toutes** les
branches (`git bundle create … --all`).

---

## Ce qui est optionnel — à toi de trancher

| # | Action | Pour | Contre |
| --- | --- | --- | --- |
| **O1** | Renommer le dépôt `climbContestServer` → `climbcontest-core` | Il ne contient plus seulement le serveur mais les specs de tout le projet | Casse l'URL dans les scripts de déploiement hérités. GitHub redirige les anciennes URL |
| **O2** | Renommer `master` → `main` | Cohérent avec l'app Android du même projet | Casse `deploy_RPi.sh` (`git reset --hard origin/master`), remplacé aussi. Tes autres dépôts sont mixtes : pas de convention forte |
| **O3** | Déplacer l'app Android dans le workspace | App et backend côte à côte, une seule session pour une évolution qui touche les deux | Il faut rouvrir le projet depuis le nouveau chemin dans Android Studio |
| **O4** | Ajouter un garde-fou anti-secret (`.gitleaks.toml` + hook), comme `sowel-core` | Le dépôt est **public**, et l'incident HelloAsso montre que ça arrive | Une pièce de plus à maintenir |

Mon avis : **O3 et O4 valent le coup**, O1 est confortable, O2 n'apporte presque
rien.

---

## Ce que je recommande d'écarter

- **Le monorepo** (décision D3), pour les quatre raisons ci-dessus.
- **Passer les dépôts en privé.** Ils sont publics, comme guestFlow. Ça a même
  un bénéfice inattendu, voir ci-dessous.

---

## Le dépôt public simplifie la spec 001

Les assets d'une release **publique** se téléchargent **sans authentification**.

Conséquence directe : l'agent de tirage sur la VM **n'a besoin d'aucun jeton
GitHub**. C'est un secret de moins sur la machine, là où solio-map (dépôt privé)
doit porter un PAT.

J'ai mis la spec 001 à jour : le script gère les deux cas — jeton présent, il
l'utilise ; jeton absent, il tire en anonyme. Si le dépôt devenait privé un jour,
il suffit de déposer le PAT.

La contrepartie est la règle inverse, et elle est stricte : **aucun secret ne
peut jamais être committé**. D'où l'intérêt de O4.

---

## L'ordre

```
P1 → P2 → P3 → P4 → P5     (le nécessaire, ~30 min)
puis O3, O4 si tu les valides
puis spec 001 IT1
```

P1 en premier : tant que la documentation n'est pas versionnée, tout le reste se
fait sans filet.


---

## Journal d'exécution — 28 août 2026

| | Action | Résultat |
| --- | --- | --- |
| **O1** | Renommage du dépôt | ⚠️ **`climbcontest` était déjà pris** : GitHub ignore la casse, et `computingify/ClimbContest` (l'app Android) occupe ce nom. Renommé en **`climbcontest-core`**, sur le modèle de `sowel-core` |
| **P5** | Étiquette `V2.1.1` | poussée sur GitHub |
| **P4** | Ménage des branches | 5 supprimées, `feature/ResultAlgorithm` conservée. **Les 4 branches non fusionnées ont d'abord été étiquetées** `archive/…` et poussées : leurs commits restent joignables sur GitHub, pas seulement dans le bundle local |
| **P1** | Documentation versionnée | `CLAUDE.md`, `docs/`, `specs/`, `tools/`, `fixtures/` déplacés dans le dépôt |
| **P2** | `.gitignore` | `archive/`, `*.bundle`, `*.apk`, `*.aab`, `dump_*.json`, `*.db`, secrets |
| **P3** | Scripts de charge | déplacés en `tools/load/`, renommés `charge_*.py`, et **ils refusent désormais de démarrer** sans `CLIMBCONTEST_LOAD_URL` explicite (risque R11 neutralisé) |
| **O3** | App Android | déplacée en `annonayEscalade/climbcontest-android/` ; build `assembleDebug` vérifié vert depuis le nouveau chemin |
| **O4** | Garde-fou anti-secret | `.gitleaks.toml` + hook `pre-commit` + `scripts/hooks/install.sh`. `gitleaks` installé. **Scan des 100 commits d'historique : aucune fuite** |
| **O2** | `master` → `main` | non retenu |

### Les étiquettes d'archive

Les branches supprimées restent récupérables :

```bash
git checkout archive/feature-FillLocalBdWithGSheet   # 0d46171
git checkout archive/feature-UnitTest                # 06752e5
git checkout archive/feature-TryUT                   # d9820d3
git checkout archive/tmp                             # eb629b8
```

`bugfix/MissingSuccess` n'a pas d'étiquette : elle était déjà fusionnée dans
`master`.

### Le piège de la casse, à retenir

macOS et GitHub traitent tous deux les noms **sans distinction de casse**. C'est
pour ça que :

- le dépôt pivot ne peut pas s'appeler `climbcontest` ;
- le dossier local de l'app Android s'appelle `climbcontest-android` et non
  `ClimbContest`, qui entrerait en collision avec `climbcontest-core`… et
  surtout aurait empêché les deux dossiers de coexister si le pivot avait gardé
  un nom proche.

### Ce qui reste à ta main

- Copier `archive/gel-2026-08/secrets/` **hors de ce Mac** (voir
  [plan-de-repli.md](plan-de-repli.md)).
- Rouvrir le projet Android dans Android Studio depuis
  `~/Documents/workspace/annonayEscalade/climbcontest-android`.
- `brew install gitleaks` est fait sur ce Mac ; à refaire sur toute autre machine
  qui committe dans ce dépôt, puis `./scripts/hooks/install.sh`.
