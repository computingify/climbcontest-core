"""Mise à jour du serveur depuis la console (spec 031).

Ce qui est vérifié ici tient en une phrase : **la console ne doit interroger
GitHub qu'une fois par jour, et ne doit jamais installer pendant une
compétition.**

Le reste — télécharger, vérifier l'empreinte, sonder `/health`, revenir en
arrière — appartient à `climbcontest-deploy`, qui n'est pas du Python et n'est
pas testé ici. Ce module ne fait que décider et déléguer.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
import requests

from climbcontest import comptes, maj
from climbcontest.extensions import db
from climbcontest.models import PREPARATION, Competition, Reglage

MDP = "un-mot-de-passe-assez-long"


class FausseReponse:
    def __init__(self, corps=None, status=200, entetes=None):
        self._corps = corps or {}
        self.status_code = status
        self.headers = entetes or {}

    def json(self):
        return self._corps

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def release(tag="v0.17.0", corps="### Corrigé\n\n- Une chose."):
    return FausseReponse({
        "tag_name": tag,
        "body": corps,
        "published_at": "2026-09-03T09:05:00Z",
    })


@pytest.fixture()
def github(monkeypatch):
    """Remplace l'appel à GitHub et COMPTE les requêtes.

    Le compte est le cœur du sujet : c'est un minuteur qui en faisait trente par
    heure qui a motivé cette spec.
    """
    appels = []

    def faux_get(url, **kwargs):
        appels.append(url)
        return faux_get.reponse

    faux_get.reponse = release()
    monkeypatch.setattr(maj.requests, "get", faux_get)
    faux_get.appels = appels
    return faux_get


@pytest.fixture()
def sans_competition(app):
    """Aucune compétition active : rien ne bloque l'installation."""
    return app


@pytest.fixture()
def secret(app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    return app


@pytest.fixture()
def connecte(client, secret):
    comptes.creer("chef", MDP, [comptes.ADMIN])
    client.post("/admin/connexion", json={"identifiant": "chef", "mot_de_passe": MDP})
    return client


@pytest.fixture()
def organisateur(client, secret):
    comptes.creer("benevole", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "benevole", "mot_de_passe": MDP})
    return client


class TestCadence:
    """Une vérification par jour, pas une par chargement de page."""

    def test_la_premiere_consultation_interroge_github(self, sans_competition, github):
        maj.etat("v0.16.0")
        assert len(github.appels) == 1

    def test_les_suivantes_ne_l_interrogent_pas(self, sans_competition, github):
        maj.etat("v0.16.0")
        maj.etat("v0.16.0")
        maj.etat("v0.16.0")
        assert len(github.appels) == 1

    def test_le_lendemain_elle_l_interroge_de_nouveau(self, sans_competition, github):
        maj.etat("v0.16.0")
        veille = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
        stocke = maj._charger(maj.CLE_VERIFICATION)
        maj._ecrire(maj.CLE_VERIFICATION, {**stocke, "fait_le": veille})
        maj.etat("v0.16.0")
        assert len(github.appels) == 2

    def test_le_bouton_verifier_force_l_appel(self, sans_competition, github):
        maj.etat("v0.16.0")
        maj.verifier(force=True)
        assert len(github.appels) == 2

    def test_l_horodatage_est_pose_avant_l_appel(self, sans_competition, monkeypatch):
        """Deux workers qui démarrent ensemble ne doivent pas partir tous les deux.

        On le vérifie en regardant l'état de la base PENDANT l'appel : si
        `fait_le` n'y est pas encore, le worker suivant croirait la
        vérification due.
        """
        vu = {}

        def faux_get(url, **kwargs):
            vu["fait_le"] = maj._charger(maj.CLE_VERIFICATION).get("fait_le")
            return release()

        monkeypatch.setattr(maj.requests, "get", faux_get)
        maj.etat("v0.16.0")
        assert vu["fait_le"], "l'horodatage doit etre ecrit avant l'appel reseau"


class TestCeQueLaConsoleLit:

    def test_meme_version_egale_a_jour(self, sans_competition, github):
        github.reponse = release(tag="v0.16.0")
        etat = maj.etat("v0.16.0")
        assert etat["disponible"] is None
        assert etat["erreur"] is None

    def test_version_plus_recente_avec_son_changelog(self, sans_competition, github):
        etat = maj.etat("v0.16.0")
        assert etat["disponible"]["tag"] == "v0.17.0"
        assert "Corrigé" in etat["disponible"]["changelog"]

    def test_le_quota_est_nomme(self, sans_competition, github):
        github.reponse = FausseReponse({}, status=403, entetes={"x-ratelimit-remaining": "0"})
        etat = maj.etat("v0.16.0")
        assert "quota" in etat["erreur"].lower()

    def test_github_muet_ne_perd_pas_ce_qu_on_savait(self, sans_competition, github):
        """Une version trouvée hier l'est toujours aujourd'hui."""
        maj.etat("v0.16.0")
        stocke = maj._charger(maj.CLE_VERIFICATION)
        veille = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(timespec="seconds")
        maj._ecrire(maj.CLE_VERIFICATION, {**stocke, "fait_le": veille})

        github.reponse = FausseReponse({}, status=403, entetes={"x-ratelimit-remaining": "0"})
        etat = maj.etat("v0.16.0")
        assert etat["erreur"]
        assert etat["disponible"]["tag"] == "v0.17.0"


