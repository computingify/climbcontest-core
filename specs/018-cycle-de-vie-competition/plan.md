# Plan — spec 018

Branche : `feat/console-cycle-de-vie`, dans un worktree isolé
(`.worktrees/018-cycle-de-vie`).

## Étapes

- [x] **1. Le modèle** — `models.py` : la table `Archive`, sans clé étrangère,
      avec ses compteurs recopiés. Un test qui vérifie que `create_all` la crée
      sur une base existante.
- [x] **2. La charge publique** — `classement_service.charge_publique(comp)`,
      extraite de `routes/public.py`. La route publique l'appelle ; sa réponse
      ne change pas d'un octet. *C'est un refactor pur, livré et vérifié avant
      d'ajouter quoi que ce soit* — si la page de résultats bouge ici, on le
      voit tout de suite, pas trois étapes plus loin.
- [x] **3. Le module** — `climbcontest/cycle.py` : `regler_statut`,
      `_garde_en_cours` (avec forçage), `effacer_donnees` (déménagée de
      `parametrage`, + `catalogue_version` + invalidation du cache), `archiver`,
      `lister`, `classement_archive`, `supprimer`. `parametrage.relier()`
      importe la version déménagée **et** la garde partagée ; l'import inutilisé
      de `EN_COURS` sort de `contest.py`.
- [x] **4. L'essai d'écriture** — `client.essai_ecriture()`, `protectedRanges`
      ajouté au `fields` existant, `parametrage.tester(…, ecriture=True)`.
- [x] **5. L'import en deux temps** — `Lecture`, `lire_tout()`,
      `importer(lecture=…)`. Les tests de `test_import.py` doivent passer
      **sans être touchés**.
- [x] **6. Les routes** — les six nouvelles, plus les modes sur l'import et le
      drapeau d'écriture sur le test.
- [x] **7. La page de rejeu** — `source` paramétrable dans `resultats.html`,
      `/console/archives/<id>/resultats` dans `pages.py`.
