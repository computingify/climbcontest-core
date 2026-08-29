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
import sqlite3
from datetime import datetime, timedelta
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
    """Un port que le noyau vient de nous donner.

    Il est libre a cet instant, pas forcement une milliseconde plus tard : entre
    la fermeture de cette socket et le `bind` de gunicorn, un autre processus
    peut le prendre. On ne peut pas fermer cette fenetre depuis ici, alors
    [ServeurReel.demarrer] la rattrape en reessayant sur un autre port.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class PortDejaPris(RuntimeError):
    """Le port choisi a ete pris entre son attribution et le `bind` de gunicorn."""


#: La cle que `ServeurReel` configure. Les appels la portent par defaut, comme
#: l'application des juges depuis la spec 012 -- le regime par defaut du serveur
#: etant desormais STRICT, un appel sans cle serait refuse.
CLE_E2E = "cle-e2e"


def appeler(base: str, chemin: str, corps: dict | None = None,
            methode: str = "POST", cle: str | None = CLE_E2E):
    """Un appel HTTP, comme le ferait l'application. Renvoie (code, json).

    `cle=None` omet l'en-tete : c'est ce que fait le gel `V3.1.4`, et c'est ce
    qu'il faut pour verifier qu'une route est bien fermee.
    """
    donnees = json.dumps(corps).encode() if corps is not None else None
    entetes = {"Content-Type": "application/json"}
    if cle is not None:
        entetes["X-Api-Key"] = cle
    requete = urllib.request.Request(
        f"{base}{chemin}", data=donnees, method=methode, headers=entetes,
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

    def __init__(self, dossier: Path, workers: int = 3, env_sup: dict | None = None,
                 sante_attendue: int = 200):
        self.dossier = dossier
        self.workers = workers
        self.env_sup = env_sup or {}
        # Ce que `/health` doit repondre pour qu'on considere le serveur pret.
        #
        # 200 par defaut, et c'est important : plusieurs tests supposent qu'a la
        # sortie de cette attente, le schema est pret et la base interrogeable.
        # Accepter 503 « pour que le processus reponde » a fait passer le test
        # du verrou orphelin AVANT que le schema ne soit prepare -- il est
        # tombe, et il avait raison.
        #
        # Un test qui veut observer une configuration MAUVAISE le dit ici.
        self.sante_attendue = sante_attendue
        self.port = port_libre()
        self.base = f"http://127.0.0.1:{self.port}"
        self.processus: subprocess.Popen | None = None
        # Le journal va dans un FICHIER, pas un tube. Un tube que personne ne
        # draine se remplit (64 ko sur macOS) et bloque gunicorn en ecriture ;
        # et `stderr.read()` attend l'EOF, qu'un worker orphelin peut retenir
        # indefiniment. Le fichier permet aussi de VERIFIER ce qui est journalise.
        self.journal = dossier / f"gunicorn-{self.port}.log"

    def demarrer(self, essais: int = 3) -> None:
        """Lance gunicorn, en reessayant si le port a ete pris entre-temps."""
        for essai in range(essais):
            try:
                self._demarrer_une_fois()
                return
            except PortDejaPris:
                if essai == essais - 1:
                    raise
                self.port = port_libre()
                self.base = f"http://127.0.0.1:{self.port}"
                self.journal = self.journal.with_name(f"gunicorn-{self.port}.log")

    def _demarrer_une_fois(self) -> None:
        env = {
            **os.environ,
            "CLIMBCONTEST_DATA_DIR": str(self.dossier),
            "CLIMBCONTEST_SHEETS_ACTIF": "0",     # aucun acces reseau
            "CLIMBCONTEST_API_KEY": "cle-e2e",
            "PYTHONPATH": str(RACINE),
            **self.env_sup,
        }
        env.pop("CLIMBCONTEST_TEST", None)        # on veut la vraie config
        self.sortie = open(self.journal, "w")
        self.processus = subprocess.Popen(
            [sys.executable, "-m", "gunicorn",
             "--workers", str(self.workers), "--threads", "4",
             "--worker-class", "gthread",
             "--bind", f"127.0.0.1:{self.port}",
             "wsgi:app"],
            cwd=RACINE, env=env,
            stdout=subprocess.DEVNULL, stderr=self.sortie,
        )
        limite = time.monotonic() + 30
        while time.monotonic() < limite:
            if self.processus.poll() is not None:
                journal = self.lire_journal()
                # Distingue « le port a ete pris sous nos pieds », qu'on sait
                # rattraper, d'une vraie panne de demarrage, qu'il faut montrer.
                if "Address already in use" in journal or "in use" in journal.lower():
                    self.arreter()
                    raise PortDejaPris(self.port)
                raise RuntimeError(f"gunicorn n'a pas demarre :\n{journal[-800:]}")
            try:
                code, _ = appeler(self.base, "/health", methode="GET")
                if code == self.sante_attendue:
                    return
            except Exception:
                pass
            # On dort TOUJOURS : sans ca, un /health qui repond autre chose que
            # 200 ferait tourner cette boucle a 100 % de CPU pendant 30 s --
            # empechant precisement le serveur de finir de demarrer.
            time.sleep(0.3)
        raise RuntimeError("gunicorn n'a pas repondu en 30 s")

    def lire_journal(self) -> str:
        try:
            return self.journal.read_text(errors="replace")
        except OSError:
            return ""

    def arreter(self) -> None:
        if self.processus and self.processus.poll() is None:
            self.processus.terminate()
            try:
                self.processus.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.processus.kill()
                self.processus.wait(timeout=5)
        sortie = getattr(self, "sortie", None)
        if sortie and not sortie.closed:
            sortie.close()

    def __enter__(self):
        # Si demarrer() leve, le `with` n'est jamais entre, donc __exit__ n'est
        # jamais appele : le gunicorn resterait vivant, gardant le port et la
        # base d'un dossier temporaire que la fixture va supprimer sous ses
        # pieds. Sur une machine chargee, chaque test lent laisserait un serveur
        # orphelin, qui ferait expirer le suivant.
        try:
            self.demarrer()
        except Exception:
            self.arreter()
            raise
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


class TestLotSousGunicorn:
    """La route de lot, sur un vrai serveur multi-processus.

    Les tests unitaires du lot tournent dans un seul processus avec une base en
    memoire : ils ne peuvent rien dire de la concurrence reelle. Ici, quatre
    workers se disputent la meme base SQLite.
    """

    def test_un_lot_simple_passe(self, serveur):
        code, corps = appeler(serveur.base, "/api/v3/successes", {"items": [
            {"ref": "a", "bib": "1", "bloc": "B1"},
            {"ref": "b", "bib": "1", "bloc": "B2"},
            {"ref": "c", "bib": "2", "bloc": "B3"},
        ]})
        assert code == 200, corps
        assert [r["etat"] for r in corps["resultats"]] == ["enregistree"] * 3
        _, sante = appeler(serveur.base, "/health", methode="GET")
        assert sante["reussites_en_attente"] == 3

    def test_le_meme_lot_envoye_dix_fois_en_parallele(self, serveur):
        """Le cas du reseau qui hoquette : le telephone reessaie sans savoir
        si le premier envoi est passe. Dix envois, trois reussites en base.

        C'est la garantie qui rend la file d'attente sure : reessayer est
        gratuit. Elle ne peut venir que de la contrainte d'unicite en base --
        un verrou en memoire ne verrait qu'un worker sur quatre.
        """
        lot = {"items": [
            {"ref": "a", "bib": "5", "bloc": "B1"},
            {"ref": "b", "bib": "5", "bloc": "B2"},
            {"ref": "c", "bib": "5", "bloc": "B3"},
        ]}
        codes, verrou = [], threading.Lock()

        def envoyer():
            code, _ = appeler(serveur.base, "/api/v3/successes", lot)
            with verrou:
                codes.append(code)

        fils = [threading.Thread(target=envoyer) for _ in range(10)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()

        assert codes == [200] * 10, f"aucun envoi ne doit echouer, obtenu {set(codes)}"
        _, sante = appeler(serveur.base, "/health", methode="GET")
        assert sante["reussites_en_attente"] == 3, "trois reussites, pas trente"

    def test_dix_lots_distincts_en_parallele(self, serveur):
        """50 reussites reparties en 10 lots simultanes : aucune perdue."""
        def envoyer(i):
            appeler(serveur.base, "/api/v3/successes", {"items": [
                {"ref": f"{i}-{j}", "bib": str(i + 1), "bloc": f"B{j + 1}"}
                for j in range(5)
            ]})

        fils = [threading.Thread(target=envoyer, args=(i,)) for i in range(10)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()

        _, sante = appeler(serveur.base, "/health", methode="GET")
        assert sante["reussites_en_attente"] == 50

    def test_un_lot_mixte_n_echoue_pas_en_bloc(self, serveur):
        code, corps = appeler(serveur.base, "/api/v3/successes", {"items": [
            {"ref": "a", "bib": "9", "bloc": "B1"},
            {"ref": "b", "bib": "9999", "bloc": "B1"},
            {"ref": "c", "bib": "9", "bloc": "B2"},
        ]})
        assert code == 200
        assert [r["etat"] for r in corps["resultats"]] == \
            ["enregistree", "refusee", "enregistree"]

    def test_un_corps_malforme_donne_400_pas_500(self, serveur):
        """Sous gunicorn aussi : un 500 se lirait comme une panne a reessayer."""
        for corps in ([1, 2], "x", 42):
            code, _ = appeler(serveur.base, "/api/v3/successes", corps)
            assert code == 400, f"corps {corps!r} -> {code}"


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
    def test_absente_refusee_par_defaut(self, serveur):
        """Le regime par defaut est STRICT depuis la spec 012.

        Sur un gunicorn reel, sans aucune variable de regime : les trois routes
        du juge refusent une requete sans cle. C'est le coeur de la spec, et
        c'est le seul test qui le verifie sur le vrai serveur.
        """
        for chemin, corps in [
            ("/api/v2/contest/climber/name", {"id": "1"}),
            ("/api/v2/contest/bloc/name", {"id": "B1"}),
            ("/api/v2/contest/success", {"bib": "1", "bloc": "B1"}),
        ]:
            code, _ = appeler(serveur.base, chemin, corps, cle=None)
            assert code == 401, f"{chemin} devrait etre ferme sans cle"

    def test_absente_acceptee_en_mode_tolere(self, dossier):
        """La porte de sortie du plan de repli.

        Le gel `V3.1.4` n'envoie aucune cle. Poser
        `CLIMBCONTEST_API_KEY_STRICTE=0` doit le faire remarcher, sinon le repli
        de novembre ne repliera rien.
        """
        with ServeurReel(dossier, workers=1,
                         env_sup={"CLIMBCONTEST_API_KEY_STRICTE": "0"}) as s:
            for chemin, corps in [
                ("/api/v2/contest/climber/name", {"id": "1"}),
                ("/api/v2/contest/bloc/name", {"id": "B1"}),
                ("/api/v2/contest/success", {"bib": "1", "bloc": "B1"}),
            ]:
                code, reponse = appeler(s.base, chemin, corps, cle=None)
                assert code == 201, f"{chemin} refuse : le repli V3.1.4 casserait"
                assert reponse["success"] is True

    def test_strict_sans_aucune_cle_configuree_donne_503(self, dossier):
        """Une erreur de CONFIGURATION doit se lire comme telle, pas comme un 401."""
        with ServeurReel(dossier, workers=1,
                         env_sup={"CLIMBCONTEST_API_KEY": ""},
                         sante_attendue=503) as s:
            code, reponse = appeler(s.base, "/api/v2/contest/climber/name",
                                    {"id": "1"}, cle=None)
            assert code == 503
            assert "CLIMBCONTEST_API_KEY" in reponse["message"]

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
        with ServeurReel(dossier, workers=1,
                         env_sup={"CLIMBCONTEST_API_KEY_STRICTE": "0"}) as s:
            appeler(s.base, "/api/v2/contest/climber/name", {"id": "1"}, cle=None)
            appeler(s.base, "/api/v2/contest/climber/name", {"id": "2"}, cle=None)
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


# --- Le garde-fou du mode strict --------------------------------------------

class TestModeStrictEtSonGardeFou:
    """Le mode strict, et la trace qu'il laisse.

    Il est le defaut depuis la spec 012. Le journal reste indispensable, mais il
    ne sert plus a decider du passage : il sert a REPERER, le jour J, un
    telephone reste sur l'ancienne application et dont les envois sont refuses.
    """

    def test_le_journal_recoit_bien_les_appels_sans_cle(self, serveur):
        """Le test qui manquait, et son absence était dangereuse.

        `auth.py` et le runbook décident du passage en mode strict sur :

            journalctl -u climbcontest --since today | grep -c "appel sans cle"

        Cette ligne ne sortait nulle part : le logger racine est à WARNING sans
        handler, et le service ne passe ni --log-level ni --capture-output. La
        commande renvoyait 0 quoi qu'il arrive.

        ⚠️ Un test avec `caplog` passerait alors que la production reste muette :
        caplog installe son propre handler et force le niveau. Seul un vrai
        gunicorn, dont on lit la sortie, prouve quelque chose.
        """
        for _ in range(3):
            appeler(serveur.base, "/api/v2/contest/climber/name", {"id": "1"},
                    cle=None)
        time.sleep(0.5)
        journal = serveur.lire_journal()
        assert journal.count("appel sans cle") >= 3, (
            "le journal ne recoit pas les appels sans cle : la commande du "
            "runbook renverrait 0 et ferait activer le mode strict a tort.\n"
            f"journal :\n{journal[-600:]}")

    def test_le_mode_strict_refuse_les_routes_du_juge(self, dossier):
        """Ce que fait l'interrupteur, écrit noir sur blanc.

        Ce test ne dit pas que c'est bien : il dit que **c'est ça**. Tant que
        l'application v3.1.4 est en service, poser
        CLIMBCONTEST_API_KEY_STRICTE=1 arrête la compétition.
        """
        with ServeurReel(dossier, workers=1,
                         env_sup={"CLIMBCONTEST_API_KEY_STRICTE": "1"}) as s:
            for chemin, corps in [
                ("/api/v2/contest/climber/name", {"id": "1"}),
                ("/api/v2/contest/bloc/name", {"id": "B1"}),
                ("/api/v2/contest/success", {"bib": "1", "bloc": "B1"}),
            ]:
                code, _ = appeler(s.base, chemin, corps, cle=None)
                assert code == 401, f"{chemin} devrait etre refuse en mode strict"

    def test_le_mode_strict_accepte_avec_la_cle(self, dossier):
        with ServeurReel(dossier, workers=1,
                         env_sup={"CLIMBCONTEST_API_KEY_STRICTE": "1"}) as s:
            requete = urllib.request.Request(
                f"{s.base}/api/v2/contest/climber/name",
                data=json.dumps({"id": "1"}).encode(), method="POST",
                headers={"Content-Type": "application/json", "X-Api-Key": "cle-e2e"},
            )
            with urllib.request.urlopen(requete, timeout=10) as r:
                assert r.status == 201

    def test_fausse_cle_refusee_sur_les_routes_du_juge(self, serveur):
        """Le comportement NOUVEAU de cette branche, jusqu'ici non couvert :
        le decorateur sur les trois routes gelees."""
        requete = urllib.request.Request(
            f"{serveur.base}/api/v2/contest/success",
            data=json.dumps({"bib": "1", "bloc": "B1"}).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Api-Key": "fausse"},
        )
        try:
            urllib.request.urlopen(requete, timeout=10)
            pytest.fail("une fausse cle doit etre refusee, meme en mode tolere")
        except urllib.error.HTTPError as e:
            assert e.code == 401


# --- Le banc de test lui-meme -----------------------------------------------

class TestBancDeTest:
    """Le harnais doit etre fiable, sinon ses verdicts ne valent rien.

    Un test E2E qui echoue une fois sur vingt pour une raison qui ne concerne
    pas le produit finit par etre relance sans etre lu -- et le jour ou il
    signale un vrai defaut, personne ne le croit.
    """

    def test_reprend_un_autre_port_si_le_sien_est_pris(self, tmp_path):
        serveur = ServeurReel(tmp_path, workers=1)
        # On simule exactement la course : le noyau nous a donne un port, et
        # quelqu'un le prend avant que gunicorn ne s'y attache.
        squatteur = socket.socket()
        squatteur.bind(("127.0.0.1", serveur.port))
        squatteur.listen(1)
        port_pris = serveur.port
        try:
            serveur.demarrer()
            assert serveur.port != port_pris, "le serveur devait changer de port"
            code, _ = appeler(serveur.base, "/health", methode="GET")
            assert code == 200
        finally:
            serveur.arreter()
            squatteur.close()


class TestVerrouOrphelinAuRedemarrage:
    """Le pire scenario du verrou, celui que le TTL seul n'attrape jamais.

    L'unite systemd relance le service **5 s** apres un plantage
    (`RestartSec=5s`). Un verrou laisse par un worker tue a donc toujours moins
    de 60 s au redemarrage : il n'est jamais considere comme perime, personne ne
    le vole, et les quatre nouveaux workers servaient avec une base vide --
    pendant que `/health` repondait 200 « ok » et que l'agent de deploiement
    validait la mise en production.

    C'est exactement le chemin que prend une VM qui perd le courant en pleine
    competition.
    """

    def _poser_verrou_frais(self, dossier: Path) -> None:
        """Une base qui ne contient QUE la table verrou, avec un verrou d'il y a 5 s."""
        base = dossier / "climbcontest.db"
        if base.exists():
            base.unlink()
        cx = sqlite3.connect(base)
        cx.execute("CREATE TABLE verrou (nom TEXT PRIMARY KEY,"
                   " detenu_par TEXT, pris_le TIMESTAMP)")
        cx.execute("INSERT INTO verrou VALUES ('schema', 'mort:99999', ?)",
                   (str(datetime.now() - timedelta(seconds=5)),))
        cx.commit()
        cx.close()

    def test_le_serveur_prepare_le_schema_au_lieu_de_servir_une_base_vide(self, tmp_path):
        self._poser_verrou_frais(tmp_path)

        with ServeurReel(tmp_path, workers=4) as s:
            code, sante = appeler(s.base, "/health", methode="GET")
            assert code == 200, f"/health devait remonter, obtenu {code} : {sante}"
            assert sante["status"] == "ok"

            # La preuve qui compte : une vraie requete de juge, pas la sonde.
            code, _ = appeler(s.base, "/api/v2/contest/climber/name", {"id": "1"})
            assert code != 500, "le schema n'a pas ete prepare : la base est vide"

        # Le verrou a bien ete rendu, sinon le prochain demarrage rejouerait tout.
        cx = sqlite3.connect(tmp_path / "climbcontest.db")
        restant = cx.execute("SELECT * FROM verrou WHERE nom = 'schema'").fetchall()
        tables = {r[0] for r in cx.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        cx.close()
        assert restant == [], "le verrou doit etre libere"
        assert "competition" in tables, "les tables doivent avoir ete creees"


# --- Le demarrage a froid ---------------------------------------------------

class TestDemarrageAFroid:
    def test_base_vide_quatre_workers_repondent_proprement(self, dossier):
        """Quatre workers, base vide : personne ne doit voir d'erreur SQL.

        Toutes les autres fixtures peuplent la base **avant** de lancer
        gunicorn ; ici elle est vide au démarrage, avec quatre workers qui se
        disputent la préparation du schéma.

        Ce que ce test ne fait **pas**, contrairement à ce que sa version
        précédente prétendait : courir après le détenteur du verrou. Le harnais
        sonde `/health` jusqu'à obtenir 200 avant de rendre la main, donc la
        préparation est finie depuis longtemps quand la requête part. Il n'y a
        pas de « première requête immédiate ».

        Ce qu'il vaut quand même : depuis que `/health` interroge la base et
        répond **503** quand elle est inutilisable, cette attente n'est plus une
        formalité — c'est l'assertion que le serveur ne se déclare pas prêt
        avant que le schéma le soit. La vraie course, elle, est couverte par
        [TestVerrouOrphelinAuRedemarrage], qui la provoque au lieu de l'espérer.
        """
        vide = dossier / "vide"
        vide.mkdir()
        with ServeurReel(vide, workers=4) as s:
            # Pas de competition : on attend un 409 propre, jamais un 500 ni
            # une erreur SQL sur une table absente.
            code, corps = appeler(s.base, "/api/v2/contest/climber/name", {"id": "1"})
            assert code == 409, f"attendu 409, obtenu {code} : {corps}"
            code, _ = appeler(s.base, "/health", methode="GET")
            assert code == 200


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
