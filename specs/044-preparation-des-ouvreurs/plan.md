# Spec 044 — Plan de travail

> Le plan de test est écrit **avant** l'implémentation. C'est ce qui force à
> penser les cas limites avant d'avoir le nez dans le code.

## 1. Les étapes

### Étape 0 — la porte 2
- [x] Les **trois points de la §6** tranchés le 05/09 : miroir **filtré voie par
      voie**, écriture réservée à `preparation`, plan non redessinable par
      l'ouvreur
- [ ] Adrien valide la spec et la maquette dans leur version corrigée

### Étape 1 — le socle, sans écran
- [ ] `Bloc.numero_couleur` et `Bloc.source` dans `models.py`
- [ ] `schema.COLONNES_AJOUTEES["bloc"]` complété
- [ ] `comptes.OUVREUR` ajouté à `ROLES_CONNUS`
- [ ] `climbcontest/ouverture.py` : `INITIALES`, `inventaire`, `verifier_modifiable`
- [ ] `tests/test_ouverture.py` — la partie lecture

### Étape 2 — la saisie
- [ ] `creer`, `modifier`, `supprimer`, avec l'attribution de rang par `max + 1`
- [ ] `renumeroter`, en **deux passes de tag** (voir architecture §3.2)
- [ ] les garde-fous de F7, tous dans `verifier_modifiable`
- [ ] `tests/test_ouverture.py` — la partie écriture, dont la **stabilité**

### Étape 3 — les routes
- [ ] les huit routes, `exige_role(OUVREUR, ORGANISATEUR)`
- [ ] l'interrupteur `source_blocs`, réservé à l'organisateur
- [ ] le garde d'`importer_blocs` et la sortie de `mirror.synchroniser`
- [ ] `tests/test_admin_ouverture.py` — dont **la matrice des rôles**

### Étape 4 — l'écran
- [ ] `static/console/ouverture.js`, réutilisant `resultats/plan.js`
- [ ] la vue `vueOuvreurs` dans `admin.html`, préfixes respectés
- [ ] le masquage du tiroir pour un compte purement ouvreur
- [ ] un test de navigateur sur le parcours complet

### Étape 5 — la fermeture
- [ ] `docs/specs-index.md` : la ligne 044
- [ ] `CHANGELOG.md` : section `[Non publié]` (⚠️ **toujours en laisser une**)
- [ ] `docs/contraintes-metier.md` §2 : la ligne « Plan des blocs » n'est plus
      une intention
- [ ] **fusion à blanc** avec `feat/008-helloasso-import` et
      `docs/043-...`, les deux suites lancées ensemble, console ouverte au
      navigateur
- [ ] PR, revue de code sur le diff complet, porte 7

---

## 2. Le plan de test

### 2.1 `ouverture.py` — le calcul

| Scénario | Résultat attendu |
| --- | --- |
| Zone avec 3 voies dont 1 sans couleur | compteur `2/3` |
| Zone sans aucune voie | **aucun compteur**, pas `0/0` |
| Zone absente du plan mais portant des voies | remontée dans `hors_plan` |
| Poser Vert sur une voie nue, 6 vertes existantes (rangs 1-6) | rang **7**, tag `<zone>V7` |
| Idem après suppression de la V4 | rang **7** aussi — `max + 1`, jamais `count + 1` |
| Changer Vert → Bleu | l'ancien rang est libéré, un rang bleu est pris, le tag suit |
| Retirer la couleur d'une voie | `numero_couleur` à NULL, la voie redevient « à compléter » |
| `renumeroter` sur le jeu d'essai | par couleur, `1…n`, zones parcourues de A à Z |
| `renumeroter` **deux fois** | la seconde ne change **rien** (idempotence) |
| `renumeroter` sur une permutation circulaire (`JV1↔JV2`) | réussit — les tags s'écrivent en deux passes |
| `renumeroter` avec des voies sans couleur | elles ne bougent pas |
| Les six initiales | deux à deux distinctes, et couvrant exactement `classement.COULEURS` |
| `inventaire` sur 200 voies | **3 requêtes**, mesurées |

### 2.2 Les garde-fous

