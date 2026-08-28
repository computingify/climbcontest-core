"""Point d'entrée gunicorn de ClimbContest.

⚠️ PROVISOIRE — spec 001, itération 3.

Ce module ne contient volontairement qu'une application minimale : l'objectif de
la spec 001 est de valider la *chaîne de livraison* (release signée, tirage,
vérification d'empreinte, bascule, sonde, retour arrière) **avant** qu'il y ait
un vrai backend à livrer. Déboguer le déploiement et l'application en même temps
est le meilleur moyen de ne comprendre ni l'un ni l'autre.

La spec 002 remplacera le contenu de ce fichier par la vraie fabrique
d'application. `wsgi.py` restera le point d'entrée, et
`deployment/climbcontest.service` n'aura pas à changer.

Ce qui est déjà définitif :
- la route /health, sur laquelle s'appuient l'agent de déploiement, la sonde de
  maintenance et l'alerte ClimbcontestInjoignableEnService ;
- le fait qu'elle renvoie la **version déployée**. C'est ce qui permet à l'agent
  de vérifier non pas « ça répond » mais « ça répond avec la version que je viens
  d'installer » — un service qui n'aurait pas redémarré passerait autrement pour
  un déploiement réussi.
"""

from pathlib import Path

from flask import Flask, jsonify

RACINE = Path(__file__).resolve().parent


def lire_version() -> str:
    """Version de la release installée.

    Le fichier VERSION est écrit par le workflow de release au moment de
    construire l'archive. En développement il n'existe pas : on le dit
    explicitement plutôt que de renvoyer une version inventée.
    """
    fichier = RACINE / "VERSION"
    try:
        version = fichier.read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"
    return version or "dev"


VERSION = lire_version()

app = Flask(__name__)


@app.get("/health")
def health():
    """Sonde de santé. Ne dépend d'aucune ressource externe.

    Volontairement sans accès à la base ni au classeur Google : une sonde qui
    tombe parce qu'un service tiers est lent déclencherait des retours arrière
    et des alertes pour rien. C'est la leçon du 2026-08-25 sur les VM 102 et
    103 (piège 7 des notes de maintenance).
    """
    return jsonify(status="ok", version=VERSION)


@app.get("/")
def index():
    return jsonify(
        service="climbcontest",
        version=VERSION,
        message="Socle deploye. Le backend arrive avec la spec 002.",
    )
