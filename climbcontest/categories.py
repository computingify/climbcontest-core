"""La règle des catégories d'âge, telle que la FFME la publie — spec 008.

Trois fonctions **pures** : ni base, ni Flask, ni réseau. C'est ce qui permet de
les éprouver par une table de cas, et surtout de vérifier le calcul contre le
tableau publié par la fédération — le seul test qui prouve quelque chose ici.

## La règle

« U » veut dire *under*. **U13 = moins de 13 ans**, et c'est le **plus petit
Under qui l'emporte**. Deux précisions font tout le reste :

1. C'est l'**année de naissance** qui compte, jamais la date. Personne ne change
   de catégorie le jour de son anniversaire.
2. L'année de référence est celle où **finit** la saison. La saison FFME va du
   1ᵉʳ septembre au 31 août : une compétition de novembre 2026 est dans la
   saison 2026-2027, donc sa référence est **2027**. C'est exactement ce qui
   fait qu'on démarre l'année dans une catégorie et qu'on y reste.

        age       = reference - annee_de_naissance
        categorie = le plus petit U(n) tel que age < n

Vérifié contre le tableau publié pour la saison 2025-2026 (référence 2026) :
U11 → 2016-2017, U13 → 2014-2015, U15 → 2012-2013, U17 → 2010-2011,
U19 → 2008-2009, U21 → 2006-2007. C'est `tests/test_categories.py` qui le
rejoue, ligne pour ligne.

⚠️ **La première version de la spec 008 était fausse d'un an** : elle prenait
l'année où la saison *commence*. Pour une compétition de novembre 2026, U13 est
2015-2016, et non 2014-2015.

## Pourquoi ce module n'est pas sous `helloasso/`

La règle sert au relevé HelloAsso, **mais aussi** au formulaire d'ajout manuel,
à l'édition en ligne et au bouton « Appliquer à tous ». La ranger sous
`helloasso/` ferait dépendre la saisie au guichet d'une intégration qui peut
très bien ne pas être branchée.

## Ce qui se déduit, et ce qui se cite — révision du 05/09 (spec 045)

Ce module a longtemps dit « rien n'est codé en dur », au motif que les
catégories changent d'une année sur l'autre. **C'était vrai d'une chose et faux
d'une autre**, et la spec 045 sépare les deux :

| | D'où ça vient | Pourquoi |
| --- | --- | --- |
| Les **Under d'une édition** | déduits (`unders_de`) | une compétition ne fait pas grimper toutes les catégories ; celles d'Annonay vont de U11 à U17 |
| Le **vocabulaire** | cité (`OFFICIELLES`) | la fédération le publie, il ne s'invente pas — et un champ libre a produit un « U13 M » qui a laissé un grimpeur seul dans son classement |

Autrement dit : la liste ci-dessous dit quels **noms existent**, jamais lesquels
une édition utilise. Le calcul, lui, n'a pas bougé d'une ligne.

Conséquence directe de « le plus petit Under l'emporte » : **les tranches ne
font pas forcément deux ans**. Si une édition ne déclare que U11 et U15, un
grimpeur de 12 ans est U15 — il n'y a pas de U13 pour le prendre. Et la plus
petite catégorie est ouverte vers le bas : elle prend tous les plus jeunes,
parce que c'est là qu'ils grimperont.
"""

import re
from collections import namedtuple
from datetime import date

#: Le mois où bascule la saison FFME. Septembre.
PREMIER_MOIS_DE_SAISON = 9

#: Les categories publiees par la federation, dans l'ordre du texte.
#:
#: Regles d'acces et de participation 2025-2026 (V3), §5.4 :
#:
#:     a) U9 : 7 et 8 ans          f) U19 : 17 et 18 ans
#:     b) U11 : 9 et 10 ans        g) U21 : 19 et 20 ans
#:     c) U13 : 11 et 12 ans       h) Senior : 21 a 39 ans
#:     d) U15 : 13 et 14 ans       i) Veteran 1 : 40 a 49 ans
#:     e) U17 : 15 et 16 ans       j) Veteran 2 : 50 ans et plus
#:
#: ⚠️ **Veteran 1 et Veteran 2 sont fusionnes en « Veteran »** -- decision
#: d'Adrien du 05/09, que le meme paragraphe autorise : « les veterans 1 et 2
#: concourent dans la meme categorie veteran et des podiums differencies
#: peuvent etre organises a l'issue de la competition ».
#:
#: ⚠️ **Sans accent, et ce n'est pas un oubli.** La convention du depot
#: interdit les accents dans les litteraux Python, donc dans ce qui part en
#: base et en JSON. La console affiche « Senior » accentue : sa table
#: d'accentuation est dans le gabarit, cote affichage.
OFFICIELLES = ("U9", "U11", "U13", "U15", "U17", "U19", "U21",
               "Senior", "Veteran")

