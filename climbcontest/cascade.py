"""La cascade de couleurs : lecture, écriture et contrôle de la règle.

Spec 025. Réussir **tous** les blocs d'une couleur peut en valider d'autres,
plus faciles. La règle s'écrit en **phrases** — « quand au moins 2 parmi ⟨Vert⟩
⟨Bleu⟩ ⟨Mauve⟩ ⟨Rouge⟩ ⟨Noir⟩ sont validées → valider ⟨Jaune⟩ » — et une seule
règle vaut pour l'édition, activable ou non catégorie par catégorie.

Ce module ne calcule pas le classement : il traduit le JSON rangé dans
`Competition.options` en `classement.Cascade`, et il **contrôle** ce qu'on
écrit. Le calcul est dans `classement._valider_par_couleur`.

**Deux phrases ne peuvent pas se contredire.** Le résultat est l'union de celles
dont la condition tient : une phrase ne fait qu'ajouter des validations, jamais
en retirer (vérifié par énumération exhaustive des 64 combinaisons de couleurs
pleines). Ce qu'elles peuvent, c'est **mentir à qui les écrit** — on pose une
condition qu'on croit plus stricte, et une autre phrase, plus facile à
satisfaire, a déjà tout donné. C'est ce que `controler()` cherche.
"""

from __future__ import annotations

import itertools
import logging

from .classement import COULEURS, Cascade, Phrase
from .contest import ErreurMetier

logger = logging.getLogger(__name__)

# La règle du classeur, mesurée le 02/09/2026 en activant `Listes!D29:D38` dans
# une copie jetable : un bloc de couleur X est validé dès que DEUX couleurs
# strictement plus dures que X sont entièrement réussies.
SEUIL_CLASSEUR = 2

# Six couleurs ne demandent pas trente phrases : au-dela, on ne regle plus un
# classement, on l'empoisonne. Sans plafond, 20 000 regles s'ecrivent en base et
# font passer un recalcul de 22 ms a 2,2 s -- a chaque rafraichissement, et un
# redemarrage n'y change rien puisque le document est range.
REGLES_MAX = 30
CATEGORIES_MAX = 200

# Les 64 jeux de couleurs pleines possibles. C'est peu, et ca permet de
# raisonner par EXHAUSTIVITE plutot que par regle de trois.
_COMBINAISONS = tuple(
    frozenset(c)
    for n in range(len(COULEURS) + 1)
    for c in itertools.combinations(COULEURS, n)
)


def _sortie(phrases: tuple[Phrase, ...], pleines: frozenset[str]) -> frozenset[str]:
    """Ce qu'un jeu de phrases valide, pour un jeu de couleurs pleines donne."""
    validees: set[str] = set()
    for p in phrases:
        if p.tient(pleines):
            validees |= p.cibles
    return frozenset(validees)


def _sans_effet(phrases: tuple[Phrase, ...]) -> list[int]:
    """Les indices des phrases qu'on peut retirer sans rien changer.

    ⚠️ **Exact, et pas seulement deux a deux.** Une phrase peut etre tuee par la
    REUNION de plusieurs autres sans qu'aucune ne l'implique a elle seule :

        1. au moins 1 parmi [Rouge]                 -> [Jaune]
        2. au moins 2 parmi [Vert,Mauve,Rouge,Noir] -> [Jaune]
        3. au moins 1 parmi [Vert,Bleu,Noir]        -> [Jaune]

    La 2 ne peut pas se declencher sans que la 1 ou la 3 ait deja donne Jaune,
    et aucun test par paires ne le voit.

    On retire les mortes AU FUR ET A MESURE : sinon deux phrases identiques
    s'excuseraient mutuellement et on n'en signalerait aucune.
    """
    reference = [_sortie(phrases, c) for c in _COMBINAISONS]
    gardees = list(range(len(phrases)))
    mortes: list[int] = []
    for i in range(len(phrases)):
        essai = tuple(phrases[j] for j in gardees if j != i)
        if all(_sortie(essai, c) == r for c, r in zip(_COMBINAISONS, reference)):
            mortes.append(i)
            gardees.remove(i)
    return mortes


