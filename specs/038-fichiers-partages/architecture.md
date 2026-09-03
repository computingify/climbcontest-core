# Architecture — spec 038

> Rappel : cette spec attend une décision (D1→D4). Ce document décrit **comment
> chaque variante se construirait**, pas ce qui est décidé.

## 1. Ce qui existe déjà, et qu'on ne refait pas

- `docs/specs-index.md`, **82 lignes**, trois sections : le tableau des specs
  (une ligne par spec, 34 aujourd'hui), les « specs pressenties » (008 et 009,
  réservées sans dossier), et « historique pré-specs » (de la prose stable).
  **Seule la première section bouge** — les deux autres n'ont pas conflité une
  seule fois aujourd'hui.
- Le dépôt **n'a pas de `.gitattributes`**. Il serait créé par cette spec.
- Aucun test ne lit `docs/specs-index.md` aujourd'hui : rien ne garde ce
  fichier.
- `tools/` contient déjà des outils Python autonomes en bibliothèque standard
  (`verify_ranking.py`, `extract_fixture.py`). Un générateur d'index s'y range
  sans rien introduire.
- La convention du dépôt pour un contrôle croisé existe déjà et sert de modèle :
  la spec 034 fait lire `poste.js` par un test Python pour le comparer à
  `fiches.PREFIXE_QR_POSTE`. Le test « l'index est bien ce que l'outil produit »
  est le même geste.

## 2. Fichiers touchés, quand le code viendra

### Variante A — `merge=union` plus un garde

| Fichier | Ce qui s'y passe |
| --- | --- |
| `.gitattributes` | **créé** — deux lignes, `docs/specs-index.md` et `CHANGELOG.md` |
| `tests/test_specs_index.py` | **créé** — numéros triés, uniques, et syntaxe du tableau |

### Variante B — la ligne vit avec sa spec

| Fichier | Ce qui s'y passe |
| --- | --- |
| `specs/XXX-nom/resume.md` | **créés, 34 fois** — la ligne de chaque spec, extraite de l'index actuel |
| `tools/index_specs.py` | **créé** — lit les `resume.md`, écrit l'index |
| `docs/specs-index.md` | **devient un produit** — même contenu, même ordre, un en-tête qui dit qu'il se régénère |
| `tests/test_specs_index.py` | **étendu** — l'index committé est exactement ce que l'outil produit |

### Variante C — un fragment de changelog par PR

| Fichier | Ce qui s'y passe |
| --- | --- |
| `changelog.d/*.md` | **créés au fil des PR** — un fragment par PR, supprimés à la release |
| `tools/assembler_changelog.py` | **créé** — assemble sous un titre de version, vide le dossier |
| `.github/workflows/tests.yml` | **étendu** — une PR qui touche `climbcontest/` sans fragment est signalée |
| `docs/workflow.md` | **étendu** — le geste de release gagne une commande |

## 3. Le format de `resume.md` (variante B)

Un fichier court, lisible seul, sans dépendance à un analyseur YAML — la
bibliothèque standard n'en a pas, et le dépôt s'interdit les installations pour
ses outils.

```markdown
# 036 — avancement-par-zone
statut: 🟡 **spec écrite AVANT le code** (03/09)

Sur le plan du mur de la fiche, chaque zone où le grimpeur a des blocs de son
circuit porte son avancement — « 1/4 », blocs validés sur blocs de son circuit
dans cette zone. […]
```

Trois champs, et rien de plus : le **titre** donne le numéro et le nom, la ligne
`statut:` donne la colonne Statut, le **corps** donne la colonne Résumé. Le
générateur les replie en une ligne de tableau, en échappant les `|`.

⚠️ **Le numéro vient du titre, pas du nom du dossier.** Les deux doivent
concorder, et le test le vérifie : un dossier renommé sans son `resume.md`
sortirait sinon un index qui ne pointe nulle part.

## 4. Ce que `.gitattributes` doit nommer — et surtout ne pas nommer

```
docs/specs-index.md merge=union
CHANGELOG.md        merge=union
```

⚠️ **Deux fichiers, nommés un par un. Jamais de motif.** Un `*.md merge=union`
couvrirait `specs/*/spec.md`, `docs/workflow.md` et une bonne part des 118
fichiers `.md` du dépôt : deux branches qui réécrivent le même paragraphe le verraient
alors sortir **en double**, sans conflit et sans un mot. Le critère C6 existe
pour ça, et il se teste : un fichier de prose quelconque doit **toujours**
conflire.

Si la variante C est retenue, `CHANGELOG.md` sort de cette liste — il ne serait
plus écrit que par la release, donc par une seule main à la fois.

## 5. Ce qui ne doit pas casser

- **`CLAUDE.md` pointe sur `docs/specs-index.md`.** Le chemin ne bouge pas, quelle
  que soit la variante. Un index généré reste committé, et lisible sur GitHub.
- **Les liens relatifs `../specs/XXX-nom/`** de chaque ligne : ils sont écrits
  depuis `docs/`, et le générateur doit les produire à l'identique. Le critère
  C7 les compare texte à texte.
- **Les deux sections stables** (specs pressenties, historique) sont recopiées
  telles quelles par le générateur, depuis un gabarit — elles ne se déduisent
  d'aucun dossier.
- **Le geste de release** (spec 031 : le corps de la release GitHub est la
  section du changelog) ne change pas en A, change en C. C'est l'objet de D2.
- **La CI ne doit pas devenir bloquante sur un oubli de fragment** sans qu'Adrien
  l'ait voulu : en C, le contrôle commence en **avertissement**.
