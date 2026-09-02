"""Logique métier de la compétition.

Tout ce qui décide est ici ; les routes ne font que traduire HTTP.
"""

import logging
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from . import formatage
from .extensions import db
from .models import (
    Bloc, Competition, EN_COURS, Participant, ReaffectationDossard, SOURCE_MANUEL,
    SOURCE_SCAN, Success, prochaine_version_catalogue,
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
                         source: str = SOURCE_SCAN,
                         dossard_scanne: int | None = None,
                         scanne_le: datetime | None = None,
                         saisie_par: str | None = None,
                         appareil: dict | None = None,
                         ref_client: str | None = None,
                         hors_circuit_force: bool | None = None) -> tuple[Success, bool]:
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
        # Trace du geste reel du juge, pour retrouver apres coup une reussite
        # arrivee sur un dossard qui avait change de main entre-temps.
        dossard_scanne=dossard_scanne if dossard_scanne is not None else participant.dossard,
        scanne_le=scanne_le,
        saisie_par=saisie_par,
        # De quel telephone (spec 011). Vide pour une saisie manuelle ou un
        # import : ils n'ont pas d'appareil, et en inventer un serait faux.
        appareil_id=(appareil or {}).get("id"),
        appareil_nom=(appareil or {}).get("nom"),
        ref_client=ref_client,
        # Ce que le juge a vu au moment d'appuyer (spec 019). `None` quand
        # personne n'a verifie -- saisie manuelle, import, telephone d'avant.
        hors_circuit_force=hors_circuit_force,
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


def ajouter_participant(nom: str, prenom: str | None = None,
                        club: str | None = None, categorie: str | None = None,
                        dossard: int | None = None,
                        source: str = SOURCE_MANUEL) -> Participant:
    """Ajoute un participant a la competition en cours.

    Le cas reel : quelqu'un s'inscrit a 8 h 45, ou pendant la competition. Sans
    cette fonction, il fallait passer par le classeur puis un reimport -- ce qui
    reecrit toute la base au moment ou elle est le plus utilisee.

    Le dossard est FACULTATIF : un inscrit qui n'est pas venu n'en a pas, et
    c'est precisement lui dont on reprendra le numero.
    """
    # Formate AVANT de tester le vide : « ,,, » n'est pas un nom, mais «   Jean »
    # en est un. Spec 013 -- la mise en forme vit dans le metier, pas dans le
    # navigateur, sinon le premier appel direct a l'API la contourne.
    nom = formatage.nom(nom)
    if not nom:
        raise ErreurMetier("Le nom est obligatoire")

    comp = competition_active()

    if dossard is not None:
        try:
            dossard = int(str(dossard).strip())
        except (TypeError, ValueError):
            raise ErreurMetier(f"Dossard invalide : {dossard!r}")
        occupant = Participant.query.filter_by(
            competition_id=comp.id, dossard=dossard).first()
        if occupant:
            # On dit QUI le porte. « Dossard deja pris » obligerait a aller
            # chercher dans la liste, au moment ou on a le moins de temps.
            raise ErreurMetier(
                f"Le dossard {dossard} est deja porte par {occupant.nom_complet}.",
                code=409)

    p = Participant(
        competition_id=comp.id,
        nom=nom,
        prenom=formatage.nom(prenom),
        club=formatage.club(club),
        categorie=formatage.categorie(categorie),
        dossard=dossard,
        present=dossard is not None,
        source=source,
    )
    db.session.add(p)
    # Sans cette incrementation, les telephones ne verraient jamais le nouveau
    # venu : ils ne retelechargent le catalogue que si la version a bouge.
    incrementer_catalogue(comp)
    db.session.commit()
    logger.info("participant ajoute : %s (dossard %s)", p.nom_complet, dossard)
    return p


def dossards_pris(comp: Competition) -> list[int]:
    """Les dossards deja attribues dans cette competition, tries."""
    return sorted(
        d for (d,) in db.session.query(Participant.dossard)
        .filter(Participant.competition_id == comp.id,
                Participant.dossard.isnot(None))
        if d is not None
    )


