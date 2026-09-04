# Spec 043 — architecture

## 1. Rien ne bouge côté données

Aucune colonne, aucune migration, aucun champ de plus dans une réponse JSON. La
charge de `/api/public/classement` est **identique champ pour champ** à celle
d'avant la spec (critère A12). C'est le point qui rend cette spec sûre : elle
n'ajoute que des en-têtes, un pied de page et deux documents.

## 2. La non-indexation, en trois poses

| Surface | Où ça se pose | Pourquoi là |
| --- | --- | --- |
| `GET /robots.txt` | nouvelle route dans `routes/pages.py` | une seule ligne de vérité, dans le dépôt |
| `<meta name="robots">` | `templates/resultats.html`, `admin.html`, `juge.html` | ce que lit un moteur qui a déjà la page |
| `X-Robots-Tag: noindex` | `@bp.after_request` sur le blueprint `public` | ce que lit un moteur sur une réponse **JSON**, où aucune balise n'existe |

```python
# routes/public.py
@bp.after_request
def _pas_d_indexation(reponse):
    """Une reponse JSON n'a pas de balise meta : l'en-tete est le seul canal.

    Pose sur le BLUEPRINT et non sur l'application : /admin et /api/v2 ne sont
    pas concernes, et un crochet global finirait par etre lu comme une regle
    generale qu'il n'est pas.
    """
    reponse.headers["X-Robots-Tag"] = "noindex"
    return reponse
```

⚠️ `after_request` de blueprint s'exécute **aussi sur les réponses d'erreur**
produites par les vues (`404` d'un groupe inconnu, `409` d'une compétition
absente) — c'est voulu, et c'est le critère A3. Il ne s'exécute pas sur une
exception non gérée ; il n'y en a pas sur ces routes.

⚠️ **L'en-tête doit être dans la réponse que Caddy met en cache.** Posé par
l'application, il l'est. Un `header` ajouté côté proxy serait, lui, appliqué à
la sortie du cache — même effet, mais dans un fichier qui dérive et qu'aucun
test ne lit. La règle est celle de l'étude : le proxy peut doubler, il ne porte
pas seul.

## 3. La mention

### Placement

```html
<main>
  …
  <div id="defile">
    <div id="liste"></div>
    <footer id="mentions" class="hors-mur">…</footer>   ← ici
  </div>
</main>
```

⚠️ **Pas après `<main>`.** `body` est une colonne flex, `main` vaut `flex: 1`,
et en mode téléphone `#defile` passe en `overflow: visible` : la liste déborde
de la boîte de `main`. Un pied posé après `main` se rend à ~790 px du haut,
sous le classement qui le recouvre. Constaté en injectant les deux placements
dans la page réelle avant d'écrire cette spec.

### Style

Il reprend les jetons de la page — `--encre2` pour le texte, `--trait` pour le
filet supérieur. Aucune couleur nouvelle.

```css
#mentions { padding: 14px 16px 22px; text-align: center;
            font-size: 0.78rem; color: var(--encre2);
            border-top: 1px solid var(--trait); }
body.mur #mentions { display: none; }
```

La classe `hors-mur` existe déjà dans ce gabarit pour les commandes ; la règle
`body.mur … { display: none }` est le motif en place, repris tel quel.

## 4. La page de confidentialité

- Route : `GET /confidentialite` dans `routes/pages.py`, sans session — comme
  `/` et `/console`.
- Gabarit : `templates/confidentialite.html`, autonome, thème clair/sombre par
  `prefers-color-scheme`, sans dépendance extérieure.
- Ancre `#opposition` sur la section visée par le second lien.
- Elle porte elle aussi la balise `noindex` : c'est une page de service, pas un
  contenu à référencer.

## 5. Le registre

`docs/registre-des-traitements.md`, un tableau par traitement. Aucun code, aucun
test — c'est un document, et le seul contrôle utile est qu'il existe et qu'il
est à jour (critère A11).

## 6. Fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/routes/public.py` | `after_request` d'en-tête |
| `climbcontest/routes/pages.py` | routes `/robots.txt` et `/confidentialite` |
| `climbcontest/templates/resultats.html` | balise `noindex` + pied `#mentions` + CSS |
| `climbcontest/templates/admin.html`, `juge.html` | balise `noindex` |
| `climbcontest/templates/confidentialite.html` | **nouveau** |
| `docs/registre-des-traitements.md` | **nouveau** |
| `tests/test_non_indexation.py` | **nouveau** |
| `CHANGELOG.md` / `changelog.d/` | section « Non publié » |

Aucun de ces fichiers n'est touché par les deux autres sessions en cours
(spec 008 sur `models.py` et l'import HelloAsso ; PR #122 sur `tests/`). Le
seul point de contact possible est `docs/specs-index.md`, où la ligne 043 sera
ajoutée au dernier moment.
