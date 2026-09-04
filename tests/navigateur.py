"""Piloter un vrai navigateur, sans les trois pièges qui coûtent une heure.

Deux fichiers de tests s'en servent. Ils ne partagent pas un « utilitaire » par
goût de la factorisation : ils partagent **trois corrections** qui ont chacune
été payées, et qu'on ne veut pas repayer dans un troisième fichier.

**1. `--virtual-time-budget` ne marche pas partout.** Il accélère les
minuteries avec le shell headless de Playwright et **pas** avec un chromium
complet — celui de `ubuntu-latest`, donc celui de la CI. Là-bas le temps
virtuel n'accélère rien, `--dump-dom` attend une page qui n'a jamais fini, et
le processus expire au bout de deux minutes sans rien dire. Pire : même quand
il marche, il fait courir les minuteries **plus vite que le réseau**, si bien
qu'une attente de huit secondes virtuelles expire avant qu'une requête réelle
soit revenue. Le verdict remonte donc par un `fetch`, et le test tue le
navigateur dès qu'il l'a reçu.

**2. `contentDocument` rend d'abord le `about:blank` initial**, dont le
`readyState` vaut déjà « complete ». Attendre cet état seul ne prouve donc
rien ; on demande **aussi** que l'adresse ne soit plus `about:blank`. Et on
relit `contentDocument` à **chaque** accès — la référence prise avant la
navigation pointe ensuite sur un document mort.

Ce qu'on n'attend **plus** : « le document contient plus de vingt éléments ».
C'était un pari sur la vitesse de l'analyseur. `admin.html` fait 1600 lignes,
`#connexion` est à la 850ᵉ et `#console` à la 889ᵉ : une sonde qui attendait le
premier lisait `null` sur le second dès que le runner ralentissait, et rendait
un échec qui n'accusait personne.

**3. `app.run` dans un fil démon survit au test** et garde son port, ce qui
fait échouer sans rapport apparent le premier test suivant qui démarre un vrai
serveur. `make_server`, et `shutdown()` dans un `finally`.

**4. Un chromium par pilotage, c'était payer un démarrage à chaque parcours.**
Mesuré : 0,3 s à chaud, **7,2 s au premier lancement** d'un runner. Passer les
fixtures en portée module a ramené le compte à un démarrage par FICHIER — il en
restait six. Ici on descend à **un pour toute la session** : le navigateur est
lancé une fois, et chaque pilotage ouvre un *contexte* isolé (mesuré : **2 à
5 ms**) au lieu d'un processus.

⚠️ « Isolé » n'est pas une facilité de langage, et c'est ce qui rend le partage
légitime : `Target.createBrowserContext` donne à chaque parcours ses propres
cookies, son `localStorage`, ses service workers — exactement ce que garantit
un profil neuf, sans en payer le prix. Sans ça, un test qui range un thème dans
`localStorage` le ferait lire par le suivant, et le partage n'aurait plus rien
de gratuit.

Le pilotage passe donc par CDP, en **bibliothèque standard seulement** : une
poignée d'octets de WebSocket écrits à la main plutôt qu'une dépendance de test
de plus. Le verdict, lui, continue de remonter par un `fetch` vers
l'application — rien de ce que les tests observent ne change.
"""
import atexit
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request
import warnings
from pathlib import Path

def _playwright():
    """Les binaires Playwright installes, quel que soit leur numero de build.

    ⚠️ Ce chemin a longtemps ete FIGE sur `chromium_headless_shell-1234`. Le
    jour ou Playwright passe au build suivant, un chemin en dur ne trouve plus
    rien, et les tests **se sautent en silence** : plus personne ne protege le
    branchement, et rien ne le dit. Le motif vient de
    `test_navigateur_fiche.py`, qui l'avait deja ; il est ici pour que les deux
    ne divergent plus.
    """
    racine = Path.home() / "Library/Caches/ms-playwright"
    return sorted(racine.glob("chromium*/chrome-*/chrome-headless-shell")) + \
        sorted(racine.glob("chromium*/chrome-*/Chromium")) + \
        sorted(racine.glob("chromium*/chrome-*/Google Chrome for Testing"))


