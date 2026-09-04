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

from flask import Blueprint, Response, render_template

from ..suivi import plan_public
from ..version import VERSION

logger = logging.getLogger(__name__)
bp = Blueprint("pages", __name__)


# L'adresse a qui ecrire pour exercer ses droits. Choix d'Adrien du 04/09 :
# « pour le moment laisse la mienne ». Une adresse d'association survivrait
# mieux a un changement de benevole -- le jour ou elle existe, c'est ici qu'on
# la change, et a un seul endroit.
CONTACT = "adrien.jouve@adn-dev.fr"


# Le contenu est ecrit ici, en clair, plutot que servi depuis un fichier
# statique : une regle d'indexation est une decision, elle se relit dans le code
# qui la porte et un test la lit.
ROBOTS = "User-agent: *\nDisallow: /\n"


@bp.get("/robots.txt")
def robots():
    """Ce site ne s'indexe pas. Spec 043.

    `Disallow: /` demande de ne pas VISITER. La balise `noindex` des gabarits
    demande de ne pas GARDER, et l'en-tete `X-Robots-Tag` dit la meme chose aux
    reponses JSON. Les trois ne se remplacent pas : un robot qui n'a pas visite
    ne lit aucune balise, et un robot qui ignore ce fichier lit la balise.
    """
    return Response(ROBOTS, mimetype="text/plain")


@bp.get("/confidentialite")
def confidentialite():
    """Ce qui est publie, pourquoi, et comment s'y opposer. Spec 043.

    Servie par l'application et non depuis un site exterieur : elle est
    versionnee avec le code qu'elle decrit, elle reste joignable si le wifi de
    la salle ne sort pas, et elle suit le theme de la page de resultats.

    ⚠️ A ne pas confondre avec la politique du depot
    `climbcontestConfidentiality`, qui couvre l'application juge du Play Store
    et dit « aucune donnee personnelle n'est collectee » : exact pour le juge,
    faux pour le systeme. Sa reecriture est un autre chantier.
    """
    return render_template("confidentialite.html", contact=CONTACT)


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
    # La version est posee A LA COMPOSITION de la page, et non demandee ensuite
    # par un appel : la console est servie a chaque ouverture, jamais mise en
    # cache. Elle affiche donc toujours la version qui la sert -- ce qui n'est
    # PAS le cas de la PWA, dont la coquille vit dans un cache et peut avoir un
    # tour de retard. Les deux ecrans disent la meme chose, chacun a sa maniere.
    return render_template("admin.html", version=VERSION)


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
