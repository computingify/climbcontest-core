"""Commandes en ligne, pour ce qui ne doit surtout pas etre une route HTTP.

    flask creer-admin <identifiant>
    flask lister-comptes

Le premier administrateur se cree ICI, jamais par une route ouverte « juste
pour le premier ». Ce genre de route reste : on la met en place un soir, on se
promet de la retirer, et elle se retrouve en production trois mois plus tard.

Le mot de passe est DEMANDE, jamais passe en argument : un argument finit dans
l'historique du shell et dans la liste des processus, visible par n'importe qui
sur la machine.
"""
import getpass
import sys

import click
from flask.cli import with_appcontext

from . import comptes
from .models import Utilisateur


def enregistrer(app):
    app.cli.add_command(creer_admin)
    app.cli.add_command(lister_comptes)


@click.command("creer-admin")
@click.argument("identifiant")
@click.option("--organisateur-seulement", is_flag=True,
              help="Cree un organisateur plutot qu'un administrateur.")
@with_appcontext
def creer_admin(identifiant, organisateur_seulement):
    """Cree un compte. Le mot de passe est demande, jamais en argument."""
    roles = [comptes.ORGANISATEUR] if organisateur_seulement else [comptes.ADMIN]

    mot_de_passe = getpass.getpass("Mot de passe : ")
    confirmation = getpass.getpass("Confirmer     : ")
    if mot_de_passe != confirmation:
        click.echo("Les deux saisies different.", err=True)
        sys.exit(1)

    try:
        u = comptes.creer(identifiant, mot_de_passe, roles)
    except comptes.ErreurCompte as e:
        click.echo(f"ECHEC : {e.message}", err=True)
        sys.exit(1)

    click.echo(f"Compte « {u.identifiant} » cree ({', '.join(roles)}).")


@click.command("lister-comptes")
@with_appcontext
def lister_comptes():
    """Qui a acces a la console, et avec quels roles."""
    tous = Utilisateur.query.order_by(Utilisateur.identifiant).all()
    if not tous:
        click.echo("Aucun compte. En creer un : flask creer-admin <identifiant>")
        return
    for u in tous:
        etat = "" if u.actif else "  (desactive)"
        click.echo(f"  {u.identifiant:<20} {', '.join(sorted(r.role for r in u.roles))}{etat}")
