"""Ce que contiennent les circuits, et ce qui cloche dedans — spec 019.

Un seul point d'entrée, `inventaire()`, qui répond à deux questions :

    « quels blocs composent le circuit U13 ? »
    « le classeur a-t-il été lu correctement ? »

La seconde est la vraie raison d'être de ce module. Le correctif du 01/09 —
les colonnes de circuit figées à trois au lieu de cinq — a laissé, sur le
classeur de novembre 2025, **37 blocs rattachés à aucun circuit et un circuit
entier absent**. Le rapport d'import annonce désormais les circuits qu'il lit ;
il ne dit toujours pas quels blocs sont restés orphelins. C'est ce que fait
`anomalies()`.

**Aucun Flask ici**, comme dans `cycle.py` : ce module ne parle qu'à la base, et
tout se teste sans client HTTP.
"""

from collections import defaultdict

from .extensions import db
from .models import Bloc, BlocCircuit, Circuit, Participant


def _circuit_de(categorie: str | None) -> str | None:
    """« U13 F » → « U13 ». La même règle que `Participant.circuit`.

    Reprise ici parce qu'on la calcule sur des chaînes venues d'une requête
    `distinct`, sans instancier de participants — quatre-vingt-dix-huit objets
    ORM pour lire une colonne serait du gaspillage, et le résultat serait le
    même.
    """
    if not categorie:
        return None
    return categorie.rsplit(" ", 1)[0] if " " in categorie else categorie


def _categories_par_circuit(competition_id: int) -> dict[str, set[str]]:
    """Circuit → les catégories RÉELLEMENT portées par des participants.

    On ne déduit jamais « U13 F » et « U13 H » de l'existence du circuit
    « U13 » : une compétition peut n'avoir que des filles dans une tranche
    d'âge, et afficher une catégorie que personne ne porte ferait chercher des
    grimpeurs qui n'existent pas.
    """
    lignes = (db.session.query(Participant.categorie)
              .filter(Participant.competition_id == competition_id,
                      Participant.categorie.isnot(None))
              .distinct().all())
    par_circuit: dict[str, set[str]] = defaultdict(set)
    for (categorie,) in lignes:
        circuit = _circuit_de(categorie)
        if circuit:
            par_circuit[circuit].add(categorie)
    return par_circuit


def inventaire(comp) -> dict:
    """Les circuits, les blocs, et ce qui cloche. Trois requêtes, pas plus.

    Le même budget que `classement_service.charger()` : les blocs, les liens
    bloc↔circuit joints aux circuits, et les catégories distinctes.
    """
    blocs = (Bloc.query.filter_by(competition_id=comp.id)
             .order_by(Bloc.numero).all())
    circuits = (Circuit.query.filter_by(competition_id=comp.id)
                .order_by(Circuit.nom).all())

    noms_circuits = {c.id: c.nom for c in circuits}
    par_bloc: dict[int, set[str]] = defaultdict(set)
    if noms_circuits:
        liens = (db.session.query(BlocCircuit.bloc_id, BlocCircuit.circuit_id)
                 .filter(BlocCircuit.circuit_id.in_(noms_circuits)).all())
        for bloc_id, circuit_id in liens:
            par_bloc[bloc_id].add(noms_circuits[circuit_id])

    categories = _categories_par_circuit(comp.id)

    def categories_de(noms: set[str]) -> list[str]:
        reunion: set[str] = set()
        for nom in noms:
            reunion |= categories.get(nom, set())
        return sorted(reunion)

    lignes_blocs = [{
        "id": b.id,
        "tag": b.tag,
        "zone": b.zone,
        "numero": b.numero,
        "couleur": b.couleur,
        "couleur_prises": b.couleur_prises,
        "circuits": sorted(par_bloc.get(b.id, ())),
        "categories": categories_de(par_bloc.get(b.id, set())),
    } for b in blocs]

    # Combien de blocs par circuit, et combien de grimpeurs. Les deux chiffres
    # qu'on regarde avant d'ouvrir le tableau.
    comptes_blocs: dict[str, int] = defaultdict(int)
    for noms in par_bloc.values():
        for nom in noms:
            comptes_blocs[nom] += 1

    comptes_participants: dict[str, int] = defaultdict(int)
    for categorie, nombre in (
            db.session.query(Participant.categorie, db.func.count(Participant.id))
            .filter(Participant.competition_id == comp.id)
            .group_by(Participant.categorie).all()):
        circuit = _circuit_de(categorie)
        if circuit:
            comptes_participants[circuit] += nombre

    lignes_circuits = [{
        "nom": c.nom,
        "blocs": comptes_blocs.get(c.nom, 0),
        "participants": comptes_participants.get(c.nom, 0),
        "categories": sorted(categories.get(c.nom, set())),
    } for c in circuits]

    return {
        "circuits": lignes_circuits,
        "blocs": lignes_blocs,
        "anomalies": anomalies(lignes_blocs, lignes_circuits, categories,
                               set(noms_circuits.values())),
    }


def anomalies(lignes_blocs, lignes_circuits, categories, noms_circuits) -> dict:
    """Les trois façons dont l'import a pu passer à côté de quelque chose.

    Chacune est SILENCIEUSE aujourd'hui : elle ne fait pas échouer l'import, ne
    lève aucune erreur, et se paie à la remise des prix. C'est exactement le
    genre de panne qui mérite un écran.
    """
    return {
        # Un bloc que personne ne grimpe. Soit la croix manque dans le
        # classeur, soit sa colonne de circuit n'a pas ete lue.
        "blocs_sans_circuit": [b["tag"] for b in lignes_blocs
                               if not b["circuits"]],
        # Un circuit dont le classement sortira vide, sur « aucun bloc
        # n'appartient au circuit ».
        "circuits_sans_bloc": [c["nom"] for c in lignes_circuits
                               if not c["blocs"]],
        # Le plus couteux des trois : ces grimpeurs-la scannent normalement, et
        # chacune de leurs reussites compte pour zero.
        "categories_sans_circuit": sorted(
            categorie
            for circuit, ensemble in categories.items() if circuit not in noms_circuits
            for categorie in ensemble
        ),
    }
