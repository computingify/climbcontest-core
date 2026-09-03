"""Mise à jour du serveur, déclenchée depuis la console (spec 031).

Ce module remplace `climbcontest-deploy.timer`, retiré le 2026-09-03. Le
minuteur interrogeait `api.github.com` toutes les deux minutes — 30 requêtes par
heure sur un quota **anonyme de 60 par heure et par adresse IP publique**,
partagée par toute la maison. Cinq déploiements avaient déjà échoué le 30/08
pour dépassement, et l'échec ne se voyait que dans le journal.

Ici : **une vérification par jour**, au plus, et déclenchée par la console
elle-même. Personne n'ouvre la console, personne ne consomme le quota.

Ce module ne déploie pas. Il décide, et il délègue à
`climbcontest-deploy.service` — le script `/usr/local/bin/climbcontest-deploy`
reste le seul code qui installe, avec son verrou, sa sonde `/health` et son
retour arrière vérifié.
"""
import json
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from .extensions import db
from .models import EN_COURS, Competition, Reglage

logger = logging.getLogger(__name__)

DEPOT = "computingify/climbcontest-core"
CLE_VERIFICATION = "maj_verification"
CLE_INSTALLATION = "maj_installation"

# Une fois par jour. Le quota anonyme se recharge par heure glissante : une
# requête toutes les 24 h en consomme 1 sur 60, contre 30 pour l'ancien minuteur.
DELAI_VERIFICATION = timedelta(hours=24)

# L'installation est asynchrone : on rend la main tout de suite et le service
# redémarre l'application quelques secondes plus tard. Au-delà de ce délai sans
# nouvelle, on cesse d'annoncer « en cours » — le script a un verrou et une
# sonde, il ne peut pas rester suspendu indéfiniment sans que ce soit une panne.
DELAI_INSTALLATION = timedelta(minutes=10)


class ErreurMaj(Exception):
    """Refus explicite, destiné à être montré tel quel dans la console."""

    def __init__(self, message: str, code: int = 409):
        super().__init__(message)
        self.message = message
        self.code = code


# --- Où vivent les fichiers de l'agent de déploiement ------------------------
#
# `/opt/climbcontest/current` est un lien vers `releases/<tag>` : la racine du
# code est donc DANS le dossier des releases, et la base de l'installation deux
# crans au-dessus. En développement, rien de tout ça n'existe et les lectures
# renvoient None — la console affiche alors « version de développement » plutôt
# que de tomber.
def _base() -> Path | None:
    force = os.environ.get("CLIMBCONTEST_BASE")
    if force:
        return Path(force)
    racine = Path(__file__).resolve().parent.parent
    if racine.parent.name == "releases":
        return racine.parent.parent
    return None


def _lire(nom: str) -> str | None:
    base = _base()
    if not base:
        return None
    try:
        return (base / nom).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _jeton() -> str | None:
    """Jeton GitHub à portée lecture, s'il a été posé.

    Sans lui, le quota est de 60 requêtes par heure et par adresse IP — partagé
    avec tout ce qui sort de la maison. Avec, il passe à 5 000. Le script de
    déploiement lit le même fichier.
    """
    base = _base()
    if not base:
        return None
    try:
        return (base / "shared/secrets/github-token").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


# --- L'état stocké -----------------------------------------------------------
#
# Deux clés dans `reglage`, et non deux fichiers : `climbcontest-sauvegarde` ne
# recopie que la base. C'est le raisonnement déjà écrit sur le modèle Reglage.


def _charger(cle: str) -> dict:
    ligne = db.session.get(Reglage, cle)
    if not ligne:
        return {}
    try:
        return json.loads(ligne.valeur)
    except (TypeError, ValueError):
        return {}


