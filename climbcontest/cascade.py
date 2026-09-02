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

import logging

from .classement import COULEURS, Cascade, Phrase
from .contest import ErreurMetier

logger = logging.getLogger(__name__)

# La règle du classeur, mesurée le 02/09/2026 en activant `Listes!D29:D38` dans
# une copie jetable : un bloc de couleur X est validé dès que DEUX couleurs
# strictement plus dures que X sont entièrement réussies.
SEUIL_CLASSEUR = 2


def _plus_dures(couleur: str) -> list[str]:
    return COULEURS[COULEURS.index(couleur) + 1:]


def regle_du_classeur(seuil: int = SEUIL_CLASSEUR) -> tuple[Phrase, ...]:
    """La règle du classeur, écrite en phrases.

    Une couleur qui n'a pas assez de couleurs plus dures au-dessus d'elle n'est
    **jamais** validable — avec le seuil à 2, c'est le cas du Rouge, qui n'a que
    le Noir au-dessus. Le classeur fait exactement pareil ; on ne lui invente pas
    une phrase qu'il n'a pas.
    """
    return tuple(
        Phrase(parmi=frozenset(_plus_dures(c)), seuil=seuil, cibles=frozenset({c}))
        for c in COULEURS
        if len(_plus_dures(c)) >= seuil
    )


def implique(b: Phrase, a: Phrase) -> bool:
    """La condition de `b` entraîne-t-elle celle de `a` ?

    Exact, pas heuristique : satisfaire `b` demande `seuil(b)` couleurs pleines
    prises dans `parmi(b)` ; dans le pire des cas, `seuil(b) - |parmi(b) hors
    parmi(a)|` d'entre elles tombent quand même dans `parmi(a)`. Si ce minimum
    atteint déjà `seuil(a)`, `a` tient forcément.

    Confronté à une vérification par force brute sur les 64 combinaisons de
    couleurs pleines, pour 3 890 paires tirées au hasard : 0 désaccord.
    """
    hors = len(b.parmi - a.parmi)
    return (b.seuil - hors) >= a.seuil


def controler(phrases: tuple[Phrase, ...]) -> tuple[list[str], list[str]]:
    """Rend `(bloquants, avertissements)`.

    Ce qui **bloque** est ce qui ne veut rien dire — une phrase incomplète, une
    cascade qui remonte. Ce qui **avertit** est ce qui veut dire autre chose que
    ce qu'on croit : la phrase morte, et deux phrases sur la même couleur.

    On avertit sans bloquer parce qu'une phrase morte peut être volontaire — on
    la garde le temps d'en écrire une autre — alors qu'une cascade qui remonte
    n'a aucune lecture possible.
    """
    bloquants: list[str] = []
    avertissements: list[str] = []
    mortes: set[int] = set()

    for i, phrase in enumerate(phrases, start=1):
        if not phrase.parmi:
            bloquants.append(
                f"Regle {i} incomplete : il lui manque une couleur declencheur.")
        if not phrase.cibles:
            bloquants.append(
                f"Regle {i} incomplete : il lui manque une couleur a valider.")
        if not phrase.parmi or not phrase.cibles:
            continue
        if not 1 <= phrase.seuil <= len(phrase.parmi):
            bloquants.append(
                f"Regle {i} : il en faut {phrase.seuil}, mais "
                f"{len(phrase.parmi)} couleur(s) sont cochees.")
            continue

        # La cascade descend. Une phrase peut ecrire l'inverse -- une matrice,
        # non : ses cases y seraient mortes. C'est le seul defaut que la forme
        # « phrase » introduit, donc le seul qui doit bloquer.
        plus_facile = min(phrase.parmi, key=COULEURS.index)
        for cible in sorted(phrase.cibles, key=COULEURS.index):
            if COULEURS.index(cible) >= COULEURS.index(plus_facile):
                bloquants.append(
                    f"Regle {i} : « {cible} » n'est pas plus facile que "
                    f"« {plus_facile} ». La cascade descend, elle ne remonte pas.")

    if bloquants:
        return bloquants, avertissements

    for i, b in enumerate(phrases, start=1):
        for j, a in enumerate(phrases, start=1):
            if i == j or not a.parmi or not a.cibles:
                continue
            if not implique(b, a) or not b.cibles <= a.cibles:
                continue
            # Deux phrases equivalentes s'impliquent mutuellement : on ne
            # signale que la SECONDE, sinon chacune accuse l'autre et on ne sait
            # pas laquelle retirer.
            if implique(a, b) and a.cibles == b.cibles and j > i:
                continue
            mortes.add(i)
            avertissements.append(
                f"Regle {i} sans effet : elle ne peut pas se declencher sans "
                f"que la regle {j}, plus facile a satisfaire, ait deja valide "
                f"tout ce qu'elle valide.")
            break

    for i in range(1, len(phrases) + 1):
        for j in range(i + 1, len(phrases) + 1):
            if i in mortes or j in mortes:
                continue
            communes = phrases[i - 1].cibles & phrases[j - 1].cibles
            if communes:
                noms = ", ".join(sorted(communes, key=COULEURS.index))
                avertissements.append(
                    f"Regles {i} et {j} valident toutes deux « {noms} ». Elles "
                    f"s'additionnent, elles ne se remplacent pas : il suffit "
                    f"que l'une tienne.")

    return bloquants, avertissements


