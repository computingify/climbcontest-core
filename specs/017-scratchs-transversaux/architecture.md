# Architecture — spec 017

## 1. Le point dur : un groupe, plusieurs circuits

`calculer_groupe()` ne savait travailler que sur **un** circuit : il en dérivait
`blocs_du_circuit`, le même filtre pour tout le monde. Un scratch qui traverse
les circuits a besoin d'un filtre **par membre**.

Le calcul est donc extrait dans `_classer()`, qui reçoit `blocs_par_membre` :

```
calculer_groupe(...)   →  {chaque membre : les blocs du circuit du groupe}  ┐
                                                                            ├→ _classer()
calculer_scratch(...)  →  {chaque membre : les blocs de SON circuit}        ┘
```

Rien d'autre ne change : les mêmes lignes calculent les réussites tenues, la
valeur des blocs, les scores et les rangs. C'est ce qui garantit qu'un scratch
ne pourra pas diverger du reste — il n'y a qu'un seul chemin de calcul.

`verify_ranking.py` sert de filet : il rejoue le classeur de novembre 2025 et
doit toujours annoncer **196 conformes, 0 écart**.

## 2. Les nouvelles fonctions

| Fonction | Rôle |
| --- | --- |
| `blocs_du_circuit(blocs, circuit)` | l'ensemble des blocs d'un circuit, extrait pour être réutilisé |
| `genre_de(categorie)` | « U13 F » → `F` ; `None` si la catégorie n'en porte pas |
| `calculer_scratch(groupe, membres, …)` | un classement qui traverse les circuits |
| `_scratchs(...)` | décide **lesquels** produire, et les nomme |
| `_classer(...)` | le calcul commun, avec le filtre par membre |

`_scratchs()` porte la règle « ne produire que ce qui apprend quelque chose » :
pas de scratch général sous deux circuits, pas de scratch genré sous deux
genres.

## 3. L'ordre d'affichage

`ORDRE_DES_TYPES = {categorie: 0, circuit: 1, scratch: 2, club: 3}` dans
`routes/public.py`. Le tri se faisait sur `(type, groupe)`, c'est-à-dire sur
l'alphabet : « club » passait avant « scratch ». Ça se voit sur le mur, où
l'ordre de la réponse est l'ordre du cycle.

## 4. Côté page

`TYPES_MUR` accueille `scratch` : les trois nouveaux classements entrent dans la
rotation. Le classement club reste hors cycle et consultable au doigt.

## 5. Fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/classement.py` | `_classer` extrait, `calculer_scratch`, `genre_de`, `_scratchs` |
| `climbcontest/routes/public.py` | ordre explicite des types |
| `climbcontest/templates/resultats.html` | les scratchs dans la rotation |
| `tests/test_classement.py` | 9 tests |
| `tests/test_classement_api.py` | l'ordre de la réponse |
