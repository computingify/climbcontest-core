"""Configuration, lue de l'environnement.

Rien n'est en dur : ni l'identifiant du classeur (il vit en base, par
compétition), ni les secrets. Sur la VM, systemd charge
/opt/climbcontest/shared/secrets/env.
"""
import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _chemin_donnees() -> Path:
    """shared/data sur la VM, ./instance en développement.

    Les données ne sont JAMAIS dans une release : un déploiement ou un retour
    arrière ne doit pas pouvoir les toucher.
    """
    if defaut := os.environ.get("CLIMBCONTEST_DATA_DIR"):
        return Path(defaut)
    partage = Path("/opt/climbcontest/shared/data")
    return partage if partage.is_dir() else RACINE / "instance"


def _chemin_secrets() -> Path:
    """Ou vivent le jeton Google et les identifiants OAuth.

    Comme les donnees, ils sont HORS des releases : un deploiement ou un retour
    arriere ne doit pas pouvoir les toucher. L'unite systemd de la VM definit
    deja `CLIMBCONTEST_SECRETS_DIR` -- le code, lui, cherchait `token.pickle`
    en chemin RELATIF, donc dans le repertoire de travail du service, ou il n'a
    jamais ete. Resultat : « Aucun jeton Google » toutes les 40 secondes, et
    aucune reussite ne serait jamais arrivee dans le classeur.
    """
    if defaut := os.environ.get("CLIMBCONTEST_SECRETS_DIR"):
        return Path(defaut)
    partage = Path("/opt/climbcontest/shared/secrets")
    return partage if partage.is_dir() else RACINE / "security"


class Config:
    DOSSIER_DONNEES = _chemin_donnees()
    DOSSIER_SECRETS = _chemin_secrets()
    # Les recopies locales de la base, ecrites par climbcontest-sauvegarde.
    # `/health` en expose l'age : une sauvegarde qui s'arrete doit SE VOIR.
    DOSSIER_SAUVEGARDES = Path(
        os.environ.get("CLIMBCONTEST_SAUVEGARDES", str(DOSSIER_DONNEES.parent / "sauvegardes")))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "CLIMBCONTEST_DATABASE_URI",
        f"sqlite:///{DOSSIER_DONNEES / 'climbcontest.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ⚠️ Les fichiers statiques sont TOUJOURS revalides (spec 007).
    #
    # Par defaut, Flask les annonce cachables douze heures. Les vingt-cinq
    # telephones des juges garderaient donc l'ancien `juge.js` apres une
    # correction, sans que personne ne comprenne pourquoi le correctif « ne
    # marche pas » -- constate en developpant, sur cette machine.
    #
    # Le cout est nul : Flask envoie un `ETag`, le navigateur revalide et
    # recoit un `304` de quelques octets. Le fonctionnement HORS LIGNE est
    # assure par le service worker (IT4), avec une strategie explicite plutot
    # qu'un cache navigateur qu'on ne controle pas.
    SEND_FILE_MAX_AGE_DEFAULT = 0
    SECRET_KEY = os.environ.get("CLIMBCONTEST_SECRET_KEY", "dev-non-secret")

    # Le cookie de session de la console (audit du 30/08).
    #
    # Flask ne pose PAS `Secure` par defaut : le cookie d'un organisateur
    # connecte partirait en clair si quelqu'un force http://. En production le
    # site n'existe qu'en HTTPS derriere Caddy -- le cookie ne doit donc jamais
    # voyager autrement. `CLIMBCONTEST_COOKIE_SECURE=0` reste possible pour un
    # developpement local en http.
    SESSION_COOKIE_SECURE = os.environ.get("CLIMBCONTEST_COOKIE_SECURE", "1") == "1"
    SESSION_COOKIE_HTTPONLY = True     # le defaut de Flask, mais ecrit noir sur blanc
    # `Lax` et pas `Strict` : la console est ouverte en suivant un lien, et un
    # `Strict` couperait la session au premier clic depuis un message.
    SESSION_COOKIE_SAMESITE = "Lax"

    # Cles d'API des juges (spec 012).
    #
    # Plusieurs cles acceptees en parallele, pour pouvoir en changer sans jour
    # de bascule : on publie la nouvelle application, on attend que les
    # vingt-cinq telephones l'aient, puis on retire l'ancienne cle.
    #
    # Une chaine VIDE n'est pas une cle et n'entre pas dans le tuple. Sans ce
    # filtre, `CLIMBCONTEST_API_KEY=` ouvrirait la porte a un `X-Api-Key:` vide
    # -- exactement le trou qu'on ferme ici.
    API_KEYS = ()   # renseigne juste apres, par `cles_depuis_environnement`

    # ⚠️ Le defaut est STRICT depuis la spec 012 : une installation qui oublie
    # la variable est FERMEE, pas ouverte. Le mode tolere reste atteignable par
    # `CLIMBCONTEST_API_KEY_STRICTE=0` -- c'est la porte de sortie du plan de
    # repli, puisque le gel `V3.1.4` n'envoie aucune cle.
    API_KEY_STRICTE = os.environ.get("CLIMBCONTEST_API_KEY_STRICTE", "1") == "1"

    # Miroir vers le classeur Google.
    SHEETS_ACTIF = os.environ.get("CLIMBCONTEST_SHEETS_ACTIF", "1") == "1"
    SHEETS_TAILLE_LOT = int(os.environ.get("CLIMBCONTEST_SHEETS_LOT", "50"))
    # Rythme conserve de la version precedente (decision Q2 du 28/08) :
    # 50 reussites par lot, une tentative toutes les 40 secondes.
    SHEETS_PERIODE_S = int(os.environ.get("CLIMBCONTEST_SHEETS_PERIODE", "40"))


