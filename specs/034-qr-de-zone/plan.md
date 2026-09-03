# Plan — spec 034

## Étapes

- [x] **E0 — La spec** (`spec.md`, `architecture.md`, `plan.md`), l'index, et
      les **maquettes** HTML statiques de l'écran console et de la planche
      imprimée. Commitées **avant** la première ligne de code : c'est la
      demande, et c'est ce qui manque aux specs 027 et 032.
- [x] **E1 — `poste.js`**, le décodage, testable sur Node. Les tests d'abord
      dans le même commit, jamais dans un commit d'après.
- [x] **E2 — Le geste dans la PWA** : le bouton dans les réglages, la fonction
      `scannerMonPoste()`, la coquille hors ligne (`sw.js` → `v4`).
- [x] **E3 — `fiches.postes()`** et le préfixe côté Python, avec le test qui
      tient les deux préfixes égaux.
- [x] **E4 — La route et le gabarit** `/admin/postes` + `postes.html`.
- [x] **E5 — La console** : la carte dans la vue Téléphones, la clé `zones` de
      `/admin/referentiels`.
- [x] **E6 — Vérification à l'écran** : serveur de démo, Playwright, captures de
      la console et de la planche.
- [x] **E7 — Revue du diff complet**, changelog, PR.
- [x] **E8 — Les retouches du 03/09**, après relecture d'Adrien. Cinq
      décisions, cinq tests en face :
      la planche passe à **huit par A4** en deux colonnes, avec la géométrie
      déduite d'une seule constante ; le **mode d'emploi quitte le carton** ; le
      geste apparaît sur l'**écran d'accueil** de la PWA tant que le poste n'est
      pas nommé ; le nom envoyé à la console devient **« Zone A »**, composé par
      l'application ; et la console **distingue deux téléphones du même nom**
      par le code court de leur appareil.

## Plan de test

**Écrit avant l'implémentation.** Un test en face de chaque comportement.

### `tests/js/poste.test.mjs` — le décodage (Node)

| Scénario | Attendu |
| --- | --- |
| `CCPOSTE:A` | `"Zone A"` — le libellé est **composé**, pas encodé |
| `ccposte:C` (casse) | `"Zone C"` — un QR refait à la main n'est pas un QR mort |
| `CCPOSTE:Zone Nord` | `"Zone Nord"` — **pas** de double préfixe |
| `CCPOSTE:  Mur jaune  ` | `"Zone Mur jaune"` — nettoyé comme la saisie clavier |
| `CCPOSTE:` + 80 caractères | coupé à 60, comme `identite.LONGUEUR_NOM` |
| `CCPOSTE:à l'ombre` | accents et apostrophes passent |
| `MOT_ZONE` | vaut « Zone », et `libelleDuPoste("A")` en dépend |
| `libelleDuPoste("")` | `null` — sinon « Zone » tout court effacerait un nom |
| `CCPOSTE:` (rien derrière) | `null` — **jamais** un renommage à vide |
| `CCPOSTE:   ` (que des espaces) | `null` |
| `ZJ6` (bloc) | `null` |
| `42` (dossard) | `null` |
| `https://x/juge?j=abc` (organisateur) | `null` |
| `""`, `null`, `undefined` | `null` |
| `PASCCPOSTE:x` (préfixe au milieu) | `null` — le préfixe est en **tête**, pas dedans |
| `texteDuQrDePoste("C")` | `"CCPOSTE:C"` |
| aller-retour `nomDePoste(texteDuQrDePoste(z))` | `z`, pour une poignée de noms |
| message pour `ZJ6` | contient « posé sur ta table » |
| message pour un lien d'organisateur | contient « organisateur » et **pas** « posé sur ta table » |
| message pour `CCPOSTE:` sans nom | dit que le QR ne porte **aucun nom** |

### `tests/test_postes.py` — la planche (pytest)

