"""Clé d'API des juges.

Deux régimes, choisis par `CLIMBCONTEST_API_KEY_STRICTE` :

| Requête | Mode **strict** (défaut) | Mode toléré (`=0`) |
| --- | --- | --- |
| clé absente | refusée `401` | **acceptée**, comptée |
| clé correcte | acceptée | acceptée |
| clé **incorrecte** | refusée `401` | refusée `401` |

Une clé incorrecte est refusée dans les deux régimes : quelqu'un qui en envoie
une fausse n'est pas l'application d'origine.

**Le défaut est strict depuis la spec 012.** Il était toléré jusque-là, pour une
raison qui n'a pas disparu : l'application `v3.1.4` du Play Store n'envoie aucune
clé, et c'est elle le plan de repli garanti de novembre. Y revenir suppose donc
de reposer `CLIMBCONTEST_API_KEY_STRICTE=0` — c'est écrit en tête du plan de
repli, parce que c'est exactement le genre d'étape qu'on oublie dans l'urgence.

⚠️ **Ce qu'une clé compilée dans un APK protège.** Elle s'extrait en quelques
minutes de l'application, qui est distribuée publiquement. Elle arrête un robot
qui balaie Internet et trouve `/api/v3/successes` ; elle n'arrête pas quelqu'un
qui a l'application et veut fausser la compétition. Le raisonnement complet est
dans `specs/012-cle-api-juges/spec.md`.

Plusieurs clés peuvent être acceptées en même temps, pour en changer sans jour
de bascule.
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


def cles_acceptees() -> tuple:
    return tuple(current_app.config.get("API_KEYS") or ())


def cle_valide(fournie: str | None) -> bool:
    """Compare a TOUTES les cles acceptees, sans court-circuit.

    Un `any(...)` s'arreterait a la premiere qui correspond, et le temps de
    reponse dirait alors LAQUELLE des cles a ete reconnue -- ce qui indique a
    quelqu'un qui tatonne laquelle des deux il vient de deviner. On les compare
    donc toutes, et on accumule.
    """
    if not fournie:
        return False
    resultat = False
    for attendue in cles_acceptees():
        resultat |= hmac.compare_digest(str(fournie), str(attendue))
    return resultat


def _configuration_incoherente():
    """Mode strict et aucune cle : personne ne peut plus rien envoyer.

    Repondre `401` enverrait chercher un probleme de cle cote application, alors
    que la variable est absente cote serveur. Un `503` nommant la variable dit
    ce qui se passe -- le meme choix que `auth_session` fait deja pour une
    `SECRET_KEY` absente.
    """
    if not current_app.config.get("API_KEY_STRICTE"):
        return None
    if cles_acceptees():
        return None
    logger.error("cle d'API exigee mais AUCUNE n'est configuree : "
                 "poser CLIMBCONTEST_API_KEY, ou CLIMBCONTEST_API_KEY_STRICTE=0")
    return jsonify({
        "success": False,
        "message": "Serveur mal configure : aucune cle d'API n'est definie "
                   "(CLIMBCONTEST_API_KEY).",
    }), 503


def exige_cle_api(vue):
    """Protège une route selon le régime configuré."""

    @wraps(vue)
    def enveloppe(*args, **kwargs):
        incoherente = _configuration_incoherente()
        if incoherente:
            return incoherente

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
