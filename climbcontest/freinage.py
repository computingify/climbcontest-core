"""Frein anti-force-brute sur la connexion a la console.

Depuis que `/admin` est joignable depuis Internet -- decision du 29/08, parce
que les organisateurs sont au gymnase et la VM a la maison -- l'authentification
par session est la seule barriere. Elle est solide, mais rien n'empechait un
robot d'essayer des mots de passe en boucle.

CE QUE CE MODULE FAIT
  Compte les echecs par adresse, et impose une attente qui DOUBLE a chaque
  nouvel echec au-dela d'un seuil de tolerance. Trois fautes de frappe ne
  genent personne ; mille tentatives deviennent impraticables.

CE QU'IL NE FAIT PAS
  Il ne bloque jamais definitivement. Un organisateur qui se trompe cinq fois
  le matin de la competition doit pouvoir entrer deux minutes plus tard -- pas
  attendre qu'on vienne le debloquer. Le plafond est a cinq minutes.

  Il ne compte pas non plus par identifiant : ce serait offrir a n'importe qui
  le moyen de bloquer le compte d'un organisateur en se trompant expres.
"""
import logging
from datetime import datetime, timedelta

from .extensions import db
from .models import TentativeConnexion

logger = logging.getLogger(__name__)

# En dessous, aucune attente. Une faute de frappe, un mot de passe hesitant, un
# clavier de telephone : ca arrive, et ca ne doit rien couter.
TOLERANCE = 3

ATTENTE_INITIALE = timedelta(seconds=2)
ATTENTE_MAX = timedelta(minutes=5)

# Passe ce delai sans echec, l'ardoise est effacee. Sinon une erreur du matin
# penaliserait encore l'apres-midi.
OUBLI = timedelta(minutes=30)


def _ligne(adresse: str) -> TentativeConnexion | None:
    return db.session.get(TentativeConnexion, adresse or "inconnue")


def attente_restante(adresse: str, maintenant: datetime | None = None) -> timedelta:
    """Combien de temps cette adresse doit encore patienter. Zero si elle peut essayer."""
    maintenant = maintenant or datetime.now()
    ligne = _ligne(adresse)
    if ligne is None or ligne.echecs <= TOLERANCE:
        return timedelta(0)

    if maintenant - ligne.derniere > OUBLI:
        return timedelta(0)

    attente = ATTENTE_INITIALE
    for _ in range(ligne.echecs - TOLERANCE - 1):
        attente = min(attente * 2, ATTENTE_MAX)
    attente = min(attente, ATTENTE_MAX)

    ecoule = maintenant - ligne.derniere
    return max(timedelta(0), attente - ecoule)


def noter_echec(adresse: str) -> int:
    """Enregistre un echec. Renvoie le nombre total d'echecs pour cette adresse."""
    adresse = adresse or "inconnue"
    maintenant = datetime.now()
    ligne = _ligne(adresse)

    if ligne is None:
        ligne = TentativeConnexion(adresse=adresse, echecs=0, derniere=maintenant)
        db.session.add(ligne)
    elif maintenant - ligne.derniere > OUBLI:
        ligne.echecs = 0                       # l'ardoise etait effacee

    ligne.echecs += 1
    ligne.derniere = maintenant
    db.session.commit()

    if ligne.echecs == TOLERANCE + 1:
        logger.warning("frein active pour %s apres %d echecs", adresse, ligne.echecs)
    return ligne.echecs


def noter_reussite(adresse: str) -> None:
    """Une connexion reussie efface l'ardoise de cette adresse."""
    ligne = _ligne(adresse)
    if ligne is not None:
        db.session.delete(ligne)
        db.session.commit()
