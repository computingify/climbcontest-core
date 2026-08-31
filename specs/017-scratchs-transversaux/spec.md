# Spec 017 — Les scratchs qui traversent les circuits

> **Statut : codée, en attente de relecture (31/08/2026).**
> Demandée par Adrien le 31/08 : « je veux un scratch où il y a tout le monde,
> et un scratch homme, un autre femme ».

## 1. Ce qui existe déjà, et qui prête à confusion

Le mot « scratch » désigne aujourd'hui **le classement d'un circuit** : « U13
scratch », c'est-à-dire les filles et les garçons U13 ensemble. C'est la
définition du classeur, et elle ne change pas.

Ce qui manquait, c'est la lecture **transversale** : un classement où figurent
tous les grimpeurs de la compétition, et deux autres par genre.

## 2. Ce qu'on ajoute

| Groupe | Qui | Type |
| --- | --- | --- |
| `Scratch` | tous les grimpeurs ayant un circuit | `scratch` |
| `Scratch F` | toutes les catégories féminines | `scratch` |
| `Scratch H` | toutes les catégories masculines | `scratch` |

**La règle de calcul ne change pas d'un iota.** Chaque grimpeur reste jugé sur
**les blocs de son propre circuit** — un U11 n'a jamais pu essayer les blocs
U17 — et la valeur d'un bloc reste `1000 / nombre de membres du groupe qui l'ont
réussi`. Seule la taille du groupe change.

### Ce qui n'est produit que si ça apprend quelque chose

- Le scratch général demande **au moins deux circuits** : avec un seul, il
  répéterait mot pour mot le « U13 scratch » d'à côté.
- Les scratchs genrés demandent **les deux genres** : sinon celui qui existe
  répète le général.

Un classement qui double son voisin ne fait pas gagner de temps ; il fait douter
de celui qu'on regarde.

### Le genre vient de la catégorie

« U13 F » → `F`, « U13 H » → `H`. Une catégorie sans genre — l'import est
tolérant, ça existe — figure au scratch général mais dans aucun des deux
genrés.

## 3. ⚠️ Ce qu'il faut savoir avant de l'annoncer au micro

**Les scores d'un scratch ne sont comparables qu'entre eux.**

En écrivant cette spec j'ai d'abord affirmé qu'une fille garderait, au scratch
féminin, le score de sa catégorie. **C'est faux**, et la fixture de novembre
2025 l'a montré en une exécution : **51 blocs sur 67 appartiennent à plus d'un
circuit** (`['U11', 'U13']`). Le dénominateur d'un scratch compte donc des
grimpeurs que la catégorie ne comptait pas — 54 écarts sur 57 grimpeuses.

Deux conséquences, à dire plutôt qu'à découvrir devant le podium :

1. **Un grimpeur a un score différent dans chaque classement où il figure.**
   C'était déjà vrai entre sa catégorie et son circuit ; ça le reste.
2. **Un groupe plus petit donne des blocs plus chers**, donc des scores plus
   hauts. Sur les données de novembre 2025, la première du scratch **féminin**
   affiche 5110 quand le premier du scratch **général** affiche 4978 — sans
   avoir grimpé davantage.

Et surtout : un scratch qui traverse les circuits compare des grimpeurs **qui
n'ont pas grimpé les mêmes blocs**. C'est une lecture transversale, pas un
titre. **La catégorie reste le résultat officiel**, celui du podium.

## 4. Ce que ça ne change pas

- **Le classement club** additionne les scores des **catégories** uniquement.
  Il ignore les scratchs, comme il ignorait déjà les circuits : les compter
  reviendrait à compter chaque grimpeur quatre fois.
- **Les classements existants** sont calculés exactement comme avant :
  `tools/verify_ranking.py` reproduit toujours **196 scores et rangs sur 196**
  du classeur de novembre 2025, sans écart.

## 5. Où ça se voit

- `/api/public/classement` renvoie les trois nouveaux groupes, de type
  `scratch`. L'ordre de la réponse devient explicite — catégories, circuits,
  scratchs, club — parce que c'est l'ordre de la barre, donc l'ordre du cycle
  sur le mur. Trié sur le seul nom de type, « club » passait avant « scratch ».
- La page de résultats les fait **défiler sur le mur** avec les autres, et les
  propose au doigt sur téléphone.

## 6. Critères d'acceptation

| # | Critère | Vérification |
| --- | --- | --- |
| A1 | Les trois scratchs sont produits quand il y a ≥ 2 circuits et 2 genres | Test unitaire |
| A2 | Chacun reste jugé sur les blocs de **son** circuit | Test : une réussite hors circuit ne compte pas |
| A3 | `Scratch F` et `Scratch H` ne se mélangent pas | Test |
| A4 | Aucun scratch avec un seul circuit ; aucun genré avec un seul genre | Tests |
| A5 | Une catégorie sans genre figure au général, dans aucun genré | Test |
| A6 | Le classement club est inchangé | Test : somme des catégories |
| A7 | Les classements existants ne bougent pas | `verify_ranking.py` : 196/196 |
| A8 | L'ordre de l'API est catégories → circuits → scratchs → club | Test de route |
