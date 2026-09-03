# Architecture — spec 034

## 1. Vue d'ensemble

Rien de nouveau ne s'invente ici : les deux moitiés sont des **copies de motifs
qui tournent déjà**.

```
   CONSOLE                                        TÉLÉPHONE DU JUGE
   ───────                                        ─────────────────

   /admin/plan  ──── zones ────┐
   (spec 029)                  │
                               ▼
                        fiches.plan_courant()
                        fiches.zones_du_plan()
                               │
                               ▼
                        fiches.postes()  ──► qr.svg("CCPOSTE:C", 80mm)
                               │
                               ▼
                        fiches.en_feuilles(…, 2)
                               │
                               ▼
                        postes.html  ──► imprimante ──► carton sur la table
                                                              │
                                                              │ scan
                                                              ▼
                                                        scan.lireUnQr()
                                                              │
                                                              ▼
                                                        poste.nomDePoste()
                                                              │
                                                        ┌─────┴─────┐
                                                    null│           │"C"
                                                        ▼           ▼
                                          poste.expliquer…()   identite.renommer()
                                                        │           │
                                                        ▼           ▼
                                                     dire(…)   ouvrirLesReglages()
```

Le **seul lien** entre les deux moitiés est une chaîne de huit caractères :
`CCPOSTE:`. C'est le point de fragilité, et F6 de la spec dit comment il est
tenu.

## 2. Le contrat du QR

```
CCPOSTE:<nom de la zone>
```

- préfixe `CCPOSTE:`, écrit en majuscules, **lu sans tenir compte de la casse** ;
- suit le nom de la zone, tel qu'il est dans le plan, **sans échappement** : le
  QR encode de l'UTF-8, un accent ou un espace ne posent aucun problème ;
- le nom est nettoyé à la lecture par `identite.nettoyerLeNom()` : `trim()` puis
  coupe à 60 caractères. Un nom vide après nettoyage → refus.

Pas de version, pas de somme de contrôle, pas de signature. Un QR de poste ne
donne accès à rien : il écrit une étiquette dans le stockage local du téléphone
qui l'a scanné. Signer ce que n'importe qui peut lire sur une table serait du
théâtre.

## 3. Ce qui est touché

### 3.1 Nouveau — `climbcontest/static/juge/poste.js`

Aucun accès au DOM, aucun `fetch` : se teste sur Node, comme `jeton.js`,
`politique.js`, `catalogue.js`.

```js
export const PREFIXE_POSTE = "CCPOSTE:";

/** Le texte à encoder dans un QR de poste. */
export function texteDuQrDePoste(zone): string

/** Le nom de poste porté par ce QR, ou `null` si ce n'en est pas un. */
export function nomDePoste(texte): string | null

/** Pourquoi ce QR est refusé, en français et avec la marche à suivre. */
export function expliquerLeQrRefuse(texte): string
```

`nomDePoste` réutilise `nettoyerLeNom` de `identite.js` — un seul nettoyage pour
le clavier et pour le scan.

`expliquerLeQrRefuse` réutilise `jetonDUneAdresse` de `jeton.js` pour
reconnaître le lien de l'organisateur. C'est le seul cas où un message générique
serait franchement mauvais : le juge tient le bon QR, au mauvais endroit.

### 3.2 Touché — `climbcontest/static/juge/juge.js`

Une fonction `scannerMonPoste()`, sœur jumelle de `relier()` :

```
annulation = new AbortController()
consigne ← « Vise le QR posé sur ta table »
viseur    ← visible
code      ← await lireUnQr(...)          # peut lever : caméra
viseur    ← caché
si code == null            → retour silencieux (annulé)
nom = nomDePoste(code)
si nom == null             → dire(expliquerLeQrRefuse(code), "erreur")
sinon                        identite = await renommer(reglages, nom)
                             await ouvrirLesReglages()   # relit le champ
                             dire(« Ce téléphone s'appelle maintenant "…" »)
```

`ouvrirLesReglages()` est **le rafraîchissement d'écran existant** : il repose
`$("nomTelephone").value` depuis `identite`. On ne réécrit pas le champ à la
main, sinon on aurait deux endroits qui savent d'où vient sa valeur.

⚠️ Le viseur est **plein écran** et se pose par-dessus l'écran des réglages :
`#viseur` est déjà en `position: fixed`, aucun changement de mise en page n'est
nécessaire.

### 3.3 Touché — `climbcontest/templates/juge.html`

Un bouton dans la section **« Ce téléphone »** de `#ecranReglages`, sous le
champ `#nomTelephone` :

```html
<button class="action" id="btnScannerPoste" type="button">Scanner le QR de mon poste</button>
```

⚠️ **Le bloc `<header>` n'est pas touché.** Voir le périmètre de la spec : il
est refondu en parallèle dans `fix/revue-du-03-09`, et deux branches qui le
réécrivent fusionneraient sans conflit et en silence.

