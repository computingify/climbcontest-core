"""Routes d'administration.

Squelette de la spec 002 : seul l'import du classeur est ici. La console
complete -- saisie manuelle, parametrage, participants a chaud, impression des
dossards, archives, comptes -- est le sujet de la spec 005.

⚠️ PROTECTION PROVISOIRE. Ces routes exigent la cle d'API pour l'instant. La
spec 005 les passera en session + roles, sur le modele de guestFlow
(requireAuth + enforceRoleAccess, liste blanche par role, fail-closed). Le
Caddyfile distingue deja /admin/* des autres surfaces : CrowdSec y reste actif,
et l'exemption posee pour l'API des juges ne s'y applique pas.
"""
import logging
import os
from urllib.parse import quote

from flask import (Blueprint, Response, current_app, g, jsonify, redirect,
                   render_template, request, session)

from ..auth_session import exige_role, fermer, ouvrir, utilisateur_courant
from .. import freinage
from .. import comptes
from ..comptes import ADMIN, ORGANISATEUR, ErreurCompte, verifier
from .. import qr
from .. import classement_service
from ..extensions import db
from ..models import (Bloc, SOURCE_MANUEL, Competition, Participant,
                      Success, Utilisateur)
from ..contest import (
    ErreurMetier, ajouter_participant, ajouter_participant_numerote, appareils,
    bloc_par_tag, club_canonique, competition_active,
    enregistrer_reussite, homonymes,
    incrementer_catalogue,
    participant_par_dossard, reussites_tracees,
    supprimer_reussite, verifier_annee,
)
from .. import bareme as bareme_module
from ..helloasso import client as ha_client
from ..helloasso import correspondance as ha_correspondance
from ..helloasso import planificateur as ha_planificateur
from ..helloasso import releve as ha_releve
from ..helloasso import salle as ha_salle
from .. import categories
from .. import formatage
from .. import circuits as circuits_module
from .. import cascade as cascade_module
from .. import cycle
from .. import fiches
from .. import maj
from ..models import Archive
from ..sheets import consentement, parametrage
from ..sheets.client import ErreurClasseur, ecrire_jeton_json
from ..sheets.importer import importer, lire_tout
from .. import version as version_module

logger = logging.getLogger(__name__)
bp = Blueprint("admin", __name__, url_prefix="/admin")


# --- Connexion --------------------------------------------------------------
#
# La cle d'API partagee qui protegeait ces routes etait une mesure d'attente,
# posee en urgence le 28/08 apres avoir constate qu'elles repondaient 200 depuis
# Internet. Elle est remplacee ici par de vrais comptes.

@bp.post("/connexion")
def connexion():
    """{"identifiant": "...", "mot_de_passe": "..."} -> ouvre une session."""
    corps = request.get_json(silent=True)
    if not isinstance(corps, dict):
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    # Le frein AVANT la verification : sinon un robot ferait travailler le
    # hachage scrypt a chaque tentative, ce qui est precisement ce qu'on veut
    # eviter -- il est lent a dessein.
    adresse = request.remote_addr or "inconnue"
    attente = freinage.attente_restante(adresse)
    if attente.total_seconds() > 0:
        secondes = max(1, int(attente.total_seconds()))
        logger.warning("connexion freinee pour %s (%d s restantes)", adresse, secondes)
        reponse = jsonify({
            "success": False,
            "message": f"Trop de tentatives. Reessaie dans {secondes} seconde"
                       f"{'s' if secondes > 1 else ''}.",
        })
        reponse.headers["Retry-After"] = str(secondes)
        return reponse, 429

    u = verifier(corps.get("identifiant", ""), corps.get("mot_de_passe", ""))
    if u is None:
        freinage.noter_echec(adresse)
        # Le MEME message et le MEME delai que l'identifiant existe ou non :
        # distinguer les deux revelerait quels comptes sont valides.
        logger.warning("connexion refusee pour « %s » depuis %s",
                       str(corps.get("identifiant", ""))[:40], request.remote_addr)
        return jsonify({"success": False,
                        "message": "Identifiant ou mot de passe incorrect"}), 401

    freinage.noter_reussite(adresse)
    ouvrir(u)
    logger.info("connexion de %s depuis %s", u.identifiant, adresse)
    return jsonify(_identite(u)), 200


@bp.post("/deconnexion")
def deconnexion():
    u = utilisateur_courant()
    fermer()
    if u:
        logger.info("deconnexion de %s", u.identifiant)
    return jsonify({"success": True}), 200


def _identite(u) -> dict:
    """Ce que la console sait de l'utilisateur connecte.

    ⚠️ UNE seule fonction pour `/admin/connexion` et `/admin/moi`, et c'est le
    correctif : les deux reponses etaient ecrites separement, `/moi` a recu le
    champ `competition` et la connexion ne l'a jamais eu. La console lit
    `etat.moi.competition` juste apres la connexion -- elle affichait donc
    « aucune competition active » alors qu'une competition l'etait, et ne se
    corrigeait qu'au rechargement de la page.

    C'est le pire moment pour ce message : un organisateur qui se connecte le
    matin de la competition lit exactement le contraire de la verite, sur
    l'ecran meme qui existe pour lui dire SUR QUOI il agit.

    Deux reponses qui doivent dire la meme chose ne s'ecrivent pas deux fois.
    """
    from ..models import Competition
    active = Competition.query.filter_by(active=True).first()
    return {
        "success": True,
        "identifiant": u.identifiant,
        "nom_affiche": u.nom_affiche,
        "roles": sorted(r.role for r in u.roles),
        # « Le classeur est-il le bon ? » est le point le plus souvent oublie du
        # runbook, et la console etait le seul endroit ou l'on agissait sans
        # jamais voir sur quoi.
        "competition": {"id": active.id, "nom": active.nom} if active else None,
        # Le compteur de la pastille (spec 008). Il voyage ICI, comme celui des
        # mises a jour : la console appelle deja cette route a chaque ecran,
        # une route dediee ferait un aller-retour de plus pour un nombre.
        "inscriptions_en_attente": ha_salle.en_attente(active) if active else 0,
        # « HelloAsso est-il branche ? » est un FAIT, pas un secret : il decide
        # d'une entree de menu. Et il doit voyager ICI, parce que la vue
        # Inscriptions appartient aux ORGANISATEURS alors que le reglage de la
        # cle est reserve aux administrateurs -- le faire lire par
        # /admin/helloasso priverait de menu ceux-la memes qui impriment les
        # dossards et les portent.
        "helloasso_relie": ha_client.configure(),
        # D'ou viennent les inscrits de l'edition active. La console s'en sert
        # pour n'afficher AUCUN parametrage HelloAsso quand il n'est pas
        # selectionne -- demande d'Adrien du 04/09.
        "sources_inscriptions": (cycle.sources_inscriptions(active)
                                 if active else []),
    }


@bp.get("/moi")
@exige_role()
def moi():
    """Qui je suis, et ce que j'ai le droit de faire. La console s'en sert
    pour n'afficher que les boutons utilisables."""
    return jsonify(_identite(g.utilisateur)), 200

# Dernier rapport, en memoire. C'est un confort de consultation, pas une donnee :
# le perdre a un redemarrage est sans consequence, on relance l'import.
_dernier_rapport: dict | None = None


# --- Les comptes ------------------------------------------------------------
#
# La ligne de commande sert a AMORCER -- le tout premier compte, quand il n'y a
# encore personne pour en creer un. Tout le reste se fait d'ici : creer un
# organisateur, remettre un mot de passe oublie, changer un role. Demander un
# acces SSH a chaque nouveau benevole n'aurait aucun sens.

@bp.get("/comptes")
@exige_role(ADMIN)
def lister_comptes():
    tous = Utilisateur.query.order_by(Utilisateur.identifiant).all()
    return jsonify({
        "success": True,
        "comptes": [{
            "id": u.id,
            "identifiant": u.identifiant,
            "nom_affiche": u.nom_affiche,
            "actif": u.actif,
            "roles": sorted(r.role for r in u.roles),
            # Pour que la console puisse griser ce qui fermerait la porte.
            "dernier_admin": u.a_le_role(ADMIN) and u.actif
                             and len(comptes.administrateurs_actifs()) == 1,
        } for u in tous],
        "roles_possibles": sorted(comptes.ROLES_CONNUS),
        "longueur_minimale": comptes.LONGUEUR_MINIMALE,
    }), 200


@bp.post("/comptes")
@exige_role(ADMIN)
def creer_compte():
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400
    try:
        u = comptes.creer(
            corps.get("identifiant", ""), corps.get("mot_de_passe", ""),
            corps.get("roles") or [], corps.get("nom_affiche"),
        )
    except comptes.ErreurCompte as e:
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("compte %s cree par %s", u.identifiant, g.utilisateur.identifiant)
    return jsonify({"success": True, "identifiant": u.identifiant}), 201


@bp.post("/comptes/<int:compte_id>/mot-de-passe")
@exige_role(ADMIN)
def reinitialiser_mot_de_passe(compte_id):
    """Le « mot de passe oublie », sans serveur de courriel.

    L'administrateur en pose un nouveau et le transmet de vive voix. Dans un
    club, c'est le chemin le plus court et le plus sur -- une chaine de
    reinitialisation par courriel demanderait un serveur de mail, donc une
    piece de plus a maintenir pour un usage annuel.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    u = db.session.get(Utilisateur, compte_id)
    if u is None:
        return jsonify({"success": False, "message": "Compte inconnu"}), 404

    try:
        comptes.changer_mot_de_passe(u, corps.get("mot_de_passe", ""))
    except comptes.ErreurCompte as e:
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("mot de passe de %s reinitialise par %s",
                u.identifiant, g.utilisateur.identifiant)
    return jsonify({"success": True}), 200


@bp.post("/comptes/<int:compte_id>/roles")
@exige_role(ADMIN)
def changer_roles(compte_id):
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    u = db.session.get(Utilisateur, compte_id)
    if u is None:
        return jsonify({"success": False, "message": "Compte inconnu"}), 404

    try:
        comptes.definir_roles(u, corps.get("roles") or [])
    except comptes.ErreurCompte as e:
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("roles de %s changes par %s", u.identifiant, g.utilisateur.identifiant)
    return jsonify({"success": True}), 200


@bp.post("/comptes/<int:compte_id>/actif")
@exige_role(ADMIN)
def activer_ou_desactiver(compte_id):
    """Desactive plutot que supprime : les reussites saisies gardent leur auteur."""
    corps = _corps_objet()
    if corps is None or "actif" not in corps:
        return jsonify({"success": False, "message": "Champ « actif » attendu"}), 400

    u = db.session.get(Utilisateur, compte_id)
    if u is None:
        return jsonify({"success": False, "message": "Compte inconnu"}), 404

    try:
        if corps["actif"]:
            comptes.reactiver(u)
        else:
            comptes.desactiver(u)
    except comptes.ErreurCompte as e:
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("compte %s %s par %s", u.identifiant,
                "reactive" if corps["actif"] else "desactive",
                g.utilisateur.identifiant)
    return jsonify({"success": True}), 200


@bp.post("/mon-mot-de-passe")
@exige_role()
def changer_mon_mot_de_passe():
    """Chacun change le sien, sans passer par un administrateur.

    L'ANCIEN mot de passe est exige, meme si la session est deja ouverte : sans
    ca, une session volee -- un ordinateur laisse deverrouille dans la salle --
    permettrait de s'approprier le compte definitivement.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    u = g.utilisateur
    if verifier(u.identifiant, corps.get("actuel", "")) is None:
        logger.warning("changement de mot de passe refuse pour %s : ancien incorrect",
                       u.identifiant)
        return jsonify({"success": False,
                        "message": "Mot de passe actuel incorrect"}), 401

    try:
        comptes.changer_mot_de_passe(u, corps.get("nouveau", ""))
    except comptes.ErreurCompte as e:
        return jsonify({"success": False, "message": e.message}), e.code

    return jsonify({"success": True}), 200


