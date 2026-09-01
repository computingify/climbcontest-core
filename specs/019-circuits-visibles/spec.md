# Spec 019 — Les circuits, vus par l'organisateur et respectés par le juge

> **Statut : validée (porte 2) et codée — 01/09/2026.** Adrien : « tu merges
> la PR du lot A puis tu fais les lots B et C ». La porte 7 (merge) reste la
> sienne.
> Demandée par Adrien le 01/09/2026, à l'issue d'un test de bout en bout sur le
> vrai classeur : « j'aimerais bien aussi pouvoir avoir une vue des circuits de
> la compétition […] ont une difficulté et une couleur de prise aussi que les
> catégories qui doit faire ce blocs » et « si ce participant n'est pas censé le
> faire, il faut l'afficher sur l'application avant même de l'envoyer ».
>
> Deux points tranchés par Adrien avant rédaction :
> - un bloc hors circuit **avertit et se laisse forcer**, il ne bloque jamais ;
> - la vue des circuits vit **dans la console d'administration**, pas ailleurs.

## 1. Ce qui manque

### M1 — La couleur des prises n'est jamais lue

L'onglet `Plan` porte **deux** couleurs par bloc :

| Colonne | Index | Contenu |
| --- | --- | --- |
| F | 2 | Couleur de **difficulté** (`Jaune` < `Vert` < `Bleu` < `Mauve` < `Rouge` < `Noir`) |
| H | 4 | Couleur des **prises** |

`importer.py` ne lit que la première (`Bloc.couleur`). La couleur des prises
n'existe nulle part côté serveur. C'est pourtant elle qu'on cherche des yeux sur
le mur : deux blocs de difficulté `Rouge` dans la même zone ne se distinguent
que par leurs prises.

### M2 — Rien ne montre les circuits

La console affiche les participants, les réussites, les téléphones, le classeur,
la compétition, les archives. **Pas les blocs.** L'organisateur ne dispose
d'aucun écran pour répondre à « quels blocs composent le circuit U13 ? » ni,
surtout, à « le classeur a-t-il été lu correctement ? ».

Ce manque a un coût mesuré : le correctif du 01/09 (colonnes de circuit figées
à trois au lieu de cinq — voir le CHANGELOG) a laissé, sur le classeur de
novembre 2025, **37 blocs rattachés à aucun circuit et un circuit entier
absent**, sans que rien à l'écran ne puisse le montrer. Le rapport d'import
annonce désormais les circuits lus ; il ne dit toujours pas quels blocs sont
orphelins.

### M3 — Le juge peut valider un bloc que le grimpeur n'a pas à faire

Constaté par Adrien en scannant : un grimpeur, puis un bloc **hors de son
circuit**. L'application accepte, la réussite part, elle est écrite en base et
dans le classeur.

Elle ne fausse **pas** le classement — `classement.py` filtre par circuit, c'est
l'écart mesuré à 17 grimpeurs sur 98 qui a motivé ce filtre. Mais :

- le juge croit avoir validé quelque chose qui ne comptera jamais ;
- le grimpeur croit avoir marqué des points ;
- personne ne s'en aperçoit avant la remise des prix, si tant est qu'on s'en
  aperçoive.

Le contrôle est possible **hors ligne** : `/api/v2/catalog` envoie déjà
`participants[].categorie` et `blocs[].circuits`. C'est `catalogue.js` qui les
jette au rangement, pour une raison écrite et légitime — ne pas entreposer des
données de mineurs sur vingt-cinq téléphones de bénévoles.

## 2. Ce qu'on fait

### F1 — La couleur des prises entre en base

`Bloc.couleur_prises`, lue en colonne H, exposée par `Bloc.to_dict()`, archivée
par `cycle._donnees_brutes()`.

⚠️ `Bloc.couleur` ne change **pas** de sens : la validation par couleur
(`classement._valider_par_couleur`) et la teinte d'écran de l'application juge
s'appuient dessus. On ajoute, on ne renomme pas.

### F2 — Une vue « Circuits » dans la console

Rôle **organisateur** (elle ne fait que lire). Deux parties :

**a) Le contrôle de cohérence, en tête de page.** Trois compteurs, affichés
seulement quand ils ne sont pas nuls, chacun avec la liste :

| Anomalie | Ce que ça veut dire |
| --- | --- |
| Blocs sans aucun circuit | Une colonne de circuit n'a pas été lue, ou la croix manque dans le classeur. Ces blocs ne comptent pour personne. |
| Circuits sans aucun bloc | Le circuit existe mais son classement sortira vide. |
| Catégories sans circuit | Un participant porte « U19 F » alors qu'aucun circuit « U19 » n'existe. Ses réussites compteront toutes pour zéro. |

