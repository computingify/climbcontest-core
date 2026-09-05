"""Le miroir : rejoue vers le classeur ce qui n'y est pas encore.

C'est le remplacement de la file en mémoire vive, et le cœur de la spec 002.

**Avant**

    reussite → queue.Queue (RAM) → travailleur → batchUpdate
                                                      ↓
                                    erreur ? le lot est vide quand meme

Un redémarrage, un crash, une mise en veille de l'hébergeur ou une erreur de
l'API Google faisait disparaître jusqu'à cinquante réussites, sans trace et sans
alerte (risques R2 et R3).

**Après**

    reussite → base (sheet_synced_at = NULL) → reponse au juge
                        ↑
              SELECT ... WHERE sheet_synced_at IS NULL
                        ↓
                  batchUpdate
                        ↓
              succes ? UPDATE sheet_synced_at = now()
              echec  ? on ne touche a rien → retente au cycle suivant

Trois propriétés que l'ancien n'avait pas : rien n'est perdu à un redémarrage,
un échec Google se rattrape tout seul, et on sait à tout moment ce qui reste à
envoyer — une requête SQL, exposée par `/health`.
"""

import logging
import os
import socket
import threading
from datetime import datetime, timedelta

from sqlalchemy import text

from ..extensions import db
from ..models import Bloc, Competition, Participant, Success
from .client import ClasseurGoogle, ErreurClasseur

logger = logging.getLogger(__name__)

VERROU_MIROIR = "miroir_classeur"
# Au-delà, on considère que le détenteur est mort (worker tué en plein travail)
# et on reprend le verrou. Sans ça, un crash bloquerait la synchronisation
# jusqu'au prochain redémarrage complet.
VERROU_PERIME = timedelta(minutes=5)


def _identite() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{threading.get_ident()}"


def _prendre_verrou() -> bool:
    """Un seul processus synchronise.

    Quatre workers gunicorn tourneraient sinon le même lot en parallèle :
    quatre fois la même écriture Google, pour rien, et le quota qui monte.
    """
    moi = _identite()
    maintenant = datetime.now()
    limite = maintenant - VERROU_PERIME
    try:
        pris = db.session.execute(
            text("UPDATE verrou SET detenu_par = :moi, pris_le = :maintenant "
                 "WHERE nom = :nom AND (pris_le IS NULL OR pris_le < :limite)"),
            {"moi": moi, "maintenant": maintenant, "nom": VERROU_MIROIR, "limite": limite},
        ).rowcount
        if not pris:
            db.session.execute(
                text("INSERT INTO verrou (nom, detenu_par, pris_le) VALUES (:n, :d, :p)"),
                {"n": VERROU_MIROIR, "d": moi, "p": maintenant},
            )
            pris = 1
        db.session.commit()
        return bool(pris)
    except Exception:
        db.session.rollback()
        return False


