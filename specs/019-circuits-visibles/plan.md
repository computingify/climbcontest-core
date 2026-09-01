# Spec 019 — Plan

Branche `feat/circuits-visibles`. Quatre étapes, chacune livrable et testée
seule. L'ordre n'est pas négociable : la donnée d'abord, l'écran ensuite, le
téléphone en dernier — c'est lui qu'on ne peut pas remettre à jour le matin
d'une compétition.

## Étape 1 — La couleur des prises entre en base

- [ ] `Bloc.couleur_prises` dans `models.py`, exposée par `to_dict()`
- [ ] `schema.COLONNES_AJOUTEES["bloc"]`
- [ ] `importer.py` : `I_COULEUR_PRISES = 4`, lue et comparée comme `couleur`
- [ ] `cycle._donnees_brutes()` l'archive
- [ ] Tests A1, A2

## Étape 2 — Le calcul des circuits et des anomalies

- [ ] `climbcontest/circuits.py` : `inventaire(comp)` → circuits, blocs,
      anomalies. Aucun Flask, aucune requête HTTP.
- [ ] `GET /admin/circuits`, rôle `ORGANISATEUR`
- [ ] Tests A3 à A7

## Étape 3 — La vue « Circuits » dans la console

- [ ] Entrée de navigation, sous « Les données », après « Participants »
- [ ] Bloc de contrôle de cohérence — **masqué quand tout va bien**
- [ ] Tableau filtrable par circuit
- [ ] Relecture à l'écran, en vrai, sur `seed_dev.py` (4 circuits)

## Étape 4 — Le garde-fou du juge

- [ ] `catalogue.js` : `FORMAT` 3, nouvelle forme, `estDansLeCircuit`
- [ ] `juge.js` : avertissement dans `redessiner()`, « Envoyer quand même »
- [ ] `juge.html` : le style
- [ ] `Success.hors_circuit_force`, `schema`, `enregistrer_lot`
- [ ] `/admin/reussites-tracees` expose les deux champs
- [ ] Tests A8 à A12

## Plan de test

| Module | Scénario | Attendu |
| --- | --- | --- |
| `test_import.py` | `Plan` avec colonne H | `couleur_prises` lue, `couleur` intacte (A1) |
| `test_import.py` | `Plan` sans colonne H | `None`, aucun avertissement (A2) |
| `test_import.py` | ré-import avec la couleur de prises changée | compté dans `blocs_mis_a_jour` |
| `test_circuits.py` | inventaire nominal | un bloc par ligne, catégories dérivées (A3) |
| `test_circuits.py` | bloc sans lien `bloc_circuit` | listé dans `blocs_sans_circuit` (A5) |
| `test_circuits.py` | circuit sans bloc | listé (A5) |
| `test_circuits.py` | participant « U19 F » sans circuit « U19 » | listé (A6) |
| `test_circuits.py` | tout cohérent | les trois listes vides (A7) |
| `test_circuits.py` | catégories dérivées | « U13 » ne donne « U13 F » que si quelqu'un l'est |
| `test_circuits.py` | route sans session / rôle lecture | 401 / 403 (A4) |
| `tests/js/` | `estDansLeCircuit` bloc du circuit | `true` (A8) |
| `tests/js/` | bloc hors circuit | `false` (A9) |
| `tests/js/` | dossard inconnu · tag inconnu · sans catégorie | `null` (A12) |
| `tests/js/` | catalogue au format 2 | catalogue vide → rechargement complet (A11) |
| `tests/js/` | aller-retour `versJson` / `depuisJson` au format 3 | identique |
| `test_lot.py` | `hors_circuit: true` | `hors_circuit_force` vrai en base (A10) |
| `test_lot.py` | champ absent | `NULL`, comportement inchangé |
| `test_tracabilite.py` | réussite forcée | les deux champs exposés |
| `test_schema.py` | base d'avant la spec | les deux colonnes ajoutées, données intactes |
| `tools/verify_ranking.py` | `fixtures/contest-nov2025.json` | 196 conformes, 0 écart (A13) |

## Vérification à la main

`scripts/dev-server.sh` + `scripts/seed_dev.py` (4 circuits, blocs rattachés à
un ou deux circuits voisins — exactement le cas réel) :

1. console → **Circuits** : le tableau montre les deux couleurs, le contrôle de
   cohérence ne s'affiche pas ;
2. supprimer un lien `bloc_circuit` à la main → l'anomalie apparaît, nommée ;
3. `/juge` : grimpeur U11 + bloc U11 → rien ; grimpeur U11 + bloc U17 →
   avertissement et « Envoyer quand même » ;
4. forcer l'envoi → la réussite apparaît marquée dans la vue **Réussites** ;
5. corriger le classeur et réimporter → la marque « hors circuit » calculée
   disparaît, `hors_circuit_force` reste.

## Ce qui reste après

L'application Android ne connaît pas ce garde-fou et ne le connaîtra pas : elle
est gelée. Si elle devait resservir, ce serait à noter dans le runbook du jour J
— les téléphones sous Android ne préviennent pas.
