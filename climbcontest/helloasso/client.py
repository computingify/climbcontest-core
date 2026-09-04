"""Parler à l'API HelloAsso — spec 008.

## Le jeton vit en base, et un seul processus le rafraîchit

C'est la contrainte la plus dure du fournisseur, et elle est écrite noir sur
blanc dans sa documentation :

> Lorsqu'un refresh token A est utilisé, un nouveau refresh token B est renvoyé.
> Si une nouvelle utilisation du refresh token A est faite, alors un nouveau
> refresh_token C est créé et **B est révoqué**.

Avec quatre workers gunicorn et un jeton gardé en mémoire vive, deux
rafraîchissements simultanés **se révoquent l'un l'autre**. Le symptôme serait
le pire qui soit : ça marche en développement — un seul processus — et ça tombe
en production au bout de trente minutes, un jour de compétition, sans qu'aucun
test ne l'ait vu.

D'où trois décisions :

1. le couple `access_token` / `refresh_token` est **lu et écrit en base**, dans
   la table `reglage` ;
2. le rafraîchissement prend le verrou `helloasso_jeton` de la table `verrou` —
   celui-là même que le miroir vers le classeur utilise déjà ;
3. celui qui n'obtient pas le verrou **relit** la base : le voisin vient
   probablement d'y déposer un jeton frais.

Coût : **2 appels d'authentification par heure**, sur les 50 que HelloAsso
autorise (10 par 10 s, 20 par 10 min, 50 par heure).

## Le secret ne vit pas en base

`client_id` et `client_secret` vont dans `shared/secrets/helloasso.json`, hors
du dépôt et hors des releases — exactement comme le jeton Google. Conséquence
assumée, et la même que pour Google : une restauration de sauvegarde ne les
ramène pas, il faut les reposer. C'est le prix pour qu'un secret ne se promène
jamais dans un dump de base.

Le secret n'est **jamais** renvoyé par une route, **jamais** journalisé,
**jamais** réaffiché. `etat()` ne rend que les quatre derniers caractères de
l'identifiant, ce qui suffit à reconnaître une clé sans permettre de s'en
servir.
"""

import json
import logging
import os
import socket
import threading
from datetime import datetime, timedelta
from pathlib import Path

import requests
from sqlalchemy import text

from ..extensions import db
from ..models import Reglage

logger = logging.getLogger(__name__)

FICHIER_SECRET = "helloasso.json"
CLE_JETON = "helloasso_jeton"
VERROU_JETON = "helloasso_jeton"
VERROU_PERIME = timedelta(minutes=2)

PRODUCTION, BAC_A_SABLE = "production", "sandbox"

HOTES = {
    PRODUCTION: "https://api.helloasso.com",
    BAC_A_SABLE: "https://api.helloasso-sandbox.com",
}

#: L'access_token vit 1799 s. On le renouvelle avec deux minutes d'avance : un
#: relevé qui dure quelques secondes ne doit pas se faire couper au milieu.
MARGE_EXPIRATION = timedelta(minutes=2)

#: Au-delà, on n'attend plus le réseau. Le fil retentera au tour suivant ; ce
#: qu'on ne veut pas, c'est qu'un worker reste bloqué sur une socket muette.
DELAI_RESEAU = 20


