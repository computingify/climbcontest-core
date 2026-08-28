#!/usr/bin/env python3
"""Mesure le volume reseau echange par l'application juge — critere A12.

    python3 tools/mesurer_volume.py http://127.0.0.1:5007

La spec 003 existe pour faire baisser un chiffre. Tant qu'il n'est pas mesure
apres coup, on n'a rien prouve. Ce script rejoue les deux protocoles contre un
serveur reel et compte les octets qui passent VRAIMENT sur le fil : ligne de
requete, en-tetes, corps, dans les deux sens.

Il ne simule rien. Chaque requete est envoyee ; les reussites sont ecrites en
base. Ne le lancer que contre un serveur de developpement -- il refuse de
demarrer sans URL explicite, comme les scripts de charge.
"""
import json
import ssl
import sys
import urllib.error
import urllib.request
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlparse

VALIDATIONS = 3600          # une competition : ~120 grimpeurs x 30 blocs
LOT = 5                     # PolitiqueEnvoi.LOT_PLEIN


class Compteur:
    """Compte les octets reellement echanges, en-tetes compris."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        u = urlparse(self.base)
        self.hote = u.hostname
        self.port = u.port or (443 if u.scheme == "https" else 80)
        self.https = u.scheme == "https"
        self.envoyes = 0
        self.recus = 0
        self.requetes = 0

    def _connexion(self):
        if self.https:
            return HTTPSConnection(self.hote, self.port,
                                   context=ssl.create_default_context(), timeout=15)
        return HTTPConnection(self.hote, self.port, timeout=15)

    def appeler(self, methode: str, chemin: str, corps=None, entetes=None) -> tuple[int, bytes]:
        entetes = dict(entetes or {})
        donnees = json.dumps(corps).encode() if corps is not None else None
        if donnees is not None:
            entetes["Content-Type"] = "application/json"
            entetes["Content-Length"] = str(len(donnees))
        entetes.setdefault("Host", self.hote)
        entetes.setdefault("User-Agent", "okhttp/5.3.2")
        entetes.setdefault("Accept-Encoding", "gzip")
        entetes.setdefault("Connection", "keep-alive")

        # Taille reelle de la requete sur le fil.
        ligne = f"{methode} {chemin} HTTP/1.1\r\n"
        brut = ligne + "".join(f"{k}: {v}\r\n" for k, v in entetes.items()) + "\r\n"
        self.envoyes += len(brut.encode()) + (len(donnees) if donnees else 0)
        self.requetes += 1

        cx = self._connexion()
        try:
            cx.request(methode, chemin, body=donnees, headers=entetes)
            r = cx.getresponse()
            charge = r.read()
            entetes_reponse = "".join(f"{k}: {v}\r\n" for k, v in r.getheaders())
            self.recus += len(f"HTTP/1.1 {r.status} {r.reason}\r\n".encode())
            self.recus += len(entetes_reponse.encode()) + 2 + len(charge)
            return r.status, charge
        finally:
            cx.close()


def mesurer_ancien(base: str, echantillon: int) -> dict:
    """Le protocole v2 : trois allers-retours BLOQUANTS par validation."""
    c = Compteur(base)
    for i in range(echantillon):
        dossard = str((i % 40) + 1)
        bloc = f"ZJ{(i % 20) + 1}"
        c.appeler("POST", "/api/v2/contest/climber/name", {"id": dossard})
        c.appeler("POST", "/api/v2/contest/bloc/name", {"id": bloc})
        c.appeler("POST", "/api/v2/contest/success", {"bib": dossard, "bloc": bloc})
    return {"requetes": c.requetes, "octets": c.envoyes + c.recus,
            "bloquants": 3 * echantillon}


def mesurer_nouveau(base: str, echantillon: int) -> dict:
    """Le protocole v3 : catalogue une fois, puis des lots. Zero blocage.

    ⚠️ Deux natures de cout, a ne surtout pas melanger :

    - un cout FIXE par journee et par telephone -- le catalogue telecharge au
      demarrage, et les rafraichissements periodiques ;
    - un cout PROPORTIONNEL au nombre de validations -- les lots.

    Extrapoler l'ensemble multiplierait le cout fixe par le facteur
    d'echantillonnage, et flatterait le resultat d'un facteur 18. C'est
    exactement l'erreur commise a la premiere mesure : elle annoncait « divise
    par 4,4 » alors que le vrai chiffre est meilleur, et pour une autre raison.
    """
    # --- Cout FIXE : une fois par journee et par telephone -------------------
    fixe = Compteur(base)
    statut, corps = fixe.appeler("GET", "/api/v2/catalog")
    version = json.loads(corps)["version"] if statut == 200 else 0
    cout_catalogue = fixe.envoyes + fixe.recus

    # Le filet : un 304 toutes les 5 minutes sur une journee de 8 heures.
    for _ in range(12 * 8):
        fixe.appeler("GET", "/api/v2/catalog", entetes={"If-None-Match": f'"{version}"'})

    # --- Cout PROPORTIONNEL : les lots ---------------------------------------
    # Les scans, eux, ne coutent RIEN : ils sont valides sur le telephone.
    lots = Compteur(base)
    envoyes = 0
    while envoyes < echantillon:
        taille = min(LOT, echantillon - envoyes)
        items = [{"ref": f"m{envoyes + j}",
                  "bib": str(((envoyes + j) % 40) + 1),
                  "bloc": f"ZJ{((envoyes + j) % 20) + 1}"}
                 for j in range(taille)]
        lots.appeler("POST", "/api/v3/successes", {"items": items})
        envoyes += taille

    return {
        "requetes_fixes": fixe.requetes,
        "octets_fixes": fixe.envoyes + fixe.recus,
        "requetes_par_lot": lots.requetes,
        "octets_par_lot": lots.envoyes + lots.recus,
        "bloquants": 0,
        "cout_catalogue": cout_catalogue,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        print("ERREUR : donner l'URL explicitement. Jamais la production.")
        return 1
    base = sys.argv[1]
    echantillon = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    print(f"Serveur   : {base}")
    print(f"Mesure sur {echantillon} validations, extrapolee a {VALIDATIONS}.\n")

    ancien = mesurer_ancien(base, echantillon)
    nouveau = mesurer_nouveau(base, echantillon)
    facteur = VALIDATIONS / echantillon

    # Seul le cout proportionnel est extrapole. Le cout fixe est compte une fois.
    v2_req = ancien["requetes"] * facteur
    v2_oct = ancien["octets"] * facteur
    v3_req = nouveau["requetes_fixes"] + nouveau["requetes_par_lot"] * facteur
    v3_oct = nouveau["octets_fixes"] + nouveau["octets_par_lot"] * facteur

    def ligne(nom, a, n):
        print(f"  {nom:<32} {a:>15,.0f} {n:>15,.0f}".replace(",", " "))

    print(f"  {'':<32} {'v2 (aujourd hui)':>15} {'v3 (spec 003)':>15}")
    print("  " + "-" * 66)
    ligne("Requetes HTTP", v2_req, v3_req)
    ligne("Octets sur le fil", v2_oct, v3_oct)
    ligne("Allers-retours BLOQUANTS", ancien["bloquants"] * facteur, 0)
    print()
    print(f"  Requetes  : divisees par {v2_req / max(1, v3_req):.1f}")
    print(f"  Octets    : divises par {v2_oct / max(1, v3_oct):.1f}")
    print(f"  Bloquants : {int(ancien['bloquants'] * facteur)} -> 0")
    print()
    print(f"  Detail du cout v3, par telephone et par journee :")
    print(f"    catalogue complet, une fois : {nouveau['cout_catalogue']:>9,} octets"
          .replace(",", " "))
    print(f"    {nouveau['requetes_fixes'] - 1} rafraichissements 304   : "
          f"{nouveau['octets_fixes'] - nouveau['cout_catalogue']:>9,} octets"
          .replace(",", " "))
    print(f"    les {VALIDATIONS} reussites en lots  : "
          f"{nouveau['octets_par_lot'] * facteur:>9,.0f} octets".replace(",", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
