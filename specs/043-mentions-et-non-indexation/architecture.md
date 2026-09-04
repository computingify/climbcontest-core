# Spec 043 — architecture

## 1. Une seule colonne, et pas par un fichier `.sql`

```python
# schema.py — COLONNES_AJOUTEES
"participant": {
    "publication_refusee": "BOOLEAN NOT NULL DEFAULT 0",
},
```

⚠️ **Correction apportée pendant l'implémentation.** Cette spec prévoyait
d'abord `migrations/001_publication_refusee.sql`. C'était faux, et
`schema.py` le dit déjà en toutes lettres :

> Un fichier `.sql` ne conviendrait pas ici : le lanceur de migrations joue
> chaque fichier une fois, mais sur une base NEUVE `create_all` a déjà créé la
> colonne, et l'ALTER échouerait sur « duplicate column ».

Le défaut aurait été **vert là où on regarde et rouge là où on ne regarde
pas** : sur la VM de production, la table existe sans la colonne et l'`ALTER`
serait passé ; sur une base neuve — un poste de développement, la CI, une VM
réinstallée — `create_all()` crée la colonne d'après `models.py`, l'`ALTER`
lève, et **l'application ne démarre pas** (aucun `except` n'entoure la boucle
des migrations). Constaté au premier lancement des tests.

`COLONNES_AJOUTEES` lit `PRAGMA table_info` et n'ajoute que ce qui manque :
idempotent dans les deux sens. C'est déjà le chemin qu'a pris la spec 019 pour
`bloc.couleur_prises`.

⚠️ **`NOT NULL DEFAULT 0` et non `NULL`.** Un booléen à trois états
(`vrai`/`faux`/`inconnu`) obligerait chaque lecture à décider ce que vaut
`NULL`, et deux lectures finiraient par en décider différemment. Pour une
opposition RGPD, « personne ne s'est opposé » et « on ne sait pas » doivent être
la **même chose** — sinon il faudrait interpréter un `NULL` le jour d'un
contrôle. Les lignes existantes passent à `0`, c'est-à-dire l'état d'avant.

**La forme de la charge publique ne change pas** : aucun champ de plus, aucun
champ de moins (critère A12). Seule la *valeur* de `nom` change, pour les
participants concernés.

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

## 4. L'anonymisation, en un seul endroit

```python
# classement_service.py
def charge_publique(comp, forcer=False, anonymiser=True):
    ...
    noms = {
        p.id: {
            "nom": f"Dossard {p.dossard}" if (anonymiser and p.publication_refusee)
                   else p.nom_complet,
            "club": p.club, "categorie": p.categorie,
        }
        for p in Participant.query.filter_by(competition_id=comp.id).all()
    }
```

⚠️ **`anonymiser=True` par défaut, et `cycle.archiver` passe `False`.** Le défaut
protège : le paramètre n'a qu'un seul appelant qui l'inverse, et il est nommé.
L'inverse — un défaut permissif qu'il faut penser à restreindre — se serait
oublié au premier nouvel appelant.

⚠️ **Un participant sans dossard** (`dossard is None`, cas prévu par le modèle :
inscrit absent) ne peut pas s'afficher « Dossard None ». Il n'apparaît de toute
façon au classement que s'il a des réussites, donc un dossard ; le repli est
« Participant » tout court, et un test le couvre.

`suivi.fiche()` applique la **même règle** — la fiche du grimpeur porte `nom`,
et sans ça le réglage se contourne en touchant une ligne du classement.

La **recherche** de la page de résultats n'a besoin d'aucun code : elle filtre
sur le `nom` de la charge, qui est désormais « Dossard 42 ».

## 5. L'interrupteur dans la console

| Côté | Quoi |
| --- | --- |
| API | `POST /admin/participants/<id>/publication` — corps `{"refusee": true}`, rôle organisateur, journalisé |
| Lecture | `GET /admin/participants` porte `publication_refusee` en plus |
| Rendu | une cellule de plus dans `dessinerParticipants()`, `label.bascule` + `.glissiere` (spec 021), case native conservée sous le visuel avec `role="switch"` (spec 042) |

⚠️ **La console affiche toujours le vrai nom** — c'est elle qui sert à retrouver
la personne. La pastille « publié : Dossard N » dit ce que le public voit.

⚠️ **Le geste invalide le cache du classement** : `classement_service.invalider()`,
comme le fait déjà la réaffectation de dossard. Sans ça, l'anonymisation
n'apparaîtrait qu'au bout de 5 s côté serveur et 5 s de plus côté Caddy — et
l'organisateur, qui vient de raccrocher avec un parent, verrait un écran qui
n'obéit pas.

## 6. La page de confidentialité

- Route : `GET /confidentialite` dans `routes/pages.py`, sans session — comme
  `/` et `/console`.
- Gabarit : `templates/confidentialite.html`, autonome, thème clair/sombre par
  `prefers-color-scheme`, sans dépendance extérieure.
- Ancre `#opposition` sur la section visée par le second lien.
- Elle porte elle aussi la balise `noindex` : c'est une page de service, pas un
  contenu à référencer.

## 7. Le registre

`docs/registre-des-traitements.md`, un tableau par traitement. Aucun code, aucun
test — c'est un document, et le seul contrôle utile est qu'il existe et qu'il
est à jour (critère A11).

## 8. Fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/schema.py` | la colonne dans `COLONNES_AJOUTEES` |
| `climbcontest/models.py` | la colonne sur `Participant` |
| `climbcontest/classement_service.py` | `anonymiser=` dans `charge_publique` |
| `climbcontest/suivi.py` | même règle sur la fiche |
| `climbcontest/cycle.py` | `archiver` fige le nom réel |
| `climbcontest/routes/admin.py` | la route de bascule, et le champ en lecture |
| `climbcontest/routes/public.py` | `after_request` d'en-tête |
| `climbcontest/routes/pages.py` | routes `/robots.txt` et `/confidentialite` |
| `climbcontest/templates/resultats.html` | balise `noindex` + pied `#mentions` + CSS |
| `climbcontest/templates/admin.html`, `juge.html` | balise `noindex` |
| `climbcontest/templates/confidentialite.html` | **nouveau** |
| `docs/registre-des-traitements.md` | **nouveau** |
| `climbcontest/templates/admin.html` | colonne « Anonymisé » dans la liste |
| `tests/test_non_indexation.py` | **nouveau** |
| `tests/test_opposition.py` | **nouveau** |
| `CHANGELOG.md` / `changelog.d/` | section « Non publié » |

⚠️ **`models.py` et `migrations/` sont partagés avec la spec 008**, en cours sur
une autre branche. Les deux ajouts sont additifs et sur des lignes différentes —
mais git fusionne sans conflit deux ajouts voisins, et c'est précisément le cas
où l'on découvre le problème après le merge. Les deux branches seront testées
**ensemble** avant la porte 7, pas seulement chacune de son côté. `002_` est
laissé à la 008.

Reste `docs/specs-index.md`, où la ligne 043 sera ajoutée au dernier moment.