def prochain_dossard(comp: Competition) -> int:
    """Le plus petit numero LIBRE. Un trou d'abord, sinon la suite.

    Choix d'Adrien du 30/08 : « on ne prend que des emplacements de dossard
    libre ». Avec 1, 2, 3, 7, 8 en base, on rend 4. Sans trou, 1..109 rend 110.

    Sur cent vingt participants, c'est la lecture d'une colonne et une boucle :
    le cout est nul, et l'algorithme se lit d'un coup d'oeil -- ce qui compte
    davantage ici que la finesse.

    ⚠️ Ce calcul ne garantit RIEN a lui seul : entre le moment ou il rend un
    numero et celui ou la ligne est ecrite, une autre requete peut avoir pris le
    meme. Ce qui protege, c'est la contrainte d'unicite en base, et la retente
    de [ajouter_participant_numerote].
    """
    attendu = 1
    for pris in dossards_pris(comp):
        if pris > attendu:
            break                       # trou trouve
        if pris == attendu:
            attendu += 1
    return attendu


def ajouter_participant_numerote(nom: str, prenom: str | None = None,
                                 club: str | None = None,
                                 categorie: str | None = None,
                                 essais: int = 5) -> Participant:
    """Ajoute un participant en lui attribuant le prochain dossard libre.

    **La politique « toute inscription recoit un numero » est ici, pas dans
    [ajouter_participant].** Celle-ci sait encore creer un inscrit SANS dossard,
    et le modele de la spec 002 en depend : l'absent sans numero est precisement
    celui dont on reprend le dossard.

    Deux organisateurs qui inscrivent en meme temps calculent le meme « plus
    petit numero libre ». C'est la contrainte `uq_dossard_competition` qui
    tranche -- pas le calcul. On attrape les deux formes que prend ce conflit :

    - `ErreurMetier(409)` : le controle d'occupation a vu l'autre arriver ;
    - `IntegrityError` : l'autre est arrive entre le controle et le commit.

    Au-dela de `essais` tentatives, ce n'est plus une course mais un defaut : il
    doit remonter plutot qu'etre avale.
    """
    comp = competition_active()
    derniere = None
    for _ in range(essais):
        numero = prochain_dossard(comp)
        try:
            return ajouter_participant(nom, prenom=prenom, club=club,
                                       categorie=categorie, dossard=numero)
        except ErreurMetier as e:
            if e.code != 409:
                raise                   # « nom obligatoire » : retenter n'y changerait rien
            derniere = e
        except IntegrityError as e:
            db.session.rollback()
            derniere = e
        logger.warning("dossard %s pris pendant l'inscription, nouvelle tentative",
                       numero)
    raise ErreurMetier(
        "Impossible d'attribuer un dossard : trop de saisies simultanees. "
        "Reessaie dans un instant.", code=409) from derniere


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

    # Journalise, meme quand le dossard etait libre : c'est la comparaison entre
    # cette heure et celle du scan qui permettra de reperer une reussite arrivee
    # apres coup (voir ReaffectationDossard et reussites_suspectes).
    db.session.add(ReaffectationDossard(
        competition_id=comp.id,
        dossard=dossard,
        ancien_participant_id=ancien.id if ancien and ancien.id != participant.id else None,
        nouveau_participant_id=participant.id,
        effectuee_le=datetime.now(),
    ))
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


def incrementer_tous_les_catalogues() -> int:
    """Signale un changement de donnée **globale**. Rend le nombre d'éditions
    prévenues.

    ⚠️ **Pour ce qui n'appartient à aucune compétition.** Le plan du mur est le
    premier cas : le club a un mur, pas un mur par édition (spec 029 F1), et il
    voyage pourtant dans le catalogue de chacune. `incrementer_catalogue` ne
    sait prévenir qu'une seule édition, et **aucune** quand il n'y en a pas
    d'active — or c'est exactement le moment où l'on redessine le mur.

    ⚠️ **Un numéro NEUF par édition, jamais le même pour deux.** Le 304 de
    `/api/v2/catalog` se décide par égalité stricte, et c'est délibéré : un
    client qui annonce un numéro venu d'ailleurs n'est pas à jour. Donner le
    même numéro à deux éditions ferait donc répondre « rien de neuf » à un
    téléphone qui vient de changer de compétition et qui a besoin d'une autre
    liste de participants. On tire donc un numéro par édition, sur l'horloge
    commune.
    """
    editions = Competition.query.order_by(Competition.id).all()
    for comp in editions:
        comp.catalogue_version = prochaine_version_catalogue()
        db.session.add(comp)
        # ⚠️ `flush`, sinon `prochaine_version_catalogue()` relit le maximum
        # d'avant et rend le MEME numero a l'edition suivante -- ce que la
        # docstring interdit deux lignes plus haut.
        db.session.flush()
    return len(editions)


