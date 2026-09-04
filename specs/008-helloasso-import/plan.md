# Plan — spec 008, l'import HelloAsso

Huit lots. Le plan de test est écrit **avant** l'implémentation, comme
[`docs/workflow.md`](../../docs/workflow.md) l'impose.

**L'ordre a changé le 04/09**, et c'est la conséquence la plus utile de la
décision D1 : la règle des catégories et les écrans de la liste **ne dépendent
pas de HelloAsso**. Ils passent devant. Si la clé d'API tarde, la moitié utile
est déjà en production.

---

## Lot 0 — Solder R13, et obtenir une clé *(Adrien)*

- [ ] **Révoquer** la clé de bac à sable publiée dans le `README.md` du dépôt
      public `climbBackEnd`
- [ ] **Retirer** ces lignes, committer, pousser
- [ ] Créer une **association de test** sur `helloasso-sandbox.com` et un
      **formulaire d'événement** qui ressemble à celui du club
- [ ] Générer la clé d'API du bac à sable, et me la donner **hors du dépôt**
- [ ] *(à la recette)* la clé du vrai compte du club

⚠️ Le formulaire de test doit porter un champ **date de naissance** et un champ
**Sexe**. Depuis D1 c'est l'année qui fait la catégorie ; un formulaire de test
sans elle validerait un chemin qui n'existe pas en vrai. Le tarif, lui, n'a plus
aucune importance — tout le monde paie le même.

**Ce lot ne bloque que les lots 4 à 8.** Les lots 1 à 3 avancent sans lui.

---

## Lot 1 — La règle FFME, seule

Aucune interface, aucune base, aucun réseau. Le lot qui se teste le mieux, et
celui dont tout le reste dépend.

- [ ] `climbcontest/categories.py` : `annee_de_reference()`, `circuit()`,
      `bareme()` — **fonctions pures**
- [ ] Les `unders` se déduisent des catégories de l'édition, **rien en dur**

**Fin du lot** : le barème calculé reproduit le tableau FFME publié pour
2025-2026, ligne pour ligne.

---

## Lot 2 — Les catégories dans la console

- [ ] `models.py` : `Participant.annee_naissance`, `Participant.categorie_forcee`,
      + leurs deux lignes dans `COLONNES_AJOUTEES`
- [ ] Écran **Catégories** : le barème, la saison, les compteurs, le verdict
- [ ] `POST /admin/categories/appliquer?apercu=1` — l'avant / après **sans écrire**
- [ ] Le bouton qui se **maintient** (spec 027), et le refus de toucher un
      inscrit sans année
- [ ] *(D10)* une catégorie corrigée à la main est protégée, comptée à part,
      forçable explicitement
- [ ] Ajout manuel : champ **Année**, et la proposition dans les deux sens (D8)

---

## Lot 3 — La liste des participants

Indépendant de HelloAsso lui aussi. C'est le lot qui change le geste quotidien.

- [ ] Colonne **Source** : `G` / `H` / `M`, plusieurs pastilles possibles
- [ ] Filtre **Catégorie** dans la barre de la liste
- [ ] **Sélection pour impression** : bande ocre, colonne de cases, *Tout
      sélectionner*, compteur, bouton d'impression, *Annuler*
- [ ] **Retirer la tuile « Imprimer les fiches »**
- [ ] **Crayon** et édition en ligne : `PATCH /admin/participants/<id>`
- [ ] Listes déroulantes club et catégorie avec **« + Créer… »**, formatage
      appliqué à ce qui est créé
- [ ] L'édition respecte la règle du dossard (spec 002)

**Fin du lot** : les écrans se comportent comme la maquette validée.

---

## Lot 4 — Parler à HelloAsso

- [ ] `helloasso/client.py` — `ClientHelloAsso`, `ErreurHelloAsso`
- [ ] Jeton **en base**, rafraîchissement sous le verrou `helloasso_jeton`
- [ ] Secret dans `shared/secrets/helloasso.json`, jamais renvoyé, jamais journalisé
- [ ] Pagination : arrêt sur **tableau vide**
- [ ] Bascule production / bac à sable par le réglage
- [ ] `tools/dump_helloasso.py` — lecture seule, refuse de démarrer sans
      `CLIMBCONTEST_HELLOASSO_ENV`
- [ ] `.gitleaks.toml` : motif pour une clé HelloAsso

**Fin du lot** : le formulaire de test s'affiche depuis le Mac, avec ses champs
et les réponses vues.

---

## Lot 5 — Le relevé et le rapprochement

- [ ] `models.py` : table `inscription`
- [ ] `helloasso/releve.py` : la boucle, la transformation, un `commit` par
      article, un `Rapport` sur le modèle de `sheets/importer.py`
