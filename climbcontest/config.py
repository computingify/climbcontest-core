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


class Config:
    DOSSIER_DONNEES = _chemin_donnees()
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
    SHEETS_PERIODE_S = int(os.environ.get("CLIMBCONTEST_SHEETS_PERIODE", "30"))


class ConfigTest(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite://"   # en mémoire
    SHEETS_ACTIF = False                    # aucun accès réseau dans les tests
    API_KEY = "cle-de-test"
