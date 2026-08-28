"""Préparation du schéma — créer si absent, ne JAMAIS détruire.

Ce module remplace les trois lignes les plus dangereuses de l'ancien `main.py` :

    db.drop_all()
    db.create_all()
    sync_data_from_google_sheet()

Elles s'exécutaient **au niveau module**, donc à chaque import, donc dans chacun
des quatre workers gunicorn de la spec 001 : la base était effacée quatre fois au
démarrage, et une fois de plus à chaque redémarrage d'un worker. C'est le risque
R1 de l'état des lieux, et le symptôme côté juge était « grimpeur inconnu » de
façon aléatoire.

Ici :

- on crée les tables **si elles n'existent pas** ;
- on joue les migrations en séquence, chacune une seule fois ;
- **aucune destruction**, sous aucun prétexte. Réinitialiser une compétition est
  une action explicite de la console d'administration, pas un effet de bord du
  démarrage ;
- le tout sous un **verrou porté par la base**, pour que quatre workers qui
  démarrent en même temps ne se marchent pas dessus.
"""

import logging
import os
import socket
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from .extensions import db

logger = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_MIGRATIONS = RACINE / "migrations"
VERROU_SCHEMA = "schema"


def _identite() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _table_migrations() -> None:
    db.session.execute(text(
        "CREATE TABLE IF NOT EXISTS migration ("
        " nom TEXT PRIMARY KEY,"
        " jouee_le TIMESTAMP NOT NULL)"
    ))
    db.session.commit()


def _deja_jouees() -> set[str]:
    lignes = db.session.execute(text("SELECT nom FROM migration")).fetchall()
    return {l[0] for l in lignes}


def _prendre_verrou() -> bool:
    """Verrou consultatif en base.

    Renvoie True si ce processus doit faire le travail. Les autres passent leur
    tour : le schéma sera prêt quand ils serviront leur première requête, parce
    que le détenteur du verrou termine avant de libérer.
    """
    from .models import Verrou

    db.session.execute(text(
        "CREATE TABLE IF NOT EXISTS verrou ("
        " nom TEXT PRIMARY KEY, detenu_par TEXT, pris_le TIMESTAMP)"
    ))
    db.session.commit()

    try:
        db.session.execute(
            text("INSERT INTO verrou (nom, detenu_par, pris_le) VALUES (:n, :d, :p)"),
            {"n": VERROU_SCHEMA, "d": _identite(), "p": datetime.now()},
        )
        db.session.commit()
        return True
    except Exception:
        # Quelqu'un l'a déjà : il fait le travail, on le laisse faire.
        db.session.rollback()
        return False


def _rendre_verrou() -> None:
    try:
        db.session.execute(text("DELETE FROM verrou WHERE nom = :n"), {"n": VERROU_SCHEMA})
        db.session.commit()
    except Exception:
        db.session.rollback()


def preparer_schema() -> None:
    """Crée le schéma si besoin et joue les migrations. Idempotent."""
    proprietaire = _prendre_verrou()
    if not proprietaire:
        logger.info("schema : un autre processus s'en charge")
        return

    try:
        # create_all ne touche pas aux tables existantes : sûr à relancer.
        db.create_all()
        _table_migrations()

        jouees = _deja_jouees()
        fichiers = sorted(DOSSIER_MIGRATIONS.glob("*.sql")) if DOSSIER_MIGRATIONS.is_dir() else []
        for fichier in fichiers:
            if fichier.name in jouees:
                continue
            logger.info("migration %s", fichier.name)
            sql = fichier.read_text(encoding="utf-8")
            for instruction in filter(None, (i.strip() for i in sql.split(";"))):
                db.session.execute(text(instruction))
            db.session.execute(
                text("INSERT INTO migration (nom, jouee_le) VALUES (:n, :d)"),
                {"n": fichier.name, "d": datetime.now()},
            )
            db.session.commit()

        logger.info("schema pret (%d migration(s) connue(s))", len(jouees) + len(fichiers))
    finally:
        _rendre_verrou()
