# 011 — Architecture

## Vue d'ensemble

```
  Téléphone juge                        Backend                     Console
  ──────────────                        ───────                     ───────
  appareil.json          POST /api/v3/successes
   { id, nom }   ────────►  { appareil: {id, nom},   ──►  success.appareil_id
                              items: [{ref, ...}] }        success.appareil_nom
  historique.jsonl                                         success.ref_client
   une ligne par
   évènement                GET /api/v3/appareils     ◄──  page « Appareils »
                            GET /api/v3/reussites          recherche par ref
  écran « Mes scans »
```

Trois pièces indépendantes. Chacune peut être livrée seule : le téléphone garde
son journal même si le serveur ignore l'identité, et le serveur accepte
l'identité même si aucune console ne la lit.

## Côté Android

### L'identité de l'appareil — `IdentiteAppareil.kt`

```kotlin
data class IdentiteAppareil(val id: String, val nom: String?)
```

Rangée dans `appareil.json`, à côté de la file, dans `context.filesDir` :

```json
{"id": "8f3c1d20-...", "nom": "Mur jaune"}
```

- `id` : un `UUID.randomUUID()` au premier lancement, jamais réécrit ensuite.
  **Pas** `Settings.Secure.ANDROID_ID` : c'est un identifiant d'appareil au sens
  du Play Store, soumis à sa politique sur les identifiants persistants, et il
  survit à la désinstallation — deux propriétés dont on n'a aucun besoin. Un
  UUID d'application est cantonné à l'application et disparaît avec elle.
- `nom` : saisi par le juge, facultatif, modifiable.

La classe est **pure** — un fichier, du JSON — donc testable sur la JVM avec un
dossier temporaire, comme `FileDeReussites`. Pas d'émulateur.

### Le journal complet — `HistoriqueScans.kt`

Un quatrième fichier, `historique.jsonl`, en **ajout seul**, jamais compacté.
Une ligne par évènement :

```json
{"ref":"a1b2...","bib":"42","bloc":"ZV3","at":"2026-11-08T10:42:03Z","etat":"en_attente"}
{"ref":"a1b2...","etat":"partie","at":"2026-11-08T10:42:11Z"}
```

**Règle de relecture : pour une `ref` donnée, la dernière ligne fait foi.** Elle
est triviale à implémenter et à tester, et elle tolère une coupure au milieu de
n'importe quoi — au pire, un état reste « en attente » alors que la réussite est
partie, ce qui est le sens de l'erreur qu'on préfère.

Pourquoi un fichier de plus plutôt que d'arrêter de compacter `file.jsonl` : le
compactage est ce qui garde la file d'envoi courte, donc les envois rapides. Il
existe pour une bonne raison. Le journal poursuit un but différent — la mémoire —
et n'a pas les mêmes contraintes de relecture.

**Le journal n'est jamais la source de vérité de l'envoi.** `file.jsonl` le
reste. C'est ce qui rend la purge à 30 jours sans danger : elle ne peut pas
perdre une réussite non envoyée, parce qu'elle ne touche pas au fichier qui la
porte.

La purge s'exécute au démarrage, réécrit le fichier en `.partiel` puis renomme —
le même motif atomique que le script de sauvegarde de la VM.

### L'écran — `ScansScreen.kt`

Accessible depuis les réglages et depuis la bande de file. Liste inversée :
heure, grimpeur, bloc, état, référence courte (6 caractères). Un interrupteur
« seulement ce qui n'est pas parti ».

Les états reprennent les couleurs déjà en place : `EtatFait` pour parti,
`Attention` pour en attente, `Alerte` pour refusé.

### L'envoi — `ClimbContestApi.envoyerLot`

Le corps gagne un objet, à côté de `items` :

```json
{"appareil": {"id": "...", "nom": "Mur jaune"}, "items": [...]}
```

## Côté backend

### Modèle — trois colonnes sur `success`

| Colonne | Type | Rôle |
| --- | --- | --- |
| `appareil_id` | `String(40)` | L'identifiant envoyé par le téléphone. NULL pour une saisie manuelle ou un import. |
| `appareil_nom` | `String(60)` | Le nom **au moment de l'envoi**. Dénormalisé exprès : renommer un téléphone ne doit pas réécrire l'histoire. |
| `ref_client` | `String(40)`, indexée | La référence donnée par le téléphone. **Pas une clé** : l'idempotence reste portée par `uq_reussite (participant_id, bloc_id)`. |

Ajoutées par `COLONNES_AJOUTEES` dans `schema.py`, le mécanisme déjà en place
pour `dossard_scanne`, `scanne_le` et `saisie_par` — SQLite n'a pas de
`ADD COLUMN IF NOT EXISTS`.

Un index sur `ref_client` : c'est la colonne de la recherche.

### Le commentaire de `saisie_par` est corrigé

Il affirme aujourd'hui qu'il n'y a « aucune raison » d'identifier le juge. La
raison existe désormais, mais elle porte sur l'**appareil**. Le commentaire doit
dire les deux, sans quoi la prochaine lecture y verra une contradiction.

### API

| Route | Rôle | Réponse |
| --- | --- | --- |
| `POST /api/v3/successes` | inchangée, accepte `appareil` en plus | inchangée |
| `GET /api/v3/appareils` | admin, organisateur | un objet par appareil : `id`, `nom`, `reussites`, `derniere_le`, `silencieux_depuis_s` |
| `GET /api/v3/reussites?ref=&appareil=&limite=` | admin, organisateur | les réussites correspondantes, avec grimpeur, bloc, heure et appareil |

`appareil` est **facultatif** dans le corps de l'envoi. Une application plus
ancienne continue de fonctionner : on ne peut pas supposer que les vingt-cinq
téléphones seront à jour le matin de la compétition.

Le corps est validé comme le reste : un `appareil` mal formé est **ignoré**, pas
rejeté. Perdre une réussite parce qu'un nom contient un caractère inattendu
serait le pire des échanges.

### Console

Un onglet « Appareils » dans `templates/admin.html`, avec la liste et un champ de
recherche. Le point qui compte visuellement : un appareil **silencieux depuis
plus de dix minutes** ressort — c'est le signal qu'un juge est en panne, et
c'est la seule chose de cette page qui soit urgente.

## Fichiers touchés

**climbcontest-android**

| Fichier | Nature |
| --- | --- |
| `IdentiteAppareil.kt` | nouveau |
| `HistoriqueScans.kt` | nouveau |
| `ScansScreen.kt` | nouveau |
| `Server.kt` | note chaque scan au journal, passe l'identité à l'API |
| `ClimbContestApi.kt` | ajoute `appareil` au corps du lot |
| `SettingsScreen.kt` | champ « nom de ce téléphone », accès à l'écran des scans |
| `MainActivity.kt` | navigation vers l'écran des scans |
| `strings_fr.xml` | libellés |

**climbcontest-core**

| Fichier | Nature |
| --- | --- |
| `models.py` | trois colonnes, commentaire de `saisie_par` corrigé |
| `schema.py` | `COLONNES_AJOUTEES` |
| `routes/lot.py` | lit `appareil`, renseigne les colonnes |
| `routes/admin.py` | les deux routes de lecture |
| `templates/admin.html` | l'onglet « Appareils » |