| Module | Scénario | Attendu |
| --- | --- | --- |
| `fiches` | plan d'usine (17 zones) | 17 affiches, une par zone, **3 feuilles** |
| `fiches` | deux murs, même zone | **une** affiche |
| `fiches` | un mur sans zone (`None`) | ignoré, aucune affiche vide |
| `fiches` | ordre | trié par nom de zone |
| `fiches` | contenu du QR | `CCPOSTE:` + la zone, exactement |
| `fiches` | le SVG rendu | dimensionné à `COTE_QR_POSTE_MM` |
| `fiches` | taille de module à 70 mm | > `qr.MODULE_MINI_MM` |
| `fiches` | ce n'est pas un Micro QR | version ≥ 1, symbologie standard |
| `fiches` | `zone="C"` | une seule affiche |
| `fiches` | `zone="Q"` absente du plan | liste **vide**, pas une exception |
| `fiches` | plan dessiné dans la console | les zones du plan **courant**, pas celles d'usine |
| `fiches` | plan sans aucun mur nommé | liste vide |
| `en_feuilles` | 9 affiches, 8 par feuille | 2 feuilles, la dernière à 1 |
| **densité** | `POSTES_PAR_FEUILLE` | vaut **8** |
| **densité** | `geometrie_postes(8)` | 2 colonnes × 4 lignes |
| **densité** | `geometrie_postes(6)` | 2 colonnes × 3 lignes, affiches **plus hautes**, même largeur |
| **densité** | 4, 6, 8, 10 par feuille | les affiches remplissent la feuille **exactement** |
| **densité** | le QR | ≥ **42 mm**, le plancher mesuré des étiquettes de blocs |
| **densité** | QR + rembourrage | tient dans la hauteur, à 6 comme à 8 |
| **densité** | un nom de 3 lettres | reste ≥ 10 mm, à 6 comme à 8 |
| gabarit | la géométrie | vient du serveur (`{{ geo.… }}`), jamais écrite en dur |
| gabarit | **mode d'emploi** | **absent** de l'affiche |
| gabarit | le mot « Zone » | vient de `fiches.MOT_ZONE` |
| route | la page rendue | porte `--colonnes`, `--affiche-hauteur`, `--qr` du serveur |
| route | anonyme | 401 |
| route | rôle insuffisant | 403 |
| route | organisateur, sans compétition active | **200** — le plan ne dépend pas d'une compétition |
| route | organisateur | 200, une affiche par zone dans le HTML |
| route | `?zone=C` | une seule affiche, le HTML nomme la zone |
| route | `?zone=Q` inconnue | 200, page vide qui **nomme** la zone demandée |
| route | plan vide | 200, le HTML renvoie vers `/admin/plan` |
| gabarit | ressources extérieures | aucune (`http://`, `https://`, `//cdn`) |
| gabarit | impression | `@page`, `margin: 10mm`, `print-color-adjust` |
| gabarit | pagination | `break-before: page` sur `.feuille`, pas sur l'affiche |
| **cohérence** | préfixe `poste.js` == `fiches.PREFIXE_QR_POSTE` | égaux |
| **cohérence** | `MOT_ZONE` de `poste.js` == `fiches.MOT_ZONE` | égaux |
| **cohérence** | le QR | ne contient **pas** le mot « Zone » |
| **décodeur** | OpenCV relit le QR produit | le texte exact, pour 6 noms de zone |
| gabarit | budget de hauteur | QR + rembourrage ≤ hauteur d'affiche, et 3 × 90 ≤ 277 |
| `referentiels` | avec compétition | `zones` = les zones du plan courant |
| `referentiels` | sans compétition | `zones` **quand même** rempli, 200 |
| `juge.html` | le bouton existe | `#btnScannerPoste` dans `#ecranReglages` |
| `juge.html` | l'écran d'accueil | `#poste` / `#btnPoste` hors des écrans, avec son petit texte |
| `juge.html` | le bloc d'accueil | `hidden` par défaut |
| `juge.js` | une seule décision | `$("poste").hidden` écrit **une** fois, `proposerDeNommerLePoste` appelée trois |
| `juge.html` | le `<header>` | ne contient **pas** `btnScannerPoste` — un test qui survit au merge |
| `sw.js` | la coquille | contient `poste.js`, et le cache a changé de nom |
| `admin.html` | la carte | `#btnPostes` et `#pZone` dans `#vueTelephones` |
| `admin.html` | le libellé | `a.libelle` et `r.appareil_libelle`, plus jamais `r.appareil_nom \|\|` |

### `tests/test_postes.py` et `tests/test_tracabilite.py` — le libellé d'un poste

| Scénario | Attendu |
| --- | --- |
| `libelle_poste("Zone A", "3f9a1c2b-…")` | `"Zone A (3f9a1c2b)"` |
| **deux téléphones, même nom** | **deux libellés différents** |
| code | 8 caractères, comme la colonne « Identifiant » |
| téléphone sans nom | `"Sans nom (3f9a1c2b)"` |
| saisie manuelle (aucun appareil) | `None` — la console dit « saisie de … » |
| nom sans appareil | le nom, inchangé |
| bout en bout | `CCPOSTE:A` → « Zone A » → « Zone A (3f9a1c2b) » |
| les deux vues de la console | **le même** libellé pour le même appareil |

### Vérification à l'écran (E6)

**Fait le 03/09.** Les captures sont dans `captures/`.

| Écran | Ce qu'on a vu |
| --- | --- |
| `/console` → Téléphones | La carte est là, la liste porte les 17 zones du plan |
| `/admin/postes` | ⚠️ **Un défaut** : le mode d'emploi sortait coupé — 164 mm de contenu dans 136. Corrigé en passant à l'horizontale, 3 par page |
| `/admin/postes` (après) | 6 feuilles, trois affiches par feuille, rien de coupé |
| `/juge` → Réglages | Le bouton sous le champ du nom, avec son explication |

**Refait le 03/09 après les retouches.** Les captures sont dans `captures/`.

| Écran | Ce qu'on a vu |
| --- | --- |
| `/admin/postes` à **8 par A4** (`captures/planche.png`) | Deux colonnes de quatre, QR de 48 mm, plus aucun mode d'emploi, rien de coupé |
| `/admin/postes` à **6 par A4** (`captures/planche-a-six.png`) | La même chose, plus aérée — la comparaison sur laquelle Adrien tranche |
| `/juge`, poste pas nommé (`captures/juge-accueil.png`) | Le petit texte en haut, le bouton juste dessous, au-dessus des cartes de scan |

⚠️ **Un piège repayé** : avec `--virtual-time-budget`, la capture partait
**avant** que `demarrer()` ait lu l'identité dans IndexedDB — le bloc du poste
apparaissait vide sur l'image alors qu'il était correct dans le navigateur. La
leçon est déjà écrite dans `tests/navigateur.py` ; le temps virtuel court plus
vite que le stockage.

C'est exactement ce que la vérification à l'écran est censée attraper, et
qu'aucun test n'attrapait : la géométrie d'impression ne se relit pas, elle se
regarde.

### Suites complètes

```bash
.venv-dev/bin/python -m pytest tests/ -q
node --test "tests/js/*.test.mjs"
```

Les deux vertes avant la PR.
