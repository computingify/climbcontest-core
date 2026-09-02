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
    club: str | None = None

    @property
    def circuit(self) -> str | None:
        """« U13 F » → « U13 »."""
        if not self.categorie:
            return None
        return self.categorie.rsplit(" ", 1)[0] if " " in self.categorie else self.categorie


GENRES = ("F", "H")
SCRATCH = "Scratch"


def genre_de(categorie: str | None) -> str | None:
    """« U13 F » → « F ». None si la catégorie n'en porte pas.

    Le club écrit « F » et « H ». Une catégorie sans genre — ça existe, l'import
    est tolérant — ne rejoint aucun des deux scratchs genrés, mais figure bien
    au scratch général : elle est venue grimper.
    """
    if not categorie or " " not in categorie:
        return None
    suffixe = categorie.rsplit(" ", 1)[1].upper()
    return suffixe if suffixe in GENRES else None


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
    # Combien de ces blocs viennent de la CASCADE et non d'un scan (spec 025,
    # D5). Sans ce champ, « 36 blocs » ne dit plus ce qu'il dit : le dossard 59
    # de novembre 2025 en aurait grimpe 7. Zero quand la cascade est eteinte,
    # ce qui est le defaut -- la page ne montre alors rien de plus.
    blocs_credites: int = 0
    # Renseigne UNIQUEMENT pour un classement de clubs : combien de grimpeurs
    # composent la ligne. Un champ dedie plutot qu'un detournement de `dossard`
    # -- un detournement se paie toujours plus tard, quand quelqu'un affiche
    # « dossard 15 » pour un club.
    membres: int | None = None
    # Le nom porte par la ligne quand ce n'est pas un participant -- un club,
    # aujourd'hui. Un champ declare plutot qu'un dictionnaire pose a cote de la
    # dataclass : un canal parallele ne se serialise pas et casse au premier
    # remaniement.
    libelle: str | None = None

    def to_dict(self) -> dict:
        base = {
            "participant_id": self.participant_id,
            "dossard": self.dossard,
            "score": self.score,
            "rang": self.rang,
            "blocs": self.blocs_reussis,
        }
        if self.blocs_credites:
            base["credites"] = self.blocs_credites
        if self.membres is not None:
            base["membres"] = self.membres
        if self.libelle is not None:
            base["nom"] = self.libelle
        return base


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


@dataclass(frozen=True)
class Phrase:
    """« Quand au moins `seuil` parmi `parmi` sont validées → valider `cibles`. »

    C'est l'unité de la règle, telle qu'elle se lit dans la console (spec 025).
    Le `seuil` est ce qui permet d'exprimer le « et » du classeur — deux couleurs
    pleines — qu'une correspondance couleur → couleur ne sait pas dire.
    """

    parmi: frozenset[str]
    seuil: int
    cibles: frozenset[str]

    def tient(self, pleines: frozenset[str]) -> bool:
        return len(self.parmi & pleines) >= self.seuil


@dataclass(frozen=True)
class Cascade:
    """La règle de l'édition, et les catégories qui ne la suivent pas.

    On range les catégories **éteintes**, jamais les allumées — même principe
    que `cycle.groupes_masques` (spec 020), et pour la même raison : une
    catégorie créée à l'inscription à chaud est absente de toute liste écrite le
    matin. Rangée en « allumées » elle sortirait éteinte, et ses grimpeurs
    seraient classés sous une autre règle que leurs camarades sans que rien ne
    le dise.
    """

    phrases: tuple[Phrase, ...] = ()
    categories_eteintes: frozenset[str] = frozenset()

    def __bool__(self) -> bool:
        return bool(self.phrases)

    def pour(self, categorie: str | None) -> "Cascade":
        """La cascade telle qu'elle s'applique à CE grimpeur.

        C'est le cœur de la portée par catégorie : la règle n'est plus un
        paramètre de la compétition mais du grimpeur, résolu par sa catégorie.
        Les scratchs, qui mélangent les catégories, héritent donc naturellement
        de la règle de chacun — exactement ce que fait le classeur, dont
        `Inter!DJ19` se calcule ligne par ligne.
        """
        if categorie is not None and categorie in self.categories_eteintes:
            return Cascade()
        return self


