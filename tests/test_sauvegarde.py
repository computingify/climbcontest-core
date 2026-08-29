"""La recopie locale de la base, et sa visibilite (spec 001, revu le 29/08).

La strategie d'origine disait « pendant la journee : rien », en s'appuyant sur
un argument -- le miroir vers le classeur Google donne une redondance gratuite
des donnees du jour.

Le 29/08 on a decouvert que ce miroir etait casse EN SILENCE depuis des heures :
il cherchait le jeton Google au mauvais endroit. La redondance n'etait donc pas
une garantie, c'etait une esperance.

D'ou une recopie locale, qui ne depend de personne -- et surtout d'ou son AGE
expose par /health : une sauvegarde qui s'arrete doit se voir, sinon on ne le
decouvre que le jour ou on en a besoin.
"""
import os
import subprocess
import time
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SCRIPT = RACINE / "deployment" / "climbcontest-sauvegarde"


class TestSonde:
    """Ce que /health doit dire de la sauvegarde."""

    def test_aucune_copie_est_dit_franchement(self, client, app, jeu, tmp_path):
        app.config["DOSSIER_SAUVEGARDES"] = str(tmp_path)
        d = client.get("/health").get_json()["sauvegarde"]
        assert d["copies"] == 0
        assert d["derniere_il_y_a_s"] is None

    def test_l_age_de_la_derniere_est_expose(self, client, app, jeu, tmp_path):
        (tmp_path / "climbcontest-20261115-090000.db").write_bytes(b"x" * 100)
        app.config["DOSSIER_SAUVEGARDES"] = str(tmp_path)

        d = client.get("/health").get_json()["sauvegarde"]

        assert d["copies"] == 1
        assert d["derniere_il_y_a_s"] is not None
        assert d["derniere_il_y_a_s"] < 60
        assert d["derniere_octets"] == 100

    def test_c_est_la_PLUS_RECENTE_qui_compte(self, client, app, jeu, tmp_path):
        """Une copie ancienne qui traine ne doit pas masquer un arret."""
        vieille = tmp_path / "climbcontest-20200101-000000.db"
        vieille.write_bytes(b"x")
        os.utime(vieille, (time.time() - 86400, time.time() - 86400))
        recente = tmp_path / "climbcontest-20261115-090000.db"
        recente.write_bytes(b"x")
        app.config["DOSSIER_SAUVEGARDES"] = str(tmp_path)

        d = client.get("/health").get_json()["sauvegarde"]

        assert d["copies"] == 2
        assert d["derniere_il_y_a_s"] < 60, "l'age doit etre celui de la plus recente"

    def test_un_dossier_absent_ne_fait_pas_tomber_la_sonde(self, client, app, jeu):
        """Ne pas savoir sauvegarder n'est pas la meme chose que ne pas savoir
        servir. La sonde reste verte, elle dit juste qu'il n'y a rien."""
        app.config["DOSSIER_SAUVEGARDES"] = "/dossier/qui/n/existe/pas"
        r = client.get("/health")
        assert r.status_code == 200
        assert r.get_json()["sauvegarde"]["copies"] == 0


@pytest.mark.skipif(not SCRIPT.exists(), reason="script absent")
class TestScript:
    """Le script lui-meme, execute pour de vrai sur une base SQLite."""

    def _base(self, tmp_path):
        base = tmp_path / "climbcontest.db"
        subprocess.run(
            ["sqlite3", str(base),
             "CREATE TABLE success (id INTEGER PRIMARY KEY);"
             "INSERT INTO success (id) VALUES (1),(2),(3);"],
            check=True)
        return base

    def _lancer(self, tmp_path, garder="24"):
        return subprocess.run(
            ["bash", str(SCRIPT)],
            env={**os.environ,
                 "CLIMBCONTEST_DB": str(tmp_path / "climbcontest.db"),
                 "CLIMBCONTEST_SAUVEGARDES": str(tmp_path / "sauvegardes"),
                 "CLIMBCONTEST_SAUVEGARDES_GARDEES": garder},
            capture_output=True, text=True)

    def test_une_copie_est_produite(self, tmp_path):
        self._base(tmp_path)
        r = self._lancer(tmp_path)
        assert r.returncode == 0, r.stderr
        copies = list((tmp_path / "sauvegardes").glob("climbcontest-*.db"))
        assert len(copies) == 1

    def test_la_copie_contient_les_donnees(self, tmp_path):
        """Une sauvegarde qu'on n'a pas relue n'est pas une sauvegarde."""
        self._base(tmp_path)
        self._lancer(tmp_path)
        copie = next((tmp_path / "sauvegardes").glob("climbcontest-*.db"))
        lu = subprocess.run(["sqlite3", str(copie), "SELECT COUNT(*) FROM success;"],
                            capture_output=True, text=True)
        assert lu.stdout.strip() == "3"

    def test_le_compte_de_reussites_est_annonce(self, tmp_path):
        self._base(tmp_path)
        r = self._lancer(tmp_path)
        assert "3 reussites" in r.stdout

    def test_aucun_fichier_partiel_ne_traine(self, tmp_path):
        """Une copie interrompue ne doit pas avoir l'air valide."""
        self._base(tmp_path)
        self._lancer(tmp_path)
        assert not list((tmp_path / "sauvegardes").glob("*.partiel"))

    def test_la_rotation_garde_le_nombre_demande(self, tmp_path):
        self._base(tmp_path)
        for _ in range(4):
            self._lancer(tmp_path, garder="2")
            time.sleep(1.05)          # l'horodatage est a la seconde
        copies = list((tmp_path / "sauvegardes").glob("climbcontest-*.db"))
        assert len(copies) == 2, f"{len(copies)} copies conservees"

    def test_ce_sont_les_PLUS_RECENTES_qui_restent(self, tmp_path):
        self._base(tmp_path)
        noms = []
        for _ in range(3):
            self._lancer(tmp_path, garder="1")
            time.sleep(1.05)
            noms += [f.name for f in (tmp_path / "sauvegardes").glob("climbcontest-*.db")]
        restante = next((tmp_path / "sauvegardes").glob("climbcontest-*.db")).name
        assert restante == max(noms), "la plus recente doit survivre"

    def test_sans_base_le_script_ne_plante_pas(self, tmp_path):
        """Avant le premier demarrage, il n'y a rien a sauvegarder."""
        r = self._lancer(tmp_path)
        assert r.returncode == 0
        assert "pas de base" in r.stderr

    def test_la_base_reste_utilisable_pendant(self, tmp_path):
        """`.backup` ne bloque pas les ecritures : un juge doit pouvoir valider
        pendant qu'une sauvegarde tourne."""
        base = self._base(tmp_path)
        self._lancer(tmp_path)
        ecriture = subprocess.run(
            ["sqlite3", str(base), "INSERT INTO success (id) VALUES (99);"],
            capture_output=True, text=True)
        assert ecriture.returncode == 0, ecriture.stderr
