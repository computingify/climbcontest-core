"""Cette personne est-elle déjà dans la liste ? — spec 008.

Fonctions **pures** : ni base, ni Flask, ni réseau. C'est ce qui permet de les
éprouver par une table de cas, et une règle de rapprochement ne se teste bien
que comme ça.

## Deux mécanismes qu'il ne faut pas confondre

Ce module ne répond **pas** à « ai-je déjà relevé cet article ? ». Cette
question-là est tranchée par une contrainte SQL — `UNIQUE(competition_id,
article_id)` — parce qu'un contrôle applicatif finit toujours par se contourner
par un chemin qu'on n'avait pas prévu.

Ici on répond à « cette personne est-elle déjà dans la liste ? », et la réponse
ne peut pas venir de HelloAsso : un participant saisi au guichet n'a aucun
identifiant HelloAsso. On compare donc ce qu'on a — le nom, le prénom, le club.

**Et surtout pas le numéro de commande.** Il est unique et fiable, mais *pour
une commande*, pas pour une personne : un parent qui inscrit deux enfants
produit une commande et deux articles. S'en servir comme clé perdrait le second
enfant, silencieusement.

## Ce qui autorise à fusionner sans demander

**Le club, et lui seul.** Deux enfants du même nom dans un club d'escalade, ça
se voit ; deux enfants du même nom **dans le même club**, non. Dès que le club
diffère ou manque d'un côté, un humain tranche — c'est le cas que la contrainte
métier §3 demande explicitement de traiter.

La catégorie, elle, ne décide pas : elle **contrôle**. Un rattachement dont les
catégories diffèrent se fait quand même, et se signale. Refuser sur ce critère
bloquerait le cas le plus banal — un classeur importé avant que le barème n'ait
été appliqué.
"""

from collections import namedtuple

from .. import formatage

#: Ce qu'on sait d'une personne, d'où qu'elle vienne.
Personne = namedtuple("Personne", "identifiant nom prenom club categorie")

NOUVEAU = "nouveau"
MEME_PERSONNE = "meme_personne"
A_TRANCHER = "a_trancher"

#: Le verdict, et de quoi l'expliquer à l'écran.
Verdict = namedtuple("Verdict", "quoi identifiant motif categorie_differente")

MOTIF_CLUB_DIFFERENT = "club_different"

# ⚠️ La cle d'identite n'est PAS definie ici : elle vit dans `formatage.py`,
# avec les regles de mise en forme qui la rendent vraie.
#
# Elle y a ete deplacee le 04/09, quand Adrien a demande « uniformise le
# formatage, je ne veux pas de doublon ». La raison tient en une phrase : si la
# mise en forme et la comparaison vivent dans deux modules, elles derivent --
# l'une gagne une regle que l'autre n'a pas -- et le doublon revient par la
# porte qu'on n'a pas refermee.
#
# Les deux alias ci-dessous existent pour que ce module se lise sans aller
# chercher ailleurs, et pour que les appelants n'aient pas a changer.
cle = formatage.identite
cle_club = formatage.identite_club


def confronter(candidat: Personne, existants) -> Verdict:
    """Le verdict pour un candidat, face à ce qui est déjà en base.

    `existants` peut contenir des participants **et** des inscriptions : les
    deux origines se rencontrent au même endroit, sinon deux inscriptions en
    ligne pour la même personne créeraient deux participants.
    """
    ma_cle = cle(candidat.nom, candidat.prenom)
    if not ma_cle:
        return Verdict(A_TRANCHER, None, "sans_nom", False)

    homonymes = [p for p in existants if cle(p.nom, p.prenom) == ma_cle]
    if not homonymes:
        return Verdict(NOUVEAU, None, None, False)

    mon_club = cle_club(candidat.club)
    memes_clubs = [p for p in homonymes if mon_club and cle_club(p.club) == mon_club]

    if len(memes_clubs) == 1:
        trouve = memes_clubs[0]
        differente = bool(candidat.categorie and trouve.categorie
                          and candidat.categorie != trouve.categorie)
        return Verdict(MEME_PERSONNE, trouve.identifiant, None, differente)

    # Plusieurs homonymes du meme club, ou aucun : dans les deux cas un humain
    # tranche. Le second est le cas courant -- un club absent d'un cote -- et
    # le premier ne devrait pas exister, mais le silence serait pire.
    return Verdict(A_TRANCHER, None, MOTIF_CLUB_DIFFERENT, False)
