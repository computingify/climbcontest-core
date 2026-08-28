# 003 — Architecture

## Le flux, avant et après

```
AVANT — 3 allers-retours bloquants par validation

  juge scanne grimpeur ──► POST /climber/name ──► attente ──► nom affiché
  juge scanne bloc     ──► POST /bloc/name    ──► attente ──► tag affiché
  juge appuie Envoyer  ──► POST /success      ──► attente ──► « Validé »


APRÈS — 0 aller-retour bloquant

  juge scanne grimpeur ──► catalogue local ──► nom affiché      (< 1 ms)
  juge scanne bloc     ──► catalogue local ──► tag affiché      (< 1 ms)
  juge appuie Envoyer  ──► file sur disque ──► « Validé »       (< 5 ms)

                              │
                              ▼  en arrière-plan, sans bloquer personne
                        POST /api/v3/successes   (lot de 5, ou toutes les 10 s)
```

Le point important : **la troisième flèche n'attend plus le serveur**. « Validé »
s'affiche quand la réussite est sur le disque du téléphone, pas quand elle est
sur celui de la VM. C'est le disque du téléphone qui devient le point de
non-retour, et il est bien plus fiable qu'un wifi de salle.

## Côté serveur

### Le catalogue

`GET /api/v2/catalog` existe déjà (spec 002). Il gagne deux choses :

| Ajout | Pourquoi |
| --- | --- |
| En-tête `ETag: "<version>"` | Un rafraîchissement qui n'a rien à dire coûte **304 Not Modified**, ~150 octets, au lieu de 8 ko |
| Paramètre `?depuis=<version>` | Même effet que l'`ETag`, sous une forme que l'application juge lit plus facilement (elle garde sa version en mémoire) et qui se voit dans un journal d'accès |

