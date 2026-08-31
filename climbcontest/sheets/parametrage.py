"""Régler le classeur depuis la console — spec 015.

Trois gestes, et un seul endroit qui les décide :

    tester()      lecture seule : « est-ce que ce classeur répond, et à quoi
                  ressemble-t-il ? » — se fait AVANT de relier quoi que ce soit
    relier()      pointer la compétition active vers un autre classeur, dans
                  l'un des trois modes tranchés avec Adrien le 31/08
    poser_jeton() écrire le jeton Google dans le dossier des secrets

Ce qui n'est pas ici : le consentement OAuth (il demande un navigateur), et la
gestion de plusieurs compétitions (autre écran, autre spec).
"""

import json
import logging
import re

from sqlalchemy import func

from ..contest import ErreurMetier
from ..extensions import db
from ..models import (
    Bloc, Circuit, EN_COURS, Participant, ReaffectationDossard, Success,
    prochaine_version_catalogue,
)
from .client import ClasseurGoogle, ecrire_jeton_json, etat_jeton

logger = logging.getLogger(__name__)

# Les onglets dont le backend dépend vraiment. Leur absence n'empêche pas de
# relier — on prépare parfois le lien avant la feuille — mais elle se dit.
ONGLETS_ATTENDUS = ("Import", "Listes", "Plan")

# La matrice ou le miroir ecrit. Lue de la classe, mais figee ici : `tester()`
# doit continuer a designer le bon onglet meme quand un test remplace
# `ClasseurGoogle` par un double.
ONGLET_MATRICE = ClasseurGoogle.ONGLET_IMPORT

# Ce pour quoi les formules du classeur sont dimensionnées
# (docs/technical/classeur-google.md : « 120 grimpeurs et 50 blocs »). Agrandir
# la grille fait que l'écriture ABOUTIT ; ça ne fait pas entrer le grimpeur dans
# les formules. La console doit le dire, avec les deux chiffres.
CAPACITE_FORMULES = 120

MODE_RELIER = "relier"
MODE_REJOUER = "rejouer"
MODE_REINITIALISER = "reinitialiser"
MODES = (MODE_RELIER, MODE_REJOUER, MODE_REINITIALISER)

MOT_DE_CONFIRMATION = "EFFACER"

# Un identifiant de classeur Google : au moins vingt caractères de l'alphabet
# des URL. Court, c'est un fragment de lien mal collé, pas un identifiant.
MOTIF_IDENTIFIANT = re.compile(r"^[A-Za-z0-9_-]{20,}$")
MOTIF_URL = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})")

# Ce qu'un jeton doit porter pour vivre plus d'une heure. Sans `refresh_token`,
# il meurt à la première expiration : le refuser tout de suite vaut mieux qu'une
# panne le lendemain matin, quand plus personne n'a le temps de comprendre.
CLES_JETON = ("refresh_token", "client_id", "client_secret")


def lien_classeur(identifiant: str | None) -> str | None:
    if not identifiant:
        return None
    return f"https://docs.google.com/spreadsheets/d/{identifiant}/edit"


def extraire_identifiant(texte: str) -> str:
    """Le lien collé → l'identifiant du classeur.

    Accepte l'URL complète (avec `/edit#gid=0`, avec des paramètres, peu
    importe) et l'identifiant nu. Ce qu'on colle vient d'une barre d'adresse :
    c'est cette forme-là qui doit marcher sans réfléchir.
    """
    valeur = (texte or "").strip()
    if not valeur:
        raise ErreurMetier(
            "Colle le lien du classeur Google (celui de la barre d'adresse, "
            "de la forme https://docs.google.com/spreadsheets/d/…).")

    trouve = MOTIF_URL.search(valeur)
    if trouve:
        return trouve.group(1)
    if MOTIF_IDENTIFIANT.match(valeur):
        return valeur

    raise ErreurMetier(
        "Ce n'est pas un lien de classeur Google. Ouvre la feuille dans le "
        "navigateur et copie l'adresse complete : elle contient "
        "« /spreadsheets/d/… ».")


# --- L'état affiché par la console ------------------------------------------

def _compteurs(comp) -> dict:
    """Ce qui est en base pour cette compétition — les chiffres qui décident.

    « Combien de réussites vais-je emporter en changeant de feuille ? » est la
    question qu'on se pose la main sur le bouton ; elle mérite une réponse à
    l'écran, pas un calcul de tête.
    """
    ids = db.session.query(Participant.id).filter(Participant.competition_id == comp.id)
    total = Success.query.filter(Success.participant_id.in_(ids)).count()
    attente = Success.query.filter(
        Success.participant_id.in_(ids), Success.sheet_synced_at.is_(None)).count()
    dossard_max = db.session.query(func.max(Participant.dossard)).filter(
        Participant.competition_id == comp.id).scalar()
    return {
        "participants": Participant.query.filter_by(competition_id=comp.id).count(),
        "blocs": Bloc.query.filter_by(competition_id=comp.id).count(),
        "reussites": total,
        "reussites_en_attente": attente,
        "dossard_max": dossard_max,
    }


