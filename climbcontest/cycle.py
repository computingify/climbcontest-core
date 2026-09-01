"""Le cycle de vie d'une édition — spec 018.

Cinq gestes, et un seul endroit qui les décide :

    regler_statut()    dire où on en est : préparation, en cours, terminée
    effacer_donnees()  repartir de zéro côté serveur, et rien d'autre
    archiver()         figer le classement et clore l'édition
    lister()           les archives, sans jamais désérialiser leur contenu
    supprimer()        retirer une archive

**Aucun appel réseau ici.** C'est ce qui distingue ce module de
`sheets/parametrage.py` : celui-là parle à Google, celui-ci ne parle qu'à la
base. La séparation permet de tester tout ce fichier sans le moindre double.
"""

import json
import logging
from datetime import datetime

from sqlalchemy import func

from . import classement_service
from .classement_service import charge_publique
from .contest import ErreurMetier
from .extensions import db
from .models import (
    Archive, Bloc, BlocCircuit, Circuit, EN_COURS, FORMAT_ARCHIVE, Participant,
    PREPARATION, ReaffectationDossard, Success, TERMINEE,
    prochaine_version_catalogue,
)

logger = logging.getLogger(__name__)

STATUTS = (PREPARATION, EN_COURS, TERMINEE)

# Le mot à frapper pour détruire. Repris tel quel de la spec 015 : un seul mot
# dans tout le produit, pour qu'il n'y ait jamais à se demander lequel.
MOT_DE_CONFIRMATION = "EFFACER"


# --- Les compteurs ----------------------------------------------------------

