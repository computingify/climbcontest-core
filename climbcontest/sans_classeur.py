"""Le mode sans classeur — spec 045.

Un réglage **global** qui débranche Google Sheets : l'écran, l'import, le jeton
et le fil de synchronisation. Il n'y a rien d'autre dans ce module que le
réglage lui-même et le contrôle qu'on fait avant de le poser.

⚠️ **Nommé `sans_classeur` et non `reglages`.** `sqlite_reglages.py` existe déjà
et parle d'autre chose (les PRAGMA de la connexion) : deux modules dont le nom
ne dit pas lequel on veut sont deux modules qu'on ouvre à tour de rôle.

DEUX PRINCIPES, et ils s'opposent au reste du dépôt sur un point :

1. **Le réglage se relit en base à CHAQUE décision.** Il n'est jamais mémorisé
   dans le processus. Quatre workers gunicorn tournent : un réglage lu au
   démarrage laisserait trois d'entre eux continuer d'appeler Google après la
   bascule, et le défaut serait intermittent — donc irreproductible.

2. **Le repli est `False`, c'est-à-dire « le classeur marche ».** Ailleurs on
   *fail closed* : `auth_session` refuse au moindre doute. Ici le défaut sûr est
   l'inverse. Ce mode RETIRE des fonctions, il n'en protège aucune ; replier sur
   `True` couperait l'import et le miroir d'un club qui n'a rien demandé, sur
   une simple lecture ratée.
"""

import logging

from .extensions import db
from .models import Bloc, Circuit, Reglage, SOURCE_HELLOASSO

logger = logging.getLogger(__name__)

CLE = "mode_sans_classeur"

#: La valeur qui allume. Tout le reste — clé absente, ligne vide, texte
#: inattendu — vaut éteint : voir le principe 2.
ALLUME = "1"


def actif() -> bool:
    """Le classeur Google est-il débranché ? **Ne lève jamais.**

    Même contrat que `plan_du_mur.lire()` : une base indisponible ou une ligne
    abîmée rend `False`, c'est-à-dire le comportement d'aujourd'hui.
    """
    try:
        ligne = db.session.get(Reglage, CLE)
    except RuntimeError:
        # Hors contexte applicatif : un appel depuis un script ou un test
        # unitaire, pas une panne. On se tait.
        return False
    except Exception:
        logger.exception("mode sans classeur : lecture impossible, on garde le classeur")
        return False
    return bool(ligne) and (ligne.valeur or "").strip() == ALLUME


def basculer(vers: bool, par: str | None = None) -> bool:
    """Allume ou éteint. Rend l'état obtenu.

    ⚠️ Éteindre **supprime la ligne** au lieu d'y écrire « 0 ». Une clé absente
    et une clé à zéro diraient la même chose, et deux façons de dire la même
    chose finissent par ne plus la dire pareil — `actif()` devrait alors
    connaître les deux.
    """
    ligne = db.session.get(Reglage, CLE)
    if vers:
        if ligne is None:
            ligne = Reglage(cle=CLE)
            db.session.add(ligne)
        ligne.valeur = ALLUME
        ligne.modifie_par = par
    elif ligne is not None:
        db.session.delete(ligne)
    db.session.commit()
    logger.info("mode sans classeur : %s par %s",
                "allume" if vers else "eteint", par or "?")
    return vers


# --- Le contrôle avant bascule ----------------------------------------------
#
# On ne débranche pas à l'aveugle. Ce qu'on vérifie, ce n'est PAS ce que le
# classeur contient — c'est que ce qu'il détenait est bien **en base**. C'est le
# seul moment où la vérification est encore possible : après, le fichier sera
# supprimé.

#: Les refus DURS : la bascule est impossible tant qu'ils tiennent.
B1 = "B1"
B2 = "B2"
#: Les avertissements : ils s'affichent, on passe outre en les ayant lus.
A1, A2, A3, A4 = "A1", "A2", "A3", "A4"


def _constat(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def controle(comp) -> dict:
    """Ce qui empêche, ce qui alerte, et si l'on peut basculer.

    `comp` peut être `None` : aucune compétition active est un cas normal entre
    deux éditions, et c'est B2 qui le dira. Lever ici obligerait l'appelant à
    traiter séparément un cas que le contrôle sait déjà nommer.
    """
    from . import circuits as circuits_module
    from .contest import reussites_en_attente
    from .cycle import source_active

    refus: list[dict] = []
    avertissements: list[dict] = []

    if comp is None:
        refus.append(_constat(
            B2, "Aucune competition active : il n'y a rien a verifier, et rien "
                "a reprendre si le classeur disparait."))
        return {"peut_basculer": False, "refus": refus,
                "avertissements": [_constat(A4, _PHRASE_SAUVEGARDE)]}

    # B1 -- sans source d'inscrits, plus personne ne peut charger cent
    # participants. C'est le prerequis, et il se verifie plutot qu'il ne se
    # rappelle.
    if not source_active(comp, SOURCE_HELLOASSO):
        refus.append(_constat(
            B1, "Aucune source d'inscrits en dehors du classeur. Relier "
                "HelloAsso a cette edition avant de debrancher, sinon il ne "
                "reste que la saisie au guichet, une personne a la fois."))

    # B2 -- zero bloc, c'est un classeur jamais importe. Debrancher laisserait
    # une competition sans mur, et sans moyen d'en recuperer un.
    blocs = Bloc.query.filter_by(competition_id=comp.id).count()
    circuits = Circuit.query.filter_by(competition_id=comp.id).count()
    if not blocs or not circuits:
        refus.append(_constat(
            B2, f"« {comp.nom} » porte {blocs} voie(s) et {circuits} "
                f"categorie(s) en base. Importer le classeur avant de le "
                f"debrancher, ou saisir les voies dans la console."))

    en_attente = reussites_en_attente()
    if en_attente:
        avertissements.append(_constat(
            A1, f"{en_attente} reussite(s) attendent d'etre ecrites au "
                f"classeur. Elles n'y arriveront jamais -- elles ne sont "
                f"perdues pour personne, elles sont en base."))

    # A2 et A3 ne recalculent rien : `circuits.anomalies()` les connait deja.
    anomalies = circuits_module.inventaire(comp).get("anomalies") or {}
    orphelins = anomalies.get("blocs_sans_circuit") or []
    if orphelins:
        avertissements.append(_constat(
            A2, f"{len(orphelins)} voie(s) ne sont rattachees a aucune "
                f"categorie. Elles ne comptent pour personne."))
    sans_categorie = anomalies.get("categories_sans_circuit") or []
    if sans_categorie:
        avertissements.append(_constat(
            A3, "Des categories de participants n'ont pas de circuit : "
                + ", ".join(str(c) for c in sans_categorie)))

    # A4 s'affiche TOUJOURS. Ce n'est pas un defaut a corriger, c'est une
    # phrase a lire : la redondance gratuite disparait, et c'etait ecrit dans
    # docs/contraintes-metier.md §2 des le premier jour.
    avertissements.append(_constat(A4, _PHRASE_SAUVEGARDE))

    return {"peut_basculer": not refus, "refus": refus,
            "avertissements": avertissements}


_PHRASE_SAUVEGARDE = (
    "Le classeur ne redondera plus rien : la copie de la base toutes les dix "
    "minutes devient le seul filet.")
