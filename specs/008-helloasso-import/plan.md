# Plan — spec 008, l'import HelloAsso

Six lots. Les cinq premiers sont livrables séparément ; **le lot 0 est un
préalable, et il n'est pas de moi**.

Le plan de test est écrit **avant** l'implémentation, comme
[`docs/workflow.md`](../../docs/workflow.md) l'impose : c'est ce qui force à
regarder les cas limites avant d'avoir le nez dans le code.

---

## Lot 0 — Solder R13, et obtenir une clé *(Adrien)*

Rien ne commence avant.

- [ ] **Révoquer** la clé de bac à sable publiée dans le `README.md` du dépôt
      public `climbBackEnd` (`clientId` `e417b84a…`, secret, deux jetons)
- [ ] **Retirer** ces lignes du `README.md`, committer, pousser
- [ ] Créer une **association de test** sur `helloasso-sandbox.com` et un
      **formulaire d'événement** qui ressemble à celui du club : quelques tarifs
      nommés comme des catégories, un champ *Club*, un champ *Date de naissance*
- [ ] Générer la clé d'API du bac à sable, et me la donner **hors du dépôt**
- [ ] *(plus tard, à la recette)* la clé d'API du vrai compte du club

> Je ne peux pas faire ces gestes : ils demandent d'être connecté au compte
> HelloAsso du club. C'est la décision **D7**.

---

## Lot 1 — Parler à HelloAsso

Le socle. Aucune interface, aucune table : juste savoir demander.

- [ ] `helloasso/client.py` — `ClientHelloAsso`, `ErreurHelloAsso`
- [ ] Jeton **en base** (`reglage`), rafraîchissement sous le verrou
      `helloasso_jeton`
- [ ] Secret dans `shared/secrets/helloasso.json`, jamais renvoyé, jamais
      journalisé
- [ ] Pagination `continuationToken` — arrêt sur **tableau vide**
- [ ] Bascule production / bac à sable par le réglage, pas par une constante
- [ ] `tools/dump_helloasso.py` : liste les formulaires, puis les tarifs et les
      champs personnalisés d'un formulaire. **Lecture seule**, refuse de
      démarrer sans `CLIMBCONTEST_HELLOASSO_ENV` explicite
- [ ] `.gitleaks.toml` : motif pour une clé HelloAsso

**Fin du lot** : `python3 tools/dump_helloasso.py --formulaires` affiche le
formulaire de test du bac à sable.

---

## Lot 2 — Le cœur : relever, comprendre, rapprocher

Toujours aucune interface. C'est le lot qui se teste le mieux.

- [ ] `models.py` : table `inscription`, constantes d'état et de motif
- [ ] `helloasso/correspondance.py` : découverte des tarifs et des champs d'un
      formulaire ; lecture / écriture dans `competition.options["helloasso"]`
- [ ] `helloasso/rapprochement.py` : `cle()`, `confronter()` — **fonctions
      pures**, aucune base
- [ ] `helloasso/releve.py` : la boucle, la copie élaguée, un `commit` par
      article, un `Rapport` sur le modèle de `sheets/importer.py`
- [ ] Création du participant par `contest.ajouter_participant_numerote()`,
      `source="helloasso"` — **le même chemin que le bouton « Ajouter »**

**Fin du lot** : un relevé sur le bac à sable crée les participants et remplit
les trois piles, vérifié en `flask shell`.

---

## Lot 3 — La console *(ne commence qu'après validation de la maquette)*

- [ ] Vue **Inscriptions** : les trois piles, la carte de doublon à deux
      colonnes, le rafraîchissement toutes les 30 s
- [ ] Page **HelloAsso** dans *Administration* : clé, environnement, formulaire,
      correspondance, « Relever maintenant »
- [ ] **Pastille** dans le bandeau, comptée dans `/admin/moi`
- [ ] « Imprimer le dossard » → `/admin/dossards?dossard=…`, et la ligne passe
      en *faite*
- [ ] Rappel dans *Ajouter un participant* quand une inscription en ligne porte
      le même nom
- [ ] Les dix routes, avec leurs codes de refus

**Fin du lot** : les écrans se comportent comme la maquette validée.

---

## Lot 4 — Le fil, et le reste du système