def trouver_chrome():
    candidats = [os.environ.get("CLIMBCONTEST_CHROME", "")]
    candidats += [str(c) for c in _playwright()]
    candidats += [
        # `ubuntu-latest` le FOURNIT : ces tests tournent sur la CI, ils ne s'y
        # sautent pas.
        "/usr/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
    ]
    for chemin in candidats:
        if not chemin:
            continue
        if os.path.isfile(chemin) and os.access(chemin, os.X_OK):
            return chemin
        trouve = shutil.which(chemin)
        if trouve:
            return trouve
    return None


CHROME = trouver_chrome()

# L'entête de tout pilote : les outils d'attente, et le renvoi du verdict.
# Le corps propre à chaque test vient après, et dispose de `$`, `$$` et `vue()`.
PREAMBULE = r"""
const etapes = [];
const note = (n, v) => etapes.push(n + "=" + String(v).replace(/[ |]/g, "_"));
const rendre = (v) => fetch("/__verdict", { method: "POST", body: v });
function attendre(quoi, cond, ms = 15000) {
  return new Promise((ok, ko) => {
    const t0 = Date.now();
    (function b() {
      let r; try { r = cond(); } catch (e) { r = false; }
      if (r) {
        // Une attente qui a vraiment attendu le DIT, et le verdict la porte.
        // Sans ca, un test instantane sur le Mac et long sur un runner ne
        // nomme jamais ce qu'il attendait -- c'est ce qui a coute deux
        // passages de CI pour trouver le battement de la page de resultats.
        const duree = Date.now() - t0;
        if (duree > 500) note("attente_" + quoi.replace(/[ |]/g, "_"), duree);
        return ok(r);
      }
      if (Date.now() - t0 > ms) return ko(new Error("delai sur " + quoi));
      setTimeout(b, 50);
    })();
  });
}
(async function () {
  try {
    const cadre = document.getElementById("page");
    const $ = (s) => cadre.contentDocument.querySelector(s);
    const $$ = (s) => [...cadre.contentDocument.querySelectorAll(s)];
    const vue = () => cadre.contentWindow;
    // ⚠️ « Le document est-il FINI ? », pas « y a-t-il deja du monde
    // dedans ? ». Le compte d'elements etait un pari sur la vitesse de
    // l'analyseur : `admin.html` fait 1600 lignes, `#connexion` est a la 850e
    // et `#console` a la 889e -- sur un runner charge, une sonde qui attend le
    // premier lisait `null` sur le second et rendait un ECHEC qui n'accusait
    // personne. `readyState` seul ne suffit pas non plus : le `about:blank`
    // initial vaut deja « complete », d'ou la question sur l'adresse.
    await attendre("vraie page", () => {
      const doc = cadre.contentDocument, fen = cadre.contentWindow;
      return doc && fen && fen.location.href !== "about:blank"
          && doc.readyState === "complete";
    });

    // ⚠️ « La page a-t-elle FINI de reagir ? », et non « ai-je attendu assez
    // longtemps ? ». Une sonde qui veut constater qu'il ne s'est RIEN passe
    // n'a rien a observer -- alors elle dormait. `rejeu_archive` dormait
    // 1200 ms, deux fois : 2,4 s de la suite, et un pari perdant sur un runner
    // lent, ou la feuille se serait ouverte a 1300 ms sans que le test la
    // voie. Un sommeil trop court rend VERT ce qu'il devrait attraper.
    //
    // `calme()` attend ce qui est observable : que plus aucune requete ne soit
    // en vol, puis deux rafraichissements d'ecran -- de quoi laisser passer un
    // gestionnaire de clic et sa transition. Il rend la main en une trentaine
    // de millisecondes quand il ne s'est rien passe, et attend VRAIMENT quand
    // il se passe quelque chose.
    let _enVol = 0, _fenetreSuivie = null;
    function _suivreLesRequetes() {
      const fen = cadre.contentWindow;
      if (fen === _fenetreSuivie) return fen;
      // Page rechargee : le compteur de l'ancienne ne veut plus rien dire, et
      // ses requetes en vol ne redescendront jamais a zero.
      _enVol = 0;
      _fenetreSuivie = fen;
      const dorigine = fen.fetch;
      fen.fetch = function (...args) {
        _enVol++;
        return dorigine.apply(this, args).finally(() => { _enVol--; });
      };
      return fen;
    }
    _suivreLesRequetes();
    const calme = async (quoi = "que la page ait fini de reagir") => {
      const fen = _suivreLesRequetes();
      await attendre(quoi, () => _enVol === 0, 10000);
      await new Promise((r) => fen.requestAnimationFrame(
          () => fen.requestAnimationFrame(r)));
    };
"""

