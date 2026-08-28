# Le classeur Google — mécanique décodée

Résultat de l'analyse des trois classeurs des éditions 2024, novembre 2025 et
mars 2026 (lecture seule, valeurs **et** formules).

**L'algorithme de classement est entièrement reconstitué et validé** : il
reproduit 196 scores et rangs réels sur 196, sans écart, sur l'édition de
novembre 2025. Voir [§4](#4-validation-sur-données-réelles).

---

## 1. Les trois classeurs

| Identifiant | Titre | Catégories | Réussites |
| --- | --- | --- | --- |
| `1lOWe3j-4KG62wcKCsBd7T0Yj4iduFzH5QB76wS7dc9M` | Gestion contest import de l'appli | U10/U12/U14 F+H | 1678 |
| `1ilQ2-ogmTfpgYa_oz4ogO9SN_jJvSTL9BogcmHxHtEo` | U11 U17 Nov 2025 | U11→U17 F+H | 1003 |
| `1h3e8QUSXnCJLSYSFyB8X92cppDubeDx0yi8mn3NSh5s` | **U11 U15 Mars 2026** | U11/U13/U15 F+H | 0 (onglet `Import` vidé) |

> ⚠ Le troisième est celui que le code vise aujourd'hui. Le commentaire
> `# Dec 2025` dans `google_sheets.py` est périmé : le classeur a été réutilisé
> et renommé pour une compétition de **mars 2026**.

Le classeur se décrit lui-même en A1 de l'onglet `Listes` :
*« Outil pour 10 catégories, 5 circuits, 20 zones, 120 grimpeurs et 5 blocs par
zone (max 50 blocs) »*.

---

## 2. Les onglets

| Onglet | Rôle | Lu / écrit par le backend |
| --- | --- | --- |
| `Listes` | Grimpeurs, catégories, circuits, couleurs | **lu** (`F2:K`) |
| `Plan` | Un bloc par ligne : zone, numéro, couleur, circuits | **lu** (`D29:Y`) |
| `Import` | Matrice grimpeurs × blocs, une réussite = `"A"` | **écrit** |
| `Saisie manuelle` | Saisie papier de secours, alimente le calcul | non |
| `Inter` | Calculs intermédiaires : validation directe, par couleur, manuelle | non |
| `Résultats` | Valeur des blocs, scores et rangs **par catégorie** | non |
| `Scratchs` | Mêmes calculs **par circuit** (filles + garçons) | non |
| `Podium`, `Stats`, `Finales` | Affichage et analyses | non |
| `Fiches`, `QR Code` | Génération des fiches et des QR codes à imprimer | non |
| `Archives / Bilan`, `XLSX`, `Bénévoles` | Annexes | non |

---

## 3. Le modèle

### Catégorie et circuit

Une **catégorie** est une tranche d'âge et un genre : `U11 F`, `U13 H`…
Un **circuit** est la tranche d'âge seule : `U11`, `U13`, `U15`.

Filles et garçons d'une même tranche grimpent **le même circuit** mais sont
classés séparément. Le classement dit « scratch » du classeur, c'est le
classement **par circuit** (F + H ensemble) — pas un classement toutes
catégories confondues.

`Listes!A5:B14` porte la correspondance catégorie → circuit.

### Blocs

Onglet `Plan`, à partir de la ligne 29, une ligne par bloc :

| Colonne | Index dans `D29:Y` | Contenu |
| --- | --- | --- |
| D | 0 | Lettre de zone (`Z`, `D`, `M`…) |
| E | 1 | Rang du bloc dans la zone |
| F | 2 | Couleur de difficulté |
| H | 4 | Couleur des prises |
| J, L, N | 6, 8, 10 | `1` si le bloc appartient au circuit U11 / U13 / U15 |
| T | 16 | Numéro du bloc dans sa zone |
| Y | 21 (dernier) | **Numéro de ligne du bloc dans l'onglet `Import`** |

Le contenu du QR code d'un bloc = **colonne D + colonne T** → `Z` + `J6` = `ZJ6`.
La ligne 28 sert d'en-tête et porte les noms de circuits en J, L, N.

### Grimpeurs

Onglet `Listes`, à partir de la ligne 2 :

| Colonne | Contenu |
| --- | --- |
| F | Nom complet (= nom + prénom, colonnes H et I) |
| G | **Dossard** — c'est le contenu du QR code nominatif |
| J | Club |
| K | Catégorie |
| L | Marqueur d'erreur, `d` en cas de doublon de nom |
| M | `A` pour autoriser un doublon assumé |

> Les homonymes sont un cas **connu et prévu** par le classeur (colonnes L et M).
> Le backend actuel, lui, impose une contrainte d'unicité sur le nom et casse
> tout l'import dans ce cas (risque R5).

### La matrice `Import`

- Ligne 1 : les dossards, à partir de la colonne D → `colonne = dossard + 3`
- Colonne A : le numéro de bloc → `ligne = numéro + 1`
- Colonne B : le tag du bloc, retrouvé depuis `Plan`
- Une réussite = la lettre `"A"` dans la cellule d'intersection
- `D103` porte l'horodatage de la dernière écriture

C'est exactement ce que fait `GoogleSheet.update_google_sheet()`. ✅

---

## 4. L'algorithme de classement

### La règle

```
Pour un classement (catégorie « U13 F », ou circuit « U13 ») :

  membres  = les grimpeurs de ce groupe
  circuit  = U13
  réussites retenues = les couples (grimpeur, bloc) où
                       le grimpeur est membre
                       ET le bloc appartient au circuit

  valeur(bloc) = 1000 / nombre de MEMBRES ayant réussi ce bloc
  score(grimpeur) = arrondi( somme des valeurs de ses blocs réussis )
  rang = décroissant sur le score, les ex æquo partagent le même rang
```

Trois points que le backend actuel et la branche `feature/ResultAlgorithm`
**ne font pas correctement** :

1. **Le filtre par circuit est indispensable.** Une réussite sur un bloc hors du
   circuit du grimpeur est enregistrée dans `Import` mais **ne compte pas**. Sans
   ce filtre, 17 grimpeurs sur 98 obtiennent un score trop élevé.
2. **Le dénominateur est relatif au groupe classé.** Un même bloc n'a pas la même
   valeur en `U13 F`, en `U13 H` et au scratch `U13`.
3. **Le « scratch » est par circuit**, pas toutes catégories confondues.

### D'où ça vient dans le classeur

| Cellule | Formule | Traduction |
| --- | --- | --- |
| `Résultats!H2` | `=IF(SUMPRODUCT(H19:H138;DE19:DE138)=0;"";1000/SUMPRODUCT(...))` | valeur du bloc pour la catégorie |
| `Résultats!DF19` | `=ROUND(SUMPRODUCT(H19:DC19;H2:DC2);0)` | score du grimpeur |
| `Résultats!DG19` | `=RANK(DF19;DF19:DF138;0)` | rang, ex æquo au même rang |
| `Résultats!H19` | `=IF(Inter!H19+Inter!DJ19+Inter!HJ19>=1;1;"")` | le grimpeur valide le bloc |

Les six blocs de colonnes `DE`, `DK`, `DQ`, `DW`, `EC`, `EI`… (pas de 6)
correspondent aux six catégories. `Scratchs` a la même structure, par circuit.

### Validation sur données réelles

`tools/verify_ranking.py` rejoue l'algorithme sur les 1003 réussites de
novembre 2025 et compare aux résultats du classeur :

```
$ python3 tools/verify_ranking.py fixtures/contest-nov2025.json
  [OK  ] catégorie U11 F    11 grimpeur(s) conforme(s), 0 ecart(s)
  ...
  [OK  ] circuit   U17      11 grimpeur(s) conforme(s), 0 ecart(s)

Total : 196 conforme(s), 0 ecart(s)
```

Scores **et** rangs, sur 8 catégories et 4 circuits. C'est le test d'acceptation
du futur moteur de classement.

---

## 5. Deux mécanismes en réserve (à décider)

Le classeur sait faire deux choses de plus, qui n'étaient **pas actives** en
novembre 2025 — l'algorithme brut suffit à reproduire les résultats.

### La validation par couleur

Les couleurs de difficulté sont ordonnées (`Listes!A41:A46`) :

```
Jaune  <  Vert  <  Bleu  <  Mauve  <  Rouge  <  Noir
```

`Inter!DJ19` implémente la règle : **un grimpeur qui a réussi 100 % des blocs de
deux couleurs plus difficiles se voit valider automatiquement tous les blocs des
couleurs plus faciles.** L'onglet documente d'autres variantes prêtes à coller
(une seule couleur au lieu de deux, variantes par genre) — le format est donc
paramétrable d'une édition à l'autre.

> **À trancher** : reprend-on cette règle côté backend, et sous quelle variante ?
> Si oui, elle doit être configurable par compétition.

### La saisie manuelle

`Inter!HJ19` lit l'onglet `Saisie manuelle` : un juge peut inscrire une réussite
à la main, sans passer par l'application. C'est le mode papier de secours, et il
compte dans le classement au même titre qu'un scan.

> **À trancher** : l'équivalent côté backend serait une page d'arbitrage
> permettant d'ajouter ou de retirer une réussite. Utile le jour J, mais c'est
> aussi la seule route capable de fausser un classement — donc à protéger.

---

## 6. Relire le classeur

Accès en lecture seule, via le jeton OAuth existant du serveur :

```bash
python3 -m venv /tmp/gs && /tmp/gs/bin/pip install google-api-python-client google-auth-oauthlib
cd climbcontest-core                       # là où se trouve token.pickle
/tmp/gs/bin/python ../tools/dump_sheet.py <SPREADSHEET_ID>
```

Le script n'appelle que des méthodes de lecture (`spreadsheets().get`,
`values().batchGet`) — il ne peut pas écrire. Il produit un `dump_<id>.json`
contenant valeurs et formules de tous les onglets.

Puis, pour en tirer un jeu de test :

```bash
/tmp/gs/bin/python tools/extract_fixture.py dump_<id>.json fixtures/<nom>.json
```

> ⚠ **Données personnelles** : les classeurs contiennent les noms de mineurs et
> leurs clubs. Le jeu de test `fixtures/contest-nov2025.json` en a été
> volontairement expurgé — dossard et catégorie suffisent au calcul. Ne jamais
> committer un dump brut.
