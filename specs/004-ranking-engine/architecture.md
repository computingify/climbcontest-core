# 004 — Architecture

## Le principe de séparation

```
  classement.py            ──  CALCULE. Pur. Aucun import Flask, aucun SQL.
      │                        Entrées : des dataclasses. Sortie : un Classement.
      │                        Comparable directement au classeur.
      │
  classement_service.py    ──  ALIMENTE et MÉMORISE. Charge depuis la base,
      │                        garde le résultat 5 s, gère les options.
      │
  routes/public.py         ──  EXPOSE. Sans authentification, pour la page
                               résultats et les téléphones des spectateurs.
```

Cette séparation est ce qui rend l'algorithme **vérifiable**. `classement.py`
prend des structures simples et rend un résultat : on peut lui donner les 1003
réussites de novembre 2025 et comparer les 196 scores et rangs qu'il produit à
ceux que le classeur Google avait calculés à l'époque. C'est le test
d'acceptation, et il tourne en continu.

Si le calcul avait été mêlé à SQLAlchemy, cette comparaison aurait demandé une
base, des fixtures, et aurait fini par ne plus être faite.

## L'algorithme, et comment il a été trouvé

Le classeur ne documente pas sa formule ; elle a été **reconstituée** à partir
de ses colonnes, puis validée sur données réelles. Le détail de la
rétro-ingénierie est dans
[classeur-google.md](../../docs/technical/classeur-google.md).

```
valeur(bloc)  =  1000 / nombre de membres du groupe l'ayant réussi
score(membre) =  round( somme des valeurs des blocs qu'il a tenus )
```

Un bloc réussi par une seule personne vaut 1000. Un bloc réussi par tout le
monde ne vaut presque rien. C'est une **cotation par la difficulté observée**,
et non par une difficulté annoncée : le mur se cote lui-même.

Deux conséquences qui ne sautent pas aux yeux :

- Le score d'un grimpeur **dépend de ce que font les autres**. Une réussite
  arrivée en fin de journée peut faire baisser le score de tous ceux qui avaient
  déjà ce bloc. C'est voulu, et c'est pourquoi le calcul repart toujours de zéro
  au lieu d'être incrémental.
- La valeur d'un bloc est **relative au groupe**. Le même bloc ne vaut pas la
  même chose en U11 et en U17.

### Le filtre par circuit, qui n'est pas un détail

**Seuls les blocs du circuit du grimpeur comptent.**

Sans ce filtre, 17 grimpeurs sur 98 obtenaient un score trop élevé — ils avaient
réussi des blocs hors de leur circuit, que le classeur ignore. C'est l'écart qui
a permis de trouver la règle : tant que les 196 valeurs ne tombaient pas
*toutes* juste, l'algorithme était faux quelque part.

Le piège est dans le vocabulaire. `U13 F` et `U13 H` sont deux **catégories**
d'un même **circuit** `U13`. Le classement « scratch » du classeur est par
**circuit**, pas toutes catégories confondues.

### Les ex æquo

Deux scores égaux partagent le même rang, et le suivant saute les places
occupées : `1, 2, 2, 4`. C'est ce que fait le classeur, vérifié sur les cas
réels de novembre 2025.

### La validation par couleur

Option **par compétition**, désactivée par défaut — elle n'était pas active en
novembre 2025, et le format change d'une édition à l'autre (décision du 28/08).

Le principe : `Jaune < Vert < Bleu < Mauve < Rouge < Noir`. Réussir **100 %**
des blocs de *N* couleurs plus difficiles valide d'office toutes les couleurs
plus faciles. Le réglage vit dans `Competition.options`, sous
`validation_couleur` : `0` désactive, `N` exige *N* couleurs pleines.

Un JSON dans une colonne plutôt qu'une colonne par option : les options de
format vont se multiplier (finales, coefficients, nombre de blocs comptés), et
chacune n'aurait valu qu'une migration.

## Le cache, et pourquoi il n'est pas prématuré

Le jour d'une compétition, **les trois quarts du trafic viennent des
spectateurs** qui rafraîchissent la page résultats. Ils ne produisent aucune
donnée ; ils relanceraient pourtant le calcul complet à chaque appel.

Deux plafonds, l'un derrière l'autre :

| Où | Durée | Effet |
| --- | --- | --- |
| Caddy, sur `edge` | 5 s | ~60 téléphones à 15 s d'intervalle → 12 requêtes/min atteignent le backend |
| `classement_service` | 5 s | Le calcul lui-même n'a lieu qu'une fois par 5 s et par worker |

Le cache est **par processus** — quatre workers gunicorn, quatre caches. Un
spectateur peut donc voir un classement jusqu'à cinq secondes plus vieux que son
voisin. C'est acceptable : tous lisent la même base, et cinq secondes de
décalage ne se remarquent pas sur un classement d'escalade. Un cache partagé
demanderait Redis ou une table de plus, pour un problème qui n'existe pas.

Ce qui serait un vrai défaut, c'est un classement **faux** — et il ne peut pas
l'être : chaque calcul repart de la base, il n'y a aucun état incrémental à
désynchroniser.

## Les données en entrée

Le service charge quatre choses, en quatre requêtes, pas une par participant :

| Quoi | D'où |
| --- | --- |
| Participants de la compétition | `Participant` |
| Blocs et leur couleur | `Bloc` |
| Affectation bloc ↔ circuit | `BlocCircuit` |
| Réussites | `Success` |

Puis il construit les groupes : un classement par **catégorie** (`U13 F`) et un
par **circuit** (`U13`, le « scratch »).

## L'API publique

```
GET /api/public/classement            tous les groupes
GET /api/public/classement?groupe=U13 F   un seul
GET /api/public/groupes               la liste, pour construire un menu
```

Trois choix :

**Aucune authentification.** C'est fait pour être ouvert dans le navigateur de
n'importe quel spectateur, sans rien installer. Ces routes sont exemptées de
CrowdSec côté `edge` — sinon 100 téléphones derrière le même NAT ressemblent
exactement à une attaque.

**Les noms sont inclus.** Ils sont déjà publics : imprimés sur les dossards,
annoncés au micro. Une page de résultats sans nom n'aurait aucun intérêt.
En revanche, rien d'autre ne sort — pas de date de naissance, pas de contact.

**`calcule_le` est renvoyé**, pour que la page puisse afficher « il y a 3 s » au
lieu de laisser croire à du temps réel.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `climbcontest/classement.py` | Le calcul. Pur, sans dépendance |
| `climbcontest/classement_service.py` | Chargement, cache, options |
| `climbcontest/routes/public.py` | Les trois routes spectateurs |
| `tests/test_classement.py` | L'algorithme, dont la comparaison au classeur |
| `tests/test_classement_api.py` | Les routes |
| `tools/verify_ranking.py` | Le test d'acceptation sur données réelles |
| `fixtures/contest-nov2025.json` | Les données de novembre 2025, **anonymisées** |

## Ce qui pourrait mal tourner

| Risque | Parade |
| --- | --- |
| L'algorithme diverge du classeur après une modification | `verify_ranking.py` sur les données réelles : 196/196 ou rien |
| Le calcul devient lent quand la compétition grossit | Mesuré : < 1 s pour 98 participants et 1003 réussites. Le cache plafonne la fréquence |
| Un spectateur voit un classement figé | `calcule_le` est affiché ; la fraîcheur est visible, pas supposée |
| Une catégorie orpheline fait planter la page | Classement vide et signalé, jamais d'exception |
| Les options JSON sont illisibles | Journalisé, options ignorées, valeurs par défaut |
