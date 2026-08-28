"""Sonde de sante et page d'accueil provisoire."""
import os
from pathlib import Path

from flask import Blueprint, jsonify

bp = Blueprint("sante", __name__)
RACINE = Path(__file__).resolve().parent.parent.parent


def _version() -> str:
    try:
        return (RACINE / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


VERSION = _version()


@bp.get("/health")
def health():
    """Sonde. Ne depend d'aucun service externe.

    Volontairement sans acces au classeur Google : une sonde qui tombe parce
    qu'un tiers est lent declencherait des retours arriere de deploiement et des
    alertes pour rien.

    `reussites_en_attente` dit si le miroir vers le classeur suit. Un nombre qui
    monte sans redescendre = le classeur n'est plus alimente, mais AUCUNE donnee
    n'est perdue : tout est en base.
    """
    corps = {"status": "ok", "version": VERSION}
    try:
        from ..contest import reussites_en_attente
        corps["reussites_en_attente"] = reussites_en_attente()
    except Exception:
        corps["reussites_en_attente"] = None

    # ⚠️ Compteurs PAR WORKER, pas globaux. Avec 4 workers gunicorn, ce que
    # vous lisez ici est la vue d'un seul d'entre eux. Pour savoir si quelqu'un
    # appelle encore sans cle d'API -- la question qui decide du passage en mode
    # strict -- utiliser le journal, qui agrege tout :
    #   journalctl -u climbcontest --since today | grep -c "appel sans cle"
    from ..auth import compteurs
    from ..sheets.planificateur import est_actif
    corps["api"] = {**compteurs, "portee": "ce worker seulement", "pid": os.getpid()}
    corps["miroir_actif"] = est_actif()
    return jsonify(corps)


@bp.get("/")
def index():
    return jsonify({
        "service": "climbcontest",
        "version": VERSION,
        "message": "La page de resultats arrive avec la spec 006.",
    })
