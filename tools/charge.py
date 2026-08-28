#!/usr/bin/env python3
"""Test de charge ClimbContest — simule une compétition réelle.

Le point critique n'est PAS le débit : c'est que **tout le monde partage une
seule adresse IP publique**, celle du NAT de la salle. 25 juges et plus de
100 spectateurs derrière une seule adresse, c'est exactement le profil qu'un
système de détection d'intrusion prend pour une attaque.

Ce script doit donc être lancé depuis **une seule machine hors du LAN** — le
partage de connexion d'un téléphone en 4G fait très bien l'affaire.

    python3 tools/charge.py --url https://climbcontest.adn-dev.fr \\
            --juges 25 --spectateurs 80 --duree 600

Après le test, vérifier qu'aucune adresse n'a été bannie :

    ssh root@192.168.0.21 "pct exec 101 -- cscli decisions list"
    ssh root@192.168.0.21 "pct exec 101 -- cscli alerts list"

⚠️ Ce script ne fait que LIRE. Il n'écrit aucune réussite : les routes d'écriture
demandent une clé d'API et n'existent pas encore (spec 002). C'est volontaire —
les anciens scripts de charge (`tools/load/`) écrivaient réellement dans le
classeur de la compétition, ce qui est le risque R11 de l'état des lieux.
"""

import argparse
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

arret = threading.Event()
verrou = threading.Lock()
latences: list[float] = []
codes: Counter = Counter()


def appel(url: str, timeout: float = 10.0) -> None:
    debut = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            code = r.status
            r.read()
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # réseau, TLS, timeout
        code = type(e).__name__
    duree = time.monotonic() - debut
    with verrou:
        codes[code] += 1
        if isinstance(code, int):
            latences.append(duree)


def juge(base: str, pause: float) -> None:
    """Un juge valide un passage toutes les `pause` secondes.

    Tant que l'API d'écriture n'existe pas, on simule le rythme sur la page
    d'accueil : ce qu'on mesure ici, c'est la réaction de CrowdSec et de Caddy
    à un trafic soutenu venant d'une seule adresse, pas le backend.
    """
    while not arret.is_set():
        appel(f"{base}/")
        arret.wait(pause)


def spectateur(base: str, pause: float) -> None:
    """Un spectateur rafraîchit le classement toutes les `pause` secondes."""
    while not arret.is_set():
        appel(f"{base}/")
        arret.wait(pause)


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--url", required=True)
    a.add_argument("--juges", type=int, default=25)
    a.add_argument("--spectateurs", type=int, default=80)
    a.add_argument("--duree", type=int, default=600, help="secondes")
    a.add_argument("--pause-juge", type=float, default=45.0)
    a.add_argument("--pause-spectateur", type=float, default=15.0)
    o = a.parse_args()
    base = o.url.rstrip("/")

    attendu = o.juges * 60 / o.pause_juge + o.spectateurs * 60 / o.pause_spectateur
    print(f"Cible          : {base}")
    print(f"Population     : {o.juges} juges + {o.spectateurs} spectateurs")
    print(f"Débit attendu  : ~{attendu:.0f} requêtes/minute, depuis UNE seule adresse")
    print(f"Durée          : {o.duree}s\n")

    fils = [threading.Thread(target=juge, args=(base, o.pause_juge), daemon=True)
            for _ in range(o.juges)]
    fils += [threading.Thread(target=spectateur, args=(base, o.pause_spectateur), daemon=True)
             for _ in range(o.spectateurs)]

    debut = time.monotonic()
    for f in fils:
        f.start()
        time.sleep(0.02)  # démarrage étalé, pas un mur de connexions

    try:
        while time.monotonic() - debut < o.duree:
            time.sleep(15)
            with verrou:
                total = sum(codes.values())
                med = statistics.median(latences) if latences else 0
            ecoule = time.monotonic() - debut
            print(f"  {ecoule:5.0f}s  {total:6d} requêtes  "
                  f"{total / ecoule * 60:6.0f}/min  médiane {med * 1000:5.0f} ms  {dict(codes)}")
    except KeyboardInterrupt:
        print("\ninterrompu")
    finally:
        arret.set()

    ecoule = time.monotonic() - debut
    with verrou:
        total = sum(codes.values())
        ok = sum(v for k, v in codes.items() if isinstance(k, int) and k < 400)
        tri = sorted(latences)
    print(f"\n{'=' * 62}")
    print(f"Requêtes        : {total} en {ecoule:.0f}s ({total / ecoule * 60:.0f}/min)")
    print(f"Réussies        : {ok} ({ok / total * 100:.2f} %)" if total else "aucune requête")
    if tri:
        print(f"Latence médiane : {statistics.median(tri) * 1000:.0f} ms")
        print(f"Latence p95     : {tri[int(len(tri) * 0.95)] * 1000:.0f} ms")
        print(f"Latence max     : {tri[-1] * 1000:.0f} ms")
    print(f"Codes           : {dict(codes)}")
    print(f"{'=' * 62}")
    print("\nÀ vérifier maintenant, c'est le vrai résultat du test :")
    print("  ssh root@192.168.0.21 \"pct exec 101 -- cscli decisions list\"   # doit être vide")
    print("  ssh root@192.168.0.21 \"pct exec 101 -- cscli alerts list\"      # aucun débordement")


if __name__ == "__main__":
    main()