# --- Participants a chaud ---------------------------------------------------
#
# Le besoin qu'Adrien a decrit en premier : « nous pouvons avoir des ajouts de
# participant quelques minutes avant le debut de la competition voire meme
# alors que la competition a demarre ».

@bp.get("/referentiels")
@exige_role(ORGANISATEUR)
def referentiels():
    """Les categories, les clubs, et les zones du plan.

    De quoi remplir les listes deroulantes de la console (spec 013).

    ⚠️ **Les CATEGORIES ne sont plus derivees depuis la spec 045.** Elles
    l'etaient -- l'ensemble des valeurs portees par les participants -- et
    c'est precisement ce qui laissait le « U13 M » de production se proposer
    lui-meme, a cote des vingt-six « U13 H ». Une liste qui se deduit des
    donnees ne peut pas corriger les donnees. C'est desormais
    `categories.LISTE`, les dix-huit libelles publies par la federation.

    Les valeurs hors liste ENCORE PORTEES partent a part, dans
    `categories_hors_liste` : la console les remet dans la ligne de celui qui
    les porte, et nulle part ailleurs. Sans elles, ouvrir le crayon sur ce
    grimpeur changerait sa categorie en silence -- un `<select>` qui ne
    contient pas sa valeur courante en choisit une autre tout seul.

    Les CLUBS, eux, restent derives : leur vocabulaire n'est publie par
    personne.

    Un seul appel pour toutes les listes : la console les charge ensemble, a
    l'ouverture. Deux routes auraient fait deux allers-retours pour un geste --
    c'est aussi pourquoi les ZONES sont ici (spec 034) et non sur une route a
    elles. Elles ne sont PAS derivees des participants : elles viennent du plan
    de la salle, et existent donc sans competition active.

    Sans competition active : les categories officielles quand meme, les clubs
    vides, et `success: true` -- **pas une erreur**. Le formulaire doit rester
    utilisable, et la liste des categories ne depend d'aucune edition.
    """
    # ⚠️ HORS du `try` : les zones viennent du PLAN, qui ne depend d'aucune
    # competition (spec 034). Les calculer apres la garde priverait la console
    # de sa liste de zones tant qu'aucune edition n'est active -- or c'est
    # exactement le moment ou on imprime les QR de poste, la veille au soir.
    zones = sorted(fiches.zones_du_plan(fiches.plan_courant()))

    try:
        comp = competition_active()
    except ErreurMetier:
        return jsonify({"success": True, "categories": list(categories.LISTE),
                        "categories_hors_liste": [], "clubs": [],
                        "zones": zones}), 200

    def distinctes(colonne):
        return sorted(
            v for (v,) in db.session.query(colonne)
            .filter(Participant.competition_id == comp.id, colonne.isnot(None))
            .distinct()
            if v and v.strip()
        )

    return jsonify({
        "success": True,
        "categories": list(categories.LISTE),
        "categories_hors_liste": [c for c in distinctes(Participant.categorie)
                                  if c not in categories.LISTE],
        "clubs": distinctes(Participant.club),
        # Les zones du plan courant : de quoi remplir la liste deroulante des
        # QR de poste sans une deuxieme route pour un seul geste (spec 034).
        "zones": zones,
    }), 200


@bp.get("/participants")
@exige_role(ORGANISATEUR)
def lister_participants():
    """La liste, pour retrouver quelqu'un avant de le modifier."""
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    q = (request.args.get("q") or "").strip().lower()
    participants = Participant.query.filter_by(competition_id=comp.id).all()
    if q:
        participants = [p for p in participants
                        if q in p.nom_complet.lower() or q == str(p.dossard or "")]

    # Le filtre par categorie sert la SELECTION D'IMPRESSION (spec 008) :
    # filtrer, tout selectionner, imprimer. C'est ce qui remplace le champ
    # « une categorie (vide = toutes) » de la tuile d'impression retiree.
    categorie = (request.args.get("categorie") or "").strip()
    if categorie:
        participants = [p for p in participants if (p.categorie or "") == categorie]

    participants.sort(key=lambda p: (p.dossard is None, p.dossard or 0, p.nom))
    return jsonify({
        "success": True,
        # `pour_la_console()` porte `publication_refusee` (spec 043) : la
        # serialisation de la console, distincte de `to_dict()` qui alimente le
        # catalogue des vingt-cinq telephones des juges et doit rester maigre.
        "participants": [p.pour_la_console() for p in participants],
    }), 200


@bp.post("/participants")
@exige_role(ORGANISATEUR)
def ajouter_participant_route():
    """{"nom", "prenom", "club", "categorie", "dossard", "annee_naissance"}."""
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    # ⚠️ Le doublon se PREVIENT avant de se refuser (04/09).
    #
    # La garde de `ajouter_participant` refuse un homonyme du meme club. Mais
    # un homonyme d'un club DIFFERENT, ou dont le club n'est pas encore saisi,
    # passe -- et c'est voulu, deux « Martin Lea » existent vraiment. Reste que
    # l'organisateur doit le savoir AVANT de creer : la route rend donc les
    # homonymes avec la reponse, et la console propose de reprendre la fiche
    # plutot que d'en ouvrir une seconde.
    #
    # C'est ce que la contrainte metier §3 demande : « detection de doublon
    # [...] avec validation humaine ».
    try:
        comp = competition_active()
        deja_la = [p.pour_la_console() for p in homonymes(
            comp, corps.get("nom", ""), corps.get("prenom"))]
    except ErreurMetier:
        deja_la = []

    # Le dossard n'est plus saisi (spec 013) : il est attribue. Un corps qui en
    # porte un quand meme est honore -- la route reste compatible avec les
    # appels existants, et avec ses propres tests.
    try:
        if corps.get("dossard") in (None, ""):
            p = ajouter_participant_numerote(
                nom=corps.get("nom", ""), prenom=corps.get("prenom"),
                club=corps.get("club"), categorie=corps.get("categorie"),
                annee_naissance=corps.get("annee_naissance"),
                autoriser_homonyme=bool(corps.get("autoriser_homonyme")),
            )
        else:
            p = ajouter_participant(
                nom=corps.get("nom", ""), prenom=corps.get("prenom"),
                club=corps.get("club"), categorie=corps.get("categorie"),
                dossard=corps.get("dossard"),
                annee_naissance=corps.get("annee_naissance"),
                autoriser_homonyme=bool(corps.get("autoriser_homonyme")),
            )
    except ErreurMetier as e:
        # Le refus porte les fiches qui ressemblent : la console peut proposer
        # « Reprendre » sans un aller-retour de plus.
        return jsonify({"success": False, "message": e.message,
                        "homonymes": deja_la}), e.code

    logger.info("participant ajoute par %s : %s", g.utilisateur.identifiant, p.nom_complet)
    return jsonify({"success": True, "participant": p.pour_la_console(),
                    "homonymes": deja_la}), 201


@bp.patch("/participants/<int:participant_id>")
@exige_role(ORGANISATEUR)
def modifier_participant(participant_id):
    """L'edition en ligne : la ligne de la liste devient modifiable (spec 008).

    Ne touche QUE les champs presents dans le corps. Envoyer `{"club": "X"}` ne
    doit pas effacer la categorie -- c'est la difference entre un PATCH et un
    PUT, et la console n'envoie que ce qui a bouge.

    ⚠️ **Le dossard ne se change plus**, ni ici ni ailleurs -- decision d'Adrien
    du 05/09. Il est imprime sur un QR code distribue, et le classeur Google
    porte le sien : deux ecritures d'un meme numero finissaient toujours par se
    contredire, et c'est cette contradiction qui fabriquait les doublons.
    Un corps qui en porte un est refuse, jamais ignore en silence.

    Chaque champ modifie est MARQUE (`Participant.forcer`) : c'est ce qui
    empeche l'import du classeur de defaire la correction au tour suivant.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    p = db.session.get(Participant, participant_id)
    if p is None:
        return jsonify({"success": False, "message": "Participant inconnu"}), 404

    try:
        comp = competition_active()
        if p.competition_id != comp.id:
            return jsonify({"success": False,
                            "message": "Ce participant n'est pas de la competition active"}), 409

        if "dossard" in corps and str(corps["dossard"] or "") != str(p.dossard or ""):
            return jsonify({
                "success": False,
                "message": "Le dossard ne se change pas depuis la console. Il "
                           "est imprime sur le QR code deja distribue, et le "
                           "classeur porte le sien : le changer ici fabrique un "
                           "doublon au prochain import. Corriger le classeur, "
                           "puis reimporter.",
            }), 409

        if "nom" in corps:
            nom = formatage.nom(corps["nom"])
            if not nom:
                return jsonify({"success": False,
                                "message": "Le nom est obligatoire"}), 400
            if nom != p.nom:
                p.nom = nom
                p.forcer("nom")
        if "prenom" in corps:
            prenom = formatage.nom(corps["prenom"])
            if prenom != p.prenom:
                p.prenom = prenom
                p.forcer("prenom")
        if "club" in corps:
            # L'orthographe deja en base fait reference : « caf vivarais »
            # corrige a la main ne doit pas fabriquer un second « Caf Vivarais »
            # a cote du « CAF Vivarais » du classeur.
            club = club_canonique(comp, corps["club"])
            if club != p.club:
                p.club = club
                p.forcer("club")
        if "annee_naissance" in corps:
            p.annee_naissance = verifier_annee(corps["annee_naissance"])
        if "categorie" in corps:
            # Passe par le bareme : c'est lui qui pose la trace du geste, pour
            # que « Appliquer a tous » ne defasse pas ce choix (decision D10).
            # `categorie_forcee` est la trace lue par `est_force("categorie")`.
            bareme_module.regler_a_la_main(p, corps["categorie"])

        db.session.add(p)
        incrementer_catalogue(comp)
        db.session.commit()
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("participant %s modifie par %s", p.id, g.utilisateur.identifiant)
    return jsonify({"success": True, "participant": p.pour_la_console()}), 200


@bp.get("/categories")
@exige_role(ORGANISATEUR)
def categories_bareme():
    """Le bareme de l'edition : calcule, jamais saisi (spec 008).

    Il se deduit de la date de la competition -- qui donne la saison, donc
    l'annee de reference -- et des categories que portent les participants.
    Rien n'est stocke : un bareme enregistre pourrait un jour contredire la
    regle, et personne ne saurait lequel des deux fait autorite.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    reference = bareme_module.reference(comp)
    return jsonify({
        "success": True,
        "date": comp.date.isoformat() if comp.date else None,
        "reference": reference,
        "saison": f"{reference - 1}-{reference}",
        "tranches": bareme_module.tranches(comp),
        "hors_de_portee": bareme_module.hors_de_portee(comp),
        "declarees": bareme_module.categories_declarees(comp),
        # Le vocabulaire officiel, pour que la console dessine ses neuf lignes
        # et ses dix-huit interrupteurs sans avoir a le recopier (spec 045).
        "officielles": list(categories.OFFICIELLES),
        "genres": list(categories.GENRES),
        # Les neuf lignes de l'ecran, assemblees cote serveur (spec 045, D5).
        "tableau": bareme_module.tableau(comp),
        # Ce qui est en base et n'y appartient pas, avec sa cible proposee.
        "hors_liste": bareme_module.hors_liste(comp),
    }), 200