def etat(comp) -> dict:
    """Tout ce que la vue « Classeur » affiche. Ne touche pas au réseau."""
    if comp is None:
        return {"competition": None, "classeur": {"relie": False, "identifiant": None,
                                                  "url": None},
                "jeton": etat_jeton(), "compteurs": None, "modes": list(MODES)}

    identifiant = (comp.spreadsheet_id or "").strip() or None
    return {
        "competition": {"id": comp.id, "nom": comp.nom, "statut": comp.statut},
        "classeur": {"relie": bool(identifiant), "identifiant": identifiant,
                     "url": lien_classeur(identifiant)},
        "jeton": etat_jeton(),
        "compteurs": _compteurs(comp),
        "modes": list(MODES),
    }


# --- Tester avant de relier -------------------------------------------------

def _exiger_jeton(classeur) -> None:
    """Refuse tôt, et en une phrase, quand aucun jeton n'est posé.

    Sans ce garde-fou, la console affichait le message du client — la liste des
    six chemins où le jeton a été cherché. C'est ce qu'il faut dans un journal ;
    à l'écran, c'est un mur de texte qui ne dit pas quoi faire. Ici, la réponse
    tient en une phrase et désigne le geste suivant.
    """
    if classeur is None and not etat_jeton()["present"]:
        raise ErreurMetier(
            "Aucun jeton Google sur le serveur : pose-le dans la carte "
            "« Jeton Google » ci-dessous, puis retente.", code=409)


def tester(identifiant: str, comp=None, classeur=None) -> dict:
    """Lecture seule. Répond ce que Google répond, sans rien changer.

    Sert de vérification AVANT de relier : c'est le seul moment où l'on peut
    encore se rendre compte qu'on avait la mauvaise feuille.
    """
    _exiger_jeton(classeur)
    cl = classeur or ClasseurGoogle(identifiant)

    titre = cl.titre()
    onglets = cl.onglets()
    manquants = [nom for nom in ONGLETS_ATTENDUS if nom not in onglets]

    rapport = {
        "identifiant": identifiant,
        "url": lien_classeur(identifiant),
        "titre": titre,
        "onglets": onglets,
        "onglets_manquants": manquants,
        "grille": None,
        "avertissements": [],
    }

    if manquants:
        rapport["avertissements"].append(
            "Onglet(s) absent(s) : " + ", ".join(manquants)
            + ". Le miroir ecrit dans « Import », l'import lit « Listes » et « Plan ».")
        if ONGLET_MATRICE in manquants:
            return rapport

    grille = cl.grille(ONGLET_MATRICE)
    rapport["grille"] = grille
    # colonne = dossard + 3 : la largeur dit le plus grand dossard écrivable
    # sans agrandissement.
    rapport["dossard_max_sans_agrandir"] = max(0, grille["colonnes"] - 3)

    dossard_max = (comp and _compteurs(comp)["dossard_max"]) or 0
    if dossard_max and dossard_max > CAPACITE_FORMULES:
        rapport["avertissements"].append(
            f"Le dossard le plus haut attribue est {dossard_max}, au-dela des "
            f"{CAPACITE_FORMULES} grimpeurs pour lesquels les formules du "
            "classeur sont ecrites. La reussite sera bien posee dans « Import » "
            "(la grille s'agrandit toute seule), mais le classeur ne la comptera "
            "pas : c'est la page de resultats du serveur qui fait foi.")
    return rapport


# --- Relier -----------------------------------------------------------------

def _remettre_en_attente(comp) -> int:
    """Toutes les réussites repartent vers le nouveau classeur."""
    ids = db.session.query(Participant.id).filter(Participant.competition_id == comp.id)
    nombre = (db.session.query(Success)
              .filter(Success.participant_id.in_(ids))
              .update({Success.sheet_synced_at: None}, synchronize_session=False))
    return nombre


def _vider_la_base(comp) -> dict:
    """Efface tout ce qui décrit une édition : participants, blocs, réussites.

    Les réaffectations de dossard partent EN PREMIER : elles pointent vers des
    participants par clé étrangère, et SQLite applique l'intégrité référentielle
    (`PRAGMA foreign_keys=ON`). Sans ça, la suppression échouerait.
    """
    compte = _compteurs(comp)

    ReaffectationDossard.query.filter_by(competition_id=comp.id).delete(
        synchronize_session=False)
    db.session.flush()

    # Suppression par objet, pas en masse : les cascades ORM emportent les
    # réussites d'un participant et les liens bloc↔circuit d'un bloc. Sur
    # quelques centaines de lignes, la lisibilité vaut mieux que la vitesse.
    for participant in Participant.query.filter_by(competition_id=comp.id):
        db.session.delete(participant)
    for bloc in Bloc.query.filter_by(competition_id=comp.id):
        db.session.delete(bloc)
    for circuit in Circuit.query.filter_by(competition_id=comp.id):
        db.session.delete(circuit)
    db.session.flush()
    return compte


