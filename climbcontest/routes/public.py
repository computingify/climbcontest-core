"""Ce que voient les spectateurs. Aucune authentification.

Ces routes sont exemptees de CrowdSec (voir la whitelist posee sur `edge`) et
mises en cache 5 s par Caddy : le jour d'une competition, ~60 telephones
rafraichissent toutes les 15 s, soit les trois quarts du trafic. Le cache
plafonne le calcul a 12 fois par minute quel que soit le nombre de spectateurs.
"""
import logging
import time

from flask import Blueprint, jsonify, request

from ..classement_service import classements
from ..contest import ErreurMetier, competition_active

logger = logging.getLogger(__name__)
bp = Blueprint("public", __name__, url_prefix="/api/public")


# L'ordre d'affichage, et pas l'ordre alphabetique des types : les categories
# d'abord (le resultat officiel), puis les circuits, puis les scratchs qui les
# traversent, et le club en dernier. Trie sur `type` seul, « club » se
# retrouvait AVANT « scratch » -- un detail qui se voit sur le mur, ou l'ordre
# de la barre est l'ordre du cycle.
ORDRE_DES_TYPES = {"categorie": 0, "circuit": 1, "scratch": 2, "club": 3}


def _ordre(classement):
    return (ORDRE_DES_TYPES.get(classement.type, 9), classement.groupe)


@bp.get("/classement")
def classement():
    """Tous les classements, ou un seul avec ?groupe=U13%20F.

    Le nom des participants est inclus : la page resultats doit les afficher,
    et ils sont deja publics -- affiches sur les dossards et annonces au micro.
    """
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    tous, calcule_le = classements(comp)

    demande = request.args.get("groupe")
    if demande:
        if demande not in tous:
            return jsonify({"success": False,
                            "message": f"Groupe « {demande} » inconnu",
                            "groupes": sorted(tous)}), 404
        choisis = {demande: tous[demande]}
    else:
        choisis = tous

    # Les noms, en une seule requete plutot qu'une par ligne.
    from ..models import Participant, Success
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

    return jsonify({
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
            for c in sorted(choisis.values(), key=_ordre)
        ],
    }), 200


@bp.get("/groupes")
def groupes():
    """La liste des classements disponibles, pour construire un menu."""
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code
    tous, _ = classements(comp)
    return jsonify({
        "groupes": [{"nom": c.groupe, "type": c.type, "participants": len(c.lignes)}
                    for c in sorted(tous.values(), key=lambda c: (c.type, c.groupe))]
    }), 200
