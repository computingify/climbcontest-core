"""Logique métier de la compétition.

Tout ce qui décide est ici ; les routes ne font que traduire HTTP.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from . import formatage
from .extensions import db
from .version import VERSION
from .models import (
    Appareil, Bloc, Competition, EN_COURS, Participant, ReaffectationDossard,
    SOURCE_MANUEL, SOURCE_SCAN, Success, prochaine_version_catalogue,
)

logger = logging.getLogger(__name__)


class ErreurMetier(Exception):
    """Erreur attendue, avec un message destiné à l'utilisateur.

    `doublon` distingue le refus « cette personne est déjà inscrite » de tous
    les autres 409. Sans lui, `ajouter_participant_numerote` reessaie cinq fois
    -- il prend tout 409 pour une course sur le dossard -- et rend finalement
    « trop de saisies simultanees », qui n'a aucun rapport avec ce qui s'est
    passe. Le message le plus utile serait alors perdu.
    """

    def __init__(self, message: str, code: int = 400, doublon: bool = False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.doublon = doublon


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


def verifier_annee(valeur) -> int | None:
    """Une année de naissance saisie à la main. Rend None pour un champ vide.

    Les bornes sont larges à dessein : ce n'est pas ici qu'on juge si l'année
    est plausible — `categories.circuit()` le fait, et met l'inscription en
    attente. Ici on refuse seulement ce qui n'est pas une année.
    """
    if valeur is None or str(valeur).strip() == "":
        return None
    try:
        annee = int(str(valeur).strip())
    except (TypeError, ValueError):
        raise ErreurMetier(f"Annee de naissance invalide : {valeur!r}")
    if not 1900 <= annee <= 2100:
        raise ErreurMetier(f"Annee de naissance invalide : {annee}")
    return annee


def club_canonique(comp, nom_du_club: str | None) -> str | None:
    """L'orthographe DEJA EN BASE pour ce club, sinon celle qu'on vient de taper.

    ⚠️ C'est la piece qui ferme le dernier chemin par lequel un doublon
    revenait, et elle a ete trouvee par un test : `formatage.club()` ne preserve
    un sigle que s'il est DEJA en capitales. « CAF Vivarais » importe du
    classeur survit donc, mais « caf vivarais » tape au guichet devient « Caf
    Vivarais » -- deux clubs dans la liste deroulante, et le rapprochement qui
    echoue entre les deux.

    Aucune liste de sigles connus ne reglerait ca : il faudrait la tenir a jour
    pour chaque club de la region. La regle retenue est plus simple et plus
    juste : **la premiere orthographe fait reference**. Le club existe deja sous
    une forme ? On reprend la sienne, quelle que soit la facon dont on vient de
    l'ecrire.
    """
    propre = formatage.club(nom_du_club)
    if not propre:
        return propre
    ma_cle = formatage.identite_club(propre)
    for (existant,) in db.session.query(Participant.club).filter(
            Participant.competition_id == comp.id,
            Participant.club.isnot(None)).distinct():
        if existant and formatage.identite_club(existant) == ma_cle:
            return existant
    return propre


def participant_identique(comp, nom, prenom=None, club=None):
    """Le participant qui EST deja cette personne, ou None.

    Meme identite normalisee **et** meme club. C'est la seule combinaison qui
    autorise a parler de doublon : deux homonymes de clubs differents existent
    vraiment (risque R5), et les confondre en perdrait une.

    Un club absent d'un cote ne suffit pas a conclure -- on rend None, et
    l'appelant demande. Deviner ici ferait fusionner deux personnes sur la seule
    foi d'un champ vide.
    """
    ma_cle = formatage.identite(nom, prenom)
    if not ma_cle:
        return None
    mon_club = formatage.identite_club(club)
    if not mon_club:
        return None
    for autre in Participant.query.filter_by(competition_id=comp.id):
        if (formatage.identite(autre.nom, autre.prenom) == ma_cle
                and formatage.identite_club(autre.club) == mon_club):
            return autre
    return None


def homonymes(comp, nom, prenom=None, sauf=None) -> list:
    """Tous ceux qui portent le meme nom, quel que soit leur club.

    Sert a PREVENIR, pas a refuser : la console montre la fiche existante et
    laisse choisir. C'est ce que la contrainte metier §3 demande -- « detection
    de doublon [...] avec validation humaine ».
    """
    ma_cle = formatage.identite(nom, prenom)
    if not ma_cle:
        return []
    return [p for p in Participant.query.filter_by(competition_id=comp.id)
            if formatage.identite(p.nom, p.prenom) == ma_cle
            and (sauf is None or p.id != sauf)]


def ajouter_participant(nom: str, prenom: str | None = None,
                        club: str | None = None, categorie: str | None = None,
                        dossard: int | None = None,
                        source: str = SOURCE_MANUEL,
                        annee_naissance=None,
                        autoriser_homonyme: bool = False) -> Participant:
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

    # Verifiee ICI et non dans la route : un appel direct a l'API doit passer
    # par le meme controle que le formulaire. C'est le raisonnement du
    # formatage juste au-dessus, applique a la validation.
    annee_naissance = verifier_annee(annee_naissance)

    comp = competition_active()

    prenom = formatage.nom(prenom)
    club = club_canonique(comp, club)

    # ⚠️ La garde anti-doublon (04/09 : « je ne veux pas de doublon »).
    #
    # Elle porte sur l'IDENTITE NORMALISEE **et le club**, jamais sur le nom
    # seul. Le modele autorise deux homonymes depuis la spec 002, et c'est
    # volontaire : deux « Martin Lea » de deux clubs differents existent
    # vraiment, et le risque R5 est precisement d'en perdre une. Ce qui n'existe
    # pas, c'est deux « Martin Lea » du MEME club.
    #
    # Elle se leve explicitement -- `autoriser_homonyme` -- parce que le cas
    # rarissime doit rester possible : deux cousins homonymes au meme club, ca
    # se voit une fois, et l'organisateur doit pouvoir passer outre depuis la
    # console plutot que d'aller modifier la base.
    if not autoriser_homonyme:
        jumeau = participant_identique(comp, nom, prenom, club)
        if jumeau is not None:
            raise ErreurMetier(
                f"{jumeau.nom_complet} est deja inscrit"
                + (f" ({jumeau.club})" if jumeau.club else "")
                + (f", dossard {jumeau.dossard}" if jumeau.dossard else "")
                + ". Reprendre sa fiche, ou forcer l'ajout si ce sont deux "
                  "personnes differentes.",
                code=409, doublon=True)

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
        prenom=prenom,
        club=club,
        categorie=formatage.categorie(categorie),
        dossard=dossard,
        present=dossard is not None,
        source=source,
        annee_naissance=annee_naissance,
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
                                 essais: int = 5,
                                 source: str = SOURCE_MANUEL,
                                 annee_naissance=None,
                                 autoriser_homonyme: bool = False) -> Participant:
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
                                       categorie=categorie, dossard=numero,
                                       source=source,
                                       annee_naissance=annee_naissance,
                                       autoriser_homonyme=autoriser_homonyme)
        except ErreurMetier as e:
            if e.code != 409 or e.doublon:
                # « nom obligatoire », ou « deja inscrit » : retenter n'y
                # changerait rien, et masquerait le vrai message.
                raise
            derniere = e
        except IntegrityError as e:
            db.session.rollback()
            derniere = e
        logger.warning("dossard %s pris pendant l'inscription, nouvelle tentative",
                       numero)
    raise ErreurMetier(
        "Impossible d'attribuer un dossard : trop de saisies simultanees. "
        "Reessaie dans un instant.", code=409) from derniere


# ⚠️ `reaffecter_dossard()` a ete SUPPRIMEE le 05/09, avec sa route
# `POST /admin/participants/<id>/dossard` et le champ dossard du crayon.
#
# Elle donnait le dossard d'un absent a un arrivant de derniere minute -- une
# economie de papier, jamais une necessite : `ajouter_participant_numerote()`
# attribue un numero libre, et la console imprime la fiche.
#
# Elle fabriquait en revanche le doublon que la spec 008 promet d'empecher.
# L'absent repartait avec `dossard = NULL`, l'import du classeur ne le
# retrouvait plus par son numero, et **recreait sa fiche**. Adrien a tranche le
# 05/09 : aucun changement de dossard, nulle part.
#
# `ReaffectationDossard` et `reussites_suspectes()` restent : une base de
# production porte deja des lignes posees avant cette date, et elles doivent
# continuer a se voir a l'ecran.


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

    Depuis la spec 030, l'objet peut porter un champ `app` : la version que le
    client execute. Facultatif comme le reste, et absent de l'application
    Android -- qui doit continuer de fonctionner sans rien changer.
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

    identite = {"id": identifiant.strip()[:40], "nom": nom}

    # ⚠️ La cle `app` n'apparait QUE si le client en a envoye une. Une cle
    # toujours presente, a `None`, changerait la forme rendue a des appelants
    # qui ne demandent rien -- et deux tests de la spec 011 comparent ce
    # dictionnaire entier. Ne rien dire, c'est different de dire « rien ».
    version = valeur.get("app")
    if isinstance(version, str) and version.strip():
        identite["app"] = version.strip()[:20]

    return identite


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
    """Ce que le miroir a encore à écrire dans le classeur.

    Exposé par /health : c'est l'indicateur qui dit si le miroir suit, et c'est
    le chiffre qu'on regarde le jour de la compétition.

    ⚠️ Il comptait TOUTES les réussites non synchronisées, sans distinguer la
    compétition. Or le miroir ne sert que l'**active**. Le 03/09, `/health`
    annonçait 714 en attente pendant que le miroir n'avait plus rien à faire :
    714 réussites d'ailleurs, inenvoyables par construction, affichées à jamais.

    Le coût n'est pas cosmétique. Un vrai retard de cinquante réussites aurait
    affiché 764 — indistinguable de 714 au coup d'œil. Le garde-fou était
    aveuglé par son propre bruit, et c'est exactement le jour où il sert qu'il
    aurait manqué. Ce qui n'est pas envoyable se compte désormais à part, dans
    `reussites_inenvoyables` : on le sort du chiffre, on ne le cache pas.
    """
    from .sheets.mirror import en_attente
    comp = Competition.query.filter_by(active=True).first()
    return en_attente(comp.id) if comp else 0


def reussites_inenvoyables() -> int:
    """Celles que le miroir n'écrira JAMAIS : d'une autre compétition, ou sans dossard.

    Elles ne sont perdues pour personne — elles sont en base, et l'archive de
    leur compétition les contient. Mais elles n'iront pas dans le classeur relié
    à la compétition d'aujourd'hui, et le dire vaut mieux que de les mélanger à
    un retard qui, lui, se rattrape.
    """
    total = Success.query.filter(Success.sheet_synced_at.is_(None)).count()
    return total - reussites_en_attente()


# --- Tracabilite : quel telephone a envoye quoi (spec 011) -------------------
#
# Le besoin, tel qu'Adrien l'a pose : « il faut qu'on trace quelle mobile a
# envoye quelle reussite pour pouvoir controler ». Ce qu'on trace est un
# APPAREIL, pas une personne — les telephones changent de main dans la journee.

#: Au-dela, un telephone est considere comme silencieux et signale dans la
#: console. Dix minutes sans rien envoyer pendant une competition, c'est
#: presque toujours un juge bloque : batterie, wifi, ou application fermee.
SILENCE_S = 600

#: Au-dela, on considere que les ANNONCES de ce telephone ne nous arrivent plus.
#: Ecran allume, la PWA s'annonce toutes les TRENTE SECONDES (`juge.js`,
#: `PERIODE_PRESENCE_MS`) : un quart d'heure laisse donc passer une trentaine
#: d'occasions avant de crier au loup. Le seuil est genereux exprès -- une
#: alerte qui se declenche pour un creux de wifi apprend a ignorer les alertes.
SILENCE_ANNONCE_S = 900

#: En deca, un telephone en retard sur le catalogue est simplement en train de
#: le RATTRAPER : il s'est annonce tres recemment, donc il est en service, donc
#: il reprendra le numero tout seul dans la minute. Six minutes plutot que
#: trente secondes pour absorber un creux de wifi sans changer de discours.
#:
#: ⚠️ Au-dela, il ne devient pas « en panne » : il sort simplement du cas
#: benin. C'est ce qui fait qu'un telephone EN VEILLE -- dont la boucle ne
#: tourne plus du tout -- cesse d'etre annonce comme « se remet a jour tout
#: seul », ce qui serait faux : il attend qu'on rallume son ecran.
PERIODE_RATTRAPAGE_S = 360

#: Au-dela, un telephone sort du tableau de la console s'il n'a rien envoye sur
#: l'edition en cours. Sans cette fenetre, les telephones de toutes les editions
#: passees s'y empileraient -- et la question posee par cet ecran est « qui
#: tourne AUJOURD'HUI ».
FENETRE_APPAREIL_S = 24 * 3600


def enregistrer_annonce(identifiant: str, nom: str | None = None,
                        version_app: str | None = None,
                        catalogue_version: int | None = None,
                        maintenant: datetime | None = None) -> None:
    """Note qu'un telephone s'est manifeste. **Ne leve jamais.** (spec 030)

    Meme principe que `identite_appareil` : ce qui est mal forme est ignore,
    jamais rejete. Cette fonction est appelee depuis le chemin du catalogue --
    celui qui, s'il echoue, arrete les scans de tout le monde. Une colonne vide
    dans la console rend Adrien aveugle sur un point ; un catalogue qui n'arrive
    pas arrete la competition. Les deux ne se comparent pas.

    ⚠️ `catalogue_version` n'est passe QUE par la route du catalogue, et c'est
    volontaire. Recevoir un lot prouve que le telephone est vivant, pas qu'il
    detient le catalogue courant : ecrire le numero depuis la route des lots
    afficherait « a jour » un telephone qui ne s'est pas synchronise depuis des
    heures.
    """
    if not isinstance(identifiant, str) or not identifiant.strip():
        return
    quand = maintenant or datetime.now()
    try:
        appareil = db.session.get(Appareil, identifiant.strip()[:40])
        if appareil is None:
            appareil = Appareil(id=identifiant.strip()[:40],
                                premiere_vue_le=quand)
            db.session.add(appareil)
        # Un champ absent ne DOIT PAS effacer ce qu'on savait : un lot sans nom
        # ne rend pas un telephone anonyme.
        if nom:
            appareil.nom = nom[:60]
        if version_app:
            appareil.version_app = version_app[:20]
        if catalogue_version is not None:
            appareil.catalogue_version = catalogue_version
            appareil.catalogue_vu_le = quand
        appareil.vu_le = quand
        db.session.commit()
    except Exception as e:
        # Une base verrouillee, une colonne manquante sur une vieille base : on
        # journalise et on rend la main. L'appelant continue son travail.
        db.session.rollback()
        logger.warning("annonce d'appareil ignoree (%s) : %s", type(e).__name__, e)

#: Le nombre de caracteres d'`appareil_id` qui suffisent a distinguer les
#: telephones d'une competition. Huit caracteres d'UUID, c'est ce que
#: l'application affiche deja dans ses reglages et ce que la colonne
#: « Identifiant » de la console montre : le juge peut donc LIRE le meme code
#: sur son ecran et le dicter par radio.
CODE_APPAREIL_CARACTERES = 8


def libelle_poste(nom: str | None, appareil_id: str | None) -> str | None:
    """Comment un poste se nomme dans la console : « Zone A (3f9a1c2b) ».

    ⚠️ **PLUSIEURS TELEPHONES PEUVENT PORTER LE MEME NOM**, et c'est desormais
    la norme, pas l'accident. Depuis la spec 034, un poste se nomme en scannant
    le carton pose sur la table : deux juges affectes a la meme zone scannent
    le MEME carton, et leurs deux telephones s'appellent « Zone A ». Adrien, le
    03/09 : « il peut y avoir plusieurs telephones par zone [...] ce que je
    veux, c'est que tu sois capable de les distinguer cote console ».

    Deux lignes « Zone A » cote a cote ne disent pas laquelle est laquelle. Le
    code court les separe -- et il n'invente RIEN : `appareil_id` est l'UUID
    que `static/juge/identite.js` pose sur chaque telephone depuis la spec 011,
    et que la vue « Telephones » affiche deja dans sa colonne « Identifiant ».
    Ce qui manquait n'etait pas une donnee, c'etait de la LISIBILITE.

    ⚠️ **UNE SEULE FONCTION COMPOSE CE LIBELLE**, et toutes les vues de la
    console l'appellent -- « Qui envoie quoi », la colonne « Telephone » de la
    recherche de scans, et ce qui viendra. La forme exacte (parentheses, tiret,
    code devant ou derriere) est en cours d'arbitrage : elle doit rester une
    modification d'un seul endroit.

    Rend `None` quand il n'y a pas d'appareil du tout -- une saisie manuelle
    n'en a pas, et lui en inventer un serait faux. L'appelant sait quoi dire a
    la place (« saisie de adrien »).
    """
    code = str(appareil_id or "").strip()[:CODE_APPAREIL_CARACTERES]
    propre = str(nom or "").strip()
    if not code:
        return propre or None
    if not propre:
        # Un telephone qui envoie sans s'etre nomme. Le code seul serait
        # illisible ; « Sans nom » seul se confondrait avec les autres.
        return f"Sans nom ({code})"
    return f"{propre} ({code})"


def appareils(comp: Competition, maintenant: datetime | None = None) -> list[dict]:
    """Les telephones connus de cette competition, du plus recent au plus ancien.

    Regroupe par IDENTIFIANT et non par nom : deux telephones peuvent porter le
    meme nom — personne n'a le temps de verifier l'unicite d'un nom le jour J —
    et un meme telephone peut avoir ete renomme en cours de route.

    Le nom affiche est donc le DERNIER connu, celui du dernier envoi.

    ⚠️ **Deux sources, et il en faut deux** (spec 030) :

    1. les REUSSITES de l'edition en cours -- qui a envoye quoi, et quand ;
    2. les ANNONCES, table `appareil` -- qui tourne sur quelle version, avec
       quel catalogue.

    Un telephone peut n'etre que dans la seconde : c'est le cas du matin, quand
    les juges ouvrent l'application avant la premiere grimpe. C'est precisement
    celui qu'on veut voir -- verifier les versions APRES la premiere reussite,
    c'est verifier trop tard.

    Un telephone peut n'etre que dans la premiere : l'application Android du
    Play Store envoie des lots et ne s'annonce pas. Ses colonnes de version
    restent vides, et c'est deja un renseignement.
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

    par_id: dict[str, dict] = {}
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
        par_id[identifiant] = {
            "id": identifiant,
            "nom": dernier_nom,
            "reussites": nombre,
            "premiere_le": premiere.isoformat() if premiere else None,
            "derniere_le": derniere.isoformat() if derniere else None,
            "silence_s": round(silence) if silence is not None else None,
            "silencieux": silence is not None and silence >= SILENCE_S,
            # Le nom SUIVI du code court : deux juges d'une meme zone scannent
            # le meme carton et portent le meme nom. Voir `libelle_poste`.
            "libelle": libelle_poste(dernier_nom, identifiant),
            # Comblees juste apres par la table des annonces, quand elle en a.
            "version_app": None,
            "catalogue_version": None,
            "vu_le": None,
            "annonce": False,
            "app_a_jour": None,
            "catalogue_a_jour": None,
            "annonce_perdue": False,
            "rattrapage": False,
        }

    depuis = maintenant - timedelta(seconds=FENETRE_APPAREIL_S)
    for annonce in Appareil.query.filter(Appareil.vu_le >= depuis).all():
        fiche = par_id.get(annonce.id)
        if fiche is None:
            # Vu, mais rien envoye sur cette edition. Il compte quand meme.
            fiche = {
                "id": annonce.id,
                "nom": annonce.nom,
                "reussites": 0,
                "premiere_le": None,
                "derniere_le": None,
                "silence_s": None,
                "silencieux": False,
                "libelle": libelle_poste(annonce.nom, annonce.id),
            }
            par_id[annonce.id] = fiche
        # Le nom d'une annonce est plus FRAIS que celui recopie sur la derniere
        # reussite : un juge qui renomme son poste sans rien scanner ensuite
        # verrait sinon l'ancien nom jusqu'a sa prochaine reussite.
        if annonce.nom:
            fiche["nom"] = annonce.nom
            # Le libelle derive du nom : il se refait ici, sinon la vue
            # « Qui envoie quoi » garderait l'ancien nom entre parentheses.
            fiche["libelle"] = libelle_poste(annonce.nom, annonce.id)
        fiche["version_app"] = annonce.version_app
        fiche["catalogue_version"] = annonce.catalogue_version
        fiche["vu_le"] = annonce.vu_le.isoformat() if annonce.vu_le else None
        fiche["annonce"] = annonce.version_app is not None
        # ⚠️ EGALITE STRICTE, jamais un ordre. Le numero de catalogue identifie
        # un couple (edition, etat de son catalogue) : depuis la fermeture de
        # l'incoherence du plan, il SAUTE et il saute pour toutes les editions a
        # la fois. « Plus grand » ne veut rien dire ; « different » veut dire
        # « pas les memes donnees ».
        fiche["app_a_jour"] = (
            None if not annonce.version_app else annonce.version_app == VERSION)
        fiche["catalogue_a_jour"] = (
            None if annonce.catalogue_version is None
            else annonce.catalogue_version == comp.catalogue_version)
        fiche["annonce_perdue"] = _annonce_perdue(annonce, fiche, maintenant)
        fiche["rattrapage"] = _rattrapage(annonce, fiche, maintenant)

    resultat = list(par_id.values())
    # Trie sur la derniere ACTIVITE, quelle qu'elle soit : un telephone qui
    # s'annonce sans rien envoyer est actif, et doit remonter.
    resultat.sort(key=lambda a: max(a["derniere_le"] or "", a["vu_le"] or ""),
                  reverse=True)
    return resultat


