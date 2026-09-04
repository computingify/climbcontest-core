"""Le fil qui relève les inscriptions — spec 008.

Copie conforme de `sheets/planificateur.py`, y compris ses deux qualités qui
ont été payées cher :

1. **il ne meurt jamais** — un `except Exception` autour du corps de boucle. Un
   fil mort accumulerait des inscriptions sans que personne ne le voie ;
2. **il ne répète pas sa plainte** — on journalise ce qui *change*, pas ce qui
   dure. Une heure sans réseau produit une ligne, pas soixante, et c'est ainsi
   qu'un journal reste lisible assez pour qu'on y voie la vraie panne.

## Trois différences avec le miroir, et chacune a sa raison

**La cadence est variable.** Relever toutes les soixante secondes hors
compétition serait 1 440 appels par jour pour rien. La cadence se déduit de
l'état de l'édition — c'est le seul endroit du projet où le rythme dépend de ce
qui se passe dans la salle.

**Le fil ne démarre pas sans clé.** Pas de clé posée, pas de fil, **aucun appel
réseau**. Une intégration non configurée doit être exactement aussi coûteuse
qu'une intégration absente.

**Il s'arrête sur une clé refusée.** C'est la différence entre une panne
passagère et une clé morte : insister sur la seconde brûlerait le quota
d'authentification — 50 appels par heure — et rendrait la reconnexion
impossible au moment précis où on en aurait besoin.
"""

import logging
import threading
from datetime import date, datetime, timedelta

from ..models import EN_COURS, PREPARATION, Competition
from .client import ErreurHelloAsso, configure
from .releve import relever

logger = logging.getLogger(__name__)

_fil: threading.Thread | None = None
_verrou_demarrage = threading.Lock()

#: Ce que `/health` et la console lisent. Le 30/08, 714 réussites attendaient
#: et il a fallu ouvrir un SSH pour apprendre pourquoi : la cause était dans
#: une variable locale. On ne recommence pas.
_derniere_erreur: str | None = None
_dernier_releve: str | None = None
#: Une clé refusée arrête le fil. Il ne repartira qu'au prochain démarrage, ou
#: quand une clé sera reposée depuis la console.
_arrete_pour_cle: bool = False

CADENCE_EN_COURS = 60
CADENCE_IMMINENTE = 300
CADENCE_LENTE = 1800


def derniere_erreur() -> str | None:
    return _derniere_erreur


def dernier_releve() -> str | None:
    return _dernier_releve


def cadence(comp) -> int:
    """À quelle vitesse relever, selon ce qui se passe dans la salle."""
    if comp is None:
        return CADENCE_LENTE
    if comp.statut == EN_COURS:
        return CADENCE_EN_COURS
    if comp.statut == PREPARATION and comp.date:
        # Aujourd'hui ou demain : on est la veille au soir, ou le matin meme.
        # Les inscriptions de derniere minute arrivent la.
        if 0 <= (comp.date - date.today()).days <= 1:
            return CADENCE_IMMINENTE
    return CADENCE_LENTE


def _un_tour(app) -> int:
    """Un passage. Rend la cadence à tenir pour le suivant."""
    global _derniere_erreur, _dernier_releve, _arrete_pour_cle

    with app.app_context():
        if not configure():
            return CADENCE_LENTE
        comp = Competition.query.filter_by(active=True).first()
        if comp is None:
            return CADENCE_LENTE

        prochaine = cadence(comp)
        try:
            rapport = relever(comp)
            _dernier_releve = datetime.now().isoformat(timespec="seconds")
            if _derniere_erreur:
                logger.info("HelloAsso : ca repart")
            _derniere_erreur = None
            if rapport.nouvelles or rapport.en_attente:
                logger.info("HelloAsso : %s", rapport.resume())
        except ErreurHelloAsso as e:
            if e.reconnecter:
                # Cle morte : on s'arrete. Insister bruleraiat le quota, et
                # c'est precisement ce quota qu'il faudra pour se reconnecter.
                _arrete_pour_cle = True
                logger.error("HelloAsso : cle refusee, le fil s'arrete")
            elif e.message != _derniere_erreur:
                # Volontairement en warning : rien n'est perdu, ce sera
                # retente. Et une seule fois par cause -- la repetition
                # n'apprend rien, alors que le retour a la normale, si.
                logger.warning("HelloAsso : %s", e.message)
            _derniere_erreur = e.message
        return prochaine


def _boucle(app) -> None:
    arret = app.extensions.setdefault("climbcontest_arret", threading.Event())
    logger.info("HelloAsso : fil demarre")
    attente = CADENCE_LENTE
    while not arret.wait(attente):
        if _arrete_pour_cle:
            attente = CADENCE_LENTE
            continue
        try:
            attente = _un_tour(app)
        except Exception:
            # Le fil ne doit JAMAIS mourir : s'il s'arrete, les inscriptions
            # cessent d'arriver sans que rien ne le dise.
            logger.exception("HelloAsso : erreur inattendue, on continue")
            attente = CADENCE_LENTE
    logger.info("HelloAsso : fil arrete")


def demarrer(app) -> bool:
    """Démarre le fil, **si une clé est posée**. Rend True s'il a démarré.

    Appelé à la création de l'application, donc dans chacun des quatre workers
    gunicorn. Ce n'est pas un problème : le relevé est idempotent par sa
    contrainte SQL, et le jeton est protégé par son verrou.
    """
    global _fil, _arrete_pour_cle
    with _verrou_demarrage:
        if _fil is not None and _fil.is_alive():
            return True
        with app.app_context():
            if not configure():
                logger.info("HelloAsso : pas de cle posee, aucun fil")
                return False
        _arrete_pour_cle = False
        _fil = threading.Thread(target=_boucle, args=(app,), daemon=True,
                                name="helloasso")
        _fil.start()
        return True


def reveiller() -> None:
    """Repart après une clé reposée depuis la console."""
    global _arrete_pour_cle, _derniere_erreur
    _arrete_pour_cle = False
    _derniere_erreur = None
