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
| [007](../specs/007-pwa-juge/) | `pwa-juge` | ✅ **livrée** (29/08) — les 4 itérations. ⚠️ Le scan reste à essayer sur un vrai iPhone | L'application juge sur iPhone, sans payer de store. Une PWA servie par le backend, jeton dans le lien, jsQR versé dans le dépôt. File hors ligne en IndexedDB : le juge n'attend plus le réseau |
| [010](../specs/010-classement-club/) | `classement-club` | ✅ **livrée** (29/08) | Somme des scores de tous les grimpeurs du club, dérivée des classements par catégorie. Chaque grimpeur compte une fois, par sa catégorie |
| [011](../specs/011-tracabilite-des-scans/) | `tracabilite-des-scans` | ✅ **livrée** (29/08) — les 3 itérations | Le journal complet des scans sur le téléphone, l'appareil et la référence client gardés côté serveur, et une page de contrôle qui dit si un scan précis est arrivé |
| [012](../specs/012-cle-api-juges/) | `cle-api-juges` | ✅ **livrée** (29/08) | L'application envoie sa clé, le serveur l'exige. Mode strict par défaut, plusieurs clés acceptées pour en changer sans coupure. Le plan de repli porte l'étape qui rouvre l'API au gel `V3.1.4` |
| [013](../specs/013-console-saisie-guidee/) | `console-saisie-guidee` | 🟡 **codée, en attente de relecture** (30/08) | Catégorie et club en listes déroulantes, formatage serveur de ce qui est saisi, dossard attribué automatiquement. La navigation en tiroir de la spec est arrivée autrement, par la refonte livrée en 0.8.0 |
| [014](../specs/014-jeton-juge-dans-le-lien/) | `jeton-juge-dans-le-lien` | 🟡 **codée, en attente de relecture** (30/08) — ⚠️ reste l'essai sur un vrai iPhone, et le filtre de journal sur `edge` | Le jeton du juge survit à l'installation : il passe dans la requête et le manifeste devient dynamique, pour que `start_url` le porte à chaque lancement |
| [015](../specs/015-classeur-parametrable/) | `classeur-parametrable` | 🟡 **codée, en attente de relecture** (31/08) | Le classeur se règle depuis la console : lien, test d'accès en lecture seule, jeton Google en JSON, et trois modes de bascule. La grille de l'onglet `Import` s'agrandit toute seule quand un dossard attribué à chaud sort de sa largeur |
| [016](../specs/016-page-resultats-projetee/) | `page-resultats-projetee` | 🟡 **codée, en attente de relecture** (31/08) | La page faite pour être projetée : fond clair, la catégorie entière à l'écran, les changements de place qui glissent avec leur flèche, rotation proportionnelle au plateau. `/resultats` supprimée au profit de la racine |
| [017](../specs/017-scratchs-transversaux/) | `scratchs-transversaux` | 🟡 **codée, en attente de relecture** (31/08) | Un scratch avec tout le monde, un féminin, un masculin. La règle du classeur appliquée telle quelle à un groupe plus large — avec l'avertissement qui va avec : les scores d'un scratch ne se comparent qu'entre eux |
| [018](../specs/018-cycle-de-vie-competition/) | `cycle-de-vie-competition` | 🟡 **codée, en attente de relecture** (01/09) | Le cycle d'une édition depuis la console : régler l'état, tester l'accès en **écriture**, importer en mise à jour ou en remplacement, archiver, effacer, et **revoir une édition archivée** dans la vraie page de résultats. Découverte au passage : `Competition.statut` était écrit une fois et plus jamais, ce qui inversait la garde de la spec 015 |

## Specs pressenties

Issues de la [feuille de route](roadmap.md), **pas encore rédigées** — elles
attendent la validation du cadrage et les réponses aux décisions D1→D6.

| # prévu | Nom pressenti | Chantier | Bloqué par |
| --- | --- | --- | --- |


| 008 | `helloasso-import` | import des inscriptions en ligne, rapprochement avec les inscriptions sur place | 005 |
| 009 | `finales` | **tours de finale.** Format tranché le 28/08 : les **N meilleurs de chaque catégorie regrimpent des blocs dédiés**, et le classement final ne tient compte **que du second tour** — le score de qualification ne se reporte pas. Reste à fixer : la valeur de N, et si elle varie selon la catégorie | 004 |


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