@bp.post("/categories/declarees")
@exige_role(ORGANISATEUR)
def categories_declarer():
    """Les categories que l'edition annonce. `{"categories": [...]}`.

    ⚠️ C'est la porte de sortie du classeur Google, dont la disparition est
    prevue. Les `Circuit` ne sont crees que par son import : sans cette liste,
    une edition alimentee par HelloAsso seul n'aurait aucun Under au premier
    releve, et les cent inscriptions partiraient en attente.
    """
    corps = _corps_objet() or {}
    demandees = corps.get("categories") or []

    # Spec 045, A12. `declarer_categories` passe par `formatage.categorie`,
    # donc « u13f » arrive deja range en « U13 F ». Ce controle-ci sert a autre
    # chose : rendre le REFUS lisible. Sans lui, « Poussin » serait accepte,
    # range « POUSSIN », et n'apporterait aucun Under au bareme -- un reglage
    # qui ne fait rien et ne dit pas pourquoi.
    if isinstance(demandees, list):
        inconnues = sorted({str(n) for n in demandees if str(n).strip()
                            and formatage.categorie(str(n)) not in categories.LISTE})
        if inconnues:
            return jsonify({
                "success": False,
                "message": "Categorie inconnue : " + ", ".join(inconnues)
                           + ". Seules les categories FFME sont acceptees.",
            }), 400

    try:
        comp = competition_active()
        declarees = bareme_module.declarer_categories(comp, demandees)
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    return jsonify({"success": True, "categories": declarees}), 200


@bp.post("/categories/rattacher")
@exige_role(ORGANISATEUR)
def categories_rattacher():
    """{"apercu": true} montre; sans lui, ecrit. Spec 045, D6.

    Rattache les categories hors liste deja en base -- le « U13 M » du 30/08 --
    a leur equivalent officiel. L'apercu et l'application partagent la meme
    fonction de decision (`bareme.hors_liste`), pour la raison ecrite sur
    `/categories/appliquer` : un apercu calcule par un autre chemin finirait
    par annoncer ce qui ne se produit pas.
    """
    corps = _corps_objet() or {}
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    if corps.get("apercu"):
        return jsonify({"success": True, "rattaches": 0,
                        "hors_liste": bareme_module.hors_liste(comp)}), 200

    rapport = bareme_module.rattacher_hors_liste(
        comp, par=g.utilisateur.identifiant)
    if rapport["rattaches"]:
        classement_service.invalider(comp.id)
    return jsonify({"success": True, **rapport}), 200


@bp.post("/categories/appliquer")
@exige_role(ORGANISATEUR)
def categories_appliquer():
    """{"apercu": true} montre; sans lui, ecrit.

    L'apercu et l'application partagent la MEME fonction de decision : un
    apercu calcule par un autre chemin finirait par annoncer ce qui ne se
    produit pas.
    """
    corps = _corps_objet() or {}
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    forcer = bool(corps.get("forcer"))
    if corps.get("apercu"):
        rapport = bareme_module.apercu(comp, forcer=forcer)
    else:
        rapport = bareme_module.appliquer(
            comp, par=g.utilisateur.identifiant, forcer=forcer)
    return jsonify({"success": True, **rapport}), 200


@bp.post("/participants/<int:participant_id>/publication")
@exige_role(ORGANISATEUR)
def publication_participant_route(participant_id):
    """{"refusee": true} -> ce grimpeur ne parait plus sous son nom. Spec 043.

    C'est le geste qui rend le droit d'opposition (art. 21 RGPD) exercable un
    samedi matin, au telephone. Sans lui, satisfaire un parent supposait de
    SUPPRIMER le grimpeur -- ce qui decale le rang de tous ceux qui le suivent.

    Ici, la ligne reste : seul son nom devient « Dossard N » sur la page
    publique. La console, elle, continue d'afficher le vrai nom -- c'est elle
    qui sert a retrouver la personne.
    """
    corps = _corps_objet()
    if corps is None or "refusee" not in corps:
        return jsonify({"success": False, "message": "Champ « refusee » attendu"}), 400

    p = db.session.get(Participant, participant_id)
    if p is None:
        return jsonify({"success": False, "message": "Participant inconnu"}), 404

    p.publication_refusee = bool(corps["refusee"])
    db.session.add(p)
    db.session.commit()

    # ⚠️ Sans cette invalidation, le changement n'arriverait qu'au bout des 5 s
    # du cache de classement, plus les 5 s du cache de Caddy. L'organisateur
    # vient de raccrocher avec un parent : il regarde la page TOUT DE SUITE, et
    # un ecran qui n'obeit pas se lit comme une panne.
    classement_service.invalider(p.competition_id)

    logger.info("publication du nom %s pour %s par %s",
                "refusee" if p.publication_refusee else "retablie",
                p.nom_complet, g.utilisateur.identifiant)
    return jsonify({"success": True,
                    "participant": {**p.to_dict(),
                                    "publication_refusee": p.publication_refusee}}), 200


# --- Saisie manuelle --------------------------------------------------------
#
# Un QR illisible, un telephone a plat, un juge qui a oublie d'envoyer. Sans
# cette route, la reussite est perdue pour de bon -- et personne ne s'en apercoit
# avant le depouillement.

@bp.post("/reussites")
@exige_role(ORGANISATEUR)
def saisir_reussite():
    """{"bib": "...", "bloc": "..."} -> enregistre une reussite a la main."""
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        participant = participant_par_dossard(corps.get("bib"))
        bloc = bloc_par_tag(corps.get("bloc"))
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    reussite, nouvelle = enregistrer_reussite(
        participant, bloc,
        source=SOURCE_MANUEL,
        saisie_par=g.utilisateur.identifiant,
    )
    logger.info("saisie manuelle par %s : %s sur %s%s",
                g.utilisateur.identifiant, participant.nom_complet, bloc.tag,
                "" if nouvelle else " (deja connue)")
    return jsonify({
        "success": True,
        "nouvelle": nouvelle,
        "reussite": {"id": reussite.id, "grimpeur": participant.nom_complet,
                     "bloc": bloc.tag},
    }), 201


@bp.delete("/reussites/<int:reussite_id>")
@exige_role(ORGANISATEUR)
def supprimer_reussite_route(reussite_id):
    """Corrige une saisie erronee. Journalise QUI, QUOI et QUAND avant d'effacer."""
    try:
        trace = supprimer_reussite(reussite_id, par=g.utilisateur.identifiant)
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    return jsonify({"success": True, "supprimee": trace}), 200


# --- Le plan de la salle (spec 029) -----------------------------------------

@bp.get("/plan")
@exige_role(ORGANISATEUR)
def page_plan():
    """La planche de dessin du plan de la salle, servie DEPUIS la console.

    ⚠️ Elle vivait dans `tools/`, hors de l'application : changer le plan
    demandait de modifier du code et de redeployer. Adrien : « est-ce que tu as
    prevu une page dans la console qui permet de lancer l'outil [...] et
    d'injecter ce nouveau plan via un bouton ? Sinon il faut le faire. »
    """
    # Une seule lecture : la PR a justement ajoute un test de budget de
    # requetes pour ce motif, il aurait ete malvenu de le trahir ici.
    plan = fiches.plan_courant()
    return render_template("plan.html", plan=plan, profils=fiches.PROFILS,
                           usine=plan is fiches.PLAN)


@bp.post("/plan")
@exige_role(ORGANISATEUR)
def plan_enregistrer():
    """{"vue": [l, h], "murs": [...], "reperes": [...], "contour": [...] | null}"""
    from .. import plan_du_mur

    # ⚠️ La taille se controle AVANT d'analyser quoi que ce soit. La verifier
    # apres `valider()` et `json.dumps()` faisait construire quatre cent mille
    # tuples et serialiser le document avant de le refuser -- et rendait 400 la
    # ou la spec 029 F5 promet un 413.
    if (request.content_length or 0) > plan_du_mur.TAILLE_MAXI:
        return jsonify({"success": False,
                        "message": "Le plan dépasse la taille maximale."}), 413

    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        propre = plan_du_mur.ecrire(corps, par=getattr(utilisateur_courant(), "identifiant", None))
    except plan_du_mur.PlanInvalide as e:
        # Le message nomme le mur fautif : c'est ce qui permet de le corriger
        # sans relire tout le document.
        return jsonify({"success": False, "message": str(e)}), 400

    zones = sum(1 for m in propre["murs"] if m["zone"])
    return jsonify({
        "success": True,
        # ⚠️ On renvoie le plan TEL QU'IL A ETE RANGE. Le serveur repare en
        # silence -- zone mise en capitales et tronquee a trois, texte de
        # repere a vingt-quatre, profil inconnu replie -- et la page affirmait
        # ensuite « le plan enregistre est celui affiche ». Recoller un bloc
        # portant « abcd » laissait « abcd » a l'ecran quand le dossard
        # imprimait « ABC ».
        "plan": propre,
        "murs": len(propre["murs"]),
        "zones": zones,
        "reperes": len(propre["reperes"]),
        "message": (f"{len(propre['murs'])} mur(s) dont {zones} avec une lettre, "
                    f"{len(propre['reperes'])} repère(s) enregistrés. "
                    "Les prochains dossards imprimés porteront ce plan."),
    }), 200


@bp.delete("/plan")
@exige_role(ORGANISATEUR)
def plan_effacer():
    """Revient au plan d'usine — la sortie de secours d'un jour de competition."""
    from .. import plan_du_mur
    efface = plan_du_mur.effacer()
    return jsonify({
        "success": True,
        # Le plan d'usine, pour que la page reprenne CE qu'elle vient de
        # retablir et non ce qu'elle avait charge au depart.
        "plan": fiches.PLAN,
        "efface": efface,
        "message": ("Retour au plan d'usine." if efface
                    else "Aucun plan enregistré : c'est déjà le plan d'usine."),
    }), 200


# --- Impression des dossards ------------------------------------------------

