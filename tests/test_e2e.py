"""Tests de bout en bout : un vrai serveur, du vrai HTTP, une vraie base.

Les autres tests utilisent le client Flask et une base en mémoire — rapides,
mais ils court-circuitent gunicorn, le pool de connexions, les threads et le
fichier sur disque. Or c'est **là** que vivent les défauts qui font perdre des
réussites un jour de compétition.

Ici : gunicorn est lancé pour de vrai, avec plusieurs workers, sur un port
libre, contre une base fichier temporaire. On lui parle en HTTP comme le fait
l'application juge.

Ce que ces tests garantissent :

- le contrat de l'application `v3.1.4` tient **sous gunicorn**, pas seulement
  dans le client de test ;
- une réussite **survit à un redémarrage complet du serveur** ;
- l'idempotence tient sous concurrence réelle, répartie sur plusieurs workers ;
- la base n'est jamais effacée au démarrage, quel que soit le nombre de workers.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def appeler(base: str, chemin: str, corps: dict | None = None, methode: str = "POST"):
    """Un appel HTTP, comme le ferait l'application. Renvoie (code, json)."""
    donnees = json.dumps(corps).encode() if corps is not None else None
    requete = urllib.request.Request(
        f"{base}{chemin}", data=donnees, method=methode,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=15) as r:
            texte = r.read().decode()
            return r.status, (json.loads(texte) if texte else None)
    except urllib.error.HTTPError as e:
        texte = e.read().decode()
        return e.code, (json.loads(texte) if texte else None)


