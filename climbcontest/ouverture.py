"""La préparation des ouvreurs — spec 044.

Ce que les ouvreurs déclarent, zone par zone, sur le plan de la salle : les
voies qu'ils posent, leur couleur de difficulté, leur couleur de prises et les
catégories pour lesquelles elles comptent.

**Aucun Flask ici**, comme `fiches.py`, `cycle.py`, `circuits.py` et `suivi.py` :
ce module ne parle qu'à la base, et tout se teste sans client HTTP.

LE NOM D'UNE VOIE
-----------------
C'est **l'initiale de sa couleur suivie de son rang dans cette couleur** :
« V7 » est la septième verte de la salle. Ce n'est pas une invention — c'est
déjà la convention du club, lisible dans `fixtures/contest-nov2025.json` :
« z J4 » (zone z, Jaune n°4), « a B10 », « b R8 ».

Le `tag` — le contenu du QR que le juge scanne — est **zone + nom** : « J » +
« V7 » = « JV7 ».

CE QUI SE PASSE QUAND ON N'A PAS ENCORE DE COULEUR
-------------------------------------------------
Une voie peut vivre sans couleur : le remplissage s'étale sur plusieurs
séances. Elle porte alors un tag de réserve, « J?12 », qui n'a qu'un rôle —
satisfaire `uq_bloc_tag` sans mentir sur ce qu'elle est. Aucun QR ne se génère
à partir de lui : une voie incomplète ne s'imprime pas.
"""

import logging

from .classement import COULEURS
from .extensions import db
from .models import (Bloc, BlocCircuit, Circuit, PREPARATION, SOURCE_CONSOLE,
                     Success)

logger = logging.getLogger(__name__)

#: L'initiale de chaque couleur de difficulté.
#:
#: ⚠️ Écrit à la main, et **vérifié par un test** contre `classement.COULEURS` :
#: les six initiales doivent être deux à deux distinctes et couvrir exactement
#: les six couleurs. Une septième couleur ajoutée un jour sans initiale
#: fabriquerait des tags en collision, et `uq_bloc_tag` transformerait une
#: saisie ordinaire en erreur 500.
INITIALES = {"Jaune": "J", "Vert": "V", "Bleu": "B",
             "Mauve": "M", "Rouge": "R", "Noir": "N"}

#: Le marqueur d'une voie sans couleur, dans son tag de réserve.
SANS_COULEUR = "?"

#: Ce qui sépare les deux couleurs d'une prise bicolore : « Bleu/Blanc ».
SEPARATEUR_PRISES = "/"

#: Deux, et pas plus. Une prise tricolore existe peut-être quelque part ; sur
#: un mur, on ne la retrouve pas des yeux — et c'est la seule chose que cette
#: couleur sert à faire.
PRISES_MAXI = 2

#: L'ordre de référence des couleurs de prises. Il ne sert QU'À canonicaliser
#: une paire — voir `ranger_prises`.
#:
#: ⚠️ Relevé sur les trois classeurs archivés (novembre 2025, mars 2026 et
#: l'édition précédente), pas inventé : ce sont les couleurs que le club pose
#: réellement. « Mint » n'y figurait qu'une fois, et il y est quand même — une
#: couleur écrite une seule fois est une couleur qu'on doit pouvoir réécrire.
ORDRE_PRISES = ("Blanc", "Gris", "Noir", "Beige", "Marron", "Jaune", "Fluo",
                "Orange", "Rouge", "Rose", "Violet", "Bleu", "Turquoise",
                "Mint", "Vert")