@bp.get("/dossards")
@exige_role(ORGANISATEUR)
def page_dossards():
    """La planche a imprimer. `?dossard=42` pour un seul, `?categorie=U13 F` pour un lot.

    Format repris de l'onglet « Fiches » du classeur (spec 023) : une fiche A5
    par grimpeur, deux par A4. Elle porte son identite et son QR, mais aussi
    TOUS LES BLOCS DE SON CIRCUIT dans l'ordre de difficulte, et le plan de la
    salle avec ses zones allumees. La bande de trois centimetres qu'on imprimait
    avant ne lui disait rien de ce qu'il devait grimper.

    L'adresse garde le mot « dossard » : c'est toujours le numero qu'on imprime,
    et une URL n'est pas le produit. Seule la console parle de « fiches ».

    Le QR est genere LOCALEMENT -- le classeur, lui, appelle api.qrserver.com,
    ce qui envoie les dossards a un tiers et ne marche pas si la connexion
    tombe le matin de la competition.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    participants = Participant.query.filter_by(competition_id=comp.id).all()
    participants = [p for p in participants if p.dossard is not None]

    un_seul = request.args.get("dossard", type=int)
    categorie = (request.args.get("categorie") or "").strip()
    # `?dossards=12,47,128` : la SELECTION PAR CASES de la console (spec 008).
    # Elle remplace la tuile « Imprimer les fiches » et son champ « une
    # categorie (vide = toutes) » -- on filtre la liste, on coche, on imprime.
    #
    # Un numero illisible est ignore plutot que de faire echouer la planche :
    # le geste se fait debout, la file attend, et une planche de dix-neuf
    # fiches vaut mieux qu'une page d'erreur.
    choisis = [n for n in ((request.args.get("dossards") or "").split(","))
               if n.strip().isdigit()]

    if choisis:
        voulus = {int(n) for n in choisis}
        participants = [p for p in participants if p.dossard in voulus]
        titre = f"{len(participants)} fiche(s)"
    elif un_seul is not None:
        participants = [p for p in participants if p.dossard == un_seul]
        titre = f"dossard {un_seul}"
    elif categorie:
        participants = [p for p in participants if (p.categorie or "") == categorie]
        titre = categorie
    else:
        titre = comp.nom

    participants.sort(key=lambda p: p.dossard)
    planche = fiches.construire(comp, participants)

    logger.info("impression de %d fiche(s) par %s (%s)",
                len(planche), g.utilisateur.identifiant, titre)
    return render_template("dossards.html",
                           feuilles=fiches.en_feuilles(planche,
                                                       fiches.FICHES_PAR_FEUILLE),
                           total=len(planche), titre=titre,
                           # Les motifs de trame du plan sont declares une
                           # seule fois pour tout le document, pas par fiche.
                           profils=fiches.PROFILS)


@bp.get("/etiquettes")
@exige_role(ORGANISATEUR)
def page_etiquettes():
    """La planche a coller au mur. `?zone=Z` pour une zone, `?bloc=ZJ6` pour une.

    Le juge scanne DEUX QR : celui du grimpeur, puis celui du bloc. Le second
    est colle au mur, et rien ne savait l'imprimer -- preparer une competition
    demandait encore d'ouvrir le classeur et d'imprimer son onglet « Fiches ».
    Ces QR-la etaient produits par api.qrserver.com : un appel vers un tiers,
    qui ne marche pas si la connexion tombe la veille au soir, quand on colle
    les etiquettes.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    zone = (request.args.get("zone") or "").strip() or None
    tag = (request.args.get("bloc") or "").strip() or None
    planche = fiches.etiquettes(comp, zone=zone, tag=tag)

    if tag:
        filtre, titre = f"le bloc {tag}", f"bloc {tag}"
    elif zone:
        filtre, titre = f"la zone {zone}", f"zone {zone}"
    else:
        filtre, titre = None, comp.nom

    logger.info("impression de %d etiquette(s) par %s (%s)",
                len(planche), g.utilisateur.identifiant, titre)
    # ⚠️ Plus de saut de page par zone (correctif du 02/09). Il produisait des
    # feuilles a moitie vides -- une zone de cinq blocs laissait trois places
    # perdues, une zone d'un seul en gaspillait cinq. Les blocs sortent zone
    # par zone (`fiches.etiquettes` trie par zone) : le regroupement physique
    # est conserve sans payer une feuille par zone.
    return render_template("etiquettes.html",
                           feuilles=fiches.en_feuilles(planche,
                                                       fiches.ETIQUETTES_PAR_FEUILLE),
                           total=len(planche), titre=titre, filtre=filtre,
                           taille_numero=fiches.TAILLE_NUMERO_MM)


@bp.get("/postes")
@exige_role(ORGANISATEUR)
def page_postes():
    """Les QR de poste a poser sur les tables des juges. `?zone=C` pour une seule.

    Le juge arrive a sa table, ouvre l'application, scanne le carton pose
    devant lui : son telephone s'appelle « Zone C ». Il n'a rien tape.

    ⚠️ LES ZONES VIENNENT DU PLAN, jamais d'une liste tenue a la main (spec
    034). Un mur ajoute dans `/admin/plan` sort son QR a l'impression suivante.

    ⚠️ PAS DE `competition_active()`, donc PAS DE 409 : c'est la seule page
    d'impression de la console qui marche sans competition, et c'est voulu. Le
    plan de la salle ne depend d'aucune edition, et on imprime ces cartons la
    veille au soir, avant meme d'avoir importe le classeur.
    """
    zone = (request.args.get("zone") or "").strip() or None
    planche = fiches.postes(zone=zone)

    logger.info("impression de %d QR de poste par %s (%s)",
                len(planche), g.utilisateur.identifiant, zone or "toutes zones")
    # ⚠️ LA GEOMETRIE VIENT DU SERVEUR, pas du CSS : la densite (huit affiches
    # par A4) commande la hauteur d'une affiche, le nombre de colonnes et la
    # place laissee au nom. Ecrite en dur dans le gabarit, elle mentirait des
    # qu'on repasse a six.
    return render_template("postes.html",
                           feuilles=fiches.en_feuilles(planche,
                                                       fiches.POSTES_PAR_FEUILLE),
                           geo=fiches.geometrie_postes(),
                           mot_zone=fiches.MOT_ZONE,
                           total=len(planche), filtre=zone)


def _corps_objet():
    """Le corps JSON s'il est bien un objet, sinon None.

    Meme garde que sur les routes des juges : un corps qui n'est pas un objet
    doit donner 400, jamais 500.
    """
    corps = request.get_json(silent=True)
    return corps if isinstance(corps, dict) else None


MODE_MISE_A_JOUR = "mise_a_jour"
MODE_REMPLACER = "remplacer"
MODES_IMPORT = (MODE_MISE_A_JOUR, MODE_REMPLACER)


@bp.post("/import/sheet")
@exige_role(ORGANISATEUR)
def importer_classeur():
    """Relit le classeur et met la base a jour.

    Sur COMMANDE, jamais dans le chemin d'une requete juge (risque R7). Un
    dossard inconnu scanne en boucle ne doit pas pouvoir declencher des lectures
    Google en rafale.

    Deux modes depuis la spec 018 :

      mise_a_jour  ajoute ce qui manque, corrige ce qui a change. Le defaut,
                   et le comportement d'avant : c'est le geste du samedi matin.
      remplacer    efface les donnees de la competition active, PUIS importe.
                   Destructeur, donc reserve a ADMIN et confirme a la main.

    Le role est porte par le mode, et c'est le seul endroit du produit ou c'est
    le cas : `ORGANISATEUR` ne detruit rien, `ADMIN` seul peut remplacer.
    """
    global _dernier_rapport
    corps = _corps_objet() or {}
    mode = str(corps.get("mode") or MODE_MISE_A_JOUR).strip()
    if mode not in MODES_IMPORT:
        return jsonify({"success": False,
                        "message": f"Mode d'import inconnu « {mode} ». "
                                   f"Attendus : {', '.join(MODES_IMPORT)}."}), 400

    if mode == MODE_REMPLACER and not g.utilisateur.a_le_role(ADMIN):
        return jsonify({
            "success": False,
            "message": "Le remplacement complet efface les donnees du serveur : "
                       "il est reserve aux administrateurs. La mise a jour, "
                       "elle, reste ouverte."}), 403

    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    # La confirmation AVANT le reseau : refuser apres avoir fait travailler
    # Google pour rien serait gratuit, et ferait dependre un 400 d'un
    # aller-retour qui peut echouer.
    if mode == MODE_REMPLACER:
        try:
            cycle.exiger_confirmation(str(corps.get("confirmation") or ""))
            cycle.garde_en_cours(comp, bool(corps.get("forcer")))
        except ErreurMetier as e:
            return jsonify({"success": False, "message": e.message}), e.code

    try:
        classeur = parametrage.ClasseurGoogle(comp.spreadsheet_id)
        # ⚠️ On LIT avant d'effacer. Si Google refuse ici, la base n'a pas
        # bouge -- l'ordre inverse laisserait une base vide et un import qui
        # n'a jamais eu lieu.
        lecture = lire_tout(classeur)
    except ErreurClasseur as e:
        logger.warning("import refuse : %s", e)
        return jsonify({"success": False,
                        "message": f"{e} — rien n'a ete modifie."}), 502

    efface = None
    try:
        if mode == MODE_REMPLACER:
            efface = cycle.effacer_donnees(
                comp, str(corps.get("confirmation") or ""), bool(corps.get("forcer")))
        rapport = importer(comp, classeur, lecture=lecture)
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code
    except ErreurClasseur as e:
        db.session.rollback()
        logger.warning("import refuse : %s", e)
        return jsonify({"success": False, "message": str(e)}), 502

    _dernier_rapport = rapport.to_dict()
    _dernier_rapport["resume"] = rapport.resume()
    _dernier_rapport["mode"] = mode
    _dernier_rapport["efface"] = efface

    logger.info("%s a importe le classeur (mode %s) : %s",
                g.utilisateur.identifiant, mode, rapport.resume())
    return jsonify({"success": True, "rapport": _dernier_rapport}), 200


@bp.get("/import/rapport")
@exige_role(ORGANISATEUR)
def dernier_rapport():
    if _dernier_rapport is None:
        return jsonify({"success": True, "rapport": None,
                        "message": "Aucun import depuis le demarrage"}), 200
    return jsonify({"success": True, "rapport": _dernier_rapport}), 200