def cles_depuis_environnement(env=None) -> tuple:
    """Les cles d'API acceptees, lues dans l'environnement.

    Une fonction plutot qu'une expression dans la classe : la regle qui compte
    -- une chaine VIDE n'est pas une cle -- se teste alors avec un
    environnement choisi. Ecrite en ligne, elle ne se testait pas : la variable
    est absente pendant les tests, donc le tuple etait vide quoi qu'on fasse, et
    le test passait dans les deux sens.

    Sans ce filtre, `CLIMBCONTEST_API_KEY=` ouvrirait la porte a un
    `X-Api-Key: ` vide -- exactement le trou qu'on ferme.
    """
    env = os.environ if env is None else env
    return tuple(
        cle.strip() for cle in (
            env.get("CLIMBCONTEST_API_KEY"),
            # La PWA (spec 007) a SA cle, distincte de celle de l'Android. Elle
            # voyage dans un lien qu'on donne aux benevoles, donc elle se
            # promene plus qu'une cle enfermee dans un APK. La separer permet de
            # la revoquer sans toucher aux telephones Android.
            env.get("CLIMBCONTEST_API_KEY_PWA"),
            env.get("CLIMBCONTEST_API_KEY_PRECEDENTE"),
        ) if cle and cle.strip()
    )


Config.API_KEYS = cles_depuis_environnement()


class ConfigTest(Config):
    # ⚠️ **Le seul endroit du dépôt qui affaiblit la dérivation**, et le seul
    # qui ait le droit de le faire. `Config` — donc la production — n'en parle
    # pas et garde `scrypt` ; il n'existe aucune variable d'environnement pour
    # y toucher (voir `comptes.METHODE_HACHAGE`, et le garde
    # `tests/test_hachage.py` qui échoue si ce réglage remonte dans `Config`).
    #
    # Pourquoi : la suite fait plusieurs centaines de connexions, chacune à
    # deux dérivations. Mesuré le 04/09 — **39 s sur 123 s**, un tiers du temps
    # passé à calculer une lenteur dont aucun de ces tests ne vérifie l'effet.
    # Ceux dont le coût EST le sujet redemandent `scrypt` explicitement.
    HACHAGE_MOT_DE_PASSE = "pbkdf2:sha256:1"

    SQLALCHEMY_DATABASE_URI = "sqlite://"   # en mémoire
    SHEETS_ACTIF = False                    # aucun accès réseau dans les tests
    API_KEYS = ("cle-de-test",)
    # Le client de test parle en http : un cookie `Secure` n'y reviendrait
    # jamais, et TOUS les tests de session echoueraient pour une raison qui
    # n'a rien a voir avec ce qu'ils testent.
    SESSION_COOKIE_SECURE = False
