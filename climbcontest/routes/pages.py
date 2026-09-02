"""Les pages HTML, par opposition aux routes qui rendent du JSON.

Un blueprint a part, sans prefixe : la page de resultats vit a la RACINE, pas
sous `/api/public`. C'est cette adresse qui est ouverte par les spectateurs,
exemptee de CrowdSec et mise en cache 5 s par Caddy.

⚠️ `/resultats` a ete SUPPRIMEE (spec 016). Les deux adresses servaient la meme
vue : `climbcontest.adn-dev.fr` menait deja au meme endroit. Un doublon d'URL
finit toujours par diverger dans les tetes -- « la page de resultats » et « la
racine » devenaient deux choses alors qu'il n'y en a qu'une. Les alias
`resultats.maison.adn-dev.fr` et la regle `@public path /resultats` du proxy ont
ete retires le meme jour.
"""
import logging

from flask import Blueprint, render_template

from ..suivi import plan_public

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


@bp.get("/")
def resultats():
    """La page que les spectateurs ouvrent, et qu'on projette dans la salle.

    Servie presque telle quelle : la page va chercher le classement elle-meme,
    ce qui lui permet de se rafraichir sans rechargement -- et surtout de GARDER le dernier classement connu quand le
    serveur devient injoignable. Une page de resultats qui se vide sur une
    erreur reseau fait croire que la competition s'est arretee.

    `?mur` bascule en mode grand ecran : rotation automatique des categories,
    grande echelle, aucun bouton. L'ecran de la salle est accroche en hauteur ;
    personne ne le touchera de la journee. `?mur&sombre` pour une salle qu'on
    peut assombrir -- le defaut est CLAIR depuis la spec 016, parce qu'un
    videoprojecteur ajoute de la lumiere sur un mur et n'en retire pas.

    Aucune authentification, et c'est le but. Elle ne fait que lire, et
    n'affiche que ce qui est deja public : nom, club, categorie, score, rang et
    un compte de blocs.
    """
    return render_template("resultats.html", plan=plan_public())


@bp.get("/console/archives/<int:identifiant>/resultats")
def archive_resultats(identifiant: int):
    """Revoir une edition archivee, dans la VRAIE page de resultats.

    Le meme gabarit que `/`, avec une source de donnees differente : podium,
    colonnes, scratchs, mode mur, tout marche sans qu'une ligne d'affichage
    soit dupliquee. `?mur` reste utilisable -- revoir l'edition passee sur le
    videoprojecteur pendant que la salle se remplit est exactement l'usage.

    **Consultation seule** (Adrien, 01/09 : « cette visu ne doit etre que
    temporaire, c'est juste de la consultation »). Rien n'est restaure, rien ne
    redevient actif, et `/` continue d'afficher la competition ACTIVE pendant
    qu'on regarde une archive dans un autre onglet.

    La page est servie sans session -- comme `/console`, elle ne contient
    aucune donnee. C'est `/admin/archives/<id>/classement` qui exige la
    session, et c'est la que sont les noms.
    """
    from ..extensions import db
    from ..models import Archive

    archive = db.session.get(Archive, identifiant)
    if archive is None:
        return render_template("resultats.html", plan=plan_public()), 404

    libelle = archive.date.isoformat() if archive.date else (
        archive.cree_le.date().isoformat() if archive.cree_le else "")
    return render_template(
        "resultats.html", plan=plan_public(),
        source=f"/admin/archives/{identifiant}/classement",
        archive_libelle=libelle)