class ServeurReel:
    """Un gunicorn lancé pour de vrai, arrêté proprement à la fin."""

    def __init__(self, dossier: Path, workers: int = 3):
        self.dossier = dossier
        self.workers = workers
        self.port = port_libre()
        self.base = f"http://127.0.0.1:{self.port}"
        self.processus: subprocess.Popen | None = None

    def demarrer(self) -> None:
        env = {
            **os.environ,
            "CLIMBCONTEST_DATA_DIR": str(self.dossier),
            "CLIMBCONTEST_SHEETS_ACTIF": "0",     # aucun acces reseau
            "CLIMBCONTEST_API_KEY": "cle-e2e",
            "PYTHONPATH": str(RACINE),
        }
        env.pop("CLIMBCONTEST_TEST", None)        # on veut la vraie config
        self.processus = subprocess.Popen(
            [sys.executable, "-m", "gunicorn",
             "--workers", str(self.workers), "--threads", "4",
             "--worker-class", "gthread",
             "--bind", f"127.0.0.1:{self.port}",
             "--log-level", "error", "wsgi:app"],
            cwd=RACINE, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        limite = time.monotonic() + 30
        while time.monotonic() < limite:
            if self.processus.poll() is not None:
                erreur = self.processus.stderr.read().decode()[-800:]
                raise RuntimeError(f"gunicorn n'a pas demarre :\n{erreur}")
            try:
                code, _ = appeler(self.base, "/health", methode="GET")
                if code == 200:
                    return
            except Exception:
                time.sleep(0.3)
        raise RuntimeError("gunicorn n'a pas repondu en 30 s")

    def arreter(self) -> None:
        if self.processus and self.processus.poll() is None:
            self.processus.terminate()
            try:
                self.processus.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.processus.kill()
                self.processus.wait(timeout=5)

    def __enter__(self):
        self.demarrer()
        return self

    def __exit__(self, *_):
        self.arreter()


def peupler(dossier: Path) -> None:
    """Crée une compétition minimale, hors serveur."""
    env = {**os.environ, "CLIMBCONTEST_DATA_DIR": str(dossier),
           "CLIMBCONTEST_SHEETS_ACTIF": "0", "PYTHONPATH": str(RACINE)}
    env.pop("CLIMBCONTEST_TEST", None)
    code = """
from climbcontest import creer_app
from climbcontest.extensions import db
from climbcontest.models import Competition, Participant, Bloc, Circuit, BlocCircuit, EN_COURS
app = creer_app()
with app.app_context():
    c = Competition(nom="E2E", statut=EN_COURS, active=True, spreadsheet_id="x")
    db.session.add(c); db.session.commit()
    circuit = Circuit(competition_id=c.id, nom="U11")
    db.session.add(circuit); db.session.flush()
    for i in range(1, 21):
        b = Bloc(competition_id=c.id, tag=f"B{i}", numero=i, zone="Z", couleur="Jaune")
        db.session.add(b); db.session.flush()
        db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=circuit.id))
    for i in range(1, 41):
        db.session.add(Participant(competition_id=c.id, nom=f"Nom{i}", prenom=f"Prenom{i}",
                                   club="Club", categorie="U11 F", dossard=i, present=True))
    db.session.commit()
"""
    r = subprocess.run([sys.executable, "-c", code], cwd=RACINE, env=env,
                       capture_output=True, timeout=90)
    if r.returncode:
        raise RuntimeError(f"peuplement echoue :\n{r.stderr.decode()[-800:]}")


@pytest.fixture()
def dossier():
    d = Path(tempfile.mkdtemp(prefix="climbcontest-e2e-"))
    peupler(d)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def serveur(dossier):
    with ServeurReel(dossier) as s:
        yield s


# --- Le contrat de l'application, sous gunicorn -----------------------------

class TestParcoursDuJuge:
    def test_scan_scan_envoi(self, serveur):
        """Le geste complet : deux scans, un envoi."""
        code, corps = appeler(serveur.base, "/api/v2/contest/climber/name", {"id": "12"})
        assert code == 201 and corps["success"] is True
        assert corps["id"] == "Nom12 Prenom12"      # le NOM, pas le dossard

        code, corps = appeler(serveur.base, "/api/v2/contest/bloc/name", {"id": "B3"})
        assert code == 201 and corps["id"] == "B3"

        code, corps = appeler(serveur.base, "/api/v2/contest/success",
                              {"bib": "12", "bloc": "B3"})
        assert code == 201 and corps["success"] is True

    def test_dossard_inconnu(self, serveur):
        code, corps = appeler(serveur.base, "/api/v2/contest/climber/name", {"id": "999"})
        assert code == 400 and corps["success"] is False

    def test_double_appui_sur_envoyer(self, serveur):
        """Ne doit jamais ressembler à une erreur, sinon le juge recommence."""
        for _ in range(3):
            code, corps = appeler(serveur.base, "/api/v2/contest/success",
                                  {"bib": "5", "bloc": "B1"})
            assert code == 201 and corps["success"] is True
        _, sante = appeler(serveur.base, "/health", methode="GET")
        assert sante["reussites_en_attente"] == 1


# --- Ce qui faisait perdre des donnees --------------------------------------

class TestSurvieAuRedemarrage:
    def test_les_reussites_survivent(self, dossier):
        """Risque R2 : la file en RAM disparaissait au redémarrage.

        Le test qui compte : on écrit, on **tue le serveur**, on le relance, et
        on vérifie que tout est là. Aucun test en mémoire ne peut le montrer.
        """
        with ServeurReel(dossier) as s:
            for dossard in range(1, 26):
                code, _ = appeler(s.base, "/api/v2/contest/success",
                                  {"bib": str(dossard), "bloc": "B1"})
                assert code == 201
            _, avant = appeler(s.base, "/health", methode="GET")
            assert avant["reussites_en_attente"] == 25

        # serveur arrete, processus termines, tout est relance a neuf
        with ServeurReel(dossier) as s:
            _, apres = appeler(s.base, "/health", methode="GET")
            assert apres["reussites_en_attente"] == 25, \
                "des reussites ont disparu au redemarrage"

    def test_la_base_n_est_pas_effacee_au_demarrage(self, dossier):
        """Risque R1 : `drop_all()` s'exécutait dans chaque worker."""
        with ServeurReel(dossier, workers=4) as s:
            appeler(s.base, "/api/v2/contest/success", {"bib": "1", "bloc": "B1"})

        for _ in range(3):
            with ServeurReel(dossier, workers=4) as s:
                code, corps = appeler(s.base, "/api/v2/contest/climber/name", {"id": "1"})
                assert code == 201, "la base a ete effacee au demarrage"
                _, sante = appeler(s.base, "/health", methode="GET")
                assert sante["reussites_en_attente"] == 1


class TestConcurrence:
    def test_meme_couple_depuis_20_requetes_simultanees(self, serveur):
        """Deux juges qui valident le même passage, ou un double appui.

        Réparti sur 3 workers : la garantie ne peut pas venir d'un verrou en
        mémoire, seulement de la contrainte d'unicité en base.
        """
        codes, verrou = [], threading.Lock()

        def envoyer():
            code, _ = appeler(serveur.base, "/api/v2/contest/success",
                              {"bib": "7", "bloc": "B2"})
            with verrou:
                codes.append(code)

        fils = [threading.Thread(target=envoyer) for _ in range(20)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()

        assert codes == [201] * 20, f"toutes doivent reussir, obtenu {set(codes)}"
        _, sante = appeler(serveur.base, "/health", methode="GET")
        assert sante["reussites_en_attente"] == 1, "une seule reussite doit exister"

    def test_couples_distincts_en_parallele(self, serveur):
        """40 réussites distinctes envoyées en même temps : aucune perdue."""
        def envoyer(i):
            appeler(serveur.base, "/api/v2/contest/success",
                    {"bib": str((i % 40) + 1), "bloc": f"B{(i % 20) + 1}"})

        fils = [threading.Thread(target=envoyer, args=(i,)) for i in range(40)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()

        _, sante = appeler(serveur.base, "/health", methode="GET")
        assert sante["reussites_en_attente"] == 40


# --- Le catalogue -----------------------------------------------------------

class TestCatalogue:
    def test_contenu_et_version(self, serveur):
        code, corps = appeler(serveur.base, "/api/v2/catalog", methode="GET")
        assert code == 200
        assert len(corps["participants"]) == 40
        assert len(corps["blocs"]) == 20
        assert corps["version"] >= 1

    def test_304_quand_rien_ne_bouge(self, serveur):
        _, corps = appeler(serveur.base, "/api/v2/catalog", methode="GET")
        code, _ = appeler(serveur.base,
                          f"/api/v2/catalog?depuis={corps['version']}", methode="GET")
        assert code == 304

    def test_les_blocs_portent_leur_circuit(self, serveur):
        _, corps = appeler(serveur.base, "/api/v2/catalog", methode="GET")
        assert all(b["circuits"] == ["U11"] for b in corps["blocs"])


# --- La cle d'API -----------------------------------------------------------

class TestCleApi:
    def test_absente_acceptee(self, serveur):
        """Mode toléré : l'application v3.1.4 n'envoie aucune clé.

        Les trois routes du juge doivent répondre sans clé, sinon l'application
        déployée cesse de fonctionner.
        """
        for chemin, corps in [
            ("/api/v2/contest/climber/name", {"id": "1"}),
            ("/api/v2/contest/bloc/name", {"id": "B1"}),
            ("/api/v2/contest/success", {"bib": "1", "bloc": "B1"}),
        ]:
            code, reponse = appeler(serveur.base, chemin, corps)
            assert code == 201, f"{chemin} refuse sans cle : l'app v3.1.4 casserait"
            assert reponse["success"] is True

    def test_le_compteur_est_par_worker_et_le_dit(self, serveur):
        """Le compteur de /health ne vaut que pour le worker qui a répondu.

        C'est une limite assumée, mais elle doit être **annoncée** : lue comme
        un total, elle ferait activer le mode strict à tort. La mesure agrégée
        est dans le journal.
        """
        appeler(serveur.base, "/api/v2/catalog", methode="GET")
        _, sante = appeler(serveur.base, "/health", methode="GET")
        assert sante["api"]["portee"] == "ce worker seulement"
        assert isinstance(sante["api"]["pid"], int)

    def test_compteur_fiable_avec_un_seul_worker(self, dossier):
        """Avec un worker, le compteur est exact — c'est le cas du dev."""
        with ServeurReel(dossier, workers=1) as s:
            appeler(s.base, "/api/v2/contest/climber/name", {"id": "1"})
            appeler(s.base, "/api/v2/contest/climber/name", {"id": "2"})
            _, sante = appeler(s.base, "/health", methode="GET")
            assert sante["api"]["sans_cle"] >= 2

    def test_bonne_cle_acceptee(self, serveur):
        requete = urllib.request.Request(
            f"{serveur.base}/api/v2/catalog", method="GET",
            headers={"X-Api-Key": "cle-e2e"},
        )
        with urllib.request.urlopen(requete, timeout=10) as r:
            assert r.status == 200

    def test_fausse_cle_refusee(self, serveur):
        requete = urllib.request.Request(
            f"{serveur.base}/api/v2/catalog", method="GET",
            headers={"X-Api-Key": "pas-la-bonne"},
        )
        try:
            urllib.request.urlopen(requete, timeout=10)
            pytest.fail("une fausse cle doit etre refusee")
        except urllib.error.HTTPError as e:
            assert e.code == 401


# --- La sonde ---------------------------------------------------------------

class TestSante:
    def test_ne_depend_d_aucun_service_externe(self, serveur):
        """Le classeur est désactivé ici : /health doit répondre quand même.

        Une sonde qui tombe parce qu'un tiers est lent déclencherait des retours
        arrière de déploiement et des alertes pour rien.
        """
        code, corps = appeler(serveur.base, "/health", methode="GET")
        assert code == 200 and corps["status"] == "ok"
        assert "reussites_en_attente" in corps
