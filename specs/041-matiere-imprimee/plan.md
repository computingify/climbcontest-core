# Plan : 041 — La matière imprimée

## Étape 1 — Établir l'écart (fait)

- [x] Remonter l'état réel : la 035 est mergée (#95), ses cinq décisions sont
      au § 7 bis, la 039 (#109) en a livré la palette
- [x] Comparer la direction A de `specs/035-*/maquettes/index.html` au
      `juge.html` d'aujourd'hui, règle par règle
- [x] Constater que la **pastille en aplat existait déjà** — l'écart est plus
      étroit qu'annoncé : il ne reste que la matière, pas la mise en page
- [x] Corriger deux faits périmés : la porte 2 du plan de la 035 était encore
      cochée « en attente », et l'index disait « décision en attente »

## Étape 2 — Montrer avant de faire (fait)

- [x] Servir le **vrai** `juge.html` et poser l'état comme `redessiner()`
- [x] Capturer avant / après à 390 × 844 : trois états, deux thèmes
- [x] `maquettes/index.html` — la planche avant / après
- [x] **Porte : Adrien valide la matière** — validée, avec deux réserves
- [x] Cinq ombres et trois traitements du « Noir », le témoin refusé compris
- [x] `maquettes/reglages.html` — la planche des deux réglages
- [x] **Porte : Adrien tranche** — **S3** (courte, puis floue) et **N2**
      (la carte du Noir reste papier)

## Étape 3 — Implémenter (fait)

- [x] `couleurs.js` : `estLeNoir(nom)`, déduit du nom et jamais de la valeur
- [x] `juge.js` : la classe `encre` sur `#carteBloc`, posée dans `redessiner()`
- [x] `juge.html` : G1 à G5, et les images-clés du souffle réécrites
- [x] `sw.js` : la coquille passe en **v7**
- [x] Deux tests sur `estLeNoir`

## Étape 4 — Ce qui ne se fait pas depuis un Mac

- [ ] Essai sur un vrai téléphone, en salle, avant la mise en production
- [ ] L'éblouissement (D2 de la 035) : jamais mesuré, toujours pas mesuré ici

## Plan de test

### Ce qui se teste sans navigateur

| Module | Scénario | Résultat attendu |
| --- | --- | --- |
| `couleurs.js` | `estLeNoir("Noir")`, `"  NOIR "`, `"noir"` | `true` — les règles de lecture du classeur, comme `couleurDeCircuit` |
| `couleurs.js` | `estLeNoir` sur les cinq autres circuits | `false` : leur carte reste teintée |
| `couleurs.js` | `estLeNoir(null)`, `undefined`, `""`, `42` | `false`, jamais d'erreur — le bloc pas encore scanné passe ici à chaque rendu |
| `couleurs.js` | « Noir » vaut deux couleurs selon le thème, le marqueur n'en vaut qu'une | Fige le fait que le marqueur ne lit **pas** la table des couleurs |

### Ce qui se mesure au navigateur

Le CSS ne se teste pas ; il se **mesure**. La page réelle, servie à 390 × 844,
l'état posé comme `redessiner()`, puis `getComputedStyle`.

| # | Mesure | Relevé |
| --- | --- | --- |
| M1 | Ombre du bouton actif, thème clair | deux couches : `0 3px 0` à 26 % d'encre, `0 9px 20px -8px` à 50 % |
| M2 | Ombre du bouton actif, thème sombre | les mêmes, sur l'encre **claire** — la matière suit le thème |
| M3 | Liseré du bouton | `2px` dans les deux thèmes |
| M4 | Bouton **désactivé** | `box-shadow: none`, `border-top-style: dashed`, `2px` |
| M5 | Pastille, circuit Jaune, clair | liseré `rgb(23, 20, 15)`, aplat `rgb(245, 183, 46)` — la teinte du circuit est **exacte** (C1) |
| M6 | Pastille, circuit Jaune, sombre | liseré `rgb(244, 243, 240)` — de la craie, pas du noir invisible |
| M7 | Carte du bloc, circuit **Noir**, clair | `rgb(252, 251, 249)` — du papier, pas de gris (N2) |
| M8 | Carte du bloc, circuit **Noir**, sombre | `rgb(27, 30, 40)` — la carte active du thème sombre |

### Ce qui n'est couvert par aucun test

- **Le « waouh ».** Il se juge à l'œil, et il a été jugé : deux tours d'aperçu.
- **L'éblouissement en salle**, la lisibilité au soleil, la fatigue sur deux
  cents validations. Aucun ne se simule sur un Mac.
- **Le rendu sur un vrai téléphone.** Les captures sont faites par un moteur de
  bureau : le rendu des ombres et des liserés d'un iPhone peut différer d'un
  cheveu. C'est l'objet de l'étape 4.
