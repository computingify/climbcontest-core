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

## Étape 4 — Fusionner avec ce qui a bougé pendant (fait)

Master a bougé **deux fois** pendant le travail.

- [x] `#115` (la documentation dit l'état réel) : conflits sur `CHANGELOG.md` et
      `docs/specs-index.md`, les deux fichiers de la spec 038. Pour l'index, le
      bloc de master est repris **en entier** — #115 a réécrit les 37 lignes
      pour y porter les versions, garder l'autre côté les aurait écrasées
- [x] `#116` (spec 040, le thème au choix) : les **deux** branches avaient
      revendiqué la coquille `v7`. La 040 la garde, la 041 passe à **v8**
- [x] ⚠️ `juge.html`, `juge.js` et `couleurs.js` ont fusionné **sans conflit**,
      et c'est là qu'était le vrai risque : la 040 a ressuscité
      `--trait-circuit` en recopiant le bloc sombre. Re-supprimée, et le piège
      rendu **détectable** par un test
- [x] Mesurer l'intégration des deux specs sur les **six** croisements

## Étape 5 — Ce qui ne se fait pas depuis un Mac

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

### La couture avec la spec 040 — les six croisements

Le juge peut désormais **imposer** un thème depuis les Réglages. La matière
doit suivre ce choix, et pas le thème du système. Mesuré, pas raisonné :

| Système | Imposé | Circuit | Fond obtenu | Liseré |
| --- | --- | --- | --- | --- |
| clair | *(aucun)* | Jaune | `#F3EEE3` | encre |
| clair | **sombre** | Jaune | `#15161B` | craie |
| sombre | **clair** | Jaune | `#F3EEE3` | encre |
| sombre | *(aucun)* | Jaune | `#15161B` | craie |
| clair | **sombre** | Noir | `#15161B` | la carte du thème sombre |
| sombre | **clair** | Noir | `#F3EEE3` | le papier |

L'ombre et le liseré sont présents dans les six cas. C'est la conséquence
directe du choix d'architecture : tout est pris sur des **jetons**, donc rien
n'a eu à être ajouté pour que la 041 suive la 040.

### Ce qui n'est couvert par aucun test

- **Le « waouh ».** Il se juge à l'œil, et il a été jugé : deux tours d'aperçu.
- **L'éblouissement en salle**, la lisibilité au soleil, la fatigue sur deux
  cents validations. Aucun ne se simule sur un Mac.
- **Le rendu sur un vrai téléphone.** Les captures sont faites par un moteur de
  bureau : le rendu des ombres et des liserés d'un iPhone peut différer d'un
  cheveu. C'est l'objet de l'étape 4.