def _annonce_perdue(annonce: Appareil, fiche: dict,
                    maintenant: datetime) -> bool:
    """Ce telephone envoie-t-il des reussites SANS plus s'annoncer ? (spec 030)

    C'est la signature exacte d'un cache pose devant `/api/v2/catalog` : les
    lots partent en POST, qu'aucun cache n'absorbe, tandis que l'annonce voyage
    sur un GET qui, lui, peut etre servi depuis un cache sans jamais atteindre
    l'application. Le serveur cesse alors de savoir qui tourne sur quoi, et
    RIEN ne le dirait -- le tableau se viderait tout seul, et on croirait les
    telephones eteints.

    Trois conditions, et les trois comptent :

    - le telephone SAIT s'annoncer (on connait sa version) -- sinon c'est
      l'application Android, et son silence est normal ;
    - il a envoye une reussite recemment -- sinon il est simplement eteint, ce
      que `silencieux` dit deja ;
    - sa derniere annonce date de plus d'un quart d'heure, alors qu'ecran
      allume la PWA s'annonce toutes les trente secondes.

    ⚠️ La deuxieme condition n'est pas un confort, c'est ce qui rend le
    detecteur SUR : la boucle de l'application sort des sa premiere ligne quand
    l'ecran est eteint, donc un telephone en veille n'envoie rien ET ne
    s'annonce plus. Exiger une reussite recente elimine ce cas -- il ne reste
    que celui ou les lots passent pendant que les annonces disparaissent, ce
    qui ne peut venir que d'un cache pose devant le GET.

    ⚠️ **CE RAISONNEMENT REPOSE SUR UNE HYPOTHESE : aucun lot ne part hors du
    premier plan.** Elle est vraie aujourd'hui -- les cinq chemins d'envoi de
    `juge.js` sont soit la boucle (qui teste `visibilityState`), soit un geste
    du juge -- et `sw.js` n'ecoute ni `sync` ni `periodicsync`. Le jour ou
    quelqu'un ajoutera une synchronisation en arriere-plan pour vider la file
    hors ligne -- une evolution naturelle pour une PWA offline-first -- des
    lots partiront sans annonce, et ce detecteur criera au cache sur un
    telephone en veille parfaitement sain. Verifier `sw.js` avant de conclure,
    et rendre alors l'annonce solidaire de l'envoi.
    """
    if not annonce.version_app:
        return False
    if fiche["silence_s"] is None or fiche["silence_s"] >= SILENCE_S:
        return False
    # Jamais annonce du tout : c'est le cas d'un cache pose des le depart. Mais
    # on laisse passer le quart d'heure qui suit la premiere apparition, sinon
    # un telephone qui vient d'envoyer son premier lot avant meme d'avoir
    # telecharge son catalogue declencherait l'alerte pour quelques secondes.
    reference = annonce.catalogue_vu_le or annonce.premiere_vue_le
    if reference is None:
        return False
    return (maintenant - reference).total_seconds() >= SILENCE_ANNONCE_S


