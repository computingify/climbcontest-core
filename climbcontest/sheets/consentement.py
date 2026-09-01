"""Le consentement Google, depuis la console — spec 022.

Poser un jeton demandait jusqu'ici cinq gestes, dont deux en ligne de commande :
retrouver un Mac où `token.pickle` existe, y créer un environnement Python avec
`google-auth`, lancer `tools/exporter_jeton.py`, copier une ligne de JSON qui
contient un `refresh_token` — un secret au même titre qu'un mot de passe — et la
coller dans la console. Cinq gestes pour un écran dont toute la raison d'être
est justement de **remplacer le SSH**. Et aucun de ces gestes ne produit un
jeton neuf : ils recopient celui qui existait déjà.

`parametrage.py` disait en tête : « ce qui n'est pas ici : le consentement OAuth
(il demande un navigateur) ». C'était vrai de la ligne de commande. La console,
elle, **est** un navigateur.

**Aucune écriture disque ici** : `echanger()` rend une chaîne, la route appelle
`client.ecrire_jeton_json()`. La séparation permet de tester l'échange sans
toucher au disque, et de n'avoir qu'un seul endroit qui écrit un jeton.
"""

import json
import logging
import secrets

from ..contest import ErreurMetier
from .client import chemin_credentials, etat_credentials

logger = logging.getLogger(__name__)

# Lire et écrire une feuille partagée, et rien de plus. **Pas de scope Drive** :
# le jeton n'a jamais eu à lister ni supprimer des fichiers, et supprimer les
# classeurs jetables reste un geste manuel (voir docs/technical/classeur-google.md).
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# La clé sous laquelle le `state` voyage dans la session Flask.
CLE_ETAT = "google_state"


def disponible() -> dict:
    """`credentials.json` est-il là ? Ne lève jamais — voir `etat_credentials`."""
    return etat_credentials()


def _flux(uri_retour: str):
    """Le `Flow` de `google-auth-oauthlib`, monté sur notre credentials.json.

    Importé ici et non en tête de module : `google_auth_oauthlib` tire
    `requests` et `oauthlib`, et la console doit pouvoir afficher « aucun
    credentials.json » sans que rien de tout ça soit chargé.
    """
    from google_auth_oauthlib.flow import Flow

    etat = etat_credentials()
    if not etat["pret"]:
        raise ErreurMetier(etat["message"], code=409)

    flux = Flow.from_client_secrets_file(str(chemin_credentials()), scopes=SCOPES)
    flux.redirect_uri = uri_retour
    return flux


def url_de_consentement(uri_retour: str) -> tuple[str, str]:
    """`(url Google, state)`. Le `state` est à ranger en session par l'appelant.

    ⚠️ `prompt="consent"` n'est pas une politesse. Sans lui, Google **ne redonne
    pas de `refresh_token`** à un compte qui a déjà consenti une fois : on
    reposerait un jeton qui meurt dans l'heure, et la panne se découvrirait le
    lendemain matin. C'est le piège classique de ce flux, et il est silencieux.

    `access_type="offline"` demande le rafraîchissement ; `include_granted_scopes`
    évite de faire perdre à l'utilisateur les autorisations déjà données.
    """
    flux = _flux(uri_retour)
    etat = secrets.token_urlsafe(32)
    url, _ = flux.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=etat,
    )
    return url, etat


def echanger(code: str, uri_retour: str) -> str:
    """Le code d'autorisation contre un jeton. Rend le JSON, n'écrit rien.

    Refuse un jeton **sans `refresh_token`** : la même garde que
    `parametrage.poser_jeton`, pour la même raison — sans lui, le jeton meurt à
    la première expiration.
    """
    if not (code or "").strip():
        raise ErreurMetier("Google n'a pas renvoye de code d'autorisation.")

    flux = _flux(uri_retour)
    try:
        flux.fetch_token(code=code)
    except Exception as e:                                   # noqa: BLE001
        # Le message de Google est parfois bavard et contient l'URI complète.
        # On le journalise, on n'en renvoie que la nature.
        logger.warning("echange du code Google refuse : %s", e)
        raise ErreurMetier(
            "Google a refuse l'echange du code. Recommence le consentement.",
            code=502,
        ) from e

    contenu = flux.credentials.to_json()
    try:
        pose = json.loads(contenu)
    except ValueError as e:                                  # pragma: no cover
        raise ErreurMetier("Jeton illisible rendu par Google.", code=502) from e

    if not pose.get("refresh_token"):
        raise ErreurMetier(
            "Le consentement n'a pas donne de jeton durable (pas de "
            "refresh_token) : il mourrait a la premiere expiration. "
            "Recommence — et si ca se reproduit, retire l'acces de "
            "l'application dans le compte Google avant de reessayer.",
            code=502,
        )
    return contenu


def verifier_etat(attendu: str | None, recu: str | None) -> None:
    """Le garde-fou CSRF du retour. Comparaison à temps constant.

    Sans lui, n'importe quel site pourrait faire aboutir chez nous un code
    d'autorisation obtenu ailleurs, et poser SON compte Google comme identité du
    serveur.
    """
    if not attendu or not recu or not secrets.compare_digest(attendu, recu):
        raise ErreurMetier(
            "Retour Google non reconnu (jeton d'etat absent ou different). "
            "Rien n'a ete pose. Relance le consentement depuis la console.")
