"""La salle d'attente : les trois piles, et les gestes qui les vident — spec 008.

Les quatre états d'une inscription décrivent un **geste physique**, pas un état
informatique. Derrière chaque ligne il y a un dossard à imprimer et à porter à
quelqu'un ; c'est ce qui explique l'ordre des piles, et le fait qu'imprimer
suffise à clore (décision D4).

    a_trancher  →  un humain doit dire quelque chose
    a_imprimer  →  le participant existe, le papier n'est pas sorti
    faite       →  le dossard est entre ses mains
    ignoree     →  mise de côté volontairement
"""

import logging
from datetime import datetime

from ..contest import ErreurMetier, ajouter_participant_numerote, incrementer_catalogue
from ..extensions import db
from ..models import (
    A_IMPRIMER, A_TRANCHER, FAITE, IGNOREE, Inscription, Participant,
    SOURCE_HELLOASSO,
)

logger = logging.getLogger(__name__)


def piles(comp) -> dict:
    """Les trois piles, dans l'ordre où on les traite."""
    toutes = (Inscription.query.filter_by(competition_id=comp.id)
              .order_by(Inscription.recue_le.desc()).all())

    def vue(inscription):
        detail = inscription.to_dict()
        # Ce que la carte a besoin de montrer face a face quand il faut
        # trancher : la fiche deja en base, a cote de celle qui arrive.
        if inscription.motif == "club_different":
            detail["ressemble_a"] = [
                {"id": p.id, "dossard": p.dossard, "nom": p.nom_complet,
                 "club": p.club, "categorie": p.categorie,
                 "annee_naissance": p.annee_naissance}
                for p in _homonymes(comp, inscription)]
        return detail

    return {
        "a_trancher": [vue(i) for i in toutes if i.etat == A_TRANCHER],
        "a_imprimer": [vue(i) for i in toutes if i.etat == A_IMPRIMER],
        "faites": [vue(i) for i in toutes if i.etat == FAITE],
        "ignorees": [vue(i) for i in toutes if i.etat == IGNOREE],
    }


def en_attente(comp) -> int:
    """Le compteur de la pastille : à trancher **plus** à imprimer.

    Les deux, parce que les deux demandent un geste. Ne compter que « à
    trancher » ferait disparaître la pastille alors qu'il reste des dossards à
    imprimer et à porter.
    """
    return Inscription.query.filter(
        Inscription.competition_id == comp.id,
        Inscription.etat.in_((A_TRANCHER, A_IMPRIMER))).count()


def _homonymes(comp, inscription) -> list:
    from . import rapprochement
    ma_cle = rapprochement.cle(inscription.nom, inscription.prenom)
    return [p for p in Participant.query.filter_by(competition_id=comp.id)
            if rapprochement.cle(p.nom, p.prenom) == ma_cle]


def _inscription(comp, identifiant) -> Inscription:
    i = db.session.get(Inscription, identifiant)
    if i is None or i.competition_id != comp.id:
        raise ErreurMetier("Inscription inconnue", code=404)
    return i


def trancher(comp, identifiant, choix: str, par: str | None = None,
             participant_id=None, categorie: str | None = None) -> Inscription:
    """Le choix humain. Quatre formes, et une seule tranche à la fois.

    ⚠️ Une inscription déjà tranchée ne se retranche pas : `409`, et on le dit.
    Deux organisateurs devant le même écran, c'est le cas normal un matin de
    compétition — le second doit apprendre que le premier est passé, pas
    écraser son choix.
    """
    inscription = _inscription(comp, identifiant)
    if inscription.etat not in (A_TRANCHER,):
        raise ErreurMetier(
            f"Cette inscription a deja ete traitee ({inscription.etat}).", code=409)

    if choix == "meme_personne":
        participant = db.session.get(Participant, participant_id)
        if participant is None or participant.competition_id != comp.id:
            raise ErreurMetier("Participant inconnu", code=404)
        inscription.participant_id = participant.id
        if participant.annee_naissance is None:
            participant.annee_naissance = inscription.annee_naissance
        if not participant.club:
            participant.club = inscription.club
        db.session.add(participant)
        inscription.etat = A_IMPRIMER

    elif choix == "deux_personnes":
        participant = ajouter_participant_numerote(
            nom=inscription.nom, prenom=inscription.prenom,
            club=inscription.club,
            categorie=categorie or inscription.categorie,
            source=SOURCE_HELLOASSO,
            annee_naissance=inscription.annee_naissance)
        inscription.participant_id = participant.id
        inscription.etat = A_IMPRIMER

    elif choix == "categorie":
        if not categorie:
            raise ErreurMetier("Une categorie est attendue")
        inscription.categorie = categorie
        participant = ajouter_participant_numerote(
            nom=inscription.nom, prenom=inscription.prenom,
            club=inscription.club, categorie=categorie,
            source=SOURCE_HELLOASSO,
            annee_naissance=inscription.annee_naissance)
        # Range a la main : « Appliquer le bareme a tous » ne doit pas defaire
        # ce choix (decision D10).
        participant.categorie_forcee = True
        db.session.add(participant)
        inscription.participant_id = participant.id
        inscription.etat = A_IMPRIMER

    elif choix == "retirer":
        # L'annulation apres coup : on retire le participant que cette
        # inscription avait cree. L'inscription, elle, RESTE -- sinon le releve
        # suivant recreerait tout, l'article etant redevenu inconnu.
        participant = (db.session.get(Participant, inscription.participant_id)
                       if inscription.participant_id else None)
        if participant is not None:
            if participant.reussites:
                raise ErreurMetier(
                    f"{participant.nom_complet} porte deja des reussites : "
                    f"le retirer effacerait des resultats.", code=409)
            inscription.participant_id = None
            db.session.delete(participant)
        inscription.etat = IGNOREE

    elif choix == "ignorer":
        inscription.etat = IGNOREE

    elif choix == "garder":
        # L'annulation est vue, on garde le participant tel quel.
        inscription.etat = FAITE if inscription.participant_id else IGNOREE

    else:
        raise ErreurMetier(f"Choix inconnu : {choix!r}")

    inscription.motif = None
    inscription.traitee_le = datetime.now()
    inscription.traitee_par = par
    db.session.add(inscription)
    incrementer_catalogue(comp)
    db.session.commit()
    logger.info("inscription %s tranchee par %s : %s", identifiant, par, choix)
    return inscription


def remise(comp, identifiant, par: str | None = None) -> Inscription:
    """Le dossard est entre ses mains. C'est ce qui clôt (décision D4)."""
    inscription = _inscription(comp, identifiant)
    inscription.etat = FAITE
    inscription.traitee_le = datetime.now()
    inscription.traitee_par = par
    db.session.add(inscription)
    db.session.commit()
    return inscription


def dossards_a_imprimer(comp) -> list[int]:
    """Les dossards de la pile « à imprimer », pour la planche."""
    numeros = []
    for i in Inscription.query.filter_by(competition_id=comp.id, etat=A_IMPRIMER):
        participant = (db.session.get(Participant, i.participant_id)
                       if i.participant_id else None)
        if participant and participant.dossard is not None:
            numeros.append(participant.dossard)
    return sorted(numeros)
