# Plan — spec 026

Trois livraisons qui tiennent chacune debout toute seule. L'ordre n'est pas
négociable : chacune est inutile sans la précédente, et **aucune ne casse quoi
que ce soit si la suivante n'arrive jamais**.

## Itération 1 — Le serveur sait répondre (livrable seul)

Rien ne change pour personne : la page n'appelle pas encore la route.

- [x] `classement_service.blocs_du_grimpeur()` — les trois ensembles disjoints
- [x] `suivi.py` : `plan_public()` et `fiche()`
- [x] `GET /api/public/grimpeur/<id>`, avec la garde de compétition
- [x] `tests/test_suivi.py` — 28 tests
- [x] Les deux gardes anti-pourrissement du contrat de plan

**Vu à l'écran** : `curl /api/public/grimpeur/1` rend les blocs et leurs états.

## Itération 2 — La fiche, et sa pile d'historique

- [x] `static/resultats/suivi.js` + `tests/js/suivi.test.mjs` (16 tests)
- [x] Le garde qui rend impossible une **seconde** définition de
      `blocs_du_grimpeur` : la spec 025 en ajoute une au même fichier, et git
      fusionnerait les deux **sans conflit** — la seconde écrasant la première
      en silence, l'ordre dans le fichier décidant laquelle survit
- [x] Le plan embarqué dans la page (`<script type="application/json">`)
- [x] `data-participant` sur les lignes ; délégation du clic ; mode mur exclu
- [x] La feuille, les trois états de bloc, les compteurs
- [x] Le dièse, `hashchange`, `history.back()`, `replaceState`

**Vu à l'écran** : A1, A2, A3, A7, A8, A10, A11, A15, A16.

## Itération 3 — Le mur

- [x] `static/resultats/plan.js` + `tests/js/plan.test.mjs` (22 tests)
- [x] Le rendu SVG, les états de zone, la couche de cadres
- [x] Le rebond, et son absence quand on explore
- [x] Le bouton « Le mur » de la fiche
- [x] `tests/test_navigateur_fiche.py` — le parcours entier

**Vu à l'écran** : A4, A5, A6, A9, A13, A14.

## Ce qui a été corrigé en route

Sept défauts, documentés dans la spec § 6 et chacun gardé par un test — trois
trouvés sur la maquette, quatre par la relecture :

1. La transition qui jouait le retour avant l'aller — corrigée en posant la
   position **avant** toute mesure.
2. La page devenue traversante au clic (`.cadre`) — corrigée par le préfixe
   `sf-`, et **couverte par le test de pointage** du navigateur, qui est le
   seul à pouvoir l'attraper.
3. Le drapeau qui contredisait l'historique — supprimé ; l'état du mur est lu
   dans l'adresse.

## Vérification

```bash
python -m pytest -q                       # 1365 tests
node --test "tests/js/*.test.mjs"         # 190 tests
python tools/serveur_de_demo.py           # pour regarder de ses yeux
```

## Décisions restées ouvertes

Elles sont dans la spec § 3 (hors périmètre) : le rejeu d'archive, le mur seul,
la couleur des prises, et le hors-circuit à loger dans la console.
