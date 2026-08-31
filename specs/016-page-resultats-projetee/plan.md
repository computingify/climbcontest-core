# Plan — spec 016

## Étapes

- [x] **1. Les maquettes** — trois directions, mêmes données, 1920×1080, animées
      (`maquettes/`). Choix d'Adrien : **A**, avec défilement doux du reste du
      plateau.
- [x] **2. Le serveur** — `/resultats` supprimée, `reussites` ajouté, logo servi.
- [x] **3. La page** — bandeau, podium, colonnes, FLIP, flèches, rotation,
      défilement, mode clair/sombre, mise en page téléphone.
- [x] **4. Les tests** — 404, contrat d'API, mécanismes vérifiables.
- [x] **5. L'infrastructure** — proxy `edge`, portail et Caddy d'`intra`.
- [x] **6. Vérification à l'écran** — 1920×1080, 1280×720, 1280×470 (débordement),
      390 px, mode sombre, et un vrai mouvement de classement provoqué par la
      console.
- [ ] **7. Le jour J** — vérifier sur le vrai vidéoprojecteur de la salle. Aucun
      test ne remplace ça : la luminosité de la salle et la distance de lecture
      ne se simulent pas.

## Plan de test

### Ce que pytest vérifie

| Scénario | Attendu | Critère |
| --- | --- | --- |
| `GET /resultats` | **404** | A11 |
| `GET /` | 200, du HTML, aucune donnée dedans | — |
| `GET /?mur` | même octet que `/` | — |
| Charge utile de `/api/public/classement` | porte `reussites` | — |
| Chaque ligne porte `rang, score, blocs, nom, dossard` | et la page les lit | — |
| `/static/logo-club.png` | 200, et c'est bien un PNG | — |
| La page réutilise ses lignes (`etat.noeuds`, `.animate(`) | présent | A4 |
| Fond clair par défaut, `body.sombre` existe | présent | A8 |
| Rotation sur catégories **et** circuits | présent | A6 |
| Défilement du débordement | `programmerDefilement` présent | A3 |
| `prefers-reduced-motion` honoré | présent | A13 |
| Aucune ressource externe | inchangé | A9 |
| `innerHTML` ne sert qu'à vider | inchangé | — |

### Ce qui se vérifie dans un navigateur, et qui l'a été

| Écran | Résultat |
| --- | --- |
| 1920×1080, catégorie de 24 | **les 24 visibles**, lignes de 96 px | A1 |
| 1280×720 | les 24 encore visibles | A2 |
| 1280×470 (forcé) | débordement de 184 px → défilement en boucle de 18 s | A3 |
| Mouvement réel (7 réussites saisies depuis la console) | `▲8` sur le grimpeur qui monte, `▼1` sur les sept doublés, pulsation, glissement | A5 |
| Deux ex æquo en tête | **deux médailles d'or**, le suivant troisième | — |
| Nœuds DOM après deux rafraîchissements | le **même** élément (`memeNoeud: true`) | A4 |
| Mode sombre | fond nuit, lisible | A8 |
| Téléphone 390 px | bandeau sur deux lignes, chips, recherche, aucun débordement horizontal | A12 |

### Non régression

| Suite | Résultat |
| --- | --- |
| `pytest` | **761 vert** |
| `node --test tests/js` | 124 vert |