EPILOGUE = r"""
    rendre("OK " + etapes.join(" "));
  } catch (e) { rendre("ECHEC " + etapes.join(" ") + " || " + e.message); }
})();
"""


def pilote(corps: str) -> str:
    """Le script complet, à poser dans la page du harnais."""
    return PREAMBULE + corps + EPILOGUE


def port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# La taille du cadre par défaut : un téléphone. C'est la page de résultats et
# la PWA juge qui s'y regardent, et c'est là qu'elles sont vraiment lues.
TELEPHONE = (390, 844)


def page_harnais(src: str, corps: str, taille=TELEPHONE) -> str:
    """Le harnais : la page à tester dans un cadre, et le pilote au-dessus.

    Servi par l'application elle-même : le pilote doit être en MÊME ORIGINE que
    la page pour la lire, et on ne veut aucun crochet de test dans le livré.

    ⚠️ `taille` n'est pas un détail de confort. Une règle sous
    `@media (min-width: 1080px)` n'existe tout simplement pas dans un cadre de
    390 px — et c'est exactement une règle de ce genre qui a rendu la console
    visible sans session. Un test doit pouvoir demander un ÉCRAN.
    """
    largeur, hauteur = taille
    return ("<!doctype html><meta charset=utf-8><title>harnais</title>"
            "<style>html,body{margin:0}</style>"
            f"<iframe id=page src='{src}' "
            f"style='width:{largeur}px;height:{hauteur}px;border:0'></iframe>"
            f"<script>{pilote(corps)}</script>")


