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
| **J, L, N, P, R** | **6, 8, 10, 12, 14** | `1` si le bloc appartient à ce circuit — **une colonne sur deux, cinq au plus** |
| T | 16 | Numéro du bloc dans sa zone |
| Y | 21 (dernier) | **Numéro de ligne du bloc dans l'onglet `Import`** |

Le contenu du QR code d'un bloc = **colonne D + colonne T** → `Z` + `J6` = `ZJ6`.

### La ligne 28 : combien de circuits, et où (correctif du 01/09)

La ligne 28 est l'en-tête. Elle porte les noms de circuits, **et eux seuls**,
dans les colonnes J, L, N, P, R. Les autres intitulés désignent la structure et
ne bougent jamais :

| Classeur | F | H | J | L | N | **P** | T · U · V · W · X · Y |
| --- | --- | --- | --- | --- | --- | --- | --- |
| U11 U17 Nov 2025 | `Dif` | `Prises` | `U11` | `U13` | `U15` | **`U17`** | `N°` `E` `D` `A1` `A2` `N°` |
| U11 U15 Mars 2026 | `Dif` | `Prises` | `U11` | `U13` | `U15` | — | idem |
| Gestion contest (2024) | `Dif` | `Prises` | `U10` | `U12` | `U14` | — | idem |

