# 002 — La base devient la source de vérité

## Résumé

Aujourd'hui une réussite n'existe nulle part côté serveur : elle transite par une
file en mémoire vive puis part dans le classeur Google. Si le processus redémarre,
si l'API Google renvoie une erreur, ou si la base est effacée au démarrage — trois
choses qui arrivent — la réussite est perdue **sans trace et sans alerte**.

Cette spec inverse le rapport : **la base porte la vérité, le classeur en devient
un miroir**. C'est le préalable de tout le reste — pas de classement live, pas de
page résultats, pas de saisie manuelle, pas d'archives, tant que les données ne
sont pas fiables.

## Pourquoi maintenant

Quatre des cinq risques critiques de l'[état des lieux](../../docs/etat-des-lieux.md)
sont ici, et un cinquième est aggravé par la spec 001 :

| Risque | Aujourd'hui |
| --- | --- |
| **R1** | `db.drop_all()` au niveau module. La spec 001 fait tourner **4 workers gunicorn** : la base serait effacée quatre fois au démarrage, et à chaque redémarrage d'un worker |
| **R2** | Jusqu'à 50 réussites en RAM, perdues au moindre redémarrage |
| **R3** | Une erreur d'écriture Google vide le lot quand même |
| **R4** | Aucune trace locale : ni rejeu, ni recompte, ni audit d'une contestation |
| **R12** | Pas de dédoublonnage durable — sans conséquence aujourd'hui, faux classement demain |

## Périmètre

### Inclus

1. **Modèle de données multi-compétition**, avec une **identité stable distincte
   du dossard**, et les tables d'utilisateurs et de rôles posées dès maintenant
   pour éviter une migration plus tard.
2. **Persistance des réussites** : écrites en base **avant** de répondre au juge,
   uniques par `(participant, bloc)`.
3. **Le classeur devient un miroir** : un travailleur rejoue depuis la base ce
   qui n'est pas encore synchronisé, et **ne marque comme fait que ce qui a
   réellement réussi**.
4. **Initialisation propre** : fin du `drop_all()` à l'import, migrations
   explicites, compatible avec plusieurs workers.
5. **Import du classeur sur commande**, tolérant, avec un rapport lisible —
   plus jamais dans le chemin d'une requête juge.
6. **Clé d'API** sur les routes d'écriture.
7. **Suite de tests** pytest sur base en mémoire.

### Explicitement exclu

- Le moteur de classement (spec 004) — mais le modèle doit le rendre possible.
- La console d'administration (spec 005).
- La page résultats (spec 006).
- L'import HelloAsso (spec 008).
- Toute évolution de l'application Android (spec 003).

## La contrainte qui commande tout le reste

> **L'application juge déployée sur le Play Store (`v3.1.4`) doit continuer de
> fonctionner sans être mise à jour.**

Elle appelle trois routes avec un contrat précis. Tant que la spec 003 n'a pas
livré une nouvelle application, ce contrat est **intangible** :

| Route | Corps | Réponse attendue par l'app |
| --- | --- | --- |
| `POST /api/v2/contest/climber/name` | `{"id": "<dossard>"}` | `201 {"success": true, "id": "<nom>"}` |
| `POST /api/v2/contest/bloc/name` | `{"id": "<tag>"}` | `201 {"success": true, "id": "<tag>"}` |
| `POST /api/v2/contest/success` | `{"bib", "bloc"}` | `201 {"success": true}` |

Conséquence directe sur la clé d'API : **elle ne peut pas être obligatoire tout
de suite**, l'application déployée n'en envoie aucune. Voir Q1.

## Critères d'acceptation

> Coché = **il existe un test qui tombe si la propriété disparaît**, et son nom
> est en face. Les cases qui restent ouvertes le sont pour une raison écrite,
> pas par oubli.

### Les données survivent

- [x] Une réussite envoyée est en base **avant** que le juge reçoive sa réponse.
      → `test_la_reussite_est_en_base_avant_la_reponse`
- [x] Le service redémarré en pleine charge : **aucune réussite perdue**,
      vérifié en comptant avant et après.
      → E2E `TestSurvieAuRedemarrage::test_les_reussites_survivent`
- [x] `(participant, bloc)` envoyé deux fois → **une seule** ligne, réponse `201`
      les deux fois (l'app ne doit pas voir d'erreur sur un double appui).
      → `test_double_envoi_renvoie_201_et_une_seule_ligne`, et sous gunicorn
      `test_meme_couple_depuis_20_requetes_simultanees`
- [x] La base n'est **jamais** effacée au démarrage, quel que soit le nombre de
      workers. Vérifié avec les 4 workers de la spec 001.
      → `test_ne_detruit_jamais_les_donnees` et E2E
      `test_la_base_n_est_pas_effacee_au_demarrage`

### Le classeur est un miroir, pas la source

- [x] Une réussite est marquée synchronisée **seulement** si l'écriture Google a
      réellement réussi. → `test_rien_n_est_marque_si_l_ecriture_echoue`
- [x] API Google en erreur : la réussite reste en base, marquée non
      synchronisée, et **retentée** au cycle suivant. → `test_rattrapage_automatique`
- [x] Classeur injoignable pendant 10 minutes puis rétabli : tout est rattrapé
      sans intervention. → `test_les_reussites_en_attente_survivent` +
      `test_rattrapage_automatique`
