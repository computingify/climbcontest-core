"""L'application juge en version web, installable sur un iPhone (spec 007).

Un benevole qui arrive avec un iPhone ne peut pas juger : l'application est
Android, et l'App Store coute 99 $/an. Cette PWA leve la contrainte sans rien
payer, sans compte developpeur et sans delai de publication.

⚠️ **Tout ce qui est servi ici est PUBLIC**, et doit le rester :

- une coquille HTML et du JavaScript ne contiennent aucun secret ;
- un service worker ne s'installe pas depuis une page protegee par un cookie ;
- le manifeste doit etre lisible par le navigateur avant toute interaction.

Ce qui est garde, c'est l'**API**. Le jeton qui l'ouvre arrive par le lien qu'on
donne aux benevoles, et n'est jamais ecrit dans ces fichiers.
"""
import logging

from flask import (
    Blueprint, current_app, make_response, render_template, send_from_directory,
)

logger = logging.getLogger(__name__)
bp = Blueprint("pwa", __name__, url_prefix="/juge")


@bp.get("")
@bp.get("/")
def application():
    """La coquille. Aucune donnee, aucun secret : tout arrive par l'API.

    ⚠️ **Servie sans cache**, et ce n'est pas un detail. Constate en developpant :
    le navigateur gardait la page precedente et ignorait les modifications. En
    production, ca voudrait dire publier un correctif et voir vingt-cinq
    telephones continuer de tourner sur l'ancienne version -- sans que personne
    ne comprenne pourquoi le correctif « ne marche pas ».

    Le cout est nul : la coquille fait quelques kilo-octets, et c'est le service
    worker (IT4) qui prendra en charge le fonctionnement hors ligne, avec une
    strategie explicite plutot qu'un cache navigateur qu'on ne controle pas.
    """
    reponse = make_response(render_template("juge.html"))
    reponse.headers["Cache-Control"] = "no-cache, must-revalidate"
    return reponse


@bp.get("/sw.js")
def service_worker():
    """Le service worker, servi depuis /juge/ et NON depuis /static/.

    Sa PORTEE est le dossier d'ou il est servi. Depuis `/static/juge/sw.js`, il
    ne pourrait controler que `/static/juge/` -- donc pas `/juge`, donc pas
    l'application. C'est la seule raison de cette route.

    Servi sans cache : un service worker mis en cache est un service worker
    qu'on ne peut plus corriger.

    ⚠️ **`Service-Worker-Allowed` n'est pas optionnel ici.** Par defaut, un
    script servi depuis `/juge/` ne peut controler que `/juge/` -- avec la barre
    finale. Or l'application vit a `/juge`, SANS barre, qui n'est pas sous
    `/juge/`. Le navigateur refuse alors l'enregistrement, avec un message que
    seul un essai reel fait apparaitre :

        The path of the provided scope ('/juge') is not under the max scope
        allowed ('/juge/').

    Cet en-tete elargit la portee autorisee a `/juge`, ce qui couvre
    l'application ET ses fichiers. Sans lui, la PWA s'installe mais ne
    fonctionne jamais hors ligne -- et rien ne le dit.
    """
    reponse = send_from_directory(_dossier(), "sw.js", mimetype="text/javascript")
    reponse.headers["Cache-Control"] = "no-cache, must-revalidate"
    reponse.headers["Service-Worker-Allowed"] = "/juge"
    return reponse


@bp.get("/manifest.webmanifest")
def manifeste():
    return send_from_directory(_dossier(), "manifest.webmanifest",
                               mimetype="application/manifest+json")


def _dossier() -> str:
    return str(current_app.root_path) + "/static/juge"