def _valider_par_couleur(
    reussites: set[int],
    blocs: dict[int, BlocCalcul],
    blocs_du_circuit: set[int],
    cascade: Cascade,
) -> set[int]:
    """Étend les réussites d'un participant par la règle des couleurs.

    Réussir **tous** les blocs d'une couleur la rend « pleine » ; les phrases de
    la cascade disent ce qu'un jeu de couleurs pleines valide en plus.

    Deux points qui sont des décisions, pas des détails d'implémentation :

    - **une seule passe** (D2) : ce qu'une phrase valide n'alimente jamais
      `pleines`, donc une couleur créditée ne peut pas en déclencher une autre.
      Sans ça, « Noir → Rouge » et « Rouge → tout » se composeraient en une règle
      que personne n'a écrite ;
    - **une couleur à zéro bloc n'est jamais pleine** (D3). Sinon « toutes les
      Noir » serait vrai sans effort sur un circuit sans Noir — c'est-à-dire sur
      les quatre circuits de novembre 2025 — et la cascade se déclencherait pour
      tout le monde, tout le temps.

    Renvoie l'ensemble étendu ; ne modifie rien sur place.
    """
    if not cascade:
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

    pleines = frozenset(
        c for c in COULEURS
        if total_par_couleur.get(c, 0) > 0
        and reussis_par_couleur.get(c, 0) == total_par_couleur[c]
    )

    validees: set[str] = set()
    for phrase in cascade.phrases:
        if phrase.tient(pleines):
            validees |= phrase.cibles
    if not validees:
        return reussites

    etendues = set(reussites)
    for bloc_id in blocs_du_circuit:
        if blocs[bloc_id].couleur in validees:
            etendues.add(bloc_id)
    return etendues


def blocs_du_circuit(blocs: dict[int, BlocCalcul], circuit: str) -> set[int]:
    return {b.id for b in blocs.values() if circuit in b.circuits}


def calculer_groupe(
    groupe: str,
    type_groupe: str,
    circuit: str | None,
    membres: list[ParticipantCalcul],
    blocs: dict[int, BlocCalcul],
    reussites_par_participant: dict[int, set[int]],
    cascade: Cascade = Cascade(),
) -> Classement:
    """Calcule le classement d'un groupe d'UN SEUL circuit. Fonction pure."""
    classement = Classement(groupe=groupe, type=type_groupe, circuit=circuit)

    if circuit is None:
        classement.avertissements.append(
            f"« {groupe} » n'a pas de circuit : classement vide")
        return classement

    du_circuit = blocs_du_circuit(blocs, circuit)
    if not du_circuit:
        classement.avertissements.append(
            f"aucun bloc n'appartient au circuit « {circuit} »")

    return _classer(classement, membres, {m.id: du_circuit for m in membres},
                    blocs, reussites_par_participant, cascade)