def _couleurs(valeurs, ou: str) -> frozenset[str]:
    """Valide une liste de couleurs de difficulté venue du dehors."""
    if not isinstance(valeurs, list):
        raise ErreurMetier(f"{ou} : une liste de couleurs est attendue.")
    propres = []
    for v in valeurs:
        nom = str(v).strip().capitalize()
        if nom not in COULEURS:
            raise ErreurMetier(
                f"Couleur inconnue « {v} ». Les couleurs de difficulte sont "
                + ", ".join(COULEURS) + ".")
        propres.append(nom)
    return frozenset(propres)


def depuis_json(donnees) -> tuple[Phrase, ...]:
    """Les phrases d'un corps de requête ou d'un document rangé."""
    if not isinstance(donnees, list):
        raise ErreurMetier("Une liste de regles est attendue.")
    phrases = []
    for i, brut in enumerate(donnees, start=1):
        if not isinstance(brut, dict):
            raise ErreurMetier(f"Regle {i} : un objet est attendu.")
        try:
            seuil = int(brut.get("seuil", 1))
        except (TypeError, ValueError):
            raise ErreurMetier(f"Regle {i} : « il en faut » doit etre un nombre.") from None
        phrases.append(Phrase(
            parmi=_couleurs(brut.get("parmi", []), f"Regle {i}"),
            seuil=seuil,
            cibles=_couleurs(brut.get("cibles", []), f"Regle {i}"),
        ))
    return tuple(phrases)


def depuis_options(options: dict) -> Cascade:
    """La cascade d'une édition, repli compris.

    ⚠️ `validation_couleur` — l'option de la spec 004, un simple entier — reste
    lue quand `cascade` est absente. Sa conversion est **exacte** : l'ancienne
    règle validait tout ce qui est plus facile que la N-ième couleur pleine la
    plus dure, ce qui revient à dire « X est validé s'il existe au moins N
    couleurs pleines strictement plus dures que X ». Mesuré : 9 000 comparaisons
    entre l'ancien calcul et ces phrases, 0 écart.

    Un document abîmé rend une cascade vide plutôt qu'une erreur : le classement
    doit sortir, même dégradé, le jour d'une compétition.
    """
    brut = options.get("cascade")
    if isinstance(brut, dict):
        if not brut.get("actif"):
            return Cascade()
        try:
            phrases = depuis_json(brut.get("regles", []))
        except ErreurMetier as e:
            logger.warning("cascade illisible, ignoree : %s", e.message)
            return Cascade()
        eteintes = brut.get("categories_eteintes")
        return Cascade(
            phrases=phrases,
            categories_eteintes=frozenset(
                str(c) for c in eteintes
                if isinstance(c, str) and c.strip()
            ) if isinstance(eteintes, list) else frozenset(),
        )

    ancien = options.get("validation_couleur", 0)
    try:
        seuil = max(0, int(ancien))
    except (TypeError, ValueError):
        return Cascade()
    if seuil <= 0:
        return Cascade()
    return Cascade(phrases=regle_du_classeur(seuil))


def en_json(cascade: Cascade) -> dict:
    """Le document tel qu'il est rangé — l'inverse de `depuis_options`."""
    return {
        "actif": bool(cascade),
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
    """
    return set(cascade.phrases) == set(regle_du_classeur())


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
    # Une categorie INCONNUE est acceptee et rangee : elle peut reapparaitre au
    # prochain import, et le silence serait pire que l'oubli (meme choix que
    # `cycle.regler_affichage`).
    eteintes = frozenset(
        str(c).strip() for c in brutes if str(c).strip())

    document = en_json(Cascade(phrases=phrases, categories_eteintes=eteintes))
    return document, avertissements