**b) Le tableau des blocs**, filtrable par circuit :

`tag` · zone · n° d'import · difficulté · couleur de prises · circuits ·
**catégories**

Les catégories sont **dérivées** : circuit `U13` → les catégories réellement
portées par des participants dont le circuit est `U13` (« U13 F », « U13 H »).
On n'invente pas « U13 F » si personne ne l'est.

### F3 — Le garde-fou du juge

**Sur le téléphone, hors ligne, avant l'envoi.**

Quand le grimpeur et le bloc sont tous deux scannés et que le bloc **n'est pas**
dans le circuit du grimpeur :

- la carte du bloc passe en avertissement ;
- le message dit les deux côtés : « **Ce bloc est U15 · ce grimpeur est U13** » ;
- le bouton devient « **Envoyer quand même** ».

L'envoi reste **toujours possible**. Raison, tranchée par Adrien : le classeur
peut être faux — il l'a été le 01/09 — et un juge bloqué en pleine compétition
n'a aucun recours.

Quand l'information manque (catalogue ancien, bloc ou grimpeur inconnu du
catalogue, participant sans catégorie), on **ne dit rien**. Un avertissement
qu'on ne sait pas justifier apprend à ignorer les avertissements.

**Sur le serveur, la trace.** `Success.hors_circuit_force` retient que le juge
est passé outre. Le statut **courant** — ce bloc est-il aujourd'hui dans le
circuit ? — reste calculé à la lecture : corriger le classeur doit faire
disparaître l'anomalie, pas la figer.

## 3. Ce qu'on ne fait pas

- **L'application Android n'est pas touchée.** Elle est publiée, gelée
  (`V3.1.4`), et elle est le plan de repli. Le garde-fou est pour la PWA.
- **On ne refuse rien côté serveur.** `/api/v3/successes` enregistre la réussite
  hors circuit comme les autres. Refuser casserait l'idempotence et laisserait
  une file bloquée sur un téléphone.
- **Le classement ne change pas.** Il filtre déjà par circuit. `verify_ranking`
  doit continuer à sortir 196/196.
- **Pas de correction du classeur depuis la console.** On signale, on ne
  réécrit pas : le classeur est la mémoire de la compétition.

## 4. Critères d'acceptation

| # | On vérifie | Attendu |
| --- | --- | --- |
| A1 | Import d'un `Plan` avec la colonne H remplie | `bloc.couleur_prises` renseignée, `bloc.couleur` inchangée |
| A2 | Import d'un `Plan` sans colonne H | `couleur_prises` à `None`, aucun avertissement |
| A3 | `GET /admin/circuits` en organisateur | 200, un bloc par ligne, circuits et catégories dérivées |
| A4 | Même route sans session | 401 |
| A5 | Un bloc n'a aucun circuit | Il apparaît dans le contrôle de cohérence, nommé |
| A6 | Un participant est « U19 F », aucun circuit « U19 » | Idem, catégorie nommée |
| A7 | Tout est cohérent | Le bloc de contrôle ne s'affiche pas du tout |
| A8 | PWA : grimpeur U11 + bloc de son circuit | Aucun avertissement, bouton normal |
| A9 | PWA : grimpeur U11 + bloc U17 | Avertissement nommant les deux circuits, bouton « Envoyer quand même » |
| A10 | PWA : envoi forcé | La réussite part, `hors_circuit_force` vrai en base |
| A11 | PWA : catalogue au format précédent | Rechargement complet, aucun avertissement entre-temps |
| A12 | PWA : participant sans catégorie | Aucun avertissement |
| A13 | `tools/verify_ranking.py` | 196 conformes, 0 écart |

## 5. Cas limites

**Un bloc appartient à plusieurs circuits.** C'est le cas normal — 36 blocs sur
67 en novembre 2025. Le test est une appartenance, pas une égalité.

**Un participant sans catégorie.** Le classeur en produit (risque R5), l'import
les garde volontairement. Circuit inconnu → aucun avertissement.

**Un dossard réaffecté entre le scan et l'envoi.** Le garde-fou a jugé sur le
porteur **au moment du scan**. C'est cohérent avec la décision du 28/08 : on
autorise, on trace. `hors_circuit_force` dit ce que le juge a vu, pas ce que la
base dira plus tard.

**Le catalogue a du retard.** Un bloc ajouté à 14 h est inconnu du téléphone :
`estDansLeCircuit` rend `null`, on se tait, et le rafraîchissement existant
répare tout seul.

**Le format du catalogue local change.** `FORMAT` passe de 2 à 3. Le marqueur
existe précisément pour ça et force un rechargement complet — sans lui, un
téléphone à jour garderait un catalogue illisible que le `304` du serveur ne
remplacerait jamais.
