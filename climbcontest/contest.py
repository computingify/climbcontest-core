"""Logique métier de la compétition.

Tout ce qui décide est ici ; les routes ne font que traduire HTTP.
"""

import logging
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import (
    Bloc, Competition, EN_COURS, Participant, SOURCE_SCAN, Success,
)

logger = logging.getLogger(__name__)


class ErreurMetier(Exception):
    """Erreur attendue, avec un message destiné à l'utilisateur."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code


def competition_active() -> Competition:
    comp = Competition.query.filter_by(active=True).first()
    if not comp:
        raise ErreurMetier(
            "Aucune competition active. En creer une depuis la console "
            "d'administration avant d'ouvrir les scans.",
            code=409,
        )
    return comp


def participant_par_dossard(dossard) -> Participant:
    """Retrouve un participant par son dossard.

    ⚠️ Ne déclenche AUCUN appel au classeur Google. L'ancienne version relisait
    tout l'onglet `Listes` quand un dossard était inconnu (risque R7) : un QR
    code étranger scanné en boucle suffisait à grignoter le quota et à allonger
    le temps de réponse de tous les juges.
    """
    try:
        numero = int(str(dossard).strip())
    except (TypeError, ValueError):
        raise ErreurMetier(f"Dossard invalide : {dossard!r}")

    comp = competition_active()
    p = Participant.query.filter_by(competition_id=comp.id, dossard=numero).first()
    if not p:
        raise ErreurMetier(f"Dossard {numero} inconnu")
    return p


def bloc_par_tag(tag) -> Bloc:
    if not tag or not str(tag).strip():
        raise ErreurMetier("Tag de bloc vide")
    comp = competition_active()
    b = Bloc.query.filter_by(competition_id=comp.id, tag=str(tag).strip()).first()
    if not b:
        raise ErreurMetier(f"Bloc {tag} inconnu")
    return b


def enregistrer_reussite(participant: Participant, bloc: Bloc,
                         source: str = SOURCE_SCAN) -> tuple[Success, bool]:
    """Enregistre une réussite. Renvoie (réussite, était_nouvelle).

    **Idempotent.** Un double appui sur « Envoyer », ou deux juges qui valident
    le même passage, ne créent qu'une seule réussite — et l'appelant reçoit la
    même réponse dans les deux cas. C'est ce que garantit la contrainte
    d'unicité `(participant_id, bloc_id)`, pas une vérification préalable :
    entre le SELECT et l'INSERT, deux requêtes concurrentes passeraient toutes
    les deux.

    La réussite est en base **avant** que l'appelant ne reçoive sa réponse. Elle
    part vers le classeur ensuite, par le miroir — et si cet envoi échoue, elle
    reste ici, marquée non synchronisée, et sera retentée.
    """
    existante = Success.query.filter_by(
        participant_id=participant.id, bloc_id=bloc.id
    ).first()
    if existante:
        return existante, False

    reussite = Success(
        participant_id=participant.id,
        bloc_id=bloc.id,
        horodatage=datetime.now(),
        source=source,
    )
    db.session.add(reussite)
    try:
        db.session.commit()
        return reussite, True
    except IntegrityError:
        # Course gagnée par une autre requête : c'est un succès, pas une erreur.
        db.session.rollback()
        existante = Success.query.filter_by(
            participant_id=participant.id, bloc_id=bloc.id
        ).first()
        if existante:
            return existante, False
        raise


def reaffecter_dossard(participant: Participant, dossard: int) -> None:
    """Donne un dossard à un participant.

    Règle métier tranchée le 28/08 : **un dossard ne peut être réaffecté que
    s'il ne porte aucune réussite**. Le cas réel est celui d'un inscrit qui ne
    vient pas — on récupère son dossard pour un arrivant de dernière minute
    plutôt que d'en imprimer un nouveau.

    Cette règle est ce qui évite d'avoir un jour à démêler des réussites entre
    deux personnes : le dossard change de main alors qu'il ne porte rien.
    """
    comp = competition_active()
    ancien = Participant.query.filter_by(
        competition_id=comp.id, dossard=dossard
    ).first()

    if ancien and ancien.id != participant.id:
        if Success.query.filter_by(participant_id=ancien.id).count():
            raise ErreurMetier(
                f"Le dossard {dossard} porte deja des reussites "
                f"({ancien.nom_complet}) : il ne peut pas etre reaffecte. "
                f"Imprimer un nouveau dossard.",
                code=409,
            )
        ancien.dossard = None
        db.session.add(ancien)

    participant.dossard = dossard
    db.session.add(participant)
    incrementer_catalogue(comp)
    db.session.commit()


def incrementer_catalogue(comp: Competition) -> None:
    """Signale un changement de catalogue.

    L'application juge (spec 003) compare cette version à la sienne pour savoir
    s'il faut retélécharger — c'est ce qui lui permet de voir un participant
    ajouté à 14 h sans recharger tout le catalogue.
    """
    comp.catalogue_version = (comp.catalogue_version or 0) + 1
    db.session.add(comp)


def reussites_en_attente() -> int:
    """Combien de réussites ne sont pas encore dans le classeur.

    Exposé par /health : c'est l'indicateur qui dit si le miroir suit.
    """
    return Success.query.filter(Success.sheet_synced_at.is_(None)).count()
