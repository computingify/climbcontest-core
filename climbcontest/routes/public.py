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

logger = logging.getLogger(__name__)
bp = Blueprint("public", __name__, url_prefix="/api/public")


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
