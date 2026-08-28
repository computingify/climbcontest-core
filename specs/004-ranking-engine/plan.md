# 004 — Plan

> **Note de méthode.** Ce plan a été écrit **après** l'implémentation, pour
> combler un manquement : la spec 004 est partie en PR avec son seul `spec.md`,
> sans `architecture.md` ni `plan.md`, contrairement à
> [workflow.md](../../docs/workflow.md). Les cases sont donc cochées d'après ce
> qui a réellement été livré et vérifié — pas d'après une intention.
>
> Le plan de test, lui, garde toute sa valeur : c'est la liste de ce qui est
> couvert aujourd'hui, et elle sert de socle aux specs 006 et 005.
>
> **Et il a servi tout de suite.** En écrivant ce tableau, dix lignes se sont
> révélées non couvertes alors que je les croyais acquises — bloc dans aucun
> circuit, participant sans catégorie, expiration réelle du cache, ce que la
> réponse publique divulgue. Les dix tests ont été écrits. C'est exactement ce
> que la méthode cherche à provoquer : écrire le plan de test **force à
> constater** ce qui manque, là où une relecture du code se contente de
> retrouver ce qu'on y a mis.

---

## IT1 — Décoder le classeur

- [x] Récupérer le classeur en lecture seule (`tools/dump_sheet.py`)
- [x] Reconstituer la formule à partir des colonnes
- [x] Comprendre le vocabulaire : `U13 F` est une **catégorie**, `U13` un
      **circuit**, et le « scratch » est par circuit
- [x] Figer les données de novembre 2025 en fixture **anonymisée**
      (`fixtures/contest-nov2025.json`)

Découverte décisive de cette étape : **seuls les blocs du circuit du grimpeur
comptent**. Sans ce filtre, 17 grimpeurs sur 98 avaient un score trop élevé.
C'est cet écart qui a révélé la règle — tant que les 196 valeurs ne tombaient
pas *toutes* juste, l'algorithme était faux quelque part.

## IT2 — Le calcul, pur

- [x] `classement.py` — aucun import Flask, aucun SQL
- [x] Valeur d'un bloc, score, rangs avec ex æquo partagés
- [x] Validation par couleur, en option
- [x] `tools/verify_ranking.py` — le test d'acceptation

## IT3 — Le branchement à la base

- [x] `classement_service.py` — chargement en quatre requêtes, pas une par
      participant
- [x] Groupes par catégorie **et** par circuit
- [x] Options lues dans `Competition.options` (JSON)
- [x] Cache de 5 s, par processus, documenté comme tel

## IT4 — L'exposition

- [x] `GET /api/public/classement`, sans authentification
- [x] `?groupe=`, et `GET /api/public/groupes`
- [x] `calcule_le` dans la réponse
- [x] Exemption CrowdSec côté `edge` et cache Caddy de 5 s

## Ce qui reste à faire

- [ ] Répondre aux questions **Q1** (variante de validation par couleur par
      défaut), **Q2** (tours de finale) et **Q3** (classement club) — elles
      appartiennent à Adrien
- [ ] La page résultats elle-même : spec 006

---

## Plan de test

### Le critère qui décide de tout

| Vérification | Résultat |
| --- | --- |
| `verify_ranking.py` sur les données réelles de novembre 2025 | ✅ **196 conformes, 0 écart** |
| Groupes couverts | 8 catégories + 4 circuits = 12 |
| Réussites rejouées | 1003 |

C'est le seul critère qui compte vraiment : l'algorithme reproduit-il, au point
près, ce que le classeur a calculé le jour de la vraie compétition ? Un test
unitaire qui passe avec un algorithme faux ne vaut rien ; celui-ci ne peut pas.

### L'algorithme

| Scénario | Attendu | Couvert |
| --- | --- | --- |
| Un seul grimpeur réussit un bloc | Il vaut 1000 pour lui | ✅ |
| Tout le monde réussit un bloc | Il vaut 1000/n | ✅ |
| Aucune réussite | Tous à 0, aucun plantage | ✅ |
| Deux scores égaux | Même rang, le suivant saute les places (`1,2,2,4`) | ✅ |
| Bloc hors du circuit du grimpeur | **Ne compte pas** | ✅ |
| Bloc dans aucun circuit | Ne compte nulle part, reste au catalogue | ✅ **ajouté** |
| Participant sans catégorie | Absent des classements par catégorie, aucune exception | ✅ **ajouté** |
| Participant sans dossard mais avec des réussites | Compté, et classé (saisie manuelle) | ✅ **ajouté** |
| Catégorie dont le circuit n'existe pas | Classement vide, signalé, pas d'exception | ✅ |
| Deux compétitions en base | Les classements ne se mélangent jamais | ✅ |

### La validation par couleur

| Scénario | Attendu | Couvert |
| --- | --- | --- |
| Option à 0 (défaut) | Aucune validation implicite | ✅ |
| 100 % d'une couleur, option à 1 | Les couleurs plus faciles sont validées | ✅ |
| Presque toute une couleur | Rien n'est validé — c'est « 100 % », pas « presque » | ✅ **ajouté** |
| Couleur pleine **hors du circuit** | Ne compte pas comme pleine | ✅ **ajouté** — le piège : un U11 qui fait le seul bloc Noir du U13 ne doit pas gagner une couleur |
| Bloc sans couleur dans les données | Ignoré, pas d'exception | ✅ **ajouté** |
| L'option ne change rien à novembre 2025 | 196/196 toujours, option désactivée | ✅ |

### L'API

| Scénario | Attendu | Couvert |
| --- | --- | --- |
| `GET /classement` sans authentification | 200 | ✅ |
| `?groupe=U13 F` | Un seul classement | ✅ |
| `?groupe=` inconnu | 404 **avec la liste des groupes valides** | ✅ |
| Aucune compétition active | 409, message explicite | ✅ |
| `calcule_le` présent | ✅ | ✅ |
| Les noms sont là, **rien d'autre** | Liste blanche stricte des champs. Ces pages sont ouvertes à tout Internet et portent des données de **mineurs** | ✅ **ajouté** |
| `GET /groupes` | Liste avec le nombre de participants | ✅ |

### Le cache

| Scénario | Attendu | Couvert |
| --- | --- | --- |
| Deux appels rapprochés | Un seul calcul | ✅ |
| Après la durée de fraîcheur | Recalcul — le mécanisme d'expiration, pas un appel forcé | ✅ **ajouté** |
| Le cache ne survit pas entre deux tests | Fixture `_cache_propre` autouse | ✅ |
| Une réussite arrivée pendant la fraîcheur | Prise au calcul suivant, **entière**. Jamais un classement à moitié à jour | ✅ **ajouté** |

Le cache **par worker** est documenté dans le module : quatre workers, quatre
caches, donc jusqu'à cinq secondes d'écart entre deux spectateurs. C'est un
choix, pas un oubli — et ce qui serait grave, un classement *faux*, est
impossible puisque chaque calcul repart de la base.

### Performance

| Mesure | Cible | Mesuré |
| --- | --- | --- |
| Classement complet de novembre 2025 (98 participants, 67 blocs, 1003 réussites, 12 groupes) | < 1 s | **~23 ms** de bout en bout, interpréteur Python compris |
| Fréquence maximale de calcul | 1 / 5 s / worker | ✅ |
| Le calcul bloque-t-il l'enregistrement d'une réussite ? | Non | ✅ chemins séparés |

### Total

**47 tests** sur `test_classement.py` et `test_classement_api.py` — 37 avant
l'écriture de ce plan, 10 ajoutés à cause de lui — plus le test d'acceptation
sur données réelles.
