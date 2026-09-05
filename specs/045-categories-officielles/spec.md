# Spec 045 — les catégories officielles FFME, et rien d'autre

## 1. D'où vient cette spec

Adrien, le 05/09/2026 :

> « Maintenant je voudrais que tu regardes sur le site de la FFME pour récupérer
> toutes les catégories officielles et que tu les mettes dans la console. Ainsi
> dans la modification ou l'ajout de participants le champ catégorie deviendra
> une simple liste sélectionnable. Pour l'importation des participants il faut
> que tu te débrouilles pour faire marcher ce qu'on reçoit avec les catégories
> dispo dans la console. Le principal risque c'est qu'il manque un espace ou un
> défaut de majuscule, il peut aussi arriver qu'il manque le U. »

C'est la **troisième fois** que le même défaut revient, sous trois formes :

| Quand | Ce qu'on a mesuré | Ce qu'on a fait |
| --- | --- | --- |
| 30/08 | 26 « U13 H » et **un** « U13 M » en production | Spec 013 : listes déroulantes au lieu de champs libres |
| 04/09 | « ANNONAY ESCALADE » et « Annonay Escalade » = deux clubs | Spec 008 : le formatage s'applique à **toutes** les sources |
| 05/09 | Ce qui arrive du classeur peut encore écrire n'importe quoi | **Cette spec** : le vocabulaire se ferme |

Le « U13 M » du 30/08 n'a jamais été corrigé. Il est toujours en base, ce
grimpeur est toujours seul dans un classement d'une personne, et **la liste
déroulante de la spec 013 ne l'a pas empêché** : elle proposait les valeurs
déjà présentes, donc « U13 M » avec les autres, et gardait un « + Autre… » pour
en inventer une nouvelle. Une liste qui se déduit des données ne peut pas
corriger les données.

## 2. Ce qu'on cherche

Qu'une catégorie ne puisse plus être qu'une des catégories **publiées par la
fédération**, quelle que soit la porte par laquelle elle entre — formulaire
d'ajout, crayon, salle d'attente HelloAsso, import du classeur — et que ce qui
arrive écrit de travers soit **rattaché sans qu'on ait à y penser**.

## 3. La source

**Règles d'accès et de participation FFME 2025-2026 (V3)**, §5.4 « Catégories »,
[PDF officiel](https://www.ffme.fr/wp-content/uploads/2025/12/Regles-de-participation-2025-2026-V3.pdf).
Cité tel quel :

> Les catégories en escalade sont :
> a) U9 : 7 et 8 ans
> b) U11 : 9 et 10 ans
> c) U13 : 11 et 12 ans
> d) U15 : 13 et 14 ans
> e) U17 : 15 et 16 ans
> f) U19 : 17 et 18 ans
> g) U21 : 19 et 20 ans
> h) Sénior : 21 à 39 ans
> i) Vétéran 1 : 40 à 49 ans
> j) Vétéran 2 : 50 ans et plus

Le même paragraphe confirme, mot pour mot, la règle d'année que
`categories.py` applique déjà — et qui avait été fausse d'un an dans la
première version de la spec 008 :

> Le changement de catégorie pour une saison sportive est déterminé en prenant
> en référence l'année de naissance et l'année civile débutant au cours de la
> saison sportive. Pour la saison sportive 2026 (01/09/2025 – 31/08/2026), un
> jeune né le 15/05/2009 aura 17 ans dans l'année civile 2026 et sera donc U19.

**Rien à changer de ce côté.** `annee_de_reference()` rend bien 2027 pour la
compétition du 15/11/2026. C'est la vérification qui manquait à la spec 008 :
elle s'appuyait sur un tableau de saison lu sur une page, pas sur le règlement.

## 4. Ce qui est décidé

### D1 — Neuf catégories, dix-huit entrées

Vétéran 1 et Vétéran 2 sont **fusionnés en « Veteran »**, sur décision d'Adrien
du 05/09 — et le règlement le dit lui-même au même endroit :

> Les vétérans 1 et 2 concourent dans la même catégorie vétéran et des podiums
> différenciés peuvent être organisés à l'issue de la compétition.

| | F | H |
| --- | --- | --- |
| U9 | `U9 F` | `U9 H` |
| U11 | `U11 F` | `U11 H` |
| U13 | `U13 F` | `U13 H` |
| U15 | `U15 F` | `U15 H` |
| U17 | `U17 F` | `U17 H` |
| U19 | `U19 F` | `U19 H` |
| U21 | `U21 F` | `U21 H` |
| Senior | `Senior F` | `Senior H` |
| Veteran | `Veteran F` | `Veteran H` |

