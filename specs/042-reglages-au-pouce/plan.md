# Spec 042 — plan

## Le plan de test, écrit avant l'implémentation

Un test en face de chaque critère d'acceptation. Les tests navigateur se
sautent proprement là où il n'y a pas de Chrome, comme les autres
`test_navigateur_*.py`.

| # | Fichier | Scénario | Résultat attendu | Critère |
| --- | --- | --- | --- | --- |
| T1 | `test_pwa_juge.py` | Le gabarit : le bouton de scan n'a plus de `style=` en ligne, et porte `class="action pleine"` | Aucun `width:100%` en ligne dans l'écran Réglages | C2 |
| T2 | `test_navigateur_juge_reglages.py` | Téléphone **sans nom**, Réglages ouverts | `#btnScannerPoste` calculé avec un fond opaque et une largeur > 300 px ; `#expliquerScanPoste` en `display: block` | C1 |
| T3 | idem | Téléphone **nommé** (`identite.nom` posé avant l'ouverture) | Fond `rgba(0, 0, 0, 0)`, largeur du texte < 300 px ; explication en `display: none` et hauteur 0 | C2 |
| T4 | idem | On tape « Z » dans `#nomTelephone`, puis on efface | La demande s'éteint à la frappe **et** se rallume à l'effacement, sans réouvrir l'écran ; `#poste` de l'accueil suit dans le même mouvement | C4 |
| T5 | `test_pwa_juge.py` | La source de `proposerDeNommerLePoste` | Elle touche `#poste`, `#btnScannerPoste` **et** `#expliquerScanPoste` ; `ouvrirLesReglages` l'appelle | C3, C5 |
| T6 | `test_navigateur_juge_reglages.py` | L'interrupteur, allumé puis éteint | `label.bascule` en `display: flex` (⚠️ pas `block`) ; `#garderGrimpeur` de largeur 0 ; `.glissiere` de 51 × 31 ; la pastille se déplace de ~20 px entre les deux états | C6 |
| T7 | `test_pwa_juge.py` | Le gabarit : l'ordre des enfants du `<label class="bascule">` | L'`<input>` précède **immédiatement** la `.glissiere`, et porte `role="switch"` | C6, C7 |
| T8 | `test_navigateur_juge_reglages.py` | Cliquer l'interrupteur, fermer, rouvrir les Réglages | L'état est retrouvé — le rangement `garder-grimpeur` n'a pas bougé | C8 |
| T9 | `test_pwa_juge.py` | Le numéro du cache et la **raison** de son changement | Le dernier commentaire `// vN le …` porte le numéro de la constante — l'un ne part jamais sans l'autre | C10 |
| T10 | `maquettes/` | Les deux thèmes | Captures clair et sombre de chaque état, sur l'application réelle | C9 |

⚠️ **T3 et T6 mesurent le style CALCULÉ, pas le gabarit.** C'est la leçon de
`#ligneRefus` : le gabarit disait la vérité pendant que l'écran affichait un
bouton mort. Un test qui relit le HTML ne voit pas la cascade.

⚠️ **T4 est un aller-retour, pas un aller.** Un test qui vérifierait seulement
l'extinction passerait au vert avec une règle qui cacherait la demande **pour
toujours** — et le carton changé de table deviendrait inaccessible, ce qui est
pire que le défaut qu'on corrige.

## Les étapes

- [x] **1. Le geste** — `juge.html` : `.action.pleine`, l'`id` sur
      l'explication, le `style=` en ligne retiré. `juge.js` :
      `proposerDeNommerLePoste()` gagne les deux nœuds, `ouvrirLesReglages()`
      l'appelle. T1, T2, T3, T4, T5.
- [x] **2. L'interrupteur** — `juge.html` : le CSS `label.bascule` /
      `.glissiere`, la ligne « Garder le grimpeur » réécrite. Aucun changement
      dans `juge.js`. T6, T7, T8.
- [x] **3. La coquille** — `sw.js` : `CACHE` en **`v10`**, avec la raison écrite
      à la suite des précédentes. T9.
- [x] **4. Les captures** — rejouer la planche sur le code **final** (et non
      sur le prototype), remplacer `maquettes/captures/`. T10.
- [x] **5. Le tour de la suite** — `pytest` complet dans un venv jetable
      (`requirements.txt` + `requirements-dev.txt`), et `node --test tests/js/`.
- [x] **6. L'index et le changelog** — une ligne dans `docs/specs-index.md`,
      une entrée sous `## [Non publié]` du `CHANGELOG.md`.
- [x] **7. Fusion — pour de vrai.** Les specs **040** et **030** ont été
      mergées sur `master` pendant l'écriture de ce lot : la fusion à blanc est
      devenue un vrai rebase. Deux conflits, tous deux attendus (`sw.js` sur le
      numéro de cache, `docs/specs-index.md` sur une ligne de tableau) ;
      `juge.html` a fusionné **sans conflit**, et c'est là qu'il fallait
      regarder — l'écran Réglages déroulé est dans `maquettes/`, section 4.
- [x] **8. PR** — résumé, plan de test, planche de maquettes en lien.

## Ce qui n'est pas dans ce lot

La section « Thème » de la spec 040. Elle est déjà écrite, sur sa propre
branche, et coupler les deux PR fabriquerait le conflit au lieu de l'éviter.