| Scénario | Résultat attendu |
| --- | --- |
| Écrire sur une compétition `en_cours` | 409, message qui nomme le statut |
| Supprimer une voie qui porte 1 réussite | 409, message qui nomme le nombre |
| Changer la couleur d'une voie qui porte 1 réussite | 409 |
| `renumeroter` alors qu'une réussite existe **ailleurs** dans l'édition | 409 — le geste est global |
| Supprimer un circuit qui porte une voie | 409 |
| Supprimer un circuit vide | 200 |

### 2.3 Les rôles — la matrice

| Compte | `/admin/ouverture` | `/admin/participants` | `/admin/plan` (POST) | `/admin/comptes` | `/admin/moi` |
| --- | --- | --- | --- | --- | --- |
| `ouvreur` | 200 | **403** | **403** | **403** | 200 |
| `organisateur` | **200** | 200 | 200 | 403 | 200 |
| `admin` | 200 | 200 | 200 | 200 | 200 |
| non connecté | 401 | 401 | 401 | 401 | 401 |

⚠️ La ligne `organisateur` / `/admin/ouverture` est celle qui attrape l'oubli de
le nommer dans `exige_role`.

### 2.4 L'interrupteur

| Scénario | Résultat attendu |
| --- | --- |
| Compétition neuve | `source_blocs` = `classeur` |
| Import en mode `classeur` | comportement **identique** à aujourd'hui (test de non-régression sur le rapport) |
| Import en mode `console` | participants importés, **zéro bloc créé ou modifié**, avertissement présent |
| `synchroniser` avec des voies des deux origines | les réussites des voies **importées** partent, celles des voies **console** ne partent pas |
| Blocs d'avant ce lot (`source` à `NULL`) | **ils partent** — la clause `is_(None)` est testée pour elle-même |
| `non_reportables` | compte exactement les réussites sautées ; `en_attente` ne les compte pas |
| Une voie importée dont un ouvreur change la couleur | elle reste reportable (`source` inchangé) |
| Le compteur d'attente après un envoi complet | tombe à zéro, même s'il reste des non-reportables |
| Bascule `classeur` → `console` | les blocs déjà importés sont toujours là |
| Bascule par un `ouvreur` | 403 — c'est une décision d'organisateur |

### 2.5 Le catalogue

| Scénario | Résultat attendu |
| --- | --- |
| Créer, modifier, supprimer une voie | `catalogue_version` incrémentée à chaque fois |
| `renumeroter` | incrémentée **une seule fois**, pas une par voie |
| Un téléphone déjà à jour | reçoit le nouveau catalogue, pas un 304 |

### 2.6 Le navigateur

| Scénario | Résultat attendu |
| --- | --- |
| Connexion d'un compte ouvreur | la vue Ouverture s'ouvre seule, le tiroir n'a qu'une entrée |
| Toucher une zone | le tiroir s'ouvre, le plan se replie **au-dessus**, la zone garde son anneau |
| Ajouter une voie, choisir Vert | le numéro s'affiche sans rechargement, la pastille de la zone bouge |
| Ouvrir la confirmation de renumérotation | l'aperçu vient du **serveur** (`?apercu=1`), pas d'un calcul local |
| Ouvrir à 1280 px | le tiroir est à droite, le plan entier et non voilé |

---

## 3. Ce qui pourrait mal tourner

| Risque | Ce qu'on fait |
| --- | --- |
| **Collision silencieuse dans `admin.html`** avec les branches 008 et 043 | préfixes `ouvreurs*`, section insérée dans le bloc des vues, fusion à blanc avant merge |
| **`uq_bloc_tag` pendant une renumérotation** | écriture des tags en deux passes, testée sur une permutation circulaire |
| **Un import lancé par réflexe efface le travail des ouvreurs** | le garde de F1, et un avertissement dans le rapport plutôt qu'un silence |
| **Le miroir écrit sur les mauvaises lignes du classeur** | filtre voie par voie sur `bloc.source` (F9), avec la clause `is_(None)` pour les blocs d'avant le lot |
| **Le compteur d'attente se fige sur des réussites inenvoyables** | une seule requête pour l'envoi et le compteur, et un second compteur **nommé** pour ce qui ne partira pas |
| **Une couleur hors des six arrive du classeur** | affichée, non modifiable sans choisir parmi les six ; test dédié |
| **Le plan change entre deux séances d'ouverture** | les voies d'une zone disparue remontent dans `hors_plan`, jamais supprimées |