⚠️ **Cette section a été écrite sur le classeur de mars 2026, qui n'a que trois
circuits — et `importer.py` a figé « J, L, N » d'après elle.** Le classeur de
novembre 2025 en a **quatre** : la colonne P n'était jamais lue, le circuit U17
n'était jamais créé, et ses **37 blocs** n'étaient rattachés à aucun circuit.
Conséquence en cascade : le classement `U17` sortait vide (« aucun bloc
n'appartient au circuit »), et chaque réussite d'un grimpeur U17 comptait pour
zéro. Rien, nulle part, ne le signalait.

Les colonnes sont désormais **découvertes** dans l'en-tête, jamais figées, et
l'import **annonce les circuits qu'il a lus avec leur colonne** — « U17 (colonne
P) » — dans son rapport comme dans le journal. C'est ce chiffre-là qu'on compare
de tête à ce qu'on attend.

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

#### La grille s'agrandit toute seule (spec 015)

L'API Google **refuse** une écriture hors de la grille existante :

```
Range ('Import'!DZ12) exceeds grid limits. Max rows: 1000, max columns: 120
```

Le cas arrive pour de vrai : la spec 013 attribue au participant inscrit **à
chaud** le premier dossard libre, et ce numéro sort sans difficulté de la
largeur préparée dans la feuille. Le miroir ne marquant rien comme synchronisé
en cas d'échec (spec 002), **une seule réussite de ce genre bloquait son lot et
tous les suivants, indéfiniment** — la grille ne s'agrandit jamais seule.

`ClasseurGoogle.marquer_reussites()` appelle donc `agrandir_si_besoin()` avant
d'écrire : lecture de `gridProperties` (mise en cache), et `updateSheetProperties`
**uniquement** si la grille est trop petite, avec cinq lignes/colonnes de marge.

⚠️ **Agrandir la grille ne fait pas entrer le grimpeur dans les formules.**
Le classeur est écrit pour 120 grimpeurs et 50 blocs (`Résultats!H19:DC138`) :
au-delà, la réussite est bien posée dans `Import`, mais le classeur ne la compte
pas. C'est la page de résultats du **serveur** qui fait foi. La console le dit,
avec les deux chiffres, au moment de « Tester l'accès ».

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

⚠️ **Relecture exhaustive du 30/08** (les ~213 000 formules des deux classeurs
ont été extraites et dédupliquées par structure) : la formule réelle de
`Inter!DJ19` est plus riche que le résumé ci-dessus ne le disait.

- **Un interrupteur PAR CATÉGORIE** : `Listes!D29:D38` (colonne « Valid dif
  précé »). Vide = règle inactive pour cette catégorie. Constaté **vide
  partout** dans les classeurs de novembre 2025 ET de mars 2026 — la règle n'a
  jamais servi, et l'algorithme brut reproduit 196/196 résultats.
- **Deux variantes PAR GENRE** (`Listes!A23`/`B23` = F/H) : réussir 100 % des
  blocs d'une couleur valide en cascade les couleurs plus faciles, mais le
  plafond de la cascade diffère — les **3** premières couleurs pour un genre,
  les **2** premières pour l'autre.

**Ce que fait le backend** (`classement._valider_par_couleur`) : une option par
compétition (`options.validation_couleur = N`), inactive par défaut — N couleurs
pleines valident tout ce qui est plus facile que la plus facile d'entre elles.
**Ce n'est pas la même variante que le classeur.** Tant que la règle reste
inactive des deux côtés (l'état réel), aucun écart possible. Si elle devait être
activée pour une édition, il faudrait d'abord trancher la variante — et
l'implémenter à l'identique des deux côtés, sous peine d'un classement affiché
différent du classeur.

### La saisie manuelle

`Inter!HJ19` lit l'onglet `Saisie manuelle` : une grille de fiches papier par
grimpeur, cochable dans le classeur, qui compte au même titre qu'un scan.
⚠️ **Ce terme n'existe que dans le classeur de mars 2026** — celui de novembre
2025 additionne deux termes (`Import + couleur`), pas trois.

**Tranché depuis la spec 005** : la console offre la saisie manuelle
(`POST /admin/reussites`, source `manuel`, protégée par rôle), la réussite
entre en base et le miroir la pose dans `Import` — le classeur la compte donc
aussi. **La consigne d'exploitation qui en découle** : le jour J, on ne coche
PLUS la grille du classeur. Une case cochée là-bas ne serait vue que par le
classeur, jamais par la page de résultats — deux classements divergents.

---

## 5 bis. Ce que la relecture exhaustive du 30/08 a classé

L'extraction complète des formules (`~107 000` en novembre 2025, `~186 000` en
mars 2026, dédupliquées à ~400 structures) confirme que **tout ce qui touche au
classement est couvert** par le backend, et range le reste :

| Mécanisme du classeur | Où | Verdict |
| --- | --- | --- |
| Valeur de bloc `1000/n`, sans arrondi intermédiaire | `Résultats!H2` | ✅ backend identique (196/196) |
| Score `ROUND(Σ;0)`, rang `RANK` ex æquo partagé | `Résultats!DF/DG` | ✅ backend identique |
| Rang de départage pour l'AFFICHAGE (`RANK+COUNTIF-1`) | `Résultats!DH` | ✅ équivalent (tri stable de la page) |
| Filtre par circuit, scratch par circuit | `Inter!H19`, `Scratchs` | ✅ backend identique |
| Validation par couleur | `Inter!DJ19` | ⚠️ inactive partout ; variantes divergentes si activée (§ 5) |
| Saisie manuelle | `Inter!HJ19` (mars) | ✅ via la console (§ 5) |
| Détection doublons / catégorie inconnue à l'inscription | `Listes!L2,C5` | ✅ rapport d'import du backend |
| QR dossards et blocs (contenu : dossard nu, tag) | `QR Code` | ✅ généré localement (`qr.py`), même contenu |
| Pourcentage de réussite par grimpeur, tranches <50/75/90 % | `Résultats!FN,FU,D143` | ➖ analyse interne, non repris (volontaire) |
| Compteurs de réussites par bloc/catégorie | `Résultats!H140` | ➖ idem |
| Podium de cérémonie, règle « Trop d'exæquo » affichée | `Podium!C1` | ➖ affichage manuel de cérémonie, le classeur reste l'outil |
| `Fiches` — fiche du grimpeur : blocs du circuit, plan de la salle | `Fiches!O3:Z13` | ✅ reprise (spec 023, `fiches.py`) |
| `Stats` (classement filtrable) | mars 2026 | ➖ analyse |
| `XLSX` (normalisation des inscriptions importées) | mars 2026 | ➖ c'est l'amont : spec 008 (HelloAsso), non commencée |

Les inventaires bruts (une ligne par structure de formule, avec exemple et
nombre d'occurrences) ont été archivés le 30/08 ; l'outil d'extraction tient en
80 lignes contre l'API `spreadsheets.get` en lecture seule.

## 5 ter. Le jeton et le lien, réglés depuis la console (spec 015)

**Le lien.** `Competition.spreadsheet_id` porte l'identifiant, une compétition à
la fois. Il s'écrit depuis `/console` → **Classeur**, avec trois modes de
bascule (relier seulement / même compétition, autre feuille / nouvelle
compétition). Le détail est dans [la spec](../../specs/015-classeur-parametrable/).

**Le jeton.** Trois formes, lues dans cet ordre :

| Fichier | Contenu | Posé par |
| --- | --- | --- |
| `token.json` | le JSON de `Credentials.to_json()` | **la console** — consentement OAuth en un clic (spec 022), ou collage du JSON de `tools/exporter_jeton.py` |
| `token.pickle` | l'objet `Credentials` sérialisé | `scp` (chemin historique) |
| `token.base64` | le même, en base64 | repli pour un hébergement sans fichier binaire |

Cherchés dans `DOSSIER_SECRETS`, puis `CLIMBCONTEST_SECRETS_DIR`, puis le
répertoire courant.

La console n'accepte **que** le JSON : recevoir un pickle par HTTP ferait
appeler `pickle.loads()` sur du contenu venu du réseau, et une session
d'administrateur volée deviendrait une exécution de code sur la VM.
`tools/exporter_jeton.py` convertit un `token.pickle` existant, sur le Mac.

**Depuis la spec 022, la console fait le consentement elle-même**
(`sheets/consentement.py`) : un bouton, l'écran Google, le jeton posé. Le flux
demande `access_type=offline` **et** `prompt=consent` — sans le second, Google
ne redonne pas de `refresh_token` à un compte qui a déjà consenti, et on
reposerait un jeton qui meurt dans l'heure. Le `state` est aléatoire, rangé en
session, comparé puis **retiré** : un code d'autorisation ne se rejoue pas.

⚠️ **Le piège d'exploitation** : si l'écran de consentement du projet Google est
en état « Test », le `refresh_token` expire au bout de **7 jours**. Voir
[runbook-competition.md](../runbook-competition.md#poser-le-jeton-google).

Un jeton rafraîchi est **réécrit** dans `token.json` : sans ça, chaque
redémarrage du service repart d'un jeton périmé et redemande un rafraîchissement
à Google.

---

## 5 quater. Vérifier qu'on a le droit d'ÉCRIRE (spec 018)

Lire le classeur ne prouve rien sur le droit d'y écrire. Une feuille partagée
en **lecture seule** avec le compte du jeton répond au titre, aux onglets et à
la grille exactement comme une feuille en modification — et ne se trahit qu'au
premier lot du miroir, quarante secondes après le premier scan, quand les
réussites commencent à s'empiler « en attente ».

`ClasseurGoogle.essai_ecriture()` fait donc un aller-retour réel :

```
1. lire   Import!<dernier coin de la grille>   ← doit être VIDE, sinon on renonce
2. écrire « climbcontest-test <horodatage> »
3. relire                                       ← doit rendre ce qu'on a écrit
4. effacer                                      ← on remet comme c'était
```

**Le coin de la grille, jamais la matrice.** La ligne 1 porte les dossards, les
colonnes A à C portent les blocs, `D2:…` porte les « A » et `D103` un
horodatage. Tester là où le miroir écrit vraiment détruirait une réussite réelle
si l'effacement final échouait. Sur une grille de 120 × 1000, la cellule témoin
est `DP1000`.

La méthode **ne lève jamais** : son échec est la réponse attendue, pas une
panne. Elle rend `{"tentee", "cellule", "ecriture", "restauree", "message",
"plages_protegees"}`.

**L'angle mort, et ce qui le couvre.** Une protection posée sur `D2:DP103`
laisse le coin parfaitement écrivable et bloque pourtant le miroir. D'où
`plages_protegees()`, lue des métadonnées **déjà chargées** — `protectedRanges`
a été ajouté au `fields` de l'appel `spreadsheets.get` existant, ce qui ne coûte
aucune requête supplémentaire.

Dans la console : « Classeur » → **Tester l'accès en écriture**, un bouton
distinct de « Tester l'accès ». L'un écrit, l'autre pas, et ça doit se voir
avant de cliquer.

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
