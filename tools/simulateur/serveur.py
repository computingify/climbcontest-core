"""Le petit serveur local qui sert le panneau et pilote le moteur.

Bibliothèque standard uniquement : `python3 tools/simulateur_juges.py` doit
marcher sur un Mac neuf, sans environnement virtuel et sans `pip install`. Un
outil de test qui demande une installation est un outil qu'on n'utilise pas le
matin de la compétition.

⚠️ **Il n'écoute que sur la boucle locale.** Le panneau porte la clé d'API de la
compétition : l'exposer sur le réseau du gymnase reviendrait à la distribuer.
La clé n'est jamais RENVOYÉE au navigateur — `/api/etat` ne la contient pas, et
le champ du panneau reste vide même quand le simulateur la connaît.

Elle est en revanche **retenue d'une session à l'autre**, hors du dépôt et en
`0600` : voir `memoire.py`, qui explique pourquoi ce n'est pas dans le dépôt
avec une ligne de `.gitignore`.
"""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import asdict
from pathlib import Path

from . import memoire
from .moteur import Reglages, Simulation

PANNEAU = Path(__file__).with_name("panneau.html")


class Poignee(BaseHTTPRequestHandler):
    simulation: Simulation = None      # posé par `lancer`
    protocol_version = "HTTP/1.1"

    # Le journal par défaut recopierait chaque interrogation d'état, une par
    # seconde, et noierait la sortie du terminal.
    def log_message(self, *_):
        pass

    # — GET ————————————————————————————————————————————————————————————

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._html(PANNEAU.read_text(encoding="utf-8"))
        if self.path == "/api/etat":
            return self._json(self.simulation.etat())
        self._code(404, {"message": "inconnu"})

    # — POST ———————————————————————————————————————————————————————————

    def do_POST(self):
        corps = self._corps()
        sim = self.simulation

        if self.path == "/api/connecter":
            resultat = sim.connecter(corps.get("serveur", ""), corps.get("cle", ""))
            if resultat.get("ok"):
                memoire.ecrire(serveur=sim.serveur, cle=sim.api.cle)
            return self._json(resultat)
        if self.path == "/api/demarrer":
            reglages = Reglages.depuis(corps)
            resultat = sim.demarrer(reglages)
            if resultat.get("ok"):
                # Les réglages aussi : retrouver ses curseurs au lancement
                # suivant fait partie du « ne pas ressaisir ».
                memoire.ecrire(reglages=asdict(reglages))
            return self._json(resultat)
        if self.path == "/api/reglages":
            sim.appliquer(Reglages.depuis(corps))
            return self._json({"ok": True})
        if self.path == "/api/pause":
            sim.pause(bool(corps.get("valeur")))
            return self._json({"ok": True})
        if self.path == "/api/arreter":
            sim.arreter()
            return self._json({"ok": True})
        if self.path == "/api/action":
            return self._json(sim.action(corps.get("quoi", "")))
        self._code(404, {"message": "inconnu"})

    # — plomberie ———————————————————————————————————————————————————————

    def _corps(self) -> dict:
        longueur = int(self.headers.get("Content-Length") or 0)
        if not longueur:
            return {}
        try:
            lu = json.loads(self.rfile.read(longueur))
            return lu if isinstance(lu, dict) else {}
        except ValueError:
            return {}

    def _json(self, donnees, code=200):
        self._envoyer(code, json.dumps(donnees, default=str).encode(),
                      "application/json; charset=utf-8")

    def _code(self, code, donnees):
        self._json(donnees, code)

    def _html(self, texte):
        self._envoyer(200, texte.encode("utf-8"), "text/html; charset=utf-8")

    def _envoyer(self, code, brut, type_mime):
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(brut)))
        # Le panneau est relu à chaque rechargement : c'est un outil qu'on
        # modifie en le regardant tourner.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(brut)


def lancer(port: int = 8765, ouvrir: bool = True,
           serveur: str = "", cle: str = "") -> None:
    simulation = Simulation()
    retenu = memoire.lire()

    # La ligne de commande passe AVANT ce qui a été retenu : c'est le seul
    # moyen de viser ponctuellement un autre serveur sans perdre le sien.
    serveur = serveur or retenu.get("serveur", "")
    cle = cle or retenu.get("cle", "")
    if isinstance(retenu.get("reglages"), dict):
        simulation.reglages = Reglages.depuis(retenu["reglages"])

    if serveur:
        # Connexion d'amorçage : le panneau s'ouvre déjà rempli. Un échec ici
        # n'est pas bloquant — le bouton « Connecter » reste là.
        resultat = simulation.connecter(serveur, cle)
        if resultat.get("ok"):
            # ⚠️ Enregistrer ICI aussi, et pas seulement dans la route : viser un
            # serveur par `--url` est précisément la façon dont on le déclare la
            # première fois. Sans cette ligne, il fallait repasser par le
            # bouton « Connecter » pour que quoi que ce soit soit retenu.
            memoire.ecrire(serveur=simulation.serveur, cle=simulation.api.cle)
            cible = simulation.cible()
            print(f"\n  {cible['serveur']} — version {cible['version_serveur'] or '?'}"
                  f"\n  « {cible['competition']} » : {cible['participants']} dossards, "
                  f"{cible['blocs']} blocs")
        else:
            print(f"\n  ⚠ {resultat.get('message')}")

    Poignee.simulation = simulation
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Poignee)
    adresse = f"http://127.0.0.1:{port}"
    print(f"\n  Panneau  : {adresse}")
    print(f"  Retenu   : {memoire.CHEMIN}  (contient la clé — supprimer pour oublier)")
    print("  Ctrl-C pour arrêter.\n")
    if ouvrir:
        threading.Timer(0.5, lambda: webbrowser.open(adresse)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêt.")
        simulation.arreter()
        httpd.shutdown()
