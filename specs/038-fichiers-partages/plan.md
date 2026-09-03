# Plan — spec 038

> Les décisions sont prises (spec.md, section 5). Trois lots, dont **un seul**
> demande une fenêtre sans PR ouverte.

## 1. Étapes

### Lot A — la numérotation · mergeable à tout moment

Que des fichiers neufs : rien de partagé n'est réécrit. Il peut donc partir
pendant qu'il reste des PR en cours, et il protège la suite pendant que le
lot B est en revue.

- [ ] `tools/numero_de_spec.py` — alloue en lisant master, les branches
      **distantes et locales**, les PR ouvertes, et les numéros réservés
- [ ] `--reserver <slug>` — pousse aussitôt une branche vide `spec/NNN-slug`
- [ ] `tests/test_numerotation_specs.py` — pas de doublon, numéro et slug
      concordent avec le dossier
- [ ] `docs/workflow.md` — réserver son numéro devient le premier geste

### Lot B — les fragments · **fenêtre sans PR ouverte**

Le changelog et l'index migrent **ensemble**, en une seule PR. Les séparer
doublerait la fenêtre : chacun réécrit un fichier partagé de bout en bout, et
toute PR ouverte pendant ce temps entrerait en conflit massif.

⚠️ **Condition de départ** : la release est publiée, `## [Non publié]` est vide,
et `gh pr list` ne renvoie rien.

- [ ] `changelog.d/README.md` — le format d'un fragment
- [ ] `scripts/assembler_changelog.py` — groupe, écrit la section, supprime les
      fragments, laisse le résultat **non committé** pour relecture
- [ ] `scripts/release.sh` — étape 0 : refuse de taguer s'il reste des fragments
- [ ] `CHANGELOG.md` — `## [Non publié]` retiré
- [ ] `tools/index_specs.py` et `docs/specs-index.tpl.md`
- [ ] Migration : **chaque ligne** de l'index devient un `resume.md`, par
      extraction automatique, jamais à la main. Le nombre n'est pas figé ici :
      il dépend des specs qui auront atterri d'ici là
- [ ] L'index régénéré est **comparé texte à texte** à l'ancien : la migration
      est bonne si le diff est vide
- [ ] `.github/workflows/tests.yml` — le job `index` (D5) et le garde du
      fragment manquant
- [ ] `CLAUDE.md` et `docs/workflow.md` — le nouveau geste

### Lot C — le verrou sur l'index · juste après B

- [ ] `.github/workflows/tests.yml` — une PR dont le diff touche
      `docs/specs-index.md` est refusée, avec un message qui renvoie au
      `resume.md` de la spec

⚠️ Séparé de B **parce que le garde tourne sur la PR qui le porte** : dans B, il
échouerait sur son propre diff. B est donc la dernière PR autorisée à toucher
l'index à la main.

## 2. Plan de test

### Nominal

| Module | Scénario | Attendu |
| --- | --- | --- |
| bout en bout | Deux branches ajoutent chacune sa spec | Fusion **sans conflit** — aucune ne touche l'index |
| bout en bout | Deux branches déposent chacune son fragment | Fusion **sans conflit** — deux fichiers distincts |
| `index_specs.py` | Tous les `resume.md` migrés | L'index produit est **identique** à l'actuel, octet pour octet |
| `index_specs.py` | Un `resume.md` ajouté | Une ligne de plus, à sa place dans l'ordre des numéros |
| job `index` | Une spec est mergée sur master | L'index gagne sa ligne, poussé par le robot, sans qu'aucune PR ne l'ait touché |
| `assembler_changelog` | Trois fragments, deux rubriques | Une section de version, groupée, fragments supprimés |
| `numero_de_spec` | Le dépôt tel qu'il est | Rend un numéro qu'aucune branche — **même locale** — n'utilise |

### Cas limites

| Module | Scénario | Attendu |
| --- | --- | --- |
| `numero_de_spec` | Un numéro pris sur une branche **jamais poussée** (cas 030) | Il est vu, et n'est pas proposé |
| `test_specs_index` | Deux dossiers `specs/NNN-*` de même numéro | **Rouge**, le message nomme le doublon |
| `test_specs_index` | Un numéro de titre ≠ numéro du dossier | **Rouge**, le message donne les deux valeurs |
| `test_specs_index` | Un `resume.md` sans ligne `statut:` | Refus explicite, pas une colonne vide |
| `index_specs.py` | Un résumé qui contient un `\|` | Échappé — le tableau ne se casse pas |
| `index_specs.py` | Les trous (008, 009 réservées ; 030 non mergée) | Recopiés du gabarit, aucun dossier cherché en face |
| `assembler_changelog` | Dossier de fragments vide à la release | Refus explicite : une release sans changelog est une erreur |
| `assembler_changelog` | Un fragment avec `rubrique: Bidule` | Refus, et les rubriques admises sont listées |
| `release.sh` | Taguer alors que `changelog.d/` n'est pas vide | Refus à l'étape 0 |
| garde du lot C | Une PR modifie `docs/specs-index.md` | Refusée, le message renvoie au `resume.md` |
| prose du dépôt | Deux branches réécrivent le même paragraphe d'un `spec.md` | **Conflit**, comme avant (critère C7) |

### Ce qu'on vérifie en cassant

Un test qui passe ne prouve rien tant qu'on ne l'a pas vu tomber. Chacun de ces
gardes est vérifié en cassant ce qu'il surveille :

| Garde | Ce qu'on casse pour le voir tomber |
| --- | --- |
| Numéros uniques | On duplique le dossier `specs/033-*` |
| Numéro ↔ dossier | On renomme un dossier sans son `resume.md` |
| Index = produit de l'outil | On modifie l'index à la main |
| Fragment obligatoire | On touche `climbcontest/` sans déposer de fragment |
| Release complète | On tague avec `changelog.d/` non vide |
| C7, les vrais conflits survivent | On tente une fusion croisée sur un `spec.md` |

## 3. Ce que ce plan ne fait pas

- Il ne touche **aucun** fichier de `climbcontest/`. Aucun risque pour la
  production ; la CI reste le seul juge.
- Il ne change pas l'ordre de merge des PR ni la stratégie squash.
- Il ne pose **aucun** `merge=union` : voir architecture.md, section 5.
- Il ne prétend pas supprimer les conflits de code. Les trois vrais conflits du
  03/09 se seraient déclenchés à l'identique — et c'est voulu.
