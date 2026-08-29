"""Sessions de la console d'administration, et controle d'acces.

FAIL CLOSED, sans exception. Le defaut est de refuser : session absente,
illisible, expiree, utilisateur desactive ou supprime entre-temps, role
inconnu -- tout donne 401. Il n'existe aucune branche « on laisse passer en
cas de doute ».

C'est la lecon directe du 28/08. `@exige_cle_api` a un mode TOLERE qui laisse
passer une requete sans cle -- parfaitement justifie pour les trois routes de
l'application v3.1.4 du Play Store, qui n'en envoie aucune. Mais cette
tolerance avait contamine la console d'administration, et
`GET /admin/import/rapport` repondait 200 depuis Internet.

Ce module n'a pas de mode tolere. Il ne peut pas en avoir.
"""
import functools
import logging
from datetime import datetime, timedelta

from flask import current_app, g, jsonify, request, session

from .comptes import ADMIN
from .extensions import db
from .models import Utilisateur

logger = logging.getLogger(__name__)

CLE_SESSION = "utilisateur_id"
CLE_OUVERTURE = "ouverte_le"

# Une competition dure une journee. Plus court obligerait a se reconnecter en
# plein rush ; plus long laisserait une session ouverte sur l'ordinateur de la
# salle jusqu'a l'edition suivante.
DUREE_SESSION = timedelta(hours=12)

# Valeur par defaut de SECRET_KEY. Avec elle, n'importe qui peut fabriquer un
# cookie de session valide : la signature n'est plus un secret.
SECRET_DE_DEV = "dev-non-secret"


def ouvrir(utilisateur: Utilisateur) -> None:
    session.clear()
    session[CLE_SESSION] = utilisateur.id
    session[CLE_OUVERTURE] = datetime.now().isoformat()
    session.permanent = False


def fermer() -> None:
    session.clear()


def utilisateur_courant() -> Utilisateur | None:
    """L'utilisateur de la session, ou None. Verifie TOUT a chaque appel."""
    identifiant = session.get(CLE_SESSION)
    if identifiant is None:
        return None

    ouverte = session.get(CLE_OUVERTURE)
    if not ouverte:
        return None
    try:
        depuis = datetime.fromisoformat(ouverte)
    except (ValueError, TypeError):
        return None
    if datetime.now() - depuis > DUREE_SESSION:
        return None

    # Relu en base a CHAQUE requete, jamais porte par le cookie : un compte
    # desactive pendant la competition doit perdre l'acces tout de suite, pas
    # a l'expiration de sa session.
    u = db_utilisateur(identifiant)
    if u is None or not u.actif:
        return None
    return u


def db_utilisateur(identifiant):
    # `Session.get` et non `Query.get`, qui est deprecie depuis SQLAlchemy 2.0.
    return db.session.get(Utilisateur, identifiant)


def _refuser(message: str, code: int):
    logger.warning("admin refuse (%s) depuis %s sur %s",
                   message, request.remote_addr, request.path)
    return jsonify({"success": False, "message": message}), code


def exige_role(*roles: str):
    """Exige une session valide, et l'un de ces roles. `admin` les a tous.

    Sans role, exige seulement d'etre connecte.
    """

    def decorateur(vue):
        @functools.wraps(vue)
        def enveloppe(*args, **kwargs):
            if current_app.config.get("SECRET_KEY") == SECRET_DE_DEV:
                # Mieux vaut une console indisponible qu'une console ouverte :
                # avec la cle de developpement, un cookie se forge en trois
                # lignes. On refuse de servir plutot que de faire semblant.
                return _refuser(
                    "Administration desactivee : SECRET_KEY n'a pas ete definie.", 503)

            u = utilisateur_courant()
            if u is None:
                return _refuser("Authentification requise", 401)

            if roles and not (u.a_le_role(ADMIN) or any(u.a_le_role(r) for r in roles)):
                return _refuser(
                    f"Role insuffisant ({u.identifiant})", 403)

            g.utilisateur = u
            return vue(*args, **kwargs)

        return enveloppe

    return decorateur