> **Corrigé le 28/08 : il n'y a pas de réponse différentielle.** Cette section
> en promettait une ; à l'implémentation, elle s'est révélée être de la
> complexité pour rien. Un delta demande de suivre les **suppressions** — un
> participant retiré doit disparaître des téléphones — et de gérer les conflits
> de version, pour économiser quelques kilo-octets sur un catalogue de 6 à 8 ko
> compressés. Le `304` couvre le cas fréquent (rien n'a bougé) pour ~150 octets,
> et le cas rare (quelque chose a bougé) coûte un catalogue complet, une fois.
>
> La spec a été corrigée plutôt que le code aligné en douce : c'est la règle du
> projet.

La version du catalogue est déjà portée par `Competition.catalogue_version`,
posée par la spec 002. Elle est incrémentée à chaque écriture qui touche un
participant ou un bloc — c'est le rôle de la console d'administration (spec 005),
et en attendant celui de l'import du classeur.

### La route de lot

```
POST /api/v3/successes
X-Api-Key: <clé>

{
  "items": [
    {"ref": "a1", "bib": "12", "bloc": "ZJ6", "at": "2026-11-15T09:41:02Z"},
    {"ref": "a2", "bib": "12", "bloc": "ZV3", "at": "2026-11-15T09:41:40Z"}
  ]
}
```

Réponse — **toujours 200 si le lot est lisible**, le détail est par élément :

```json
{
  "resultats": [
    {"ref": "a1", "etat": "enregistree"},
    {"ref": "a2", "etat": "refusee", "message": "Dossard 12 inconnu"}
  ],
  "catalogue_version": 7
}
```

Trois décisions, chacune pour une raison précise :

**`ref` est un identifiant *client*.** Il ne sert qu'à ce que l'application
sache quelles lignes retirer de sa file. Le serveur ne le stocke pas : la clé
d'idempotence réelle est `(participant, bloc)`, garantie par la contrainte
d'unicité de la spec 002. Pas besoin d'un UUID par réussite — la réussite *est*
son couple.

**Un lot n'échoue jamais en bloc.** Si un dossard sur cinq est inconnu, les
quatre autres sont enregistrés. Sinon un seul QR mal imprimé bloquerait la file
d'un juge pour toute la compétition.

**`catalogue_version` est renvoyée à chaque lot.** L'application apprend ainsi
qu'un rafraîchissement est nécessaire **sans requête supplémentaire** — c'est
gratuit, ça voyage dans une réponse qui part de toute façon.

### Les états possibles d'un élément

| `etat` | Signification | Ce que fait l'application |
| --- | --- | --- |
| `enregistree` | Écrite en base | Retire de la file |
| `deja_connue` | Le couple existait déjà | Retire de la file — c'est un succès |
| `refusee` | Dossard ou bloc inconnu du serveur | Retire de la file, **signale au juge** |
| *(absent de la réponse)* | Le serveur n'a rien dit | **Garde en file**, réessaiera |

La dernière ligne compte : le défaut est de **garder**. Une réussite ne quitte
la file que sur une réponse explicite. Un serveur qui répond à moitié ne fait
pas perdre de données.

## Côté application

### Trois couches, dont deux testables sur la JVM

```
  UI (Compose)            ──  écrans, toasts.  Non testé automatiquement.
      │
  Logique métier          ──  Catalogue, FileDeReussites, DecisionEnvoi.
      │                       Kotlin pur. AUCUNE dépendance Android.
      │                       C'est là que sont les tests.
      │
  Adaptateurs             ──  ClimbContestApi (OkHttp), StockageFichier (java.io).
                              Fins, remplaçables par un double en test.
```

C'est la séparation déjà commencée avec `ClimbContestApi` et `DecisionEnvoi`.
Elle n'est pas cosmétique : c'est **la seule façon de tester sans émulateur**,
et l'émulateur s'est révélé trop instable sur la machine de dev pour servir de
socle (crash QEMU au démarrage, avec ou sans fenêtre).

C'est aussi ce qui rendra la spec 007 (iPhone) réaliste : la logique portée
sera celle-ci, sans réécriture.

### La file : un journal append-only, pas une base

**Décision : un fichier de lignes JSON, pas Room.**

| | Journal append-only | Room / SQLite |
| --- | --- | --- |
| Testable sur la JVM | ✅ un dossier temporaire suffit | ❌ demande Robolectric ou un appareil |
| Dépendances | aucune | processeur d'annotations, ~1 Mo |
| Volume à tenir | 3 600 lignes × ~60 o = **~216 ko** | idem |
| Écriture | `append` + `fsync`, ~1 ms | ~2 ms |
| Complexité | ~120 lignes | schéma, DAO, migrations |

À ce volume, une base de données est un marteau-pilon. Et le critère décisif
n'est pas la performance : c'est qu'un journal se teste avec un `@TempDir`,
alors que Room ramènerait l'émulateur par la fenêtre — précisément ce qu'on
vient d'écarter.

Format, une ligne par réussite :

```
{"ref":"a1","bib":"12","bloc":"ZJ6","at":"2026-11-15T09:41:02Z"}
```

Cycle de vie :

1. **Ajout** — une ligne est ajoutée, le fichier est `fsync`é, *puis* seulement
   « Validé » s'affiche. L'ordre compte : afficher avant de synchroniser
   rendrait le message mensonger.
2. **Envoi** — les *n* premières lignes non acquittées partent en lot.
3. **Acquittement** — les `ref` acquittées sont notées dans un second fichier,
   lui aussi append-only.
4. **Compactage** — quand tout est acquitté, les deux fichiers sont réécrits à
   vide, par un remplacement atomique (`écrire un .tmp`, puis `rename`).

Pourquoi deux fichiers plutôt qu'un seul qu'on réécrit : parce qu'une réécriture
peut être interrompue, et qu'une interruption au mauvais moment perdrait des
réussites déjà validées. Un `append` ne peut pas laisser le fichier dans un état
intermédiaire ; un `rename` est atomique sur tous les systèmes de fichiers
concernés. Aucune des deux opérations dangereuses n'existe dans ce schéma.

### Le catalogue local

Stocké en JSON dans le dossier privé de l'application, avec sa version. Chargé
en mémoire au démarrage sous forme de deux tables de hachage :

```kotlin
class Catalogue(
    private val parDossard: Map<String, String>,   // dossard  -> nom complet
    private val parTag: Map<String, String>,       // tag bloc -> libellé
    val version: Int,
)
```

Une recherche est un accès de table de hachage : ~100 ns contre ~200 ms pour un
aller-retour réseau. Le facteur est de **deux millions**, et c'est ce que le
juge ressent comme « instantané » au lieu de « ça rame ».

### Le repli réseau

Un QR absent du catalogue local **n'est pas refusé**. Il déclenche :

1. un appel `v2` classique — le chemin d'aujourd'hui, qui marche ;
2. en tâche de fond, un rafraîchissement du catalogue.

C'est ce qui absorbe le participant inscrit dix minutes plus tôt, sans que le
juge ait quoi que ce soit à faire. Le coût — un aller-retour — n'est payé que
pour les QR réellement nouveaux, c'est-à-dire quelques-uns par compétition.

### Le rafraîchissement

| Déclencheur | Pourquoi |
| --- | --- |
| Au démarrage de l'application | Le cas normal |
| `catalogue_version` reçue dans une réponse de lot ≠ version locale | Gratuit, et détecte un changement en quelques secondes |
| QR inconnu en local | Le signal le plus direct qu'on a du retard |
| Toutes les 5 minutes | Filet, pour un téléphone qui n'envoie rien |

## Fichiers touchés

### `climbcontest-core`

| Fichier | Nature |
| --- | --- |
| `climbcontest/routes/successes.py` | **nouveau** — la route de lot `v3` |
| `climbcontest/routes/catalog.py` | ETag, `?depuis=` |
| `climbcontest/contest.py` | `enregistrer_lot()`, au-dessus de `enregistrer_reussite()` |
| `tests/test_lot.py` | **nouveau** |
| `tests/test_e2e.py` | scénarios de lot sur vrai gunicorn |
| `tools/mesurer_volume.py` | **nouveau** — le critère A12 |

Les trois routes `v2` ne sont **pas** touchées. Leurs tests de contrat non plus :
c'est eux qui prouvent qu'on ne les a pas cassées.

### `climbcontest-android`

| Fichier | Nature |
| --- | --- |
| `Catalogue.kt` | **nouveau** — Kotlin pur |
| `FileDeReussites.kt` | **nouveau** — Kotlin pur |
| `StockageFichier.kt` | **nouveau** — adaptateur `java.io`, testable avec `@TempDir` |
| `Expediteur.kt` | **nouveau** — la boucle d'envoi, lot et retrait exponentiel |
| `ClimbContestApi.kt` | `telechargerCatalogue()`, `envoyerLot()` |
| `Server.kt` | consulte le catalogue au lieu du réseau |
| `MainViewModel.kt` | expose `reussitesEnAttente` |
| `MainActivity.kt` | l'indicateur |

## Ce qui pourrait mal tourner

| Risque | Parade |
| --- | --- |
| Le catalogue local devient obsolète et refuse des grimpeurs légitimes | Repli réseau systématique sur QR inconnu. C'est **la** protection, et A5 la teste |
| Le disque du téléphone est plein | L'ajout échoue → on n'affiche pas « Validé », on affiche l'erreur. Ne jamais mentir au juge |
| La file grossit sans jamais partir (serveur éteint) | L'indicateur la rend visible, et le bouton « tout envoyer » de Q2 donne la main |
| Un bogue de compactage perd des réussites | Le compactage n'a lieu que lorsque **tout** est acquitté, et par `rename` atomique. Testé en coupant à chaque étape |
| Deux instances de l'expéditeur envoient le même lot | Idempotent côté serveur : `(participant, bloc)` est unique. Au pire, du trafic gaspillé |
