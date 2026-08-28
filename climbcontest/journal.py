"""Configuration du journal.

Sans ce module, `logger.info(...)` ne sort **nulle part** : le logger racine de
Python est a WARNING et n'a aucun handler. Le service systemd ne passe ni
`--log-level` ni `--capture-output`, donc rien ne rattrape.

Ce n'est pas un detail de confort. Le passage en mode strict de la cle d'API --
celui qui casserait l'application v3.1.4 du Play Store -- se decide sur cette
commande :

    journalctl -u climbcontest --since today | grep -c "appel sans cle"

Sans ce module, elle renverrait **0 quoi qu'il arrive**. Lire ce 0 comme « plus
personne n'appelle sans cle », activer le mode strict, et l'application affiche
« erreur reseau » a chaque scan un dimanche matin.

Precision, parce que le raccourci serait flatteur : cette panne n'a jamais eu
lieu en production. La ligne de journal, la commande et le mode strict sont
introduits ENSEMBLE dans la meme branche que ce module. Ce qui a ete evite,
c'est de livrer un interrupteur avec un indicateur muet -- pas une panne reelle.

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

    # La RACINE reste a WARNING ; seul « climbcontest » descend au niveau
    # demande. Monter la racine a INFO reveillait aussi les bibliotheques
    # tierces -- `googleapiclient.discovery` journalise a INFO l'URL complete de
    # chaque appel, identifiant du classeur compris, et le miroir tourne toutes
    # les 40 s pendant toute la competition. Ce n'est pas une fuite de secret
    # (le jeton voyage dans un en-tete), mais c'est du bruit dans journald que
    # personne n'a demande.
    #
    # Le niveau de la racine n'empeche rien : un enregistrement emis par
    # « climbcontest.auth » est filtre par le niveau EFFECTIF de son propre
    # logger, puis remis aux handlers de la racine sans nouvelle verification de
    # niveau. C'est verifie par test_le_journal_recoit_bien_les_appels_sans_cle.
    racine.setLevel(logging.WARNING)
    logging.getLogger("climbcontest").setLevel(niveau)