def _rattrapage(annonce: Appareil, fiche: dict, maintenant: datetime) -> bool:
    """Ce telephone est-il en retard sur le catalogue, mais en train de le
    rattraper ? (spec 030)

    ⚠️ La distinction existe pour une raison precise, et elle est arrivee avec
    la fermeture de l'incoherence du plan : redessiner le mur donne un numero
    NEUF a toutes les editions d'un coup. Le jour ou un organisateur retouche
    le plan en pleine competition, les vingt-cinq telephones passent en ambre
    EN MEME TEMPS -- et il croira avoir tout casse, alors que ceux qui sont en
    service reprennent le numero dans la minute.

    Ce qui separe ce cas de la vraie panne : ici l'annonce de catalogue est
    FRAICHE. Le telephone parle, il n'a simplement pas encore repris le nouveau
    numero. Quand un cache absorbe les annonces, c'est l'inverse -- elles
    vieillissent, et `_annonce_perdue` s'allume.

    ⚠️ On regarde `catalogue_vu_le`, et surtout pas `vu_le` : ce dernier avance
    aussi a chaque lot, donc un telephone dont les annonces sont mangees par un
    cache passerait pour un simple rattrapage. Les deux horodatages sont
    distincts exactement pour ca.
    """
    if fiche["catalogue_a_jour"] is not False:
        return False
    if annonce.catalogue_vu_le is None:
        return False
    age = (maintenant - annonce.catalogue_vu_le).total_seconds()
    return age < PERIODE_RATTRAPAGE_S


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
        # Le meme libelle que dans « Qui envoie quoi », compose au meme
        # endroit : deux vues qui nommeraient un poste differemment obligeraient
        # a faire la correspondance de tete, au pire moment.
        "appareil_libelle": libelle_poste(r.appareil_nom, r.appareil_id),
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
