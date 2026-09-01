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

from flask import Blueprint, g, jsonify, render_template, request

from ..auth_session import exige_role, fermer, ouvrir, utilisateur_courant
from .. import freinage
from .. import comptes
from ..comptes import ADMIN, ORGANISATEUR, ErreurCompte, verifier
from .. import qr
from ..extensions import db
from ..models import SOURCE_MANUEL, Competition, Participant, Utilisateur
from ..contest import (
    ErreurMetier, ajouter_participant, ajouter_participant_numerote, appareils,
    bloc_par_tag, competition_active, enregistrer_reussite,
    participant_par_dossard, reaffecter_dossard, reussites_tracees,
    supprimer_reussite,
)
from .. import cycle
from ..models import Archive
from ..sheets import parametrage
from ..sheets.client import ErreurClasseur
from ..sheets.importer import importer, lire_tout

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
    """Les categories et les clubs deja connus de la competition en cours.

    De quoi remplir les listes deroulantes de la console (spec 013). La liste
    est **derivee, pas stockee** : c'est l'ensemble des valeurs distinctes
    portees par les participants. Ajouter une categorie, c'est donc l'ecrire une
    fois dans « Autre… » -- elle rejoint la liste des l'enregistrement. Aucune
    table a tenir a jour, aucun ecran de gestion.

    Un seul appel pour les deux listes : la console les charge ensemble, a
    l'ouverture. Deux routes auraient fait deux allers-retours pour un geste.

    Sans competition active : deux listes vides et `success: true`, **pas une
    erreur**. Le formulaire doit rester utilisable -- « Autre… » suffit a creer
    le tout premier participant.
    """
    try:
        comp = competition_active()
    except ErreurMetier:
        return jsonify({"success": True, "categories": [], "clubs": []}), 200

    def distinctes(colonne):
        return sorted(
            v for (v,) in db.session.query(colonne)
            .filter(Participant.competition_id == comp.id, colonne.isnot(None))
            .distinct()
            if v and v.strip()
        )

    return jsonify({
        "success": True,
        "categories": distinctes(Participant.categorie),
        "clubs": distinctes(Participant.club),
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

    participants.sort(key=lambda p: (p.dossard is None, p.dossard or 0, p.nom))
    return jsonify({
        "success": True,
        "participants": [{**p.to_dict(), "present": p.present} for p in participants],
    }), 200


@bp.post("/participants")
@exige_role(ORGANISATEUR)
def ajouter_participant_route():
    """{"nom", "prenom", "club", "categorie", "dossard"} -> le participant cree."""
    corps = _corps_objet()
    if corps is None:
        return jsonify({"success": False, "message": "Corps JSON attendu"}), 400
    # Le dossard n'est plus saisi (spec 013) : il est attribue. Un corps qui en
    # porte un quand meme est honore -- la route reste compatible avec les
    # appels existants, et avec ses propres tests.
    try:
        if corps.get("dossard") in (None, ""):
            p = ajouter_participant_numerote(
                nom=corps.get("nom", ""), prenom=corps.get("prenom"),
                club=corps.get("club"), categorie=corps.get("categorie"),
            )
        else:
            p = ajouter_participant(
                nom=corps.get("nom", ""), prenom=corps.get("prenom"),
                club=corps.get("club"), categorie=corps.get("categorie"),
                dossard=corps.get("dossard"),
            )
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("participant ajoute par %s : %s", g.utilisateur.identifiant, p.nom_complet)
    return jsonify({"success": True, "participant": p.to_dict()}), 201


@bp.post("/participants/<int:participant_id>/dossard")
@exige_role(ORGANISATEUR)
def reaffecter_dossard_route(participant_id):
    """Donne un dossard a quelqu'un, en reprenant celui d'un absent.

    La regle metier est deja ecrite et testee (spec 002) : un dossard portant
    des reussites ENREGISTREES ne peut pas changer de main. On l'expose, on ne
    la reecrit pas.
    """
    corps = _corps_objet()
    if corps is None or "dossard" not in corps:
        return jsonify({"success": False, "message": "Champ « dossard » attendu"}), 400

    p = db.session.get(Participant, participant_id)
    if p is None:
        return jsonify({"success": False, "message": "Participant inconnu"}), 404

    try:
        dossard = int(str(corps["dossard"]).strip())
    except (TypeError, ValueError):
        return jsonify({"success": False,
                        "message": f"Dossard invalide : {corps['dossard']!r}"}), 400

    try:
        reaffecter_dossard(p, dossard)
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    logger.info("dossard %s attribue a %s par %s",
                dossard, p.nom_complet, g.utilisateur.identifiant)
    return jsonify({"success": True, "participant": p.to_dict()}), 200


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


# --- Impression des dossards ------------------------------------------------

@bp.get("/dossards")
@exige_role(ORGANISATEUR)
def page_dossards():
    """La planche a imprimer. `?dossard=42` pour un seul, `?categorie=U13 F` pour un lot.

    Format repris du classeur : des bandes de quelques centimetres, a decouper.
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
    if un_seul is not None:
        participants = [p for p in participants if p.dossard == un_seul]
        titre = f"dossard {un_seul}"
    elif categorie:
        participants = [p for p in participants if (p.categorie or "") == categorie]
        titre = categorie
    else:
        titre = comp.nom

    participants.sort(key=lambda p: p.dossard)
    dossards = [{
        "dossard": p.dossard,
        "nom": p.nom_complet,
        "detail": " · ".join(x for x in (p.categorie, p.club) if x),
        "qr": qr.svg(p.dossard),
    } for p in participants]

    logger.info("impression de %d dossard(s) par %s (%s)",
                len(dossards), g.utilisateur.identifiant, titre)
    return render_template("dossards.html", dossards=dossards, titre=titre)


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
    return jsonify({"success": True, **parametrage.etat(comp)}), 200


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
    from flask import current_app
    cle = (os.environ.get("CLIMBCONTEST_API_KEY_PWA") or "").strip()
    if not cle:
        return jsonify({
            "success": False,
            "message": "Aucune cle PWA configuree : poser CLIMBCONTEST_API_KEY_PWA "
                       "sur le serveur (voir docs/runbook-competition.md).",
        }), 409

    # Derriere Caddy, gunicorn voit du http : on force https partout sauf en
    # developpement local. Pas de ProxyFix pour si peu.
    hote = request.host
    schema = "http" if hote.split(":")[0] in (
        "localhost", "127.0.0.1", "10.0.2.2") else "https"
    url = f"{schema}://{hote}/juge?j={quote(cle, safe='')}"
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
