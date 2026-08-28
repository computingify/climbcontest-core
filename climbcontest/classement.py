"""Le moteur de classement.

Reprend le calcul que fait le classeur Google, décodé et validé sur les
1003 réussites réelles de novembre 2025 : voir
`docs/technical/classeur-google.md` et `tools/verify_ranking.py`.

La règle, pour un groupe donné — une catégorie (« U13 F ») ou un circuit
(« U13 ») :

    membres           = les participants de ce groupe
    réussites tenues  = celles des membres, SUR LES BLOCS DU CIRCUIT seulement
    valeur(bloc)      = 1000 / nombre de MEMBRES ayant réussi ce bloc
    score(membre)     = arrondi( somme des valeurs de ses blocs tenus )
    rang              = score décroissant, ex æquo au même rang

Deux pièges, tous deux constatés dans la branche `feature/ResultAlgorithm` :

**Le filtre par circuit.** Une réussite sur un bloc hors du circuit du grimpeur
est enregistrée — le juge l'a vraiment vue — mais ne compte pas au classement.
Sans ce filtre, 17 grimpeurs sur 98 obtenaient un score trop élevé.

**Le dénominateur est relatif au groupe.** Un même bloc ne vaut pas la même
chose en « U13 F », en « U13 H » et au scratch « U13 ». Il faut donc recalculer
la valeur des blocs pour chaque groupe, pas une fois pour toutes.

Ce module est **pur** : il ne connaît ni Flask, ni HTTP, ni requête SQL. On lui
passe des données, il rend un classement. C'est ce qui permet de le comparer
directement au classeur.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

VALEUR_BLOC_MAX = 1000

# Ordre de difficulté, du plus facile au plus dur. Repris de `Listes!A41:A46`
# du classeur. Sert uniquement à la validation par couleur.
COULEURS = ["Jaune", "Vert", "Bleu", "Mauve", "Rouge", "Noir"]


@dataclass(frozen=True)
class ParticipantCalcul:
    """Ce dont le moteur a besoin d'un participant. Rien de plus."""

    id: int
    dossard: int | None
    categorie: str | None

    @property
    def circuit(self) -> str | None:
        """« U13 F » → « U13 »."""
        if not self.categorie:
            return None
        return self.categorie.rsplit(" ", 1)[0] if " " in self.categorie else self.categorie


@dataclass(frozen=True)
class BlocCalcul:
    id: int
    tag: str
    couleur: str | None
    circuits: frozenset[str]


@dataclass
class Ligne:
    """Une ligne de classement."""

    participant_id: int
    dossard: int | None
    score: int
    rang: int
    blocs_reussis: int

    def to_dict(self) -> dict:
        return {
            "participant_id": self.participant_id,
            "dossard": self.dossard,
            "score": self.score,
            "rang": self.rang,
            "blocs": self.blocs_reussis,
        }


@dataclass
class Classement:
    """Le classement d'un groupe."""

    groupe: str
    type: str                                   # « categorie » ou « circuit »
    circuit: str | None
    lignes: list[Ligne] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "groupe": self.groupe,
            "type": self.type,
            "circuit": self.circuit,
            "lignes": [l.to_dict() for l in self.lignes],
        }


def _valider_par_couleur(
    reussites: set[int],
    blocs: dict[int, BlocCalcul],
    blocs_du_circuit: set[int],
    couleurs_requises: int,
) -> set[int]:
    """Étend les réussites d'un participant par la règle des couleurs.

    Règle du classeur (`Inter!DJ19`) : **un grimpeur qui a réussi 100 % des blocs
    de N couleurs plus difficiles se voit valider tous les blocs des couleurs
    plus faciles**.

    `couleurs_requises` est le N — le classeur documente plusieurs variantes
    (deux couleurs pleines, une seule). C'est une option par compétition, parce
    que le format change d'une édition à l'autre.

    Renvoie l'ensemble étendu ; ne modifie rien sur place.
    """
    if couleurs_requises <= 0:
        return reussites

    # Combien de blocs par couleur dans ce circuit, et combien réussis.
    total_par_couleur: dict[str, int] = defaultdict(int)
    reussis_par_couleur: dict[str, int] = defaultdict(int)
    for bloc_id in blocs_du_circuit:
        couleur = blocs[bloc_id].couleur
        if not couleur:
            continue
        total_par_couleur[couleur] += 1
        if bloc_id in reussites:
            reussis_par_couleur[couleur] += 1

    # Les couleurs entièrement réussies, de la plus dure à la plus facile.
    pleines = [
        c for c in reversed(COULEURS)
        if total_par_couleur.get(c, 0) > 0
        and reussis_par_couleur.get(c, 0) == total_par_couleur[c]
    ]
    if len(pleines) < couleurs_requises:
        return reussites

    # La plus FACILE des couleurs pleines retenues fixe le seuil : tout ce qui
    # est plus facide qu'elle est validé.
    retenues = pleines[:couleurs_requises]
    seuil = min(COULEURS.index(c) for c in retenues)

    etendues = set(reussites)
    for bloc_id in blocs_du_circuit:
        couleur = blocs[bloc_id].couleur
        if couleur and COULEURS.index(couleur) < seuil:
            etendues.add(bloc_id)
    return etendues


