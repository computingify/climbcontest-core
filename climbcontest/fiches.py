"""Ce qu'on imprime : la fiche du grimpeur (spec 023), l'étiquette du bloc (024).

La bande de trois centimètres qu'on imprimait jusqu'ici portait un QR, un
numéro et un nom. Le classeur, lui, imprime une **fiche** (onglet `Fiches`), et
cette fiche porte ce qui manquait : **quels blocs comptent pour ce grimpeur**,
et **où ils sont dans la salle**. Sans ça, le seul papier qu'il a en main de la
journée ne lui dit rien de ce qu'il doit grimper.

**Aucun Flask ici**, comme dans `cycle.py` et `circuits.py` : ce module ne parle
qu'à la base, et tout se teste sans client HTTP.
"""

from collections import defaultdict

from . import qr
from .classement import COULEURS
from .extensions import db
from .models import Bloc, BlocCircuit, Circuit

# La taille du QR d'une ÉTIQUETTE, zone de silence comprise. Deux fois celui
# d'une fiche : il est collé au mur, souvent en hauteur, et scanné d'un bras
# tendu — pas tenu à trente centimètres comme une fiche.
COTE_QR_ETIQUETTE_MM = 45.0

# La taille du QR sur le papier, zone de silence comprise. 24 mm donnent
# 0,83 mm par module sur un dossard à quatre chiffres — plus du double du
# plancher de `qr.MODULE_MINI_MM`, et de quoi scanner à bout de bras.
COTE_QR_MM = 24.0


def REPERE(nom: str) -> tuple[str, str]:
    """Un repère de la salle — « Escalier », « Haut » — et non une zone.

    Le classeur les mélange aux lettres de zone dans les mêmes cellules ; c'est
    précisément ce qui rend son schéma illisible. Ici ils sont d'un autre type,
    donc d'une autre allure.
    """
    return ("repere", nom)


# Le mur de bloc d'Annonay, relevé de l'onglet « Fiches » du classeur (V4:X11).
# IDENTIQUE dans les trois classeurs archivés — 2024, novembre 2025, mars 2026 :
# c'est la salle, pas une donnée de compétition. D'où une constante.
#
# La grille du classeur compte trois cellules par ligne ; la première en vaut
# une, les deux autres en valent trois chacune (« c         b         a »).
# D'où sept cases par ligne ici.
#
# ⚠️ Les cellules à une ou deux lettres (`d`, `z`, `e`, `x y`, `Haut`) sont lues
# CALÉES À GAUCHE de leur cellule : le dump ne garde que le texte, pas
# l'alignement. C'est la lecture qui préserve les alignements verticaux
# visibles — D au-dessus de C, Z au-dessus de « Escalier », E sous H.
PLAN = (
    (None, None, None, None, "X",                  "Y",  None),
    (None, "D",  None, None, "Z",                  None, None),
    (None, "C",  "B",  "A",  REPERE("Escalier"),   None, None),
    (None, None, None, None, None,                 None, None),
    ("L",  None, None, None, None,                 None, None),
    ("M",  "K",  "J",  "I",  "H",                  "G",  "F"),
    ("N",  None, None, None, "E",                  None, None),
    (None, REPERE("Haut"), None, None, None,       None, None),
)

# Déduit de PLAN, jamais recopié à la main : deux listes qui divergeraient
# feraient disparaître une zone du message « hors plan » sans rien casser
# visiblement.
ZONES_DU_PLAN = frozenset(
    case for ligne in PLAN for case in ligne if isinstance(case, str))


def _rang(bloc) -> tuple[int, str]:
    """L'ordre du classeur : la difficulté d'abord, le numéro ensuite.

    C'est le tri de `Plan!AM` — `sort(AA; AB)` où `AB` vaut
    `Listes!B41:B46 + COUNTIF(...)`, soit 1000 par couleur plus le rang
    alphabétique. Le tri se fait donc sur la CHAÎNE (« J10 » avant « J9 ») ;
    on le reproduit tel quel plutôt que de le corriger, sans quoi la fiche et
    le classeur ne liraient pas dans le même ordre.

    Un bloc sans couleur connue passe APRÈS tous les autres : il est douteux, il
    ne doit pas ouvrir la liste.
    """
    couleur = bloc.couleur if bloc.couleur in COULEURS else None
    return (COULEURS.index(couleur) if couleur else len(COULEURS), bloc.tag or "")