def ranger_prises(valeurs) -> str | None:
    """Une, deux ou zéro couleur de prises → la chaîne rangée en base.

    ⚠️ **L'ORDRE EST CANONIQUE**, et ce n'est pas de la coquetterie : sans lui,
    la même prise physique s'écrit « Bleu/Blanc » chez l'un et « Blanc/Bleu »
    chez l'autre. Deux chaînes pour un objet, et tout ce qui compare —
    l'étiquette, un filtre, un futur regroupement — voit deux couleurs
    différentes là où il n'y en a qu'une.

    Une couleur inconnue de `ORDRE_PRISES` n'est pas refusée : le classeur a pu
    y écrire un mot que nous ne connaissons pas, et il doit survivre. Elle passe
    simplement **après** celles qu'on connaît, dans l'ordre alphabétique.
    """
    if valeurs is None:
        return None
    if isinstance(valeurs, str):
        valeurs = valeurs.split(SEPARATEUR_PRISES)
    propres, vues = [], set()
    for v in valeurs:
        v = str(v or "").strip()
        if not v or v in vues:
            continue
        if SEPARATEUR_PRISES in v:
            raise ErreurOuverture(
                f"« {v} » ne peut pas contenir « {SEPARATEUR_PRISES} ».", code=400)
        vues.add(v)
        propres.append(v)
    if not propres:
        return None
    if len(propres) > PRISES_MAXI:
        raise ErreurOuverture(
            f"Une prise porte au plus {PRISES_MAXI} couleurs.", code=400)
    rang = lambda v: (ORDRE_PRISES.index(v) if v in ORDRE_PRISES
                      else len(ORDRE_PRISES), v)
    return SEPARATEUR_PRISES.join(sorted(propres, key=rang))


def prises_de(bloc) -> list[str]:
    """Les couleurs de prises d'une voie, une ou deux. Jamais `None`."""
    if not bloc.couleur_prises:
        return []
    return [v for v in bloc.couleur_prises.split(SEPARATEUR_PRISES) if v]

#: Même plafond que `plan_du_mur.ZONE_MAXI` : une zone est une lettre, deux au
#: pire. Le plan est la seule source de vérité sur ce qui existe, mais on borne
#: ici pour que rien d'absurde n'entre en base.
ZONE_MAXI = 3


class ErreurOuverture(Exception):
    """Refus attendu, avec un message destiné à l'écran."""

    def __init__(self, message: str, code: int = 409):
        super().__init__(message)
        self.message = message
        self.code = code


# --- Ce qui a le droit de bouger --------------------------------------------

def ecriture_permise() -> bool:
    """La saisie n'est ouverte que par le mode sans classeur (spec 045).

    Import tardif : `sans_classeur` lit la base, ce module aussi, et les faire
    se connaître en tête créerait un cycle le jour où l'un des deux grandira.
    """
    from . import sans_classeur
    return sans_classeur.actif()


def verifier_modifiable(comp) -> None:
    """Les deux garde-fous qui valent pour TOUTE écriture."""
    if not ecriture_permise():
        raise ErreurOuverture(
            "Les voies viennent du classeur : cet ecran est en consultation. "
            "Debrancher le classeur dans les Reglages pour les saisir ici.")
    # ⚠️ Un tag qui change pendant la competition, c'est un QR colle sur le mur
    # qui ne designe plus rien : le juge scanne, l'application repond « bloc
    # inconnu », et le grimpeur perd sa reussite.
    if comp.statut != PREPARATION:
        raise ErreurOuverture(
            f"« {comp.nom} » n'est plus en preparation : les voies ne se "
            f"modifient plus. Repasser l'edition en preparation pour y "
            f"revenir.")


def _reussites(bloc) -> int:
    return Success.query.filter_by(bloc_id=bloc.id).count()


def _refuser_si_reussites(bloc, geste: str) -> None:
    """Une voie qui porte une réussite ne change plus d'identité.

    Même règle, et même formulation, que la réaffectation de dossard
    (`docs/contraintes-metier.md` §1) : on nomme le nombre, parce que c'est lui
    qui permet de décider quoi faire.
    """
    combien = _reussites(bloc)
    if combien:
        raise ErreurOuverture(
            f"« {bloc.tag} » porte {combien} reussite(s) : impossible de "
            f"{geste}. Supprimer d'abord ces reussites si elles sont des essais.")