- [x] **8. La console** — les vues « Compétition » (dont les trois boutons
      d'état) et « Archives », le `<dialog>` de confirmation partagé avec sa case
      « Effacer quand même », le JavaScript.
- [x] **9. Les tests** — `test_cycle_competition.py`, et les ajouts aux deux
      fichiers existants. Tous les critères A1→A38.
- [x] **10. La documentation** — `specs-index.md`, `CHANGELOG.md`,
      `docs/technical/classeur-google.md` (le test d'écriture),
      `docs/runbook-competition.md` (le cycle : archiver → effacer → relier →
      importer).
- [x] **11. Vérification à l'écran** — ✅ faite le 01/09, console pilotée sur un
      serveur local et une base jetable (8 grimpeurs, 24 blocs, 70 réussites).
      Vérifié en vrai, et pas seulement en Python :
      - la fenêtre de confirmation affiche les compteurs réels, la case de
        forçage n'apparaît **que** si la compétition est `en_cours`, et le
        bouton reste **désactivé** tant que le mot n'est pas frappé **et** la
        case cochée ;
      - annuler ne détruit rien ;
      - **A26 mesuré** : la page de rejeu fait **un seul** appel réseau après
        40 s d'observation (la page en direct en aurait fait trois), bandeau
        « archive du … » ;
      - `?mur` marche sur une archive — podium, colonnes, scratchs ;
      - **A27 vu à l'écran** : après effacement, l'archive affiche toujours ses
        8 lignes et 70 réussites, la page publique en affiche 0 ;
      - aucune erreur JavaScript de bout en bout.

      **Un bug trouvé, et seulement là** : `dire()` n'annulait pas son minuteur
      de masquage, et l'avertissement d'archivage disparaissait au bout de six
      secondes. Corrigé, avec ses tests de non-régression.

L'ordre n'est pas indifférent. **2 avant 3** : `archiver` consomme
`charge_publique`. **3 et 5 avant 6** : les routes n'orchestrent que du code
déjà testé. **7 après 3** : la page de rejeu a besoin d'une archive à afficher.

## Plan de test

Écrit avant l'implémentation. Aucun accès réseau : le service Google est
remplacé par un double qui compte ce qu'on lui demande — la couture
`ClasseurGoogle(identifiant, feuilles=…)` de la spec 015.

### `tests/test_client_classeur.py` — l'essai d'écriture

| Scénario | Attendu | Critère |
| --- | --- | --- |
| Grille 120 × 1000, coin vide | `values.update` sur `Import!DP1000`, relecture, `values.clear` sur la même cellule, dans cet ordre | A1 |
| Le coin porte déjà une valeur | **aucun** `values.update`, `tentee: False`, message explicite | A3 |
| `values.update` lève (403 de Google) | `ecriture: False`, message de Google repris, aucun `clear` | A2 |
| La relecture rend autre chose que ce qui a été écrit | `ecriture: False`, `clear` tenté quand même | A2 |
| `values.clear` lève | `ecriture: True`, `restauree: False`, cellule nommée dans le message | A4 |
| `Import` porte une plage protégée | avertissement dans le rapport | A5 |
| Aucune plage protégée | aucun avertissement, **aucun appel supplémentaire** | A5 |
| `tester()` sans `ecriture=True` | aucun appel d'écriture — le test en lecture n'a pas changé | A6 |

### `tests/test_cycle_competition.py` — le module, les routes, le cycle

**L'import**

| Scénario | Attendu | Critère |
| --- | --- | --- |
| `POST /admin/import/sheet` sans `mode` | mise à jour, comme aujourd'hui | A7, A12 |
| Mode `remplacer` sans confirmation | 400, **aucun appel au classeur**, compteurs identiques | A8 |
| Mode `remplacer` avec `EFFACER` | un participant absent du classeur a disparu, un participant du classeur est là, `Success` à 0 | A9 |
| Mode `remplacer`, la lecture du classeur lève | 502, participants et réussites **intacts** | A10 |
| Mode `remplacer` | le double ne voit **aucun** appel d'écriture | A11 |
| Mode `remplacer` en organisateur non-admin | 403, rien touché | A30 |
| Mode inconnu | 400 | A12 |

**Le statut**

| Scénario | Attendu | Critère |
| --- | --- | --- |
| `POST /admin/competition/statut` avec chacune des trois valeurs | statut relu en base = ce qu'on a envoyé | A32 |
| Avec `"demarree"`, une chaîne vide, un corps sans `statut` | 400, statut **inchangé** | A33 |
| Après changement, `GET /admin/classeur` | renvoie le nouveau statut | A37 |
| En organisateur non-admin | 200 — c'est son geste | A31 |
| Sans session | 401 | A31 |
| Enregistrer une réussite sur une compétition `preparation` | elle reste `preparation` | A38 |
| `archiver()` | passe à `terminee` sans passer par la route | A21 |

**L'effacement**

| Scénario | Attendu | Critère |
| --- | --- | --- |
| `POST /admin/donnees/effacer` avec `EFFACER` | participants, blocs, circuits, réussites, réaffectations à 0 | A13 |
| Idem, avec une **seconde** compétition peuplée et deux comptes | seconde compétition et `Utilisateur` inchangés | A14 |
| Idem, avec une archive en base | l'archive est toujours là | A14 |
| Sans confirmation, avec `effacer` en minuscules, avec un corps vide | 400, compteurs inchangés | A15 |
| Sur une compétition `en_cours`, sans forçage | 409, message qui contient « archiver » | A16 |
| Sur une compétition `en_cours`, `forcer: true` + `EFFACER` | 200, données effacées | A34 |
| `forcer: true` **sans** le mot `EFFACER` | 400, rien touché — le forçage ne remplace pas la confirmation | A35 |
| `forcer: true` sur une compétition `preparation` | 200, sans effet de bord : le forçage d'une garde qui ne se déclenche pas ne change rien | A34 |
| `relier(mode=reinitialiser, forcer=True)` sur `en_cours` | accepté ; sans `forcer`, 409 | A36 |
| Après effacement | `catalogue_version` > max de **toutes** les compétitions d'avant | A17 |
| Classement lu, effacement, classement relu | le second est vide (cache invalidé) | A18 |
| Après effacement | le double du classeur ne voit **aucun** appel | A19 |
| En organisateur non-admin | 403 | A30 |

**L'archivage**

| Scénario | Attendu | Critère |
| --- | --- | --- |
| `POST /admin/archives` sur une compétition peuplée | une ligne `archive`, `format: 1`, compteurs recopiés justes | A20 |
| Le `classement` de l'archive vs `/api/public/classement` | mêmes groupes, mêmes rangs, mêmes scores | A20 |
| Après archivage | `statut == "terminee"`, participants et réussites **inchangés** | A21 |
| Archiver une compétition sans aucune réussite | 200, `avertissements` non vide | A22 |
| Archiver deux fois | deux lignes, la plus récente en tête de `lister()` | § 5 |
| Le cache de classement est périmé au moment d'archiver | l'archive porte le calcul **frais**, pas le cache | § 3 |
| `GET /admin/archives` | les compteurs viennent des colonnes, `contenu` jamais chargé | A23 |
| `DELETE` sans confirmation, puis en organisateur | 400, puis 403 ; l'archive est toujours là | A29, A30 |
| `GET /admin/archives/<id>/fichier` | `Content-Disposition` avec la date dans le nom | A28 |
| Les routes de lecture sans session | 401 | A31 |
| Les routes de lecture en organisateur | 200 | A31 |

**Le cycle complet — le test qui compte**

| Scénario | Attendu | Critère |
| --- | --- | --- |
| Peupler → archiver → **effacer** → relire l'archive | le classement de l'archive est complet et identique à celui d'avant l'effacement | **A27** |
| Idem, puis réimporter un autre classeur | l'archive n'a pas bougé, la base porte la nouvelle édition | A27 |

### `tests/test_page_resultats.py` — le rejeu

| Scénario | Attendu | Critère |
| --- | --- | --- |
| `GET /` | `data-source` vaut `/api/public/classement`, `data-archive` vide | A25 |
| `GET /console/archives/<id>/resultats` | `data-source` pointe l'archive, `data-archive` porte la date | A24 |
| Idem sans session | 401 ou redirection vers la connexion | A31 |
| `GET /admin/archives/<id>/classement` | même forme que `/api/public/classement` (mêmes clés de premier niveau) | A24 |
| Pendant qu'une archive est consultée, `GET /api/public/classement` | toujours la compétition **active** | A25 |
| Archive d'un `format` inconnu | la liste l'affiche, « Revoir » désactivé avec la raison, téléchargement possible | § 5 |

### A26 — pas de test JavaScript, et c'est délibéré

`tests/js/` ne porte que les modules de la PWA juge, qui sont de vrais fichiers
ES. Le JavaScript de `resultats.html` est **inline dans le gabarit** : le
sortir pour le tester serait un refactor plus gros que la spec entière, et
`test_page_resultats.py` dit déjà pourquoi on ne simule pas ce comportement —
« le simuler ici donnerait une fausse assurance ».

A26 se vérifie donc en deux morceaux honnêtes :

- côté Python, que le serveur rend bien `data-archive` (ci-dessus) ;
- côté navigateur, à l'étape 11, que la page ne relance aucune requête : onglet
  réseau ouvert, on attend 40 s, on compte les appels. Un seul.

### Ce que ce plan ne teste pas, et pourquoi

**Le vrai classeur Google.** Aucun test de la suite ne touche le réseau — les
paquets `google-*` ne sont même pas installés dans le venv de développement.
L'essai d'écriture est vérifié contre un double qui enregistre les appels. Le
seul contrôle réel se fait à l'étape 11, à la main, sur un classeur jetable —
**jamais sur celui d'une compétition**.

**La taille d'une archive réelle.** ✅ **Mesurée** à l'étape 11 : **701 Ko**
pour 196 grimpeurs, 50 blocs et 3 031 réussites — et non les 300 Ko estimés.
La spec porte désormais le chiffre mesuré et ce qu'il implique.

## Vérifications de non-régression

À faire tourner en entier avant d'ouvrir la PR — l'étape 5 touche l'import et
l'étape 2 touche la route publique, c'est-à-dire les deux chemins que le
samedi matin emprunte :

```bash
python3 -m pytest -q
python3 tools/verify_ranking.py fixtures/contest-nov2025.json   # 196 conformes, 0 écart
```

Le second n'est pas décoratif : l'étape 2 déplace la construction de la charge
publique, donc le code qui enrichit les lignes de classement. S'il dérive, c'est
là que ça se voit.
