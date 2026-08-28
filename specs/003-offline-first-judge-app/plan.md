# 003 — Plan

Cinq itérations. Chacune se termine sur quelque chose qui marche et qui est
testé — pas sur « la moitié d'une couche ».

L'ordre suit une règle simple : **le serveur d'abord**, parce qu'une application
ne peut pas être testée contre une route qui n'existe pas, et parce que le
serveur peut être livré sans que rien ne change pour les juges.

---

## IT1 — La route de lot, côté serveur

- [x] `enregistrer_lot()` dans `contest.py`, au-dessus de `enregistrer_reussite()`
- [x] `POST /api/v3/successes`, protégée par la clé d'API
- [x] Résultat **par élément**, jamais d'échec en bloc — vérifié en cassant la
      tolérance : trois tests tombent
- [x] `catalogue_version` dans chaque réponse
- [x] Tests unitaires (38, `tests/test_lot.py`) + E2E sur vrai gunicorn à
      4 workers (`TestLotSousGunicorn`), dont le même lot envoyé dix fois en
      parallèle → trois réussites, pas trente
- [x] Les tests de contrat `v2` passent toujours, **inchangés**

Livrable : le serveur accepte les lots. Aucun client ne les envoie encore, et
rien n'a changé pour les juges. C'est délibéré — cette itération est
déployable seule et sans risque.

## IT2 — Le catalogue différentiel

- [x] `ETag` sur `/api/v2/catalog`, et `304` sur `If-None-Match` — y compris les
      étiquettes faibles (`W/`) et les listes, que les caches envoient
- [x] ~~`?depuis=<version>` → réponse différentielle~~ **Abandonné, et la spec
      corrigée plutôt que le code contourné.** La réponse est *complète ou 304*.
      À 6–8 ko compressés, un vrai delta coûterait un suivi des suppressions et
      des conflits pour économiser quelques kilo-octets, alors que le `304` — le
      cas de loin le plus fréquent — ne fait déjà passer que ~150 octets.
- [x] `catalogue_version` incrémentée à chaque écriture sur participant ou bloc
- [x] Mesure : un rafraîchissement à vide coûte **286 octets**, le catalogue
      complet **14 ko**. Mesuré sur la VM.

## IT3 — La file persistante, côté application

- [x] `StockageFichier` — `append`, `fsync`, `rename` atomique
- [x] `FileDeReussites` — ajout, lot suivant, acquittement, compactage
- [x] Tests JVM avec un dossier temporaire, dont les **coupures à chaque étape**
      → 31 tests. L'un d'eux a trouvé un vrai défaut : une ligne tronquée sans
      saut de ligne final **avalait la réussite suivante**
- [x] Rien n'est branché à l'interface : la file existe et est prouvée

C'est l'itération la plus délicate, et c'est pour ça qu'elle est isolée. Une
file qui perd des données est exactement le défaut qu'on cherche à supprimer.

## IT4 — Le catalogue local et la validation hors ligne

- [x] `Catalogue` — chargement, recherche, persistance
- [x] Le scan consulte le catalogue, plus le réseau
- [x] Repli réseau sur QR inconnu **+ rafraîchissement**
- [x] Les quatre déclencheurs de rafraîchissement
- [x] Tests JVM (22), dont le parseur confronté au **vrai catalogue de la VM**
      pris tel quel comme fixture — un test écrit à la main vérifie le format
      qu'on a imaginé, celui-ci vérifie le format qui existe

## IT5 — L'expéditeur, l'indicateur, la mesure

- [x] `Expediteur` — lot de 5 ou 10 s, retrait exponentiel plafonné à 60 s,
      reprise au lancement. 26 tests
- [x] Indicateur « n en attente » dans l'interface
- [x] Bouton « tout envoyer maintenant », dans les réglages. Il ignore le lot
      et le délai, mais **pas** le retrait — sinon appuyer en boucle sur un
      serveur éteint noierait le téléphone de requêtes
- [x] `tools/mesurer_volume.py` — le critère A12
- [x] Mesure réelle, comparée au tableau de la spec → **l'estimation était trop
      optimiste**, la spec a été corrigée avec les chiffres mesurés

---

## Plan de test

Écrit **avant** l'implémentation, comme le veut la méthode.

### Serveur — route de lot