def relier(comp, identifiant: str, mode: str = MODE_RELIER,
           confirmation: str = "", classeur=None) -> dict:
    """Pointe la compétition active vers ce classeur, dans le mode demandé.

    Les trois modes viennent d'Adrien (31/08) : « nouvelle compétition donc
    effacement des données serveur et googlesheet, ou alors simple changement de
    fichier donc toutes les données sont conservées et les données serveur sont
    appliquées dans la nouvelle feuille ».
    """
    if mode not in MODES:
        raise ErreurMetier(f"Mode inconnu « {mode} ». Attendus : {', '.join(MODES)}.")

    ancien = (comp.spreadsheet_id or "").strip() or None
    effets = {"mode": mode, "ancien": ancien, "nouveau": identifiant,
              "reussites_reprogrammees": 0, "efface": None, "classeur_vide": None}

    if mode == MODE_REINITIALISER:
        if comp.statut == EN_COURS:
            raise ErreurMetier(
                "La competition est EN COURS : effacer ses reussites n'est "
                "surement pas ce que tu voulais faire. Passe par « meme "
                "competition, autre feuille » si tu dois changer de classeur "
                "maintenant.", code=409)
        if (confirmation or "").strip() != MOT_DE_CONFIRMATION:
            raise ErreurMetier(
                f"Pour tout effacer, ecris « {MOT_DE_CONFIRMATION} » dans le "
                "champ de confirmation. Rien n'a ete touche.")

        # Le classeur AVANT la base. Si Google refuse, rien n'est détruit côté
        # serveur — l'ordre inverse laisserait une base vide et un classeur
        # plein, c'est-à-dire le pire des deux mondes.
        _exiger_jeton(classeur)
        cl = classeur or ClasseurGoogle(identifiant)
        effets["classeur_vide"] = cl.vider_matrice()
        effets["efface"] = _vider_la_base(comp)
        # Les téléphones DOIVENT retélécharger : sinon ils continuent d'afficher
        # les grimpeurs de l'édition précédente sur des dossards désormais
        # libres (le correctif du 30/08 sur `catalogue_version`).
        comp.catalogue_version = prochaine_version_catalogue()

    comp.spreadsheet_id = identifiant

    if mode == MODE_REJOUER:
        effets["reussites_reprogrammees"] = _remettre_en_attente(comp)

    db.session.add(comp)
    db.session.commit()

    logger.info("classeur de la competition %s : %s -> %s (mode %s)",
                comp.id, ancien or "aucun", identifiant, mode)
    return effets


# --- Le jeton ---------------------------------------------------------------

def poser_jeton(texte: str) -> dict:
    """Écrit le jeton Google collé dans la console.

    **Du JSON, jamais un pickle.** Un `token.pickle` collé ici ferait appeler
    `pickle.loads()` sur du contenu venu du réseau : une session
    d'administrateur volée deviendrait une exécution de code sur la VM. Le JSON
    porte exactement la même information et n'est que des données.
    `tools/exporter_jeton.py` convertit un `token.pickle` existant.
    """
    valeur = (texte or "").strip()
    if not valeur:
        raise ErreurMetier("Colle le contenu du jeton (le JSON produit par "
                           "python3 tools/exporter_jeton.py).")

    try:
        contenu = json.loads(valeur)
    except ValueError as e:
        raise ErreurMetier(
            "Ce n'est pas du JSON valide : " + str(e) + ". La console attend le "
            "fichier produit par tools/exporter_jeton.py, accolades comprises. "
            "Un token.pickle ne se colle pas ici — il est binaire.") from e

    if not isinstance(contenu, dict):
        raise ErreurMetier("Le jeton attendu est un objet JSON, entre accolades.")

    manquantes = [cle for cle in CLES_JETON if not contenu.get(cle)]
    if manquantes:
        raise ErreurMetier(
            "Jeton incomplet, rien n'a ete remplace. Cle(s) manquante(s) : "
            + ", ".join(manquantes)
            + ". Sans refresh_token, le jeton cesse de fonctionner a la premiere "
              "expiration — donc au pire moment.")

    chemin = ecrire_jeton_json(json.dumps(contenu))
    logger.info("jeton Google remplace depuis la console (%s)", chemin)
    return etat_jeton()