**`H` et non `M`.** C'est l'écriture des 98 lignes de la compétition de
novembre 2025 (`fixtures/contest-nov2025.json`) : quinze « U13 H », zéro
« U13 M ». La forme majoritaire gagne, et « M » devient une écriture qu'on
rattache.

**Sans accent en base, accentué à l'écran.** La convention du dépôt interdit
les accents dans les littéraux Python — donc dans ce qui est stocké et dans le
JSON. La console affiche « Sénior » et « Vétéran » ; la base porte `Senior` et
`Veteran`. La table de correspondance vit dans le gabarit, en JavaScript, où
les accents sont admis.

### D2 — Le champ libre disparaît

« ＋ Autre… » quitte les trois endroits où l'on choisit une catégorie :
formulaire d'ajout, ligne ouverte au crayon, et le « à trancher » de la salle
d'attente HelloAsso. Décision d'Adrien du 05/09 : *liste seule*.

Conséquence assumée : **le club ne peut plus inventer une catégorie hors FFME**
depuis la console. S'il en avait besoin un samedi matin, il faudrait une
release. C'est le prix de la garantie, et c'est le sens de la demande.

⚠️ **Une exception, et une seule** : si un participant porte déjà une valeur
hors liste, cette valeur reste **choisie et sélectionnable dans sa propre
ligne**, marquée « hors liste ». Sans cette exception, ouvrir le crayon sur ce
grimpeur pour corriger son club changerait sa catégorie **en silence** — au
premier `<select>` qui ne contient pas la valeur courante, le navigateur en
choisit une autre tout seul.

### D3 — Une seule porte pour rattacher

`formatage.categorie()` — le point de passage **obligatoire** de toute écriture
de catégorie depuis la spec 008 — rend désormais la catégorie officielle quand
il la reconnaît. Il n'y a pas de second chemin à retenir, pas de fonction à
appeler en plus, donc pas d'endroit où l'on puisse oublier de l'appeler.

Ce qui est reconnu :

| Ce qui arrive | Ce qu'on écrit | Ce qui était en cause |
| --- | --- | --- |
| `u13 f`, `U13F`, `u13f` | `U13 F` | casse, espace manquant (déjà traité) |
| `13 F`, `13f` | `U13 F` | **le U manquant** |
| `U 13 H`, `U13-H`, `U13/H` | `U13 H` | séparateurs |
| `U13 M`, `U13 masculin`, `U13 garçon` | `U13 H` | **le M de production** |
| `U13 fille`, `U13 féminin`, `U13 Femme` | `U13 F` | écritures du genre |
| `sénior femme`, `SENIORS F` | `Senior F` | accents, pluriel |
| `Vétéran 1 H`, `veteran 2 h`, `V2 F` | `Veteran H`, `Veteran F` | la fusion D1 |
| `Homme U13` | `U13 H` | ordre inversé |

Ce qui **n'est pas** reconnu, et pourquoi :

| Ce qui arrive | Résultat | Pourquoi |
| --- | --- | --- |
| `U13` | inchangé | pas de genre : « U13 » à côté de « U13 F » couperait le classement en deux |
| `2016` | inchangé | quatre chiffres, c'est une **année**, jamais une catégorie |
| `U12 F`, `U10 H` | inchangé | pas un Under officiel |
| `Poussin`, `Minime F` | inchangé | ancienne nomenclature : on ne devine pas à quoi elle correspond |
| `U13 F et U13 H` | inchangé | **deux genres** : ambigu, donc refusé |

La règle des trois dernières lignes est la même : **on rattache ou on laisse
tel quel, on ne devine jamais à moitié.** Une inscription mal rangée sans que
personne ne le sache coûte plus cher qu'une ligne à corriger à la main.

### D4 — L'import garde ce qu'il ne sait pas rattacher, et le dit

Décision d'Adrien du 05/09. La ligne est importée, le participant existe, sa
catégorie reste telle qu'elle était écrite, et le **rapport d'import** la
signale :

```
⚠ Listes L34 : « POUSSIN » n'est pas une categorie FFME (importee telle quelle)
```

Ni ligne refusée — un classeur mal rempli ne doit pas bloquer un import la
veille de la compétition — ni catégorie vidée : ce que le classeur dit se
conserve, c'est ce qui permet de retrouver l'intention.

### D5 — Les catégories de l'édition se cochent

