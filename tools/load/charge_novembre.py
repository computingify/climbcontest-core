"""Banc de charge du scénario de novembre 2026 — à lancer sur un serveur LOCAL.

⚠️ JAMAIS contre la production. Le banc démarre son propre gunicorn (4 workers,
comme la VM) sur une base temporaire, miroir Sheets coupé.

Deux scénarios, dans l'ordre où la journée les produit :

1. **Régime de croisière** : 25 juges envoient des petits lots au fil de l'eau,
   30 spectateurs consultent le classement, la page projetée se rafraîchit.
2. **Rafale de reprise** : le wifi vient de revenir, les 25 téléphones vident
   leur file EN MÊME TEMPS (25 lots de 50).

À la fin, l'intégrité est vérifiée en base : chaque réussite envoyée y est,
exactement une fois.

Usage :
    python3 tools/load/charge_novembre.py
"""
import json
import os
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
CLE = "cle-de-charge"
JUGES = 25
SPECTATEURS = 30
DUREE_CROISIERE_S = 45


# --------------------------------------------------------------------------- outillage
def port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Mesures:
    """p50/p95/p99 par famille de requête, thread-safe."""

    def __init__(self):
        self.verrou = threading.Lock()
        self.durees = {}
        self.erreurs = {}

    def noter(self, famille, duree_s, ok):
        with self.verrou:
            self.durees.setdefault(famille, []).append(duree_s * 1000)
            if not ok:
                self.erreurs[famille] = self.erreurs.get(famille, 0) + 1

    def rapport(self):
        lignes = []
        for famille, valeurs in sorted(self.durees.items()):
            valeurs = sorted(valeurs)
            def pct(p):
                return valeurs[min(len(valeurs) - 1, int(p / 100 * len(valeurs)))]
            lignes.append({
                "famille": famille, "n": len(valeurs),
                "erreurs": self.erreurs.get(famille, 0),
                "p50_ms": round(pct(50), 1), "p95_ms": round(pct(95), 1),
                "p99_ms": round(pct(99), 1), "max_ms": round(max(valeurs), 1),
                "moy_ms": round(statistics.mean(valeurs), 1),
            })
        return lignes


def appeler(base, chemin, corps=None, cle=None, mesures=None, famille=None):
    donnees = json.dumps(corps).encode() if corps is not None else None
    entetes = {"Content-Type": "application/json"}
    if cle:
        entetes["X-Api-Key"] = cle
    requete = urllib.request.Request(
        f"{base}{chemin}", data=donnees,
        method="POST" if corps is not None else "GET", headers=entetes)
    debut = time.monotonic()
    ok, reponse = False, None
    try:
        with urllib.request.urlopen(requete, timeout=30) as r:
            reponse = json.load(r)
            ok = 200 <= r.status < 300
    except Exception:
        pass
    if mesures:
        mesures.noter(famille, time.monotonic() - debut, ok)
    return ok, reponse


# --------------------------------------------------------------------------- montage
def peupler(dossier):
    env = {**os.environ, "CLIMBCONTEST_DATA_DIR": str(dossier),
           "CLIMBCONTEST_SHEETS_ACTIF": "0", "PYTHONPATH": str(RACINE)}
    env.pop("CLIMBCONTEST_TEST", None)
    code = """
from climbcontest import creer_app
from climbcontest.extensions import db
from climbcontest.models import Competition, Participant, Bloc, Circuit, BlocCircuit, EN_COURS
app = creer_app()
with app.app_context():
    c = Competition(nom="Charge novembre", statut=EN_COURS, active=True, spreadsheet_id=None)
    db.session.add(c); db.session.commit()
    circuit = Circuit(competition_id=c.id, nom="U11")
    db.session.add(circuit); db.session.flush()
    for i in range(1, 31):
        b = Bloc(competition_id=c.id, tag=f"B{i}", numero=i, zone="Z", couleur="Jaune")
        db.session.add(b); db.session.flush()
        db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=circuit.id))
    for i in range(1, 121):
        db.session.add(Participant(competition_id=c.id, nom=f"Nom{i}", prenom=f"P{i}",
                                   club="Club", categorie="U11 F", dossard=i, present=True))
    db.session.commit()
"""
    r = subprocess.run([sys.executable, "-c", code], cwd=RACINE, env=env,
                       capture_output=True, timeout=90)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-600:])


