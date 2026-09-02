"""Le catalogue — ce que l'application juge télécharge pour travailler hors ligne.

C'est la pièce qui permettra à l'application (spec 003) de valider un scan
**sans réseau**, tout en voyant un participant ajouté à 14 h.

Le mécanisme est un simple numéro de version :

    GET /api/v2/catalog                       → tout, plus la version courante
    GET /api/v2/catalog?depuis=41             → 304 si rien n'a bougé, sinon tout
    GET /api/v2/catalog  If-None-Match: "41"  → idem, en HTTP standard

Il transporte aussi **le plan de la salle** (spec 029). C'est de la donnée de
référence partagée, comme les blocs — et surtout, la faire voyager ici la rend
versionnée : servie par une route à part, un client garderait un mur périmé sans
aucun moyen de le savoir.

Pourquoi renvoyer **tout** plutôt qu'un vrai delta : 98 participants et 67 blocs
font 6 à 8 ko compressés. Un delta économiserait quelques kilo-octets au prix
d'un suivi des suppressions et des conflits — de la complexité pour rien à cette
échelle. Le `304` fait déjà l'essentiel : quand rien n'a changé, il ne passe
presque rien sur le réseau, et c'est le cas la plupart du temps.

⚠️ Les specs 002 et 003 annonçaient toutes deux une « réponse différentielle ».
C'est **volontairement** abandonné, et les deux specs ont été corrigées plutôt
que le code : la règle du projet est que la spec suive la décision, pas qu'on
répare en douce en s'éloignant de ce qui a été écrit.

Deux mécanismes plutôt qu'un, parce qu'ils ne servent pas au même :

- `?depuis=` est explicite, se lit dans un journal d'accès, et convient à
  l'application juge qui garde sa version en mémoire ;
- `ETag` / `If-None-Match` est le mécanisme HTTP standard : c'est lui que
  comprennent Caddy, un cache intermédiaire ou un simple navigateur. Sans lui,
  la page de consultation retéléchargerait tout à chaque ouverture.
"""

import logging

from flask import Blueprint, jsonify, make_response, request

from ..auth import exige_cle_api
from ..contest import ErreurMetier, competition_active
from .. import fiches
from ..models import Bloc, Circuit, Participant

logger = logging.getLogger(__name__)
bp = Blueprint("catalogue", __name__, url_prefix="/api/v2")


@bp.get("/catalog")
@exige_cle_api
def catalogue():
    try:
        comp = competition_active()
    except ErreurMetier as e:
        return jsonify({"success": False, "message": e.message}), e.code

    version = comp.catalogue_version
    etiquette = f'"{version}"'

    # Deux façons de dire « j'ai déjà la version N ». On accepte les deux, et on
    # répond pareil : 304, corps vide, ~150 octets sur le réseau.
    depuis = request.args.get("depuis", type=int)
    connue = request.headers.get("If-None-Match", "")
    a_jour = (
        # ⚠️ `==`, et non `>=` (correctif du 30/08). Un client annoncant un
        # numero PLUS GRAND que la version courante n'est pas a jour : il vient
        # d'ailleurs -- d'une autre competition, ou d'une base restauree. Lui
        # repondre 304 le laissait travailler sur une liste qui n'est pas celle
        # de la competition en cours.
        (depuis is not None and depuis == version)
        # Un cache peut envoyer plusieurs étiquettes, ou les préfixer par W/.
        or any(e.strip().lstrip("W/").strip() == etiquette
               for e in connue.split(",") if e.strip())
    )
    if a_jour:
        # Rien de neuf : l'application garde ce qu'elle a.
        reponse = make_response("", 304)
        reponse.headers["ETag"] = etiquette
        reponse.headers["Cache-Control"] = "no-cache"
        return reponse

    participants = (Participant.query
                    .filter_by(competition_id=comp.id)
                    .order_by(Participant.dossard)
                    .all())
    blocs = (Bloc.query
             .filter_by(competition_id=comp.id)
             .order_by(Bloc.numero)
             .all())
    circuits = Circuit.query.filter_by(competition_id=comp.id).all()

    reponse = jsonify({
        "competition": {"id": comp.id, "nom": comp.nom, "statut": comp.statut},
        "version": version,
        # Seuls les participants qui ont un dossard sont scannables.
        "participants": [p.to_dict() for p in participants if p.dossard is not None],
        "blocs": [b.to_dict() for b in blocs],
        "circuits": [c.nom for c in circuits],
        # ⚠️ LE PLAN DE LA SALLE voyage avec le catalogue, et pas par une route
        # a lui (demande d'Adrien du 02/09 : « pourquoi tu ne pousses pas le
        # plan sur l'application ou le navigateur, [...] comme la base grimpeur
        # avec un systeme d'update ? »).
        #
        # Trois raisons, et la troisieme est la vraie :
        # 1. c'est de la donnee de REFERENCE partagee, comme les blocs ;
        # 2. le `304` la rend gratuite quand elle n'a pas bouge -- et elle ne
        #    bouge presque jamais ;
        # 3. surtout, elle devient VERSIONNEE. Servie a part, un client
        #    garderait un mur perime sans aucun moyen de le savoir.
        #
        # Enregistrer un plan incremente donc `catalogue_version`
        # (`plan_du_mur.ecrire`), exactement comme ajouter un participant.
        "plan": fiches.plan_courant(),
    })
    reponse.headers["ETag"] = etiquette
    # `no-cache` ne veut pas dire « ne cache pas » : il veut dire « revalide
    # avant de servir ». C'est exactement ce qu'on veut — un participant ajouté
    # à 14 h doit être vu, et la revalidation coûte 150 octets.
    reponse.headers["Cache-Control"] = "no-cache"
    return reponse, 200
