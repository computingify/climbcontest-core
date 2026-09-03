# Plan — spec 038

> Rien ne se code avant la porte 2. Ce plan décrit l'ordre **si** D1→D4 sont
> tranchées comme recommandé : A d'abord, puis B, puis C dans une PR à part.

## 1. Étapes

### Lot 1 — le pansement (variante A), livrable seul

- [ ] `.gitattributes` : les deux fichiers, nommés un par un
- [ ] `tests/test_specs_index.py` : numéros triés, uniques, tableau bien formé
- [ ] Un test qui rejoue les **scénarios 2 et 5** de la spec dans un dépôt git
      jetable, et vérifie que le garde les attrape
- [ ] Un test qui vérifie qu'un fichier de prose **quelconque** conflite
      toujours (critère C6)

### Lot 2 — la ligne vit avec sa spec (variante B)

- [ ] `tools/index_specs.py` : lit les `resume.md`, écrit l'index
- [ ] Migration : les 34 lignes actuelles deviennent 34 `resume.md`
      — **par extraction automatique**, pas à la main
- [ ] `docs/specs-index.md` régénéré, puis **comparé texte à texte** à
      l'ancien : la migration est bonne si le diff est vide (critère C7)
- [ ] Le gabarit des deux sections stables
- [ ] Le test C4 : l'index committé est ce que l'outil produit
- [ ] `docs/workflow.md` : une spec nouvelle écrit son `resume.md`

### Lot 3 — les fragments de changelog (variante C), **PR séparée**

- [ ] `tools/assembler_changelog.py`
- [ ] `changelog.d/` avec son `README.md` qui donne le format
- [ ] Le contrôle de CI, **en avertissement d'abord**
- [ ] `docs/workflow.md` et le geste de release
- [ ] `CHANGELOG.md` sort de `.gitattributes`

## 2. Plan de test

### Nominal

| Module | Scénario | Attendu |
| --- | --- | --- |
| `.gitattributes` | Deux branches ajoutent chacune sa ligne d'index | Fusion **sans conflit**, les deux lignes présentes |
| `.gitattributes` | Deux branches créent la même rubrique de changelog | **Une** rubrique, les deux entrées dessous |
| `.gitattributes` | L'une corrige une ligne, l'autre en ajoute une | La correction tient, l'ajout aussi |
| `test_specs_index` | L'index tel qu'il est aujourd'hui | Vert — le garde ne casse pas l'existant |
| `index_specs.py` | Les 34 `resume.md` migrés | L'index produit est **identique** à l'actuel, octet pour octet |
| `index_specs.py` | Un `resume.md` ajouté | Une ligne de plus, à sa place dans l'ordre |

### Cas limites

| Module | Scénario | Attendu |
| --- | --- | --- |
| `test_specs_index` | Numéros dans le désordre (**scénario 2**) | **Rouge**, et le message nomme les deux numéros |
| `test_specs_index` | Deux fois le même numéro (**scénario 5**) | **Rouge**, et le message nomme le doublon |
| `test_specs_index` | Une ligne dont le lien pointe sur un dossier absent | Rouge |
| `.gitattributes` | Deux branches réécrivent le même paragraphe d'un `spec.md` | **Conflit**, comme avant (critère C6) |
| `index_specs.py` | Un `resume.md` sans ligne `statut:` | Refus explicite, pas une colonne vide |
| `index_specs.py` | Un numéro de titre ≠ numéro du dossier | Refus, et le message donne les deux |
| `index_specs.py` | Un résumé qui contient un `\|` | Échappé — le tableau ne se casse pas |
| `index_specs.py` | Les trous (008, 009 réservées ; 030 non mergée) | Recopiés du gabarit, aucun dossier cherché |
| `assembler_changelog` | Deux fragments, même rubrique | Une rubrique, deux entrées, dans l'ordre des numéros de PR |
| `assembler_changelog` | Dossier de fragments vide à la release | Refus explicite : une release sans changelog est une erreur |

### Ce qu'on vérifie en cassant

Un test qui passe ne prouve rien tant qu'on ne l'a pas vu tomber. Chacun de ces
gardes est vérifié en cassant ce qu'il surveille :

| Garde | Ce qu'on casse pour le voir tomber |
| --- | --- |
| Numéros triés | On intervertit deux lignes de l'index |
| Numéros uniques | On duplique la ligne 033 |
| Index = produit de l'outil | On modifie l'index à la main sans toucher aux `resume.md` |
| C6, les vrais conflits survivent | On tente une fusion croisée sur un `spec.md` |

## 3. Ce que ce plan ne fait pas

- Il ne touche **aucun** fichier de `climbcontest/`. Aucun risque pour la
  production ; la CI reste le seul juge.
- Il ne change pas l'ordre de merge des PR ni la stratégie squash.
- Il ne prétend pas supprimer les conflits de code. Les trois vrais conflits du
  03/09 se seraient déclenchés à l'identique — et c'est voulu.