def servir(app):
    """Un vrai serveur HTTP, arrêtable et **fileté**. Rend `(url, arreter)`.

    ⚠️ `wsgiref` sert UNE requête à la fois. Un navigateur en ouvre six en
    parallèle — le gabarit, ses modules ES, la police, l'API — et une page qui
    relit ses données pendant ce temps-là passe devant les fichiers qu'elle
    attend encore. Sur le Mac ça ne se voit pas ; sur un runner partagé, la
    page met des dizaines de secondes à finir de se charger, et le test qui
    l'observe a l'air d'attendre une horloge alors qu'il fait la queue.
    """
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIServer, make_server
    import threading

    class ServeurFile(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    port = port_libre()
    httpd = make_server("127.0.0.1", port, app, server_class=ServeurFile)
    # ⚠️ `poll_interval` par defaut : **0,5 s**. C'est le temps que `shutdown()`
    # passe a attendre que la boucle veuille bien regarder son drapeau -- une
    # attente d'horloge pure, payee a CHAQUE fermeture de serveur. Elle ne se
    # voyait nulle part : elle est logee dans le teardown, ou personne ne lit
    # les durees. Mesure du 04/09 sur les six fichiers navigateur : **5,4 s de
    # teardown** pour 3,9 s de setup et 8,6 s de travail reel.
    #
    # 20 ms : la fermeture reste franche, et le serveur ne consomme rien de
    # plus entre deux sondes -- `selectors` dort, il ne tourne pas.
    threading.Thread(target=httpd.serve_forever, args=(0.02,), daemon=True).start()

    def arreter():
        httpd.shutdown()
        httpd.server_close()

    return f"http://127.0.0.1:{port}", arreter


# Au-dela, un test navigateur n'est plus « un peu lent » : il attend. Le seuil
# est bas expres -- le but n'est pas de faire echouer, c'est de NOMMER, et une
# alerte qui ne se declenche jamais ne sert a rien.
SEUIL_ALERTE_S = 5


def _signaler_si_lent(rendu: str, secondes: float) -> str:
    """Un verdict lent remonte en AVERTISSEMENT, avec ses attentes nommees.

    Un test navigateur qui passe ne montre rien de ce qu'il a fait. Celui de la
    couture des zones a mis 29 s sur un runner et 0,7 s sur le Mac : il a fallu
    deux passages de CI pour savoir ce qu'il attendait. Le preambule note
    desormais chaque attente de plus de 500 ms, et cette alerte les fait
    apparaitre dans le resume des avertissements de pytest -- sans faire
    echouer quoi que ce soit.
    """
    if secondes < SEUIL_ALERTE_S:
        return rendu
    attentes = " ".join(m for m in rendu.split(" ") if m.startswith("attente_"))
    if not attentes:
        attentes = ("(aucune -- le temps est passe AVANT le pilote : demarrage"
                    " du navigateur, ou chargement de la page)")
    warnings.warn(
        f"navigateur : {secondes:.1f} s pour un verdict."
        f" Attentes de plus de 500 ms : {attentes}",
        stacklevel=3)
    return rendu


# --- Le navigateur partagé ---------------------------------------------------
#
# ⚠️ Ce qui suit remplace « un processus chromium par pilotage ». Le compte de
# démarrages est la seule variable qui compte : 0,3 s à chaud, 7,2 s au premier
# lancement d'un runner. Il vaut désormais UN pour toute la session, quel que
# soit le nombre de parcours.
#
# Deux règles pour que ce partage reste honnête :
#
# 1. **Chaque parcours a son contexte.** `Target.createBrowserContext` isole
#    cookies, `localStorage`, `sessionStorage`, cache et service workers aussi
#    complètement qu'un profil neuf. C'est ce qui permet à
#    `test_navigateur_theme_au_choix.py` de vérifier qu'un choix SURVIT sans
#    que le fichier suivant hérite de ce choix.
# 2. **On ne parle CDP qu'avec la bibliothèque standard.** Une dépendance de
#    test de plus se paie à chaque installation, en CI comme sur le Mac ; le
#    protocole tient ici en une centaine de lignes, et il ne bouge pas.


class _WebSocket:
    """Le strict nécessaire du protocole, côté client. RFC 6455, §5.

    Volontairement minimal : CDP en local n'envoie que des trames texte, jamais
    de fragmentation, et le seul cadre de contrôle qui arrive vraiment est le
    ping. Tout le reste est traité comme une erreur plutôt que deviné.
    """

    def __init__(self, url: str, delai: float = 30.0):
        reste = url.split("://", 1)[1]
        hote, _, chemin = reste.partition("/")
        machine, _, port = hote.partition(":")
        self.prise = socket.create_connection((machine, int(port)), timeout=delai)
        cle = base64.b64encode(os.urandom(16)).decode()
        self.prise.sendall(
            (f"GET /{chemin} HTTP/1.1\r\nHost: {hote}\r\n"
             "Upgrade: websocket\r\nConnection: Upgrade\r\n"
             f"Sec-WebSocket-Key: {cle}\r\nSec-WebSocket-Version: 13\r\n\r\n"
             ).encode())
        self.tampon = b""
        while b"\r\n\r\n" not in self.tampon:
            morceau = self.prise.recv(4096)
            if not morceau:
                raise ConnectionError("le navigateur a refuse la connexion CDP")
            self.tampon += morceau
        entetes, self.tampon = self.tampon.split(b"\r\n\r\n", 1)
        if b" 101 " not in entetes.split(b"\r\n")[0] + b" ":
            raise ConnectionError(f"CDP : {entetes.splitlines()[0]!r}")

    def _lire(self, n: int) -> bytes:
        while len(self.tampon) < n:
            morceau = self.prise.recv(65536)
            if not morceau:
                raise ConnectionError("le navigateur a ferme la connexion CDP")
            self.tampon += morceau
        debut, self.tampon = self.tampon[:n], self.tampon[n:]
        return debut

    def _trame(self, code: int, charge: bytes) -> None:
        n = len(charge)
        entete = bytes([0x80 | code])
        if n < 126:
            entete += struct.pack("!B", 0x80 | n)
        elif n < 65536:
            entete += struct.pack("!BH", 0x80 | 126, n)
        else:
            entete += struct.pack("!BQ", 0x80 | 127, n)
        # Le masque est OBLIGATOIRE pour un client, meme en local : chromium
        # ferme la connexion sur une trame non masquee, et le diagnostic est
        # alors un « connexion fermee » qui n'accuse personne.
        masque = os.urandom(4)
        self.prise.sendall(entete + masque +
                           bytes(o ^ masque[i % 4] for i, o in enumerate(charge)))

    def envoyer(self, objet: dict) -> None:
        self._trame(0x1, json.dumps(objet).encode())

    def recevoir(self) -> dict:
        while True:
            premier, second = self._lire(2)
            code = premier & 0x0F
            n = second & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._lire(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._lire(8))[0]
            charge = self._lire(n)
            if code == 0x9:                       # ping -> pong
                self._trame(0xA, charge)
                continue
            if code == 0xA:                       # pong non sollicite
                continue
            if code == 0x8:
                raise ConnectionError("le navigateur a ferme la connexion CDP")
            if code in (0x0, 0x1):
                return json.loads(charge)
            raise ConnectionError(f"trame websocket inattendue : code {code}")

    def fermer(self) -> None:
        try:
            self.prise.close()
        except OSError:
            pass


class _Navigateur:
    """Un chromium pour toute la session, et un contexte isolé par parcours."""

    def __init__(self):
        self.processus = None
        self.profil = None
        self.ws = None
        self.numero = 0
        self.verrou = threading.Lock()

    # -- le cycle de vie ----------------------------------------------------
    def demarrer(self) -> None:
        """Idempotent, et sûr si deux fils le demandent en même temps."""
        with self.verrou:
            if self.ws is not None and self.processus.poll() is None:
                return
            self._demarrer()

    def _demarrer(self) -> None:
        self.profil = tempfile.mkdtemp(prefix="climbcontest-chromium-")
        self.processus = subprocess.Popen(            [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
             "--no-first-run", "--disable-dev-shm-usage",
             f"--user-data-dir={self.profil}",
             # Port 0 : le noyau choisit, et chromium l'écrit dans le profil.
             # Un port fixe se ferait voler par le voisin sur une machine
             # partagée -- et par un autre worker sur le même runner.
             "--remote-debugging-port=0", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        drapeau = Path(self.profil) / "DevToolsActivePort"
        fin = time.time() + 60
        while time.time() < fin:
            if drapeau.exists():
                lignes = drapeau.read_text().splitlines()
                if lignes and lignes[0].strip().isdigit():
                    break
            if self.processus.poll() is not None:
                raise RuntimeError(
                    f"chromium s'est arrete tout de suite (code "
                    f"{self.processus.returncode}) : {CHROME}")
            time.sleep(0.01)
        else:
            self.arreter()
            raise RuntimeError("chromium n'a pas ouvert son port CDP en 60 s")
        port = int(drapeau.read_text().splitlines()[0])
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=30) as r:
            adresse = json.load(r)["webSocketDebuggerUrl"]
        self.ws = _WebSocket(adresse)
        atexit.register(self.arreter)

    def arreter(self) -> None:
        if self.ws is not None:
            self.ws.fermer()
            self.ws = None
        if self.processus is not None and self.processus.poll() is None:
            self.processus.kill()
            self.processus.wait(timeout=30)
        self.processus = None
        if self.profil:
            # `ignore_errors` : chromium ecrit encore dans `Default/` pendant
            # qu'on le tue, et une suppression stricte leve « Directory not
            # empty » sur une machine chargee.
            shutil.rmtree(self.profil, ignore_errors=True)
            self.profil = None

    # -- le protocole -------------------------------------------------------
    def appeler(self, methode: str, **params):
        self.numero += 1
        attendu = self.numero
        self.ws.envoyer({"id": attendu, "method": methode, "params": params})
        while True:
            message = self.ws.recevoir()
            if message.get("id") != attendu:
                continue                    # un evenement : rien a en faire ici
            if "error" in message:
                raise RuntimeError(f"CDP {methode} : {message['error']}")
            return message.get("result", {})

    def ouvrir(self, url: str, taille):
        """Un onglet neuf, dans un contexte à lui. Rend `(cible, contexte)`."""
        contexte = self.appeler("Target.createBrowserContext")["browserContextId"]
        cible = self.appeler("Target.createTarget", url=url,
                             browserContextId=contexte,
                             # ⚠️ La taille de la FENETRE, pas celle du cadre :
                             # `page_harnais` fixe le cadre en CSS, et c'est lui
                             # que lisent les media queries de la page testee.
                             # La fenetre doit juste etre assez grande pour ne
                             # pas le rogner -- meme marge qu'avant.
                             width=taille[0] + 40, height=taille[1] + 120,
                             )["targetId"]
        return cible, contexte

    def refermer(self, cible: str, contexte: str) -> None:
        # Jamais d'exception ici : une fermeture ratee ne doit pas transformer
        # un test VERT en rouge. Un navigateur vraiment mort se signalera au
        # pilotage suivant, qui le relancera.
        for methode, params in (("Target.closeTarget", {"targetId": cible}),
                                ("Target.disposeBrowserContext",
                                 {"browserContextId": contexte})):
            try:
                self.appeler(methode, **params)
            except Exception:
                pass


#: Le nom du groupe `xdist` qui garde tous les tests navigateur sur un MEME
#: worker. Il vit ici, avec le harnais, et non dans `tests/conftest.py` : le
#: garde qui verifie le regroupement doit pouvoir le nommer sans importer un
#: conftest.
GROUPE = "navigateur"

#: Le navigateur de ce processus. Un seul, quel que soit le nombre de fichiers.
#: Sous `pytest-xdist`, tous les tests navigateur sont regroupes sur UN worker
#: (voir `tests/conftest.py`), donc un seul pour toute l'execution.
NAVIGATEUR = _Navigateur()


def piloter(url: str, verdict: dict, secondes: int = 60,
            taille=TELEPHONE) -> str:
    """Ouvre le harnais dans un onglet isolé et rend le verdict qu'il a posté.

    Le navigateur, lui, est déjà là : cette fonction n'en démarre un que la
    toute première fois.

    """
    # ⚠️ ON POSE L'ETAT DONT ON DEPEND, au lieu de le supposer. La boucle
    # ci-dessous attend que `verdict["texte"]` cesse d'etre `None` : elle tenait
    # donc pour acquis qu'on lui remettait un verdict vierge, sans jamais
    # l'ecrire nulle part. Tant que chaque appel recevait une fixture neuve, le
    # pari etait gagne -- mais il ne tenait qu'a la portee des fixtures.
    #
    # Le jour ou une fixture qui monte le serveur passe en portee module et que
    # plusieurs tests appellent `piloter`, le deuxieme appel trouve le verdict
    # du PREMIER, rend instantanement, et ne lance meme pas de navigateur. Le
    # test suivant passe alors au VERT sur les mesures du parcours precedent :
    # un test qui ne mesure plus rien et qui ne le dit pas, le pire des deux
    # modes d'echec.
    #
    # Trouve le 04/09 par deux sessions independamment, apres que la spec 041 a
    # introduit les premieres fixtures en portee module. Une ligne ici rend le
    # piege impossible ; aucun appelant existant ne change de comportement,
    # puisqu'ils partaient tous d'un verdict vierge. Elle compte double depuis
    # que le navigateur est PARTAGE : c'est elle qui garantit qu'un parcours
    # attend bien son propre verdict, et pas celui du precedent.
    verdict["texte"] = None
    NAVIGATEUR.demarrer()
    cible, contexte = NAVIGATEUR.ouvrir(url, taille)
    try:
        debut = time.time()
        fin = debut + secondes
        while time.time() < fin:
            if verdict["texte"] is not None:
                return _signaler_si_lent(verdict["texte"], time.time() - debut)
            if NAVIGATEUR.processus.poll() is not None:
                return ("ECHEC || le navigateur est mort pendant le parcours "
                        f"(code {NAVIGATEUR.processus.returncode})")
            # 20 ms, et pas 200 : ce n'est pas une attente d'horloge, c'est la
            # relecture d'un verdict DEJA pose. Un pas grossier ajoutait un
            # dixieme de seconde a chaque parcours pour rien.
            time.sleep(0.02)
        return "ECHEC || le pilote n'a rien rendu en " + str(secondes) + " s"
    finally:
        NAVIGATEUR.refermer(cible, contexte)


def chauffer(persistant: bool = True) -> None:
    """Paie le démarrage du navigateur en fond, hors de tout test.

    ⚠️ Mesure du 03/09 sur un runner GitHub : `/usr/bin/chromium` met **7,21 s**
    a rendre sa premiere requete, puis **0,33 s** et **0,32 s**. Google Chrome
    fait pareil (5,32 puis 0,25). Ce n'est pas un defaut : c'est la lecture du
    binaire et de ses bibliotheques depuis un disque froid.

    Ce prix etait facture au PREMIER test navigateur venu -- celui de la couture
    des zones, par ordre alphabetique. Il affichait 15 s en CI contre 0,7 s sur
    le Mac, et passait pour un test qui attend une horloge.

    Elle ne lance plus un chromium jetable : elle demarre CELUI que tous les
    parcours vont utiliser. La chauffe et le navigateur de travail sont donc le
    meme processus -- on ne paie plus deux demarrages pour n'en amortir qu'un.

    Appelee dans un fil, apres la collecte, elle tourne pendant les quinze cents
    tests qui n'ont pas besoin de navigateur.

    ⚠️ `persistant=False` sous `pytest-xdist`. Le processus qui coordonne les
    workers ne joue AUCUN test : le navigateur qu'il garderait ouvert ne
    servirait a personne, et le worker qui herite du groupe navigateur en
    ouvrirait un autre. Mais le demarrage n'est pas qu'une affaire de
    processus -- les 7,2 s sont la LECTURE du binaire et de ses bibliotheques
    depuis un disque froid, et ce travail-la profite a tout le monde une fois
    fait. On demarre donc, puis on referme : le processus ne survit pas, le
    cache du systeme si.
    """
    try:
        NAVIGATEUR.demarrer()
        if not persistant:
            NAVIGATEUR.arreter()
    except Exception:
        # La chauffe est un CONFORT. Si elle echoue, le premier pilotage
        # relancera -- et c'est lui qui devra dire pourquoi, avec sa propre
        # exception, plutot qu'un fil de fond que personne ne regarde.
        pass
