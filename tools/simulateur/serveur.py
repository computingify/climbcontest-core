"""Le petit serveur local qui sert le panneau et pilote le moteur.

Bibliothèque standard uniquement : `python3 tools/simulateur_juges.py` doit
marcher sur un Mac neuf, sans environnement virtuel et sans `pip install`. Un
outil de test qui demande une installation est un outil qu'on n'utilise pas le
matin de la compétition.

⚠️ **Il n'écoute que sur la boucle locale.** Le panneau porte la clé d'API de la
compétition : l'exposer sur le réseau du gymnase reviendrait à la distribuer.
La clé n'est d'ailleurs jamais écrite sur le disque ni renvoyée par `/api/etat`
— elle vit en mémoire, le temps de la session.
"""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
            return self._json(sim.connecter(corps.get("serveur", ""),
                                            corps.get("cle", "")))
        if self.path == "/api/demarrer":
            return self._json(sim.demarrer(Reglages.depuis(corps)))
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
    if serveur:
        # Connexion d'amorçage : le panneau s'ouvre déjà rempli. Un échec ici
        # n'est pas bloquant — le bouton « Connecter » reste là.
        resultat = simulation.connecter(serveur, cle)
        if not resultat.get("ok"):
            print(f"  ⚠ {resultat.get('message')}")

    Poignee.simulation = simulation
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Poignee)
    adresse = f"http://127.0.0.1:{port}"
    print(f"\n  Panneau : {adresse}\n  Ctrl-C pour arrêter.\n")
    if ouvrir:
        threading.Timer(0.5, lambda: webbrowser.open(adresse)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêt.")
        simulation.arreter()
        httpd.shutdown()
