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

import logging
import threading
import time
from collections import defaultdict

from .classement import (
    BlocCalcul, Cascade, Classement, ParticipantCalcul, _valider_par_couleur,
    blocs_du_circuit, calculer_clubs, calculer_tout,
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
    """Les options de l'édition, lues par `cycle` — une seule définition.

    Import tardif : `cycle` importe ce module, et le faire en tête créerait un
    cycle d'imports. La lecture des options a été écrite en double ici et là
    jusqu'à la spec 020 ; deux lectures d'un même JSON finissent toujours par
    diverger sur ce qu'elles tolèrent.
    """
    from .cycle import lire_options
    return lire_options(comp)


def cascade(comp: Competition) -> Cascade:
    """La règle de cascade de l'édition — vide par défaut (spec 025).

    Vide est le défaut, et ça compte : la règle n'était active ni en novembre
    2025, ni en mars 2026. Une édition qui n'en parle pas se classe comme avant.

    Import tardif : `cascade` lit `contest.ErreurMetier`, qui remonte à
    `models` — le faire en tête créerait un cycle.
    """
    from .cascade import depuis_options
    return depuis_options(_options(comp))


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
            cascade=cascade(comp),
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
def blocs_du_grimpeur(comp: Competition, participant: Participant) -> dict:
    """Ce qu'UN grimpeur a fait, vu du moteur : trois ensembles disjoints.

        grimpes      -- ses réussites réelles, SUR LES BLOCS DE SON CIRCUIT
        credites     -- ce que la cascade lui ajoute, jamais grimpé
        hors_circuit -- ses réussites réelles hors de son circuit, sans valeur
                        au classement. Un juge a forcé l'avertissement de la
                        spec 019 : la réussite est bien enregistrée, elle ne
                        compte simplement pas.

    ⚠️ **Les trois sont disjoints par construction, pas par convention.**
    `credites` est l'étendu MOINS le brut, donc jamais un bloc de `grimpes` ;
    `hors_circuit` est le brut MOINS les blocs du circuit, donc jamais un bloc
    des deux autres. La fiche du grimpeur (spec 026) peint l'union des deux
    premiers : si un identifiant tombait dans deux ensembles, elle afficherait
    le même bloc deux fois, dans deux états contraires.

    ⚠️ **C'est le SEUL accesseur, et il ne doit pas être recopié.** L'extension
    par couleur se calcule à l'intérieur du classement, groupe par groupe, et
    n'est stockée nulle part : la recalculer ailleurs créerait deux chemins vers
    la même vérité. Les réussites viennent de `charger()`, comme le classement,
    pour la même raison.

    La règle appliquée est celle de la **catégorie du grimpeur** (spec 025) :
    c'est le même `cascade.pour()` que le classement, donc l'écran ne peut pas
    montrer autre chose que ce qui est compté.
    """
    _, blocs, reussites, _ = charger(comp)
    du_circuit = (blocs_du_circuit(blocs, participant.circuit)
                  if participant.circuit else set())

    brutes = reussites.get(participant.id, set())
    grimpes = brutes & du_circuit
    etendues = _valider_par_couleur(
        grimpes, blocs, du_circuit, cascade(comp).pour(participant.categorie))

    return {
        "grimpes": grimpes,
        "credites": etendues - grimpes,
        "hors_circuit": brutes - du_circuit,
    }


def ordre(classement):
    if classement.type == "scratch":            # les generaux, tout a gauche
        return (0, "", 0, classement.groupe)
    if classement.type == "club":               # et le cumul par club a la fin
        return (2, "", 0, classement.groupe)
    # Un circuit ouvre sa famille, ses categories suivent.
    return (1, classement.circuit or "",
            0 if classement.type == "circuit" else 1, classement.groupe)


def nom_publie(participant, anonymiser: bool = True) -> str:
    """Le nom sous lequel ce grimpeur paraît en public. Spec 043.

    Un grimpeur qui s'est opposé à la publication de son nom (art. 21 RGPD)
    garde sa ligne, son rang et son score : seule son IDENTITE change. Retirer
    la ligne décalerait le rang de tous les suivants, et un rang qui saute de 3
    à 5 est une information sur celui qui manque.

    ⚠️ Le repli quand il n'y a pas de dossard n'est pas une politesse.
    `Participant.dossard` est nullable — c'est ainsi qu'un inscrit absent est
    représenté. « Dossard None » s'afficherait tel quel sur la page projetée.
    """
    if not anonymiser or not participant.publication_refusee:
        return participant.nom_complet
    return f"Dossard {participant.dossard}" if participant.dossard else "Participant"


def charge_publique(comp: Competition, forcer: bool = False,
                    anonymiser: bool = True) -> dict:
    """Tous les classements de cette compétition, prêts à être servis.

    Le nom des participants est inclus : la page resultats doit les afficher,
    et ils sont deja publics -- affiches sur les dossards et annonces au micro.
    Cet argument vaut DANS LA SALLE ; sur Internet, il justifie d'afficher, pas
    de publier durablement. C'est pourquoi la spec 043 ajoute la non-indexation
    et le droit d'opposition autour de cette charge, sans en changer la forme.

    `anonymiser=False` rend les noms RÉELS. Un seul appelant l'utilise :
    `cycle.archiver`, qui fige l'édition. L'archive est servie derrière la
    session organisateur, c'est un usage interne légitime — et une archive
    amputée serait irréparable. La règle tient en une phrase : **on fige
    complet, on rend anonymisé.**

    ⚠️ Le défaut protège. L'inverse — un défaut permissif qu'il faudrait penser
    à restreindre — s'oublierait au premier nouvel appelant.
    """
    tous, calcule_le = classements(comp, forcer=forcer)

    # Les noms, en une seule requete plutot qu'une par ligne.
    from .models import Participant, Success
    noms = {
        p.id: {"nom": nom_publie(p, anonymiser), "club": p.club,
               "categorie": p.categorie}
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

    from .cycle import groupes_masques

    return {
        "competition": {
            "id": comp.id, "nom": comp.nom, "statut": comp.statut,
            # ⚠️ Un REGLAGE D'AFFICHAGE, pas un filtre. Tous les classements
            # restent dans la charge, sans exception, pour trois raisons dans
            # cet ordre : `charge_publique` est aussi ce que `cycle.archiver`
            # fige, et une archive amputee serait irreparable ; demasquer un
            # classement l'apres-midi ne doit rien recalculer ; et la reponse
            # est mise en cache 5 s par Caddy pour tout le monde, donc elle ne
            # peut pas dependre de qui regarde.
            "groupes_masques": groupes_masques(comp),
        },
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
