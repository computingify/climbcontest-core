# Plan — Spec 013

Branche : `feat/console-saisie-guidee`. Aucun commit sur `master`.
**Rien n'est écrit avant la validation de la spec (porte 2).**

## IT1 — Le formatage

- [ ] `climbcontest/formatage.py` : `mots()` et `categorie()`
- [ ] `tests/test_formatage.py` : la table de vérité ci-dessous
- [ ] Branché dans `contest.ajouter_participant` — **pas** dans l'importateur

## IT2 — L'attribution du dossard

- [ ] `contest.prochain_dossard(comp)` — plus petit numéro libre
- [ ] `contest.ajouter_participant_numerote(...)` — avec retente sur collision
- [ ] `POST /admin/participants` attribue quand le corps ne porte pas de dossard
- [ ] Les 3 tests existants sur les participants sans dossard passent **inchangés**

## IT3 — Les référentiels

- [ ] `GET /admin/referentiels` — catégories et clubs distincts, rôle organisateur
- [ ] Liste vide et `success: true` quand aucune compétition n'est active

## IT4 — L'interface

- [ ] Barre latérale + burger, media query à 900 px, fermeture par voile / `Échap` / choix
- [ ] Listes déroulantes catégorie et club, avec « ＋ Autre… »
- [ ] Champ dossard retiré ; le message de confirmation annonce le numéro attribué
- [ ] Onglet Dossards : catégorie en liste déroulante, entrée vide = toutes
- [ ] Rechargement des référentiels après un ajout réussi

## IT5 — Documentation

- [ ] `docs/specs-index.md` : la ligne 013
- [ ] `CHANGELOG.md` : la section de version
- [ ] `docs/runbook-competition.md` : l'inscription à chaud ne demande plus de dossard

## Plan de test

Écrit **avant** l'implémentation, comme le veut le workflow.

### Formatage — `tests/test_formatage.py`

| Entrée | Attendu | Ce que ça protège |
| --- | --- | --- |
| `"jean-luc"` | `Jean-Luc` | le trait d'union est un séparateur |
| `"roc n'potes"` | `Roc N'Potes` | l'apostrophe droite aussi |
| `"roc n’potes"` | `Roc N’Potes` | et l'apostrophe typographique |
| `"CAF annonay"` | `CAF Annonay` | un sigle de 3 lettres survit |
| `"ASPTT lyon"` | `ASPTT Lyon` | un sigle de 5 lettres aussi |
| `"MARTIN"` | `Martin` | 6 lettres : ce n'est plus un sigle (**Q3**) |
| `"  annonay   escalade  "` | `Annonay Escalade` | espaces réduits, bords coupés |
| `"élise"` | `Élise` | les accents ne cassent pas la casse |
| `""` / `None` / `"   "` | `None` | un champ vide reste vide, pas `""` |
| `categorie("u13  f")` | `U13 F` | majuscules + espaces réduits |
| `categorie("U13 F")` | `U13 F` | **idempotent** — l'existant ne bouge pas |

La dernière ligne est la plus importante des onze : elle prouve que le
formatage ne modifie **aucune** valeur déjà en base, donc qu'aucun classement
ne change.

### Dossard — `tests/test_admin_participants.py`

| Scénario | Attendu |
| --- | --- |
| Base avec 1, 2, 3, 7, 8 | le suivant attribué est **4** |
| Base avec 1..109 | **110** |
| Base vide | **1** |
| `POST /admin/participants` sans dossard | `201`, la réponse porte un dossard |
| `POST` avec un dossard explicite | honoré, comportement inchangé |
| `ajouter_participant("Sans")` | `dossard is None` — **contrat métier intact** |
| `ajouter_participant("Sans").present` | `False` — inchangé |
| Deux créations concurrentes | deux dossards différents, aucune 500 |

### Référentiels

| Scénario | Attendu |
| --- | --- |
| Compétition avec les 5 clubs connus | les 5, triés, sans `null` |
| Un participant sans club | absent de la liste, pas de `null` dedans |
| Aucune compétition active | `success: true`, deux listes vides |
| Appel sans session | `401` |
| Appel avec un rôle insuffisant | `403` |
| Catégorie inédite créée puis rappel | elle est dans la liste |

### Interface — vérification manuelle

Le JavaScript de la console est inline dans le gabarit : il n'est pas
testable en l'état (voir architecture §6). Ces trois points se vérifient donc
**dans un vrai navigateur**, et le résultat est consigné ici :

| # | À vérifier | Comment |
| --- | --- | --- |
| A12 | ≥ 900 px : barre visible, burger absent. < 900 px : l'inverse | réduire la fenêtre |
| A13 | `Échap`, voile et choix d'une section referment la barre | au clavier et à la souris |
| — | « Autre… » révèle le champ et enregistre la valeur | inscrire un participant fictif, puis le supprimer |

### Non-régression

`pytest` en entier, et `node --test "tests/js/*.test.mjs"`. Les suites qui
comptent ici :

- `test_admin_participants.py` — le contrat de l'ajout
- `test_import.py` — l'importateur n'a pas bougé
- `test_classement.py` et `test_qr_et_dossards.py` — catégories et dossards intacts
- `tools/verify_ranking.py fixtures/contest-nov2025.json` → **196 conformes, 0 écart**

Ce dernier est le juge de paix : il rejoue une vraie compétition et compare
scores et rangs au classeur. S'il passe, aucune valeur de catégorie ni aucun
dossard n'a changé de sens.
