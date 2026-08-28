"""Fabrique d'application ClimbContest.

Point d'entrée unique. `wsgi.py` appelle `creer_app()`.

⚠️ Différence essentielle avec la version précédente : **rien n'est détruit au
démarrage**. `main.py` exécutait `db.drop_all()` au niveau module, donc à chaque
import — donc dans chacun des quatre workers gunicorn. C'est le risque R1 de
l'état des lieux, et la spec 001 le rendait mortel.
"""
import logging
import os

from flask import Flask

from . import sqlite_reglages  # noqa: F401  (branche les pragmas SQLite)
from .config import Config, ConfigTest
from .extensions import db

logger = logging.getLogger(__name__)


def creer_app(config=None) -> Flask:
    from .journal import configurer
    configurer()

    app = Flask(__name__)
    app.config.from_object(config or (ConfigTest if os.environ.get("CLIMBCONTEST_TEST") else Config))

    dossier = app.config.get("DOSSIER_DONNEES")
    if dossier and app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:////"):
        os.makedirs(dossier, exist_ok=True)

    # check_same_thread : gunicorn sert en threads (4 workers x 4 threads).
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS",
                              {"connect_args": {"check_same_thread": False}})

    db.init_app(app)

    from . import models  # noqa: F401  (enregistre les tables)
    from .routes.admin import bp as bp_admin
    from .routes.catalogue import bp as bp_catalogue
    from .routes.lot import bp as bp_lot
    from .routes.pages import bp as bp_pages
    from .routes.contest import bp as bp_contest
    from .routes.public import bp as bp_public
    from .routes.sante import bp as bp_sante

    app.register_blueprint(bp_contest)
    app.register_blueprint(bp_catalogue)
    app.register_blueprint(bp_lot)
    app.register_blueprint(bp_pages)
    app.register_blueprint(bp_admin)
    app.register_blueprint(bp_public)
    app.register_blueprint(bp_sante)

    with app.app_context():
        from .schema import preparer_schema
        preparer_schema()

    # Le miroir vers le classeur. Chaque worker gunicorn demarre le fil ; le
    # verrou porte par la base fait qu'un seul travaille reellement.
    from .sheets.planificateur import demarrer
    demarrer(app)

    return app