def _plus_dures(couleur: str) -> list[str]:
    return COULEURS[COULEURS.index(couleur) + 1:]


def regle_du_classeur(seuil: int = SEUIL_CLASSEUR) -> tuple[Phrase, ...]:
    """La règle du classeur, écrite en phrases.

    Une couleur qui n'a pas assez de couleurs plus dures au-dessus d'elle n'est
    **jamais** validable — avec le seuil à 2, c'est le cas du Rouge, qui n'a que
    le Noir au-dessus. Le classeur fait exactement pareil ; on ne lui invente pas
    une phrase qu'il n'a pas.
    """
    if seuil < 1:
        # Sans cette garde, « au moins 0 parmi [] » se declenche sur RIEN et
        # valide les six couleurs pour tout le monde. Le defaut n'est pas
        # atteignable aujourd'hui ; c'est un piege pour le prochain appelant.
        raise ValueError("le seuil de la regle du classeur vaut au moins 1")
    return tuple(
        Phrase(parmi=frozenset(_plus_dures(c)), seuil=seuil, cibles=frozenset({c}))
        for c in COULEURS
        if len(_plus_dures(c)) >= seuil
    )


def implique(b: Phrase, a: Phrase) -> bool:
    """La condition de `b` entraîne-t-elle celle de `a` ?

    Exact sur **tout** le domaine, y compris les seuils absurdes qu'un document
    rangé à la main peut porter :

    - une phrase **insatisfiable** (`seuil > len(parmi)`) implique tout, puisque
      sa condition n'est jamais vraie ;
    - une phrase **toujours vraie** (`seuil <= 0`) n'est impliquée que par une
      autre phrase toujours vraie — d'où le `max(0, ...)` : le nombre de couleurs
      pleines que `b` garantit à `a` ne peut pas descendre sous zéro.

    Sinon : satisfaire `b` demande `seuil(b)` couleurs prises dans `parmi(b)` ;
    au pire, `seuil(b) - |parmi(b) hors parmi(a)|` d'entre elles tombent quand
    même dans `parmi(a)`.
    """
    if b.seuil > len(b.parmi):
        return True
    return max(0, b.seuil - len(b.parmi - a.parmi)) >= max(0, a.seuil)


def analyser(phrases: tuple[Phrase, ...]) -> dict:
    """Les constats bruts, sans phrase de message.

    Séparé de `controler` pour une raison précise : la console refait ce même
    contrôle en JavaScript, pour répondre sans aller-retour. Deux copies d'une
    règle finissent toujours par diverger — c'est **cette** fonction que le
    test de parité compare à sa jumelle du gabarit, sur des jeux tirés au
    hasard. Comparer des messages traduits n'aurait rien prouvé.

    Rend `{"bloquants": [(code, rang, detail)], "mortes": [(rang, temoin)],
    "communes": [(rang_a, rang_b, [couleurs])]}`, les rangs comptés à partir
    de zéro.
    """
    bloquants: list[tuple] = []

    if len(phrases) > REGLES_MAX:
        return {"bloquants": [("trop", -1, len(phrases))],
                "mortes": [], "communes": []}

    for i, phrase in enumerate(phrases):
        if not phrase.parmi:
            bloquants.append(("sans_declencheur", i, None))
        if not phrase.cibles:
            bloquants.append(("sans_cible", i, None))
        if not phrase.parmi or not phrase.cibles:
            continue
        if not 1 <= phrase.seuil <= len(phrase.parmi):
            bloquants.append(("seuil", i, (phrase.seuil, len(phrase.parmi))))
            continue
        # La cascade descend. Une phrase peut ecrire l'inverse -- une grille,
        # non : ses cases y seraient mortes. C'est le seul defaut que la forme
        # « phrase » introduit, donc le seul qui doit bloquer.
        plus_facile = min(phrase.parmi, key=COULEURS.index)
        for cible in sorted(phrase.cibles, key=COULEURS.index):
            if COULEURS.index(cible) >= COULEURS.index(plus_facile):
                bloquants.append(("remonte", i, (cible, plus_facile)))

    if bloquants:
        # Tant qu'une phrase ne veut rien dire, chercher les regles mortes ne
        # rendrait qu'un bruit qu'on ne peut pas corriger.
        return {"bloquants": bloquants, "mortes": [], "communes": []}

    morts = _sans_effet(phrases)
    ensemble = set(morts)
    mortes: list[tuple] = []
    for i in morts:
        # Le temoin sert au MESSAGE, pas a la detection : on nomme la phrase qui
        # rend celle-ci inutile quand il y en a une seule. Quand c'est la
        # reunion de plusieurs, on le dit sans en designer une au hasard.
        temoin = next(
            (j for j in range(len(phrases))
             if j != i and j not in ensemble
             and implique(phrases[i], phrases[j])
             and phrases[i].cibles <= phrases[j].cibles),
            None)
        mortes.append((i, temoin))

    communes: list[tuple] = []
    for i in range(len(phrases)):
        for j in range(i + 1, len(phrases)):
            if i in ensemble or j in ensemble:
                continue
            partagees = phrases[i].cibles & phrases[j].cibles
            if partagees:
                communes.append(
                    (i, j, sorted(partagees, key=COULEURS.index)))

    return {"bloquants": bloquants, "mortes": mortes, "communes": communes}


