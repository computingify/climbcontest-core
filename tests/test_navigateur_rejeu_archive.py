"""La fiche du grimpeur N'EXISTE PAS en rejeu d'archive — dans un navigateur.

La spec 026 met le rejeu hors périmètre en une phrase : « la route publique ne
parle que de la compétition active ». La garde, elle, n'a jamais été posée —
`if (!MUR)` couvrait le mode mur et rien d'autre. Une ligne d'archive restait
donc cliquable, et `GET /api/public/grimpeur/<id>` répondait avec la
**compétition active**.

⚠️ **Pourquoi ce n'est pas une simple fiche vide.** `Participant.id` est un
rowid SQLite ; effacer une édition (spec 018) libère ses identifiants, et la
suivante les reprend. Le scénario ci-dessous le reproduit : mars est archivée
puis effacée, novembre reprend les id 1 et 2, et toucher « MARS-Alice » ouvrait
la fiche de « NOV-Chloe ». Deux personnes réelles, nommées, dont l'une est
mineure — c'est ce que ce fichier empêche de revenir.

Un test dans un vrai navigateur, et non sur le gabarit : ce qui est en cause
est un **branchement** — un gestionnaire de clic et une règle de curseur — et
un test qui chercherait la chaîne `!ARCHIVE` dans le HTML passerait au vert le
jour où quelqu'un déplacerait la garde ailleurs sans la faire marcher.

⚠️ Ce fichier se saute proprement s'il n'y a pas de navigateur, comme
`test_navigateur_fiche.py`.
"""
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from datetime import date
from pathlib import Path
from wsgiref.simple_server import make_server

import pytest

RACINE = Path(__file__).resolve().parent.parent