L'écran **Catégories** porte aujourd'hui un champ de texte libre, « Catégories,
séparées par des virgules ». Il devient une grille de neuf lignes à deux cases,
F et H — le même vocabulaire que partout ailleurs. Il ne peut plus contenir
qu'une catégorie officielle, ce qui referme la dernière porte par laquelle une
catégorie inventée pouvait entrer dans le barème.

Ce qui est stocké ne change pas de forme : la liste des libellés cochés
(`["U11 F", "U11 H", "U13 F", …]`).

### D6 — L'existant se rattrape en un clic, jamais en silence

Une carte paraît dans l'écran **Catégories** quand la base porte au moins une
catégorie hors liste :

```
2 catégories hors liste
  U13 M   →  U13 H      1 participant     [ rattacher ]
  POUSSIN →  —          3 participants    (à corriger à la main)
```

Le motif est celui d'« Appliquer le barème à tous » (spec 008) : **l'aperçu
d'abord, le bouton ensuite**, et rien ne bouge sans un clic. Ce qui n'a pas de
cible proposée est montré mais pas actionnable — on ne choisit pas à la place
de quelqu'un ce que « Poussin » veut dire.

⚠️ **Et le classeur ne le défait pas.** Corriger « U13 M » en base pendant que
le classeur écrit toujours « U13 M » ne servirait à rien : le prochain import
le remettrait. C'est le défaut fermé par la PR #125 pour le crayon, et il se
reposerait ici. D3 le règle à la racine : le prochain import lira « U13 M » et
écrira « U13 H », parce que le rattachement est **dans la porte d'entrée**, pas
dans un bouton de la console.

### D7 — Une édition neuve connaît ses catégories et leurs années

Demande d'Adrien du 05/09 :

> « Il faut aussi que les années des catégories soient automatiquement mises à
> jour lors de la création d'une nouvelle compétition. »

**Les années le sont déjà**, et c'est vérifié : l'écran Catégories les recalcule
à chaque ouverture depuis `Competition.date` (`bareme.reference()`), donc
changer la date de l'édition suffit à les décaler d'un an. Rien n'est figé en
base.

**Ce qui manque est ailleurs**, et c'est réel : une édition qui vient d'être
créée n'a **ni participant, ni circuit, ni catégorie déclarée**. Or les Under se
déduisent de ces trois sources — l'écran Catégories est donc **entièrement
vide** jusqu'au premier import. Il n'y a pas d'années à mettre à jour parce
qu'il n'y a aucune ligne.

Décision : **quand les trois sources sont vides, le barème prend les neuf
catégories officielles.** Une édition neuve ouvre donc sur les neuf tranches,
années calculées depuis sa date, avant tout import.

| L'édition dit… | Le barème prend… |
| --- | --- |
| rien (édition neuve) | les **neuf officielles** |
| U11, U13, U15 (cochées, importées ou portées par des inscrits) | U11, U13, U15 |

⚠️ **Le repli ne s'applique que sur le vide.** Une édition qui annonce U11-U15
garde trois tranches : « le plus petit Under l'emporte » y range un grimpeur de
12 ans en U15 s'il n'y a pas de U13, et c'est un comportement voulu, écrit et
testé depuis la spec 008. Un repli qui écraserait ce choix ferait apparaître des
catégories que la compétition ne fait pas grimper.

### D8 — Une catégorie sans inscrit ne paraît pas sur la page de résultats

Demande d'Adrien du 05/09 :

> « Si certaines catégories n'ont aucun participant il faut qu'elles soient
> désactivées de l'affichage de la page résultat, et si un import ajoute un
> participant dedans il faut la réactiver automatiquement. »

**C'est déjà le comportement, et par construction.** `classement.calculer_tout`
ne parcourt pas une liste de catégories : il parcourt les **participants** et
range chacun dans son groupe. Une catégorie que personne ne porte ne produit
aucun groupe, donc n'entre pas dans la charge publique, donc n'a aucun onglet
sur la page de résultats. Elle y entre au premier inscrit, sans geste — le
cache de classement est invalidé par l'import.

Deux raisons de l'écrire ici plutôt que de n'en rien dire :

1. **C'est D7 qui pourrait le casser.** Déclarer neuf catégories d'office, c'est
   exactement le changement qui ferait apparaître sept classements vides si la
   charge publique se mettait un jour à lire la liste déclarée. Le critère A14
   verrouille la garantie.
