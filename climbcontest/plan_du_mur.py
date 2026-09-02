"""Le plan de la salle : lecture, validation, écriture (spec 029).

⚠️ Le plan a changé de nature. Tant qu'il était une constante Python, il était
du CODE : relu en revue, déployé, impossible à casser depuis un navigateur.
Depuis qu'il se dessine dans la console, c'est de la **donnée saisie** — et
elle est rendue en SVG sur un papier que cent vingt personnes reçoivent.

D'où deux règles qui gouvernent tout ce module :

1. **On ne fait confiance à rien de ce qui arrive.** Ce qui est réparable est
   réparé, ce qui ne l'est pas est refusé en nommant le mur fautif.
2. **Une lecture ne peut pas échouer.** Une ligne abîmée retombe sur le plan
   d'usine et le journalise. Imprimer les dossards la veille au soir ne doit
   pas dépendre de l'intégrité d'une ligne de base.
"""

import json
import logging

from .extensions import db
from .models import Reglage

logger = logging.getLogger(__name__)

CLE = "plan_du_mur"

# Les bornes. Généreuses : elles n'existent pas pour contraindre le dessin mais
# pour qu'un document absurde -- accidentel ou non -- ne parte pas au rendu.
MURS_MAXI = 200
REPERES_MAXI = 50
POINTS_MINI, POINTS_MAXI = 3, 60
VUE_MINI, VUE_MAXI = 40, 400
ZONE_MAXI = 3
TEXTE_MAXI = 24
TAILLE_MAXI = 256 * 1024        # le document JSON, en octets


class PlanInvalide(ValueError):
    """Le document est irréparable. Le message nomme ce qui cloche."""


def _nombre(v, quoi):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise PlanInvalide(f"{quoi} : « {v} » n'est pas un nombre")
    return round(float(v), 2)


def _point(p, quoi):
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        raise PlanInvalide(f"{quoi} : un point s'écrit avec deux nombres")
    return (_nombre(p[0], quoi), _nombre(p[1], quoi))


def valider(brut: dict) -> dict:
    """Rend un plan propre, ou lève `PlanInvalide` en nommant le fautif."""
    from . import fiches

    if not isinstance(brut, dict):
        raise PlanInvalide("le plan doit être un objet")

    vue = brut.get("vue")
    if not isinstance(vue, (list, tuple)) or len(vue) != 2:
        raise PlanInvalide("« vue » doit porter une largeur et une hauteur")
    largeur, hauteur = (_nombre(vue[0], "vue"), _nombre(vue[1], "vue"))
    for nom, v in (("largeur", largeur), ("hauteur", hauteur)):
        if not VUE_MINI <= v <= VUE_MAXI:
            raise PlanInvalide(
                f"la {nom} de la vue doit tenir entre {VUE_MINI} et {VUE_MAXI}")

    murs_bruts = brut.get("murs")
    if not isinstance(murs_bruts, (list, tuple)):
        raise PlanInvalide("« murs » doit être une liste")
    if len(murs_bruts) > MURS_MAXI:
        raise PlanInvalide(f"{len(murs_bruts)} murs : le maximum est {MURS_MAXI}")

    murs = []
    for i, m in enumerate(murs_bruts):
        if not isinstance(m, dict):
            raise PlanInvalide(f"le mur n° {i + 1} n'est pas un objet")
        # La zone identifie le mur dans les messages : on la lit en premier.
        zone = str(m.get("zone") or "").strip().upper()[:ZONE_MAXI]
        quoi = f"la zone {zone}" if zone else f"le mur n° {i + 1}"

        points = m.get("points")
        if not isinstance(points, (list, tuple)):
            raise PlanInvalide(f"{quoi} n'a pas de points")
        if not POINTS_MINI <= len(points) <= POINTS_MAXI:
            raise PlanInvalide(
                f"{quoi} a {len(points)} points ; il en faut entre "
                f"{POINTS_MINI} et {POINTS_MAXI}")
        propres = [_point(p, quoi) for p in points]
        for x, y in propres:
            if not (0 <= x <= largeur and 0 <= y <= hauteur):
                raise PlanInvalide(
                    f"{quoi} sort du dessin : ({x:g}, {y:g}) hors de "
                    f"{largeur:g} × {hauteur:g}")

        # ⚠️ Un profil inconnu ne fait PAS échouer l'enregistrement : il se
        # replie. Un plan par ailleurs bon ne doit pas être perdu pour un mot.
        profil = m.get("profil")
        if profil not in fiches.PAR_PROFIL:
            if profil is not None:
                logger.info("plan : profil « %s » inconnu sur %s, replie sur %s",
                            profil, quoi, fiches.PROFIL_PAR_DEFAUT)
            profil = fiches.PROFIL_PAR_DEFAUT

        etiquette = m.get("etiquette")
        murs.append({
            "zone": zone,
            "profil": profil,
            "points": tuple(propres),
            "etiquette": _point(etiquette, quoi) if etiquette else None,
        })

    reperes_bruts = brut.get("reperes") or []
    if not isinstance(reperes_bruts, (list, tuple)):
        raise PlanInvalide("« reperes » doit être une liste")
    if len(reperes_bruts) > REPERES_MAXI:
        raise PlanInvalide(
            f"{len(reperes_bruts)} repères : le maximum est {REPERES_MAXI}")

    reperes = []
    for i, r in enumerate(reperes_bruts):
        if not isinstance(r, dict):
            raise PlanInvalide(f"le repère n° {i + 1} n'est pas un objet")
        texte = str(r.get("texte") or "").strip()[:TEXTE_MAXI]
        if not texte:
            continue                      # un repère sans mot ne dit rien
        reperes.append({"texte": texte,
                        "point": _point(r.get("point"), f"le repère « {texte} »")})

    contour = brut.get("contour")
    if contour is not None:
        if not isinstance(contour, (list, tuple)) or len(contour) < POINTS_MINI:
            raise PlanInvalide("le contour doit porter au moins trois points")
        contour = tuple(_point(p, "le contour") for p in contour)

    return {"vue": (largeur, hauteur), "contour": contour,
            "murs": tuple(murs), "reperes": tuple(reperes)}


