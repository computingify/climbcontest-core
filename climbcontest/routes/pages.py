"""Les pages HTML, par opposition aux routes qui rendent du JSON.

Un blueprint a part, sans prefixe : la page de resultats doit vivre a la racine
(`/resultats`), pas sous `/api/public`. C'est cette adresse qui est ouverte par
les spectateurs, exemptee de CrowdSec et mise en cache 5 s par Caddy.
"""
import logging

from flask import Blueprint, render_template

logger = logging.getLogger(__name__)
bp = Blueprint("pages", __name__)


@bp.get("/console")
def console():
    """La console d'administration, pour les organisateurs.

    Servie SANS authentification -- c'est la page elle-meme qui demande la
    connexion, puis appelle les routes `/admin/*`, lesquelles exigent une
    session. Proteger le HTML n'apporterait rien : il ne contient aucune
    donnee, seulement le formulaire de connexion.

    En mauve, la ou la page publique est en bleu : sur un ecran d'organisateur,
    on doit savoir en un coup d'oeil si on regarde ce que voient les
    spectateurs ou ce qu'on peut modifier.
    """
    return render_template("admin.html")


@bp.get("/resultats")
@bp.get("/")
def resultats():
    """La page que les spectateurs ouvrent, et qu'on projette dans la salle.

    Servie telle quelle : **aucune donnee n'est injectee dans le HTML**. La page
    va chercher le classement elle-meme, ce qui lui permet de se rafraichir sans
    rechargement -- et surtout de GARDER le dernier classement connu quand le
    serveur devient injoignable. Une page de resultats qui se vide sur une
    erreur reseau fait croire que la competition s'est arretee.

    `?mur` bascule en mode grand ecran : rotation automatique des categories,
    grande echelle, aucun bouton. L'ecran de la salle est accroche en hauteur ;
    personne ne le touchera de la journee.

    Aucune authentification, et c'est le but. Elle ne fait que lire, et
    n'affiche que ce qui est deja public : nom, club, categorie, score, rang et
    un compte de blocs.
    """
    return render_template("resultats.html")