@pytest.fixture
def demande(tmp_path, monkeypatch):
    """Le fichier que la console dépose pour réclamer une installation.

    ⚠️ Ces tests remplaçaient `subprocess.run` par un leurre. Ils prouvaient
    qu'on appelait `sudo` — la seule chose qui, en production, ne pouvait pas
    marcher (voir `test_deploiement_sans_privileges.py`). On exerce maintenant
    le vrai mécanisme sur un vrai dossier.
    """
    monkeypatch.setenv("CLIMBCONTEST_BASE", str(tmp_path))
    return tmp_path / "shared" / maj.NOM_DEMANDE


class TestCompetitionEnCours:
    """Le seul vrai risque de ce bouton : redémarrer pendant les scans."""

    def test_une_competition_en_cours_bloque(self, competition, github):
        etat = maj.etat("v0.16.0")
        assert etat["blocage"] and "bloqu" in etat["blocage"].lower()

    def test_installer_est_refuse(self, competition, github, demande):
        maj.etat("v0.16.0")
        with pytest.raises(maj.ErreurMaj):
            maj.installer("v0.17.0")
        assert not demande.exists(), "aucun deploiement ne doit partir"

    def test_une_competition_en_preparation_ne_bloque_pas(self, app, github):
        db.session.add(Competition(nom="Novembre", statut=PREPARATION, active=True))
        db.session.commit()
        assert maj.etat("v0.16.0")["blocage"] is None


class TestInstallation:

    def test_elle_depose_une_demande_sans_attendre(self, sans_competition, github, demande):
        """Elle n'attend pas : l'agent redémarre l'application, c'est-à-dire le
        processus qui traite cette requête."""
        maj.etat("v0.16.0")
        maj.installer("v0.17.0", par="chef")
        assert demande.exists(), "la demande doit etre deposee"
        corps = json.loads(demande.read_text(encoding="utf-8"))
        assert corps["tag"] == "v0.17.0"
        assert corps["par"] == "chef"

    def test_un_second_clic_reecrit_le_fichier(self, sans_competition, github, demande):
        """`climbcontest-deploy.path` écoute les MODIFICATIONS.

        Un fichier simplement laissé en place ne redéclencherait rien : le
        bouton ne marcherait qu'une fois, et le second clic n'aurait aucun
        effet visible.
        """
        maj.etat("v0.16.0")
        maj.installer("v0.17.0", par="chef")
        premier = demande.stat().st_mtime_ns
        demande.write_text("{}", encoding="utf-8")   # comme si l'agent avait lu
        maj.installer("v0.17.0", par="chef")
        assert demande.stat().st_mtime_ns != premier
        assert json.loads(demande.read_text(encoding="utf-8"))["tag"] == "v0.17.0"

    def test_une_ecriture_impossible_est_annoncee(self, sans_competition, github,
                                                  tmp_path, monkeypatch):
        """Sur la VM, `shared/` est le seul chemin accessible en écriture.

        Le jour où il ne l'est plus, la console doit le dire — pas repartir
        « en cours » sur un déploiement que personne n'a demandé.
        """
        monkeypatch.setenv("CLIMBCONTEST_BASE", str(tmp_path))
        (tmp_path / "shared").mkdir()
        (tmp_path / "shared").chmod(0o500)
        maj.etat("v0.16.0")
        try:
            with pytest.raises(maj.ErreurMaj) as leve:
                maj.installer("v0.17.0")
        finally:
            (tmp_path / "shared").chmod(0o700)
        assert leve.value.code == 500

    def test_une_version_perimee_a_l_ecran_est_refusee(self, sans_competition, github, demande):
        maj.etat("v0.16.0")
        with pytest.raises(maj.ErreurMaj):
            maj.installer("v0.14.0")

    def test_l_issue_n_est_annoncee_que_le_temps_de_la_lire(self, sans_competition, github,
                                                            demande):
        """Sinon « v0.17.0 installée » resterait à l'écran des semaines."""
        maj.etat("v0.16.0")
        maj.installer("v0.17.0")
        assert maj.etat("v0.17.0")["installation"]["etat"] == "reussie"

        vieux = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
        maj._ecrire(maj.CLE_INSTALLATION, {"tag": "v0.17.0", "demandee_le": vieux})
        assert maj.etat("v0.17.0")["installation"] is None


class TestPortesFermees:
    """Les trois routes sont réservées aux administrateurs."""

    def test_sans_session(self, client, secret):
        # `secret` pose la SECRET_KEY : sans elle, TOUTE l'administration repond
        # 503 « desactivee » et ce test ne prouverait rien sur l'authentification.
        assert client.get("/admin/maj").status_code == 401

    def test_organisateur_refuse(self, organisateur):
        assert organisateur.get("/admin/maj").status_code == 403

    def test_organisateur_ne_peut_pas_installer(self, organisateur):
        assert organisateur.post("/admin/maj/installer", json={}).status_code == 403

    def test_admin_lit(self, connecte, github):
        reponse = connecte.get("/admin/maj")
        assert reponse.status_code == 200
        assert reponse.get_json()["success"] is True

    def test_installer_pendant_une_competition_repond_409(self, connecte, competition, github):
        connecte.get("/admin/maj")
        reponse = connecte.post("/admin/maj/installer", json={"tag": "v0.17.0"})
        assert reponse.status_code == 409


def test_la_cle_de_verification_est_bien_rangee_en_base(sans_competition, github):
    """En base et non dans un fichier : `climbcontest-sauvegarde` ne recopie que
    la base, un JSON posé à côté serait le seul fichier sans sauvegarde."""
    maj.etat("v0.16.0")
    assert db.session.get(Reglage, maj.CLE_VERIFICATION) is not None
