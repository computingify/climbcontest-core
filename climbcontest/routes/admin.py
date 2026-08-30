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
from ..models import SOURCE_MANUEL, Participant, Utilisateur
from ..contest import (
    ErreurMetier, ajouter_participant, appareils, bloc_par_tag,
    competition_active, enregistrer_reussite, participant_par_dossard,
    reaffecter_dossard, reussites_tracees, supprimer_reussite,
)
from ..sheets.client import ErreurClasseur
from ..sheets.importer import importer

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
    return jsonify({"success": True, "identifiant": u.identifiant,
                    "roles": sorted(r.role for r in u.roles)}), 200


@bp.post("/deconnexion")
def deconnexion():
    u = utilisateur_courant()
    fermer()
    if u:
        logger.info("deconnexion de %s", u.identifiant)
    return jsonify({"success": True}), 200


@bp.get("/moi")
@exige_role()
def moi():
    """Qui je suis, et ce que j'ai le droit de faire. La console s'en sert
    pour n'afficher que les boutons utilisables."""
    u = g.utilisateur
    return jsonify({
        "success": True,
        "identifiant": u.identifiant,
        "nom_affiche": u.nom_affiche,
        "roles": sorted(r.role for r in u.roles),
    }), 200

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
    try:
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


@bp.post("/import/sheet")
@exige_role(ORGANISATEUR)
def importer_classeur():
    """Relit le classeur et met la base a jour.

    Sur COMMANDE, jamais dans le chemin d'une requete juge (risque R7). Un
    dossard inconnu scanne en boucle ne doit pas pouvoir declencher des lectures
    Google en rafale.

    `ORGANISATEUR`, et plus seulement « connecte » (audit du 30/08) : un
    reimport REECRIT la base et declenche une rafale d'appels Google. Aucun
    compte sans role n'a de raison de pouvoir ca.
    """
    global _dernier_rapport
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    try:
        rapport = importer(comp)
    except ErreurClasseur as e:
        logger.warning("import refuse : %s", e)
        return jsonify({"success": False, "message": str(e)}), 502

    _dernier_rapport = rapport.to_dict()
    _dernier_rapport["resume"] = rapport.resume()
    return jsonify({"success": True, "rapport": _dernier_rapport}), 200


@bp.get("/import/rapport")
@exige_role(ORGANISATEUR)
def dernier_rapport():
    if _dernier_rapport is None:
        return jsonify({"success": True, "rapport": None,
                        "message": "Aucun import depuis le demarrage"}), 200
    return jsonify({"success": True, "rapport": _dernier_rapport}), 200


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