def calculer_scratch(
    groupe: str,
    membres: list[ParticipantCalcul],
    blocs: dict[int, BlocCalcul],
    reussites_par_participant: dict[int, set[int]],
    cascade: Cascade = Cascade(),
) -> Classement:
    """Un classement qui TRAVERSE les circuits : tout le monde, ou tout un genre.

    Demandé par Adrien le 31/08 : « un scratch où il y a tout le monde, et un
    scratch homme, un autre femme ».

    La règle ne change pas d'un iota — elle est seulement appliquée à un groupe
    plus large. Chaque membre reste jugé sur **les blocs de SON circuit** (un
    U11 n'a jamais pu essayer les blocs U17), et la valeur d'un bloc reste
    `1000 / nombre de membres du groupe l'ayant réussi`.

    ⚠️ **Les scores d'un scratch ne sont comparables qu'entre eux.** J'ai
    d'abord écrit ici qu'une fille garderait le score de sa catégorie ; c'est
    faux, et la fixture de novembre 2025 le montre en une exécution : un bloc
    appartient souvent à **plusieurs circuits** (`['U11', 'U13']`). Le
    dénominateur d'un scratch compte donc des grimpeurs que la catégorie ne
    comptait pas, et le score change — 54 écarts sur 57 grimpeuses.

    C'est la règle du classeur, appliquée telle quelle : la valeur d'un bloc est
    relative au groupe qu'on classe. Deux conséquences à dire au micro plutôt
    qu'à découvrir devant le podium :

    - un grimpeur a un score DIFFÉRENT dans chaque classement où il figure —
      c'était déjà vrai entre sa catégorie et son circuit ;
    - un groupe plus petit donne des blocs plus chers, donc des scores plus
      hauts. Le premier du scratch féminin peut afficher davantage que le
      premier du scratch général sans avoir grimpé davantage.

    Un scratch qui traverse les circuits compare de toute façon des grimpeurs
    qui n'ont pas grimpé les mêmes blocs. C'est une lecture transversale, pas un
    titre : la catégorie reste le résultat officiel.
    """
    classement = Classement(groupe=groupe, type="scratch", circuit=None)
    cache: dict[str, set[int]] = {}
    par_membre: dict[int, set[int]] = {}
    for m in membres:
        if m.circuit not in cache:
            cache[m.circuit] = blocs_du_circuit(blocs, m.circuit)
        par_membre[m.id] = cache[m.circuit]
    return _classer(classement, membres, par_membre, blocs,
                    reussites_par_participant, cascade)


def _classer(
    classement: Classement,
    membres: list[ParticipantCalcul],
    blocs_par_membre: dict[int, set[int]],
    blocs: dict[int, BlocCalcul],
    reussites_par_participant: dict[int, set[int]],
    cascade: Cascade,
) -> Classement:
    """Le calcul lui-même. `blocs_par_membre` porte le filtre par circuit —
    identique pour tout le monde dans un groupe d'un seul circuit, propre à
    chacun dans un scratch qui les traverse."""
    # 1. Ce qui compte pour chaque membre : ses réussites, limitées aux blocs de
    #    son circuit, éventuellement étendues par la règle des couleurs.
    tenues: dict[int, set[int]] = {}
    credites: dict[int, int] = {}
    for m in membres:
        autorises = blocs_par_membre.get(m.id, set())
        brutes = reussites_par_participant.get(m.id, set()) & autorises
        tenues[m.id] = _valider_par_couleur(
            brutes, blocs, autorises, cascade.pour(m.categorie))
        credites[m.id] = len(tenues[m.id]) - len(brutes)

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
            blocs_credites=credites[m.id],
        ))

    return classement