class ErreurHelloAsso(Exception):
    """Erreur attendue, destinée à être montrée telle quelle dans la console.

    Volontairement distincte des erreurs métier : elle ne fait jamais échouer
    une requête de juge, elle retarde un relevé. Même rôle qu'`ErreurClasseur`.

    `reconnecter` distingue la panne passagère de la clé morte, et cette
    distinction commande un comportement, pas seulement un message : sur une
    clé morte le fil **s'arrête**. Insister brûlerait le quota
    d'authentification et rendrait la reconnexion impossible au moment où on en
    aurait besoin.
    """

    def __init__(self, message: str, code: int = 502, reconnecter: bool = False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.reconnecter = reconnecter


# --- Le secret ---------------------------------------------------------------

def _dossier_secrets() -> Path:
    from flask import current_app
    try:
        configure = current_app.config.get("DOSSIER_SECRETS")
        if configure:
            return Path(configure)
    except RuntimeError:
        pass                              # hors contexte Flask : outils du Mac
    if env := os.environ.get("CLIMBCONTEST_SECRETS_DIR"):
        return Path(env)
    return Path.cwd()


def _chemin_secret() -> Path:
    return _dossier_secrets() / FICHIER_SECRET


def lire_secret() -> dict | None:
    """La clé posée, ou None. Ne lève jamais : l'absence est un état normal."""
    try:
        contenu = json.loads(_chemin_secret().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(contenu, dict) or not contenu.get("client_id"):
        return None
    return contenu


def ecrire_secret(client_id: str, client_secret: str,
                  environnement: str = PRODUCTION) -> Path:
    """Pose la clé. Le fichier est écrit en 0600, comme le jeton Google."""
    if environnement not in HOTES:
        raise ErreurHelloAsso(f"Environnement inconnu : {environnement}", code=400)
    chemin = _chemin_secret()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({
        "client_id": (client_id or "").strip(),
        "client_secret": (client_secret or "").strip(),
        "environnement": environnement,
    }), encoding="utf-8")
    try:
        chemin.chmod(0o600)
    except OSError:
        pass                              # systeme de fichiers qui ne sait pas
    logger.info("cle HelloAsso posee (%s)", environnement)
    return chemin


def effacer_secret() -> None:
    """Débranche. Le fil s'arrêtera de lui-même au tour suivant."""
    try:
        _chemin_secret().unlink()
    except OSError:
        pass
    ligne = db.session.get(Reglage, CLE_JETON)
    if ligne:
        db.session.delete(ligne)
        db.session.commit()
    logger.info("cle HelloAsso retiree")


def configure() -> bool:
    return lire_secret() is not None


# --- Le jeton, en base -------------------------------------------------------

def _lire_jeton() -> dict:
    ligne = db.session.get(Reglage, CLE_JETON)
    if not ligne:
        return {}
    try:
        valeur = json.loads(ligne.valeur)
    except ValueError:
        return {}
    return valeur if isinstance(valeur, dict) else {}


def _ecrire_jeton(donnees: dict) -> None:
    ligne = db.session.get(Reglage, CLE_JETON)
    contenu = json.dumps(donnees)
    if ligne:
        ligne.valeur = contenu
    else:
        db.session.add(Reglage(cle=CLE_JETON, valeur=contenu))
    db.session.commit()


def _identite() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{threading.get_ident()}"


def _prendre_verrou() -> bool:
    """Le même verrou que le miroir, sur une autre ligne.

    Rend False si un autre l'a : l'appelant relit alors la base plutôt que de
    demander un second jeton — c'est tout l'objet de la manœuvre.
    """
    moi, maintenant = _identite(), datetime.now()
    limite = maintenant - VERROU_PERIME
    try:
        pris = db.session.execute(
            text("UPDATE verrou SET detenu_par = :moi, pris_le = :maintenant "
                 "WHERE nom = :nom AND (pris_le IS NULL OR pris_le < :limite)"),
            {"moi": moi, "maintenant": maintenant, "nom": VERROU_JETON,
             "limite": limite},
        ).rowcount
        if not pris:
            deja = db.session.execute(
                text("SELECT 1 FROM verrou WHERE nom = :n"), {"n": VERROU_JETON}
            ).first()
            if deja:
                db.session.rollback()
                return False
            db.session.execute(
                text("INSERT INTO verrou (nom, detenu_par, pris_le) "
                     "VALUES (:n, :d, :p)"),
                {"n": VERROU_JETON, "d": moi, "p": maintenant})
            pris = 1
        db.session.commit()
        return bool(pris)
    except Exception:
        db.session.rollback()
        return False


def _rendre_verrou() -> None:
    try:
        db.session.execute(
            text("UPDATE verrou SET pris_le = NULL WHERE nom = :n"),
            {"n": VERROU_JETON})
        db.session.commit()
    except Exception:
        db.session.rollback()


def _encore_valide(jeton: dict) -> bool:
    if not jeton.get("access_token") or not jeton.get("expire_le"):
        return False
    try:
        expire = datetime.fromisoformat(jeton["expire_le"])
    except ValueError:
        return False
    return datetime.now() + MARGE_EXPIRATION < expire


class ClientHelloAsso:
    """Lecture seule. Ce client n'écrit jamais chez HelloAsso, sans exception.

    Le back-office du club reste le seul endroit qui modifie quoi que ce soit :
    rembourser, annuler, changer un formulaire. Une intégration qui sait écrire
    est une intégration qui peut, un jour, écrire par erreur.
    """

    def __init__(self, secret: dict | None = None):
        self.secret = secret or lire_secret()
        if not self.secret:
            raise ErreurHelloAsso(
                "HelloAsso n'est pas relie. Poser la cle d'API depuis la console.",
                code=409)
        self.hote = HOTES.get(self.secret.get("environnement") or PRODUCTION,
                              HOTES[PRODUCTION])

    # --- authentification ---------------------------------------------------

    def _demander_jeton(self, corps: dict) -> dict:
        try:
            reponse = requests.post(
                f"{self.hote}/oauth2/token", data=corps,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=DELAI_RESEAU)
        except requests.RequestException as e:
            raise ErreurHelloAsso(f"HelloAsso injoignable : {e}") from e

        if reponse.status_code in (400, 401, 403):
            # Un refus d'authentification n'est pas une panne passagere : la
            # cle est morte, ou le refresh_token a plus de trente jours.
            raise ErreurHelloAsso(
                "Cle HelloAsso refusee. La reconnecter depuis la console.",
                code=401, reconnecter=True)
        if reponse.status_code != 200:
            raise ErreurHelloAsso(
                f"HelloAsso a repondu {reponse.status_code} a la demande de jeton")

        donnees = reponse.json()
        duree = int(donnees.get("expires_in") or 1799)
        return {
            "access_token": donnees.get("access_token"),
            "refresh_token": donnees.get("refresh_token"),
            "expire_le": (datetime.now() + timedelta(seconds=duree)).isoformat(),
        }

    def jeton(self) -> str:
        """Un access_token valide. Ne fait un appel réseau que s'il le faut."""
        actuel = _lire_jeton()
        if _encore_valide(actuel):
            return actuel["access_token"]

        if not _prendre_verrou():
            # Un autre processus rafraichit. On relit : il vient probablement
            # d'ecrire. Sinon on echoue proprement -- le tour suivant reessaiera,
            # ce qui vaut mieux que de demander un second jeton et de revoquer
            # celui du voisin.
            db.session.expire_all()
            actuel = _lire_jeton()
            if _encore_valide(actuel):
                return actuel["access_token"]
            raise ErreurHelloAsso(
                "Jeton HelloAsso en cours de renouvellement. Reessayer.", code=503)

        try:
            # Relire APRES avoir pris le verrou : entre le premier controle et
            # le verrou, le voisin a pu finir. Sans cette seconde lecture, deux
            # workers qui arrivent ensemble font deux rafraichissements a la
            # suite -- et le second revoque le premier.
            db.session.expire_all()
            actuel = _lire_jeton()
            if _encore_valide(actuel):
                return actuel["access_token"]

            if actuel.get("refresh_token"):
                nouveau = self._demander_jeton({
                    "grant_type": "refresh_token",
                    "refresh_token": actuel["refresh_token"]})
            else:
                nouveau = self._demander_jeton({
                    "grant_type": "client_credentials",
                    "client_id": self.secret["client_id"],
                    "client_secret": self.secret["client_secret"]})
            _ecrire_jeton(nouveau)
            logger.info("jeton HelloAsso renouvele")
            return nouveau["access_token"]
        finally:
            _rendre_verrou()

    # --- appels -------------------------------------------------------------

    def _get(self, chemin: str, params: dict | None = None, reessai: bool = True):
        entetes = {"Authorization": f"Bearer {self.jeton()}"}
        try:
            reponse = requests.get(f"{self.hote}/v5{chemin}", params=params or {},
                                   headers=entetes, timeout=DELAI_RESEAU)
        except requests.RequestException as e:
            raise ErreurHelloAsso(f"HelloAsso injoignable : {e}") from e

        if reponse.status_code == 401 and reessai:
            # Le jeton a expire entre la lecture et l'appel. UN seul reessai :
            # boucler ici sur une cle morte brulerait le quota.
            _ecrire_jeton({**_lire_jeton(), "expire_le": ""})
            return self._get(chemin, params, reessai=False)
        if reponse.status_code in (401, 403):
            raise ErreurHelloAsso(
                "Cle HelloAsso refusee. La reconnecter depuis la console.",
                code=401, reconnecter=True)
        if reponse.status_code == 429:
            raise ErreurHelloAsso("HelloAsso limite les appels. On retentera.")
        if reponse.status_code >= 400:
            raise ErreurHelloAsso(
                f"HelloAsso a repondu {reponse.status_code} sur {chemin}")
        return reponse.json()

    def organisation(self, slug: str) -> dict:
        return self._get(f"/organizations/{slug}")

    def formulaires(self, slug: str) -> list[dict]:
        """Les formulaires du club, pour en choisir un dans la console."""
        page = self._get(f"/organizations/{slug}/forms",
                         {"pageSize": 100, "states": "Public"})
        return page.get("data") or []

    def formulaire(self, slug: str, type_de_formulaire: str,
                   slug_formulaire: str) -> dict:
        return self._get(
            f"/organizations/{slug}/forms/{type_de_formulaire}/"
            f"{slug_formulaire}/public")

    def articles(self, slug: str, type_de_formulaire: str, slug_formulaire: str,
                 depuis: datetime | None = None):
        """Les articles vendus, page par page. **Un article = un inscrit.**

        Générateur : les articles sortent au fil de l'eau et la totalité n'est
        jamais en mémoire. Une coupure ne perd que la page en cours.

        Trois paramètres, trois raisons :

        - `sortField=UpdateDate` et non `Date` : une commande modifiée après
          coup — une annulation, une correction de nom — garde sa date de
          création. Trier par création la rendrait invisible pour toujours ;
        - `from` avec un recouvrement de cinq minutes : les horloges des deux
          côtés ne sont pas les mêmes, et un article pile à la seconde de la
          borne serait perdu. Le recouvrement ne coûte rien, la contrainte
          d'unicité absorbe ;
        - `withDetails=true` : sans lui, pas de `customFields`, donc ni année
          de naissance, ni genre, ni club — la moitié de l'information.
        """
        params = {
            "pageSize": 100,
            "withDetails": "true",
            "sortField": "UpdateDate",
            "sortOrder": "Asc",
        }
        if depuis:
            params["from"] = (depuis - timedelta(minutes=5)).isoformat()

        chemin = (f"/organizations/{slug}/forms/{type_de_formulaire}/"
                  f"{slug_formulaire}/items")
        jeton_suite = None
        while True:
            appel = dict(params)
            if jeton_suite:
                appel["continuationToken"] = jeton_suite
            page = self._get(chemin, appel)

            articles = page.get("data") or []
            # ⚠️ LE SIGNAL DE FIN EST LE TABLEAU VIDE, pas l'absence de jeton.
            # Leur documentation est explicite : un `continuationToken` peut
            # etre renvoye alors qu'il n'y a plus rien. S'arreter sur son
            # absence ferait boucler.
            if not articles:
                return
            yield from articles

            jeton_suite = (page.get("pagination") or {}).get("continuationToken")
            if not jeton_suite:
                return                    # ceinture apres la bretelle


def etat() -> dict:
    """Ce que la console affiche. **Jamais le secret.**

    Seuls les quatre derniers caracteres de l'identifiant sortent : de quoi
    reconnaitre une cle sans permettre de s'en servir.
    """
    secret = lire_secret()
    if not secret:
        return {"configure": False}
    identifiant = secret.get("client_id") or ""
    jeton = _lire_jeton()
    return {
        "configure": True,
        "environnement": secret.get("environnement") or PRODUCTION,
        "cle": f"…{identifiant[-4:]}" if len(identifiant) > 4 else "…",
        "jeton_valide": _encore_valide(jeton),
    }