#: Le genre, dans l'ecriture des donnees reelles. Les 98 lignes de novembre
#: 2025 (`fixtures/contest-nov2025.json`) portent « H », jamais « M » : c'est
#: la forme majoritaire qui gagne, et « M » devient une ecriture qu'on
#: rattache (`formatage.rattacher`).
GENRES = ("F", "H")

#: Les 18 libelles complets. C'est ce que propose la console, et rien d'autre.
LISTE = tuple(f"{nom} {genre}" for nom in OFFICIELLES for genre in GENRES)

#: Un nom de catégorie qui porte un Under : « U13 », « U13 F », « u9 ».
#: Ancré au début, insensible à la casse, et le genre qui suit est ignoré.
_UNDER = re.compile(r"^\s*U\s*(\d{1,2})\b", re.IGNORECASE)

#: Une tranche du barème.
#:
#: `age_min` et `annee_max` valent None pour la plus petite catégorie : elle est
#: ouverte vers les plus jeunes, donc vers les années les plus récentes.
Tranche = namedtuple("Tranche", "circuit age_min age_max annee_min annee_max")


def annee_de_reference(jour: date) -> int:
    """L'année civile qui sert de référence : celle où **finit** la saison.

    Une compétition du 15/11/2026 et une du 15/03/2027 sont dans la même saison
    2026-2027 : les deux rendent 2027, et donc le même barème. C'est ce qui fait
    qu'un grimpeur ne change pas de catégorie au milieu de sa saison.
    """
    return jour.year + 1 if jour.month >= PREMIER_MOIS_DE_SAISON else jour.year


def under(nom_de_categorie: str | None) -> int | None:
    """« U13 F » → 13. Rend None pour « Senior », « Adulte », « Vétéran ».

    Une catégorie qui ne porte pas de Under n'est pas une erreur : elle existe,
    elle est simplement hors barème, et personne n'y sera rangé automatiquement.
    """
    if not nom_de_categorie:
        return None
    trouve = _UNDER.match(str(nom_de_categorie))
    return int(trouve.group(1)) if trouve else None


def unders_de(categories) -> list[int]:
    """Les Under distincts portés par une liste de catégories, croissants."""
    return sorted({n for n in (under(c) for c in categories or []) if n})


def circuit(annee_naissance, reference: int, unders) -> str | None:
    """Le circuit d'un grimpeur : le plus petit Under qui le contient.

    Rend None quand aucun ne le contient — un adulte, ou une année aberrante.
    L'appelant met alors l'inscription en attente ; il ne devine pas.

    ⚠️ **L'âge négatif est refusé**, et ce n'est pas une précaution théorique :
    une faute de frappe sur l'année (2916 pour 2016) donne un âge de -889, qui
    est bel et bien « inférieur à 11 ». Sans cette garde, la faute la plus
    banale rangerait quelqu'un dans la plus petite catégorie au lieu de se
    signaler.
    """
    try:
        annee = int(str(annee_naissance).strip())
    except (TypeError, ValueError):
        return None

    age = reference - annee
    if age < 0:
        return None

    candidats = [n for n in unders if age < n]
    return f"U{min(candidats)}" if candidats else None


def bareme(reference: int, unders) -> list[Tranche]:
    """Le barème complet : une tranche par Under, de la plus jeune à la plus âgée.

    Les bornes se **déduisent de l'ensemble**, pas d'une largeur de deux ans
    supposée. Chaque Under prend les âges laissés par celui d'en dessous :

        unders = {11, 13, 15}        →  U11 : jusqu'à 10 ans
                                        U13 : 11 et 12 ans
                                        U15 : 13 et 14 ans

        unders = {11, 15}            →  U11 : jusqu'à 10 ans
                                        U15 : 11, 12, 13 et 14 ans

    Le second cas n'est pas une bizarrerie de test : c'est ce que « le plus
    petit Under l'emporte » impose quand une édition saute une catégorie.
    """
    tranches = []
    precedent = None                       # le Under d'en dessous, s'il existe
    for n in sorted(set(unders)):
        age_min = precedent                # None pour la plus petite
        age_max = n - 1
        tranches.append(Tranche(
            circuit=f"U{n}",
            age_min=age_min,
            age_max=age_max,
            annee_min=reference - age_max,
            annee_max=None if age_min is None else reference - age_min,
        ))
        precedent = n
    return tranches


def annees_attendues(nom_de_categorie: str | None, reference: int,
                     unders) -> tuple[int | None, int | None] | None:
    """Les années de naissance attendues pour une catégorie donnée.

    Le sens inverse de `circuit()`, et il sert à une seule chose : quand on
    choisit « U13 F » dans le formulaire d'ajout, dire quelles années on attend
    (décision D8). Rend None pour une catégorie hors barème.

    Le couple rendu est `(annee_min, annee_max)`, et `annee_max` vaut None pour
    la plus petite catégorie — elle est ouverte vers les plus jeunes.
    """
    n = under(nom_de_categorie)
    if n is None or n not in set(unders):
        return None
    for tranche in bareme(reference, unders):
        if tranche.circuit == f"U{n}":
            return (tranche.annee_min, tranche.annee_max)
    return None
