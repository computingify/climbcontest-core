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

from . import categories

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


def _sans_accent(texte: str) -> str:
    """« Vétéran » -> « veteran ». Sert au genre, au rattachement et a l'identite."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


#: Ce que « F » veut dire, et ce que « H » veut dire, dans les ecritures qu'on
#: rencontre vraiment. Compare sans accent et en minuscules.
#:
#: ⚠️ **Cette table etait dans `helloasso/correspondance.py`.** Elle a demenage
#: ici le 05/09 (spec 045) parce que le rattachement des categories en a besoin
#: lui aussi -- et que la lecon du bas de ce fichier vaut ici mot pour mot : si
#: deux modules portent la meme table, elles derivent, l'une gagne une ecriture
#: que l'autre n'a pas, et le doublon revient par la porte qu'on n'a pas
#: refermee. `correspondance` l'importe.
GENRES_CONNUS = {
    "f": "F", "fille": "F", "filles": "F", "feminin": "F", "feminine": "F",
    "femme": "F", "girl": "F", "female": "F", "mademoiselle": "F", "mme": "F",
    "h": "H", "m": "H", "garcon": "H", "garcons": "H", "masculin": "H",
    "homme": "H", "boy": "H", "male": "H", "monsieur": "H", "mr": "H",
}

#: Un Under, seul (« U13 », « 13 ») ou colle a son genre (« U13F », « 13m »).
#: Le `u` est FACULTATIF : « il peut aussi arriver qu'il manque le U »
#: (Adrien, 05/09).
#:
#: ⚠️ `\d{1,2}` et non `\d+`. Quatre chiffres, c'est une ANNEE : « 2016 » ne
#: doit jamais devenir une categorie. Sans cette borne, une colonne decalee
#: d'une case dans le classeur rangerait toute une liste en « U2016 ».
_UNDER_SEUL = re.compile(r"^u?(\d{1,2})$")
_UNDER_COLLE = re.compile(r"^u?(\d{1,2})([fhm])$")

#: Les categories d'adultes, qui ne portent pas de Under. « Veteran 1 » et
#: « Veteran 2 » tombent sur le meme « Veteran » (spec 045, D1).
_SENIOR = re.compile(r"^seniors?$")
_VETERAN = re.compile(r"^(?:veterans?\s*[12]?|v[12])$")

#: Les separateurs qu'on ramene a l'espace avant de decouper : « U13-F »,
#: « U13/F », « U13.F » sont trois ecritures de « U13 F ».
_LIANTS = re.compile(r"[-_/.,;:’']+")


def genre_connu(reponse) -> str | None:
    """« Fille » → « F ». None si ce n'est pas une écriture reconnue.

    ⚠️ Ne devine JAMAIS par défaut. Une réponse inconnue rend None, et
    l'inscription part en attente — faire entrer une grimpeuse dans un
    classement masculin parce qu'on a choisi une valeur par défaut serait le
    genre d'erreur que personne ne remarque avant le podium.
    """
    if reponse is None:
        return None
    return GENRES_CONNUS.get(_sans_accent(str(reponse)).strip().lower())


def rattacher(texte: str | None) -> str | None:
    """Une écriture quelconque → la catégorie officielle. Spec 045.

    « u13f », « 13 F », « U 13 h », « U13 M », « sénior femme », « V2 H » →
    « U13 F », « U13 F », « U13 H », « U13 H », « Senior F », « Veteran H ».

    Rend **None** quand on ne peut pas trancher, et l'appelant garde alors ce
    qui était écrit (décision D4). Trois cas, tous rencontrés pour de vrai :

    - **Pas de genre** (« U13 ») : « U13 » à côté de « U13 F » couperait le
      classement en deux.
    - **Pas un Under officiel** (« U12 F ») : on ne l'invente pas.
    - **Deux âges ou deux genres** (« U13 F et U13 H ») : c'est une entête de
      tableau, pas une catégorie. Deviner ici rangerait des gens au hasard.

    Les jetons inconnus sont **tolérés** — « catégorie U13 F » marche — mais ils
    ne peuvent jamais fabriquer une réponse à eux seuls.
    """
    if texte is None:
        return None
    propre = _LIANTS.sub(" ", _sans_accent(str(texte)).lower())
    jetons = propre.split()

    ages: set[str] = set()
    genres: set[str] = set()
    i = 0
    while i < len(jetons):
        jeton = jetons[i]
        i += 1

        colle = _UNDER_COLLE.match(jeton)
        if colle:
            ages.add(f"U{int(colle.group(1))}")
            genres.add(GENRES_CONNUS[colle.group(2)])
            continue

        seul = _UNDER_SEUL.match(jeton)
        if seul:
            ages.add(f"U{int(seul.group(1))}")
            continue

        if _SENIOR.match(jeton):
            ages.add("Senior")
            continue

        if _VETERAN.match(jeton):
            ages.add("Veteran")
            # « Veteran 1 » s'ecrit aussi en DEUX jetons. Sans cette ligne, le
            # « 1 » qui suit serait lu comme un Under et fabriquerait un
            # conflit d'age avec le veteran qu'on vient de reconnaitre.
            if i < len(jetons) and jetons[i] in ("1", "2"):
                i += 1
            continue

        connu = GENRES_CONNUS.get(jeton)
        if connu:
            genres.add(connu)

    if len(ages) != 1 or len(genres) != 1:
        return None
    age = ages.pop()
    if age not in categories.OFFICIELLES:
        return None
    return f"{age} {genres.pop()}"


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
    """La catégorie officielle quand on la reconnaît, la forme nettoyée sinon.

    « u13 f », « U13F », « 13 F », « U13 M » -> « U13 F », « U13 F »,
    « U13 F », « U13 H ». Spec 045.

    ⚠️ **C'est ICI que le vocabulaire se ferme, et nulle part ailleurs.** Cette
    fonction est le passage oblige de toute ecriture de categorie depuis la
    spec 008 -- formulaire d'ajout, crayon, salle d'attente HelloAsso, import
    du classeur. Ajouter le rattachement a cote, dans une fonction qu'il
    faudrait penser a appeler, laisserait exactement le chemin par lequel le
    defaut est revenu trois fois.

    Consequence directe : le classeur Google peut continuer d'ecrire
    « U13 M » -- on n'ecrit jamais dedans (regle 3 du CLAUDE.md) -- le prochain
    import lira « U13 M » et posera « U13 H ». Le rattrapage de la console ne
    sera pas defait au premier import.

    Ce qui n'est pas reconnu ressort par **l'ancienne regle, intacte** : tout
    en majuscules, l'espace garanti avant le genre. « Poussin » reste
    « POUSSIN », et le rapport d'import le signale (D4).
    """
    reduit = _vide(texte)
    if reduit is None:
        return None
    return rattacher(reduit) or _GENRE_COLLE.sub(r" \1", reduit.upper())


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
