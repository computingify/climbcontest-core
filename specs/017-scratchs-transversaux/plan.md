# Plan — spec 017

## Étapes

- [x] **1. Extraire `_classer()`** de `calculer_groupe()`, avec un filtre de
      blocs par membre. Vérifier immédiatement que `verify_ranking.py` annonce
      toujours 196/196 — c'est le filet de sécurité de tout le reste.
- [x] **2. `calculer_scratch()`**, `genre_de()`, `_scratchs()`.
- [x] **3. L'ordre explicite** des types dans la réponse publique.
- [x] **4. La page** : les scratchs entrent dans la rotation du mur.
- [x] **5. Les tests** — 9 unitaires + l'ordre de l'API.
- [x] **6. Vérification sur données réelles** — la fixture de novembre 2025.

## Plan de test

| Scénario | Attendu | Critère |
| --- | --- | --- |
| Deux circuits, deux genres | `Scratch`, `Scratch F`, `Scratch H` produits | A1 |
| Une réussite hors du circuit du grimpeur | ne compte pas, même au scratch général | A2 |
| Composition des groupes genrés | aucun mélange | A3 |
| Un seul circuit | aucun scratch | A4 |
| Un seul genre | seulement `Scratch` | A4 |
| Catégorie sans genre | au général, dans aucun genré | A5 |
| Classement club | somme des seules catégories | A6 |
| `verify_ranking.py` sur novembre 2025 | **196 conformes, 0 écart** | A7 |
| Ordre de `/api/public/classement` | catégories → circuits → scratchs → club | A8 |
| Bloc partagé entre deux circuits | le score du scratch **diffère** de celui de la catégorie (2000 → 1500) | § 3 |

### Sur données réelles (novembre 2025, 98 grimpeurs)

| Mesure | Valeur |
| --- | --- |
| Blocs appartenant à plus d'un circuit | **51 sur 67** |
| Écarts entre `Scratch F` et les catégories féminines | 54 sur 57 |
| Tête du scratch général | n°67, 4978 |
| Tête du scratch féminin | n°74, **5110** — plus haut que le général, groupe plus petit |

Ces trois chiffres sont la raison du § 3 de la spec : ils doivent être dits au
micro, pas découverts devant le podium.

### Non régression

| Suite | Résultat |
| --- | --- |
| `pytest` | **779 vert** |
| `node --test tests/js` | 124 vert |
| `tools/verify_ranking.py` | 196 conformes, 0 écart |
