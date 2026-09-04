"""Envoi de réussites par lots — la route qui remplacera les appels un par un.

Aujourd'hui, chaque validation coûte au juge **trois allers-retours réseau
bloquants** : dossard, bloc, envoi. Il attend à chacun des trois, et chacun peut
échouer. Sur une compétition, cela fait ~10 800 requêtes.

Cette route accepte un lot. Elle est le versant serveur de la spec 003 — et
elle est délibérément livrable **seule** : tant qu'aucune application ne
l'appelle, rien ne change pour personne. C'est ce qui permet de la déployer sans
risque avant que l'application ne bouge.

⚠️ Les trois routes `v2` restent en service, inchangées. Cette route est
**ajoutée**, jamais substituée : rien ne garantit que les 25 téléphones auront
pris la mise à jour le jour J, et le plan de repli suppose que la `v3.1.4` gelée
parle au backend de production.
"""
import logging

from flask import Blueprint, jsonify, request

from ..auth import exige_cle_api
from ..contest import (
    ErreurMetier, competition_active, enregistrer_annonce, enregistrer_lot,
    identite_appareil,
)

logger = logging.getLogger(__name__)
bp = Blueprint("lot", __name__, url_prefix="/api/v3")

# Un lot plus gros que ça n'a aucune raison d'exister : l'application envoie par
# 5. Une valeur énorme viendrait d'un bogue ou d'un abus, et traiter 100 000
# éléments dans une requête bloquerait un worker sur les quatre pendant la
# compétition. On refuse proprement, avec un message qui dit quoi faire.
TAILLE_MAX = 200


@bp.post("/successes")
@exige_cle_api
def envoyer_lot():
    """{"appareil": {...}, "items": [{"ref", "bib", "bloc", "at"}]} → un verdict par élément.

    `appareil` est **facultatif**. Rien ne garantit que les 25 téléphones auront
    pris la mise à jour le matin de la compétition ; une application qui ne
    l'envoie pas doit continuer à fonctionner exactement comme avant.
    """
    corps = request.get_json(silent=True)
    if not isinstance(corps, dict):
        # Même garde que sur les routes v2 : un corps qui n'est pas un objet
        # doit donner 400, jamais 500. Un 500 est indistinguable d'une panne.
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    elements = corps.get("items")
    if not isinstance(elements, list):
        return jsonify({"success": False, "message": "Champ « items » attendu"}), 400
    if len(elements) > TAILLE_MAX:
        return jsonify({
            "success": False,
            "message": f"Lot trop gros ({len(elements)}), maximum {TAILLE_MAX}. "
                       f"Decouper en plusieurs envois.",
        }), 413
    if any(not isinstance(e, dict) for e in elements):
        return jsonify({"success": False,
                        "message": "Chaque element doit etre un objet"}), 400

    try:
        comp = competition_active()
    except ErreurMetier as e:
        # 409 et non 400 : l'application doit garder sa file et réessayer plus
        # tard, pas jeter ce qu'elle a.
        return jsonify({"success": False, "message": e.message}), e.code

    appareil = identite_appareil(corps.get("appareil"))
    resultats = enregistrer_lot(elements, appareil)

    # ⚠️ La MEME annonce que sur la route du catalogue, et c'est deliberement
    # redondant (spec 030, F8). L'annonce voyage normalement sur un GET, qu'un
    # cache pose un jour devant `/api/v2/catalog` absorberait sans que rien ne
    # le dise. Un POST, lui, n'est jamais mis en cache : tant que des reussites
    # arrivent, la console sait au moins quelle VERSION tourne sur ce telephone.
    #
    # ⚠️ Et surtout : **pas de `catalogue_version` ici.** Recevoir un lot prouve
    # que le telephone est vivant, pas qu'il detient le catalogue courant. Le
    # renseigner depuis cette route afficherait « a jour » un telephone qui ne
    # s'est pas synchronise depuis des heures -- exactement le mensonge que
    # cette spec existe pour supprimer.
    if appareil:
        enregistrer_annonce(appareil["id"], nom=appareil.get("nom"),
                            version_app=appareil.get("app"))

    # La version du catalogue voyage dans une réponse qui part de toute façon :
    # l'application apprend qu'elle a du retard sans requête supplémentaire.
    return jsonify({
        "success": True,
        "resultats": resultats,
        "catalogue_version": comp.catalogue_version,
    }), 200
