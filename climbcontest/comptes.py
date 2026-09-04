"""Comptes de la console d'administration : creation, mot de passe, roles.

Le modele (`Utilisateur`, `UtilisateurRole`) est en base depuis la spec 002,
pose a l'avance pour eviter une migration ici. Ce module lui donne enfin un
usage.

DEUX ROLES, et rien de plus (decision d'Adrien du 29/08) :

    admin          comptes, competitions, parametres, classeur
                   + tout ce que fait l'organisateur
    organisateur   participants a chaud, reaffectation, saisie manuelle,
                   impression des dossards

Assez pour que personne ne casse rien par accident, sans transformer une
journee benevole en gestion de droits.
"""
import logging

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import Utilisateur, UtilisateurRole

logger = logging.getLogger(__name__)

ADMIN = "admin"
ORGANISATEUR = "organisateur"
ROLES_CONNUS = frozenset({ADMIN, ORGANISATEUR})

# --- Le cout de derivation du mot de passe ----------------------------------
#
# `scrypt` est le defaut de Werkzeug, et il est LENT A DESSEIN : 54 ms par
# hachage sur cette machine. C'est ce qui rend une liste de mots de passe voles
# inexploitable, et ce que `routes/admin.py` protege derriere le frein de la
# spec 015.
#
# ⚠️ Cette valeur reste le defaut PARTOUT. Une installation qui ne dit rien
# hache en scrypt -- il n'y a pas de variable d'environnement pour l'affaiblir,
# et c'est voulu : un reglage de securite qu'on peut baisser depuis
# l'environnement finit baisse en production, un jour, par accident.
#
# Le seul moyen d'en changer est de PASSER une configuration qui le dit, et
# `ConfigTest` est la seule du depot a le faire. `tests/test_hachage.py`
# verifie qu'une application de production hache bien en scrypt -- et il echoue
# si quelqu'un pose ce reglage dans `Config`.
METHODE_HACHAGE = "scrypt"


def _methode_hachage() -> str:
    """La methode de derivation de cette application.

    Lue dans la configuration plutot que figee : la suite de tests fait
    plusieurs centaines de connexions, et chacune coute DEUX derivations -- une
    a la creation du compte, une a la verification. Mesure du 04/09 : **39 s
    sur 123 s**, un tiers de la suite passe a deriver des cles dont aucun test
    ne verifie la solidite.

    Les rares tests dont le cout EST le sujet -- l'egalisation du temps de
    reponse entre un compte connu et un inconnu -- redemandent la vraie
    methode. Chacun paie ce qu'il verifie, et rien d'autre.
    """
    from flask import current_app, has_app_context
    if has_app_context():
        return current_app.config.get("HACHAGE_MOT_DE_PASSE") or METHODE_HACHAGE
    return METHODE_HACHAGE


def _hacher(mot_de_passe: str) -> str:
    return generate_password_hash(mot_de_passe, method=_methode_hachage())

# Longueur minimale. Volontairement modeste : ces comptes servent a des
# benevoles, le jour d'une competition, souvent sur un clavier de telephone.
# Exiger une majuscule, un chiffre et un caractere special produirait un
# mot de passe ecrit sur un post-it colle a l'ecran -- ce qui est pire.
LONGUEUR_MINIMALE = 10


class ErreurCompte(Exception):
    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code


def creer(identifiant: str, mot_de_passe: str, roles: list[str],
          nom_affiche: str | None = None) -> Utilisateur:
    """Cree un compte. Le mot de passe n'est jamais conserve en clair."""
    identifiant = (identifiant or "").strip().lower()
    if not identifiant:
        raise ErreurCompte("Un identifiant est obligatoire.")
    if len(mot_de_passe or "") < LONGUEUR_MINIMALE:
        raise ErreurCompte(
            f"Le mot de passe doit faire au moins {LONGUEUR_MINIMALE} caracteres.")

    inconnus = set(roles or []) - ROLES_CONNUS
    if inconnus:
        # Fail closed : un role qu'on ne connait pas n'est pas un role qu'on
        # accorde « au cas ou ». Il est refuse a la creation, sinon il vivrait
        # en base et le controle d'acces devrait deviner quoi en faire.
        raise ErreurCompte(f"Role(s) inconnu(s) : {', '.join(sorted(inconnus))}")
    if not roles:
        raise ErreurCompte("Un compte sans role ne sert a rien.")

    if Utilisateur.query.filter_by(identifiant=identifiant).first():
        raise ErreurCompte(f"L'identifiant « {identifiant} » est deja pris.", code=409)

    u = Utilisateur(
        identifiant=identifiant,
        mot_de_passe_hache=_hacher(mot_de_passe),
        nom_affiche=(nom_affiche or "").strip() or None,
        actif=True,
    )
    db.session.add(u)
    db.session.flush()
    for role in sorted(set(roles)):
        db.session.add(UtilisateurRole(utilisateur_id=u.id, role=role))
    db.session.commit()
    # L'identifiant, jamais le mot de passe -- meme pas sa longueur.
    logger.info("compte cree : %s (%s)", identifiant, ", ".join(sorted(set(roles))))
    return u


