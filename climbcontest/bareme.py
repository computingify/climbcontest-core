"""Le barème d'une édition : appliquer la règle FFME aux inscrits — spec 008.

`categories.py` porte la **règle**, pure et sans base. Ce module-ci la branche
sur une compétition : il en déduit l'année de référence et les Under, compte les
inscrits par tranche, et sait recalculer les catégories de tout le monde.

La séparation vaut la peine : la règle se vérifie contre le tableau publié par
la fédération sans monter d'application, et c'est le seul test qui prouve
quelque chose. Ici, on ne fait que la promener sur des lignes de base.

## Ce qu'« Appliquer à tous » ne touche jamais

Quatre familles sont **laissées en place**, et chacune pour une raison qu'on
peut dire à voix haute :

| Famille | Pourquoi |
| --- | --- |
| Sans année de naissance | On ne remplace pas une catégorie saisie par un vide calculé |
| Sans catégorie de départ | Le genre est inconnu : produire « U13 » à côté de « U13 F » fragmenterait le classement |
| Hors barème | Un adulte, une année aberrante. On signale, on ne devine pas |
| Corrigée à la main | Décision D10 : quelqu'un connaissait le cas particulier |

C'est ce qui permet au bouton d'être sûr : il ne peut rien faire d'autre que ce
que l'aperçu vient de montrer.
"""

import logging
from datetime import datetime

from . import categories, formatage
from .contest import ErreurMetier, incrementer_catalogue
from .cycle import ecrire_options, lire_options
from .extensions import db
from .models import Circuit, Participant

logger = logging.getLogger(__name__)


def _genre(categorie: str | None) -> str | None:
    """« U13 F » → « F ». « U13 » → None.

    Le dernier mot d'une catégorie est son genre — c'est ce que
    `Participant.circuit` suppose déjà en faisant l'opération inverse.
    """
    if not categorie:
        return None
    morceaux = str(categorie).split()
    return morceaux[-1] if len(morceaux) > 1 else None


def reference(comp) -> int:
    """L'année de référence de cette édition.

    Une compétition sans date ne devrait pas exister — `Competition.date` a un
    défaut — mais si elle arrive, on retombe sur aujourd'hui plutôt que de
    lever : le barème est une aide, il ne doit jamais empêcher d'ouvrir un
    écran.
    """
    jour = comp.date or datetime.now().date()
    return categories.annee_de_reference(jour)


def categories_declarees(comp) -> list[str]:
    """Les catégories que l'édition annonce, indépendamment de toute source.

    ⚠️ **C'est la porte de sortie du classeur Google.** Adrien l'a rappelé le
    04/09 : le classeur est temporaire, il finira par disparaître.

    Or les `Circuit` ne sont créés QUE par `sheets/importer.py`. Le jour où le
    classeur s'en va, une édition alimentée par HelloAsso seul n'aurait ni
    circuit ni participant catégorisé au premier relevé : la liste des Under
    serait vide, aucune catégorie ne se calculerait, et **les cent inscriptions
    partiraient en attente** — le défaut d'amorçage déjà fermé une fois, qui
    reviendrait par une autre porte.

    Cette liste se déclare depuis la console, en une ligne. Elle ne remplace
    rien tant que le classeur est là ; elle rend simplement le barème
    indépendant de lui.
    """
    valeur = lire_options(comp).get("categories_declarees")
    if not isinstance(valeur, list):
        return []
    return [formatage.categorie(str(n)) for n in valeur
            if str(n).strip()]


def declarer_categories(comp, noms) -> list[str]:
    """Range la liste déclarée. Les noms passent par le formatage, comme le reste."""
    if not isinstance(noms, list):
        raise ErreurMetier("Une liste de categories est attendue.")
    propres = sorted({formatage.categorie(str(n)) for n in noms if str(n).strip()})
    ecrire_options(comp, categories_declarees=propres)
    logger.info("competition %s : %d categorie(s) declaree(s)", comp.id, len(propres))
    return propres


