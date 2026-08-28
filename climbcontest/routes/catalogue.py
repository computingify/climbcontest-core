"""Le catalogue — ce que l'application juge télécharge pour travailler hors ligne.

C'est la pièce qui permettra à l'application (spec 003) de valider un scan
**sans réseau**, tout en voyant un participant ajouté à 14 h.

Le mécanisme est un simple numéro de version :

    GET /api/v2/catalog             → tout, plus la version courante
    GET /api/v2/catalog?depuis=41   → 304 si rien n'a bouge, sinon tout

Pourquoi renvoyer **tout** plutôt qu'un vrai delta : 98 participants et 67 blocs
font 6 à 8 ko compressés. Un delta économiserait quelques kilo-octets au prix
d'un suivi des suppressions et des conflits — de la complexité pour rien à cette
échelle. Le `304` fait déjà l'essentiel : quand rien n'a changé, il ne passe
presque rien sur le réseau, et c'est le cas la plupart du temps.
"""

import logging

from flask import Blueprint, jsonify, request

from ..auth import exige_cle_api
from ..contest import ErreurMetier, competition_active
from ..models import Bloc, Circuit, Participant

logger = logging.getLogger(__name__)
bp = Blueprint("catalogue", __name__, url_prefix="/api/v2")


@bp.get("/catalog")
@exige_cle_api
def catalogue():
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    depuis = request.args.get("depuis", type=int)
    if depuis is not None and depuis >= comp.catalogue_version:
        # Rien de neuf : l'application garde ce qu'elle a.
        return "", 304

    participants = (Participant.query
                    .filter_by(competition_id=comp.id)
                    .order_by(Participant.dossard)
                    .all())
    blocs = (Bloc.query
             .filter_by(competition_id=comp.id)
             .order_by(Bloc.numero)
             .all())
    circuits = Circuit.query.filter_by(competition_id=comp.id).all()

    return jsonify({
        "competition": {"id": comp.id, "nom": comp.nom, "statut": comp.statut},
        "version": comp.catalogue_version,
        # Seuls les participants qui ont un dossard sont scannables.
        "participants": [p.to_dict() for p in participants if p.dossard is not None],
        "blocs": [b.to_dict() for b in blocs],
        "circuits": [c.nom for c in circuits],
    }), 200
