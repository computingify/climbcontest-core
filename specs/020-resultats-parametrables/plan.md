# Spec 020 — Plan

Branche `feat/resultats-parametrables`. Trois étapes. Les deux premières sont
indépendantes ; la troisième dépend de la deuxième.

## Étape 1 — Ce qui ne tient qu'à la page

- [ ] `contexte` porte la catégorie sur `scratch` et `circuit`, rien ailleurs
- [ ] Bouton « masquer la recherche » : markup, CSS `.hors-mur`, `localStorage`
- [ ] Masquer vide la recherche en cours
- [ ] Tests A5 à A11

Livrable seul, sans toucher au serveur.

## Étape 2 — Nommer la compétition

- [ ] `cycle.renommer(comp, nom, date)` — valide tout avant d'écrire quoi que ce soit
- [ ] `GET /admin/competition` (organisateur), `POST /admin/competition` (admin)
- [ ] Console : champs nom et date dans « État de l'édition »
- [ ] Tests A1 à A4

## Étape 3 — Choisir les classements affichés

- [ ] `cycle.ecrire_options()` — fusionne, n'écrase pas `validation_couleur`
- [ ] `POST /admin/competition/affichage`
- [ ] `charge_publique` ajoute `groupes_masques`, ne filtre rien
- [ ] Console : la liste de cases à cocher
- [ ] `groupesVisibles()` filtre, avec la garde « tout masqué »
- [ ] Tests A12 à A18

## Plan de test

| Module | Scénario | Attendu |
| --- | --- | --- |
| `test_cycle_competition.py` | renommer | nom changé, servi par l'API publique (A1) |
| `test_cycle_competition.py` | nom vide · 200 caractères | 400, rien modifié (A2) |
| `test_cycle_competition.py` | date invalide **et** nom valide | 400, le nom non plus n'a pas bougé (A4) |
| `test_cycle_competition.py` | organisateur | 403 (A3) |
| `test_cycle_competition.py` | `groupes_masques` écrit | rangé dans `options` (A12) |
| `test_cycle_competition.py` | `validation_couleur` déjà présent | toujours là après écriture (A17) |
| `test_cycle_competition.py` | groupe inconnu masqué | accepté, rangé |
| `test_classement_api.py` | charge publique | tous les classements + `groupes_masques` (A13) |
| `test_classement_api.py` | archive relue | pas de `groupes_masques`, tout servi (A18) |
| `test_page_resultats.py` | scratch et circuit | la catégorie est dans la ligne (A5, A6) |
| `test_page_resultats.py` | catégorie et club | pas de catégorie en appoint (A7, A8) |
| `test_page_resultats.py` | groupe masqué | absent de la barre et de la rotation (A14) |
| `test_page_resultats.py` | groupe courant masqué | bascule sur le premier visible (A15) |
| `test_page_resultats.py` | tout masqué | filtre ignoré, page utilisable (A16) |
| `test_page_resultats.py` | `?mur` | pas de bouton de recherche (A11) |

## Vérification à la main

`scripts/dev-server.sh` + `scripts/seed_dev.py` :

1. renommer la compétition → le bandeau de `/resultats` suit sous 15 s ;
2. `/resultats` : la catégorie n'apparaît que sur les scratchs ;
3. masquer la recherche, recharger → toujours masquée ; `?mur` → pas de bouton ;
4. décocher une catégorie dans la console → elle quitte la barre et la rotation
   au rafraîchissement suivant, sur le mur **et** sur le téléphone ;
5. tout décocher → la page reste utilisable ;
6. archiver puis revoir l'archive → tous les classements, réglage ignoré.