def _ecrire(cle: str, contenu: dict, par: str | None = None) -> None:
    ligne = db.session.get(Reglage, cle)
    if ligne:
        ligne.valeur = json.dumps(contenu)
        ligne.modifie_par = par
    else:
        db.session.add(Reglage(cle=cle, valeur=json.dumps(contenu), modifie_par=par))
    db.session.commit()


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _depuis(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


# --- La vérification ---------------------------------------------------------


def _interroger_github() -> dict:
    entetes = {"Accept": "application/vnd.github+json"}
    jeton = _jeton()
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    reponse = requests.get(
        f"https://api.github.com/repos/{DEPOT}/releases/latest",
        headers=entetes, timeout=15,
    )
    # 403 avec le compteur à zéro, c'est le quota — pas un droit manquant. Le
    # dire précisément est tout l'intérêt : c'est cette panne-là qui passait
    # inaperçue avec le minuteur.
    if reponse.status_code == 403 and reponse.headers.get("x-ratelimit-remaining") == "0":
        raise ErreurMaj("GitHub injoignable — quota atteint.")
    if reponse.status_code == 404:
        raise ErreurMaj("Aucune release publiée sur le dépôt.")
    reponse.raise_for_status()
    corps = reponse.json()
    return {
        "tag": corps.get("tag_name") or "",
        # Le corps de la release EST la section du CHANGELOG : le workflow de
        # release échoue s'il ne la trouve pas (scripts/extract_changelog.py).
        # Il n'y a donc rien à reconstituer ici.
        "changelog": corps.get("body") or "",
        "publiee_le": corps.get("published_at") or "",
    }


def verifier(force: bool = False) -> dict:
    """Interroge GitHub si c'est dû, et range le résultat.

    Renvoie la vérification stockée, qu'elle vienne d'être faite ou non.
    """
    stockee = _charger(CLE_VERIFICATION)
    fait_le = _depuis(stockee.get("fait_le"))
    du = force or not fait_le or datetime.now(timezone.utc) - fait_le >= DELAI_VERIFICATION
    if not du:
        return stockee

    # ⚠️ On horodate AVANT d'appeler GitHub, pas après. Quatre workers gunicorn
    # peuvent voir « c'est dû » à la même seconde, au premier chargement de la
    # console du matin ; celui qui passe en premier ferme la porte aux autres.
    # Il reste une fenêtre de quelques centaines de millisecondes où deux
    # requêtes partent — 2 sur 60 au lieu de 1, une fois par jour. On s'en
    # contente : un verrou à deux états aurait un mode d'échec silencieux où
    # plus AUCUNE vérification ne se ferait, ce qui est bien pire.
    _ecrire(CLE_VERIFICATION, {**stockee, "fait_le": _maintenant()})

    resultat = {"fait_le": _maintenant()}
    try:
        resultat.update(_interroger_github())
    except ErreurMaj as e:
        resultat["erreur"] = e.message
        # On garde ce qu'on savait : une version disponible hier l'est toujours
        # aujourd'hui, même si GitHub ne répond pas ce matin.
        for champ in ("tag", "changelog", "publiee_le"):
            if stockee.get(champ):
                resultat[champ] = stockee[champ]
    except requests.RequestException as e:
        logger.warning("verification de version : %s", e)
        resultat["erreur"] = "GitHub injoignable."
        for champ in ("tag", "changelog", "publiee_le"):
            if stockee.get(champ):
                resultat[champ] = stockee[champ]
    _ecrire(CLE_VERIFICATION, resultat)
    return resultat


# --- Ce que la console affiche ----------------------------------------------


def _blocage() -> str | None:
    """Pourquoi l'installation est refusée, ou None.

    Une compétition en cours bloque, et ce n'est pas négociable : redémarrer
    coupe vingt-cinq téléphones au milieu des scans. Le geste de secours reste
    la ligne de commande, où l'on sait ce qu'on fait.
    """
    comp = Competition.query.filter_by(active=True).first()
    if comp and comp.statut == EN_COURS:
        return f"Compétition en cours ({comp.nom}) — installation bloquée."
    return None


def etat(version_en_service: str) -> dict:
    """L'état complet, tel que la console le lit. Vérifie si c'est dû."""
    verification = verifier()
    tag = verification.get("tag") or ""
    disponible = bool(tag) and tag != version_en_service

    reponse = {
        "en_service": version_en_service,
        "verifie_le": verification.get("fait_le"),
        "erreur": verification.get("erreur"),
        "disponible": {
            "tag": tag,
            "publiee_le": verification.get("publiee_le"),
            "changelog": verification.get("changelog") or "",
        } if disponible else None,
        "blocage": _blocage() if disponible else None,
        "installation": _installation_en_cours(version_en_service),
    }
    return reponse


def _installation_en_cours(version_en_service: str) -> dict | None:
    """Où en est l'installation demandée depuis la console, s'il y en a eu une.

    Rien n'est stocké sur son issue : elle se LIT. `VERSION` dit ce qui tourne
    vraiment, `.failed-tag` ce que l'agent a refusé après sa sonde. Un état
    recopié à la main mentirait le jour où le processus est tué entre les deux.
    """
    demande = _charger(CLE_INSTALLATION)
    vise = demande.get("tag")
    demandee_le = _depuis(demande.get("demandee_le"))
    if not vise or not demandee_le:
        return None

    # ⚠️ L'issue n'est annoncée que le temps qu'on vienne la lire. Sans cette
    # borne, « v0.17.0 installée » resterait à l'écran des semaines après coup,
    # à côté d'une carte qui dit déjà « version à jour ». Passé le délai,
    # l'information est dans la version en service — elle n'a plus à être
    # répétée.
    if datetime.now(timezone.utc) - demandee_le >= DELAI_INSTALLATION:
        return None

    if vise == version_en_service:
        return {"tag": vise, "etat": "reussie"}
    if _lire(".failed-tag") == vise:
        return {"tag": vise, "etat": "echouee", "revenu_en": version_en_service}
    return {"tag": vise, "etat": "en_cours"}


# --- L'installation ----------------------------------------------------------


def installer(tag: str, par: str | None = None) -> dict:
    """Démarre `climbcontest-deploy.service` et rend la main immédiatement.

    ⚠️ `--no-block`, et ce n'est pas un détail : l'agent de déploiement
    **redémarre l'application**, c'est-à-dire le processus qui traite cette
    requête. Attendre la fin du service, ce serait attendre sa propre mort — la
    console n'aurait jamais de réponse et afficherait une erreur sur un
    déploiement parti correctement.
    """
    blocage = _blocage()
    if blocage:
        raise ErreurMaj(blocage)

    verification = _charger(CLE_VERIFICATION)
    if not verification.get("tag"):
        raise ErreurMaj("Aucune version connue. Vérifier d'abord.")
    if tag and tag != verification["tag"]:
        # La console a été chargée avant une nouvelle publication : on refuse
        # plutôt que d'installer autre chose que ce qui était affiché.
        raise ErreurMaj("La version affichée n'est plus la dernière. Vérifier à nouveau.")

    _ecrire(CLE_INSTALLATION,
            {"tag": verification["tag"], "demandee_le": _maintenant()}, par=par)
    logger.info("installation de %s demandee par %s", verification["tag"], par or "?")

    try:
        subprocess.run(
            ["sudo", "-n", "/bin/systemctl", "start", "--no-block",
             "climbcontest-deploy.service"],
            check=True, capture_output=True, timeout=20,
        )
    except (subprocess.SubprocessError, OSError) as e:
        detail = getattr(e, "stderr", b"") or b""
        logger.error("demarrage de climbcontest-deploy : %s %s", e, detail[:200])
        raise ErreurMaj("Le service de déploiement n'a pas pu être démarré.", code=500)

    return {"tag": verification["tag"], "etat": "en_cours"}