### 3.4 Touché — `climbcontest/static/juge/sw.js`

`poste.js` rejoint la coquille hors ligne, et `CACHE` passe de `v3` à `v4` :
sans ce changement de nom, un iPhone déjà installé garde l'ancienne coquille et
le nouveau module n'arrive jamais. Un test existant vérifie que tout ce qui est
listé dans `COQUILLE` existe vraiment.

### 3.5 Touché — `climbcontest/fiches.py`

```python
PREFIXE_QR_POSTE = "CCPOSTE:"
COTE_QR_POSTE_MM = 80.0
POSTES_PAR_FEUILLE = 2

def texte_qr_poste(zone: str) -> str
def postes(zone: str | None = None, plan: dict | None = None) -> list[dict]
```

`postes()` rend, **trié par nom de zone** :

```python
{"zone": "C", "texte": "CCPOSTE:C", "qr": "<svg …>"}
```

Une seule lecture du plan pour toute la planche, comme `construire()` :
`plan_courant()` touche la base, et `zones_du_plan(plan)` prend le plan déjà lu.

Aucune requête sur `Bloc` ni sur `Competition` : **une planche de QR de poste ne
dépend d'aucune compétition.** C'est ce qui permet de l'imprimer avant l'import
du classeur, la veille au soir.

### 3.6 Touché — `climbcontest/routes/admin.py`

```python
@bp.get("/postes")
@exige_role(ORGANISATEUR)
def page_postes():
    zone = (request.args.get("zone") or "").strip() or None
    planche = fiches.postes(zone=zone)
    return render_template("postes.html",
                           feuilles=fiches.en_feuilles(planche,
                                                       fiches.POSTES_PAR_FEUILLE),
                           total=len(planche), filtre=zone)
```

Pas de `competition_active()`, donc **pas de 409** : c'est la seule page
d'impression de la console qui marche sans compétition, et c'est voulu.

`/admin/referentiels` gagne une clé `zones` — les zones du plan courant — pour
remplir la liste déroulante de la console. Une clé de plus sur un appel déjà
fait à l'ouverture, plutôt qu'une deuxième route pour un seul geste. Elle est
calculée **hors** du `try` sur la compétition : le plan existe sans elle.

### 3.7 Nouveau — `climbcontest/templates/postes.html`

Reprend, ligne pour ligne, les leçons payées par la spec 032 :

- `@page { size: A4 portrait; margin: 10mm }` ;
- feuille de **188 × 272 mm** sur une surface utile de 190 × 277 — jamais la
  surface exacte, sinon une vraie imprimante coupe chaque feuille en deux ;
- pagination **en Python**, `break-before: page` sur la feuille, jamais sur un
  élément de grille ;
- `print-color-adjust: exact` — il y a un aplat (le bandeau du nom de zone) ;
- tout en millimètres, aucune ressource extérieure.

### 3.8 Touché — `climbcontest/templates/admin.html`

Une carte dans la vue **Téléphones** (c'est là que vivent les téléphones des
juges, et la carte voisine explique déjà comment installer l'application) :

```
┌─ Imprimer les QR de poste ────────────────────────┐
│  Un carton par zone du plan…                      │
│  [ Toutes les zones ▾ ]                           │
│  ( Ouvrir les QR de poste )                       │
└───────────────────────────────────────────────────┘
```

La liste déroulante est remplie par `chargerReferentiels()`, depuis la clé
`zones`.

## 4. Contrats

### `GET /admin/postes`

| | |
| --- | --- |
| Rôle | `ORGANISATEUR` |
| Query | `zone` (optionnel) |
| 200 | `text/html`, la planche |
| 401 / 403 | anonyme / rôle insuffisant |

Aucun 409 : voir 3.6.

### `GET /admin/referentiels` (modifié)

```json
{"success": true, "categories": [...], "clubs": [...], "zones": ["A", "B", "C"]}
```

`zones` est **toujours** présent, y compris sans compétition active.

## 5. Ce qu'on ne fait pas, et pourquoi

| Non fait | Pourquoi |
| --- | --- |
| Valider la zone contre le plan, côté téléphone | Un catalogue périmé bloquerait un juge pour une étiquette qui ne référence rien |
| Signer le QR | Il n'ouvre aucun accès ; signer un papier posé sur une table est du théâtre |
| Une URL plutôt qu'un texte | L'appareil photo natif ouvrirait un navigateur, et le juge se retrouverait hors de son application |
| Une table `Poste` en base | Les zones sont déjà dans le plan, et le nom du poste vit sur le téléphone |
| Toucher au `<header>` de `juge.html` | Refondu en parallèle ; deux branches y fusionneraient en silence |

## 6. Budget de requêtes

`fiches.postes()` : **une** lecture de réglage (le plan), quel que soit le
nombre de zones. Aucune requête sur `Bloc`, `Participant` ou `Competition`.