@bp.get("/circuits")
@exige_role(ORGANISATEUR)
def lister_circuits():
    """Les circuits, leurs blocs, et ce qui cloche — spec 019.

    `ORGANISATEUR` et non `ADMIN` : cette route ne fait que lire, et c'est la
    verification qu'on veut faire AVANT une competition, avec qui est la.

    L'interet principal n'est pas le tableau, c'est `anomalies` : un bloc
    rattache a aucun circuit ne compte pour personne, un circuit sans bloc rend
    un classement vide, et une categorie dont le circuit n'existe pas fait
    compter chaque reussite pour zero. Les trois sont SILENCIEUSES aujourd'hui
    et se paient a la remise des prix.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    return jsonify({"success": True, **circuits_module.inventaire(comp)}), 200


# --- Le classeur Google (spec 015) ------------------------------------------
#
# `ADMIN` et pas `ORGANISATEUR` : ces quatre routes decident OU vont les donnees
# et AVEC QUELLE identite Google. L'import, lui, reste organisateur — il ne fait
# que relire ce qui est deja relie.


@bp.get("/classeur")
@exige_role(ADMIN)
def classeur_etat():
    """Ce que la console affiche : classeur relie, jeton, compteurs.

    Aucun acces reseau : cette vue doit s'ouvrir meme quand Google est
    injoignable ou qu'aucun jeton n'est pose — c'est precisement dans ces
    moments-la qu'on vient la consulter.
    """
    comp = Competition.query.filter_by(active=True).first()
    etat = parametrage.etat(comp)
    # Le consentement se greffe ICI et non dans `parametrage.etat` : l'URI de
    # retour depend de la REQUETE (l'hote sur lequel on est arrive), et
    # `parametrage` ne connait pas Flask. `pret: false` desactive le bouton et
    # affiche pourquoi -- un bouton qui ne peut pas marcher ne doit pas etre
    # cliquable.
    etat["jeton"]["consentement"] = {
        **consentement.disponible(),
        "uri_retour": uri_de_retour(),
    }
    return jsonify({"success": True, **etat}), 200


@bp.post("/classeur/test")
@exige_role(ADMIN)
def classeur_test():
    """{"lien": "...", "ecriture": false}

    Lecture seule par defaut, sur le classeur relie ou sur un lien qu'on
    envisage. Pouvoir tester AVANT de relier est le seul moment ou l'on peut
    encore s'apercevoir qu'on avait la mauvaise feuille.

    Avec `"ecriture": true`, un aller-retour REEL est fait dans le coin de la
    grille (spec 018) : c'est la seule facon de detecter une feuille partagee
    en LECTURE SEULE avec le compte du jeton -- un cas qui passe tous les
    controles de lecture et ne se revele qu'apres le premier scan.
    """
    corps = _corps_objet() or {}
    comp = Competition.query.filter_by(active=True).first()
    lien = str(corps.get("lien") or "").strip()

    try:
        if lien:
            identifiant = parametrage.extraire_identifiant(lien)
        else:
            identifiant = (comp.spreadsheet_id or "").strip() if comp else ""
            if not identifiant:
                raise ErreurMetier(
                    "Aucun classeur relie a cette competition : colle un lien "
                    "pour l'essayer.", code=409)
        rapport = parametrage.tester(
            identifiant, comp, ecriture=bool(corps.get("ecriture")))
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    except ErreurClasseur as e:
        # 502 et pas 500 : la panne est chez Google (ou dans le partage de la
        # feuille), pas dans le serveur. Le message de Google est repris tel
        # quel — c'est lui qui dit « feuille introuvable » ou « acces refuse ».
        logger.warning("test du classeur refuse : %s", e)
        return jsonify({"success": False, "message": str(e)}), 502

    return jsonify({"success": True, "rapport": rapport}), 200


@bp.post("/classeur")
@exige_role(ADMIN)
def classeur_relier():
    """{"lien": "...", "mode": "relier|rejouer|reinitialiser", "confirmation": "..."}"""
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        comp = competition_active()
        identifiant = parametrage.extraire_identifiant(str(corps.get("lien") or ""))
        effets = parametrage.relier(
            comp, identifiant,
            mode=str(corps.get("mode") or parametrage.MODE_RELIER),
            confirmation=str(corps.get("confirmation") or ""),
            forcer=bool(corps.get("forcer")),
        )
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code
    except ErreurClasseur as e:
        # Le vidage du classeur a lieu AVANT toute suppression en base : si on
        # passe ici, la base n'a pas bouge. On le dit, parce que c'est
        # exactement la question que se pose celui qui lit le message.
        db.session.rollback()
        logger.warning("changement de classeur refuse : %s", e)
        return jsonify({"success": False,
                        "message": f"{e} — rien n'a ete modifie."}), 502

    logger.info("%s a relie le classeur %s (mode %s)",
                g.utilisateur.identifiant, identifiant, effets["mode"])
    return jsonify({"success": True, "effets": effets,
                    **parametrage.etat(comp)}), 200


# --- Le consentement Google, depuis la console (spec 022) --------------------
#
# Ces deux routes REDIRIGENT, elles ne rendent pas de JSON : c'est une
# navigation de page entiere, la seule chose que Google accepte. Le resultat
# revient a la console dans la requete (`/console?jeton=...`), jamais dans le
# fragment -- la console le lit, l'affiche, et nettoie l'URL.

def uri_de_retour() -> str:
    """L'URI que Google doit connaitre, au caractere pres."""
    return f"{base_publique()}/admin/classeur/google/retour"


def _retour_console(resultat: str, detail: str = "") -> Response:
    """Vers /console, avec un code COURT de notre cru.

    Jamais le message brut de Google : on ne recopie pas dans une URL ce qu'un
    tiers nous a envoye.
    """
    suite = f"&d={quote(detail, safe='')}" if detail else ""
    return redirect(f"/console?jeton={quote(resultat, safe='')}{suite}")


@bp.get("/classeur/google/consentement")
@exige_role(ADMIN)
def google_consentement():
    """302 vers Google. Le `state` part en session, jamais dans une reponse."""
    try:
        url, etat = consentement.url_de_consentement(uri_de_retour())
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    session[consentement.CLE_ETAT] = etat
    logger.info("%s ouvre le consentement Google", g.utilisateur.identifiant)
    return redirect(url)


@bp.get("/classeur/google/retour")
@exige_role(ADMIN)
def google_retour():
    """Le retour de Google : verifie, echange, ecrit, puis renvoie a la console.

    Le `state` est RETIRE de la session des la premiere lecture : un code
    d'autorisation ne se rejoue pas, et le `state` non plus.
    """
    attendu = session.pop(consentement.CLE_ETAT, None)

    if request.args.get("error"):
        # Consentement refuse : ce n'est pas une panne, c'est une reponse.
        logger.info("consentement Google refuse par %s", g.utilisateur.identifiant)
        return _retour_console("refuse")

    try:
        consentement.verifier_etat(attendu, request.args.get("state"))
        contenu = consentement.echanger(request.args.get("code", ""),
                                        uri_de_retour())
    except ErreurMetier as e:
        logger.warning("consentement Google non abouti : %s", e.message)
        return _retour_console("erreur", e.message)

    try:
        ecrire_jeton_json(contenu)
    except OSError as e:
        logger.exception("jeton non ecrit")
        return _retour_console("erreur", f"Ecriture impossible : {e}")

    # ⚠️ Le jeton n'apparait NI dans le journal, NI dans la reponse, NI dans
    # l'URL. Seul le fait qu'il ait ete pose est trace.
    logger.info("%s a pose un jeton Google par consentement",
                g.utilisateur.identifiant)
    return _retour_console("pose")


@bp.post("/classeur/jeton")
@exige_role(ADMIN)
def classeur_jeton():
    """{"jeton": "<le JSON produit par tools/exporter_jeton.py>"}

    Du JSON, jamais un pickle : voir `parametrage.poser_jeton`. Le jeton n'est
    ni journalise, ni renvoye — seul son etat l'est.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        etat = parametrage.poser_jeton(str(corps.get("jeton") or ""))
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    except OSError as e:
        logger.exception("jeton non ecrit")
        return jsonify({"success": False,
                        "message": f"Ecriture du jeton impossible : {e}"}), 500

    logger.info("%s a pose un nouveau jeton Google", g.utilisateur.identifiant)
    return jsonify({"success": True, "jeton": etat}), 200


# --- Le cycle de vie de l'edition (spec 018) ---------------------------------
#
# Trois gestes destructeurs ou irreversibles (`ADMIN`), deux gestes de
# consultation et un d'etiquetage (`ORGANISATEUR`). La regle est celle de la
# spec 015 : decider ou vont les donnees est plus grave que les relire.


@bp.get("/competition")
@exige_role(ORGANISATEUR)
def competition_etat():
    """Le nom, la date, et la liste des classements a cocher — spec 020.

    `groupes` vient du cache de classement, pas d'un calcul force : la liste
    des groupes ne change qu'a l'import.
    """
    from ..classement_service import classements

    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    tous, _ = classements(comp)
    groupes = [{"nom": c.groupe, "type": c.type, "circuit": c.circuit,
                "participants": len(c.lignes)}
               # ⚠️ L'ordre vient de `classement_service.ordre` -- la MEME
               # regle que la page publique. La console la reimplementait en
               # JavaScript : deux versions d'une regle metier, dans deux
               # langages, divergent toujours. Elles divergeaient deja sur le
               # circuit absent et sur la comparaison des chaines.
               for c in sorted(tous.values(), key=classement_service.ordre)]

    return jsonify({
        "success": True,
        "competition": {"id": comp.id, "nom": comp.nom,
                        "date": comp.date.isoformat() if comp.date else None,
                        "statut": comp.statut},
        "groupes": groupes,
        "groupes_masques": cycle.groupes_masques(comp),
        "sources_inscriptions": cycle.sources_inscriptions(comp),
    }), 200


@bp.post("/competition")
@exige_role(ADMIN)
def competition_renommer():
    """{"nom": "...", "date": "AAAA-MM-JJ"} — les deux facultatifs.

    `ADMIN` : ce nom part sur un ECRAN PUBLIC (le bandeau de la page de
    resultats) et dans le nom de fichier des archives.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        comp = competition_active()
        etat = cycle.renommer(comp, corps.get("nom"), corps.get("date"))
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("%s a renomme la competition %s en %r",
                g.utilisateur.identifiant, comp.id, comp.nom)
    return jsonify({"success": True, "competition": etat}), 200


@bp.post("/competition/affichage")
@exige_role(ADMIN)
def competition_affichage():
    """{"groupes_masques": ["U19 F"]} — ce que la page de resultats ne montre pas.

    On range ce qu'on CACHE, jamais ce qu'on montre : une categorie creee en
    cours de journee doit apparaitre, pas disparaitre en silence. Voir
    `cycle.groupes_masques`.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        comp = competition_active()
        masques = cycle.regler_affichage(comp, corps.get("groupes_masques"))
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("%s a masque %d classement(s) sur la competition %s",
                g.utilisateur.identifiant, len(masques), comp.id)
    return jsonify({"success": True, "groupes_masques": masques}), 200


@bp.get("/competition/cascade")
@exige_role(ADMIN)
def competition_cascade_etat():
    """La regle de cascade, les categories, et de quoi peindre l'apercu.

    L'apercu a besoin du nombre de blocs PAR COULEUR ET PAR CIRCUIT : une
    couleur absente d'un circuit ne peut pas etre pleine (D3), et c'est
    exactement ce qu'il faut montrer avant d'enregistrer.
    """
    from ..classement_service import cascade as cascade_de
    from ..models import Bloc, BlocCircuit, Circuit

    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    courante = cascade_de(comp)

    categories = sorted(
        c for (c,) in db.session.query(Participant.categorie)
        .filter(Participant.competition_id == comp.id,
                Participant.categorie.isnot(None))
        .distinct().all()
        if c and c.strip()
    )

    # Tous les circuits de l'edition, meme ceux sans un seul bloc colore : un
    # circuit absent de cette table disparait du menu de l'apercu, et le reglage
    # se fait alors a l'aveugle sur ce circuit-la.
    from ..classement import couleur_canonique
    par_nom: dict[str, dict] = {
        nom: {"nom": nom, "couleurs": {}, "blocs": 0, "sans_couleur": 0}
        for (nom,) in db.session.query(Circuit.nom)
        .filter(Circuit.competition_id == comp.id).all()
    }
    for nom, couleur in (
        db.session.query(Circuit.nom, Bloc.couleur)
        .join(BlocCircuit, BlocCircuit.circuit_id == Circuit.id)
        .join(Bloc, BlocCircuit.bloc_id == Bloc.id)
        .filter(Circuit.competition_id == comp.id,
                # ⚠️ Sans ce filtre, un lien vers un bloc d'une AUTRE edition
                # serait compte ici et ignore par le moteur, qui borne ses blocs
                # a la competition. L'apercu existe pour eviter cet ecart-la.
                Bloc.competition_id == comp.id)
        .all()
    ):
        circuit = par_nom[nom]
        circuit["blocs"] += 1
        # La meme normalisation que le moteur : le classeur ecrit « rouge »
        # aussi bien que « Rouge », et l'apercu doit compter comme il compte.
        propre = couleur_canonique(couleur)
        if propre is None:
            # Un bloc sans couleur compte au classement mais aucune cascade ne
            # le credite. Le taire ferait mentir le denominateur de l'apercu.
            circuit["sans_couleur"] += 1
            continue
        circuit["couleurs"][propre] = circuit["couleurs"].get(propre, 0) + 1

    return jsonify({
        "success": True,
        "cascade": cascade_module.en_json(courante),
        "couleurs": cascade_module.COULEURS,
        "categories": categories,
        "circuits": [par_nom[nom] for nom in sorted(par_nom)],
        "regle_du_classeur": cascade_module.en_json(
            cascade_module.Cascade(phrases=cascade_module.regle_du_classeur())),
    }), 200


@bp.post("/competition/cascade")
@exige_role(ADMIN)
def competition_cascade_regler():
    """{"actif": true, "regles": [...], "categories_eteintes": [...]}

    `ADMIN` : ce reglage change le CLASSEMENT, pas son affichage. Une regle
    declenchee par une seule couleur pleine changeait 264 rangs sur 392 sur les
    donnees reelles de novembre 2025.

    Ce qui bloque rend 400 sans rien ecrire ; ce qui merite seulement d'etre dit
    revient dans `avertissements`.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        comp = competition_active()
        # ⚠️ Une cle ABSENTE ne vaut pas une liste vide. `ecrire_options`
        # promet de ne jamais ecraser ce qu'on ne touche pas ; a l'interieur du
        # sous-document, c'est a nous de tenir la meme promesse. Sans ca, un
        # appel qui omet `categories_eteintes` rallume toutes les categories et
        # recredite leurs blocs, en repondant 200.
        if "categories_eteintes" not in corps:
            from ..classement_service import cascade as cascade_de
            corps = dict(corps)
            corps["categories_eteintes"] = sorted(
                cascade_de(comp).categories_eteintes)
        document, avertissements = cascade_module.valider(corps)
        cycle.ecrire_options(comp, cascade=document)
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code

    # Sans ca, le reglage ne se verrait qu'au bout de cinq secondes -- assez
    # pour qu'on le croie sans effet et qu'on recommence.
    from ..classement_service import invalider
    invalider(comp.id)

    logger.info("%s a regle la cascade de la competition %s : %d regle(s), "
                "%d categorie(s) eteinte(s)",
                g.utilisateur.identifiant, comp.id,
                len(document["regles"]), len(document["categories_eteintes"]))
    return jsonify({"success": True, "cascade": document,
                    "avertissements": avertissements}), 200