- [ ] `helloasso/planificateur.py` : cadence variable, verrou, ne meurt jamais,
      ne répète pas sa plainte
- [ ] Démarrage **conditionnel** : pas de clé → pas de fil → pas d'appel réseau
- [ ] Arrêt net sur clé refusée (401/403), pour ne pas brûler le quota
- [ ] `/health` expose la dernière erreur HelloAsso
- [ ] `cycle.py` : « Effacer les données du serveur » emporte les inscriptions
- [ ] L'archivage (spec 018) **n'emporte pas** les inscriptions
- [ ] `CHANGELOG.md` sous `## [Non publié]`, `docs/specs-index.md`,
      `docs/contraintes-metier.md` §3 qui cesse d'être au futur

---

## Lot 5 — La recette, sur le bac à sable puis en vrai

- [ ] Une inscription passée à la main sur le formulaire de test apparaît dans
      la console **en moins de 90 s**, compétition `en_cours`
- [ ] Une annulation depuis le back-office fait remonter la ligne
- [ ] Un tarif ajouté en cours de route met ses inscrits en attente, et le
      bouton « rejouer » les repêche
- [ ] Quatre workers gunicorn sur la VM : **un seul** rafraîchissement de jeton
      (compté dans le journal)
- [ ] Bascule sur la clé de production, formulaire réel, relevé à blanc
      *(la compétition n'est pas ouverte : rien n'est créé)*

---

## Plan de test

Trois niveaux, et le premier est celui qui attrape les vrais défauts.

### Fonctions pures — `tests/test_helloasso_rapprochement.py`

Aucune base, aucun réseau. Une table de cas.

| Scénario | Attendu |
| --- | --- |
| Liste vide, un candidat | `NOUVEAU` |
| « Dupont Jean-Luc » vs « DUPONT jean luc » | Même clé |
| « Roc N'Potes » vs « Roc n'potes » | Même clé |
| Homonyme, deux dates de naissance identiques | `MEME_PERSONNE(id)` |
| Homonyme, deux dates différentes | `DEUX_PERSONNES` |
| Homonyme, une date manque | `A_TRANCHER` |
| Homonyme, **les deux** dates manquent | `A_TRANCHER` |
| Trois homonymes dont un seul de même date | `MEME_PERSONNE` sur le bon |
| Prénom composé d'un côté seulement | `A_TRANCHER`, jamais `NOUVEAU` en silence |
| Nom avec espace final, casse mixte, accents | Même clé |

### Correspondance et transformation — `tests/test_helloasso_releve.py`

Le réseau est un **double** ; les données viennent de fixtures.

| Scénario | Attendu |
| --- | --- |
| Article `Processed` complet | Inscription `a_imprimer`, participant créé, dossard attribué |
| **Le même article relevé dix fois** | **Une** inscription, **un** participant |
| Article dont le tarif n'est dans aucune correspondance | `a_trancher`, motif `categorie_inconnue`, catégorie vide |
| Article sans `user`, `payer` présent | `a_trancher`, motif `sans_nom`, nom repris du payeur |
| Article `Canceled` jamais vu | Aucune inscription |
| Article `Canceled` **déjà intégré** | `a_trancher`, motif `annulee_apres_coup`, **participant intact** |
| Commande à deux articles (fratrie) | **Deux** inscriptions, deux participants |
| `customFields` absent (`withDetails` oublié) | Club et date vides, l'inscription passe quand même |
| Nom en capitales, club en minuscules | `formatage` appliqué, club en sigle préservé |
| Adresse et téléphone du payeur présents | **Absents de la base**, y compris de `detail` |
| Pagination : 3 pages puis un tableau vide | 3 pages lues, arrêt sur le vide |
| Pagination : `continuationToken` toujours renvoyé, données vides | Arrêt — **pas de boucle infinie** |
| Un article sur cent lève une exception | 99 écrits, l'erreur au rapport |
| Curseur : deuxième relevé | `from` = dernier `updatedAt` − 5 min |

### Client et jeton — `tests/test_helloasso_client.py`