- [x] Le service démarre et accepte des réussites **même si le classeur est
      injoignable**. → `test_le_service_continue_d_accepter_des_reussites`

### L'identité est stable

- [x] Un participant existe sans dossard (inscrit, absent). → `test_sans_dossard`
- [x] Un dossard **sans aucune réussite** peut être réaffecté.
      → `test_dossard_vierge_reaffectable`
- [x] Un dossard **portant au moins une réussite** : réaffectation **refusée**,
      avec un message explicite. → `test_dossard_avec_reussite_refuse`,
      et `test_la_regle_metier_d_origine_tient_toujours` qui vérifie que la
      décision du 28/08 sur la file d'attente n'a pas levé cette règle-là
- [x] Deux homonymes dans deux clubs coexistent sans casser l'import.
      → `test_deux_homonymes_coexistent`
- [x] Un dossard est unique **au sein d'une compétition**, pas globalement.
      → `test_meme_dossard_deux_competitions` et
      `test_meme_dossard_meme_competition_refuse`

### L'import du classeur

- [x] Une ligne incomplète (club ou catégorie manquants) est **importée quand
      même**, et signalée dans le rapport.
      → `test_participant_sans_club_ni_categorie_est_importe`
- [x] Le rapport dit combien de participants et de blocs ont été créés, mis à
      jour, ignorés — et pourquoi. → `test_ligne_tronquee_rejetee_et_signalee`,
      `test_participant_sans_dossard_est_signale`, `test_dossard_illisible`
- [x] Un dossard inconnu scanné **ne déclenche aucun appel à Google**.
      → `test_un_dossard_inconnu_ne_declenche_aucun_appel_a_google`, qui espionne
      la classe cliente elle-même : n'importe quel appel fait tomber le test
- [x] Une correction faite dans le classeur est reprise au réimport suivant.
      → `test_reprend_une_correction_du_classeur`

### Le catalogue

- [x] Chaque modification de participant ou de bloc **incrémente une version**.
      → `test_incremente_le_catalogue` (import) et
      `test_la_reaffectation_incremente_la_version`
- [x] `GET /api/v2/catalog` renvoie le catalogue complet et sa version.
      → `test_contenu`, `test_le_bloc_porte_ses_circuits`
- [x] ~~`GET /api/v2/catalog?depuis=<v>` renvoie uniquement les changements.~~
      **Critère corrigé le 28/08 : la réponse n'est pas différentielle.**

      Elle est *complète ou `304`*. À 6–8 ko compressés pour 98 participants et
      67 blocs, un vrai delta coûterait un suivi des suppressions et des
      conflits pour économiser quelques kilo-octets. Le `304` fait déjà
      l'essentiel : quand rien n'a bougé — le cas le plus fréquent — il ne passe
      que ~150 octets.

      C'est la spec qui a été corrigée, pas le code réparé en douce : la règle du
      projet est que la spec suive la décision.
      → `TestEtagCatalogue` (9 tests), plus `ETag` / `If-None-Match` en HTTP
      standard, pour que Caddy et les navigateurs sachent revalider

### Qualité

- [x] `pytest` passe, base en mémoire, aucun accès réseau. → 215 tests
- [ ] Le jeu de novembre 2025 s'importe et donne 98 participants et 67 blocs.
      **Ne peut pas être automatisé.** Il faudrait committer un export brut du
      classeur, qui contient des **noms de mineurs** — interdit par la règle 7
      du projet. La vérification se fait à la main, hors dépôt, avant chaque
      compétition ; elle est inscrite au [runbook](../../docs/runbook-competition.md).

## Cas limites

| Situation | Comportement attendu |
| --- | --- |
| Deux juges valident le même passage en même temps | une seule réussite, `201` pour les deux |
| Réussite sur un bloc hors du circuit du participant | acceptée et stockée, **mais ignorée au classement** (spec 004). On n'invente pas une règle que le classeur n'applique pas |
| Dossard inconnu | `400`, message clair, **aucun appel Google** |
| Base verrouillée par une écriture concurrente | réessai court, puis `503` — jamais une réussite silencieusement perdue |
| Le classeur a changé de structure | l'import échoue **explicitement** et ne touche à rien |
| Aucune compétition active | les routes d'écriture répondent `409` avec un message clair |
| Deux compétitions le même jour | interdit pour l'instant : une seule active à la fois (Q3) |

## Décisions ouvertes

| # | Question | Pourquoi ça compte |
| --- | --- | --- |
| **Q1** | La clé d'API doit-elle être **facultative** tant que l'app `v3.1.4` tourne (acceptée si présente, tolérée si absente), ou attend-on la spec 003 pour l'imposer ? | Une clé obligatoire tout de suite **casse l'application déployée** |
| **Q2** | Rythme de synchronisation vers le classeur : garde-t-on 50 réussites / 40 s, ou plus court maintenant qu'un échec n'est plus une perte ? | Confort d'usage contre quota Google |
| **Q3** | Une seule compétition active à la fois : suffisant ? | Simplifie beaucoup les routes ; à confirmer |
| **Q4** | Le classeur reste-t-il alimenté **pendant** que la base devient la source ? | Décision Q7 de la spec 001 disait oui — à reconfirmer ici |