def controler(phrases: tuple[Phrase, ...]) -> tuple[list[str], list[str]]:
    """Rend `(bloquants, avertissements)`, en clair.

    Ce qui **bloque** est ce qui ne veut rien dire — une phrase incomplète, un
    seuil hors bornes, une cascade qui remonte. Ce qui **avertit** est ce qui
    veut dire autre chose que ce qu'on croit : la phrase morte, et deux phrases
    sur la même couleur.

    On avertit sans bloquer parce qu'une phrase morte peut être volontaire — on
    la garde le temps d'en écrire une autre — alors qu'une cascade qui remonte
    n'a aucune lecture possible.
    """
    constats = analyser(phrases)
    bloquants: list[str] = []
    avertissements: list[str] = []

    for code, rang, detail in constats["bloquants"]:
        if code == "trop":
            bloquants.append(
                f"{detail} regles, {REGLES_MAX} au maximum. Six couleurs "
                f"n'en demandent pas autant.")
        elif code == "sans_declencheur":
            bloquants.append(
                f"Regle {rang + 1} incomplete : il lui manque une couleur "
                f"declencheur.")
        elif code == "sans_cible":
            bloquants.append(
                f"Regle {rang + 1} incomplete : il lui manque une couleur a "
                f"valider.")
        elif code == "seuil":
            bloquants.append(
                f"Regle {rang + 1} : il en faut {detail[0]}, mais "
                f"{detail[1]} couleur(s) sont cochees.")
        elif code == "remonte":
            bloquants.append(
                f"Regle {rang + 1} : « {detail[0]} » n'est pas plus facile que "
                f"« {detail[1]} ». La cascade descend, elle ne remonte pas.")

    for rang, temoin in constats["mortes"]:
        if temoin is None:
            avertissements.append(
                f"Regle {rang + 1} sans effet : les autres regles validaient "
                f"deja tout ce qu'elle valide.")
        else:
            avertissements.append(
                f"Regle {rang + 1} sans effet : elle ne peut pas se declencher "
                f"sans que la regle {temoin + 1}, plus facile a satisfaire, ait "
                f"deja valide tout ce qu'elle valide.")

    for a, b, partagees in constats["communes"]:
        avertissements.append(
            f"Regles {a + 1} et {b + 1} valident toutes deux "
            f"« {', '.join(partagees)} ». Elles s'additionnent, elles ne se "
            f"remplacent pas : il suffit que l'une tienne.")

    return bloquants, avertissements


def _couleurs(valeurs, ou: str) -> frozenset[str]:
    """Valide une liste de couleurs de difficulté venue du dehors."""
    if not isinstance(valeurs, list):
        raise ErreurMetier(f"{ou} : une liste de couleurs est attendue.")
    propres = []
    for v in valeurs:
        nom = str(v).strip().capitalize()
        if nom not in COULEURS:
            # Tronquee et mise sur une seule ligne : cette valeur vient du
            # dehors, et elle repart dans un message ET dans le journal.
            vue = " ".join(str(v).split())[:30]
            raise ErreurMetier(
                f"Couleur inconnue « {vue} ». Les couleurs de difficulte sont "
                + ", ".join(COULEURS) + ".")
        propres.append(nom)
    return frozenset(propres)


