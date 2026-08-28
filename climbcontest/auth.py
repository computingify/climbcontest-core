"""Clé d'API des juges — en mode toléré.

Le problème : l'application `v3.1.4`, déployée sur le Play Store, **n'envoie
aucune clé**. La rendre obligatoire aujourd'hui, c'est casser l'application le
jour de la compétition.

Trois régimes, choisis par `CLIMBCONTEST_API_KEY_STRICTE` :

| Requête | Mode toléré (défaut) | Mode strict |
| --- | --- | --- |
| clé absente | **acceptée**, comptée | refusée `401` |
| clé correcte | acceptée | acceptée |
| clé **incorrecte** | **refusée `401`** | refusée `401` |

Une clé incorrecte est refusée dans les deux modes : quelqu'un qui en envoie une
fausse n'est pas l'application d'origine.

Le compteur d'appels sans clé est exposé par `/health`. C'est lui qui dira quand
on peut passer en mode strict sans risque : le jour où il reste à zéro pendant
toute une compétition, plus personne n'utilise l'ancienne application.
"""

import hmac
import logging
from functools import wraps

from flask import current_app, jsonify, request

logger = logging.getLogger(__name__)

ENTETE = "X-Api-Key"

# ⚠️ Ces compteurs sont PAR PROCESSUS. Avec quatre workers gunicorn, `/health`
# ne montre que la vue du worker qui a servi la requête — un autre peut en avoir
# compté cinquante. Ne jamais conclure « plus personne n'appelle sans clé » sur
# ce seul chiffre : c'est ainsi qu'on activerait le mode strict et qu'on
# casserait l'application un dimanche matin.
#
# La mesure qui fait foi est le JOURNAL, agrégé sur tous les workers :
#
#   journalctl -u climbcontest --since today | grep -c "appel sans cle"
#
# Ces compteurs restent utiles en développement, avec un seul worker.
compteurs = {"sans_cle": 0, "avec_cle": 0, "refusees": 0}


def _cle_fournie() -> str | None:
    entete = request.headers.get(ENTETE)
    if entete:
        return entete
    # `get_json` rend ce que contient le corps : un objet, mais aussi bien une
    # LISTE, une chaine ou un nombre si quelqu'un poste `[1,2]`. Sans ce test,
    # `.get` levait une AttributeError et la route repondait 500 au lieu de 400
    # — un scanner de vulnerabilites suffisait a le declencher.
    corps = request.get_json(silent=True)
    return corps.get("api_key") if isinstance(corps, dict) else None


def cle_valide(fournie: str | None) -> bool:
    attendue = current_app.config.get("API_KEY")
    if not attendue or not fournie:
        return False
    return hmac.compare_digest(str(fournie), str(attendue))


def exige_cle_api(vue):
    """Protège une route selon le régime configuré."""

    @wraps(vue)
    def enveloppe(*args, **kwargs):
        fournie = _cle_fournie()
        stricte = current_app.config.get("API_KEY_STRICTE")

        if fournie:
            if cle_valide(fournie):
                compteurs["avec_cle"] += 1
                return vue(*args, **kwargs)
            compteurs["refusees"] += 1
            logger.warning("cle d'API invalide depuis %s sur %s",
                           request.remote_addr, request.path)
            return jsonify({"success": False, "message": "Cle d'API invalide"}), 401

        # Aucune clé fournie.
        compteurs["sans_cle"] += 1
        # Journalisé, parce que c'est la seule mesure agrégée sur tous les
        # workers — et c'est elle qui décidera du passage en mode strict.
        logger.info("appel sans cle sur %s depuis %s",
                    request.path, request.remote_addr)
        if stricte:
            return jsonify({"success": False, "message": "Cle d'API requise"}), 401
        return vue(*args, **kwargs)

    return enveloppe
