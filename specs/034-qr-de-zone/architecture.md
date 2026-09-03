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
                        fiches.postes()  ──► qr.svg("CCPOSTE:C", 48mm)
                               │
                               ├──► fiches.geometrie_postes()   (la densité)
                               ▼
                        fiches.en_feuilles(…, POSTES_PAR_FEUILLE)
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
                                                    null│           │"Zone C"
                                                        ▼           ▼
                                          poste.expliquer…()   identite.renommer()
                                                        │           │
                                                        ▼           ▼
                                                     dire(…)   proposerDeNommerLePoste()
                                                                    │
                                                                    │ envois
                                                                    ▼
                                                          Success.appareil_nom
                                                          Success.appareil_id
                                                                    │
                                                                    ▼
                                                        contest.libelle_poste()
                                                                    │
                                                                    ▼
                                                      « Zone C (3f9a1c2b) »
```

Le **seul lien** entre les deux moitiés est une chaîne de huit caractères :
`CCPOSTE:`. C'est le point de fragilité, et F6 de la spec dit comment il est
tenu.

## 2. Le contrat du QR

```
CCPOSTE:<lettre de la zone>          →  « Zone <lettre> » sur le téléphone
```

- préfixe `CCPOSTE:`, écrit en majuscules, **lu sans tenir compte de la casse** ;
- suit la **lettre de la zone**, telle qu'elle est dans le plan, **sans
  échappement** : le QR encode de l'UTF-8, un accent ou un espace ne posent aucun
  problème ;
- ⚠️ **le libellé est composé à la lecture**, pas encodé : `poste.libelleDuPoste`
  pose `MOT_ZONE` (« Zone ») devant. Un QR minimal se lit mieux, et le libellé
  peut changer sans réimprimer dix-sept affiches. Une lettre qui commence déjà
  par « zone » n'est pas préfixée deux fois ;
- le nom est nettoyé à la lecture par `identite.nettoyerLeNom()` : `trim()` puis
  coupe à 60 caractères — **après** composition, parce que `MOT_ZONE` plus une
  zone de 58 lettres dépasserait la limite. Un nom vide après nettoyage → refus.

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
export const MOT_ZONE = "Zone";       // ⚠️ égal à `fiches.MOT_ZONE`

/** Le texte à encoder dans un QR de poste : le préfixe et la LETTRE. */
export function texteDuQrDePoste(zone): string

/** « A » → « Zone A ». La composition du libellé, isolée et testable. */
export function libelleDuPoste(zone): string | null

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

### 3.2 bis — L'écran d'accueil (retouche du 03/09)

```
proposerDeNommerLePoste()      # UNE fonction décide de la visibilité
  $("poste").hidden = Boolean(identite && identite.nom)
```

Trois appelants, un seul endroit qui décide :

| Appelant | Pourquoi |
| --- | --- |
| `demarrer()`, **après** la lecture de l'identité | `identite` est indéfinie avant, et le bloc resterait caché sur un téléphone sans nom |
| `scannerMonPoste()`, après le renommage | Le poste vient d'être nommé : le bloc n'a plus lieu d'être |
| l'écouteur `input` de `#nomTelephone` | Le champ vidé à la main redonne le geste |

`scannerMonPoste({ depuisLAccueil })` : depuis l'accueil, **pas** de
`ouvrirLesReglages()` — ce serait déposer le juge sur un écran qu'il n'a pas
demandé, juste avant son premier scan.

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
MOT_ZONE = "Zone"                 # ⚠️ égal à `poste.MOT_ZONE`
COTE_QR_POSTE_MM = 48.0           # plancher mesuré : 42 (étiquettes, spec 024)
POSTES_PAR_FEUILLE = 8            # ⚠️ LA valeur qui commande la planche
POSTES_PAR_LIGNE = 2

def texte_qr_poste(zone: str) -> str
def geometrie_postes(par_feuille=None, par_ligne=None) -> dict
def taille_nom_poste_mm(texte: str, geometrie: dict | None = None) -> float
def postes(zone: str | None = None, plan: dict | None = None) -> list[dict]
```

⚠️ **`geometrie_postes()` est le seul endroit qui connaît des millimètres.**

```
POSTES_PAR_FEUILLE (8)  ─┬─► lignes = ceil(8 / colonnes) = 4
POSTES_PAR_LIGNE   (2)  ─┘        │
                                  ├─► hauteur = 270 / 4 = 67,5 mm
                                  ├─► largeur = 188 / 2 = 94 mm
                                  └─► largeur_nom = 94 − 2×4 − 48 − 4 = 34 mm
