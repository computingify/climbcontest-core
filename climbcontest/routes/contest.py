"""Routes de la compétition.

⚠️ CONTRAT FIGE. L'application juge v3.1.4 est deployee sur le Play Store et ne
sera PAS mise a jour avant la spec 003. Ces trois routes doivent garder
exactement leur forme : meme chemin, meme corps attendu, meme code 201, memes
cles dans la reponse.

Ce qui change est interne : la reussite est ecrite en base avant de repondre, un
dossard inconnu ne declenche plus d'appel Google, et un doublon renvoie 201 sans
creer de seconde ligne.

La cle d'API est appliquee ici en MODE TOLERE : l'application v3.1.4 n'en envoie
aucune, et une cle absente reste acceptee. C'est neanmoins sur ces routes que la
mesure compte -- ce sont elles que l'application appelle. Voir auth.py.
"""
import logging

from flask import Blueprint, current_app, jsonify, request

from ..auth import exige_cle_api
from ..contest import (
    ErreurMetier, bloc_par_tag, competition_active, enregistrer_reussite,
    participant_par_dossard,
)

logger = logging.getLogger(__name__)
bp = Blueprint("contest", __name__, url_prefix="/api/v2/contest")


def _echec(message: str, code: int = 400):
    return jsonify({"success": False, "message": message}), code


def _corps() -> dict:
    """Le corps JSON, garanti dictionnaire.

    `get_json(silent=True)` rend fidelement ce que contient la requete : un
    objet, mais aussi bien une LISTE, une chaine ou un nombre. Le motif
    `get_json(...) or {}` ne rattrape que le corps vide -- une liste passe au
    travers, et le `.get` qui suit levait une AttributeError. La route repondait
    alors 500, ce qu'un juge ne peut pas distinguer d'une vraie panne serveur.

    On repond 400 « Missing data » : le corps ne porte effectivement pas ce
    qu'on attend.
    """
    corps = request.get_json(silent=True)
    return corps if isinstance(corps, dict) else {}


@bp.post("/climber/name")
@exige_cle_api
def verifier_grimpeur():
    """{"id": "<dossard>"} -> 201 {"success": true, "id": "<nom>"}"""
    data = _corps()
    dossard = data.get("id")
    if not dossard:
        return _echec("Missing data")
    try:
        p = participant_par_dossard(dossard)
    except ErreurMetier as e:
        return _echec(e.message, e.code)
    # La cle est "id" et vaut le NOM : c'est ce que l'application affiche.
    return jsonify({"success": True,
                    "message": "Climber registered successfully",
                    "id": p.nom_complet}), 201


@bp.post("/bloc/name")
@exige_cle_api
def verifier_bloc():
    """{"id": "<tag>"} -> 201 {"success": true, "id": "<tag>"}"""
    data = _corps()
    tag = data.get("id")
    if not tag:
        return _echec("Missing data")
    try:
        b = bloc_par_tag(tag)
    except ErreurMetier as e:
        return _echec(e.message, e.code)
    return jsonify({"success": True,
                    "message": "Bloc registered successfully",
                    "id": b.tag}), 201


@bp.post("/success")
@exige_cle_api
def enregistrer():
    """{"bib": "<dossard>", "bloc": "<tag>"} -> 201 {"success": true}

    Idempotent : un second envoi du meme couple renvoie 201 sans creer de
    seconde reussite. L'application ne doit JAMAIS voir d'erreur sur un double
    appui -- le juge croirait que ca n'a pas marche et recommencerait.
    """
    data = _corps()
    dossard, tag = data.get("bib"), data.get("bloc")
    if not (dossard and tag):
        return _echec("Missing data")

    try:
        participant = participant_par_dossard(dossard)
        bloc = bloc_par_tag(tag)
        _, nouvelle = enregistrer_reussite(participant, bloc)
    except ErreurMetier as e:
        return _echec(e.message, e.code)
    except Exception:
        logger.exception("echec d'enregistrement de reussite")
        return _echec("An error occurred", 500)

    if nouvelle:
        logger.info("reussite %s (dossard %s) sur %s",
                    participant.nom_complet, participant.dossard, bloc.tag)
    else:
        logger.info("reussite deja connue %s sur %s -- ignoree",
                    participant.dossard, bloc.tag)

    return jsonify({"success": True, "message": "Well done"}), 201
