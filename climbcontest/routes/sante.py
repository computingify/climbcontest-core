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
    """Sonde. Ne depend d'aucun service EXTERNE -- mais bien de la base.

    Volontairement sans acces au classeur Google : une sonde qui tombe parce
    qu'un tiers est lent declencherait des retours arriere de deploiement et des
    alertes pour rien.

    La base, elle, n'est pas un tiers : c'est le service. Une sonde qui repond
    « ok » sans l'avoir interrogee ne mesure rien. Elle a d'ailleurs deja laisse
    passer le pire cas -- quatre workers demarres sur une base sans tables :
    l'exception etait avalee ici, `reussites_en_attente` valait `null`, le
    statut restait « ok », et l'agent de deploiement validait la mise en
    production d'un serveur ou chaque scan renvoyait 500.

    Desormais : si la base n'est pas interrogeable, la sonde repond **503
    degraded**. C'est ce qui doit declencher le retour arriere, pas ce qu'il
    faut cacher pour l'eviter.

    `reussites_en_attente` dit si le miroir vers le classeur suit. Un nombre qui
    monte sans redescendre = le classeur n'est plus alimente, mais AUCUNE donnee
    n'est perdue : tout est en base.
    """
    corps = {"status": "ok", "version": VERSION}
    code = 200
    try:
        from ..contest import reussites_en_attente
        corps["reussites_en_attente"] = reussites_en_attente()
    except Exception as e:
        corps["reussites_en_attente"] = None
        corps["status"] = "degraded"
        corps["base"] = f"injoignable : {type(e).__name__}"
        code = 503

    # ⚠️ Compteurs PAR WORKER, pas globaux. Avec 4 workers gunicorn, ce que
    # vous lisez ici est la vue d'un seul d'entre eux. Pour savoir si quelqu'un
    # appelle encore sans cle d'API -- la question qui decide du passage en mode
    # strict -- utiliser le journal, qui agrege tout :
    #   journalctl -u climbcontest --since today | grep -c "appel sans cle"
    from ..auth import compteurs
    from ..sheets.planificateur import est_actif
    corps["api"] = {**compteurs, "portee": "ce worker seulement", "pid": os.getpid()}
    corps["miroir_actif"] = est_actif()
    return jsonify(corps), code


# La racine servait un JSON de service, avec pour tout message « la page de
# resultats arrive avec la spec 006 ». Elle est arrivee : c'est desormais
# routes/pages.py qui repond sur « / ». Un visiteur qui tape l'adresse du
# service doit voir le classement, pas un objet JSON.