CHEMINS_CHROME = [
    os.environ.get("CLIMBCONTEST_CHROME", ""),
    str(Path.home() / "Library/Caches/ms-playwright/chromium_headless_shell-1234"
        "/chrome-headless-shell-mac-arm64/chrome-headless-shell"),
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
pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")


# Le pilote. Il rend son verdict par un `fetch`, et NON par le titre du
# document : `--virtual-time-budget` fait courir les minuteries plus vite que le
# reseau, et une attente de huit secondes virtuelles expire avant qu'une requete
# reelle soit revenue.
PILOTE = r"""
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
    // ⚠️ `contentDocument` rend d'abord le `about:blank` INITIAL, dont le
    // `readyState` vaut deja « complete ». On attend un contenu reel, et on
    // relit `contentDocument` a chaque acces : la reference d'avant navigation
    // pointe sur un document qui n'existe plus.
    const $ = (s) => cadre.contentDocument.querySelector(s);
    const $$ = (s) => [...cadre.contentDocument.querySelectorAll(s)];
    const vue = () => cadre.contentWindow;
    await attendre("classement archive",
      () => $$(".ligne[data-participant]").length > 0);

    const ligne = $$(".ligne[data-participant]")[0];
    note("nom", ligne.textContent.trim().slice(0, 20));
    note("id", ligne.dataset.participant);
    // Le curseur DIT s'il y a quelque chose a toucher : c'est la promesse
    // faite au doigt avant meme le clic.
    note("curseur", vue().getComputedStyle(ligne).cursor);

    ligne.click();
    await new Promise((r) => setTimeout(r, 1200));
    note("feuille", !!$(".sf-feuille"));
    note("hash", vue().location.hash || "(vide)");

    // Et l'adresse forgee a la main ne doit pas davantage ouvrir la fiche.
    vue().location.hash = "#g=" + ligne.dataset.participant;
    await new Promise((r) => setTimeout(r, 1200));
    note("feuilleApresDiese", !!$(".sf-feuille"));

    rendre("OK " + etapes.join(" "));
  } catch (e) {
    rendre("ECHEC " + etapes.join(" ") + " || " + e.message);
  }
})();
"""


def port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _semer(app):
    """Mars archivée puis effacée, novembre qui reprend ses identifiants.

    C'est la séquence que la spec 018 rend possible — archiver, puis effacer —
    et elle suffit à faire pointer un identifiant d'archive sur quelqu'un
    d'autre. On ne la simule pas : on la joue.
    """
    from climbcontest import cycle
    from climbcontest.extensions import db
    from climbcontest.models import (
        Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant, Success)

    with app.app_context():
        db.create_all()

        def edition(nom, noms, active):
            comp = Competition(nom=nom, date=date(2026, 3, 1), statut=EN_COURS,
                               active=active, spreadsheet_id="fictif")
            db.session.add(comp)
            db.session.flush()
            circuit = Circuit(competition_id=comp.id, nom="U13")
            db.session.add(circuit)
            db.session.flush()
            bloc = Bloc(competition_id=comp.id, tag="ZJ1", numero=1, zone="Z",
                        couleur="Jaune")
            db.session.add(bloc)
            db.session.flush()
            db.session.add(BlocCircuit(bloc_id=bloc.id, circuit_id=circuit.id))
            gens = []
            for i, n in enumerate(noms, 1):
                p = Participant(competition_id=comp.id, nom=n, prenom="X",
                                club="C", categorie="U13 F", dossard=i,
                                present=True)
                db.session.add(p)
                db.session.flush()
                db.session.add(Success(participant_id=p.id, bloc_id=bloc.id))
                gens.append(p)
            db.session.commit()
            return comp, gens

        mars, gens = edition("Mars 2026", ["MARS-Alice", "MARS-Bea"], True)
        ids = [p.id for p in gens]
        archive, _ = cycle.archiver(mars, par="chef")
        identifiant = archive.id

        Success.query.filter(Success.participant_id.in_(ids)).delete(
            synchronize_session=False)
        Participant.query.filter(Participant.id.in_(ids)).delete(
            synchronize_session=False)
        mars.active = False
        db.session.commit()

        _, suivants = edition("Novembre 2026", ["NOV-Chloe", "NOV-Dina"], True)
        # Sans reutilisation, le test ne demontrerait rien : il verifierait une
        # fiche VIDE et non une fiche FAUSSE. On le verifie, on ne le suppose pas.
        repris = sorted(set(ids) & {p.id for p in suivants})
        return identifiant, repris


@pytest.fixture()
def serveur():
    """L'application, un vrai serveur, et deux routes qui n'existent qu'ici.

    ⚠️ `make_server` et non `app.run` : le second laisse son fil vivre APRES le
    test et garde son port, ce qui fait echouer sans rapport apparent le
    premier test suivant qui demarre un vrai serveur.
    """
    from flask import Response, render_template, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-rejeu-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import creer_app, cycle
    from climbcontest.config import Config
    from climbcontest.extensions import db
    from climbcontest.models import Archive

    class ConfigRejeu(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "rejeu.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigRejeu)
    identifiant, repris = _semer(app)
    verdict = {"texte": None}

    # La vraie source d'archive exige une session d'organisateur. On sert le
    # MEME JSON sans session : ce test parle de la page, pas de son controle
    # d'acces, qui a ses propres tests.
    @app.get("/__archive/<int:i>/classement")
    def source(i):
        from flask import jsonify
        archive = db.session.get(Archive, i)
        charge = cycle.classement_archive(archive)
        return jsonify({**charge, "archive": archive.resume(), "age_s": None})

    @app.get("/__rejeu/<int:i>")
    def rejeu(i):
        from climbcontest.suivi import plan_public
        return render_template("resultats.html", plan=plan_public(),
                               source=f"/__archive/{i}/classement",
                               archive_libelle="2026-03-01")

    @app.post("/__verdict")
    def poser():
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    @app.get("/__harnais/<int:i>")
    def harnais(i):
        return Response(
            "<!doctype html><meta charset=utf-8><title>harnais</title>"
            f"<iframe id=page src='/__rejeu/{i}' "
            "style='width:390px;height:844px;border:0'></iframe>"
            f"<script>{PILOTE}</script>", mimetype="text/html")

    port = port_libre()
    httpd = make_server("127.0.0.1", port, app)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}", identifiant, repris, verdict
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(dossier, ignore_errors=True)


def piloter(url, verdict, secondes=45):
    with tempfile.TemporaryDirectory() as profil:
        navigateur = subprocess.Popen(
            [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={profil}", "--window-size=390,844", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            fin = time.time() + secondes
            while time.time() < fin:
                if verdict["texte"] is not None:
                    return verdict["texte"]
                time.sleep(0.2)
            return "ECHEC || le pilote n'a rien rendu"
        finally:
            navigateur.terminate()
            navigateur.wait(timeout=10)


class TestLaFicheNExistePasEnRejeuDArchive:

    def test_une_ligne_d_archive_n_ouvre_rien(self, serveur):
        url, identifiant, repris, verdict = serveur

        # Le scenario n'a de valeur que si les identifiants sont VRAIMENT
        # repris : sans ca, on testerait une fiche vide et non une fiche fausse.
        assert repris, (
            "les identifiants n'ont pas ete reutilises : le scenario ne "
            "demontre plus rien, il faut le revoir")

        rendu = piloter(f"{url}/__harnais/{identifiant}", verdict)
        assert rendu.startswith("OK "), rendu
        mesures = dict(m.split("=", 1) for m in rendu[3:].split(" ") if "=" in m)

        assert mesures["nom"].startswith("1MARS-Alice") or "MARS" in mesures["nom"]
        assert mesures["id"] in {str(i) for i in repris}

        # Rien ne s'ouvre, ni au clic ni par une adresse forgee.
        assert mesures["feuille"] == "false", (
            "une ligne d'archive ouvre une fiche : elle decrit la competition "
            "ACTIVE, donc quelqu'un d'autre")
        assert mesures["feuilleApresDiese"] == "false", (
            "l'adresse #g=<id> ouvre une fiche en rejeu d'archive")

        # Et la page ne PROMET pas un clic qu'elle ne tiendra pas.
        assert mesures["curseur"] != "pointer", (
            "le curseur invite a toucher une ligne qui n'ouvre rien")
