"""Sonde de sante et page d'accueil provisoire."""
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
    return jsonify(corps)


@bp.get("/")
def index():
    return jsonify({
        "service": "climbcontest",
        "version": VERSION,
        "message": "La page de resultats arrive avec la spec 006.",
    })