@bp.post("/competition/sources")
@exige_role(ADMIN)
def competition_sources():
    """D'ou viennent les inscrits. `{"sources": ["classeur", "helloasso"]}`.

    ⚠️ Decocher HelloAsso **ne supprime rien** : la cle, le formulaire et la
    correspondance restent en place, et reviennent tels quels a la
    reactivation. Un reglage qui efface en se desactivant n'est pas un
    interrupteur, c'est un piege.

    Pour effacer vraiment, il y a « Debrancher » sur l'ecran HelloAsso, qui dit
    ce qu'il fait.
    """
    corps = _corps_objet() or {}
    try:
        comp = competition_active()
        sources = cycle.regler_sources(comp, corps.get("sources") or [])
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    # Le fil suit le reglage sans attendre le prochain tour : on l'allume ou on
    # le laisse s'endormir de lui-meme.
    if "helloasso" in sources and ha_client.configure():
        ha_planificateur.reveiller()
        ha_planificateur.demarrer(current_app._get_current_object())

    logger.info("sources d'inscrits reglees par %s : %s",
                g.utilisateur.identifiant, sources)
    return jsonify({"success": True, "sources": sources}), 200


@bp.post("/competition/statut")
@exige_role(ORGANISATEUR)
def competition_statut():
    """{"statut": "preparation|en_cours|terminee"}

    `ORGANISATEUR` : ca ne detruit rien, et c'est le geste de celui qui ouvre la
    journee. Le statut ne commande RIEN dans le produit -- c'est une etiquette,
    qui n'arme que l'avertissement de l'effacement.

    Avant la spec 018, ce champ etait ecrit a la creation et plus jamais :
    `preparation` pour toujours sur une competition creee normalement,
    `en_cours` pour toujours sur une competition semee. La garde qui s'y
    appuyait ne se declenchait donc jamais quand il aurait fallu, et toujours
    quand il ne fallait pas.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        comp = competition_active()
        ancien = cycle.regler_statut(comp, str(corps.get("statut") or ""))
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("%s a passe la competition %s de %s a %s",
                g.utilisateur.identifiant, comp.id, ancien, comp.statut)
    return jsonify({"success": True, "ancien": ancien, "statut": comp.statut,
                    "statuts": list(cycle.STATUTS)}), 200


@bp.post("/donnees/effacer")
@exige_role(ADMIN)
def donnees_effacer():
    """{"confirmation": "EFFACER", "forcer": false}

    Efface les donnees de la competition ACTIVE, et rien d'autre : ni les
    autres competitions, ni les comptes, ni les archives, ni une seule cellule
    du classeur Google. Le classeur reste relie -- on efface le plus souvent
    pour reimporter proprement la meme feuille.
    """
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        comp = competition_active()
        efface = cycle.effacer_donnees(
            comp, str(corps.get("confirmation") or ""), bool(corps.get("forcer")))
        db.session.commit()
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code

    logger.warning("%s a EFFACE les donnees de la competition %s : %s",
                   g.utilisateur.identifiant, comp.id, efface)
    return jsonify({"success": True, "efface": efface,
                    "compteurs": cycle.compteurs(comp)}), 200


@bp.post("/archives")
@exige_role(ADMIN)
def archiver_competition():
    """Fige le classement de la competition active et la passe « terminee »."""
    try:
        comp = competition_active()
        archive, avertissements = cycle.archiver(comp, g.utilisateur.identifiant)
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("%s a archive la competition %s (archive %s)",
                g.utilisateur.identifiant, comp.id, archive.id)
    return jsonify({"success": True, "archive": archive.resume(),
                    "avertissements": avertissements}), 200


@bp.get("/archives")
@exige_role(ORGANISATEUR)
def archives_liste():
    """La liste, sans jamais desérialiser le contenu des archives."""
    return jsonify({"success": True, "archives": cycle.lister()}), 200


def _archive_ou_404(identifiant: int):
    archive = db.session.get(Archive, identifiant)
    if archive is None:
        raise ErreurMetier(f"Archive {identifiant} introuvable.", code=404)
    return archive


@bp.get("/archives/<int:identifiant>/classement")
@exige_role(ORGANISATEUR)
def archive_classement(identifiant: int):
    """Le classement fige, dans la forme exacte de /api/public/classement.

    C'est ce que consomme la page de resultats en mode archive. Rien n'est
    recalcule : l'archive est indépendante du moteur de classement, celui
    d'aujourd'hui comme celui de dans trois ans.

    Derriere la session, contrairement a la page publique : le classement d'une
    edition passee n'a pas a etre servi a qui passe, et il porte des noms de
    mineurs.
    """
    try:
        archive = _archive_ou_404(identifiant)
        charge = cycle.classement_archive(archive)
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    # L'age d'un classement fige n'a aucun sens : la page n'a rien a rafraichir.
    charge = {**charge, "archive": archive.resume(), "age_s": None}
    return jsonify(charge), 200


@bp.get("/archives/<int:identifiant>/fichier")
@exige_role(ORGANISATEUR)
def archive_fichier(identifiant: int):
    """Le JSON complet, en telechargement — une copie hors de la VM."""
    from flask import Response

    try:
        archive = _archive_ou_404(identifiant)
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    # Le nom du fichier porte la date : c'est ce qu'on cherche des mois plus
    # tard dans un dossier de telechargements. Reduit a l'ASCII sans espaces,
    # parce qu'un `Content-Disposition` accentue ne traverse pas tous les
    # navigateurs de la meme facon.
    lisible = "".join(c if (c.isascii() and c.isalnum()) else "-"
                      for c in (archive.nom or "archive"))
    lisible = "-".join(filtre for filtre in lisible.split("-") if filtre).lower()
    # Un nom entierement non-ASCII (ou vide) ne doit pas donner « …-.json ».
    nom = f"climbcontest-{archive.date.isoformat()}-{lisible or 'archive-sans-nom'}.json"

    return Response(
        archive.contenu, mimetype="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'})


@bp.delete("/archives/<int:identifiant>")
@exige_role(ADMIN)
def archive_supprimer(identifiant: int):
    """{"confirmation": "EFFACER"} — une archive ne se reconstruit pas."""
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400

    try:
        archive = _archive_ou_404(identifiant)
        cycle.exiger_confirmation(str(corps.get("confirmation") or ""))
        nom = archive.nom
        cycle.supprimer(archive)
    except ErreurMetier as e:
        db.session.rollback()
        return jsonify({"success": False, "message": e.message}), e.code

    logger.warning("%s a supprime l'archive %s (%s)",
                   g.utilisateur.identifiant, identifiant, nom)
    return jsonify({"success": True}), 200


# --- Tracabilite : quel telephone a envoye quoi (spec 011) -------------------

def base_publique() -> str:
    """« https://climbcontest.adn-dev.fr » — la racine telle qu'on la tape.

    Derriere Caddy, gunicorn voit du http : on force https partout sauf en
    developpement local. Pas de ProxyFix pour si peu -- mais cette regle sert
    maintenant a DEUX endroits (le lien de l'app juge, et l'URI de retour du
    consentement Google), et l'URI de retour doit correspondre AU CARACTERE PRES
    a celle declaree chez Google. Une seule regle, donc, et un seul endroit ou
    la changer.
    """
    hote = request.host
    schema = "http" if hote.split(":")[0] in (
        "localhost", "127.0.0.1", "10.0.2.2") else "https"
    return f"{schema}://{hote}"


@bp.get("/lien-juge")
@exige_role(ORGANISATEUR)
def lien_juge():
    """Le lien d'installation de l'application juge iPhone, et son QR.

    C'est la reponse a « sur quel site je dois aller ? » (Adrien, 30/08) : la
    spec 007 prevoyait un QR d'installation a afficher au mur, il n'existait
    pas. Le benevole scanne ce QR avec l'appareil photo de son iPhone, ouvre le
    lien, et la page range le jeton une fois pour toutes.

    Le jeton vit dans la REQUETE (`?j=`) depuis la spec 014. Il etait dans le
    fragment (`#j=`), qui a l'avantage de ne pas partir dans les journaux --
    mais un fragment n'est pas transmis a `start_url` du manifeste, donc
    l'application INSTALLEE demarrait sans jeton. Sur iPhone, ou le stockage
    d'une application de l'ecran d'accueil est cloisonne, elle ne pouvait pas le
    retrouver : « cette application a besoin du lien fourni par l'organisateur ».

    En requete, le jeton est porte par `start_url` et revient a chaque
    lancement, sur toutes les plateformes. Le prix -- sa presence dans les
    journaux -- est paye par un filtre sur le proxy, qui masque le parametre.

    Les anciens liens en `#j=` restent acceptes par l'application.

    Servi uniquement a un organisateur connecte -- le lien se transfere ensuite
    comme une cle de salle : de la main a la main.
    """
    cle = (os.environ.get("CLIMBCONTEST_API_KEY_PWA") or "").strip()
    if not cle:
        return jsonify({
            "success": False,
            "message": "Aucune cle PWA configuree : poser CLIMBCONTEST_API_KEY_PWA "
                       "sur le serveur (voir docs/runbook-competition.md).",
        }), 409

    url = f"{base_publique()}/juge?j={quote(cle, safe='')}"
    return jsonify({
        "success": True,
        "url": url,
        # Le QR est plus grand que celui d'un dossard : il se scanne a un
        # metre, affiche au mur, pas pose sur une table.
        "qr": qr.svg(url, cote_mm=70.0),
    }), 200


@bp.get("/appareils")
@exige_role(ORGANISATEUR)
def lister_appareils():
    """Les telephones vus sur la competition active, et leur derniere activite.

    Reserve aux comptes : la liste dit combien de reussites chaque poste a
    remontees, ce qui n'a aucune raison d'etre public.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    return jsonify({"success": True, "appareils": appareils(comp)}), 200