| Scénario | Attendu |
| --- | --- |
| Lot de 3 valides | 3 × `enregistree`, 3 lignes en base |
| Lot avec un doublon d'une réussite existante | `deja_connue`, aucune ligne créée |
| Lot avec le **même couple deux fois dans le lot** | Une ligne, deux `ref` acquittées |
| Lot de 3 valides + 1 dossard inconnu | 3 `enregistree`, 1 `refusee`, 3 lignes en base |
| Lot avec un bloc inconnu | `refusee`, message explicite |
| Lot vide | 200, liste vide. Pas une erreur |
| Lot de 500 éléments | Accepté, ou refusé avec un message clair. **Jamais** un 500 |
| Corps qui n'est pas un objet (`[1,2]`, `"x"`) | 400, jamais 500 |
| `items` absent | 400 |
| Sans clé d'API, mode toléré | Accepté, compté, journalisé |
| Sans clé d'API, mode strict | 401, et **la file du client n'est pas vidée** |
| Aucune compétition active | 409, message explicite |
| Deux lots concurrents avec le même couple | Une seule ligne. Testé sur vrai gunicorn, 4 workers |

### Serveur — catalogue

| Scénario | Attendu |
| --- | --- |
| Premier appel | 200, `ETag` présent |
| Rappel avec le même `ETag` | **304**, corps vide |
| Rappel après ajout d'un participant | 200, nouvel `ETag` |
| `?depuis=` version courante | Différentiel vide |
| `?depuis=` version antérieure | Seulement les modifiés |
| `?depuis=` version future ou absurde | Catalogue **complet**, pas une erreur |

### Application — file

| Scénario | Attendu |
| --- | --- |
| Ajout puis relecture par un dépôt neuf | La réussite est là |
| Coupure **après** `append`, **avant** acquittement | La réussite est là, renvoyée |
| Coupure **pendant** le compactage | Aucune perte : soit l'ancien état, soit le nouveau |
| Acquittement partiel d'un lot | Seules les `ref` acquittées disparaissent |
| Fichier d'acquittement corrompu (ligne tronquée) | Les lignes lisibles sont honorées, le reste est renvoyé |
| Fichier de file corrompu | Les lignes lisibles sont conservées, **jamais** un plantage |
| 3 600 réussites | Tient, et l'ajout reste sous 5 ms |

La ligne « coupure pendant le compactage » est celle qui justifie tout le
design. Elle sera testée en interrompant réellement entre chaque opération de
fichier, pas en le supposant.

### Application — catalogue et validation

| Scénario | Attendu |
| --- | --- |
| Dossard connu | Validé, **zéro requête** (compteur du serveur factice à 0) |
| Bloc connu | Validé, zéro requête |
| Dossard inconnu en local, connu du serveur | Validé par repli, catalogue rafraîchi |
| Dossard inconnu partout | Refusé, message clair |
| Catalogue absent (premier lancement hors ligne) | Mode dégradé `v2`, fonctionnel |
| Catalogue sur disque corrompu | Retéléchargé, jamais un plantage |
| Version reçue dans une réponse de lot ≠ locale | Rafraîchissement déclenché |

### Application — expéditeur

| Scénario | Attendu |
| --- | --- |
| 5 réussites | Un lot part |
| 2 réussites, 10 s | Un lot part |
| Serveur injoignable | Retrait exponentiel, rien n'est perdu |
| Serveur revient après 20 échecs | Tout part |
| 401 permanent | La file est **conservée**, le juge est prévenu |
| Réponse partielle (moins de `ref` que d'éléments) | Les non-mentionnées restent en file |
| Application relancée avec une file non vide | L'envoi reprend seul |

### Mesure — critère A12

| Mesure | Cible |
| --- | --- |
| Requêtes pour 3 600 validations | < 500 (contre 10 800) |
| Octets réels échangés | < 500 ko (contre ~8 Mo) |
| Allers-retours bloquants pour le juge | **0** |
| Temps entre le scan et l'affichage du nom | < 10 ms (contre ~200 ms) |

Le résultat de cette mesure va dans
[etat-des-lieux.md §7](../../docs/etat-des-lieux.md#7-volume-de-données-échangé--mesure-et-cible),
en face des chiffres d'aujourd'hui. Une spec qui existe pour faire baisser un
nombre doit finir par montrer le nombre.

---

## Ce qui n'est pas fait ici, et pourquoi

| Sujet | Renvoyé à |
| --- | --- |
| Retirer les routes `v2` | Après une compétition entière sans un seul appel `v2` |
| La console d'administration qui alimente le catalogue | Spec 005 |
| L'interdiction de réaffecter un dossard ayant des réussites en attente | Spec 005, mais **la question est posée ici** (Q3) — c'est cette spec qui crée le problème |
| La version iPhone | Spec 007, sur la logique extraite ici |
