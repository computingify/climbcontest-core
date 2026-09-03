# Plan — spec 034

## Étapes

- [ ] **E0 — La spec** (`spec.md`, `architecture.md`, `plan.md`), l'index, et
      les **maquettes** HTML statiques de l'écran console et de la planche
      imprimée. Commitées **avant** la première ligne de code : c'est la
      demande, et c'est ce qui manque aux specs 027 et 032.
- [ ] **E1 — `poste.js`**, le décodage, testable sur Node. Les tests d'abord
      dans le même commit, jamais dans un commit d'après.
- [ ] **E2 — Le geste dans la PWA** : le bouton dans les réglages, la fonction
      `scannerMonPoste()`, la coquille hors ligne (`sw.js` → `v4`).
- [ ] **E3 — `fiches.postes()`** et le préfixe côté Python, avec le test qui
      tient les deux préfixes égaux.
- [ ] **E4 — La route et le gabarit** `/admin/postes` + `postes.html`.
- [ ] **E5 — La console** : la carte dans la vue Téléphones, la clé `zones` de
      `/admin/referentiels`.
- [ ] **E6 — Vérification à l'écran** : serveur de démo, Playwright, captures de
      la console et de la planche.
- [ ] **E7 — Revue du diff complet**, changelog, PR.

## Plan de test

**Écrit avant l'implémentation.** Un test en face de chaque comportement.

### `tests/js/poste.test.mjs` — le décodage (Node)

| Scénario | Attendu |
| --- | --- |
| `CCPOSTE:Zone C` | `"Zone C"` |
| `ccposte:Zone C` (casse) | `"Zone C"` — un QR refait à la main n'est pas un QR mort |
| `CCPOSTE:  Mur jaune  ` | `"Mur jaune"` — nettoyé comme la saisie clavier |
| `CCPOSTE:` + 80 caractères | coupé à 60, comme `identite.LONGUEUR_NOM` |
| `CCPOSTE:Zone à l'ombre` | rendu tel quel — accents et apostrophes passent |
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
| `fiches` | plan d'usine (17 zones) | 17 affiches, une par zone |
| `fiches` | deux murs, même zone | **une** affiche |
| `fiches` | un mur sans zone (`None`) | ignoré, aucune affiche vide |
| `fiches` | ordre | trié par nom de zone |
| `fiches` | contenu du QR | `CCPOSTE:` + la zone, exactement |
| `fiches` | le SVG rendu | dimensionné à `COTE_QR_POSTE_MM` |
| `fiches` | taille de module à 80 mm | > `qr.MODULE_MINI_MM` |
| `fiches` | ce n'est pas un Micro QR | version ≥ 1, symbologie standard |
| `fiches` | `zone="C"` | une seule affiche |
| `fiches` | `zone="Q"` absente du plan | liste **vide**, pas une exception |
| `fiches` | plan dessiné dans la console | les zones du plan **courant**, pas celles d'usine |
| `fiches` | plan sans aucun mur nommé | liste vide |
| `en_feuilles` | 17 affiches, 2 par feuille | 9 feuilles, la dernière à 1 |
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
| `referentiels` | avec compétition | `zones` = les zones du plan courant |
| `referentiels` | sans compétition | `zones` **quand même** rempli, 200 |
| `juge.html` | le bouton existe | `#btnScannerPoste` dans `#ecranReglages` |
| `juge.html` | le `<header>` | **inchangé** par rapport à `origin/master` |
| `sw.js` | la coquille | contient `poste.js`, et le cache a changé de nom |
| `admin.html` | la carte | `#btnPostes` et `#pZone` dans `#vueTelephones` |

### Vérification à l'écran (E6)

| Écran | Ce qu'on regarde |
| --- | --- |
| `/console` → Téléphones | La carte, la liste des zones remplie |
| `/admin/postes` | 9 feuilles, deux affiches par feuille, QR net |
| `/admin/postes?zone=C` | Une seule affiche |
| `/juge` → Réglages | Le bouton sous le champ du nom |

### Suites complètes

```bash
.venv-dev/bin/python -m pytest tests/ -q
node --test "tests/js/*.test.mjs"
```

Les deux vertes avant la PR.