def _rendre_verrou() -> None:
    try:
        db.session.execute(
            text("UPDATE verrou SET pris_le = NULL WHERE nom = :n"), {"n": VERROU_MIROIR}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


def _envoyables(competition_id: int):
    """Ce que le miroir peut RÉELLEMENT écrire. Le filtre, en un seul endroit.

    Trois conditions, et chacune exclut des réussites bien réelles :

    - pas encore synchronisée — l'objet même du miroir ;
    - de la compétition servie, c'est-à-dire l'**active** : `synchroniser` ne
      regarde qu'elle, et le classeur relié est le sien ;
    - dont le grimpeur porte un **dossard** : la matrice `Import` est indexée
      par dossard, une réussite sans lui n'a aucune colonne où aller.

    ⚠️ Ce filtre est partagé avec le compteur de `/health`
    (`contest.reussites_en_attente`). Il l'est parce qu'il ne l'était pas :
    l'indicateur comptait TOUTES les réussites non synchronisées, toutes
    compétitions confondues. Le 03/09, il affichait 714 en attente alors que le
    miroir n'avait plus rien à envoyer — 714 qu'il ne pouvait pas envoyer, et
    qui resteraient affichées à jamais. Deux requêtes à tenir synchrones à la
    main finissent toujours par diverger ; celle-ci ne peut plus.
    """
    return (
        db.session.query(Success, Participant.dossard, Bloc.numero)
        .join(Participant, Success.participant_id == Participant.id)
        .join(Bloc, Success.bloc_id == Bloc.id)
        .filter(Success.sheet_synced_at.is_(None))
        .filter(Participant.competition_id == competition_id)
        .filter(Participant.dossard.isnot(None))
    )


def reussites_a_envoyer(competition_id: int, limite: int):
    """Ce qui reste à écrire dans le classeur, le plus ancien d'abord."""
    return _envoyables(competition_id).order_by(Success.horodatage).limit(limite).all()


def en_attente(competition_id: int) -> int:
    """Combien le miroir a encore à écrire. Le même filtre, au compte près."""
    return _envoyables(competition_id).count()


def synchroniser(taille_lot: int = 50, classeur=None) -> dict:
    """Envoie un lot au classeur. Renvoie un compte rendu.

    Ne lève jamais : une panne du classeur ne doit pas faire tomber le service.
    Elle laisse simplement les réussites en attente — elles sont en base.
    """
    resultat = {"envoyees": 0, "restantes": 0, "erreur": None, "ignoree": False}

    # ⚠️ LE GARDE EST ICI, DANS LE METIER, ET NULLE PART AILLEURS (spec 046).
    #
    # Pas au demarrage du fil : `planificateur.demarrer` ne s'execute qu'une
    # fois par processus, et la bascule se fait pendant que l'application
    # tourne. Un fil non demarre parce que le mode etait allume au boot ne
    # repartirait JAMAIS quand on rebranche le classeur -- il faudrait
    # redemarrer le service. Le garde au demarrage etait dans l'architecture ;
    # il est retire, parce qu'il fabrique la panne qu'il pretend eviter.
    #
    # Pas non plus dans la boucle du fil : elle n'appelle que cette fonction,
    # et un second garde dirait la meme chose a un autre endroit -- deux
    # gardes finissent par ne plus dire pareil.
    #
    # Ici, il protege AUSSI les appels directs : un script, un test, une route.
    # C'est la regle du depot, la meme que `relever()` de la spec 008.
    from ..sans_classeur import actif as sans_classeur_actif
    if sans_classeur_actif():
        resultat["ignoree"] = True
        resultat["erreur"] = "le classeur Google est debranche (mode sans classeur)"
        return resultat

    comp = Competition.query.filter_by(active=True).first()
    if not comp:
        return resultat

    if not (comp.spreadsheet_id or "").strip():
        # Une competition pas encore reliee a un classeur -- le cas normal entre
        # sa creation et son parametrage. Sans ce garde-fou, le miroir tentait
        # l'ecriture toutes les 40 secondes et journalisait une erreur Google a
        # chaque fois, sur chacun des quatre workers. Six erreurs par minute
        # pour une situation parfaitement normale : c'est ainsi qu'un journal
        # devient illisible, et qu'on rate la vraie panne quand elle arrive.
        resultat["ignoree"] = True
        resultat["erreur"] = "aucun classeur relie a cette competition"
        # Le vrai compte, pas zero : c'est le chiffre qui dit combien de
        # reussites attendent d'etre reportees le jour ou un classeur sera relie.
        resultat["restantes"] = Success.query.join(
            Participant, Success.participant_id == Participant.id
        ).filter(
            Participant.competition_id == comp.id,
            Success.sheet_synced_at.is_(None),
        ).count()
        return resultat

    if not _prendre_verrou():
        resultat["ignoree"] = True          # un autre worker s'en charge
        return resultat

    try:
        lignes = reussites_a_envoyer(comp.id, taille_lot)
        if not lignes:
            return resultat

        couples = [(dossard, numero) for _, dossard, numero in lignes]
        try:
            cl = classeur or ClasseurGoogle(comp.spreadsheet_id)
            cl.marquer_reussites(couples)
        except ErreurClasseur as e:
            # ON NE MARQUE RIEN. C'est toute la différence avec la version
            # précédente, qui vidait son lot même en cas d'échec.
            logger.warning("miroir : echec d'ecriture, %d reussite(s) restent "
                           "en attente et seront retentees — %s", len(couples), e)
            resultat["erreur"] = str(e)
            return resultat

        maintenant = datetime.now()
        for reussite, _, _ in lignes:
            reussite.sheet_synced_at = maintenant
            db.session.add(reussite)
        db.session.commit()

        resultat["envoyees"] = len(lignes)
        logger.info("miroir : %d reussite(s) synchronisee(s)", len(lignes))
        return resultat

    except Exception as e:
        db.session.rollback()
        logger.exception("miroir : erreur inattendue")
        resultat["erreur"] = str(e)
        return resultat
    finally:
        resultat["restantes"] = (
            Success.query.filter(Success.sheet_synced_at.is_(None)).count()
        )
        _rendre_verrou()