@bp.get("/versions")
@exige_role(ORGANISATEUR)
def lister_versions():
    """Ce que le serveur sert, et ce que les telephones en ont (spec 030).

    Une seule route pour les deux usages de la console : le pied de tiroir, qui
    l'affiche sur tous les ecrans, et la carte « Versions en circulation ».

    ⚠️ Les comptes se font par EGALITE STRICTE du numero de catalogue, jamais
    par comparaison d'ordre. Le numero identifie un couple (edition, etat de
    son catalogue) : il saute, et il saute pour toutes les editions a la fois
    quand le plan du mur change. « Plus grand » n'a aucun sens ici.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    liste = appareils(comp)
    return jsonify({
        "success": True,
        "serveur": version_module.resume(),
        "catalogue": {
            "version": comp.catalogue_version,
            "participants": Participant.query.filter_by(
                competition_id=comp.id).filter(
                    Participant.dossard.isnot(None)).count(),
            "blocs": Bloc.query.filter_by(competition_id=comp.id).count(),
        },
        "appareils": {
            "vus": len(liste),
            # `a_jour` compte les telephones dont les DEUX numeros collent. Un
            # telephone qui ne s'annonce pas n'est ni a jour ni en retard : il
            # est muet sur la question, et il ne doit gonfler aucun des deux
            # compteurs.
            "a_jour": sum(1 for a in liste
                          if a.get("app_a_jour") and a.get("catalogue_a_jour")),
            "en_retard": sum(1 for a in liste
                             if a.get("app_a_jour") is False
                             or a.get("catalogue_a_jour") is False),
            "muets": sum(1 for a in liste if a.get("silencieux")),
            # Le detecteur de cache (spec 030, F8). Zero en marche normale.
            "annonces_perdues": sum(1 for a in liste if a.get("annonce_perdue")),
            # Ceux qui sont en retard sur le catalogue mais le rattrapent tout
            # seuls -- typiquement juste apres un import ou un plan redessine,
            # qui renumerote toutes les editions d'un coup. Ce n'est pas une
            # panne, et la console doit le dire au lieu de virer au rouge.
            "rattrapage": sum(1 for a in liste if a.get("rattrapage")),
        },
    }), 200


@bp.get("/reussites-tracees")
@exige_role(ORGANISATEUR)
def chercher_reussites():
    """?ref=a1b2c3 ou ?appareil=... — « ce scan-la est-il arrive ? »

    Une reference introuvable donne `trouvee: false` plutot qu'une liste vide :
    « aucun resultat » et « je n'ai pas compris la question » ne doivent pas se
    ressembler quand quelqu'un cherche une reponse dans le feu de l'action.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    ref = (request.args.get("ref") or "").strip()
    appareil_id = (request.args.get("appareil") or "").strip() or None
    try:
        limite = int(request.args.get("limite", 100))
    except (TypeError, ValueError):
        limite = 100

    lignes = reussites_tracees(comp, ref=ref or None,
                               appareil_id=appareil_id, limite=limite)
    return jsonify({
        "success": True,
        "trouvee": bool(lignes) if ref else None,
        "reussites": lignes,
    }), 200


# --- Mise a jour du serveur (spec 031) --------------------------------------
#
# Trois routes, toutes reservees a un administrateur. Le raisonnement -- une
# verification par jour, pourquoi le minuteur a ete retire, pourquoi une
# competition en cours bloque -- est dans climbcontest/maj.py.


@bp.get("/maj")
@exige_role(ADMIN)
def maj_etat():
    """Ce que la console affiche : version en service, version disponible, et
    l'issue d'une installation recente s'il y en a eu une.

    C'est CETTE route qui declenche la verification quotidienne, quand elle est
    due. Il n'y a aucun minuteur : la console est le seul appelant, donc le
    quota GitHub n'est consomme que si quelqu'un regarde.
    """
    return jsonify({"success": True, **maj.etat(version_module.VERSION)}), 200


@bp.post("/maj/verifier")
@exige_role(ADMIN)
def maj_verifier():
    """Le bouton « Vérifier » : on interroge GitHub sans attendre l'echeance."""
    maj.verifier(force=True)
    return jsonify({"success": True, **maj.etat(version_module.VERSION)}), 200


@bp.post("/maj/installer")
@exige_role(ADMIN)
def maj_installer():
    """Le bouton « Installer ». Rend la main tout de suite : l'agent redemarre
    l'application quelques secondes plus tard, donc ce processus meme."""
    corps = request.get_json(silent=True) or {}
    try:
        lancee = maj.installer((corps.get("tag") or "").strip(),
                               par=g.utilisateur.identifiant)
    except maj.ErreurMaj as e:
        return jsonify({"success": False, "message": e.message}), e.code
    return jsonify({"success": True, "installation": lancee}), 202


# --- HelloAsso (spec 008) ----------------------------------------------------
#
# Le reglage de la cle est reserve aux ADMINISTRATEURS, comme le classeur : il
# manipule un secret. La correspondance et le releve, eux, sont des gestes
# d'organisateur -- ils se font le matin de la competition, par qui est devant
# l'ecran.

@bp.get("/helloasso")
@exige_role(ADMIN)
def helloasso_etat():
    """L'etat de la liaison. **Jamais le secret** -- voir `client.etat()`."""
    etat = ha_client.etat()
    try:
        comp = competition_active()
        etat["formulaire"] = ha_releve.reglages(comp)
    except ErreurMetier:
        pass                              # pas de competition : l'etat de la cle suffit
    etat["dernier_releve"] = ha_planificateur.dernier_releve()
    etat["derniere_erreur"] = ha_planificateur.derniere_erreur()
    return jsonify({"success": True, **etat}), 200


@bp.post("/helloasso/cle")
@exige_role(ADMIN)
def helloasso_poser_cle():
    """Pose la cle et demande un premier jeton, pour verifier tout de suite."""
    corps = _corps_objet() or {}
    try:
        ha_client.ecrire_secret(corps.get("client_id", ""),
                                corps.get("client_secret", ""),
                                corps.get("environnement") or ha_client.PRODUCTION)
        ha_client.ClientHelloAsso().jeton()
    except ha_client.ErreurHelloAsso as e:
        # Une cle qui ne marche pas ne RESTE PAS posee : la laisser ferait
        # demarrer le fil sur une cle morte, et bruler le quota
        # d'authentification jusqu'a rendre la reconnexion impossible.
        ha_client.effacer_secret()
        return jsonify({"success": False, "message": e.message}), 400

    # ⚠️ Le fil ne demarre qu'au lancement de l'application, et il ne demarre
    # PAS sans cle. Sans ce reveil, poser la cle depuis la console ne
    # declencherait rien jusqu'au prochain redemarrage -- et le symptome serait
    # « HelloAsso est relie mais rien n'arrive », le matin de la competition.
    ha_planificateur.reveiller()
    ha_planificateur.demarrer(current_app._get_current_object())

    # Poser la cle DECOUVRE l'association et ses formulaires. C'est tout
    # l'ecart entre « relier » et « configurer » : l'organisateur colle deux
    # chaines et voit aussitot le nom de son club, ce qui est la seule preuve
    # qui l'interesse.
    decouverte = _decouvrir_helloasso()

    logger.info("cle HelloAsso posee par %s", g.utilisateur.identifiant)
    return jsonify({"success": True, **ha_client.etat(), **decouverte}), 200


@bp.delete("/helloasso/cle")
@exige_role(ADMIN)
def helloasso_retirer_cle():
    ha_client.effacer_secret()
    logger.info("cle HelloAsso retiree par %s", g.utilisateur.identifiant)
    return jsonify({"success": True, "configure": False}), 200


def _decouvrir_helloasso() -> dict:
    """L'association et ses formulaires, sans rien demander a personne.

    Ne leve jamais : une decouverte qui echoue laisse la cle posee et l'ecran
    utilisable. C'est le releve qui dira, plus tard, ce qui ne va pas.
    """
    try:
        client = ha_client.ClientHelloAsso()
        organisations = client.organisations()
        if not organisations:
            return {"organisations": [], "formulaires": []}
        slug = organisations[0]["slug"]
        formulaires = [{"nom": f.get("title"), "type": f.get("formType"),
                        "slug": f.get("formSlug")}
                       for f in client.formulaires(slug)]
        return {"organisations": organisations, "formulaires": formulaires}
    except ha_client.ErreurHelloAsso as e:
        logger.info("decouverte HelloAsso impossible : %s", e.message)
        return {"organisations": [], "formulaires": [], "erreur": e.message}


@bp.get("/helloasso/formulaires")
@exige_role(ADMIN)
def helloasso_formulaires():
    """L'association et ses formulaires. **Aucun parametre a fournir.**"""
    return jsonify({"success": True, **_decouvrir_helloasso()}), 200


@bp.post("/helloasso/tester")
@exige_role(ADMIN)
def helloasso_tester():
    """« Est-ce que ca marche ? » — la reponse en une phrase verifiable.

    Un verdict qui dit seulement « relie » ne prouve rien a celui qui le lit :
    il pourrait etre relie a la mauvaise association. Celui-ci nomme le club,
    compte les formulaires, et va jusqu'a compter les inscriptions du
    formulaire choisi -- trois faits qu'un humain reconnait ou non.

    **Lecture seule**, comme « Tester l'acces » du classeur.
    """
    try:
        client = ha_client.ClientHelloAsso()
        organisations = client.organisations()
    except ha_client.ErreurHelloAsso as e:
        return jsonify({"success": False, "message": e.message}), e.code

    if not organisations:
        return jsonify({"success": False,
                        "message": "La cle ne donne acces a aucune association."}), 409

    resultat = {"association": organisations[0]["nom"],
                "slug": organisations[0]["slug"]}
    try:
        resultat["formulaires"] = len(client.formulaires(organisations[0]["slug"]))
    except ha_client.ErreurHelloAsso:
        resultat["formulaires"] = None

    try:
        comp = competition_active()
        config = ha_releve.reglages(comp)
        if config.get("form_slug"):
            articles = client.echantillon(
                config.get("organisation") or organisations[0]["slug"],
                config["form_type"], config["form_slug"])
            resultat["formulaire"] = config["form_slug"]
            resultat["inscriptions"] = len(articles)
    except (ErreurMetier, ha_client.ErreurHelloAsso):
        pass

    logger.info("test HelloAsso par %s : %s", g.utilisateur.identifiant, resultat)
    return jsonify({"success": True, **resultat}), 200


