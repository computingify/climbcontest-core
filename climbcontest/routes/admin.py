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

from flask import Blueprint, g, jsonify, request

from ..auth_session import exige_role, fermer, ouvrir, utilisateur_courant
from ..comptes import ErreurCompte, verifier
from ..contest import ErreurMetier, competition_active
from ..sheets.client import ErreurClasseur
from ..sheets.importer import importer

logger = logging.getLogger(__name__)
bp = Blueprint("admin", __name__, url_prefix="/admin")


# --- Connexion --------------------------------------------------------------
#
# La cle d'API partagee qui protegeait ces routes etait une mesure d'attente,
# posee en urgence le 28/08 apres avoir constate qu'elles repondaient 200 depuis
# Internet. Elle est remplacee ici par de vrais comptes.

@bp.post("/connexion")
def connexion():
    """{"identifiant": "...", "mot_de_passe": "..."} -> ouvre une session."""
    corps = request.get_json(silent=True)
    if not isinstance(corps, dict):
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    u = verifier(corps.get("identifiant", ""), corps.get("mot_de_passe", ""))
    if u is None:
        # Le MEME message et le MEME delai que l'identifiant existe ou non :
        # distinguer les deux revelerait quels comptes sont valides.
        logger.warning("connexion refusee pour « %s » depuis %s",
                       str(corps.get("identifiant", ""))[:40], request.remote_addr)
        return jsonify({"success": False,
                        "message": "Identifiant ou mot de passe incorrect"}), 401

    ouvrir(u)
    logger.info("connexion de %s depuis %s", u.identifiant, request.remote_addr)
    return jsonify({"success": True, "identifiant": u.identifiant,
                    "roles": sorted(r.role for r in u.roles)}), 200


@bp.post("/deconnexion")
def deconnexion():
    u = utilisateur_courant()
    fermer()
    if u:
        logger.info("deconnexion de %s", u.identifiant)
    return jsonify({"success": True}), 200


@bp.get("/moi")
@exige_role()
def moi():
    """Qui je suis, et ce que j'ai le droit de faire. La console s'en sert
    pour n'afficher que les boutons utilisables."""
    u = g.utilisateur
    return jsonify({
        "success": True,
        "identifiant": u.identifiant,
        "nom_affiche": u.nom_affiche,
        "roles": sorted(r.role for r in u.roles),
    }), 200

# Dernier rapport, en memoire. C'est un confort de consultation, pas une donnee :
# le perdre a un redemarrage est sans consequence, on relance l'import.
_dernier_rapport: dict | None = None


@bp.post("/import/sheet")
@exige_role()
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
@exige_role()
def dernier_rapport():
    if _dernier_rapport is None:
        return jsonify({"success": True, "rapport": None,
                        "message": "Aucun import depuis le demarrage"}), 200
    return jsonify({"success": True, "rapport": _dernier_rapport}), 200
