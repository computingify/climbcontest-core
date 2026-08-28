# 004 — Le moteur de classement

## Résumé

Reprendre côté backend le calcul que fait aujourd'hui le classeur Google. C'est
ce qui rend possible la page résultats en direct, les archives, et à terme
l'abandon du classeur.

**La règle est déjà connue, décodée et validée** — voir
[technical/classeur-google.md](../../docs/technical/classeur-google.md). Cette
spec ne cherche pas l'algorithme : elle l'implémente et le prouve.

## Le critère qui décide de tout

> `python3 tools/verify_ranking.py fixtures/contest-nov2025.json` doit sortir
> **« 196 conforme(s), 0 ecart(s) »** en interrogeant le **moteur du backend**,
> et non plus sa propre copie de l'algorithme.

196 scores et rangs réels, 8 catégories, 4 circuits, 1003 réussites. Tant que ce
chiffre n'est pas atteint, on ne bascule pas.

## La règle

```
Pour un classement donné — une catégorie (« U13 F ») ou un circuit (« U13 ») :

  membres  = les participants de ce groupe
  réussites retenues = celles des membres, SUR LES BLOCS DU CIRCUIT seulement

  valeur(bloc)    = 1000 / nombre de MEMBRES ayant réussi ce bloc
  score(membre)   = arrondi( somme des valeurs de ses blocs retenus )
  rang            = score décroissant, les ex æquo partagent le même rang
```

Trois points que la branche `feature/ResultAlgorithm` avait manqués, et qui sont
la raison d'être de cette spec :

1. **Le filtre par circuit est obligatoire.** Une réussite sur un bloc hors du
   circuit du grimpeur est enregistrée mais ne compte pas. Sans ce filtre,
   17 grimpeurs sur 98 obtiennent un score trop élevé.
2. **Le dénominateur est relatif au groupe classé.** Un même bloc ne vaut pas la
   même chose en `U13 F`, en `U13 H` et au scratch `U13`.
3. **Le « scratch » est par circuit**, pas toutes catégories confondues.

## Périmètre

### Inclus

1. Le moteur de calcul, pur et testable, sans dépendance HTTP.
2. Les classements **par catégorie** et **par circuit**.
3. La **validation par couleur**, en **option par compétition** (décision du
   28/08) : réussir 100 % de deux couleurs plus dures valide les couleurs plus
   faciles.
4. Le stockage des classements calculés, pour ne pas recalculer à chaque
   affichage.
5. Le recalcul déclenché par l'arrivée de réussites, avec un plafond.
6. `GET /api/public/classement` — ce que consommera la page résultats.

### Explicitement exclu

- La page résultats elle-même (spec 006).
- La saisie manuelle (spec 005) — mais une réussite `source=manuel` doit
  compter exactement comme un scan.
- Les tours de finale : l'onglet `Finales` du classeur est vide, on ne devine
  pas (Q2).

## Critères d'acceptation

### Justesse

- [x] `tools/verify_ranking.py` sort **0 écart** en utilisant le moteur backend.
      → `196 conformes, 0 ecart`, rejoué à chaque exécution de la suite
- [x] Les 8 catégories et les 4 circuits de novembre 2025 sont reproduits.
      → `test_reproduit_novembre_2025` (196 lignes vérifiées)
- [x] Une réussite sur un bloc hors circuit est **stockée mais non comptée**.
      → `test_bloc_hors_circuit_ne_compte_pas` + `test_bloc_hors_circuit_est_accepte`
- [x] Les ex æquo partagent le même rang, et le suivant saute les places
      occupées (deux 1ers → pas de 2ᵉ, le suivant est 3ᵉ).
- [x] Un bloc que personne n'a réussi ne vaut rien et ne fait pas diviser par
      zéro.
- [x] Un participant sans réussite apparaît avec un score de 0, pas absent.
      → `test_participant_sans_reussite_figure_au_classement`
- [x] Une réussite `source=manuel` compte comme un scan.
      → `test_une_reussite_saisie_a_la_main_compte_comme_un_scan`

### La validation par couleur

- [x] Désactivée par défaut : le classement est identique à sans l'option.
      → `test_desactivee_par_defaut` (moteur et service)
- [x] Activée : réussir 100 % de deux couleurs plus dures valide les couleurs
      plus faciles du même circuit.
- [x] L'option est **par compétition**, pas globale.
      → `test_lue_depuis_les_options_de_la_competition`
- [x] Les blocs validés par couleur comptent dans le dénominateur comme les
      autres.

### Performance et fraîcheur

- [x] Le classement complet de novembre 2025 (98 participants, 67 blocs,
      1003 réussites, 12 groupes) se calcule en **moins d'une seconde**.
- [x] Il n'est jamais recalculé plus d'une fois toutes les 5 secondes, quel que
      soit le nombre de réussites qui arrivent.
- [x] Le calcul ne bloque pas l'enregistrement d'une réussite.
      → chemins séparés : `enregistrer_reussite` ne touche jamais au classement

### API

- [x] `GET /api/public/classement` renvoie tous les groupes, sans
      authentification.
- [x] `?groupe=U13 F` renvoie un seul classement. → `test_un_seul_groupe`
- [x] La réponse porte l'heure du calcul, pour que la page puisse afficher
      « il y a 3 s ».

## Cas limites

| Situation | Comportement attendu |
| --- | --- |
| Aucune réussite | tous à 0, rangs par ordre stable, pas d'erreur |
| Un seul grimpeur a réussi un bloc | ce bloc vaut 1000 pour lui |
| Participant sans catégorie | absent des classements par catégorie, présent nulle part ailleurs — et **signalé** |
| Participant sans dossard | compté s'il a des réussites (saisie manuelle) |
| Bloc dans aucun circuit | ne compte dans aucun classement, mais reste au catalogue |
| Catégorie dont le circuit n'existe pas | classement vide, signalé, pas d'exception |
| Réussite arrivée pendant le calcul | prise au calcul suivant, jamais un classement à moitié à jour |
| Deux compétitions en base | les classements ne se mélangent jamais |

## Décisions — closes le 28/08

| # | Question | Pourquoi ça compte |
| --- | --- | --- |
| # | Question | Réponse d'Adrien, 28/08 |
| --- | --- | --- |
| **Q1** | Variante de validation par couleur par défaut | ✅ **Deux couleurs pleines.** Réussir 100 % des blocs de deux couleurs plus difficiles valide toutes les couleurs plus faciles. L'option reste **désactivée** par défaut ; c'est la valeur proposée le jour où elle est activée. Codée, testée, `couleurs_requises = 2` |
| **Q2** | Les tours de finale existent-ils ? | ✅ **Oui, attendus.** Hors périmètre de cette spec — ils changent le modèle de données. → spec **009** |
| **Q3** | Un classement **club** est-il attendu ? | ✅ **Oui, attendu.** Le moteur actuel s'y prête, mais c'est une règle d'agrégation qu'il faut définir (somme ? moyenne ? *n* meilleurs ?) → spec **010** |

Les trois questions sont closes. Les deux fonctionnalités demandées deviennent
des specs à part entière plutôt que des ajouts discrets ici : les finales
touchent au modèle de données, et le classement club demande une règle
d'agrégation qui n'existe nulle part aujourd'hui — le classeur n'en a pas.
