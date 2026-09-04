"""Le cout de derivation des mots de passe : allege en test, JAMAIS ailleurs.

La suite fait plusieurs centaines de connexions, et chacune coute DEUX
derivations `scrypt` -- une a la creation du compte, une a la verification.
Mesure du 04/09 : **45 s sur 123 s**, plus d'un tiers de la suite passe a
calculer une lenteur dont presque aucun test ne verifie l'effet. `ConfigTest`
ramene donc la derivation a `pbkdf2:sha256:1`.

⚠️ **C'est un reglage de securite qu'on baisse.** Le seul qui rende ce geste
acceptable, c'est ce fichier : il echoue si l'allegement deborde du test.
Sans lui, la ligne de `ConfigTest` serait une invitation a la recopier « pour
que ce soit pareil partout », et la production hacherait les mots de passe des
organisateurs en une milliseconde.

Le contrat verifie ici, en trois points :

1. la production hache en `scrypt`, et rien dans `Config` ne dit le contraire ;
2. aucune variable d'environnement ne peut l'affaiblir -- il n'y a pas de porte
   a fermer, il n'y en a jamais eu ;
3. l'allegement ne casse pas ce que `scrypt` protegeait : les hachages deja en
   base restent verifiables, et l'egalisation du temps de reponse tient.
"""
import os

import pytest
from werkzeug.security import check_password_hash

from climbcontest import comptes, creer_app
from climbcontest.config import Config, ConfigTest


class TestLaProductionHacheEnScrypt:
    def test_config_ne_porte_aucun_reglage_de_hachage(self):
        """Le garde principal. Si ce reglage remonte dans `Config`, TOUTE
        installation qui ne dit rien hache au rabais -- y compris la VM."""
        assert not hasattr(Config, "HACHAGE_MOT_DE_PASSE"), (
            "`Config` porte HACHAGE_MOT_DE_PASSE : la production hacherait les "
            "mots de passe avec la methode allegee des tests. Ce reglage "
            "n'appartient qu'a ConfigTest")

    def test_une_application_de_production_hache_en_scrypt(self):
        """On ne lit pas la configuration : on regarde le hachage PRODUIT."""
        app = creer_app(Config)
        with app.app_context():
            assert comptes._methode_hachage() == "scrypt"
            hache = comptes._hacher("un-mot-de-passe-de-test")
        assert hache.startswith("scrypt:"), (
            f"la production a produit un hachage {hache.split('$')[0]!r} : ce "
            "n'est pas scrypt")

    def test_hors_de_toute_application_la_methode_reste_forte(self):
        """Un script qui hache sans contexte Flask -- un outil de `tools/`, une
        commande CLI -- ne doit pas tomber sur le defaut le plus faible."""
        assert comptes._methode_hachage() == "scrypt"

    def test_aucune_variable_d_environnement_ne_peut_affaiblir_le_hachage(self,
                                                                         monkeypatch):
        """Un reglage de securite lisible depuis l'environnement finit baisse
        en production, un jour, par accident. Il n'y a donc pas de variable --
        et ce test echouerait si quelqu'un en ajoutait une."""
        for nom in ("CLIMBCONTEST_HACHAGE", "CLIMBCONTEST_HACHAGE_MOT_DE_PASSE",
                    "HACHAGE_MOT_DE_PASSE"):
            monkeypatch.setenv(nom, "pbkdf2:sha256:1")
        app = creer_app(Config)
        with app.app_context():
            assert comptes._methode_hachage() == "scrypt", (
                "une variable d'environnement a change la methode de hachage")


class TestLAllegementNeCassePasCeQuIlAllege:
    def test_le_test_hache_bien_au_rabais(self):
        """Le pendant du garde : si l'allegement ne s'appliquait plus, la suite
        redeviendrait lente sans que personne ne comprenne pourquoi."""
        assert ConfigTest.HACHAGE_MOT_DE_PASSE == "pbkdf2:sha256:1"
        app = creer_app(ConfigTest)
        with app.app_context():
            assert comptes._hacher("x").startswith("pbkdf2:sha256:1$")

    def test_un_hachage_scrypt_reste_verifiable_en_mode_test(self, app):
        """Le cas d'une VRAIE base ouverte par un test.

        Un compte cree en production porte un hachage scrypt. Si la
        verification suivait la methode CONFIGUREE au lieu de celle inscrite
        dans le hachage, ce compte ne pourrait plus se connecter -- et un
        rejeu de sauvegarde le decouvrirait le jour ou on en a besoin.
        """
        from werkzeug.security import generate_password_hash
        scrypt = generate_password_hash("mot-de-passe-de-prod", method="scrypt")
        assert check_password_hash(scrypt, "mot-de-passe-de-prod")
        assert not check_password_hash(scrypt, "autre-chose")

    def test_le_hachage_a_vide_suit_la_methode_de_l_application(self, app):
        """L'egalisation du temps de reponse ne tient que si les deux chemins
        coutent pareil.

        Le hachage a vide etait calcule UNE FOIS au chargement du module, avec
        la methode par defaut. Des lors que l'application en utilise une autre,
        le chemin « compte inconnu » aurait paye un scrypt pendant que le
        chemin « mauvais mot de passe » n'en payait plus : exactement la
        difference de temps que ce hachage existe pour effacer, mais dans
        l'autre sens.
        """
        assert comptes._hachage_factice().startswith("pbkdf2:sha256:1$")

        app_prod = creer_app(Config)
        with app_prod.app_context():
            assert comptes._hachage_factice().startswith("scrypt:")

    def test_un_compte_cree_en_mode_test_se_connecte(self, app):
        """Le bout de la chaine : creer puis verifier, avec la methode allegee."""
        comptes.creer("essai", "un-mot-de-passe-assez-long", [comptes.ADMIN])
        assert comptes.verifier("essai", "un-mot-de-passe-assez-long") is not None
        assert comptes.verifier("essai", "mauvais-mot-de-passe") is None
        assert comptes.verifier("inconnu", "un-mot-de-passe-assez-long") is None
