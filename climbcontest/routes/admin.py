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

from flask import (Blueprint, Response, g, jsonify, redirect,
                   render_template, request, session)

from ..auth_session import exige_role, fermer, ouvrir, utilisateur_courant
from .. import freinage
from .. import comptes
from ..comptes import ADMIN, ORGANISATEUR, ErreurCompte, verifier
from .. import qr
from .. import classement_service
from ..extensions import db
from ..models import Bloc, SOURCE_MANUEL, Competition, Participant, Utilisateur
from ..contest import (
    ErreurMetier, ajouter_participant, ajouter_participant_numerote, appareils,
    bloc_par_tag, competition_active, enregistrer_reussite,
    participant_par_dossard, reaffecter_dossard, reussites_tracees,
    supprimer_reussite,
)
from .. import circuits as circuits_module
from .. import cascade as cascade_module
from .. import cycle
from .. import fiches
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
    if un_seul is not None:
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
    # perdues, une zone d'un seul en gaspillait cinq. Les blocs sortent deja
    # dans l'ordre du `Plan`, donc zone par zone : le regroupement physique est
    # conserve sans payer une feuille par zone.
    return render_template("etiquettes.html",
                           feuilles=fiches.en_feuilles(planche,
                                                       fiches.ETIQUETTES_PAR_FEUILLE),
                           total=len(planche), titre=titre, filtre=filtre)


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
    from flask import current_app
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