- [ ] `helloasso/rapprochement.py` : `cle()`, `confronter()` — **pures**
- [ ] Création par `contest.ajouter_participant_numerote()`, `source="helloasso"`
- [ ] Les trois champs et les valeurs de genre, réglables depuis la console

---

## Lot 6 — La vue Inscriptions

- [ ] Les trois piles, les cartes de rapprochement à deux colonnes
- [ ] **Le même** mécanisme de sélection d'impression qu'au lot 3
- [ ] La **pastille** du bandeau, comptée dans `/admin/moi`
- [ ] Rafraîchissement toutes les 30 s
- [ ] Rappel dans *Ajouter un participant* quand une inscription porte le même nom

---

## Lot 7 — Le fil, et le reste du système

- [ ] `helloasso/planificateur.py` : cadence variable, verrou, ne meurt jamais,
      ne répète pas sa plainte
- [ ] Démarrage **conditionnel** : pas de clé → pas de fil → pas d'appel réseau
- [ ] Arrêt net sur clé refusée (401/403)
- [ ] `/health` expose la dernière erreur
- [ ] `cycle.py` : l'effacement emporte les inscriptions ; l'archivage non
- [ ] `CHANGELOG.md` sous `## [Non publié]`, `docs/specs-index.md`,
      `docs/contraintes-metier.md` §3 qui cesse d'être au futur

---

## Lot 8 — La recette

- [ ] Une inscription passée à la main sur le formulaire de test apparaît en
      **moins de 90 s**, compétition `en_cours`
- [ ] Une commande à **deux** enfants crée **deux** participants
- [ ] Une annulation depuis le back-office fait remonter la ligne
- [ ] Quatre workers gunicorn sur la VM : **un seul** rafraîchissement de jeton
- [ ] Bascule sur la clé de production, formulaire réel, relevé à blanc

---

## Plan de test

### La règle FFME — `tests/test_categories.py`

Aucune base, aucun réseau. C'est le test qui prouve quelque chose.

| Scénario | Attendu |
| --- | --- |
| **Le tableau FFME 2025-2026 entier**, référence 2026 | U11 → 2016-2017, U13 → 2014-2015, U15 → 2012-2013, U17 → 2010-2011, U19 → 2008-2009, U21 → 2006-2007 |
| Compétition du 15/11/2026 | Référence **2027** |
| Compétition du 15/03/2027 | Référence **2027** — la même saison |
| Compétition du 31/08/2026 | Référence **2026** — la saison précédente |
| Compétition du 01/09/2026 | Référence **2027** — la bascule |
| Né en 2015, référence 2027 : âge 12 | **U13**, jamais U15 — le plus petit gagne |
| Né en 2016, référence 2027 : âge 11 | **U13** |
| Né en 2017, référence 2027 : âge 10 | **U11** |
| Né en 1990 | **Aucun Under** — catégorie vide, pas d'exception |
| Catégories de l'édition = `U11 F`, `U13 H` | `unders = {11, 13}` — rien d'autre n'existe |
| Une édition sans aucune catégorie en `U` | Barème vide, aucune exception |
| Année aberrante (1015, 2916) | Catégorie vide, mise en attente |

### Le barème appliqué — `tests/test_categories_appliquer.py`

| Scénario | Attendu |
| --- | --- |
| 12 participants dont la catégorie change | L'aperçu en liste **12**, et n'écrit **rien** |
| Application réelle | 12 écrits, 110 intacts |
| Participant **sans année** | **Jamais** touché |
| Participant `categorie_forcee` *(D10)* | Non touché, compté à part |
| Le même appliquer deux fois | La seconde fois ne change rien |

### Le rapprochement — `tests/test_helloasso_rapprochement.py`

| Scénario | Attendu |
| --- | --- |
| Liste vide | `NOUVEAU` |
| « Dupont Jean-Luc » vs « DUPONT jean luc » | Même clé |
| « Roc N'Potes » vs « Roc n'potes » | Même clé |
| Nom + prénom + club identiques | `MEME_PERSONNE` |
| Nom + prénom identiques, club différent | `A_TRANCHER(club_different)` |
| Nom + prénom identiques, club absent d'un côté | `A_TRANCHER` |
| Rattachement dont les catégories diffèrent | `MEME_PERSONNE`, **signalé** |
| Trois homonymes, un seul du bon club | `MEME_PERSONNE` sur le bon |

### Le relevé — `tests/test_helloasso_releve.py`

Réseau doublé, données en fixtures.