def numero(bloc) -> str:
    """« ZJ6 » → « J6 » : le numéro tel qu'il est écrit sur le mur.

    `removeprefix` et non une découpe à un caractère : rien ne garantit qu'une
    zone tiendra toujours sur une lettre. Et si le tag se réduit à sa zone, on
    rend le tag — mieux vaut un libellé redondant qu'une case vide.
    """
    if not bloc.zone:
        return bloc.tag
    return bloc.tag.removeprefix(bloc.zone) or bloc.tag


def _blocs_par_circuit(comp) -> dict[str, list]:
    """Circuit → ses blocs, triés comme le classeur les trie.

    Deux requêtes, quel que soit le nombre de grimpeurs : c'est ce qui fait que
    cent fiches ne coûtent pas cent requêtes. Même budget que
    `circuits.inventaire()`.

    Un circuit connu mais vide rend une liste vide, jamais `None` : la fiche
    doit pouvoir distinguer « circuit inconnu » de « circuit sans bloc », les
    deux ne se réparent pas au même endroit.
    """
    blocs = {b.id: b for b in Bloc.query.filter_by(competition_id=comp.id).all()}
    circuits = {c.id: c.nom
                for c in Circuit.query.filter_by(competition_id=comp.id).all()}

    par_circuit: dict[str, list] = defaultdict(list)
    for nom in circuits.values():
        par_circuit[nom] = []

    if circuits:
        liens = (db.session.query(BlocCircuit.bloc_id, BlocCircuit.circuit_id)
                 .filter(BlocCircuit.circuit_id.in_(circuits)).all())
        for bloc_id, circuit_id in liens:
            bloc = blocs.get(bloc_id)
            if bloc is not None:
                par_circuit[circuits[circuit_id]].append(bloc)

    for liste in par_circuit.values():
        liste.sort(key=_rang)
    return dict(par_circuit)


def plan_pour(zones: set[str]) -> list[list[dict]]:
    """Le plan de la salle, chaque case sachant si elle est « la sienne ».

    Le gabarit ne fait qu'afficher : c'est ici qu'on décide ce qui s'allume, et
    ici qu'on compte les colonnes.

    ⚠️ Un repère — « Escalier », « Haut » — est un MOT, pas une lettre : il tient
    sur trois cases. Il absorbe donc les deux cases vides qui le suivent, sinon
    la ligne compterait neuf colonnes au lieu de sept et tout le plan se
    décalerait. Le calcul se fait ici et pas en Jinja : une boucle de gabarit qui
    saute des éléments est exactement ce qu'on relit trois fois sans le croire.
    """
    lignes = []
    for ligne in PLAN:
        cases, saute = [], 0
        for i, case in enumerate(ligne):
            if saute:
                saute -= 1
                continue
            if isinstance(case, tuple):
                # Les deux cases suivantes ne sont absorbées que si elles sont
                # VIDES : mieux vaut un repère étroit qu'une zone effacée.
                suivantes = ligne[i + 1:i + 3]
                large = len(suivantes) == 2 and all(c is None for c in suivantes)
                saute = 2 if large else 0
                cases.append({"zone": None, "repere": case[1], "sienne": False,
                              "colonnes": 3 if large else 1})
            elif case is None:
                cases.append({"zone": None, "repere": None, "sienne": False,
                              "colonnes": 1})
            else:
                cases.append({"zone": case, "repere": None,
                              "sienne": case in zones, "colonnes": 1})
        lignes.append(cases)
    return lignes


def _groupes(blocs) -> list[dict]:
    """Les blocs coupés par couleur de difficulté, dans l'ordre déjà trié.

    Un regroupement par parcours, et non un `groupby` sur un dictionnaire :
    la liste est déjà dans le bon ordre, et l'ordre est ce qui compte.
    """
    groupes: list[dict] = []
    for bloc in blocs:
        couleur = bloc.couleur if bloc.couleur in COULEURS else None
        if not groupes or groupes[-1]["couleur"] != couleur:
            groupes.append({"couleur": couleur, "blocs": []})
        groupes[-1]["blocs"].append({
            "tag": bloc.tag, "zone": bloc.zone, "numero": numero(bloc),
            "couleur": couleur,
        })
    return groupes