```

Le gabarit reçoit ces millimètres en variables CSS et n'en décide **aucun**.
C'est ce qui rend « repasser à six » possible en changeant une valeur — la
version précédente écrivait la densité en Python *et* dans le CSS, et les deux
ont divergé au premier changement.

`postes()` rend, **trié par nom de zone** :

```python
{"zone": "C", "texte": "CCPOSTE:C", "libelle": "Zone C",
 "taille_nom": 26.0, "qr": "<svg …>"}
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
- feuille de **188 × 270 mm** sur une surface utile de 190 × 277 — jamais la
  surface exacte, sinon une vraie imprimante coupe chaque feuille en deux ;
- pagination **en Python**, `break-before: page` sur la feuille, jamais sur un
  élément de grille ;
- `print-color-adjust: exact` ;
- tout en millimètres, aucune ressource extérieure ;
- ⚠️ **la géométrie vient du serveur**, en variables CSS
  (`--colonnes`, `--affiche-largeur`, `--affiche-hauteur`, `--qr`,
  `--rembourrage`, `--gouttiere`). Le gabarit n'écrit **aucun** millimètre
  d'affiche de son côté ; un test le vérifie ;
- ⚠️ **aucun mode d'emploi** (retouche du 03/09) : il est parti dans
  l'application. Il ne reste que le QR et le nom de la zone.

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

Et la carte voisine, « Qui envoie quoi », affiche désormais `a.libelle` au lieu
de `a.nom` — de même que la colonne « Téléphone » de la recherche de scans, qui
lit `r.appareil_libelle`. Les deux viennent de `contest.libelle_poste`.

### 3.9 Touché — `climbcontest/contest.py`

```python
CODE_APPAREIL_CARACTERES = 8

def libelle_poste(nom: str | None, appareil_id: str | None) -> str | None
```

⚠️ **C'est la seule fonction qui décide de la forme d'un nom de poste dans la
console.** `appareils()` rend `libelle`, `reussites_tracees()` rend
`appareil_libelle` ; les deux l'appellent. La forme est en arbitrage, elle doit
rester une modification d'un seul endroit.

Aucune requête de plus : le nom et l'identifiant sont déjà lus.

## 4. Contrats

### `GET /admin/postes`

| | |
| --- | --- |
| Rôle | `ORGANISATEUR` |
| Query | `zone` (optionnel) |
| 200 | `text/html`, la planche |
| 401 / 403 | anonyme / rôle insuffisant |

Aucun 409 : voir 3.6.

### `GET /admin/appareils` et `GET /admin/reussites-tracees` (modifiés)

Une clé de plus par ligne, jamais une de moins — l'ancienne reste :

```json
{"id": "3f9a1c2b-…", "nom": "Zone A", "libelle": "Zone A (3f9a1c2b)", …}
{"appareil_id": "…", "appareil_nom": "Zone A", "appareil_libelle": "Zone A (3f9a1c2b)", …}
```

`appareil_libelle` vaut `null` pour une saisie manuelle : elle n'a pas
d'appareil.

### `GET /admin/referentiels` (modifié)

```json
{"success": true, "categories": [...], "clubs": [...], "zones": ["A", "B", "C"]}
```

`zones` est **toujours** présent, y compris sans compétition active.

## 5. Ce qu'on ne fait pas, et pourquoi

| Non fait | Pourquoi |
| --- | --- |
| Écrire « Zone » dans le QR | Cinq caractères de plus par symbole, des modules plus petits, et un libellé qu'on ne pourrait plus changer sans réimprimer |
| Un identifiant de téléphone dédié | `appareil_id` existe depuis la spec 011 ; en inventer un deuxième serait une donnée de plus à tenir |
| Retirer la colonne « Identifiant » de la console | Elle porte le code seul, sélectionnable — la seule façon de le copier |
| Composer le libellé de la console dans le JavaScript | Il doit être le même dans toutes les vues, et une réponse d'API qui le porte déjà se teste |
| Valider la zone contre le plan, côté téléphone | Un catalogue périmé bloquerait un juge pour une étiquette qui ne référence rien |
| Signer le QR | Il n'ouvre aucun accès ; signer un papier posé sur une table est du théâtre |
| Une URL plutôt qu'un texte | L'appareil photo natif ouvrirait un navigateur, et le juge se retrouverait hors de son application |
| Une table `Poste` en base | Les zones sont déjà dans le plan, et le nom du poste vit sur le téléphone |
| Toucher au `<header>` de `juge.html` | Refondu en parallèle ; deux branches y fusionneraient en silence |

## 6. Budget de requêtes

`fiches.postes()` : **une** lecture de réglage (le plan), quel que soit le
nombre de zones. Aucune requête sur `Bloc`, `Participant` ou `Competition`.
