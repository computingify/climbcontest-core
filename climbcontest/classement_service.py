"""Le classement, branché sur la base — chargement, cache, exposition.

Sépare volontairement deux choses :

- `climbcontest/classement.py` **calcule**, sans rien connaître de la base. On
  peut le comparer directement au classeur, c'est ce que fait
  `tests/test_classement.py` sur les 1003 réussites de novembre 2025 ;
- ce module **alimente** le calcul et **garde le résultat sous la main**.

Le cache n'est pas une optimisation prématurée : le jour d'une compétition, les
trois quarts du trafic viennent des spectateurs qui rafraîchissent la page
résultats (voir `docs/contraintes-metier.md` §3 bis). Sans cache, chaque
rafraîchissement relancerait le calcul complet.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict

from .classement import (
    BlocCalcul, Classement, ParticipantCalcul, calculer_clubs, calculer_tout,
)
from .extensions import db
from .models import Bloc, BlocCircuit, Circuit, Competition, Participant, Success

logger = logging.getLogger(__name__)

# Le classement n'est pas recalculé plus d'une fois par cette durée, quel que
# soit le nombre de réussites qui arrivent ou de spectateurs qui regardent.
# Cinq secondes, c'est la même fraîcheur que le cache posé dans le Caddyfile.
FRAICHEUR_S = 5.0

# ⚠️ Ce cache est PAR PROCESSUS. Avec quatre workers gunicorn, il y a quatre
# caches indépendants — un spectateur peut donc voir un classement jusqu'à cinq
# secondes plus vieux que son voisin, selon le worker qui l'a servi.
#
# C'est acceptable et voulu : tous lisent la même base, et cinq secondes de
# décalage sur un classement d'escalade ne se remarquent pas. Un cache partagé
# demanderait Redis ou une table de plus, pour un problème qui n'existe pas.
#
# Ce qui serait un vrai défaut, en revanche, c'est un classement FAUX — et il ne
# peut pas l'être : chaque calcul repart de la base, il n'y a pas d'état
# incrémental à désynchroniser.

_verrou = threading.Lock()
_cache: dict[int, tuple[float, dict[str, Classement]]] = {}


def _options(comp: Competition) -> dict:
    try:
        return json.loads(comp.options or "{}")
    except ValueError:
        logger.warning("options illisibles pour la competition %s", comp.id)
        return {}


def couleurs_requises(comp: Competition) -> int:
    """Combien de couleurs pleines valident les couleurs plus faciles.

    0 = validation par couleur désactivée, ce qui est le défaut : elle n'était
    pas active en novembre 2025. C'est une **option par compétition**, parce que
    le format change d'une édition à l'autre — décision du 28/08.
    """
    valeur = _options(comp).get("validation_couleur", 0)
    try:
        return max(0, int(valeur))
    except (TypeError, ValueError):
        return 0


def charger(comp: Competition):
    """Lit en base tout ce dont le moteur a besoin. Trois requêtes, pas plus."""
    participants = [
        ParticipantCalcul(id=p.id, dossard=p.dossard, categorie=p.categorie,
                          club=p.club)
        for p in Participant.query.filter_by(competition_id=comp.id).all()
    ]

    circuits_par_bloc: dict[int, set[str]] = defaultdict(set)
    lignes = (
        db.session.query(BlocCircuit.bloc_id, Circuit.nom)
        .join(Circuit, BlocCircuit.circuit_id == Circuit.id)
        .filter(Circuit.competition_id == comp.id)
        .all()
    )
    for bloc_id, nom in lignes:
        circuits_par_bloc[bloc_id].add(nom)

    blocs = {
        b.id: BlocCalcul(id=b.id, tag=b.tag, couleur=b.couleur,
                         circuits=frozenset(circuits_par_bloc.get(b.id, ())))
        for b in Bloc.query.filter_by(competition_id=comp.id).all()
    }

    reussites: dict[int, set[int]] = defaultdict(set)
    for participant_id, bloc_id in (
        db.session.query(Success.participant_id, Success.bloc_id)
        .join(Participant, Success.participant_id == Participant.id)
        .filter(Participant.competition_id == comp.id)
        .all()
    ):
        reussites[participant_id].add(bloc_id)

    circuits = {c.nom for c in Circuit.query.filter_by(competition_id=comp.id).all()}
    return participants, blocs, reussites, circuits


def classements(comp: Competition, forcer: bool = False) -> tuple[dict[str, Classement], float]:
    """Les classements de cette compétition, et l'heure de leur calcul.

    Recalcule au plus une fois toutes les `FRAICHEUR_S` secondes. Le verrou
    évite que dix rafraîchissements simultanés déclenchent dix calculs.
    """
    maintenant = time.time()

    entree = _cache.get(comp.id)
    if entree and not forcer and (maintenant - entree[0]) < FRAICHEUR_S:
        return entree[1], entree[0]

    with _verrou:
        # Quelqu'un a pu calculer pendant qu'on attendait le verrou.
        entree = _cache.get(comp.id)
        if entree and not forcer and (time.time() - entree[0]) < FRAICHEUR_S:
            return entree[1], entree[0]

        debut = time.monotonic()
        participants, blocs, reussites, circuits = charger(comp)
        resultat = calculer_tout(
            participants, blocs, reussites, circuits,
            couleurs_requises=couleurs_requises(comp),
        )
        # Derive des classements par categorie, jamais recalcule : c'est ce qui
        # garantit qu'il ne pourra pas diverger d'eux (spec 010).
        clubs = calculer_clubs(resultat, participants)
        if clubs is not None:
            resultat[clubs.groupe] = clubs
        duree = time.monotonic() - debut
        calcule_le = time.time()
        _cache[comp.id] = (calcule_le, resultat)

        logger.info("classement recalcule : %d groupe(s) en %.0f ms",
                    len(resultat), duree * 1000)
        return resultat, calcule_le


def invalider(competition_id: int | None = None) -> None:
    """Force le prochain appel à recalculer.

    Appelé quand la donnée change hors du rythme normal : import du classeur,
    saisie manuelle, réaffectation de dossard.
    """
    with _verrou:
        if competition_id is None:
            _cache.clear()
        else:
            _cache.pop(competition_id, None)


# --- La charge que sert la page de résultats (spec 018) ---------------------
#
# Elle vivait dans le corps de `routes/public.py`. Elle en sort parce qu'elle a
# maintenant DEUX appelants : la route publique, et l'archivage — qui doit
# figer exactement ce que la page sait afficher. Écrite en double, elle aurait
# divergé au premier changement, et la page de résultats aurait cassé sur les
# archives uniquement, c'est-à-dire longtemps après.


# L'ordre d'affichage. C'est aussi l'ordre de la barre, donc l'ordre du cycle
# sur le mur : il se lit du plus general au plus precis.
#
#   Scratch, Scratch F, Scratch H        les trois qui traversent tout
#   U11 scratch, U11 F, U11 H            un circuit, puis SES categories
#   U13 scratch, U13 F, U13 H
#   ...
#   Clubs
#
# Demande d'Adrien (01/09) : « les scratchs avant leurs categories
# correspondantes, et les scratchs generaux au debut a gauche ». Grouper par
# circuit met cote a cote des classements qui parlent des memes grimpeurs --
# on passe de « U13 scratch » a « U13 F » sans traverser la barre.
def ordre(classement):
    if classement.type == "scratch":            # les generaux, tout a gauche
        return (0, "", 0, classement.groupe)
    if classement.type == "club":               # et le cumul par club a la fin
        return (2, "", 0, classement.groupe)
    # Un circuit ouvre sa famille, ses categories suivent.
    return (1, classement.circuit or "",
            0 if classement.type == "circuit" else 1, classement.groupe)


def charge_publique(comp: Competition, forcer: bool = False) -> dict:
    """Tous les classements de cette compétition, prêts à être servis.

    Le nom des participants est inclus : la page resultats doit les afficher,
    et ils sont deja publics -- affiches sur les dossards et annonces au micro.
    """
    tous, calcule_le = classements(comp, forcer=forcer)

    # Les noms, en une seule requete plutot qu'une par ligne.
    from .models import Participant, Success
    noms = {
        p.id: {"nom": p.nom_complet, "club": p.club, "categorie": p.categorie}
        for p in Participant.query.filter_by(competition_id=comp.id).all()
    }

    def enrichir(ligne):
        d = ligne.to_dict()
        # Une ligne de club porte deja son nom (`libelle`) et n'a pas de
        # participant : `participant_id` vaut 0, qu'aucun identifiant SQLite ne
        # prend. Elle traverse donc cet enrichissement sans etre ecrasee.
        d.update(noms.get(ligne.participant_id, {}))
        return d

    # Le compteur de la journee (spec 016). Il monte tout au long de la
    # competition, y compris quand un classement ne bouge pas : c'est ce qui
    # dit, sur un ecran projete, que le systeme VIT. Un COUNT indexe sur une
    # base de quelques milliers de lignes -- et la reponse est de toute facon
    # mise en cache 5 s par le proxy.
    reussites = (
        Success.query.join(Participant, Success.participant_id == Participant.id)
        .filter(Participant.competition_id == comp.id).count()
    )

    return {
        "competition": {"id": comp.id, "nom": comp.nom, "statut": comp.statut},
        "calcule_le": calcule_le,
        "reussites": reussites,
        # L'AGE du calcul, vu par le serveur. Sans lui, la page ne pourrait que
        # mesurer depuis sa propre reception -- et afficherait « calcule il y a
        # 1 s » pour un classement que le cache garde depuis 5 s. Le client ne
        # peut pas le deduire : son horloge n'est pas celle du serveur.
        "age_s": round(max(0.0, time.time() - calcule_le), 1),
        "classements": [
            {**c.to_dict(), "lignes": [enrichir(l) for l in c.lignes]}
            for c in sorted(tous.values(), key=ordre)
        ],
    }