def construire(comp, participants) -> list[dict]:
    """Une fiche par participant, dans l'ordre où on les a reçus.

    La fiche s'imprime TOUJOURS, même quand il n'y a rien à y mettre : c'est
    elle qui porte le QR, et sans QR le grimpeur ne peut pas être scanné. Ce qui
    manque se dit dans `manque`, en toutes lettres.
    """
    par_circuit = _blocs_par_circuit(comp)

    planche = []
    for p in participants:
        circuit = p.circuit
        blocs = par_circuit.get(circuit) if circuit else None

        manque = None
        if not p.categorie:
            manque = ("Aucune catégorie : ce grimpeur n'est rattaché à aucun "
                      "circuit. Corrige-la dans la console, puis réimprime.")
        elif blocs is None:
            manque = (f"Circuit « {circuit} » inconnu — le classeur n'a pas "
                      "encore été importé pour cette compétition.")
        elif not blocs:
            manque = (f"Aucun bloc dans le circuit « {circuit} ». La vue "
                      "« Circuits » de la console dit pourquoi.")

        blocs = blocs or []
        zones = {b.zone for b in blocs if b.zone}

        planche.append({
            "dossard": p.dossard,
            "nom": p.nom_complet,
            "club": p.club,
            "categorie": p.categorie,
            "circuit": circuit,
            "qr": qr.svg(p.dossard, cote_mm=COTE_QR_MM),
            "total": len(blocs),
            "groupes": _groupes(blocs),
            "plan": plan_pour(zones),
            # Une zone qu'on ne peut pas situer doit SE DIRE, pas disparaître :
            # le plan ne porte que 17 des 20 zones du classeur.
            "hors_plan": sorted(zones - ZONES_DU_PLAN),
            "manque": manque,
        })
    return planche


# --- Les étiquettes de blocs, à coller au mur (spec 024) ---------------------


def etiquettes(comp, zone: str | None = None, tag: str | None = None) -> list[dict]:
    """Les blocs à coller au mur, dans l'ordre du `Plan`.

    L'ordre est celui de `Bloc.numero` — le numéro de ligne dans l'onglet
    `Import`, qui suit le `Plan` : les blocs sortent donc zone par zone, comme
    le classeur les range. On prend la page de la zone Z, on va coller les cinq
    étiquettes de la zone Z, on ne trie rien à la main.

    Deux requêtes, quel que soit le nombre de blocs.

    `coupure` vaut vrai sur le **premier** bloc de chaque zone, sauf le tout
    premier : c'est ce que le gabarit traduit en saut de page. Le calcul est
    fait ici et pas en Jinja — une boucle de gabarit qui compare avec l'élément
    précédent est exactement ce qu'on relit trois fois sans le croire.
    """
    requete = Bloc.query.filter_by(competition_id=comp.id)
    if tag:
        requete = requete.filter(Bloc.tag == tag)
    elif zone:
        requete = requete.filter(Bloc.zone == zone)
    blocs = requete.order_by(Bloc.numero).all()

    circuits = {c.id: c.nom
                for c in Circuit.query.filter_by(competition_id=comp.id).all()}
    par_bloc: dict[int, list[str]] = defaultdict(list)
    if circuits and blocs:
        liens = (db.session.query(BlocCircuit.bloc_id, BlocCircuit.circuit_id)
                 .filter(BlocCircuit.circuit_id.in_(circuits),
                         BlocCircuit.bloc_id.in_([b.id for b in blocs])).all())
        for bloc_id, circuit_id in liens:
            par_bloc[bloc_id].append(circuits[circuit_id])

    planche = []
    zone_precedente = None
    for i, bloc in enumerate(blocs):
        planche.append({
            "tag": bloc.tag,
            "zone": bloc.zone,
            "numero": numero(bloc),
            "couleur": bloc.couleur,
            "couleur_prises": bloc.couleur_prises,
            "circuits": sorted(par_bloc.get(bloc.id, ())),
            # Le QR porte le tag COMPLET — « ZJ6 » — c'est ce que l'application
            # juge attend et ce que `bloc_par_tag()` sait relire. Pas un
            # caractère de plus.
            "qr": qr.svg(bloc.tag, cote_mm=COTE_QR_ETIQUETTE_MM),
            "coupure": i > 0 and bloc.zone != zone_precedente,
        })
        zone_precedente = bloc.zone
    return planche


def par_zone(etiquettes_: list[dict]) -> list[dict]:
    """Les étiquettes regroupées par zone, dans l'ordre où elles arrivent.

    Le gabarit boucle sur des GROUPES et non sur une liste plate : une grille
    par zone, et c'est le conteneur qui porte le saut de page. `break-before`
    sur un enfant de grille est mal supporté — refermer la grille à chaque zone
    l'évite complètement.
    """
    groupes: list[dict] = []
    for etiquette in etiquettes_:
        if not groupes or etiquette["coupure"]:
            groupes.append({"zone": etiquette["zone"], "etiquettes": []})
        groupes[-1]["etiquettes"].append(etiquette)
    return groupes