def verifier(identifiant: str, mot_de_passe: str) -> Utilisateur | None:
    """Renvoie l'utilisateur si le couple est bon, sinon None.

    ⚠️ Le temps de reponse doit etre le MEME que l'identifiant existe ou non.
    Repondre plus vite pour un compte inconnu revelerait quels identifiants sont
    valides -- et sur une console exposee, c'est la premiere chose qu'on teste.
    D'ou le hachage a vide ci-dessous, qui n'a l'air de rien mais coute
    exactement le meme temps qu'une verification reelle.
    """
    identifiant = (identifiant or "").strip().lower()
    u = Utilisateur.query.filter_by(identifiant=identifiant).first()

    if u is None or not u.actif:
        check_password_hash(_hachage_factice(), mot_de_passe or "")
        return None

    if not check_password_hash(u.mot_de_passe_hache, mot_de_passe or ""):
        return None
    return u


# Hachage d'un mot de passe qui n'existe pas. Sert uniquement a egaliser le
# temps de reponse (voir `verifier`).
#
# ⚠️ Un par METHODE, et calcule a la demande. Il etait calcule une fois au
# chargement du module, avec la methode par defaut -- ce qui aurait casse
# l'egalisation des que l'application en utilise une autre : le chemin
# « compte inconnu » aurait paye un scrypt pendant que le chemin « mauvais mot
# de passe » n'en payait plus. C'est exactement la difference de temps que ce
# hachage existe pour effacer.
_FACTICES: dict[str, str] = {}

FAUX_MOT_DE_PASSE = "aucun-compte-ne-porte-ce-mot-de-passe"


def _hachage_factice() -> str:
    methode = _methode_hachage()
    if methode not in _FACTICES:
        _FACTICES[methode] = generate_password_hash(FAUX_MOT_DE_PASSE,
                                                    method=methode)
    return _FACTICES[methode]


def changer_mot_de_passe(u: Utilisateur, nouveau: str) -> None:
    if len(nouveau or "") < LONGUEUR_MINIMALE:
        raise ErreurCompte(
            f"Le mot de passe doit faire au moins {LONGUEUR_MINIMALE} caracteres.")
    u.mot_de_passe_hache = _hacher(nouveau)
    db.session.add(u)
    db.session.commit()
    # L'identifiant, jamais le mot de passe -- meme pas sa longueur.
    logger.info("mot de passe change pour %s", u.identifiant)


def administrateurs_actifs() -> list[Utilisateur]:
    """Les comptes qui peuvent encore gerer les autres."""
    return [u for u in Utilisateur.query.filter_by(actif=True).all() if u.a_le_role(ADMIN)]


def _verifier_qu_il_restera_un_admin(u: Utilisateur, futur_admin: bool) -> None:
    """Empeche de supprimer le DERNIER administrateur.

    Le piege classique, et il est sans retour : l'unique administrateur se
    retire ses droits ou desactive son compte « pour faire propre », et plus
    personne ne peut gerer les comptes. Il faut alors un acces SSH a la VM et
    la ligne de commande -- exactement ce qu'on cherche a eviter, et
    typiquement un dimanche matin.
    """
    if futur_admin or not u.a_le_role(ADMIN):
        return                                  # on ne retire rien
    autres = [a for a in administrateurs_actifs() if a.id != u.id]
    if not autres:
        raise ErreurCompte(
            "C'est le dernier administrateur : lui retirer ce role fermerait "
            "la gestion des comptes a tout le monde. Nomme d'abord quelqu'un "
            "d'autre administrateur.",
            code=409)


def definir_roles(u: Utilisateur, roles: list[str]) -> None:
    inconnus = set(roles or []) - ROLES_CONNUS
    if inconnus:
        raise ErreurCompte(f"Role(s) inconnu(s) : {', '.join(sorted(inconnus))}")
    if not roles:
        raise ErreurCompte("Un compte sans role ne sert a rien.")
    _verifier_qu_il_restera_un_admin(u, futur_admin=ADMIN in roles)
    UtilisateurRole.query.filter_by(utilisateur_id=u.id).delete()
    for role in sorted(set(roles)):
        db.session.add(UtilisateurRole(utilisateur_id=u.id, role=role))
    db.session.commit()
    logger.info("roles de %s : %s", u.identifiant, ", ".join(sorted(set(roles))))


def desactiver(u: Utilisateur) -> None:
    """Desactive plutot que supprimer : les reussites saisies gardent leur auteur."""
    _verifier_qu_il_restera_un_admin(u, futur_admin=False)
    u.actif = False
    db.session.add(u)
    db.session.commit()
    logger.info("compte desactive : %s", u.identifiant)


def reactiver(u: Utilisateur) -> None:
    u.actif = True
    db.session.add(u)
    db.session.commit()
    logger.info("compte reactive : %s", u.identifiant)


def existe_un_admin() -> bool:
    return db.session.query(
        UtilisateurRole.query.filter_by(role=ADMIN).join(
            Utilisateur, UtilisateurRole.utilisateur_id == Utilisateur.id
        ).filter(Utilisateur.actif.is_(True)).exists()
    ).scalar()
