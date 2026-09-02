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
`readyState` vaut déjà « complete ». Attendre cet état ne prouve donc rien : on
attend un contenu réel, et on relit `contentDocument` à **chaque** accès — la
référence prise avant la navigation pointe ensuite sur un document mort.

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
from pathlib import Path

CHEMINS_CHROME = [
    os.environ.get("CLIMBCONTEST_CHROME", ""),
    str(Path.home() / "Library/Caches/ms-playwright/chromium_headless_shell-1234"
        "/chrome-headless-shell-mac-arm64/chrome-headless-shell"),
    # `ubuntu-latest` le FOURNIT : ces tests tournent sur la CI, ils ne s'y
    # sautent pas.
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "chromium", "google-chrome",
]


def trouver_chrome():
    for chemin in CHEMINS_CHROME:
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
      if (r) return ok(r);
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
    await attendre("vraie page",
      () => cadre.contentDocument
         && cadre.contentDocument.querySelectorAll("*").length > 20);
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
    """Un vrai serveur HTTP, arrêtable. Rend `(url, arreter)`."""
    from wsgiref.simple_server import make_server
    import threading

    port = port_libre()
    httpd = make_server("127.0.0.1", port, app)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def arreter():
        httpd.shutdown()
        httpd.server_close()

    return f"http://127.0.0.1:{port}", arreter


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
            fin = time.time() + secondes
            while time.time() < fin:
                if verdict["texte"] is not None:
                    return verdict["texte"]
                if navigateur.poll() is not None:
                    break
                time.sleep(0.2)
            return "ECHEC || le pilote n'a rien rendu en " + str(secondes) + " s"
        finally:
            navigateur.kill()
            navigateur.wait(timeout=30)
