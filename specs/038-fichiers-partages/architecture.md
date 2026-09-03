# Architecture — spec 038

> Les décisions D1→D5 sont prises (voir [spec.md](spec.md), section 5). Ce
> document décrit la construction **retenue** : plus aucun `merge=union`, plus
> aucun fichier partagé écrit pendant le développement.

## 1. Ce qui existe déjà, et qu'on ne refait pas

- `docs/specs-index.md`, **82 lignes**, trois sections : le tableau des specs
  (une ligne par spec, 35 avec la 038), les « specs pressenties » (008 et 009,
  réservées sans dossier), et « historique pré-specs » (de la prose stable).
  **Seule la première section bouge** — les deux autres n'ont pas conflité une
  seule fois aujourd'hui.
- Le dépôt **n'a pas de `.gitattributes`**, et n'en aura pas : voir section 5.
- Aucun test ne lit `docs/specs-index.md` aujourd'hui : rien ne garde ce
  fichier.
- `tools/` contient déjà des outils Python autonomes en bibliothèque standard
  (`verify_ranking.py`, `extract_fixture.py`). Un générateur d'index s'y range
  sans rien introduire.
- La convention du dépôt pour un contrôle croisé existe déjà et sert de modèle :
  la spec 034 fait lire `poste.js` par un test Python pour le comparer à
  `fiches.PREFIXE_QR_POSTE`. Le test « l'index est bien ce que l'outil produit »
  est le même geste.

## 2. Fichiers touchés, par lot

### Lot A — la numérotation (additif, mergeable à tout moment)

| Fichier | Ce qui s'y passe |
| --- | --- |
| `tools/numero_de_spec.py` | **créé** — alloue en lisant master, les branches **distantes et locales**, les PR ouvertes et les numéros réservés ; `--reserver <slug>` pousse aussitôt une branche vide `spec/NNN-slug` |
| `tests/test_numerotation_specs.py` | **créé** — pas de doublon, numéro et slug concordent avec le dossier |
| `docs/workflow.md` | **étendu** — réserver son numéro devient le premier geste, avant d'écrire la spec |

### Lot B — les fragments (une seule PR, fenêtre sans PR ouverte)

| Fichier | Ce qui s'y passe |
| --- | --- |
| `changelog.d/README.md` | **créé** — le format d'un fragment |
| `scripts/assembler_changelog.py` | **créé** — groupe par rubrique, écrit la section de version, supprime les fragments |
| `scripts/release.sh` | **étape 0 ajoutée** — refuse de taguer s'il reste des fragments |
| `CHANGELOG.md` | `## [Non publié]` **retiré** ; tout l'historique publié reste intact |
| `specs/NNN-*/resume.md` | **créés ×35**, par extraction automatique de l'index actuel |
| `tools/index_specs.py` | **créé** — lit les `resume.md`, écrit l'index |
| `docs/specs-index.tpl.md` | **créé** — l'en-tête et les deux sections stables |
| `docs/specs-index.md` | **devient un produit**, avec un en-tête qui le dit |
| `.github/workflows/tests.yml` | **étendu** — le job `index`, plus le garde du fragment manquant |
| `CLAUDE.md`, `docs/workflow.md` | le nouveau geste, des deux côtés |

### Lot C — le verrou sur l'index (juste après B)

| Fichier | Ce qui s'y passe |
| --- | --- |
| `.github/workflows/tests.yml` | **étendu** — une PR dont le diff touche `docs/specs-index.md` est refusée |

⚠️ **Pourquoi C ne peut pas voyager dans B.** Le garde tourne sur la PR qui le
porte. Or la PR du lot B réécrit l'index de bout en bout : elle échouerait sur
son propre garde. C part donc juste après, et B est la **dernière** PR autorisée
à toucher ce fichier à la main.

## 3. Le job qui régénère l'index (D5)

Un second job dans `tests.yml`, qui se déclenche déjà sur
`push: branches: [master]` — pas de nouveau fichier de workflow.

```yaml
  index:
    needs: tests
    if: github.ref == 'refs/heads/master'
    runs-on: ubuntu-latest
    permissions:
      contents: write        # au JOB, pas au workflow
    steps:
      - uses: actions/checkout@v4
      - run: python3 tools/index_specs.py --ecrire
      - name: Publier si l'index a bouge
        run: |
          git diff --quiet docs/specs-index.md && exit 0
          git config user.name  "climbcontest-bot"
          git config user.email "bot@users.noreply.github.com"
          git commit -m "docs(specs): index regenere [skip ci]" docs/specs-index.md
          git push
```

Trois points vérifiés le 03/09, pas supposés :

| Question | Vérifié |
| --- | --- |
| La CI peut-elle pousser sur master ? | **Oui** — `master` n'est pas une branche protégée. Si elle le devient, il faudra une exception pour le robot. |
| Le jeton peut-il écrire ? | Pas par défaut : le dépôt est réglé sur `read`. On le déclare **au job**, comme `release.yml` le fait déjà au workflow — le job des tests, lui, reste en lecture seule, y compris sur les PR. |
| Le robot boucle-t-il ? | **Non** — un push fait avec le `GITHUB_TOKEN` ne déclenche pas de nouveau workflow. `[skip ci]` n'est qu'une ceinture de plus. |

## 4. Le format de `resume.md`

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

## 5. Ce qu'on ne fait PAS : `merge=union`

Il était la variante A, et il est écarté. Non pas parce qu'il ne marche pas —
les mesures de [spec.md](spec.md) section 3 montrent qu'il aurait absorbé trois
scénarios sur cinq — mais parce qu'il aurait laissé le scénario 5 comme piège
dormant : deux branches qui modifient la même ligne produisent deux lignes, sans
un mot.

⚠️ Et si l'idée revient un jour, la forme à ne **jamais** prendre est le motif :
un `*.md merge=union` couvrirait `specs/*/spec.md`, `docs/workflow.md` et une
bonne part des 118 fichiers `.md` du dépôt. Deux branches qui réécrivent le même
paragraphe le verraient sortir **en double**, sans conflit et sans un mot. Le
critère C7 le vérifie : un fichier de prose quelconque doit **toujours**
conflire.

## 6. Ce qui ne doit pas casser

- **`CLAUDE.md` pointe sur `docs/specs-index.md`.** Le chemin ne bouge pas, et
  l'index reste committé — donc lisible sur GitHub sans outil. C'est la raison
  d'être du job de CI (D5) : une session qui démarre ne doit jamais lire une
  liste périmée.
- **Les liens relatifs `../specs/XXX-nom/`** de chaque ligne : ils sont écrits
  depuis `docs/`, et le générateur doit les produire à l'identique. Le critère
  C8 les compare texte à texte.
- **Les deux sections stables** (specs pressenties, historique) sont recopiées
  telles quelles par le générateur, depuis un gabarit — elles ne se déduisent
  d'aucun dossier.
- **Le geste de release.** `release.sh` gagne une étape 0, mais son étape 4 et
  `scripts/extract_changelog.py` ne bougent pas : `release.yml` et la carte
  « Version du serveur » de la console (spec 031) ne voient aucune différence.
- **La CI ne doit pas devenir bloquante sur un oubli de fragment** sans qu'Adrien
  l'ait voulu : le contrôle commence en **avertissement**, et ne passe bloquant
  que sur sa demande.
