"""Mise en forme de ce qui est SAISI a la main. Rien d'autre.

Spec 013. Trois fonctions pures : ni base, ni Flask, ni configuration. C'est ce
qui permet de les eprouver par une table de cas, sans monter d'application --
et une regle de casse ne se teste bien que comme ca.

⚠️ **Changement du 04/09/2026 : ce module s'applique DESORMAIS a toutes les
sources, classeur compris.**

La spec 013 l'avait volontairement tenu a l'ecart de `sheets/importer.py`, au
motif que « le classeur fait autorite sur ses propres lignes » et que les
reformater masquerait ses erreurs. Adrien a tranche autrement : « uniformise le
formatage, je ne veux pas de doublon ».

Il a raison, et le raisonnement d'origine se retourne : une erreur de CASSE dans
le classeur n'est pas une erreur qu'on veut voir, c'est une erreur qui FABRIQUE
un doublon. « ANNONAY ESCALADE » importe du classeur et « Annonay Escalade »
tape au guichet donnent deux clubs dans la liste deroulante, deux entrees a
choisir, et un rapprochement qui echoue -- donc deux fois la meme personne.

Ce qui reste vrai de la reserve d'origine : le formatage ne corrige que la
FORME. Un nom mal orthographie, une categorie inexistante, un dossard en double
restent signales par le rapport d'import. On uniformise la casse, on ne repare
pas les donnees.

Le probleme reel, mesure en production le 30/08 : la base porte 26 « U13 H » et
**un** « U13 M ». Ce grimpeur est seul dans sa categorie, donc premier d'un
classement d'une personne, et absent du vrai « U13 H ». Un champ libre produit
ce genre d'ecart ; une liste deroulante plus ces regles l'empechent.
"""
import re
import unicodedata

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


# --- L'identite : ce qui decide que deux lignes sont la meme personne -------
#
# ⚠️ Cette cle vit ICI, avec les regles de mise en forme, et pas dans le module
# qui rapproche les inscriptions HelloAsso -- ou elle etait d'abord. La raison
# est celle qu'Adrien a donnee le 04/09 : « je ne veux pas de doublon ».
#
# Un doublon nait toujours du meme ecart : deux ecritures d'un meme nom qui ne
# tombent pas sur la meme cle. Si la mise en forme et la comparaison sont dans
# deux modules, elles derivent -- l'une gagne une regle que l'autre n'a pas, et
# le doublon reapparait par la porte qu'on n'a pas refermee. Les deux sont donc
# le meme fichier, et se lisent ensemble.

def _sans_accent(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def identite(nom_de_famille: str | None, prenom: str | None = None) -> str:
    """La cle de comparaison d'une personne. « DUPONT Jean-Luc » = « dupont jean luc ».

    Minuscules, accents retires, separateurs ramenes a l'espace, blancs reduits.
    Les memes separateurs que la mise en forme -- c'est tout l'interet de les
    tenir cote a cote.

    Rend une chaine VIDE pour une personne sans nom. L'appelant doit traiter ce
    cas : deux personnes sans nom ne sont pas la meme personne.
    """
    brut = f"{nom_de_famille or ''} {prenom or ''}"
    sans = _sans_accent(brut).lower()
    for separateur in SEPARATEURS:
        sans = sans.replace(separateur, " ")
    return " ".join(sans.split())


def identite_club(nom_du_club: str | None) -> str:
    """La meme normalisation, pour comparer deux clubs.

    « Roc N'Potes », « roc n'potes » et « ROC N POTES » sont le meme club : le
    classeur ecrit l'un, un parent tape l'autre, et une liste deroulante qui les
    montrerait tous les trois serait deja un doublon.
    """
    return identite(nom_du_club)