def calculer_clubs(classements: dict[str, "Classement"],
                   participants: list[ParticipantCalcul]) -> "Classement | None":
    """Le classement par club : SOMME des scores de tous ses grimpeurs.

    Regle tranchee par Adrien le 29/08, en connaissance de cause : un club qui
    vient a quinze passera presque toujours devant un club qui vient a quatre,
    quel que soit le niveau. C'est ce que la regle mesure -- la participation
    autant que la performance. A redire au micro le jour J.

    ⚠️ ON NE RECALCULE RIEN. On additionne des scores deja calcules, en ne
    prenant que les classements de type « categorie ». C'est ce qui garantit que
    ce classement ne pourra jamais diverger des autres : recalculer a partir des
    reussites creerait un second chemin, donc la possibilite qu'ils ne disent
    pas la meme chose.

    POURQUOI LA CATEGORIE ET PAS LE SCRATCH. Un grimpeur figure dans DEUX
    classements -- sa categorie (« U13 F ») et son circuit (« U13 »). Les
    additionner le compterait deux fois. La categorie est son resultat officiel,
    celui du podium ; le scratch est une lecture transversale du meme travail.

    Renvoie `None` s'il n'y a aucun club -- un classement vide n'apprend rien.
    """
    club_de = {p.id: (p.club or "").strip() for p in participants}

    total: dict[str, dict] = defaultdict(lambda: {"score": 0, "blocs": 0, "membres": 0})
    for classement in classements.values():
        if classement.type != "categorie":
            continue
        for ligne in classement.lignes:
            club = club_de.get(ligne.participant_id, "")
            if not club:
                continue            # sans club, on n'invente pas de club fantome
            total[club]["score"] += ligne.score
            total[club]["blocs"] += ligne.blocs_reussis
            total[club]["membres"] += 1

    if not total:
        return None

    # Tri par score decroissant, puis par nom pour que l'ordre soit stable
    # d'un rafraichissement a l'autre.
    ordonnes = sorted(total.items(), key=lambda kv: (-kv[1]["score"], kv[0]))

    lignes: list[Ligne] = []
    rang, precedent, place = 0, None, 0
    for nom, valeurs in ordonnes:
        place += 1
        if valeurs["score"] != precedent:
            rang = place                       # ex aequo : le suivant saute les places
            precedent = valeurs["score"]
        lignes.append(Ligne(
            # L'identite d'un club est son nom : il n'a pas d'identifiant en
            # base. On garde le champ pour ne pas casser la forme des lignes.
            participant_id=0,
            dossard=None,
            score=valeurs["score"],
            rang=rang,
            blocs_reussis=valeurs["blocs"],
            membres=valeurs["membres"],
            libelle=nom,
        ))

    return Classement(groupe="Clubs", type="club", circuit=None, lignes=lignes)


def calculer_tout(
    participants: list[ParticipantCalcul],
    blocs: dict[int, BlocCalcul],
    reussites_par_participant: dict[int, set[int]],
    circuits: set[str] | None = None,
    cascade: Cascade = Cascade(),
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
            reussites_par_participant, cascade)

    for circuit, membres in par_circuit.items():
        if circuits is not None and circuit not in circuits:
            continue
        # Une catégorie peut porter le même nom qu'un circuit (« U17 » seul) :
        # dans ce cas le classement par catégorie fait déjà foi.
        if circuit in resultats:
            continue
        resultats[circuit] = calculer_groupe(
            circuit, "circuit", circuit, membres, blocs,
            reussites_par_participant, cascade)

    resultats.update(_scratchs(participants, par_circuit, blocs,
                               reussites_par_participant, cascade))
    return resultats


def _scratchs(participants, par_circuit, blocs, reussites_par_participant,
              cascade) -> dict[str, Classement]:
    """Le scratch général, et un par genre.

    On ne les produit que s'ils APPRENNENT quelque chose :

    - le scratch général demande **plus d'un circuit**, sinon il répète mot pour
      mot le « U13 scratch » qui est juste à côté ;
    - les scratchs genrés demandent **les deux genres**, sinon celui qui existe
      répète le scratch général.

    Un classement qui double son voisin ne fait pas gagner de temps : il fait
    douter de celui qu'on regarde.
    """
    tous = [p for p in participants if p.circuit]
    if len(par_circuit) < 2 or not tous:
        return {}

    resultats = {SCRATCH: calculer_scratch(
        SCRATCH, tous, blocs, reussites_par_participant, cascade)}

    par_genre: dict[str, list[ParticipantCalcul]] = defaultdict(list)
    for p in tous:
        genre = genre_de(p.categorie)
        if genre:
            par_genre[genre].append(p)

    if len(par_genre) > 1:
        for genre in GENRES:
            if par_genre.get(genre):
                nom = f"{SCRATCH} {genre}"
                resultats[nom] = calculer_scratch(
                    nom, par_genre[genre], blocs, reussites_par_participant,
                    cascade)

    return resultats
