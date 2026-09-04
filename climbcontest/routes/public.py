"""Ce que voient les spectateurs. Aucune authentification.

Ces routes sont exemptees de CrowdSec (voir la whitelist posee sur `edge`) et
mises en cache 5 s par Caddy : le jour d'une competition, ~60 telephones
rafraichissent toutes les 15 s, soit les trois quarts du trafic. Le cache
plafonne le calcul a 12 fois par minute quel que soit le nombre de spectateurs.
"""
import logging

from flask import Blueprint, jsonify, request

from ..classement_service import charge_publique, classements
from ..contest import ErreurMetier, competition_active
from ..models import Participant
from ..suivi import fiche

logger = logging.getLogger(__name__)
bp = Blueprint("public", __name__, url_prefix="/api/public")


@bp.after_request
def _pas_d_indexation(reponse):
    """Aucune reponse publique n'entre dans un moteur de recherche. Spec 043.

    Une reponse JSON n'a pas de balise `meta` : cet en-tete est le SEUL canal
    par lequel on peut le dire. Il porte les noms de tous les grimpeurs classes.

    ⚠️ Pose sur le BLUEPRINT, pas sur l'application. `/admin` et `/api/v2` ne
    sont pas concernes, et un crochet global finirait par etre lu comme une
    regle generale qu'il n'est pas.

    ⚠️ Il s'applique AUSSI aux reponses d'erreur de ces vues -- le 404 d'un
    groupe inconnu, le 409 d'une competition absente. Ce sont exactement les
    adresses qu'un robot fabrique en balayant.

    ⚠️ Pose ICI et non dans le Caddyfile de `edge` : cette reponse est mise en
    cache 5 s par le proxy, donc l'en-tete doit etre DEDANS. Et la
    configuration du proxy est recopiee a la main, elle derive, aucun test ne
    la lit. Caddy peut doubler ; il ne doit pas porter seul.
    """
    reponse.headers["X-Robots-Tag"] = "noindex"
    return reponse


@bp.get("/classement")
def classement():
    """Tous les classements, ou un seul avec ?groupe=U13%20F.

    Le nom des participants est inclus : la page resultats doit les afficher,
    et ils sont deja publics -- affiches sur les dossards et annonces au micro.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    charge = charge_publique(comp)

    # Le filtrage par groupe reste ICI : c'est une commodite de l'API publique
    # (`?groupe=U13%20F`), pas une propriete de la charge -- une archive fige
    # TOUS les classements, sans quoi elle ne serait consultable qu'en partie.
    demande = request.args.get("groupe")
    if demande:
        connus = [c["groupe"] for c in charge["classements"]]
        if demande not in connus:
            return jsonify({"success": False,
                            "message": f"Groupe « {demande} » inconnu",
                            "groupes": sorted(connus)}), 404
        charge["classements"] = [c for c in charge["classements"]
                                 if c["groupe"] == demande]

    return jsonify(charge), 200


@bp.get("/grimpeur/<int:identifiant>")
def grimpeur(identifiant: int):
    """La fiche d'un grimpeur : ses blocs, et ou il en est. Spec 026.

    Appelee au clic sur une ligne du classement, donc RAREMENT -- une requete
    par fiche ouverte, la ou la charge de classement est relue toutes les 15 s
    par soixante telephones. C'est pour ca qu'elle est a part : mettre ces
    blocs dans la charge publique ferait payer a tout le monde ce qu'une
    personne consulte.

    Elle n'expose rien de neuf : le nom, le club et la categorie de ceux qui
    sont AU CLASSEMENT sont deja dans la charge publique, et les blocs reussis
    sont annonces au micro et lisibles sur le mur. Le plan de la salle, lui,
    n'est pas ici : il part une fois avec la page.

    ⚠️ DEUX GARDES, et la seconde n'est pas une politesse.

    404 si le grimpeur n'est pas de la competition ACTIVE : sans elle,
    l'identifiant lirait les participants des editions passees, qui vivent dans
    la meme base.

    404 s'il ne figure dans AUCUN classement. Un inscrit sans categorie n'est
    indexe par aucun groupe (`calculer_tout`) : il n'apparait donc nulle part
    sur la page publique, et le rendre ici l'exposerait alors que rien d'autre
    ne le montre. Les identifiants sont sequentiels et rien ne limite le debit :
    sans cette garde, un balayage de `1..N` rendait le trombinoscope complet —
    nom, prenom, club, dossard. Le depot est public et les classeurs portent des
    noms de mineurs (regle 7).
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    participant = Participant.query.filter_by(
        id=identifiant, competition_id=comp.id).first()
    if participant is None or not _est_classe(comp, participant):
        return jsonify({"success": False,
                        "message": "Grimpeur inconnu dans cette competition"}), 404

    return jsonify(fiche(comp, participant)), 200


def _est_classe(comp, participant) -> bool:
    """Ce grimpeur apparait-il quelque part sur la page publique ?

    On interroge les classements DEJA CALCULES — ils sont en cache cinq
    secondes, la question ne coute donc rien de plus que ce que la page paie
    deja.
    """
    tous, _ = classements(comp)
    return any(ligne.participant_id == participant.id
               for classement in tous.values()
               for ligne in classement.lignes)


@bp.get("/reglages")
def reglages():
    """Ce que la page de resultats doit savoir TOUT DE SUITE, et rien d'autre.

    ⚠️ Une route de plus, et pas un rythme plus rapide sur `/classement`.

    « J'active un interrupteur, par exemple scratch femme, et je regarde si a
    cote mon scratch femme apparait dans ma page resultat. Du coup, non »
    (Adrien, 03/09, spec 033 R3). Le reglage arrivait bien -- mais au rythme de
    la relecture generale, quinze secondes, ce qui se lit comme « rien ne se
    passe » quand on vient d'appuyer sur « Enregistrer ».

    Baisser ce rythme etait exclu : `/classement` porte tous les classements et
    toutes leurs lignes, plusieurs dizaines de kilo-octets, relus par une
    soixantaine de telephones. Le CALCUL est deja plafonne (cache de
    `classements()`, plus 5 s de cache Caddy), la BANDE PASSANTE ne l'est pas.

    Cette reponse-ci ne calcule aucun classement : une ligne de base et un
    `json.loads` de sa colonne `options`, soit ~200 octets. Elle est donc
    relisible toutes les trois secondes sans rien couter au wifi de la salle.

    Elle ne REMPLACE rien : `groupes_masques` reste dans la charge de
    `/classement`, parce que c'est cette charge que `cycle.archiver` fige et
    qu'une archive amputee serait irreparable.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    from ..cycle import groupes_masques

    return jsonify({
        "competition": {
            "id": comp.id, "nom": comp.nom, "statut": comp.statut,
            "groupes_masques": groupes_masques(comp),
        },
    }), 200


@bp.get("/groupes")
def groupes():
    """La liste des classements disponibles, pour construire un menu."""
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    tous, _ = classements(comp)
    return jsonify({
        "groupes": [{"nom": c.groupe, "type": c.type, "participants": len(c.lignes)}
                    for c in sorted(tous.values(), key=lambda c: (c.type, c.groupe))]
    }), 200
