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
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from .extensions import db

logger = logging.getLogger(__name__)

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_MIGRATIONS = RACINE / "migrations"
VERROU_SCHEMA = "schema"

# Au-dela de ce delai, un verrou est considere comme abandonne et peut etre
# vole. Sans cette limite, un processus tue entre la prise et la liberation
# (OOM killer, `systemctl kill`, coupure de courant) laisse la ligne en base
# POUR TOUJOURS : plus aucun demarrage ne prepare le schema, les migrations
# suivantes ne sont jamais jouees, et le journal affirme tranquillement qu'un
# autre processus s'en charge. La panne serait invisible jusqu'au jour ou une
# migration manquante ferait echouer une requete en pleine competition.
#
# 60 s est genereux : `create_all` plus les migrations prennent moins d'une
# seconde sur cette base, et le vol ne casse rien meme s'il est premature
# (create_all et les migrations sont idempotents).
VERROU_TTL = timedelta(seconds=60)

# Combien de temps un worker qui n'a pas le verrou attend que le detenteur ait
# fini. Passe ce delai, il ne se contente PAS de servir : il verifie l'etat reel
# du schema et reprend le travail si besoin (voir preparer_schema).
ATTENTE_MAX = timedelta(seconds=10)


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


def _table_verrou() -> None:
    db.session.execute(text(
        "CREATE TABLE IF NOT EXISTS verrou ("
        " nom TEXT PRIMARY KEY, detenu_par TEXT, pris_le TIMESTAMP)"
    ))
    db.session.commit()


def _essayer_de_prendre() -> bool:
    """Une seule tentative d'insertion. La clé primaire arbitre."""
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


def _verrou_courant():
    """Renvoie (detenu_par, pris_le) du verrou de schéma, ou None."""
    ligne = db.session.execute(
        text("SELECT detenu_par, pris_le FROM verrou WHERE nom = :n"),
        {"n": VERROU_SCHEMA},
    ).fetchone()
    return ligne


def _prendre_verrou() -> bool:
    """Verrou consultatif en base.

    Renvoie True si ce processus doit faire le travail, False s'il doit attendre
    qu'un autre l'ait fini (voir [_attendre_liberation]).
    """
    _table_verrou()

    if _essayer_de_prendre():
        return True

    # Échec : soit un autre worker travaille en ce moment même — le cas normal
    # au démarrage des quatre workers — soit le détenteur est mort en cours de
    # route et personne ne libérera jamais. On distingue par l'ancienneté.
    ligne = _verrou_courant()
    if ligne is None:
        # Libéré entre notre INSERT et notre SELECT : on retente une fois.
        return _essayer_de_prendre()

    detenu_par, pris_le = ligne[0], ligne[1]
    pris_le_brut = pris_le            # tel qu'il est en base, pour le WHERE du vol
    if isinstance(pris_le, str):        # SQLite rend un TIMESTAMP brut en texte
        try:
            pris_le = datetime.fromisoformat(pris_le)
        except ValueError:
            pris_le = None

    if pris_le is None or datetime.now() - pris_le <= VERROU_TTL:
        return False

    logger.warning(
        "verrou de schema abandonne par %s depuis %s : on le reprend",
        detenu_par, datetime.now() - pris_le,
    )
    # Le WHERE porte sur le détenteur ET sa date. La date n'est pas décorative :
    # `_identite()` vaut `hostname:pid`, et un PID se recycle — gunicorn peut
    # attribuer à un worker vivant le PID exact du processus mort. Sans la date,
    # un voleur supprimerait alors le verrou FRAIS d'un autre voleur.
    # L'exclusion mutuelle finale reste assurée par la clé primaire sur `nom` :
    # des deux voleurs, un seul verra son INSERT passer.
    db.session.execute(
        text("DELETE FROM verrou WHERE nom = :n AND detenu_par = :d AND pris_le = :p"),
        {"n": VERROU_SCHEMA, "d": detenu_par, "p": pris_le_brut},
    )
    db.session.commit()
    return _essayer_de_prendre()


