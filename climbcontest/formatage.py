"""Mise en forme de ce qui est SAISI a la main. Rien d'autre.

Spec 013. Trois fonctions pures : ni base, ni Flask, ni configuration. C'est ce
qui permet de les eprouver par une table de cas, sans monter d'application --
et une regle de casse ne se teste bien que comme ca.

⚠️ **Ce module ne touche jamais a ce qui est IMPORTE du classeur.**
`sheets/importer.py` construit ses `Participant` directement et reste inchange :
le classeur fait autorite sur ses propres lignes. Les reformater masquerait ses
erreurs au lieu de les signaler, et ferait diverger la base de la source qu'elle
recopie.

Le probleme reel, mesure en production le 30/08 : la base porte 26 « U13 H » et
**un** « U13 M ». Ce grimpeur est seul dans sa categorie, donc premier d'un
classement d'une personne, et absent du vrai « U13 H ». Un champ libre produit
ce genre d'ecart ; une liste deroulante plus ces regles l'empechent.
"""
import re

# Espace, trait d'union, apostrophe droite et apostrophe typographique.
#
# Sans le trait d'union, « jean-luc » donnerait « Jean-luc ». Sans l'apostrophe,
# « roc n'potes » donnerait « Roc N'potes » -- or le club s'appelle « Roc
# N'Potes » dans le classeur, et les deux formes cohabiteraient alors dans la
# liste deroulante. C'est exactement ce qu'on cherche a empecher.
SEPARATEURS = " -'’"
_DECOUPE = re.compile(f"([{re.escape(SEPARATEURS)}])")

# Un sigle est COURT. C'est la seule information disponible pour distinguer
# « CAF » d'un nom de famille tape en capitales, et elle suffit :
# « ASPTT » (5) passe, « MARTIN » (6) non.
SIGLE_MAXI = 5

# Une categorie finissant par le genre colle au chiffre : « U13F » -> « U13 F ».
# Ancree sur un CHIFFRE a gauche, pour ne jamais couper un mot qui finirait par
# F ou H sans etre un genre.
_GENRE_COLLE = re.compile(r"(?<=\d)([HF])$")


def _vide(texte: str | None) -> str | None:
    """Normalise les blancs. Rend None pour ce qui ne contient rien.

    None et non « » : un champ facultatif non renseigne doit etre NULL en base,
    pas une chaine vide qui s'afficherait comme un club nomme « ».
    """
    if texte is None:
        return None
    reduit = " ".join(str(texte).split())
    return reduit or None


def mots(texte: str | None, sigles: bool = False) -> str | None:
    """Une majuscule au debut de chaque mot.

    `sigles=True` laisse intact un mot deja tout en majuscules et long de 2 a
    SIGLE_MAXI caracteres. A reserver aux noms d'organisations : une personne
    n'est jamais un sigle, et taper son nom en capitales est un reflexe courant
    sur un formulaire.
    """
    reduit = _vide(texte)
    if reduit is None:
        return None

    morceaux = _DECOUPE.split(reduit)
    for i, morceau in enumerate(morceaux):
        if morceau in SEPARATEURS or not morceau:
            continue                                    # separateur : conserve tel quel
        if sigles and morceau.isupper() and 2 <= len(morceau) <= SIGLE_MAXI:
            continue                                    # « CAF », « ASPTT »
        morceaux[i] = morceau.capitalize()
    return "".join(morceaux)


def nom(texte: str | None) -> str | None:
    """Nom ou prenom : casse stricte, aucune exception. « MARTIN » -> « Martin »."""
    return mots(texte, sigles=False)


def club(texte: str | None) -> str | None:
    """Club : meme regle, mais les sigles survivent. « CAF annonay » -> « CAF Annonay »."""
    return mots(texte, sigles=True)


def categorie(texte: str | None) -> str | None:
    """Tout en majuscules, et l'espace avant le genre est garanti.

    « u13 f » -> « U13 F », et « U13F » -> « U13 F ». Sans cette seconde regle,
    les deux saisies donneraient deux categories distinctes dans la liste, donc
    deux classements separes -- le meme defaut que le « U13 M » existant, sous
    une autre forme.
    """
    reduit = _vide(texte)
    if reduit is None:
        return None
    return _GENRE_COLLE.sub(r" \1", reduit.upper())