@bp.post("/helloasso/formulaire")
@exige_role(ORGANISATEUR)
def helloasso_choisir_formulaire():
    """Choisit le formulaire de l'edition, et DEVINE ce que veulent dire ses champs.

    « Lors des imports je veux un maximum d'automatisation » (Adrien, 04/09).
    Choisir le formulaire lit un echantillon d'articles, reconnait les champs
    -- par leur nom, et a defaut par leurs reponses -- et pre-remplit la
    correspondance. Il ne reste a l'organisateur qu'a regarder et corriger.

    ⚠️ Rien n'est devine EN SILENCE : la reponse porte `trouves`, et la console
    dit ce qu'elle a reconnu toute seule. Une reconnaissance muette
    transformerait une erreur de colonne en cent inscriptions mal rangees, sans
    que personne sache ou regarder.

    Un formulaire encore vide -- aucune inscription -- ne fait pas echouer le
    choix : on enregistre, et la reconnaissance se refera au premier releve.
    """
    corps = _corps_objet() or {}
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    type_de_formulaire = (corps.get("form_type") or "").strip()
    slug = (corps.get("form_slug") or "").strip()
    if not (type_de_formulaire and slug):
        return jsonify({"success": False,
                        "message": "Le type et le formulaire sont attendus"}), 400

    # L'association ne se saisit plus : la cle la connait.
    organisation = (corps.get("organisation") or "").strip()
    if not organisation:
        try:
            trouvees = ha_client.ClientHelloAsso().organisations()
            organisation = trouvees[0]["slug"] if trouvees else ""
        except ha_client.ErreurHelloAsso as e:
            return jsonify({"success": False, "message": e.message}), e.code
    if not organisation:
        return jsonify({"success": False,
                        "message": "La cle ne donne acces a aucune association."}), 409

    ancien = ha_releve.reglages(comp)
    devine = {"champs": {}, "genre_valeurs": {}, "trouves": [],
              "genres_inconnus": []}
    champs_vus = {}
    try:
        client = ha_client.ClientHelloAsso()
        articles = client.echantillon(organisation, type_de_formulaire, slug)
        champs_vus = ha_correspondance.champs_du_formulaire(articles)
        devine = ha_correspondance.deviner(champs_vus)
    except ha_client.ErreurHelloAsso as e:
        # Le formulaire s'enregistre quand meme : on ne perd pas le choix pour
        # une reconnaissance qui n'a pas pu se faire.
        logger.info("reconnaissance des champs impossible : %s", e.message)

    # Ce qui a ete regle A LA MAIN n'est jamais ecrase par une proposition.
    champs_retenus = dict(devine["champs"])
    for role, valeur in (ancien.get("champs") or {}).items():
        if valeur:
            champs_retenus[role] = valeur

    cycle.ecrire_options(comp, helloasso={
        **ancien,
        "organisation": organisation,
        "form_type": type_de_formulaire,
        "form_slug": slug,
        "champs": champs_retenus,
        "genre_valeurs": {**devine["genre_valeurs"],
                          **(ancien.get("genre_valeurs") or {})},
    })
    logger.info("formulaire HelloAsso choisi par %s : %s (reconnu : %s)",
                g.utilisateur.identifiant, slug, ", ".join(devine["trouves"]) or "rien")
    return jsonify({"success": True, "formulaire": ha_releve.reglages(comp),
                    "trouves": devine["trouves"],
                    "genres_inconnus": devine["genres_inconnus"],
                    "champs_vus": champs_vus}), 200


@bp.post("/helloasso/champs")
@exige_role(ORGANISATEUR)
def helloasso_champs():
    """Range les trois champs et les reponses de genre.

    Un seul refus, et c'est celui qui evite cent inscriptions bloquees sans
    qu'on comprenne pourquoi : sans champ d'annee de naissance, aucune
    categorie ne se calcule.
    """
    corps = _corps_objet() or {}
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    champs = corps.get("champs") or {}
    if not (champs.get("naissance") or "").strip():
        return jsonify({
            "success": False,
            "message": "Aucun champ de date de naissance : aucune categorie ne "
                       "pourra se calculer.",
        }), 400

    cycle.ecrire_options(comp, helloasso={
        **ha_releve.reglages(comp),
        "champs": {c: (champs.get(c) or "").strip() or None
                   for c in ("naissance", "genre", "club")},
        "genre_valeurs": corps.get("genre_valeurs") or {},
    })
    return jsonify({"success": True, "formulaire": ha_releve.reglages(comp)}), 200


@bp.post("/helloasso/relever")
@exige_role(ORGANISATEUR)
def helloasso_relever():
    """Le bouton « Relever maintenant ». `{"tout": true}` repart du debut."""
    corps = _corps_objet() or {}
    try:
        comp = competition_active()
        rapport = ha_releve.relever(comp, tout=bool(corps.get("tout")))
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    except ha_client.ErreurHelloAsso as e:
        return jsonify({"success": False, "message": e.message}), e.code
    return jsonify({"success": True, **rapport.to_dict()}), 200


# --- Les inscriptions --------------------------------------------------------

@bp.get("/inscriptions")
@exige_role(ORGANISATEUR)
def inscriptions_lister():
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    return jsonify({"success": True, **ha_salle.piles(comp),
                    "en_attente": ha_salle.en_attente(comp),
                    "a_imprimer_dossards": ha_salle.dossards_a_imprimer(comp)}), 200


@bp.post("/inscriptions/<int:identifiant>/trancher")
@exige_role(ORGANISATEUR)
def inscription_trancher(identifiant):
    corps = _corps_objet() or {}
    try:
        comp = competition_active()
        inscription = ha_salle.trancher(
            comp, identifiant, (corps.get("choix") or "").strip(),
            par=g.utilisateur.identifiant,
            participant_id=corps.get("participant_id"),
            categorie=corps.get("categorie"))
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    return jsonify({"success": True, "inscription": inscription.to_dict()}), 200


@bp.post("/inscriptions/<int:identifiant>/remise")
@exige_role(ORGANISATEUR)
def inscription_remise(identifiant):
    try:
        comp = competition_active()
        inscription = ha_salle.remise(comp, identifiant,
                                      par=g.utilisateur.identifiant)
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    return jsonify({"success": True, "inscription": inscription.to_dict()}), 200


# --- Les doublons (spec 008, 04/09) ------------------------------------------
#
# « Je ne veux pas de doublon. » Le formatage unifie et la garde d'ajout
# empechent d'en CREER de nouveaux ; ces deux routes traitent ceux qui sont
# deja la -- une base qui a vecu avant le 04/09, ou un import de classeur ecrit
# a la main.

@bp.get("/doublons")
@exige_role(ORGANISATEUR)
def doublons_lister():
    """Les groupes de participants qui sont probablement la meme personne.

    Meme identite normalisee **et** meme club : c'est la seule combinaison qui
    autorise a parler de doublon. Deux homonymes de clubs differents existent
    vraiment (risque R5), et les melanger en perdrait un.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    groupes = {}
    for p in Participant.query.filter_by(competition_id=comp.id):
        cle = (formatage.identite(p.nom, p.prenom), formatage.identite_club(p.club))
        if not cle[0] or not cle[1]:
            continue                       # sans nom ou sans club : on ne conclut pas
        groupes.setdefault(cle, []).append(p)

    doubles = []
    for (identite, _), gens in sorted(groupes.items()):
        if len(gens) < 2:
            continue
        gens.sort(key=lambda p: (p.dossard is None, p.dossard or 0, p.id))
        doubles.append({
            "identite": identite,
            "participants": [{
                **p.pour_la_console(),
                "reussites": len(p.reussites),
            } for p in gens],
        })
    return jsonify({"success": True, "doublons": doubles}), 200


@bp.post("/doublons/fusionner")
@exige_role(ORGANISATEUR)
def doublons_fusionner():
    """Fusionne deux participants. `{"garder": id, "absorber": id}`.

    Ce que ca fait, dans cet ordre :

    1. les REUSSITES de l'absorbe passent au gardé -- sauf celles qui feraient
       doublon sur un meme bloc, qui sont simplement supprimees. La contrainte
       `uq_reussite` interdirait l'insertion, et perdre une reussite deja
       presente chez l'autre ne perd rien ;
    2. les champs vides du gardé sont completes par ceux de l'absorbe ;
    3. les inscriptions HelloAsso de l'absorbe sont rattachees au gardé ;
    4. l'absorbe est supprime, et son dossard redevient libre.

    ⚠️ On ne choisit PAS lequel garder : c'est l'organisateur qui le dit. Le
    dossard survivant est celui qui est deja imprime et distribue -- le serveur
    n'a aucun moyen de savoir lequel.
    """
    corps = _corps_objet() or {}
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    garde = db.session.get(Participant, corps.get("garder"))
    absorbe = db.session.get(Participant, corps.get("absorber"))
    if garde is None or absorbe is None:
        return jsonify({"success": False, "message": "Participant inconnu"}), 404
    if garde.id == absorbe.id:
        return jsonify({"success": False,
                        "message": "Les deux fiches sont la meme"}), 400
    if comp.id not in (garde.competition_id, absorbe.competition_id) \
            or garde.competition_id != absorbe.competition_id:
        return jsonify({"success": False,
                        "message": "Les deux fiches ne sont pas de la meme competition"}), 409

    # ⚠️ Les reussites se deplacent par une MISE A JOUR, pas en reaffectant
    # `participant_id` sur des objets encore accroches a `absorbe.reussites`.
    #
    # La relation porte `cascade="all, delete-orphan"` : tant qu'un objet est
    # dans la collection, supprimer le participant l'emporte -- meme si sa cle
    # etrangere vient d'etre changee. Le test l'a montre : les reussites
    # disparaissaient au lieu de changer de main, ce qui est exactement le
    # contraire de ce que « fusionner » promet.
    deja = {r.bloc_id for r in garde.reussites}
    a_deplacer = [r.id for r in absorbe.reussites if r.bloc_id not in deja]
    en_double = [r.id for r in absorbe.reussites if r.bloc_id in deja]
    deplacees, doublons_de_reussite = len(a_deplacer), len(en_double)

    if en_double:
        # Perdre une reussite deja presente chez l'autre ne perd rien : la
        # contrainte `uq_reussite` interdirait de toute facon l'insertion.
        Success.query.filter(Success.id.in_(en_double)).delete(
            synchronize_session=False)
    if a_deplacer:
        Success.query.filter(Success.id.in_(a_deplacer)).update(
            {"participant_id": garde.id}, synchronize_session=False)
    db.session.expire(absorbe)
    db.session.expire(garde)

    for champ in ("prenom", "club", "categorie", "annee_naissance"):
        if getattr(garde, champ) in (None, "") and getattr(absorbe, champ):
            setattr(garde, champ, getattr(absorbe, champ))
    if garde.dossard is None and absorbe.dossard is not None:
        garde.dossard = absorbe.dossard
        absorbe.dossard = None

    for inscription in list(absorbe.inscriptions):
        inscription.participant_id = garde.id
        db.session.add(inscription)

    db.session.add(garde)
    db.session.flush()
    db.session.delete(absorbe)
    incrementer_catalogue(comp)
    db.session.commit()

    logger.info("doublon fusionne par %s : %s absorbe dans %s "
                "(%d reussite(s) deplacee(s), %d en double)",
                g.utilisateur.identifiant, absorbe.id, garde.id,
                deplacees, doublons_de_reussite)
    return jsonify({"success": True, "participant": garde.pour_la_console(),
                    "reussites_deplacees": deplacees,
                    "reussites_en_double": doublons_de_reussite}), 200