def unders(comp) -> list[int]:
    """Les Under de cette édition, tirés de TROIS sources qui se complètent.

    | Source | D'où elle vient | Ce qu'elle couvre |
    | --- | --- | --- |
    | Les catégories des participants | Dérivées, comme la liste déroulante | L'édition en cours de route |
    | Les **circuits** | L'import du classeur | L'amorçage, tant que le classeur existe |
    | Les catégories **déclarées** | La console | L'amorçage **sans** classeur |

    Aucune n'est obligatoire, et celle qui est vide n'empêche pas les autres.
    C'est ce qui fait que ce calcul survivra au classeur, dont la disparition
    est prévue.
    """
    des_participants = (v for (v,) in db.session.query(Participant.categorie)
                        .filter(Participant.competition_id == comp.id,
                                Participant.categorie.isnot(None))
                        .distinct())
    des_circuits = (c.nom for c in Circuit.query.filter_by(competition_id=comp.id))
    return categories.unders_de(list(des_participants) + list(des_circuits)
                                + categories_declarees(comp))


def categorie_calculee(participant, ref: int, liste_unders) -> str | None:
    """La catégorie que le barème donnerait à ce participant, ou None.

    None veut dire « on ne sait pas », jamais « pas de catégorie » : l'appelant
    laisse alors la ligne intacte.
    """
    if participant.annee_naissance is None:
        return None
    circuit = categories.circuit(participant.annee_naissance, ref, liste_unders)
    if circuit is None:
        return None
    genre = _genre(participant.categorie)
    if not participant.categorie:
        return None                     # genre inconnu : voir l'en-tete du module
    return formatage.categorie(f"{circuit} {genre}" if genre else circuit)


def tranches(comp) -> list[dict]:
    """Le barème affiché : une ligne par catégorie de l'édition.

    Les catégories hors barème — « Senior », « Adulte » — figurent aussi, avec
    des années vides. Les taire donnerait l'impression qu'elles n'existent pas,
    alors qu'elles portent des grimpeurs.
    """
    ref = reference(comp)
    liste_unders = unders(comp)

    # Les categories DECLAREES figurent a zero : voir l'edition avant que
    # quiconque se soit inscrit est precisement ce a quoi elles servent.
    comptes = {nom: 0 for nom in categories_declarees(comp)}
    for (nom,) in db.session.query(Participant.categorie).filter(
            Participant.competition_id == comp.id):
        if nom:
            comptes[nom] = comptes.get(nom, 0) + 1

    lignes = []
    for tranche in categories.bareme(ref, liste_unders):
        # Les categories de l'edition qui portent ce Under : « U13 F », « U13 H ».
        portees = sorted(n for n in comptes
                         if categories.under(n) == categories.under(tranche.circuit))
        lignes.append({
            "circuit": tranche.circuit,
            "categories": portees,
            "annee_min": tranche.annee_min,
            "annee_max": tranche.annee_max,
            "age_min": tranche.age_min,
            "age_max": tranche.age_max,
            "inscrits": sum(comptes[n] for n in portees),
            "hors_bareme": False,
        })

    for nom in sorted(comptes):
        if categories.under(nom) is None:
            lignes.append({
                "circuit": nom, "categories": [nom],
                "annee_min": None, "annee_max": None,
                "age_min": None, "age_max": None,
                "inscrits": comptes[nom], "hors_bareme": True,
            })
    return lignes


