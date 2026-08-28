"""Le fil qui déclenche la synchronisation vers le classeur.

Rythme conservé de la version précédente (décision Q2 du 28/08) : un lot de
**50 réussites**, une tentative toutes les **40 secondes**. Ce qui change n'est
pas la cadence, c'est qu'un échec ne détruit plus rien.

Chaque worker gunicorn démarre ce fil. Ce n'est pas un problème : le verrou
porté par la base fait qu'un seul travaille réellement, les autres passent leur
tour en une requête. C'est plus simple, et surtout plus robuste, que de désigner
un worker « maître » — celui-là pourrait mourir.
"""

import logging
import threading

from .mirror import synchroniser

logger = logging.getLogger(__name__)

_fil: threading.Thread | None = None
_verrou_demarrage = threading.Lock()


def _boucle(app, periode: int, taille_lot: int) -> None:
    arret = app.extensions.setdefault("climbcontest_arret", threading.Event())
    logger.info("miroir : fil demarre (lot=%d, periode=%ds)", taille_lot, periode)

    while not arret.wait(periode):
        try:
            with app.app_context():
                r = synchroniser(taille_lot=taille_lot)
            if r["envoyees"]:
                logger.info("miroir : %d envoyee(s), %d restante(s)",
                            r["envoyees"], r["restantes"])
            elif r["erreur"]:
                # Volontairement en warning, pas en error : rien n'est perdu,
                # ce sera retente. Une alerte ici crierait pour une coupure
                # reseau de trente secondes.
                logger.warning("miroir : %s (%d en attente)", r["erreur"], r["restantes"])
        except Exception:
            # Le fil ne doit JAMAIS mourir : s'il s'arrete, les reussites
            # s'accumulent en base sans que personne ne le voie -- sauf le
            # compteur de /health, qui est justement la pour ca.
            logger.exception("miroir : erreur inattendue, on continue")


def demarrer(app) -> None:
    """Démarre le fil une seule fois par processus."""
    global _fil
    if not app.config.get("SHEETS_ACTIF"):
        logger.info("miroir : desactive par configuration")
        return

    with _verrou_demarrage:
        if _fil is not None and _fil.is_alive():
            return
        _fil = threading.Thread(
            target=_boucle,
            args=(app, app.config["SHEETS_PERIODE_S"], app.config["SHEETS_TAILLE_LOT"]),
            name="miroir-classeur",
            daemon=True,
        )
        _fil.start()


def arreter(app) -> None:
    """Demande l'arrêt du fil. Utilisé par les tests."""
    evenement = app.extensions.get("climbcontest_arret")
    if evenement:
        evenement.set()


def est_actif() -> bool:
    return _fil is not None and _fil.is_alive()
