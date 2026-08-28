# Index des specs

Une ligne par spec, par ordre de numéro. Voir [workflow.md](workflow.md) pour la
méthode.

| # | Spec | Statut | Résumé |
| --- | --- | --- | --- |
| [001](../specs/001-vm-climbcontest/) | `vm-climbcontest` | **rédigée — en attente de validation (porte 2)** | VM Proxmox 110, livraison par tirage avec changelog, exposition `climbcontest.adn-dev.fr`, contrôles adaptés à une VM intermittente |

## Specs pressenties

Issues de la [feuille de route](roadmap.md), **pas encore rédigées** — elles
attendent la validation du cadrage et les réponses aux décisions D1→D6.

| # prévu | Nom pressenti | Chantier | Bloqué par |
| --- | --- | --- | --- |
| 002 | `reliable-success-storage` | la base devient la source de vérité ; **identité stable ≠ dossard** | 001 |
| 003 | `offline-first-judge-app` | catalogue local **versionné + rafraîchissable en cours de compétition** | 002 |
| 004 | `ranking-engine` | moteur de classement, **validation par couleur en option par compétition** | 002 |
| 005 | `admin-console` | participants à chaud, saisie manuelle, paramétrage, classeur — **vocation à remplacer le Google Sheet** | 002 |
| 006 | `live-results-page` | page résultats spectateurs | 004 |
| 007 | `judge-pwa` | app juge iPhone sans store | 003 |
| 008 | `helloasso-import` | import des inscriptions en ligne, rapprochement avec les inscriptions sur place | 005 |

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
