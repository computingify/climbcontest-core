"""La fiche du grimpeur EN DIRECT — spec 026.

La spec 023 imprime, avant la compétition, une fiche qui dit à un grimpeur
**quels blocs comptent pour lui** et **où ils sont**. Elle ne peut rien dire de
ce qu'il a fait : elle sort de l'imprimante le matin.

Ce module est sa jumelle d'écran. Il compose deux choses qui existent déjà —
les blocs du circuit et leur ordre (`fiches`), les réussites et la cascade de
couleurs (`classement_service`) — et n'en calcule aucune lui-même. Il ne fait
qu'**assembler** :

    fiches                    -> quels blocs, dans quel ordre, où sur le mur
    classement_service        -> lesquels sont grimpés, lesquels sont crédités
    ce module                 -> les deux, dans la forme que la page consomme

**Aucun Flask ici**, comme dans `fiches.py`, `cycle.py` et `circuits.py` : il
ne parle qu'à la base, et tout se teste sans client HTTP.
"""

from . import fiches
from .classement_service import blocs_du_grimpeur, nom_publie

# --- Le contrat du plan, versionné ------------------------------------------
#
# ⚠️ CE NUMÉRO EST LE POINT DE RENDEZ-VOUS ENTRE `PLAN` ET LA PAGE.
#
# `fiches.PLAN` a déjà changé de forme une fois — une grille de 8×7 cases est
# devenue un jeu de polygones (spec 028) — et il rechangera : c'est un relevé
# de salle — et depuis la spec 029, un relevé qu'Adrien peut REDESSINER depuis
# la console. La page de résultats ne peut donc pas se contenter de « faire
# confiance » à la forme reçue.
#
# La règle : **la page vérifie ce numéro avant de dessiner quoi que ce soit.**
# S'il ne correspond pas à ce qu'elle sait rendre, elle n'affiche PAS le mur et
# laisse les blocs non cliquables — au lieu de dessiner un plan faux, ce qui
# enverrait quelqu'un chercher un bloc au mauvais endroit.
#
# Donc : **on incrémente ce numéro dès que la forme de `plan_public()` change**
# — un champ retiré, un champ renommé, une géométrie exprimée autrement. Pas
# quand les COORDONNÉES changent : redessiner la salle ne casse rien.
FORMAT_PLAN = "polygones/1"

# Les états d'un bloc, du point de vue du grimpeur. Trois, et pas quatre : le
# hors-circuit ne s'affiche pas sur la fiche (décision du 02/09) — il reste
# visible pour un organisateur, pas pour le grimpeur, qui ne peut rien en
# faire sur un écran public.
GRIMPE, CREDITE, RESTE = "grimpe", "credite", "reste"


def plan_public() -> dict:
    """Le plan de la salle, tel que la page le reçoit. **Sans grimpeur.**

    `fiches.plan_pour()` sait déjà tout faire — le cadrage avec sa marge, la
    place et la taille des lettres, le repli d'un profil inconnu. On l'appelle
    avec un ensemble VIDE, ce qui donne exactement le plan nu.

    Pourquoi nu : le plan est le **même pour tout le monde**. Le servir par
    grimpeur transformerait une donnée commune en charge par requête, et
    multiplierait les entrées du cache de Caddy pour un dessin rigoureusement
    identique. C'est la page qui allume les zones, à partir des blocs qu'elle a
    déjà.

    ⚠️ Depuis la spec 029, il n'est plus figé : la console peut l'enregistrer.
    `plan_pour()` lit donc le plan ACTIF, et deux appels séparés par un
    enregistrement ne rendent plus la même chose. Ce qui reste vrai, et ce sur
    quoi la page compte, c'est qu'il ne dépend d'aucun grimpeur.

    `sienne` est donc retiré : le laisser à `False` inviterait quelqu'un à s'en
    servir, et il serait faux.
    """
    plan = fiches.plan_pour(set())
    return {
        "format": FORMAT_PLAN,
        "vue": list(plan["vue"]),
        "cadrage": plan["cadrage"],
        "contour": plan["contour"],
        "murs": [
            {"zone": m["zone"], "profil": m["profil"], "d": m["d"],
             "etiquette": list(m["etiquette"]), "taille": m["taille"]}
            for m in plan["murs"] if m["zone"]
        ],
        "reperes": plan["reperes"],
    }


def _etat(bloc_id: int, grimpes: set[int], credites: set[int]) -> str:
    if bloc_id in grimpes:
        return GRIMPE
    if bloc_id in credites:
        return CREDITE
    return RESTE


def fiche(comp, participant) -> dict:
    """Tout ce que la page affiche d'un grimpeur, et rien de plus.

    Les blocs sortent dans l'ordre du classeur — la difficulté d'abord, le
    numéro ensuite — parce que c'est celui de la fiche papier que le grimpeur
    tient dans la main. Deux documents qui rangent les mêmes blocs autrement,
    c'est un document de plus à déchiffrer, pas le même à jour.

    Un circuit inconnu ou vide ne lève rien : la fiche se rend quand même, avec
    `manque` en toutes lettres. C'est la même règle que `fiches.construire()` —
    ce qui manque se dit, il ne fait pas disparaître l'écran.
    """
    circuit = participant.circuit
    par_circuit = fiches._blocs_par_circuit(comp)
    blocs = par_circuit.get(circuit) if circuit else None

    manque = None
    if not participant.categorie:
        manque = ("Aucune categorie : ce grimpeur n'est rattache a aucun "
                  "circuit.")
    elif blocs is None:
        manque = (f"Circuit « {circuit} » inconnu — le classeur n'a pas encore "
                  "ete importe pour cette competition.")
    elif not blocs:
        manque = f"Aucun bloc dans le circuit « {circuit} »."

    blocs = blocs or []
    etats = blocs_du_grimpeur(comp, participant)
    grimpes, credites = etats["grimpes"], etats["credites"]

    # ⚠️ Le groupement vient de `fiches`, il n'est PAS recopie ici. Il l'a ete
    # une premiere version durant : meme boucle, meme regle de repli, meme cle
    # de rupture. Le jour ou le papier change sa facon de grouper, l'ecran
    # aurait diverge en silence — et c'est exactement ce que ce module dit ne
    # jamais faire. On annote ce que `fiches` a range, rien de plus.
    par_tag = {bloc.tag: _etat(bloc.id, grimpes, credites) for bloc in blocs}
    groupes = fiches._groupes(blocs)
    for groupe in groupes:
        for bloc in groupe["blocs"]:
            bloc["etat"] = par_tag.get(bloc["tag"], RESTE)

    ids = {b.id for b in blocs}
    return {
        "participant": {
            "id": participant.id,
            "dossard": participant.dossard,
            # Le MEME nom que le classement (spec 043) : sans ca, le reglage
            # se contournerait en touchant une ligne du classement pour ouvrir
            # la fiche.
            "nom": nom_publie(participant),
            "club": participant.club,
            "categorie": participant.categorie,
            "circuit": circuit,
        },
        "total": len(blocs),
        # On recompte SUR LES BLOCS AFFICHÉS, jamais sur les ensembles bruts.
        # Un bloc réussi puis retiré du circuit resterait dans `grimpes` et
        # ferait afficher « 13 grimpés » sous un tableau qui en montre 12.
        "grimpes": len(grimpes & ids),
        "credites": len(credites & ids),
        "groupes": groupes,
        "manque": manque,
    }
