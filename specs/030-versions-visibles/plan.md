# Plan — spec 030

## Ordre d'implémentation

L'ordre n'est pas indifférent : **le serveur d'abord**, parce que les deux
clients lisent ce qu'il expose, et qu'un écran branché sur un contrat qui n'existe
pas encore se teste avec des données inventées.

- [ ] **1. `version.py`** — module neuf : `VERSION`, `posee_le()`. `sante.py`
      l'importe et cesse de lire le fichier lui-même. Aucun changement de
      comportement de `/health`.
- [ ] **2. La table `appareil`** — modèle, et `contest.enregistrer_annonce()`.
      Vérifier d'abord `grep -rn "class Appareil\|def enregistrer_annonce"` :
      deux sessions ont déjà, cette semaine, ajouté le même nom dans un fichier
      partagé sans que git ne signale rien.
- [ ] **3. `routes/catalogue.py`** — l'annonce **avant** la garde `a_jour`,
      `X-Server-Version` et `Cache-Control: no-cache, private` sur les **deux**
      branches. Rien de ce qui est ajouté ne peut lever : l'annonce est
      enveloppée, un échec se journalise et le catalogue part quand même.
- [ ] **3 bis. `routes/lot.py`** — la même annonce à la réception d'un lot, mais
      **sans** `catalogue_version` : recevoir un lot ne prouve rien sur le
      catalogue détenu. C'est la redondance de F8, celle qu'aucun cache
      n'absorbe.
- [ ] **4. `contest.appareils()`** — union des téléphones vus et des téléphones
      qui ont envoyé, avec les nouveaux champs.
- [ ] **5. `GET /admin/versions`** et `/admin/appareils` étendue, avec le
      compte `annonces_perdues` — la détection de F8.
- [ ] **6. La console** — pied de tiroir, carte « Versions en circulation »,
      deux colonnes dans le tableau.
- [ ] **7. La PWA — affichage** — `meta` de version, sections « Catalogue » et
      « Application », verdicts.
- [ ] **8. La PWA — les deux boutons** — « Retélécharger maintenant », puis
      « Mettre à jour et redémarrer » avec son message de service worker.
- [ ] **9. Relire le diff en entier** (porte 5), `CHANGELOG.md`, index des specs.

## Plan de test

Écrit avant l'implémentation.

### Serveur — `tests/test_versions.py` (neuf)

| Module | Scénario | Attendu |
| --- | --- | --- |
| catalogue | requête sans en-tête d'annonce | 200, corps et ETag inchangés, aucune ligne `appareil` |
| catalogue | requête avec `X-Device-Id`, catalogue neuf | 200 + ligne `appareil` créée, `catalogue_version` = version courante |
| catalogue | **requête avec `X-Device-Id` et `If-None-Match` à jour** | **304 + ligne `appareil` mise à jour** (le cas majoritaire) |
| catalogue | deux requêtes du même appareil | une seule ligne, `vu_le` avancé, `premiere_vue_le` inchangé |
| catalogue | `X-Device-Name` percent-encodé avec accents | nom décodé et stocké |
| catalogue | `X-Device-Name` mal encodé (`%ZZ`) | 200, nom absent, **aucune erreur 500** |
| catalogue | `X-App-Version` de 300 caractères | tronqué à 20, pas d'exception |
| catalogue | en-tête `X-Server-Version` | présent en 200 **et** en 304 |
| catalogue | en-tête `Cache-Control` | `no-cache, private` en 200 **et** en 304 |
| lot | lot avec `appareil.app` | `version_app` et `vu_le` mis à jour, `catalogue_version` et `catalogue_vu_le` **inchangés** |
| lot | lot sans `appareil` | comportement identique à aujourd'hui, aucune ligne créée |
| admin | appareil qui envoie mais ne s'annonce plus depuis 20 min | `annonces_perdues: 1` |
| admin | appareil sans `version_app` qui envoie (Android) | `annonces_perdues: 0` — l'alerte ne vise que ceux qui savent s'annoncer |
| admin | appareil simplement éteint (rien depuis 1 h) | `annonces_perdues: 0`, il ressort « muet » |
| catalogue | la table `appareil` est inaccessible (simulée) | le catalogue part quand même, l'échec est journalisé |
| version | pas de fichier `VERSION` | `"dev"`, `posee_le()` à `None`, `/health` inchangé |
| admin | `GET /admin/versions` sans session | 401 |
| admin | `GET /admin/versions` connecté | version, numéro de catalogue, comptes de participants et de blocs |
| admin | `GET /admin/appareils` — un appareil annoncé, zéro réussite | présent, `reussites: 0`, `annonce: true` |
| admin | `GET /admin/appareils` — un appareil avec réussites, jamais annoncé | présent, `version_app: null`, `annonce: false` |
| admin | un appareil vu il y a 3 jours, sans réussite sur l'édition | absent de la liste |
| admin | comptes `a_jour` / `en_retard` | comptés sur l'égalité stricte des numéros |

### PWA — `tests/js/api.test.mjs` (étendu), `tests/js/version.test.mjs` (neuf)

| Module | Scénario | Attendu |
| --- | --- | --- |
| api | `telechargerCatalogue(42)` | en-tête `If-None-Match: "42"` |
| api | `telechargerCatalogue(null)` — **le bouton** | **aucun `If-None-Match`, aucun `?depuis`** |
| api | annonce fournie | `X-Device-Id`, `X-Device-Name` encodé, `X-App-Version` présents |
| api | annonce absente | aucun de ces en-têtes (pas d'en-tête vide) |
| api | réponse 304 | `X-Server-Version` remonté à l'appelant |
| api | réponse 200 | catalogue **et** version serveur remontés |
| api | réseau coupé | `etat: "echec"`, aucune exception |
| version | version locale = version serveur | verdict « à jour » |
| version | versions différentes | verdict « en retard », bouton de mise à jour offert |
| version | version serveur inconnue (jamais joint) | aucun verdict affiché — on ne dit pas « à jour » sans le savoir |

### Bout en bout — `tests/test_pwa_juge.py` (étendu)

| Module | Scénario | Attendu |
| --- | --- | --- |
| pwa | `GET /juge` | la coquille porte `<meta name="climbcontest-version">` |
| pwa | `GET /juge` en développement | la balise vaut `dev`, la page se rend |

### Navigateur — `tests/test_console_lisible.py` ou test neuf

| Module | Scénario | Attendu |
| --- | --- | --- |
| console | ouverture de n'importe quelle vue | le pied de tiroir affiche version et numéro de catalogue |
| console | vue Téléphones, un appareil en retard | sa ligne porte le numéro divergent **écrit**, pas seulement une couleur |

### Non-régression

| Module | Scénario | Attendu |
| --- | --- | --- |
| catalogue | les tests existants de `test_catalogue_et_cle.py` | verts sans modification |
| catalogue | `test_catalogue_entre_competitions.py` (dont le test de la PR #85) | verts : la forme du corps et l'ETag ne changent pas |
| lot | `test_lot.py` | vert : le contrat du lot n'est pas touché |
| contrat | `test_contrat_application.py` | vert : l'app Android continue sans annonce |

## Vérifications manuelles (celles qu'aucun test ne remplace)

- [ ] Sur un vrai iPhone : l'écran Réglages, le bouton de retéléchargement, puis
      la mise à jour et le redémarrage.
- [ ] Mode avion : les deux boutons refusent proprement, l'application reste
      utilisable et la file intacte.
- [ ] Deux téléphones, dont un laissé sur l'ancienne coquille : la console
      montre bien lequel est en retard.
