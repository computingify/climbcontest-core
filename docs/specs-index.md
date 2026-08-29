# Index des specs

Une ligne par spec, par ordre de numéro. Voir [workflow.md](workflow.md) pour la
méthode.

| # | Spec | Statut | Résumé |
| --- | --- | --- | --- |
| [001](../specs/001-vm-climbcontest/) | `vm-climbcontest` | ✅ **livrée** (28/08) — 2 critères restent ouverts **à dessein**, voir la spec | VM Proxmox 110, livraison par tirage avec changelog, exposition `climbcontest.adn-dev.fr`, contrôles adaptés à une VM intermittente |
| [002](../specs/002-reliable-success-storage/) | `reliable-success-storage` | ✅ **livrée** (28/08) — `v0.2.0` en production sur la VM 110 | La base devient la source de vérité, le classeur un miroir. Identité stable ≠ dossard, multi-compétition |
| [003](../specs/003-offline-first-judge-app/) | `offline-first-judge-app` | ✅ **livrée** (28/08) — les 5 itérations. Mesuré : 10 800 → **817** requêtes, et **0** aller-retour bloquant | L'app juge valide hors ligne et envoie par lots : 3 allers-retours bloquants par validation → **0**. Réponse directe à la demande initiale |
| [004](../specs/004-ranking-engine/) | `ranking-engine` | ✅ **livrée et close** (28/08) — les 3 décisions ouvertes sont tranchées | Moteur de classement pur, reproduit 196/196 scores et rangs du vrai classeur. 47 tests + le test d'acceptation sur données réelles |
| [005](../specs/005-admin-console/) | `admin-console` | ✅ **livrée** (29/08) | Console sur `/console` : comptes et rôles, participants à chaud, saisie manuelle, impression des dossards. Joignable depuis Internet, avec frein anti-force-brute |
| [006](../specs/006-live-results-page/) | `live-results-page` | ✅ **livrée** (28/08) | La page projetée dans la salle et ouverte par les spectateurs. Deux modes, aucune dépendance externe, recherche toutes catégories |

## Specs pressenties

Issues de la [feuille de route](roadmap.md), **pas encore rédigées** — elles
attendent la validation du cadrage et les réponses aux décisions D1→D6.

| # prévu | Nom pressenti | Chantier | Bloqué par |
| --- | --- | --- | --- |


| 007 | `judge-pwa` | app juge iPhone sans store | 003 |
| 008 | `helloasso-import` | import des inscriptions en ligne, rapprochement avec les inscriptions sur place | 005 |
| 009 | `finales` | **tours de finale.** Format tranché le 28/08 : les **N meilleurs de chaque catégorie regrimpent des blocs dédiés**, et le classement final ne tient compte **que du second tour** — le score de qualification ne se reporte pas. Reste à fixer : la valeur de N, et si elle varie selon la catégorie | 004 |
| 010 | `classement-club` | **classement par club.** Règle tranchée le 28/08 : **somme des scores de tous les grimpeurs du club**. Conséquence assumée — un club nombreux est avantagé ; c'est le choix d'Adrien, à redire au micro le jour J pour que personne ne s'en étonne | 004 |

L'ordre a été fixé par Adrien le 28/08 : **l'hébergement d'abord**.

Les contraintes de terrain qui traversent plusieurs de ces specs — participants
ajoutés ou dossards réaffectés en pleine compétition, remplacement du classeur
par la page de paramétrage, double origine des inscriptions — sont réunies dans
[contraintes-metier.md](contraintes-metier.md). **À lire avant de rédiger 002 à
008.**

## Historique pré-specs

Le travail réalisé avant la mise en place de cette méthode n'a pas de spec. Il
est décrit dans :

- [etat-des-lieux.md](etat-des-lieux.md) — audit complet de l'existant
- [technical/architecture-actuelle.md](technical/architecture-actuelle.md) — l'architecture telle qu'elle tourne
- [technical/classeur-google.md](technical/classeur-google.md) — la mécanique du classeur et l'algorithme de classement, validé sur données réelles
- [technical/banc-base-de-donnees.md](technical/banc-base-de-donnees.md) — SQLite ou PostgreSQL : les mesures, et à quelle condition les refaire
- [plan-de-repli.md](plan-de-repli.md) — comment revenir à la version 2025-2026
- [contraintes-metier.md](contraintes-metier.md) — ce que le terrain impose
- [preparation-depots.md](preparation-depots.md) — organisation des dépôts, décision D3

La spec 003 dispose déjà de son test d'acceptation :
`python3 tools/verify_ranking.py fixtures/contest-nov2025.json` doit sortir
« 196 conformes, 0 écart ».

À noter : la branche `feature/ResultAlgorithm` de `climbcontest-core` contient
une implémentation avancée du classement, jamais mergée. Elle servira de matière
première à la spec 003 — mais elle sera relue et corrigée, pas mergée telle
quelle (réserves listées dans la [feuille de route](roadmap.md#2a-reprendre-la-mécanique-du-classeur)).
