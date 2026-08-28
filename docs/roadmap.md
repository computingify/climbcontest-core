# Feuille de route

> **Ordre révisé le 28/08 par Adrien : on commence par l'hébergement.** Le
> chantier 4 passe en tête — spec [001](../specs/001-vm-climbcontest/), rédigée,
> en attente de validation. Les autres suivent dans l'ordre initial.

Proposition à valider ensemble. Rien n'est engagé : chaque chantier deviendra
une spec dans `specs/` (spec + architecture + plan), validée par toi avant la
moindre ligne de code — voir [workflow.md](workflow.md).

Les numéros de risque (`R1`…) renvoient à
[etat-des-lieux.md §6](etat-des-lieux.md#6-anomalies-et-risques).

---

## Chantier 1 — Fiabiliser l'existant

**Objectif : qu'aucune réussite ne puisse être perdue, et que le juge ne soit
jamais bloqué par le réseau.**

### 1a. Le backend arrête de perdre des données

| Quoi | Règle | Corrige |
| --- | --- | --- |
| Table `Success` persistée | Toute réussite est écrite en base **avant** de répondre au juge | R2, R4 |
| Contrainte d'unicité `(climber_id, bloc_id)` | Un doublon est absorbé, pas compté deux fois | R12 |
| Google Sheets devient un *miroir*, plus la source | Le worker rejoue depuis la base ce qui n'est pas encore synchronisé | R3 |
| Fin du `drop_all()` au démarrage | Migration/initialisation explicite, une seule fois | R1 |
| Réimport du classeur sur commande | Une route dédiée, plus jamais dans le chemin d'une requête juge | R7 |
| Import tolérant | Lignes courtes acceptées, homonymes gérés, rapport d'import lisible | R5, R6 |
| Clé partagée sur les routes d'écriture | En-tête `X-Api-Key`, lue depuis l'environnement | R8 |

Le point le plus important : **la base devient la source de vérité, le classeur
devient une projection**. C'est ce qui rend possible le classement live, la
reprise après panne et l'audit d'une contestation.

### 1b. L'app juge devient locale d'abord

| Quoi | Effet |
| --- | --- |
| Catalogue téléchargé au démarrage (~10 ko) | Validation des QR **sans réseau**, réponse instantanée |
| File d'attente persistante des réussites | Le juge continue même hors-ligne (R9) |
| Envoi par lots + clé d'idempotence | ~30× moins de requêtes, rejeu sans doublon |
| Indicateur « n réussites en attente » | Le juge voit ce qui n'est pas encore parti |
| `hostnameVerifier` retiré | R10 |
| URL du serveur configurable (build ou réglage) | Bascule Render ↔ VM sans recompiler |

C'est la vraie réponse à « minimiser le volume échangé » : le chiffrage est en
[etat-des-lieux.md §7](etat-des-lieux.md#7-volume-de-données-échangé--mesure-et-cible).

### 1c. Filet de sécurité

- Tests pytest sur une base en mémoire (jamais sur la prod, R11).
- Les scripts de charge déplacés hors de `tests/` et pointés sur un
  environnement de recette.
- Un scénario de bout en bout rejouable : 120 grimpeurs × 30 blocs.

---

## Chantier 2 — Le classement côté backend et la page live

**Objectif : le classeur n'est plus indispensable pendant la compétition, et
tout le monde voit les résultats en direct.**

### 2a. Reprendre la mécanique du classeur

> **Décisions d'Adrien du 28/08** : la **validation par couleur** est reprise,
> mais comme **option activable par compétition** (elle n'était pas active en
> novembre 2025 et le classeur en propose plusieurs variantes). La **saisie
> manuelle** est reprise aussi. Toutes deux se pilotent depuis une **page de
> paramétrage**, qui gère également la **connexion au classeur Google et la
> vérification de l'accès**. Ça devient la spec 005 `admin-console`.

La branche `feature/ResultAlgorithm` a déjà : le modèle (`Success`, `Ranking`,
`climber_category_bloc`), l'algorithme `1000 / nombre de réussites`, et une
page `/results` en Vue 3. C'est une base solide **mais elle n'a jamais été
mergée ni confrontée aux formules réelles du classeur**.

Étapes :

1. ~~Récupérer le classeur et documenter les formules~~ — **fait**, voir
   [technical/classeur-google.md](technical/classeur-google.md).
2. ~~Écrire la règle de calcul noir sur blanc~~ — **fait**, et validée : elle
   reproduit 196 scores et rangs réels sur 196 (novembre 2025).
3. Écrire la spec 003 à partir de cette règle, en tranchant les deux mécanismes
   optionnels (validation par couleur, saisie manuelle).
4. Implémenter, avec `tools/verify_ranking.py` comme test d'acceptation
   obligatoire : tant qu'il ne sort pas « 0 écart », on ne bascule pas.
5. Reprendre ce qui est bon de la branche, corriger ce qui ne l'est pas (voir
   les réserves ci-dessous).

Réserves connues sur la branche telle quelle :

- `google_sheets_reader.py` utilise `sqlalchemy.dialects.postgresql.insert` →
  ne fonctionne que sur PostgreSQL ;
- l'association `climber_category_bloc` fait pointer un `bloc_id` sur le
  *numéro du classeur* alors que la clé étrangère vise la clé primaire de
  `Bloc` — ça ne marche que tant que les deux coïncident par hasard ;
- le classement est recalculé intégralement toutes les 30 s, pour toutes les
  catégories ;
- pas de contrainte d'unicité sur `Success` (R12) ;
- **elle ne filtre pas les réussites par circuit** — c'est l'écart le plus grave,
  il gonfle le score de 17 grimpeurs sur 98 ;
- **son « scratch » est global** alors que celui du classeur est par circuit.

### 2b. La page résultats

L'effet « ouah » que tu veux, avec les contraintes réelles :

- **écran de la salle** (grand affichage, rotation automatique des catégories,
  podium, animation de montée/descente) ;
- **téléphone spectateur** : même page, responsive, ou une vue « mon dossard »
  où l'on scanne son propre QR pour voir sa place. À arbitrer.
- Rafraîchissement : polling court côté serveur avec cache (simple, robuste),
  ou SSE. Pas de WebSocket, ça n'apporte rien ici.
- Un cache d'une à deux secondes suffit pour absorber 200 spectateurs sans
  effort.

⚠ Point à trancher : rendre la page publique sur Internet **expose ta ligne
domestique**. Reverse proxy + cache + limitation de débit, et pas de route
d'écriture accessible depuis l'extérieur.

---

## Chantier 3 — L'iPhone, sans payer

Tu ne veux pas payer les 99 $/an du programme développeur Apple. Les options :

| Option | Coût | Verdict |
| --- | --- | --- |
| App Store / TestFlight | 99 $/an | ❌ exclu par ta contrainte |
| Sideload via AltStore / compte gratuit | 0 € | ❌ à réinstaller tous les 7 jours, ingérable pour des juges bénévoles |
| **PWA (web app installable)** | **0 €** | ✅ **recommandé** |

### Pourquoi la PWA est la bonne réponse ici

- Safari iOS sait accéder à la caméra depuis une page web depuis iOS 14.3 ; une
  PWA ajoutée à l'écran d'accueil se comporte comme une app.
- Le scan QR fonctionne avec `BarcodeDetector` (natif sur Chrome Android) et une
  bibliothèque WASM en repli sur Safari.
- La file d'attente hors-ligne du chantier 1b se fait avec un service worker +
  IndexedDB : même comportement que sur Android.
- **Une seule base de code** pour l'app juge iOS *et* la page résultats, servie
  par le même backend, mise à jour sans passer par un store.
- Zéro compte développeur, zéro validation, zéro délai de publication.

### Ce que ça implique

- L'app Android native reste en place (elle marche, elle est publiée) tant que
  la PWA n'a pas fait ses preuves sur une vraie compétition.
- À terme, tu peux garder les deux, ou tout basculer sur la PWA et abandonner
  la publication Play Store. À décider quand la PWA aura tourné en vrai.
- Les prototypes `climbContestApp/` (Flutter) et `ClimbContestIos/` (SwiftUI)
  sont à supprimer : ils ne servent aucun de ces scénarios.

---

## Chantier 4 — Hébergement à la maison ← **on commence par là**

**Spec [001](../specs/001-vm-climbcontest/) rédigée le 28/08**, en attente de
validation. Elle couvre la VM 110, la chaîne de livraison par tirage avec
changelog contraignant, l'exposition `climbcontest.adn-dev.fr`, et surtout les
**contrôles adaptés à une VM qui ne tourne que pendant les compétitions**.

Faisabilité : voir [etat-des-lieux.md §8](etat-des-lieux.md#8-une-vm-à-la-maison-est-ce-que-ça-suit).
En résumé : la charge est ridicule pour une VM, le sujet est le réseau.

Points à cadrer :

1. **Exposition HTTPS** — à mutualiser avec ton chantier `domotique.adn-dev.fr`
   sur Proxmox : même reverse proxy, sous-domaine dédié
   (`climbcontest.adn-dev.fr` par exemple).
2. **Panne de lien** — que se passe-t-il si Internet tombe côté maison **ou**
   côté salle ? Le mode hors-ligne de l'app couvre la salle. Pour la maison, il
   faut décider : on accepte l'interruption de la page résultats, ou on prévoit
   un backend de secours sur place.
3. **Option « backend à la salle »** — un mini-PC ou un Pi en réseau local le
   jour J, avec réplication vers la maison après coup. Plus robuste, plus de
   logistique. À arbitrer selon la qualité du réseau de la salle.
4. **Sauvegardes** — dump de la base après chaque compétition, archivé.

---

## Ordre proposé

```
0. préparation des dépôts (~30 min)            ← à valider, voir preparation-depots.md
1. spec 001  VM + livraison + exposition       ← rédigée, en attente de validation
2. spec 002  backend fiable (source de vérité)
3. spec 003  app juge locale d'abord
4. spec 004  moteur de classement (+ option couleur)
5. spec 005  console d'administration (saisie manuelle, paramétrage, classeur)
6. spec 006  page résultats live
7. spec 007  PWA juge (iPhone)
```

Compétition attendue **vers novembre 2026** (~3 mois). Le gel de repli
([plan-de-repli.md](plan-de-repli.md)) couvre le cas où la refonte ne serait pas
prête : on repart sur Render avec la version 2025-2026.

---

## Décisions en attente

| # | Sujet | Pourquoi ça bloque |
| --- | --- | --- |
| ~~D1~~ | ~~Accès au classeur Google~~ | **Résolu** — accès obtenu, 3 éditions analysées |
| ~~D2~~ | ~~Règle de classement exacte~~ | **Résolue** — algorithme validé sur données réelles |
| ~~D2b~~ | ~~Validation par couleur et saisie manuelle~~ | **Tranché le 28/08** : les deux sont reprises, la couleur en option par compétition, le tout piloté depuis une page de paramétrage |
| ~~D3~~ | ~~Monorepo ou dépôts séparés~~ | **Tranché** : pas de monorepo, `climbcontest-core` devient le dépôt pivot. Argumentaire dans [preparation-depots.md](preparation-depots.md) |
| D4 | Page résultats publique ou réservée au réseau de la salle | Change l'architecture d'exposition |
| D5 | Date de la prochaine compétition | Change l'ordre des chantiers |
| D6 | Sort de l'app Android native une fois la PWA prête | Peut attendre |