# --- Lecture ----------------------------------------------------------------

def _rang_couleur(couleur) -> int:
    return COULEURS.index(couleur) if couleur in COULEURS else len(COULEURS)


def nom_de(bloc) -> str | None:
    """« JV7 » → « V7 ». `None` tant que la voie n'a pas de couleur."""
    if not bloc.couleur or bloc.numero_couleur is None:
        return None
    return f"{INITIALES.get(bloc.couleur, '')}{bloc.numero_couleur}"


def est_complete(bloc, circuits: list) -> bool:
    """Une voie est complète quand elle porte une couleur ET une catégorie.

    C'est le seul jugement que l'écran porte sur une voie, et c'est ce que
    compte la pastille de sa zone.
    """
    return bool(bloc.couleur) and bool(circuits)


def inventaire(comp) -> dict:
    """Zones → voies, compteurs, répartition par couleur.

    **Cinq requêtes**, quel que soit le nombre de voies : les blocs, les
    circuits, les liens entre les deux, le compte des réussites par bloc, et le
    réglage du mode sans classeur.

    ⚠️ L'architecture en annonçait trois, écrites avant le code. Les deux de
    plus sont assumées, et chacune pour une raison :

    - le **compte des réussites** dit quelles voies sont verrouillées. Sans
      lui, l'écran proposerait de supprimer ce que le serveur refusera — pire
      qu'une requête de plus ;
    - le **réglage** est relu à chaque décision, jamais mémorisé. C'est le
      principe posé par `sans_classeur` : avec quatre workers gunicorn, un
      cache laisserait trois d'entre eux ignorer une bascule.

    Ce qui compte, et ce que le test vérifie, c'est que ce nombre **ne dépend
    pas du nombre de voies**.
    """
    blocs = Bloc.query.filter_by(competition_id=comp.id).all()
    circuits = Circuit.query.filter_by(competition_id=comp.id).order_by(
        Circuit.nom).all()
    par_id = {c.id: c.nom for c in circuits}

    liens: dict[int, list[str]] = {}
    for bloc_id, circuit_id in db.session.query(
            BlocCircuit.bloc_id, BlocCircuit.circuit_id).join(
            Bloc, BlocCircuit.bloc_id == Bloc.id).filter(
            Bloc.competition_id == comp.id).all():
        nom = par_id.get(circuit_id)
        if nom:
            liens.setdefault(bloc_id, []).append(nom)

    comptes_reussites = dict(
        db.session.query(Success.bloc_id, db.func.count(Success.id))
        .join(Bloc, Success.bloc_id == Bloc.id)
        .filter(Bloc.competition_id == comp.id)
        .group_by(Success.bloc_id).all())

    voies: list[dict] = []
    for bloc in blocs:
        siens = sorted(liens.get(bloc.id, []))
        voies.append({
            "id": bloc.id,
            "zone": bloc.zone or "",
            "tag": bloc.tag,
            "nom": nom_de(bloc),
            "couleur": bloc.couleur,
            "couleur_prises": bloc.couleur_prises,
            # La chaîne ET la liste : la chaîne pour ce qui s'imprime et se
            # compare, la liste pour ce qui se dessine — un disque en deux
            # moitiés a besoin de deux teintes, pas d'une phrase à découper.
            "couleurs_prises": prises_de(bloc),
            "circuits": siens,
            "complete": est_complete(bloc, siens),
            "reussites": comptes_reussites.get(bloc.id, 0),
            "source": bloc.source or "classeur",
        })

    # L'ordre du classeur : la difficulte d'abord, le rang ensuite. C'est celui
    # de la fiche du grimpeur -- deux documents qui rangent les memes voies
    # autrement, c'est un document de plus a dechiffrer.
    voies.sort(key=lambda v: (_rang_couleur(v["couleur"]),
                              v["nom"] is None,
                              v["nom"] or "", v["id"]))

    par_zone: dict[str, list[dict]] = {}
    for voie in voies:
        par_zone.setdefault(voie["zone"], []).append(voie)

    par_couleur = {c: 0 for c in COULEURS}
    for voie in voies:
        if voie["couleur"] in par_couleur:
            par_couleur[voie["couleur"]] += 1

    completes = sum(1 for v in voies if v["complete"])
    return {
        "competition": {"id": comp.id, "nom": comp.nom, "statut": comp.statut},
        "ecriture": ecriture_permise() and comp.statut == PREPARATION,
        "zones": par_zone,
        "circuits": [{"id": c.id, "nom": c.nom,
                      "voies": sum(1 for v in voies if c.nom in v["circuits"])}
                     for c in circuits],
        "totaux": {
            "voies": len(voies),
            "completes": completes,
            "a_completer": len(voies) - completes,
            "zones_saisies": len(par_zone),
            "par_couleur": par_couleur,
            "sans_couleur": sum(1 for v in voies if not v["couleur"]),
        },
    }


