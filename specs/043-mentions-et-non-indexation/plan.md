# Spec 043 — plan

## Étapes

- [ ] 1. Branche `feat/043-mentions-et-non-indexation` depuis `origin/master`
- [ ] 2. `after_request` sur le blueprint `public` — en-tête `X-Robots-Tag`
- [ ] 3. Route `GET /robots.txt`
- [ ] 4. Balise `noindex` dans les trois gabarits servis (`resultats`, `admin`, `juge`)
- [ ] 5. Gabarit `confidentialite.html` + route `GET /confidentialite`
- [ ] 6. Le pied `#mentions` dans `resultats.html`, à la fin de `#defile`, avec sa règle `body.mur`
- [ ] 7. `docs/registre-des-traitements.md`
- [ ] 7 bis. La colonne `publication_refusee` : migration, modèle, `charge_publique(anonymiser=)`, `suivi.fiche`, `cycle.archiver`
- [ ] 7 ter. La route `POST /admin/participants/<id>/publication` et l'invalidation du cache
- [ ] 7 quater. La colonne « Anonymisé » dans la liste des participants de la console
- [ ] 8. Tests (tableau ci-dessous)
- [ ] 9. Capture de la page réelle après implémentation, comparée à la maquette
- [ ] 10. Section « Non publié » du CHANGELOG
- [ ] 11. PR, porte 7

## Plan de test

| Module | Scénario | Résultat attendu | Critère |
| --- | --- | --- | --- |
| `pages` | `GET /robots.txt` | `200`, `text/plain`, contient `Disallow: /` | A1 |
| `pages` | `GET /` | le HTML contient `name="robots"` et `noindex` | A2 |
| `public` | `GET /api/public/classement` | en-tête `X-Robots-Tag: noindex` | A3 |
| `public` | `GET /api/public/classement?groupe=inconnu` → `404` | **l'en-tête est présent sur l'erreur aussi** | A3 |
| `public` | `GET /api/public/grimpeur/<id>` inexistant → `404` | idem | A3 |
| `public` | aucune compétition active → `409` | idem | A3 |
| `admin` | `GET /api/v2/catalog` | **pas** d'en-tête `X-Robots-Tag` — le crochet est sur le blueprint public, pas sur l'application | — |
| `pages` | `GET /console`, `GET /juge?j=…` | balise `noindex` présente | A4 |
| `pages` | `GET /confidentialite` | `200`, contient l'ancre `id="opposition"` | A7, A8 |
| `pages` | contenu de `/confidentialite` | mentionne le responsable, la base légale, le délai d'un mois, la CNIL | A9 |
| navigateur | page de résultats, 390 px | le pied est visible après la dernière ligne, ses deux liens pointent vers `/confidentialite` et `/confidentialite#opposition` | A5, A7 |
| navigateur | page de résultats, `?mur` | `#mentions` calcule `display: none` | A6 |
| navigateur | avec et sans le pied | le nombre de `.ligne` rendues est identique | A10 |
| `contrat` | charge de `/api/public/classement` | ensemble des clés **inchangé** par rapport à la référence | A12 |
| dépôt | `docs/registre-des-traitements.md` | existe, cite les trois traitements | A11 |
| `schema` | migration jouée deux fois | colonne présente, aucune erreur, aucune donnée touchée | A13 |
| `modele` | participant existant après migration | `publication_refusee` vaut `False` | A13 |
| `admin` | `POST /admin/participants/<id>/publication` `{refusee:true}` | `200`, l'état est en base | A15 |
| `admin` | même appel sans session, puis avec un rôle insuffisant | `401` puis `403` | — |
| `classement_api` | participant anonymisé, `GET /api/public/classement` | `nom == "Dossard N"`, **`rang`, `score` et `dossard` identiques au cas non anonymisé** | A16 |
| `classement_api` | participant anonymisé **sans dossard** | `nom == "Participant"`, aucune exception | A16 |
| `public` | `GET /api/public/grimpeur/<id>` | même nom anonymisé | A17 |
| `cycle` | `archiver` puis relecture de l'archive | l'archive porte le **vrai** nom | A19 |
| `classement_service` | bascule puis appel immédiat | le cache a été invalidé, la charge est à jour sans attendre 5 s | — |
| navigateur | console, liste des participants | la colonne « Anonymisé » existe, l'interrupteur reflète la base, la pastille dit « publié : Dossard N » | A14, A20 |
| navigateur | page de résultats, recherche du vrai nom d'un anonymisé | aucun résultat | A18 |

⚠️ **Le test qui compte le plus est celui de l'erreur `404`.** Un
`after_request` mal placé (sur la vue plutôt que sur le blueprint, ou posé dans
un `try`) laisse passer les réponses d'erreur — et ce sont précisément les URL
qu'un robot fabrique en balayant. Le retirer doit faire échouer ce test : c'est
la vérification à faire avant de le croire.

⚠️ **Le test A16 se lit dans les deux sens.** Vérifier que le nom change ne
suffit pas : c'est **l'immobilité du rang** qui est la propriété, et elle ne se
voit qu'en comparant la charge avec et sans l'opposition, sur le même jeu de
données. Un test qui n'affirme que le nom passerait au vert sur une
implémentation qui retire la ligne.

⚠️ **Le test navigateur suit les règles de la PR #122** (session partagée) :
aucun ajout de route ni de crochet à la fixture `app`. Attendre que la #122 soit
fusionnée avant d'écrire les tests navigateur, ou construire son application
avec `creer_app(...)`.
