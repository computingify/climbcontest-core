"""Ce que voient les spectateurs. Aucune authentification.

Ces routes sont exemptees de CrowdSec (voir la whitelist posee sur `edge`) et
mises en cache 5 s par Caddy : le jour d'une competition, ~60 telephones
rafraichissent toutes les 15 s, soit les trois quarts du trafic. Le cache
plafonne le calcul a 12 fois par minute quel que soit le nombre de spectateurs.
"""
import logging

from flask import Blueprint, jsonify, request

from ..classement_service import classements
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

    tous, calcule_le = classements(comp)

    demande = request.args.get("groupe")
    if demande:
        if demande not in tous:
            return jsonify({"success": False,
                            "message": f"Groupe « {demande} » inconnu",
                            "groupes": sorted(tous)}), 404
        choisis = {demande: tous[demande]}
    else:
        choisis = tous

    # Les noms, en une seule requete plutot qu'une par ligne.
    from ..models import Participant
    noms = {
        p.id: {"nom": p.nom_complet, "club": p.club, "categorie": p.categorie}
        for p in Participant.query.filter_by(competition_id=comp.id).all()
    }

    def enrichir(ligne):
        d = ligne.to_dict()
        d.update(noms.get(ligne.participant_id, {}))
        return d

    return jsonify({
        "competition": {"id": comp.id, "nom": comp.nom, "statut": comp.statut},
        "calcule_le": calcule_le,
        "classements": [
            {**c.to_dict(), "lignes": [enrichir(l) for l in c.lignes]}
            for c in sorted(choisis.values(), key=lambda c: (c.type, c.groupe))
        ],
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