def hors_de_portee(comp) -> dict:
    """Ce que le barème ne peut ranger, et pourquoi. Une ligne à l'écran.

    ⚠️ Le contrôle de cohérence annoncé dans la maquette — recouvrement, trou,
    circuit vide — n'a plus lieu d'être : depuis que le barème se **dérive** de
    l'ensemble des Under au lieu d'être saisi, il partitionne les années par
    construction. Un trou ou un recouvrement y sont inexprimables.

    Ce qui reste vrai et utile, c'est ceci : combien de personnes le barème ne
    peut pas ranger, et pour quelle raison. C'est actionnable — l'une se règle
    en saisissant une année, l'autre en admettant qu'un adulte n'a pas de U.
    """
    ref = reference(comp)
    liste_unders = unders(comp)
    sans_annee = hors = 0
    for p in Participant.query.filter_by(competition_id=comp.id):
        if p.annee_naissance is None:
            sans_annee += 1
        elif categories.circuit(p.annee_naissance, ref, liste_unders) is None:
            hors += 1
    return {"sans_annee": sans_annee, "hors_bareme": hors}


def apercu(comp, forcer: bool = False) -> dict:
    """Ce que « Appliquer » changerait. **N'écrit rien.**

    C'est la même fonction qui décide, ici et dans `appliquer()` : un aperçu
    calculé par un chemin différent de l'application finirait par mentir.
    """
    ref = reference(comp)
    liste_unders = unders(comp)

    changements, ignores = [], {
        "sans_annee": 0, "sans_categorie": 0,
        "hors_bareme": 0, "corrigees_a_la_main": 0,
    }
    inchanges = 0

    for p in Participant.query.filter_by(competition_id=comp.id):
        if p.annee_naissance is None:
            ignores["sans_annee"] += 1
            continue
        if p.categorie_forcee and not forcer:
            ignores["corrigees_a_la_main"] += 1
            continue
        if not p.categorie:
            ignores["sans_categorie"] += 1
            continue
        nouvelle = categorie_calculee(p, ref, liste_unders)
        if nouvelle is None:
            ignores["hors_bareme"] += 1
            continue
        if nouvelle == p.categorie:
            inchanges += 1
            continue
        changements.append({
            "id": p.id, "dossard": p.dossard, "nom": p.nom_complet,
            "annee_naissance": p.annee_naissance,
            "avant": p.categorie, "apres": nouvelle,
        })

    changements.sort(key=lambda c: (c["dossard"] is None, c["dossard"] or 0))
    return {
        "reference": ref,
        "saison": f"{ref - 1}-{ref}",
        "changements": changements,
        "inchanges": inchanges,
        "ignores": ignores,
    }


def appliquer(comp, par: str | None = None, forcer: bool = False) -> dict:
    """Recalcule les catégories. Rend le même rapport que l'aperçu.

    ⚠️ `categorie_forcee` n'est PAS remise à zéro par un forçage. Le geste a eu
    lieu ; l'effacer ferait qu'une seconde application défairait le travail sans
    plus rien pour prévenir. Elle ne se lève qu'en modifiant la ligne à la main.
    """
    rapport = apercu(comp, forcer=forcer)
    if not rapport["changements"]:
        return rapport

    par_identifiant = {c["id"]: c for c in rapport["changements"]}
    for p in Participant.query.filter(Participant.id.in_(par_identifiant)):
        p.categorie = par_identifiant[p.id]["apres"]
        db.session.add(p)

    # Les telephones doivent revoir la liste : la categorie voyage dans le
    # catalogue, et c'est elle qui decide du circuit affiche au juge.
    incrementer_catalogue(comp)
    db.session.commit()

    logger.info("bareme applique par %s : %d categorie(s) recalculee(s)",
                par or "?", len(rapport["changements"]))
    return rapport


def regler_a_la_main(participant, categorie: str | None) -> None:
    """Range quelqu'un contre le barème, et laisse la trace du geste.

    Appelée par l'édition en ligne. Elle ne décide pas si la catégorie diffère
    du barème : elle marque dès qu'un humain a touché la catégorie, ce qui est
    plus simple à expliquer — et une marque de trop ne coûte qu'un décompte
    dans l'aperçu, alors qu'une marque manquante coûte un travail défait.
    """
    propre = formatage.categorie(categorie)
    if propre != participant.categorie:
        participant.categorie_forcee = True
    participant.categorie = propre
    db.session.add(participant)
