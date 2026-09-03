# Plan — spec 033

Branche : `fix/revue-du-03-09`, partie de `origin/master` (817365c).

## 0. Ce qu'on corrige de la fois d'avant

Les specs 027 et 032 ont été écrites **après** le code, deux fois de suite. La
032 notait la correction en tête de son plan ; la voici appliquée : les trois
fichiers de `specs/033-revue-du-03-09/` sont écrits et commités **avant** la
première ligne de code, et le plan de test ci-dessous **avant** l'implémentation.

Trois lots de la même revue partent en parallèle (specs 034, 035, 036), chacun
dans son propre worktree et sa propre PR — c'est la demande explicite d'Adrien :
« pour tout ce qui est à faire dans une autre PR, tu travailles en parallèle
avec un agent et sur un worktree git ».

## 1. Étapes

- [ ] **1. La spec** — `spec.md`, `architecture.md`, `plan.md`, et
      `docs/specs-index.md`. Commit à part, avant tout code.
- [ ] **2. Impressions (R7, R8)** — `fiches.py` d'abord : c'est du Python pur,
      testable sans navigateur, et ça ne dépend de rien d'autre du lot.
- [ ] **3. API publique (R3, moitié serveur)** — `routes/public.py`, la route
      `/api/public/reglages` et ses tests.
- [ ] **4. Console (R1, R2, R12)** — `admin.html`. Les trois sont indépendants ;
      R12 en dernier, c'est le plus gros.
- [ ] **5. Page de résultats (R3 client, R4, R5, R6, R11)** — `resultats.html`.
      R3 client après la route, sinon il n'y a rien à interroger.
- [ ] **6. PWA (R9, R10)** — `catalogue.js` (forme 4) avant `juge.js` et
      `juge.html` : la donnée d'abord, le rendu ensuite.
- [ ] **7. Tests** — le tableau du §2, jusqu'au vert.
- [ ] **8. Captures** — avant/après pour chaque point visuel, à joindre à la PR.
- [ ] **9. Revue du diff complet** avec la grille de la phase 5, puis PR.

## 2. Plan de test

Trois familles : **nominal**, **cas limites**, **non-régression**.

### Nominal

| Module | Scénario | Attendu |
| --- | --- | --- |
| `fiches` | numéros « J6 », « J24 », « M40 » sur la même planche | même taille pour les trois, égale à `TAILLE_NUMERO_MM` |
| `fiches` | blocs des zones Z, A, M | la planche sort A, M, Z |
| `fiches` | deux blocs de la zone A, numéros classeur 7 et 3 | dans la zone, l'ordre du classeur est conservé (3 puis 7) |
| `public` | `GET /api/public/reglages` sur une compétition active | 200, `competition.groupes_masques` égal au réglage |
| `public` | le réglage change entre deux appels | le second appel rend le nouveau |
| `admin.html` | « Aucune cascade » coché | `#blocRegleCascade` **et** `#blocPorteeCascade` cachés |
| `admin.html` | « Comme le classeur » coché | les deux groupes visibles |
| `admin.html` | vue Réussites | la carte « dernières réussites » et son filtre par téléphone sont dans la page |
| `resultats.html` | premier chargement | `sansRecherche` vaut vrai, le champ n'est pas affiché |
| `catalogue.js` | catalogue de forme 4 | `categorie("42")` rend « U13 F », `circuitDuGrimpeur("42")` rend « U13 » |
| `juge.html` | en-tête | l'engrenage est un `<svg>` et le **dernier** enfant de `<header>` |
| navigateur | un classement masqué est rallumé dans la source des réglages | il réapparaît dans la barre **sans rechargement**, en moins de 5 s |
| navigateur | page mise en lecture puis rechargée | elle repart en lecture |
| navigateur | mur ouvert, fiche d'un grimpeur | la légende nomme les profils du plan |

### Cas limites

| Module | Scénario | Attendu |
| --- | --- | --- |
| `fiches` | numéro vide | la taille constante, aucune division par zéro |
| `fiches` | blocs sans zone | ils sortent **après** toutes les zones |
| `fiches` | aucun bloc | planche vide, aucune erreur |
| `public` | aucune compétition active | 409 et `success: false`, comme les routes voisines |
| `resultats.html` | `/api/public/reglages` répond 500 | la page garde ce qu'elle a, n'affiche pas d'erreur, continue de relire la charge |
| `resultats.html` | le classement affiché vient d'être masqué | bascule sur le premier visible |
| `resultats.html` | **tous** les classements masqués | le réglage est ignoré, la page n'est pas vide |
| `resultats.html` | rejeu d'archive | **aucun** appel à `/api/public/reglages` |
| `resultats.html` | `localStorage` indisponible | ni erreur, ni page cassée ; le défaut s'applique |
| `resultats.html` | valeur mémorisée abîmée | traitée comme absente |
| `catalogue.js` | participant sans catégorie | `categorie()` rend `null`, `circuitDuGrimpeur()` rend `null` |
| `catalogue.js` | catalogue rangé en forme 3 | jugé périmé, retéléchargé |
| `juge.js` | grimpeur sans catégorie | rien à droite de la carte |
| `resultats.html` | plan illisible par la page | aucune légende de profil, aucune erreur |

### Non-régression

| Module | Scénario | Attendu |
| --- | --- | --- |
| `resultats.html` | mode `?mur` | la recherche reste masquée, la rotation démarre en lecture |
| `resultats.html` | un classement éteint dans la console | il reste absent de la barre du téléphone (spec 032) |
| `resultats.html` | la rotation démarre quand les classements arrivent | inchangé (spec 032) |
| `admin.html` | « Comme le classeur » → « Sur mesure » | reste sélectionnable (spec 032, R2) |
| `admin.html` | recherche d'un scan par référence | inchangée |
| `fiches` | pagination huit par feuille | inchangée |
| `fiches` | fiches des grimpeurs | non touchées par R7/R8 |
| `catalogue.js` | test d'appartenance au circuit | inchangé malgré la forme 4 |
| `qr` | contenu des QR d'étiquettes | inchangé |

### Où vivent ces tests

| Fichier | Ce qu'il reçoit |
| --- | --- |
| `tests/test_etiquettes.py` | R7, R8 et leur non-régression |
| `tests/test_page_resultats.py` | la route `/api/public/reglages`, les défauts de la page |
| `tests/test_admin_cascade.py` | R1 (le second groupe caché) |
| `tests/test_console_lisible.py` | R2 (le style des boutons), R12 (la carte est là) |
| `tests/test_navigateur_reglages_resultats.py` | R3 côté page, R4 |
| `tests/test_navigateur_fiche.py` | R11 |
| `tests/test_pwa_juge.py` | R9, et R10 côté gabarit |
| `tests/js/circuit.test.mjs` | R10 côté catalogue (forme 4) |

## 3. Ce qui reste à trancher par Adrien

1. **R6 — la recherche masquée par défaut sur les téléphones des parents.**
   C'est ce qui est demandé et c'est ce qui est fait. Le prix : un parent qui
   ouvre la page ne voit plus le champ, il faut toucher `⌕`. Si l'usage montre
   que ça gêne, la même ligne peut distinguer le grand écran du téléphone.
2. **R3 — trois secondes.** C'est un compromis entre « immédiat » et le trafic
   d'une soixantaine de téléphones. Une seconde est possible sans changer une
   ligne de serveur si l'attente reste trop longue à l'usage.
3. **R7 — 19 mm.** Choisi pour que trois caractères tiennent. Si Adrien préfère
   un numéro plus gros au prix d'un « J24 » coupé, c'est une constante à
   changer.