def enregistrer_lot(elements: list[dict], appareil: dict | None = None) -> list[dict]:
    """Enregistre un lot de réussites. Un élément qui échoue n'entraîne pas les autres.

    C'est la règle centrale de la route de lot : **un lot n'échoue jamais en
    bloc**. Si un dossard sur cinq est inconnu — un QR mal imprimé, un
    participant retiré — les quatre autres sont enregistrés. Sinon un seul mauvais
    code bloquerait la file d'un juge pour toute la compétition.

    Chaque élément est traité dans sa propre transaction, pour la même raison :
    une erreur d'intégrité sur l'un ne doit pas emporter le commit des autres.

    Renvoie un verdict par élément, dans l'ordre reçu.
    """
    resultats = []
    for element in elements:
        ref = element.get("ref")
        try:
            participant = participant_par_dossard(element.get("bib"))
            bloc = bloc_par_tag(element.get("bloc"))
        except ErreurMetier as e:
            resultats.append({"ref": ref, "etat": "refusee", "message": e.message})
            continue

        try:
            _, nouvelle = enregistrer_reussite(
                participant, bloc,
                dossard_scanne=participant.dossard,
                scanne_le=_horodatage_client(element.get("at")),
                appareil=appareil,
                ref_client=str(ref) if ref else None,
                hors_circuit_force=_hors_circuit(element),
            )
        except Exception as e:
            # On NE marque PAS l'element comme traite : l'application le garde
            # en file et reessaiera. Perdre une reussite est le seul resultat
            # inacceptable ici.
            db.session.rollback()
            logger.warning("lot : echec sur ref=%s : %s", ref, e)
            continue

        resultats.append({"ref": ref,
                          "etat": "enregistree" if nouvelle else "deja_connue"})
    return resultats


def _hors_circuit(element: dict) -> bool | None:
    """Le drapeau envoye par le telephone, ou `None` s'il n'en envoie pas.

    Le meme principe que `identite_appareil` : une valeur mal formee est
    IGNOREE, jamais rejetee. Perdre une reussite parce qu'un champ facultatif
    est bizarre serait le pire des echanges -- et un juge n'a aucun moyen de
    comprendre un tel refus le jour J.

    ⚠️ On distingue « absent » de « faux » : une application qui n'envoie pas le
    champ n'a rien verifie, et le dire serait mentir. Voir le commentaire de
    `Success.hors_circuit_force`.
    """
    if "hors_circuit" not in element:
        return None
    valeur = element.get("hors_circuit")
    return bool(valeur) if isinstance(valeur, bool) else None


def identite_appareil(valeur) -> dict | None:
    """Lit l'identite du telephone dans le corps d'un lot. Ne leve jamais.

    ⚠️ Le principe est celui du reste de la route : **une identite mal formee
    est ignoree, jamais rejetee.** Perdre une reussite parce qu'un nom contient
    un caractere inattendu serait le pire des echanges — et un juge n'a aucun
    moyen de comprendre ni de corriger un tel refus le jour J.

    Renvoie `None` quand il n'y a rien d'exploitable : une application plus
    ancienne, qui n'envoie pas d'identite, continue simplement de fonctionner.
    """
    if not isinstance(valeur, dict):
        return None
    identifiant = valeur.get("id")
    if not isinstance(identifiant, str) or not identifiant.strip():
        return None

    nom = valeur.get("nom")
    if not isinstance(nom, str) or not nom.strip():
        nom = None
    else:
        # Coupe a la longueur de la colonne. Un nom trop long tronque reste
        # utilisable ; un envoi rejete pour ca ne le serait pas.
        nom = nom.strip()[:60]

    return {"id": identifiant.strip()[:40], "nom": nom}