def _schema_pret() -> bool:
    """Les tables existent-elles vraiment ?

    C'est la SEULE question qui compte. Le verrou n'est qu'un moyen d'eviter que
    quatre workers fassent le meme travail ; l'invariant a tenir est que la base
    soit utilisable avant de servir la premiere requete.

    Se fier a l'age du verrou ne suffit pas, et le detail est vicieux :
    l'unite systemd relance le service 5 s apres un plantage (`RestartSec=5s`).
    Un verrou laisse par un worker tue a donc TOUJOURS moins de 60 s au
    redemarrage -- il n'est jamais considere comme perime, personne ne le vole,
    et les quatre nouveaux workers servaient avec une base vide. Le journal
    disait « on sert quand meme », `/health` repondait 200, et l'agent de
    deploiement validait la mise en production.
    """
    try:
        db.session.execute(text("SELECT 1 FROM competition LIMIT 1"))
        return True
    except Exception:
        db.session.rollback()
        return False


def _attendre_liberation() -> None:
    """Attend que le détenteur ait fini de préparer le schéma.

    Sans cette attente, un worker qui n'a pas eu le verrou rendait la main
    immédiatement et gunicorn le déclarait prêt : il pouvait servir une requête
    avant que `create_all` du détenteur ait créé les tables. C'est exactement le
    symptôme R1 côté juge — « grimpeur inconnu » de façon aléatoire — mais pour
    une autre raison que la base effacée.
    """
    limite = time.monotonic() + ATTENTE_MAX.total_seconds()
    while time.monotonic() < limite:
        if _verrou_courant() is None:
            return
        time.sleep(0.05)


def _forcer_verrou() -> None:
    """Prend le verrou sans condition, en ecrasant ce qui s'y trouve.

    Reserve au cas ou l'attente a expire ET que le schema est toujours absent :
    a ce stade, respecter le verrou reviendrait a servir une base vide.
    """
    db.session.execute(text("DELETE FROM verrou WHERE nom = :n"), {"n": VERROU_SCHEMA})
    db.session.commit()
    _essayer_de_prendre()


def _rendre_verrou() -> None:
    """Rend le verrou -- le NOTRE, pas celui d'un autre.

    Sans la clause sur `detenu_par`, un detenteur lent mais vivant dont le
    verrou vient d'etre vole effacait en sortant le verrou FRAIS de son voleur.
    Un troisieme processus le prenait alors, et deux preparations tournaient en
    parallele -- ce qui, des la premiere vraie migration SQL, ferait echouer le
    DDL du second et tuer son worker au demarrage.
    """
    try:
        db.session.execute(
            text("DELETE FROM verrou WHERE nom = :n AND detenu_par = :d"),
            {"n": VERROU_SCHEMA, "d": _identite()},
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


# Colonnes ajoutees apres coup a des tables qui existent deja. `create_all` ne
# touche pas a une table existante, et SQLite n'a pas `ADD COLUMN IF NOT
# EXISTS` : sans ce tableau, une base d'avant la modification garderait
# l'ancienne forme et chaque requete echouerait sur la colonne manquante.
#
# Un fichier .sql ne conviendrait pas ici : le lanceur de migrations joue
# chaque fichier une fois, mais sur une base NEUVE `create_all` a deja cree la
# colonne, et l'ALTER echouerait sur « duplicate column ». On regarde donc
# l'etat reel de la table plutot que de tenir un compteur.
COLONNES_AJOUTEES = {
    "success": {
        "dossard_scanne": "INTEGER",
        "scanne_le": "TIMESTAMP",
        "saisie_par": "TEXT",
    },
}


def _completer_colonnes() -> None:
    """Ajoute les colonnes manquantes des tables deja existantes. Idempotent."""
    for table, colonnes in COLONNES_AJOUTEES.items():
        try:
            presentes = {
                ligne[1] for ligne in
                db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
            }
        except Exception:
            db.session.rollback()
            continue
        if not presentes:
            continue                      # table absente : create_all s'en charge
        for nom, type_sql in colonnes.items():
            if nom in presentes:
                continue
            logger.info("schema : ajout de %s.%s", table, nom)
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {nom} {type_sql}"))
            db.session.commit()


def preparer_schema() -> None:
    """Crée le schéma si besoin et joue les migrations. Idempotent."""
    if not _prendre_verrou():
        _attendre_liberation()
        if _schema_pret():
            logger.info("schema : prepare par un autre processus")
            return
        # Le detenteur n'a pas fini, ou ne finira jamais. On ne sert PAS une
        # base vide en esperant que ca passe : on reprend le verrou de force et
        # on fait le travail. `create_all` et les migrations sont idempotents,
        # donc au pire deux processus font deux fois la meme chose sans degat.
        logger.warning("schema : toujours absent apres l'attente, on reprend la main")
        _forcer_verrou()

    try:
        # create_all ne touche pas aux tables existantes : sûr à relancer.
        db.create_all()
        _completer_colonnes()
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
