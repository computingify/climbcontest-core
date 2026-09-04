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

## Ce que le téléphone dit de lui au passage (spec 030)

Trois en-têtes **facultatifs** — `X-Device-Id`, `X-Device-Name`,
`X-App-Version` — permettent au téléphone de dire qui il est et quelle version
il exécute, **sans une requête de plus** : écran allumé, il en fait déjà une
toutes les trente secondes. Le serveur répond avec `X-Server-Version`, sur les deux branches, et
le téléphone sait ainsi s'il est en retard sans appeler `/health`, que Caddy
lui ferme.

⚠️ **Cette route est donc un `GET` avec effet de bord, et ça se protège.** Elle
ne peut pas être mise en cache : la réponse porte `Cache-Control: no-cache,
private`, un test le verrouille sur les deux branches, la même annonce est
enregistrée en redondance depuis la route des lots (un `POST`, jamais mis en
cache), et la console signale un téléphone qui envoie des réussites sans plus
s'annoncer — la signature exacte d'un cache posé devant cette route. Le
raisonnement complet est dans `specs/030-versions-visibles/spec.md`, F8.
"""

import logging
from urllib.parse import unquote

from flask import Blueprint, jsonify, make_response, request

from ..auth import exige_cle_api
from ..contest import ErreurMetier, competition_active, enregistrer_annonce
from .. import fiches
from ..models import Bloc, Circuit, Participant
from ..version import VERSION

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

    # ⚠️ L'ANNONCE SE FAIT ICI, AVANT LE CALCUL DE `a_jour` -- et jamais apres.
    #
    # La garde ci-dessous fait un RETOUR ANTICIPE sur le 304 : tout ce qui la
    # suit n'est jamais atteint quand le telephone est deja a jour. Or c'est le
    # cas MAJORITAIRE le jour J -- la PWA revalide toutes les trente secondes et le
    # catalogue ne bouge presque jamais. Une annonce enregistree apres la garde
    # ne montrerait dans la console que les telephones EN RETARD : l'exact
    # inverse de ce qu'on veut voir, avec un telephone parfaitement a jour
    # indiscernable d'un telephone eteint.
    _annoncer(version)

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
        return _entetes(reponse)

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
    return _entetes(reponse), 200


def _entetes(reponse):
    """Les en-têtes communs aux DEUX branches, 200 et 304.

    ⚠️ Une fonction, et pas deux blocs recopiés : le `304` construit sa réponse
    séparément et repose ses en-têtes à la main. C'est exactement le genre
    d'endroit où on ajoute quelque chose au chemin `200` et où on l'oublie sur
    l'autre — c'est-à-dire sur le chemin majoritaire.

    `no-cache` ne veut pas dire « ne cache pas » : il veut dire « revalide avant
    de servir ». C'est ce qu'on veut — un participant ajouté à 14 h doit être
    vu, et la revalidation coûte 150 octets.

    ⚠️ `private` **n'est pas décoratif**, et le retirer casserait le tableau des
    appareils de la console sans qu'aucun test fonctionnel ne bronche. Cette
    route enregistre une annonce à chaque appel (`_annoncer`) : c'est un `GET`
    avec effet de bord, ce qui n'est acceptable QUE parce que la requête atteint
    réellement l'application à chaque fois. Un cache **partagé** — un module
    Caddy, un CDN, un proxy sur le wifi de la salle — aurait le droit, sans
    `private`, de servir la réponse d'un téléphone à tous les autres : le
    serveur cesserait de voir qui tourne sur quoi, et la console montrerait des
    téléphones « absents » pendant qu'ils grimpent. `private` interdit ce
    stockage-là. Il est verrouillé par un test, sur les deux branches.
    """
    reponse.headers["Cache-Control"] = "no-cache, private"
    reponse.headers["X-Server-Version"] = VERSION
    return reponse


def _annoncer(version_courante: int) -> None:
    """Note le passage du téléphone. **Ne peut jamais faire échouer la route.**

    Trois en-têtes facultatifs, et le serveur se passe des trois : une requête
    qui n'en porte aucun se comporte exactement comme avant. C'est ce qui permet
    à l'application Android du Play Store, qui ne les envoie pas, de continuer
    sans rien changer.

    ⚠️ Des **en-têtes**, et non des paramètres d'URL : le nom d'un poste n'a rien
    à faire dans le journal d'accès de Caddy — la spec 014 a justement dû y
    poser un filtre pour en retirer le jeton du juge.

    ⚠️ Le numéro enregistré est celui que le téléphone DÉTIENDRA à la fin de
    l'échange, c'est-à-dire le numéro courant. Un `304` veut dire qu'ils sont
    déjà égaux ; un `200` que le téléphone reçoit le courant à l'instant.
    Enregistrer le numéro *annoncé* ferait clignoter en ambre, pendant cinq
    minutes après chaque import, des téléphones qui viennent de se mettre à jour.
    """
    identifiant = (request.headers.get("X-Device-Id") or "").strip()
    if not identifiant:
        return
    nom = request.headers.get("X-Device-Name") or ""
    try:
        # Percent-encodé par le client : un nom porte des accents, un en-tête
        # HTTP ne les transporte pas sûrement.
        nom = unquote(nom).strip()
    except Exception:
        # Un encodage abîmé coûte le nom, jamais la requête.
        nom = ""
    enregistrer_annonce(
        identifiant,
        nom=nom or None,
        version_app=(request.headers.get("X-App-Version") or "").strip() or None,
        catalogue_version=version_courante,
    )