# --- Écriture ---------------------------------------------------------------

def _tag_de_reserve(zone: str, numero: int) -> str:
    return f"{zone}{SANS_COULEUR}{numero}"


def _prochain_rang(comp, couleur: str) -> int:
    """Le premier rang libre de cette couleur.

    ⚠️ `max + 1`, et surtout PAS `count + 1`. Après une suppression,
    `count + 1` rendrait un rang **déjà pris**, et `uq_bloc_tag` ferait échouer
    la saisie suivante. Le `max` laisse des trous — c'est précisément ce que
    « Renuméroter » sert à refermer.
    """
    maximum = db.session.query(db.func.max(Bloc.numero_couleur)).filter(
        Bloc.competition_id == comp.id, Bloc.couleur == couleur).scalar()
    return (maximum or 0) + 1


def _prochain_numero(comp) -> int:
    """L'ordinal interne. Jamais réattribué, jamais touché par la renumérotation.

    En mode classeur c'est le numéro de ligne de l'onglet `Import` ; en mode
    console ce n'est qu'un compteur. Dans les deux cas il est unique par
    édition, et c'est tout ce que la contrainte demande.
    """
    maximum = db.session.query(db.func.max(Bloc.numero)).filter(
        Bloc.competition_id == comp.id).scalar()
    return (maximum or 0) + 1


def creer(comp, zone: str) -> Bloc:
    """Une voie nue dans cette zone. Sans couleur, sans catégorie."""
    verifier_modifiable(comp)
    zone = (zone or "").strip().upper()[:ZONE_MAXI]
    if not zone:
        raise ErreurOuverture("Une voie appartient a une zone.", code=400)

    numero = _prochain_numero(comp)
    bloc = Bloc(competition_id=comp.id, zone=zone, numero=numero,
                tag=_tag_de_reserve(zone, numero), source=SOURCE_CONSOLE)
    db.session.add(bloc)
    _prevenir(comp)
    db.session.commit()
    logger.info("voie creee en zone %s (competition %s)", zone, comp.id)
    return bloc