def main():
    dossier = Path(tempfile.mkdtemp(prefix="climbcontest-charge-"))
    peupler(dossier)
    port = port_libre()
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "CLIMBCONTEST_DATA_DIR": str(dossier),
           "CLIMBCONTEST_SHEETS_ACTIF": "0", "CLIMBCONTEST_API_KEY": CLE,
           "PYTHONPATH": str(RACINE)}
    env.pop("CLIMBCONTEST_TEST", None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "gunicorn", "--workers", "4", "--threads", "4",
         "--worker-class", "gthread", "--bind", f"127.0.0.1:{port}", "wsgi:app"],
        cwd=RACINE, env=env,
        stdout=subprocess.DEVNULL, stderr=open(dossier / "gunicorn.log", "w"))
    try:
        limite = time.monotonic() + 30
        while True:
            ok, d = appeler(base, "/health")
            if ok and d.get("status") == "ok":
                break
            if time.monotonic() > limite:
                raise RuntimeError("serveur jamais pret")
            time.sleep(0.5)

        mesures = Mesures()
        compteur = {"envoyees": 0}
        verrou = threading.Lock()
        arret = threading.Event()

        # ----------------------------------------------- 1. régime de croisière
        import random

        def juge(n):
            rng = random.Random(n)
            serie = 0
            while not arret.is_set():
                taille = rng.randint(1, 5)
                elements = []
                for _ in range(taille):
                    serie += 1
                    elements.append({"ref": f"j{n}-{serie}",
                                     "bib": str(rng.randint(1, 120)),
                                     "bloc": f"B{rng.randint(1, 30)}"})
                ok, d = appeler(base, "/api/v3/successes",
                                {"appareil": {"id": f"tel-{n}", "nom": f"Juge {n}"},
                                 "items": elements},
                                cle=CLE, mesures=mesures, famille="lot v3 (juge)")
                if ok:
                    # Le serveur repond un verdict PAR element : c'est lui qui
                    # fait foi. « enregistree » = une ligne de plus en base ;
                    # un doublon (meme grimpeur, meme bloc) est absorbe.
                    with verrou:
                        compteur["envoyees"] += sum(
                            1 for r in d.get("resultats", [])
                            if r.get("etat") == "enregistree")
                # un juge valide toutes les 10 a 30 secondes ; l'attente est
                # raccourcie d'un facteur 10 pour comprimer une heure en minutes
                if arret.wait(rng.uniform(1.0, 3.0)):
                    return

        def spectateur(n):
            rng = random.Random(1000 + n)
            while not arret.is_set():
                appeler(base, "/api/public/classement",
                        mesures=mesures, famille="classement (public)")
                if arret.wait(rng.uniform(0.5, 2.0)):
                    return

        def catalogue():
            while not arret.is_set():
                appeler(base, "/api/v2/catalog", cle=CLE,
                        mesures=mesures, famille="catalogue (juge)")
                if arret.wait(2.0):
                    return

        fils = ([threading.Thread(target=juge, args=(n,)) for n in range(JUGES)]
                + [threading.Thread(target=spectateur, args=(n,)) for n in range(SPECTATEURS)]
                + [threading.Thread(target=catalogue)])
        debut = time.monotonic()
        for f in fils:
            f.start()
        time.sleep(DUREE_CROISIERE_S)
        arret.set()
        for f in fils:
            f.join()
        duree1 = time.monotonic() - debut

        # ----------------------------------------------- 2. rafale de reprise
        rafale_mesures = Mesures()

        def vider_file(n):
            elements = [{"ref": f"rafale-{n}-{i}",
                         "bib": str((n * 50 + i) % 120 + 1),
                         "bloc": f"B{i % 30 + 1}"} for i in range(50)]
            ok, d = appeler(base, "/api/v3/successes",
                            {"appareil": {"id": f"tel-{n}", "nom": f"Juge {n}"},
                             "items": elements},
                            cle=CLE, mesures=rafale_mesures, famille="rafale 25x50")
            if ok:
                with verrou:
                    compteur["envoyees"] += sum(
                        1 for r in d.get("resultats", [])
                        if r.get("etat") == "enregistree")

        fils = [threading.Thread(target=vider_file, args=(n,)) for n in range(JUGES)]
        debut = time.monotonic()
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        duree2 = time.monotonic() - debut

        # ----------------------------------------------- 3. intégrité
        import sqlite3
        con = sqlite3.connect(dossier / "climbcontest.db")
        en_base = con.execute("SELECT COUNT(*) FROM success").fetchone()[0]
        doublons = con.execute(
            "SELECT COUNT(*) FROM (SELECT participant_id, bloc_id FROM success "
            "GROUP BY participant_id, bloc_id HAVING COUNT(*) > 1)").fetchone()[0]
        con.close()

        print(f"\n=== croisière : {JUGES} juges + {SPECTATEURS} spectateurs, {duree1:.0f}s ===")
        for l in mesures.rapport():
            print(f"  {l['famille']:22s} n={l['n']:4d} err={l['erreurs']:2d} "
                  f"p50={l['p50_ms']:6.1f}ms p95={l['p95_ms']:7.1f}ms "
                  f"p99={l['p99_ms']:7.1f}ms max={l['max_ms']:7.1f}ms")
        print(f"\n=== rafale : {JUGES} lots de 50 d'un coup, {duree2:.1f}s ===")
        for l in rafale_mesures.rapport():
            print(f"  {l['famille']:22s} n={l['n']:4d} err={l['erreurs']:2d} "
                  f"p50={l['p50_ms']:6.1f}ms p95={l['p95_ms']:7.1f}ms max={l['max_ms']:7.1f}ms")
        print(f"\n=== intégrité ===")
        print(f"  « enregistrée » reçues : {compteur['envoyees']}")
        print(f"  en base                : {en_base} (doublons : {doublons})")
        verdict = "OK" if en_base == compteur["envoyees"] and doublons == 0 else "ECART !"
        print(f"  verdict            : {verdict}")
        return 0 if verdict == "OK" else 1
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
