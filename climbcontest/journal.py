"""Configuration du journal.

Sans ce module, `logger.info(...)` ne sort **nulle part** : le logger racine de
Python est a WARNING et n'a aucun handler. Le service systemd ne passe ni
`--log-level` ni `--capture-output`, donc rien ne rattrape.

Ce n'etait pas un detail de confort. Le passage en mode strict de la cle d'API
-- celui qui casserait l'application v3.1.4 du Play Store -- se decide sur cette
commande, ecrite dans auth.py et dans le runbook :

    journalctl -u climbcontest --since today | grep -c "appel sans cle"

Elle renvoyait **0 quoi qu'il arrive**. Lire ce 0 comme « plus personne n'appelle
sans cle », activer le mode strict, et l'application affiche « erreur reseau » a
chaque scan un dimanche matin.

Sous gunicorn, on se branche sur SES handlers plutot que d'en creer : le
journal applicatif part alors ou part deja celui du serveur -- journald en
production, la sortie d'erreur en developpement.
"""
import logging
import os
import sys

NIVEAU_DEFAUT = "INFO"


def configurer() -> None:
    """Idempotent : relancable sans empiler les handlers."""
    niveau = getattr(
        logging,
        os.environ.get("CLIMBCONTEST_LOG_LEVEL", NIVEAU_DEFAUT).upper(),
        logging.INFO,
    )

    racine = logging.getLogger()
    gunicorn = logging.getLogger("gunicorn.error")

    if gunicorn.handlers:
        # Servi par gunicorn : on emprunte ses handlers, donc sa destination.
        racine.handlers = list(gunicorn.handlers)
    elif not racine.handlers:
        # Lance a la main (tests, scripts, flask run).
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        racine.addHandler(handler)

    racine.setLevel(niveau)
    logging.getLogger("climbcontest").setLevel(niveau)
