"""Routes d'administration.

Squelette de la spec 002 : seul l'import du classeur est ici. La console
complete -- saisie manuelle, parametrage, participants a chaud, impression des
dossards, archives, comptes -- est le sujet de la spec 005.

⚠️ PROTECTION PROVISOIRE. Ces routes exigent la cle d'API pour l'instant. La
spec 005 les passera en session + roles, sur le modele de guestFlow
(requireAuth + enforceRoleAccess, liste blanche par role, fail-closed). Le
Caddyfile distingue deja /admin/* des autres surfaces : CrowdSec y reste actif,
et l'exemption posee pour l'API des juges ne s'y applique pas.
"""
import logging

from flask import Blueprint, jsonify

from ..auth import exige_cle_api_stricte
from ..contest import ErreurMetier, competition_active
from ..sheets.client import ErreurClasseur
from ..sheets.importer import importer

logger = logging.getLogger(__name__)
bp = Blueprint("admin", __name__, url_prefix="/admin")

# Dernier rapport, en memoire. C'est un confort de consultation, pas une donnee :
# le perdre a un redemarrage est sans consequence, on relance l'import.
_dernier_rapport: dict | None = None


@bp.post("/import/sheet")
@exige_cle_api_stricte
def importer_classeur():
    """Relit le classeur et met la base a jour.

    Sur COMMANDE, jamais dans le chemin d'une requete juge (risque R7). Un
    dossard inconnu scanne en boucle ne doit pas pouvoir declencher des lectures
    Google en rafale.
    """
    global _dernier_rapport
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    try:
        rapport = importer(comp)
    except ErreurClasseur as e:
        logger.warning("import refuse : %s", e)
        return jsonify({"success": False, "message": str(e)}), 502

    _dernier_rapport = rapport.to_dict()
    _dernier_rapport["resume"] = rapport.resume()
    return jsonify({"success": True, "rapport": _dernier_rapport}), 200


@bp.get("/import/rapport")
@exige_cle_api_stricte
def dernier_rapport():
    if _dernier_rapport is None:
        return jsonify({"success": True, "rapport": None,
                        "message": "Aucun import depuis le demarrage"}), 200
    return jsonify({"success": True, "rapport": _dernier_rapport}), 200