def calculer_groupe(
    groupe: str,
    type_groupe: str,
    circuit: str | None,
    membres: list[ParticipantCalcul],
    blocs: dict[int, BlocCalcul],
    reussites_par_participant: dict[int, set[int]],
    couleurs_requises: int = 0,
) -> Classement:
    """Calcule le classement d'un groupe. Fonction pure."""
    classement = Classement(groupe=groupe, type=type_groupe, circuit=circuit)

    if circuit is None:
        classement.avertissements.append(
            f"« {groupe} » n'a pas de circuit : classement vide")
        return classement

    blocs_du_circuit = {b.id for b in blocs.values() if circuit in b.circuits}
    if not blocs_du_circuit:
        classement.avertissements.append(
            f"aucun bloc n'appartient au circuit « {circuit} »")

    # 1. Ce qui compte pour chaque membre : ses réussites, limitées aux blocs du
    #    circuit, éventuellement étendues par la règle des couleurs.
    tenues: dict[int, set[int]] = {}
    for m in membres:
        brutes = reussites_par_participant.get(m.id, set()) & blocs_du_circuit
        tenues[m.id] = _valider_par_couleur(
            brutes, blocs, blocs_du_circuit, couleurs_requises)

    # 2. La valeur d'un bloc dépend de CE groupe : 1000 / le nombre de membres
    #    qui l'ont réussi. Un même bloc ne vaut pas la même chose ailleurs.
    reussi_par: dict[int, int] = defaultdict(int)
    for blocs_membre in tenues.values():
        for bloc_id in blocs_membre:
            reussi_par[bloc_id] += 1
    valeur = {b: VALEUR_BLOC_MAX / n for b, n in reussi_par.items() if n}

    # 3. Les scores. Un membre sans réussite marque 0 et figure au classement —
    #    il est venu, il doit apparaître.
    scores = {
        m.id: round(sum(valeur.get(b, 0) for b in tenues[m.id]))
        for m in membres
    }

    # 4. Les rangs. Les ex æquo partagent le même rang et le suivant saute les
    #    places occupées : deux premiers, pas de deuxième, le suivant est 3ᵉ.
    #    C'est le comportement de RANK() dans le classeur.
    par_dossard = {m.id: m.dossard for m in membres}
    ordonnes = sorted(
        membres,
        key=lambda m: (-scores[m.id], m.dossard if m.dossard is not None else 10**9),
    )
    precedent_score: int | None = None
    precedent_rang = 0
    for position, m in enumerate(ordonnes, start=1):
        score = scores[m.id]
        rang = precedent_rang if score == precedent_score else position
        precedent_score, precedent_rang = score, rang
        classement.lignes.append(Ligne(
            participant_id=m.id,
            dossard=par_dossard[m.id],
            score=score,
            rang=rang,
            blocs_reussis=len(tenues[m.id]),
        ))

    return classement


def calculer_tout(
    participants: list[ParticipantCalcul],
    blocs: dict[int, BlocCalcul],
    reussites_par_participant: dict[int, set[int]],
    circuits: set[str] | None = None,
    couleurs_requises: int = 0,
) -> dict[str, Classement]:
    """Tous les classements : une entrée par catégorie et une par circuit.

    Les clés sont les noms de groupe (« U13 F », « U13 ») — le même espace de
    noms que le classeur, pour pouvoir comparer directement.
    """
    resultats: dict[str, Classement] = {}

    par_categorie: dict[str, list[ParticipantCalcul]] = defaultdict(list)
    par_circuit: dict[str, list[ParticipantCalcul]] = defaultdict(list)
    for p in participants:
        if p.categorie:
            par_categorie[p.categorie].append(p)
        if p.circuit:
            par_circuit[p.circuit].append(p)

    for categorie, membres in par_categorie.items():
        resultats[categorie] = calculer_groupe(
            categorie, "categorie", membres[0].circuit, membres, blocs,
            reussites_par_participant, couleurs_requises)

    for circuit, membres in par_circuit.items():
        if circuits is not None and circuit not in circuits:
            continue
        # Une catégorie peut porter le même nom qu'un circuit (« U17 » seul) :
        # dans ce cas le classement par catégorie fait déjà foi.
        if circuit in resultats:
            continue
        resultats[circuit] = calculer_groupe(
            circuit, "circuit", circuit, membres, blocs,
            reussites_par_participant, couleurs_requises)

    return resultats