def modifier(comp, bloc, couleur=..., couleur_prises=..., circuits=...) -> Bloc:
    """Applique ce qui est fourni. `...` veut dire « ne touche pas ».

    ⚠️ `...` et non `None` : `None` est une valeur VALIDE ici — c'est ainsi
    qu'on retire une couleur ou une couleur de prises. Les confondre rendrait
    impossible de vider un champ.
    """
    verifier_modifiable(comp)

    if couleur is not ...:
        couleur = (couleur or None)
        if couleur is not None and couleur not in INITIALES:
            raise ErreurOuverture(
                f"Couleur inconnue : « {couleur} ». Les six couleurs sont "
                + ", ".join(COULEURS) + ".", code=400)
        if couleur != bloc.couleur:
            # Changer la couleur change le NOM, donc le tag, donc le QR.
            _refuser_si_reussites(bloc, "changer sa couleur")
            # ⚠️ LE RANG SE CALCULE AVANT DE POSER LA COULEUR. `_prochain_rang`
            # interroge la base, SQLAlchemy vide la session avant de repondre,
            # et cette voie-la y serait deja passee a la nouvelle couleur avec
            # son ANCIEN rang. `max` la compterait, et le rang rendu vaudrait
            # un de trop : passer « JV1 » en bleu donnait « JB2 » alors
            # qu'aucune bleue n'existait. Trouve par un test, pas a la
            # relecture.
            rang = None if couleur is None else _prochain_rang(comp, couleur)
            bloc.couleur = couleur
            if couleur is None:
                bloc.numero_couleur = None
                bloc.tag = _tag_de_reserve(bloc.zone or "", bloc.numero)
            else:
                bloc.numero_couleur = rang
                bloc.tag = f"{bloc.zone or ''}{INITIALES[couleur]}{rang}"

    if couleur_prises is not ...:
        # Accepte une chaîne — c'est ce que l'import du classeur pose — ou une
        # liste de une à deux couleurs, ce qu'envoie l'écran. Les deux
        # ressortent rangées de la même façon.
        bloc.couleur_prises = ranger_prises(couleur_prises)

    if circuits is not ...:
        _rattacher(comp, bloc, circuits or [])

    db.session.add(bloc)
    _prevenir(comp)
    db.session.commit()
    return bloc


def _rattacher(comp, bloc, noms: list[str]) -> None:
    """Rend les liens de circuit exactement égaux à `noms`."""
    connus = {c.nom: c for c in Circuit.query.filter_by(competition_id=comp.id).all()}
    inconnus = [n for n in noms if n not in connus]
    if inconnus:
        raise ErreurOuverture(
            "Categorie(s) inconnue(s) : " + ", ".join(sorted(inconnus)), code=400)

    vises = {connus[n].id for n in noms}
    actuels = {lien.circuit_id: lien for lien in
               BlocCircuit.query.filter_by(bloc_id=bloc.id).all()}
    for circuit_id, lien in actuels.items():
        if circuit_id not in vises:
            db.session.delete(lien)
    for circuit_id in vises - set(actuels):
        db.session.add(BlocCircuit(bloc_id=bloc.id, circuit_id=circuit_id))


def supprimer(comp, bloc) -> None:
    verifier_modifiable(comp)
    _refuser_si_reussites(bloc, "la supprimer")
    tag = bloc.tag
    db.session.delete(bloc)
    _prevenir(comp)
    db.session.commit()
    logger.info("voie %s supprimee (competition %s)", tag, comp.id)


# --- La renumérotation ------------------------------------------------------

def _ordre_de_renumerotation(blocs, couleur):
    """Les voies d'une couleur, dans l'ordre où elles seront numérotées.

    Zones de A à Z — la règle énoncée par Adrien — puis, à l'intérieur d'une
    zone, l'ordre de saisie.

    ⚠️ `id` en dernière clé de tri, et ce n'est pas une précaution en l'air :
    deux voies de même zone et même rang existent sur des données importées, et
    sans lui deux exécutions donneraient deux résultats. Une action qui n'est
    pas stable est une action qu'on n'ose pas lancer la veille.
    """
    siennes = [b for b in blocs if b.couleur == couleur]
    siennes.sort(key=lambda b: ((b.zone or ""), b.numero_couleur or 0, b.id))
    return siennes