2. **Il ne faut pas confondre avec `groupes_masques`** (spec 020), l'autre
   moyen de faire disparaître un classement. Celui-là est le choix **d'un
   humain** : il masque une catégorie qui a des inscrits, et il doit survivre à
   un import. Le vide, lui, ne se range nulle part — il se constate. Deux
   mécanismes, deux natures ; les mélanger ferait qu'un import « démasquerait »
   une catégorie qu'un organisateur avait délibérément cachée.

Aucun interrupteur n'est donc ajouté. Ce qui est ajouté, c'est le test qui dit
que ça restera vrai.

## 5. Périmètre

**Dedans** : les quatre points de saisie de la console, le rattachement à
l'import, le rapport d'import, la carte de rattrapage, la liste déclarée.

**Dehors, explicitement** :

- **La règle du barème.** `categories.py` déduit les Under de l'édition, et
  continue : la liste officielle ferme le **vocabulaire**, elle ne décide pas
  quelles catégories une compétition fait grimper. Une édition U11-U15 garde
  trois tranches, pas neuf — D7 n'ajoute qu'un **repli sur le vide**, et ne
  touche ni au calcul, ni aux bornes, ni à l'année de référence.
- **L'application juge.** Elle reçoit la catégorie dans le catalogue et
  l'affiche ; rien à changer.
- **Le classeur Google.** On ne réécrit jamais dedans (règle 3 du CLAUDE.md).
  Il continuera de dire « U13 M » ; c'est l'import qui rattache.
- **Les catégories mixtes ou sans genre.** Aucune n'existe dans les données
  réelles, et en inventer une ouvrirait exactement le trou qu'on ferme.

## 6. Critères d'acceptation

| # | Ce qu'on vérifie | Comment |
| --- | --- | --- |
| A1 | La liste des 18 est exactement celle du §5.4, Vétérans fusionnés | test de table, les 10 alinéas écrits en toutes lettres |
| A2 | Les 8 écritures de D3 tombent sur la bonne catégorie | table de cas |
| A3 | Les 5 refus de D3 laissent la valeur inchangée | table de cas |
| A4 | Aucun accent ne sort en JSON ni ne part en base | test sur `LISTE`, `.encode("ascii")` |
| A5 | Le formulaire d'ajout propose 18 entrées, sans « Autre… » | test navigateur |
| A6 | La ligne ouverte au crayon propose les mêmes 18 | test navigateur |
| A7 | Une valeur hors liste reste choisie dans sa propre ligne | test navigateur : la ligne « U13 M » ouverte reste sur « U13 M » |
| A8 | Un import qui lit « u13m » écrit « U13 H » | test d'import |
| A9 | Un import qui lit « Poussin » garde la valeur **et** la signale | test d'import, sur le rapport |
| A10 | L'aperçu du rattrapage montre l'avant/après sans rien changer | test d'API |
| A11 | Le rattrapage appliqué change la base **et** le n° de catalogue | test d'API : les téléphones des juges doivent recharger |
| A12 | La liste déclarée n'accepte que de l'officiel | test d'API : « Poussin » envoyé, « Poussin » refusé |
| A13 | Une édition vide ouvre sur les 9 tranches, années tirées de sa date | test d'API sur une base neuve, puis date changée d'un an |
| A14 | Une catégorie déclarée sans inscrit n'est pas dans la charge publique, et y entre au premier inscrit | test d'API : `/api/public/classement` avant / après |
| A15 | Un classement masqué à la main le reste après un import | test d'API : D8 ne doit pas démasquer |

## 7. Cas limites

**Deux participants deviennent identiques.** « U13 M » rattaché sur « U13 H »
peut faire tomber deux personnes dans la même catégorie — c'est le but, et ça
ne fabrique pas de doublon : le doublon se joue sur nom + club (spec 008), pas
sur la catégorie.

**Le classement change.** Rattacher, c'est déplacer quelqu'un d'un classement
d'une personne vers un classement de vingt-sept. Le rang de tous ceux qui
suivent bouge. C'est exactement ce qu'on veut, et c'est pour ça que ça se fait
d'un clic devant un aperçu, jamais au démarrage.

**Une catégorie hors liste dans le filtre.** Le filtre « Toutes les catégories »
de la liste des participants se déduit des données et non de la liste
officielle : il doit continuer de montrer « U13 M » tant que quelqu'un le
porte, sinon la ligne à corriger devient introuvable.

**Le catalogue des juges.** La catégorie voyage dans `to_dict()`. Un
rattachement doit incrémenter le numéro de catalogue, sinon les vingt-cinq
téléphones gardent l'ancienne pendant toute la compétition.