| Scénario | Attendu |
| --- | --- |
| Pas de clé posée | `ErreurHelloAsso` « non relié », **zéro appel réseau** |
| Premier appel | `grant_type=client_credentials`, jeton écrit en base |
| Jeton valide en base | **Aucun** appel à `/oauth2/token` |
| Jeton expiré | Un `grant_type=refresh_token`, le nouveau couple écrit |
| **Deux appels concurrents sur un jeton expiré** | **Un seul** rafraîchissement ; le second relit la base |
| `401` en cours de relevé | Un rafraîchissement, **un seul** réessai |
| `401` sur le rafraîchissement lui-même | État « clé à reconnecter », le fil s'arrête |
| `429` | Erreur réseau, retenté à la cadence normale, pas d'insistance |
| Le secret dans un journal ou une réponse | **Aucune occurrence** — test explicite sur `caplog` et sur le JSON |

### Routes et console — `tests/test_helloasso_routes.py`

| Scénario | Attendu |
| --- | --- |
| `GET /admin/helloasso` sans session | `401` |
| … avec un rôle organisateur | `403` |
| `POST /admin/helloasso/cle` avec une clé refusée | `400`, message actionnable |
| `GET /admin/helloasso` après pose | `client_id` **masqué**, secret absent |
| `GET /admin/inscriptions` | Trois piles, compteurs justes |
| Trancher « même personne » | Inscription rattachée, **aucun** participant créé |
| Trancher « deux personnes » | Participant créé, dossard attribué |
| Trancher deux fois la même inscription | La seconde ne fait rien, et le dit |
| `/admin/moi` | Porte le compteur de la pastille |
| Aucune clé posée | Le compteur vaut 0, la vue n'apparaît pas dans le menu |

### Fixtures

`fixtures/helloasso/` — des réponses d'API **fabriquées à la main**, pas des
exports réels.

> ⚠️ La règle 7 du `CLAUDE.md` interdit de committer des données personnelles.
> Un export du vrai formulaire du club contiendrait des **noms de mineurs** et
> les coordonnées de leurs parents. Les fixtures portent donc des noms inventés,
> et la structure vient de la documentation, pas d'un dump.

| Fichier | Contenu |
| --- | --- |
| `items-page-1.json`, `items-page-2.json`, `items-vide.json` | Trois pages, dont la dernière vide |
| `item-annule.json` | Un `Canceled` |
| `item-sans-user.json` | `user` absent, `payer` présent |
| `item-fratrie.json` | Une commande, deux articles |
| `formulaire-public.json` | Tarifs et champs personnalisés à découvrir |

### Non-régression

- [ ] `pytest` complet vert — la suite existante ne bouge pas
- [ ] `python3 tools/verify_ranking.py fixtures/contest-nov2025.json` sort
      toujours **« 196 conformes, 0 écart »**
- [ ] `gitleaks` passe

---

## Environnement de test

Le dépôt n'a **pas** de venv utilisable : `venv/` et `.venv-dev/` n'ont pas
`pytest`. Un venv jetable, `requirements.txt` **et** `requirements-dev.txt` —
c'est le geste connu, il est noté ici pour ne pas le redécouvrir.

```bash
python3 -m venv /tmp/venv-008 && /tmp/venv-008/bin/pip install -q \
  -r requirements.txt -r requirements-dev.txt
/tmp/venv-008/bin/python -m pytest -q
```

---

## Risques

| Risque | Ce qu'on fait |
| --- | --- |
| **Le vrai formulaire ne ressemble pas au formulaire de test** — les catégories ne sont pas des tarifs mais un champ libre | `tools/dump_helloasso.py` le montre **avant** qu'on code la correspondance. C'est sa raison d'être. Si c'est le cas, D1 bascule sur « champ personnalisé » et la correspondance gagne une ligne |
| **Le `refresh_token` meurt entre deux compétitions** | État explicite « clé à reconnecter » dans la console, et l'arrêt du fil. Un geste d'une minute, pas un mystère |
| **`admin.html` est déjà disputé par trois sessions** | La vue est un `<section class="vue">` de plus, ajouté en fin de bloc : conflit additif, résolu à la main |
| **Le relevé écrit pendant qu'un juge scanne** | Un `commit` par article, sur SQLite en mode WAL. Le banc de la spec 001 dit que la charge est ridicule ; on le re-mesure quand même au lot 5 |
| **Le quota d'authentification** | 2 appels/h contre 50 autorisés. Mesuré dans le journal au lot 5 |