def _entier(valeur, ou: str) -> int:
    """Un entier venu du dehors, ou une `ErreurMetier`.

    ⚠️ Trois pieges, tous constates : `int(True)` vaut 1, donc un booleen
    passerait pour un seuil ; `int(float("inf"))` leve `OverflowError`, que
    personne ne rattrapait — et `json.loads` accepte `Infinity` ; `int(2.9)`
    vaut 2, une troncature muette qui change la regle sans le dire.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise ErreurMetier(f"{ou} doit etre un nombre entier.")
    try:
        entier = int(valeur)
    except (ValueError, OverflowError):
        raise ErreurMetier(f"{ou} doit etre un nombre entier.") from None
    if entier != valeur:
        raise ErreurMetier(f"{ou} doit etre un nombre entier.")
    return entier


def depuis_json(donnees) -> tuple[Phrase, ...]:
    """Les phrases d'un corps de requête ou d'un document rangé."""
    if not isinstance(donnees, list):
        raise ErreurMetier("Une liste de regles est attendue.")
    if len(donnees) > REGLES_MAX:
        raise ErreurMetier(
            f"{len(donnees)} regles, {REGLES_MAX} au maximum. Six couleurs "
            f"n'en demandent pas autant.")
    phrases = []
    for i, brut in enumerate(donnees, start=1):
        if not isinstance(brut, dict):
            raise ErreurMetier(f"Regle {i} : un objet est attendu.")
        seuil = _entier(brut.get("seuil", 1), f"Regle {i} : « il en faut »")
        phrases.append(Phrase(
            parmi=_couleurs(brut.get("parmi", []), f"Regle {i}"),
            seuil=seuil,
            cibles=_couleurs(brut.get("cibles", []), f"Regle {i}"),
        ))
    return tuple(phrases)


def _categories(valeurs) -> frozenset[str]:
    if not isinstance(valeurs, list):
        return frozenset()
    propres = {str(c).strip() for c in valeurs if isinstance(c, str) and c.strip()}
    return frozenset(sorted(propres)[:CATEGORIES_MAX])


def depuis_options(options: dict) -> Cascade:
    """La cascade d'une édition, repli compris.

    ⚠️ **Ce qui est rangé est contrôlé comme ce qui est saisi.** Un document
    écrit à la main, importé, ou venu d'une version future passerait sinon
    derrière tous les garde-fous : un `seuil` à zéro rend `len(parmi & pleines)
    >= 0` toujours vrai, donc valide les six couleurs **pour tout le monde**, et
    une cascade qui remonte serait acceptée à la lecture alors qu'elle est
    refusée à l'écriture. Un document que `valider()` refuserait est ici ignoré.

    ⚠️ `validation_couleur` — l'option de la spec 004, un simple entier — reste
    lue quand `cascade` est absente. Sa conversion est **exacte** : l'ancienne
    règle validait tout ce qui est plus facile que la N-ième couleur pleine la
    plus dure, ce qui revient à dire « X est validé s'il existe au moins N
    couleurs pleines strictement plus dures que X ». C'est
    `tests/test_cascade.py::TestRepliExact` qui le mesure, en rejouant l'ancien
    algorithme.

    Un document abîmé rend une cascade vide plutôt qu'une erreur : le classement
    doit sortir, même dégradé, le jour d'une compétition.
    """
    brut = options.get("cascade")
    if brut is not None and not isinstance(brut, dict):
        logger.warning("options.cascade n'est pas un objet, ignoree")
        brut = None

    if isinstance(brut, dict):
        eteintes = _categories(brut.get("categories_eteintes"))
        if not brut.get("actif"):
            # La regle est eteinte, mais les interrupteurs restent : sinon un
            # aller-retour par une liste vide effacerait la portee sans un mot.
            return Cascade(categories_eteintes=eteintes)
        try:
            phrases = depuis_json(brut.get("regles", []))
        except ErreurMetier as e:
            logger.warning("cascade illisible, ignoree : %s", e.message)
            return Cascade(categories_eteintes=eteintes)
        bloquants, _ = controler(phrases)
        if bloquants:
            logger.warning("cascade rangee invalide, ignoree : %s", bloquants[0])
            return Cascade(categories_eteintes=eteintes)
        return Cascade(phrases=phrases, categories_eteintes=eteintes)

    ancien = options.get("validation_couleur", 0)
    if isinstance(ancien, bool) or not isinstance(ancien, (int, float)):
        if ancien not in (None, 0):
            logger.warning("validation_couleur illisible, ignoree")
        return Cascade()
    try:
        seuil = int(ancien)
    except (ValueError, OverflowError):
        logger.warning("validation_couleur hors bornes, ignoree")
        return Cascade()
    if seuil < 1:
        return Cascade()
    return Cascade(phrases=regle_du_classeur(min(seuil, len(COULEURS) - 1)))


def en_json(cascade: Cascade, actif: bool | None = None) -> dict:
    """Le document tel qu'il est rangé — l'inverse de `depuis_options`.

    `actif` se passe explicitement quand il ne se déduit pas des phrases : une
    règle vide mais des interrupteurs réglés, c'est un état qu'on doit pouvoir
    ranger sans perdre les seconds.
    """
    return {
        "actif": bool(cascade) if actif is None else bool(actif),
        "regles": [
            {"parmi": sorted(p.parmi, key=COULEURS.index),
             "seuil": p.seuil,
             "cibles": sorted(p.cibles, key=COULEURS.index)}
            for p in cascade.phrases
        ],
        "categories_eteintes": sorted(cascade.categories_eteintes),
    }


def est_celle_du_classeur(cascade: Cascade) -> bool:
    """La règle vaut-elle exactement celle du classeur ?

    Se **calcule**, ne se stocke pas : un drapeau posé à la main finirait par
    mentir sur ce que les phrases disent vraiment. C'est ce qui commande
    l'avertissement « le classeur ne saura pas suivre » (D7).

    ⚠️ On compare ce que les phrases **calculent**, pas leur écriture. Ajouter
    au préréglage une phrase sans effet ne change rien au classement : crier
    « le classeur ne saura pas suivre » serait faux, et on apprendrait vite à ne
    plus lire cet avertissement.
    """
    reference = regle_du_classeur()
    return all(_sortie(cascade.phrases, c) == _sortie(reference, c)
               for c in _COMBINAISONS)


def valider(corps: dict) -> tuple[dict, list[str]]:
    """Un corps de requête → le document à ranger, et ce qu'il faut dire.

    Ne touche NI la base NI le cache : c'est l'appelant qui range, parce que lui
    seul sait ce qu'il y a d'autre dans sa transaction. Lève `ErreurMetier` sur
    ce qui bloque, rend les avertissements sur ce qui mérite d'être dit sans
    empêcher d'enregistrer.
    """
    if not isinstance(corps, dict):
        raise ErreurMetier("Corps JSON attendu.")

    actif = bool(corps.get("actif"))
    phrases = depuis_json(corps.get("regles", [])) if actif else ()

    bloquants, avertissements = controler(phrases)
    if bloquants:
        raise ErreurMetier(" ".join(bloquants))

    brutes = corps.get("categories_eteintes", [])
    if not isinstance(brutes, list):
        raise ErreurMetier(
            "Une liste de categories eteintes est attendue.")
    if len(brutes) > CATEGORIES_MAX:
        raise ErreurMetier(
            f"{len(brutes)} categories eteintes, {CATEGORIES_MAX} au maximum.")
    # Une categorie INCONNUE est acceptee et rangee : elle peut reapparaitre au
    # prochain import, et le silence serait pire que l'oubli (meme choix que
    # `cycle.regler_affichage`).
    eteintes = frozenset(
        str(c).strip() for c in brutes if str(c).strip())

    document = en_json(
        Cascade(phrases=phrases, categories_eteintes=eteintes), actif=actif)
    return document, avertissements
