"""Configuration, lue de l'environnement.

Rien n'est en dur : ni l'identifiant du classeur (il vit en base, par
compétition), ni les secrets. Sur la VM, systemd charge
/opt/climbcontest/shared/secrets/env.
"""
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _chemin_donnees() -> Path:
    """shared/data sur la VM, ./instance en développement.

    Les données ne sont JAMAIS dans une release : un déploiement ou un retour
    arrière ne doit pas pouvoir les toucher.
    """
    if defaut := os.environ.get("CLIMBCONTEST_DATA_DIR"):
        return Path(defaut)
    partage = Path("/opt/climbcontest/shared/data")
    return partage if partage.is_dir() else RACINE / "instance"


def _chemin_secrets() -> Path:
    """Ou vivent le jeton Google et les identifiants OAuth.

    Comme les donnees, ils sont HORS des releases : un deploiement ou un retour
    arriere ne doit pas pouvoir les toucher. L'unite systemd de la VM definit
    deja `CLIMBCONTEST_SECRETS_DIR` -- le code, lui, cherchait `token.pickle`
    en chemin RELATIF, donc dans le repertoire de travail du service, ou il n'a
    jamais ete. Resultat : « Aucun jeton Google » toutes les 40 secondes, et
    aucune reussite ne serait jamais arrivee dans le classeur.
    """
    if defaut := os.environ.get("CLIMBCONTEST_SECRETS_DIR"):
        return Path(defaut)
    partage = Path("/opt/climbcontest/shared/secrets")
    return partage if partage.is_dir() else RACINE / "security"


class Config:
    DOSSIER_DONNEES = _chemin_donnees()
    DOSSIER_SECRETS = _chemin_secrets()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "CLIMBCONTEST_DATABASE_URI",
        f"sqlite:///{DOSSIER_DONNEES / 'climbcontest.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("CLIMBCONTEST_SECRET_KEY", "dev-non-secret")

    # Clé d'API des juges. Voir specs/002 §6 : mode TOLERE tant que
    # l'application v3.1.4 du Play Store, qui n'en envoie aucune, est en service.
    API_KEY = os.environ.get("CLIMBCONTEST_API_KEY")
    API_KEY_STRICTE = os.environ.get("CLIMBCONTEST_API_KEY_STRICTE", "") == "1"

    # Miroir vers le classeur Google.
    SHEETS_ACTIF = os.environ.get("CLIMBCONTEST_SHEETS_ACTIF", "1") == "1"
    SHEETS_TAILLE_LOT = int(os.environ.get("CLIMBCONTEST_SHEETS_LOT", "50"))
    # Rythme conserve de la version precedente (decision Q2 du 28/08) :
    # 50 reussites par lot, une tentative toutes les 40 secondes.
    SHEETS_PERIODE_S = int(os.environ.get("CLIMBCONTEST_SHEETS_PERIODE", "40"))


class ConfigTest(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite://"   # en mémoire
    SHEETS_ACTIF = False                    # aucun accès réseau dans les tests
    API_KEY = "cle-de-test"