def _horodatage_client(valeur) -> datetime | None:
    """L'heure du scan telle que le telephone la donne. Indicative, jamais triante.

    Une horloge de telephone peut etre fausse de plusieurs heures. On la garde
    pour le diagnostic, on ne s'en sert jamais pour ordonner quoi que ce soit —
    `horodatage`, pose par le serveur, fait foi.
    """
    if not valeur:
        return None
    try:
        return datetime.fromisoformat(str(valeur).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def supprimer_reussite(reussite_id: int, par: str) -> dict:
    """Supprime une reussite saisie par erreur, en laissant une trace.

    Le geste est destructeur et sans confirmation possible dans le feu de
    l'action : on journalise QUI, QUOI et QUAND avant d'effacer. Sans cette
    trace, un score qui change entre deux consultations serait inexplicable.
    """
    r = db.session.get(Success, reussite_id)
    if r is None:
        raise ErreurMetier(f"Reussite {reussite_id} inconnue", code=404)

    trace = {
        "reussite_id": r.id,
        "participant": r.participant.nom_complet if r.participant else None,
        "bloc": r.bloc.tag if r.bloc else None,
        "source": r.source,
        "etait_synchronisee": r.sheet_synced_at is not None,
    }
    logger.warning("SUPPRESSION de reussite par %s : %s sur %s (source=%s, "
                   "deja au classeur=%s)",
                   par, trace["participant"], trace["bloc"], trace["source"],
                   trace["etait_synchronisee"])
    db.session.delete(r)
    db.session.commit()
    return trace


def reussites_suspectes(comp: Competition | None = None) -> list[dict]:
    """Les réussites arrivées APRÈS que leur dossard ait changé de main.

    Adrien a tranché le 28/08 : une réussite en file d'attente qui arrive après
    une réaffectation est **acceptée**, et suit le nouveau porteur du dossard.
    Cette fonction ne remet pas ce choix en cause — elle le rend consultable.

    Sans elle, la réussite serait attribuée au mauvais grimpeur en silence. Avec
    elle, un organisateur peut voir la liste et trancher lui-même. C'est la
    différence entre un compromis assumé et une erreur invisible.
    """
    comp = comp or competition_active()
    reaffectations = ReaffectationDossard.query.filter_by(competition_id=comp.id).all()
    if not reaffectations:
        return []

    suspectes = []
    for r in reaffectations:
        candidates = (Success.query
                      .join(Participant, Success.participant_id == Participant.id)
                      .filter(Participant.competition_id == comp.id,
                              Success.dossard_scanne == r.dossard,
                              Success.scanne_le.isnot(None),
                              Success.scanne_le < r.effectuee_le,
                              Success.horodatage > r.effectuee_le)
                      .all())
        for s in candidates:
            suspectes.append({
                "reussite_id": s.id,
                "dossard": r.dossard,
                "bloc": s.bloc.tag if s.bloc else None,
                "attribuee_a": s.participant.nom_complet if s.participant else None,
                "scannee_le": s.scanne_le.isoformat() if s.scanne_le else None,
                "reaffectation_le": r.effectuee_le.isoformat(),
                "message": (f"Scannee avant la reaffectation du dossard {r.dossard}, "
                            f"arrivee apres : elle a ete attribuee au nouveau porteur."),
            })
    return suspectes


def reussites_en_attente() -> int:
    """Combien de réussites ne sont pas encore dans le classeur.

    Exposé par /health : c'est l'indicateur qui dit si le miroir suit.
    """
    return Success.query.filter(Success.sheet_synced_at.is_(None)).count()


# --- Tracabilite : quel telephone a envoye quoi (spec 011) -------------------
#
# Le besoin, tel qu'Adrien l'a pose : « il faut qu'on trace quelle mobile a
# envoye quelle reussite pour pouvoir controler ». Ce qu'on trace est un
# APPAREIL, pas une personne — les telephones changent de main dans la journee.

#: Au-dela, un telephone est considere comme silencieux et signale dans la
#: console. Dix minutes sans rien envoyer pendant une competition, c'est
#: presque toujours un juge bloque : batterie, wifi, ou application fermee.
SILENCE_S = 600


def appareils(comp: Competition, maintenant: datetime | None = None) -> list[dict]:
    """Les telephones vus sur cette competition, du plus recent au plus ancien.

    Regroupe par IDENTIFIANT et non par nom : deux telephones peuvent porter le
    meme nom — personne n'a le temps de verifier l'unicite d'un nom le jour J —
    et un meme telephone peut avoir ete renomme en cours de route.

    Le nom affiche est donc le DERNIER connu, celui du dernier envoi.
    """
    maintenant = maintenant or datetime.now()

    lignes = (
        db.session.query(
            Success.appareil_id,
            func.count(Success.id),
            func.min(Success.horodatage),
            func.max(Success.horodatage),
        )
        .join(Participant, Success.participant_id == Participant.id)
        .filter(Participant.competition_id == comp.id)
        .filter(Success.appareil_id.isnot(None))
        .group_by(Success.appareil_id)
        .all()
    )

    resultat = []
    for identifiant, nombre, premiere, derniere in lignes:
        # Le dernier nom connu : une requete par appareil, mais il y en a
        # vingt-cinq au plus. Le faire en une seule passerait par une
        # sous-requete correlee, pour un gain nul a cette echelle.
        dernier_nom = (
            db.session.query(Success.appareil_nom)
            .filter(Success.appareil_id == identifiant)
            .order_by(Success.horodatage.desc())
            .limit(1)
            .scalar()
        )
        silence = (maintenant - derniere).total_seconds() if derniere else None
        resultat.append({
            "id": identifiant,
            "nom": dernier_nom,
            "reussites": nombre,
            "premiere_le": premiere.isoformat() if premiere else None,
            "derniere_le": derniere.isoformat() if derniere else None,
            "silence_s": round(silence) if silence is not None else None,
            "silencieux": silence is not None and silence >= SILENCE_S,
        })

    resultat.sort(key=lambda a: a["derniere_le"] or "", reverse=True)
    return resultat


def reussites_tracees(comp: Competition, ref: str | None = None,
                      appareil_id: str | None = None,
                      limite: int = 100) -> list[dict]:
    """Les reussites de cette competition, filtrables par reference ou appareil.

    La recherche par reference est la raison d'etre de tout ceci : un juge lit
    six caracteres sur son ecran, l'organisateur les tape ici, et la question
    « est-ce arrive ? » a enfin une reponse.

    La reference est cherchee par PREFIXE : l'ecran du juge n'en montre que les
    six premiers caracteres, et lui demander de dicter un UUID complet au
    milieu d'une competition n'arriverait jamais.
    """
    q = (
        Success.query
        .join(Participant, Success.participant_id == Participant.id)
        .filter(Participant.competition_id == comp.id)
    )
    if ref:
        q = q.filter(Success.ref_client.like(f"{ref.strip()}%"))
    if appareil_id:
        q = q.filter(Success.appareil_id == appareil_id)

    lignes = q.order_by(Success.horodatage.desc()).limit(max(1, min(limite, 500))).all()
    return [{
        "id": r.id,
        "ref_client": r.ref_client,
        "appareil_id": r.appareil_id,
        "appareil_nom": r.appareil_nom,
        "grimpeur": r.participant.nom_complet if r.participant else None,
        "dossard": r.dossard_scanne,
        "bloc": r.bloc.tag if r.bloc else None,
        "horodatage": r.horodatage.isoformat() if r.horodatage else None,
        "source": r.source,
        "saisie_par": r.saisie_par,
        # Ce que le juge a vu au moment d'appuyer…
        "hors_circuit_force": r.hors_circuit_force,
        # …et ce qui est vrai MAINTENANT. Les deux, parce qu'ils divergent des
        # qu'on corrige le classeur -- et c'est precisement ce qu'on veut voir.
        "hors_circuit": _hors_du_circuit(r),
    } for r in lignes]


def _hors_du_circuit(reussite: Success) -> bool | None:
    """Ce bloc est-il, AUJOURD'HUI, hors du circuit de ce grimpeur ?

    Calcule a la lecture, jamais stocke : corriger le classeur doit faire
    disparaitre l'anomalie. `None` quand on ne peut pas trancher -- participant
    sans categorie, ou bloc rattache a aucun circuit.
    """
    participant, bloc = reussite.participant, reussite.bloc
    if participant is None or bloc is None:
        return None
    circuit = participant.circuit
    if not circuit:
        return None
    circuits = {bc.circuit.nom for bc in bloc.circuits}
    if not circuits:
        return None
    return circuit not in circuits
