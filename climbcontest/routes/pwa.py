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

from urllib.parse import quote

from flask import (
    Blueprint, current_app, make_response, render_template, request,
    send_from_directory,
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
    # Le lien vers le manifeste porte le jeton (spec 014) : c'est CE
    # manifeste-la que le navigateur lit au moment ou il propose d'installer,
    # et c'est de la que l'application installee tirera son `start_url`.
    reponse = make_response(render_template(
        "juge.html", suffixe_manifeste=_suffixe(_jeton_demande())))
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
    """Le manifeste, RENDU et non servi tel quel (spec 014).

    Son `start_url` porte le jeton quand la page qui le lie en avait un. C'est
    la piece qui corrige le defaut constate a l'installation : sans jeton dans
    `start_url`, l'application lancee depuis son icone ouvre `/juge` nu et ne
    peut retrouver sa cle que dans son stockage local -- lequel est cloisonne
    sur iPhone, donc vide.

    ⚠️ Le jeton n'est JAMAIS ecrit dans un fichier du depot : il arrive par la
    requete et ressort dans la reponse. Les deux depots sont publics, la regle
    « aucun secret committe » reste entiere.

    Sans `?j=`, la reponse est exactement le manifeste d'avant. Il doit rester
    valide et servable seul : un visiteur de passage, un robot d'indexation ou
    un navigateur qui le demande sans contexte ne doivent rien voir d'anormal.
    """
    reponse = make_response(render_template("manifest.webmanifest",
                                            depart=_depart(_jeton_demande())))
    reponse.headers["Content-Type"] = "application/manifest+json"
    return reponse


def _jeton_demande() -> str:
    return (request.args.get("j") or "").strip()


def _depart(jeton: str) -> str:
    """`start_url` : avec le jeton s'il y en a un, sinon la valeur d'origine."""
    return f"/juge?j={quote(jeton, safe='')}" if jeton else "/juge"


def _suffixe(jeton: str) -> str:
    """Ce qu'on accroche a l'adresse du manifeste pour lui transmettre le jeton."""
    return f"?j={quote(jeton, safe='')}" if jeton else ""


def _dossier() -> str:
    return str(current_app.root_path) + "/static/juge"