| Scénario | Attendu |
| --- | --- |
| **Le même article relevé dix fois** | **Une** inscription, **un** participant |
| **Une commande, deux articles** | **Deux** inscriptions, **deux** participants |
| Année absente | `a_trancher`, catégorie vide |
| Année hors barème | `a_trancher`, l'année affichée |
| Genre indéterminé | `a_trancher` |
| Réponse de genre inconnue | Genre indéterminé — **jamais `H` par défaut** |
| Article sans `user` | Nom repris du payeur, motif `sans_nom` |
| Annulé après intégration | `a_trancher`, **participant intact** |
| Payeur complet dans la réponse | **Rien de lui n'est écrit** |
| Le tarif, quel qu'il soit | **Sans effet** |
| `continuationToken` toujours renvoyé, données vides | Arrêt — **pas de boucle infinie** |
| Un article sur cent lève | 99 écrits, l'erreur au rapport |
| Deuxième relevé | `from` = dernier `updatedAt` − 5 min |

### Le jeton — `tests/test_helloasso_client.py`

| Scénario | Attendu |
| --- | --- |
| Pas de clé posée | `ErreurHelloAsso`, **zéro appel réseau** |
| Jeton valide en base | **Aucun** appel à `/oauth2/token` |
| **Deux appels concurrents sur un jeton expiré** | **Un seul** rafraîchissement |
| `401` en cours de relevé | Un rafraîchissement, **un seul** réessai |
| `401` sur le rafraîchissement | « Clé à reconnecter », le fil **s'arrête** |
| `429` | Retenté à la cadence normale, pas d'insistance |
| Le secret dans un journal ou une réponse | **Aucune occurrence** |

### La console — `tests/test_console_participants.py`

| Scénario | Attendu |
| --- | --- |
| `PATCH` d'un participant | Formatage appliqué : `u13f` → `U13 F` |
| `PATCH` du dossard d'un participant **avec réussites** | **409**, message explicite |
| `PATCH` d'un champ inconnu | Ignoré, pas d'erreur 500 |
| Impression d'une sélection de 3 dossards | Trois fiches, dans l'ordre des dossards |
| Sélection vide | Bouton inactif, route refusant en 400 |
| Ajout avec année seule | Catégorie proposée, participant créé |
| Ajout avec catégorie seule | Créé, année vide |
| Sources d'un participant rapproché | **Deux** pastilles |
| Aucune clé HelloAsso | Aucune pastille `H`, aucune entrée de menu |

### Fixtures

`fixtures/helloasso/` — des réponses **fabriquées à la main**.

> ⚠️ Règle 7 du `CLAUDE.md` : un export du vrai formulaire contiendrait des noms
> de mineurs et les coordonnées de leurs parents. Les fixtures portent des noms
> inventés ; la structure vient de la documentation, pas d'un dump.

| Fichier | Contenu |
| --- | --- |
| `items-page-1.json`, `items-page-2.json`, `items-vide.json` | Trois pages, la dernière vide |
| `item-annule.json` | Un `Canceled` |
| `item-sans-user.json` | `user` absent, `payer` présent |
| `commande-fratrie.json` | Une commande, deux articles |
| `formulaire-public.json` | Champs et réponses vues à découvrir |

### Non-régression

- [ ] `pytest` complet vert
- [ ] `tools/verify_ranking.py` sort toujours « 196 conformes, 0 écart »
- [ ] `gitleaks` passe

---

## Environnement de test

`venv/` et `.venv-dev/` n'ont pas `pytest`. Un venv jetable, avec les **deux**
fichiers de dépendances :

```bash
python3 -m venv /tmp/venv-008 && /tmp/venv-008/bin/pip install -q \
  -r requirements.txt -r requirements-dev.txt
/tmp/venv-008/bin/python -m pytest -q
```

---

## Risques

| Risque | Ce qu'on fait |
| --- | --- |
| 🔴 **Le formulaire du club ne demande pas la date de naissance.** D1 tombe | Vu au **lot 4**, avec `dump_helloasso.py`, avant qu'une ligne de relevé soit écrite. Les lots 1 à 3 restent valides quoi qu'il arrive |
| **Le formulaire ne demande pas le genre** | Toutes les inscriptions en « à trancher ». Vu au même moment |
| **La FFME change ses tranches** | Le barème se recalcule, et « Corriger à la main » existe pour ne pas attendre une release |
| **« Appliquer à tous » défait le travail de quelqu'un** | C'est **D10**. Aperçu obligatoire, bouton à maintenir, et protection des corrections manuelles |
| **`admin.html` est disputé par les autres sessions** | Les ajouts sont additifs ; le **retrait** de la tuile d'impression est la seule suppression, et elle se verra au conflit |
| **Le relevé écrit pendant qu'un juge scanne** | Un `commit` par article, SQLite en **WAL**. Re-mesuré au lot 8 |
| **Le quota d'authentification** | 2 appels/h contre 50 autorisés. Mesuré dans le journal au lot 8 |