def _signaler_le_changement() -> None:
    """Incrémente la version du catalogue : les clients doivent se remettre à jour.

    ⚠️ Sans ça, un plan enregistré resterait invisible pour tout ce qui a déjà
    téléchargé le catalogue — le mur changerait sur le papier et pas à l'écran,
    et personne n'aurait de moyen de s'en apercevoir. C'est le même geste que
    pour un participant ajouté à 14 h.

    Import tardif : `contest` importe déjà ce qui touche au modèle.
    """
    from .contest import ErreurMetier, competition_active, incrementer_catalogue
    try:
        incrementer_catalogue(competition_active())
    except ErreurMetier:
        # Pas de compétition active : rien à prévenir. Dessiner le plan hors
        # saison est parfaitement légitime.
        logger.info("plan : aucune competition active, version non incrementee")


def lire():
    """Le plan enregistré, ou `None` s'il n'y en a pas — ou s'il est abîmé.

    ⚠️ Ne lève JAMAIS. Un appelant est en train d'imprimer des dossards.
    """
    try:
        ligne = db.session.get(Reglage, CLE)
    except Exception:                                    # base indisponible
        logger.exception("plan : lecture impossible, repli sur le plan d'usine")
        return None
    if not ligne:
        return None
    try:
        return valider(json.loads(ligne.valeur))
    except (ValueError, TypeError):
        logger.exception(
            "plan : la ligne enregistree est illisible, repli sur le plan d'usine")
        return None


def ecrire(brut: dict, par: str | None = None) -> dict:
    """Valide puis enregistre. Lève `PlanInvalide` si le document est refusé."""
    propre = valider(brut)
    texte = json.dumps(propre, ensure_ascii=False, default=list)
    if len(texte.encode("utf-8")) > TAILLE_MAXI:
        raise PlanInvalide("le plan dépasse la taille maximale")
    ligne = db.session.get(Reglage, CLE)
    if ligne is None:
        ligne = Reglage(cle=CLE)
        db.session.add(ligne)
    ligne.valeur = texte
    ligne.modifie_par = par
    _signaler_le_changement()
    db.session.commit()
    return propre


def effacer() -> bool:
    """Revient au plan d'usine. Rend vrai si une ligne a bien été supprimée."""
    ligne = db.session.get(Reglage, CLE)
    if not ligne:
        return False
    db.session.delete(ligne)
    _signaler_le_changement()
    db.session.commit()
    return True
