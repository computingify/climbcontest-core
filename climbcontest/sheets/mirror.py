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


def reussites_a_envoyer(competition_id: int, limite: int):
    """Ce qui reste à écrire dans le classeur, le plus ancien d'abord."""
    return (
        db.session.query(Success, Participant.dossard, Bloc.numero)
        .join(Participant, Success.participant_id == Participant.id)
        .join(Bloc, Success.bloc_id == Bloc.id)
        .filter(Success.sheet_synced_at.is_(None))
        .filter(Participant.competition_id == competition_id)
        .filter(Participant.dossard.isnot(None))
        .order_by(Success.horodatage)
        .limit(limite)
        .all()
    )


def synchroniser(taille_lot: int = 50, classeur=None) -> dict:
    """Envoie un lot au classeur. Renvoie un compte rendu.

    Ne lève jamais : une panne du classeur ne doit pas faire tomber le service.
    Elle laisse simplement les réussites en attente — elles sont en base.
    """
    resultat = {"envoyees": 0, "restantes": 0, "erreur": None, "ignoree": False}

    comp = Competition.query.filter_by(active=True).first()
    if not comp:
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
