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
"""
import os
import shutil
import socket
import subprocess
import tempfile
import time
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
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

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


def piloter(url: str, verdict: dict, secondes: int = 60,
            taille=TELEPHONE) -> str:
    """Ouvre le harnais et rend le verdict que le pilote a posté.

    ⚠️ `ignore_cleanup_errors` : chromium écrit encore dans `Default/` pendant
    qu'on le tue, et une suppression stricte lève `Directory not empty` sur une
    machine chargée. Même idiome que `test_navigateur_fiche.py`, où la CI l'a
    fait tomber une fois.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profil:
        navigateur = subprocess.Popen(
            [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
             "--no-first-run", "--disable-dev-shm-usage",
             f"--user-data-dir={profil}",
             f"--window-size={taille[0] + 40},{taille[1] + 120}", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            debut = time.time()
            fin = debut + secondes
            while time.time() < fin:
                if verdict["texte"] is not None:
                    return _signaler_si_lent(verdict["texte"], time.time() - debut)
                if navigateur.poll() is not None:
                    break
                time.sleep(0.2)
            return "ECHEC || le pilote n'a rien rendu en " + str(secondes) + " s"
        finally:
            navigateur.kill()
            navigateur.wait(timeout=30)


def chauffer() -> None:
    """Paie le PREMIER lancement du navigateur, en fond, hors de tout test.

    ⚠️ Mesure du 03/09 sur un runner GitHub : `/usr/bin/chromium` met **7,21 s**
    a rendre sa premiere requete, puis **0,33 s** et **0,32 s**. Google Chrome
    fait pareil (5,32 puis 0,25). Ce n'est pas un defaut : c'est la lecture du
    binaire et de ses bibliotheques depuis un disque froid.

    Mais ce prix etait facture au PREMIER test navigateur venu -- celui de la
    couture des zones, par ordre alphabetique. Il affichait 15 s en CI contre
    0,7 s sur le Mac, et passait pour un test qui attend une horloge. Il
    n'attendait rien : il payait le demarrage des cinq autres.

    Appelee dans un fil, apres la collecte, elle tourne pendant les quinze
    cents tests qui n'ont pas besoin de navigateur. Quand les tests navigateur
    arrivent, le disque est chaud et plus personne n'attend -- le cout total ne
    change pas, il cesse simplement d'etre porte par un innocent.
    """
    import http.server
    import threading

    vu = []

    class Sonde(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            vu.append(True)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<!doctype html><title>chauffe</title>ok")

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", port_libre()), Sonde)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profil:
        navigateur = subprocess.Popen(
            [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
             "--no-first-run", "--disable-dev-shm-usage",
             f"--user-data-dir={profil}",
             "http://127.0.0.1:%d/" % httpd.server_address[1]],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            # On le tue des qu'il a demande la page : a ce moment-la il est
            # entierement demarre, et c'est tout ce qu'on voulait.
            fin = time.time() + 60
            while time.time() < fin and not vu:
                if navigateur.poll() is not None:
                    break
                time.sleep(0.05)
        finally:
            navigateur.kill()
            navigateur.wait(timeout=30)
            httpd.shutdown()