def renumeroter(comp, apercu: bool = False) -> list[dict]:
    """Par couleur, zones de A à Z, 1…n sans trou. Rend les changements.

    `apercu=True` calcule sans rien écrire : c'est ce qui alimente l'écran de
    confirmation. Le calculer côté navigateur obligerait à recopier la règle de
    tri là-bas, et deux implémentations d'une même règle divergent — c'est la
    leçon de `cascade.py` et de son test miroir.
    """
    verifier_modifiable(comp)

    # ⚠️ Le geste est GLOBAL, il se juge globalement : une seule reussite dans
    # l'edition, meme sur une voie qui ne bouge pas, suffit a le refuser.
    en_jeu = (Success.query.join(Bloc, Success.bloc_id == Bloc.id)
              .filter(Bloc.competition_id == comp.id).count())
    if en_jeu:
        raise ErreurOuverture(
            f"{en_jeu} reussite(s) existent sur cette edition : renumeroter "
            f"changerait des QR deja scannes.")

    blocs = Bloc.query.filter_by(competition_id=comp.id).all()
    changements: list[dict] = []
    futur: list[tuple] = []
    for couleur in COULEURS:
        if couleur not in INITIALES:
            continue
        for rang, bloc in enumerate(_ordre_de_renumerotation(blocs, couleur), start=1):
            tag = f"{bloc.zone or ''}{INITIALES[couleur]}{rang}"
            if tag != bloc.tag or bloc.numero_couleur != rang:
                changements.append({"zone": bloc.zone or "", "avant": bloc.tag,
                                    "apres": tag, "couleur": couleur})
            futur.append((bloc, rang, tag))

    if apercu:
        return changements

    # ⚠️ EN DEUX PASSES. Une permutation circulaire -- « JV3 » qui prend la
    # place de « JV2 » pas encore liberee -- ferait claquer `uq_bloc_tag` en
    # cours de route. C'est le piege classique de toute renumerotation sous
    # contrainte d'unicite, et il ne se voit qu'avec un jeu de donnees qui
    # permute.
    for bloc, _, _ in futur:
        bloc.tag = f"~{bloc.id}"
        db.session.add(bloc)
    db.session.flush()
    for bloc, rang, tag in futur:
        bloc.numero_couleur, bloc.tag = rang, tag
        db.session.add(bloc)

    _prevenir(comp)
    db.session.commit()
    logger.info("renumerotation : %d voie(s) changent de nom (competition %s)",
                len(changements), comp.id)
    return changements


# --- Les catégories ---------------------------------------------------------

def creer_circuit(comp, nom: str) -> Circuit:
    verifier_modifiable(comp)
    nom = (nom or "").strip()[:20]
    if not nom:
        raise ErreurOuverture("Une categorie a besoin d'un nom.", code=400)
    if Circuit.query.filter_by(competition_id=comp.id, nom=nom).first():
        raise ErreurOuverture(f"La categorie « {nom} » existe deja.")
    circuit = Circuit(competition_id=comp.id, nom=nom)
    db.session.add(circuit)
    _prevenir(comp)
    db.session.commit()
    return circuit


def supprimer_circuit(comp, circuit) -> None:
    verifier_modifiable(comp)
    portees = BlocCircuit.query.filter_by(circuit_id=circuit.id).count()
    if portees:
        raise ErreurOuverture(
            f"« {circuit.nom} » porte {portees} voie(s) : les detacher avant "
            f"de la supprimer.")
    db.session.delete(circuit)
    _prevenir(comp)
    db.session.commit()


# --- Prévenir les téléphones ------------------------------------------------

def _prevenir(comp) -> None:
    """Le catalogue change : les téléphones doivent se remettre à jour.

    Sans ça, une voie ajoutée resterait invisible pour tout ce qui a déjà
    téléchargé le catalogue — et un juge scannerait un QR que son téléphone ne
    connaît pas. Même geste que pour un participant ajouté à 14 h.

    ⚠️ Posé AVANT le commit de l'appelant, jamais dans un commit à lui : deux
    commits feraient deux transactions, et un échec entre les deux laisserait
    un catalogue annoncé mais pas écrit.
    """
    comp.catalogue_version = (comp.catalogue_version or 0) + 1
    db.session.add(comp)