def compteurs(comp) -> dict:
    """Ce qui est en base pour cette compétition — les chiffres qui décident.

    « Combien de réussites vais-je perdre ? » est la question qu'on se pose la
    main sur le bouton ; elle mérite une réponse à l'écran, pas un calcul de
    tête.

    Vivait dans `sheets/parametrage.py`. Elle en sort parce qu'elle ne parle pas
    du classeur : elle parle de la compétition.
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
        "circuits": Circuit.query.filter_by(competition_id=comp.id).count(),
        "reussites": total,
        "reussites_en_attente": attente,
        "dossard_max": dossard_max,
    }


# --- Le statut --------------------------------------------------------------

def regler_statut(comp, statut: str) -> str:
    """Dire où on en est. Aucun effet de bord, et c'est voulu.

    Le statut ne commande RIEN dans le produit : ni les scans, ni le classement,
    ni la page de résultats, ni les téléphones. Il sert à deux choses — se dire
    où on en est, et armer l'avertissement de `_garde_en_cours()`. Une
    étiquette, pas un interrupteur. C'est précisément ce qui permet de le
    corriger à tout moment sans rien casser.

    Il n'est PAS déduit de l'activité (spec 018 § 7) : un bénévole qui essaie
    son téléphone le jeudi soir armerait le garde-fou, et une pause déjeuner le
    désarmerait. Un statut deviné se trompe les jours où il compte.
    """
    valeur = (statut or "").strip()
    if valeur not in STATUTS:
        raise ErreurMetier(
            f"Statut inconnu « {valeur} ». Attendus : {', '.join(STATUTS)}.")

    ancien = comp.statut
    comp.statut = valeur
    db.session.add(comp)
    db.session.commit()
    logger.info("competition %s : statut %s -> %s", comp.id, ancien, valeur)
    return ancien


def garde_en_cours(comp, forcer: bool = False) -> None:
    """Refuse de détruire une compétition marquée en cours — sauf forçage.

    Une seule copie de cette règle dans tout le produit, appelée par
    `effacer_donnees()` ET par `parametrage.relier()` en mode « nouvelle
    compétition ». Écrite en double dans deux routes, elle finirait par
    diverger — elle a déjà existé une fois, à la spec 015, et c'est cette
    copie-là qui reste.

    Le forçage vient d'Adrien (01/09) : « oui je veux pouvoir le forcer ». Il
    existe parce que le statut peut être faux — il l'a été pendant toute la vie
    du produit, avant que `regler_statut()` n'existe.
    """
    if comp.statut == EN_COURS and not forcer:
        raise ErreurMetier(
            "La competition est marquee EN COURS : effacer ses reussites n'est "
            "surement pas ce que tu voulais faire. Archive-la d'abord (elle "
            "passera « terminee »), ou coche « effacer quand meme » si le "
            "statut est faux.", code=409)


def exiger_confirmation(confirmation: str) -> None:
    """Le mot frappé à la main, avant toute destruction.

    Vérifié AVANT le forçage, jamais après : cocher une case sans frapper le mot
    ne détruit rien. Deux gestes, deux intentions — la case dit « je sais que le
    statut dit en cours », le mot dit « je veux effacer ».
    """
    if (confirmation or "").strip() != MOT_DE_CONFIRMATION:
        raise ErreurMetier(
            f"Pour tout effacer, ecris « {MOT_DE_CONFIRMATION} » dans le champ "
            "de confirmation. Rien n'a ete touche.")


# --- Effacer ----------------------------------------------------------------

def vider_la_base(comp) -> dict:
    """Efface tout ce qui décrit une édition : participants, blocs, réussites.

    Les réaffectations de dossard partent EN PREMIER : elles pointent vers des
    participants par clé étrangère, et SQLite applique l'intégrité
    référentielle (`PRAGMA foreign_keys=ON`). Sans ça, la suppression
    échouerait.

    Ne valide pas la transaction : `flush()` seulement. C'est l'appelant qui
    commit, parce que lui seul sait ce qu'il y a d'autre dans la transaction —
    `relier()` y met aussi le changement de classeur, et les deux doivent
    tomber ensemble ou pas du tout.
    """
    compte = compteurs(comp)

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


def effacer_donnees(comp, confirmation: str = "", forcer: bool = False) -> dict:
    """Repartir de zéro côté serveur. Le classeur Google n'est PAS touché.

    Ce que ça n'efface pas, et qu'on écrit noir sur blanc parce que c'est la
    question qu'on se pose : les autres compétitions, les comptes de la console,
    les archives, et pas une cellule du classeur.

    Ne commit pas — voir `vider_la_base()`.
    """
    exiger_confirmation(confirmation)       # le mot d'abord…
    garde_en_cours(comp, forcer)            # …le forçage ensuite

    efface = vider_la_base(comp)

    # Les téléphones DOIVENT retélécharger : sinon ils continuent d'afficher les
    # grimpeurs de l'édition précédente sur des dossards désormais libres (le
    # correctif du 30/08 sur `catalogue_version`).
    comp.catalogue_version = prochaine_version_catalogue()
    db.session.add(comp)

    # Le cache expire seul en 5 s, donc ceci n'évite aucune panne : ça évite
    # cinq secondes à regarder un classement qu'on vient de supprimer en se
    # demandant si le bouton a marché.
    classement_service.invalider(comp.id)

    logger.info("donnees effacees pour la competition %s : %s", comp.id, efface)
    return efface


# --- Archiver ---------------------------------------------------------------

def _donnees_brutes(comp) -> dict:
    """La matière première, pour ce qu'on ne sait pas encore vouloir en faire.

    Elle ne sert à rien aujourd'hui — la consultation lit `classement`. Elle
    sert le jour où l'on veut recalculer avec la règle des finales, extraire une
    fixture pour `verify_ranking.py`, ou répondre à « combien de blocs a fait
    untel en 2026 ». Sans elle, une archive serait une capture d'écran.
    """
    participants = Participant.query.filter_by(competition_id=comp.id).all()
    blocs = Bloc.query.filter_by(competition_id=comp.id).all()
    circuits = Circuit.query.filter_by(competition_id=comp.id).all()

    ids_blocs = [b.id for b in blocs]
    liens = (BlocCircuit.query.filter(BlocCircuit.bloc_id.in_(ids_blocs)).all()
             if ids_blocs else [])
    par_bloc: dict[int, list[str]] = {}
    noms_circuits = {c.id: c.nom for c in circuits}
    for lien in liens:
        par_bloc.setdefault(lien.bloc_id, []).append(noms_circuits.get(lien.circuit_id))

    ids_participants = [p.id for p in participants]
    reussites = (Success.query.filter(Success.participant_id.in_(ids_participants)).all()
                 if ids_participants else [])

    def horodatage(valeur):
        return valeur.isoformat() if isinstance(valeur, datetime) else None

    return {
        "circuits": [{"nom": c.nom} for c in circuits],
        "participants": [
            {"id": p.id, "dossard": p.dossard, "nom": p.nom, "prenom": p.prenom,
             "club": p.club, "categorie": p.categorie, "present": p.present,
             "source": p.source, "cree_le": horodatage(p.cree_le)}
            for p in participants
        ],
        "blocs": [
            {"id": b.id, "tag": b.tag, "numero": b.numero, "zone": b.zone,
             "couleur": b.couleur, "couleur_prises": b.couleur_prises,
             "circuits": sorted(filter(None, par_bloc.get(b.id, [])))}
            for b in blocs
        ],
        "reussites": [
            {"participant_id": r.participant_id, "bloc_id": r.bloc_id,
             "horodatage": horodatage(r.horodatage), "source": r.source,
             "dossard_scanne": r.dossard_scanne, "saisie_par": r.saisie_par,
             "appareil_nom": r.appareil_nom, "ref_client": r.ref_client}
            for r in reussites
        ],
    }


def archiver(comp, par: str | None = None) -> tuple[Archive, list[str]]:
    """Fige le classement, range les données brutes, et clôt l'édition.

    Le calcul est FORCÉ. Archiver un cache vieux de cinq secondes figerait un
    classement qui ignore les dernières réussites — et une archive fausse ne se
    répare pas.

    N'efface rien : l'archive et les données coexistent. Effacer est un geste
    séparé, qu'on fait quand on veut, ou jamais.
    """
    charge = charge_publique(comp, forcer=True)
    compte = compteurs(comp)
    avertissements = []

    if not compte["reussites"]:
        avertissements.append(
            "Cette competition n'a aucune reussite : l'archive sera vide de "
            "resultats. C'est peut-etre voulu, mais ca se dit.")
    if compte["reussites_en_attente"]:
        avertissements.append(
            f"{compte['reussites_en_attente']} reussite(s) ne sont pas encore "
            "arrivees dans le classeur Google. L'archive du serveur, elle, les "
            "contient — c'est le classeur qui sera incomplet.")

    contenu = {
        "format": FORMAT_ARCHIVE,
        "cree_le": datetime.now().isoformat(timespec="seconds"),
        "cree_par": par,
        "competition": {
            "id": comp.id, "nom": comp.nom,
            "date": comp.date.isoformat() if comp.date else None,
            "statut": TERMINEE, "spreadsheet_id": comp.spreadsheet_id,
        },
        "compteurs": compte,
        "classement": charge,
        "donnees": _donnees_brutes(comp),
    }

    archive = Archive(
        competition_id=comp.id, nom=comp.nom, date=comp.date,
        format=FORMAT_ARCHIVE, cree_par=par,
        participants=compte["participants"], blocs=compte["blocs"],
        reussites=compte["reussites"],
        # `ensure_ascii=False` : les noms portent des accents, et les stocker
        # en « é » triplerait la taille pour rien. SQLite est en UTF-8.
        contenu=json.dumps(contenu, ensure_ascii=False),
    )
    db.session.add(archive)

    # Archiver, c'est clore.
    comp.statut = TERMINEE
    db.session.add(comp)
    db.session.commit()

    logger.info("archive %s creee pour la competition %s (%d participants, "
                "%d reussites, %d octets)", archive.id, comp.id,
                archive.participants, archive.reussites, len(archive.contenu))
    return archive, avertissements


# --- Consulter et supprimer -------------------------------------------------

def lister() -> list[dict]:
    """Les archives, la plus récente en tête.

    `with_entities` exclut explicitement `contenu` : trois cents kilo-octets par
    ligne, chargés pour afficher un nombre, c'est ce qui rend une page lente
    sans raison visible. Les compteurs affichés vivent dans leurs propres
    colonnes, recopiés à l'archivage exactement pour ça.
    """
    lignes = (Archive.query
              .with_entities(Archive.id, Archive.competition_id, Archive.nom,
                             Archive.date, Archive.format, Archive.cree_le,
                             Archive.cree_par, Archive.participants,
                             Archive.blocs, Archive.reussites)
              .order_by(Archive.cree_le.desc(), Archive.id.desc())
              .all())
    return [{
        "id": l.id, "competition_id": l.competition_id, "nom": l.nom,
        "date": l.date.isoformat() if l.date else None,
        "format": l.format,
        "cree_le": l.cree_le.isoformat() if l.cree_le else None,
        "cree_par": l.cree_par,
        "participants": l.participants, "blocs": l.blocs, "reussites": l.reussites,
        "lisible": l.format == FORMAT_ARCHIVE,
    } for l in lignes]


def contenu_archive(archive: Archive) -> dict:
    """Le JSON complet, tel qu'il a été rangé."""
    try:
        return json.loads(archive.contenu)
    except ValueError as e:
        raise ErreurMetier(
            f"L'archive {archive.id} est illisible : {e}. Le fichier reste "
            "telechargeable tel quel.", code=500) from e


def classement_archive(archive: Archive) -> dict:
    """Le classement figé, resservi SANS RIEN RECALCULER.

    C'est ce qui rend une archive indépendante du moteur de classement : celui
    d'aujourd'hui comme celui de dans trois ans. Un format qu'on ne sait plus
    lire se refuse ici, proprement, plutôt que de faire tomber la page de
    résultats sur une clé manquante.
    """
    if archive.format != FORMAT_ARCHIVE:
        raise ErreurMetier(
            f"Cette archive est au format {archive.format}, cette version du "
            f"serveur lit le format {FORMAT_ARCHIVE}. Elle reste "
            "telechargeable.", code=409)

    contenu = contenu_archive(archive)
    charge = contenu.get("classement")
    if not isinstance(charge, dict):
        raise ErreurMetier(
            f"L'archive {archive.id} ne porte pas de classement exploitable.",
            code=409)
    return charge


def supprimer(archive: Archive) -> None:
    identifiant, nom = archive.id, archive.nom
    db.session.delete(archive)
    db.session.commit()
    logger.info("archive %s (%s) supprimee", identifiant, nom)
