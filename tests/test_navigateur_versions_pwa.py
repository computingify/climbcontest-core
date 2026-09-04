"""Les sections « Catalogue » et « Application » des Reglages, dans un vrai
navigateur — criteres A4 a A8 de la spec 030.

⚠️ **Ce que ce fichier ferme.** La spec 030 est couverte cote serveur par
`tests/test_versions.py` (les en-tetes, la table, les verdicts) et cote logique
pure par `tests/js/versions.test.mjs` (la comparaison des numeros). Entre les
deux, il n'y avait **rien** : aucun test du depot ne mentionnait
`versionCatalogue`, `forcerCatalogue` ni `majApplication`. Le cablage — le
module qui remplit ces elements, et le bouton qui declenche la bonne requete —
tenait par une verification faite a la main le 04/09, et par rien d'autre.

Ce qui se casserait sans ces tests, et ne se verrait pas :

- un identifiant renomme dans le gabarit sans l'etre dans `juge.js` : les
  modules restent verts, l'ecran affiche des tirets ;
- « Reteecharger maintenant » qui repasserait par le rafraichissement normal :
  la requete emporterait `If-None-Match`, le serveur repondrait `304`, et le
  bouton ne ferait **rien** tout en disant que tout va bien ;
- le bouton de mise a jour de la coquille affiche en permanence, ou jamais.

La requete du bouton est observee **cote serveur**, pas cote client : c'est ce
que le serveur recoit qui decide de la reponse, et c'est donc la seule mesure
qui prouve quelque chose.
"""
import json
import os
import shutil
import tempfile
from datetime import date

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")


SONDE = """
    await attendre("demarrage fini",
      () => $("#accueil") && $("#accueil").classList.contains("parti"));
    $("#ouvrirReglages").click();
    await attendre("reglages ouverts",
      () => $("#ecranReglages") && !$("#ecranReglages").hasAttribute("hidden"));

    // Le catalogue arrive au demarrage : on attend qu'il soit peint plutot que
    // de lire un tiret et d'en tirer une conclusion.
    await attendre("catalogue peint",
      () => $("#versionCatalogue") && $("#versionCatalogue").textContent.trim() !== "—");

    // --- A4 : ce que la section Catalogue montre ---------------------------
    note("numero", $("#versionCatalogue").textContent.trim());
    note("verdictCatalogue", $("#verdictCatalogue").textContent.trim());
    note("contenu", $("#contenuCatalogue").textContent.trim());

    // --- A5 + A8, premier etat : la coquille est a jour --------------------
    note("versionApp", $("#versionApp").textContent.trim());
    const maj = $("#majApplication");
    note("majCachee", maj.hasAttribute("hidden"));
    note("majDisplay", vue().getComputedStyle(maj).display);
    note("majHauteur", Math.round(maj.getBoundingClientRect().height));

    // --- A6 : ce que le bouton envoie VRAIMENT -----------------------------
    await fetch("/__requetes", { method: "DELETE" });
    $("#forcerCatalogue").click();
    // ⚠️ Une boucle, et non `attendre` : sa condition est appelee SANS `await`,
    // donc une condition asynchrone rend une promesse -- toujours vraie. Le
    // test passait au vert avant meme que la requete parte, puis lisait un
    // journal vide.
    let vues = [];
    for (let i = 0; i < 120 && vues.length === 0; i++) {
      await new Promise((r) => setTimeout(r, 100));
      vues = await (await fetch("/__requetes")).json();
    }
    if (!vues.length) throw new Error("le bouton n'a declenche aucune requete de catalogue");
    const derniere = vues[vues.length - 1];
    note("forceSansEtag", derniere.si_none_match === null);
    note("forceSansDepuis", derniere.query === "");
    note("forceAnnonce", derniere.appareil !== null);

    // --- A5 + A8, second etat : le serveur sert une AUTRE version ----------
    await fetch("/__version/v9.9.9");
    $("#forcerCatalogue").click();
    await attendre("verdict d'application change",
      () => $("#verdictApp") && /9\\.9\\.9/.test($("#verdictApp").textContent));
    note("verdictApp", $("#verdictApp").textContent.trim().replace(/\\s+/g, "_"));
    note("majVisibleQuandEnRetard",
      !$("#majApplication").hasAttribute("hidden")
      && $("#majApplication").getBoundingClientRect().height > 0);

    // --- A7 : hors ligne, le bouton refuse et ne casse rien ----------------
    // Le reseau tombe pour de bon du point de vue de la page : `globalThis.fetch`
    // est relu a chaque appel par `api.js`, donc le remplacer suffit -- et c'est
    // exactement ce que voit une application dont le telephone n'a plus de reseau.
    const avantHorsLigne = $("#versionCatalogue").textContent.trim();
    const vraiFetch = vue().fetch;
    vue().fetch = (u, o) => (String(u).indexOf("/api/") === 0
      ? Promise.reject(new TypeError("Failed to fetch"))
      : vraiFetch(u, o));
    $("#forcerCatalogue").click();
    await attendre("message hors ligne",
      () => $("#message") && !$("#message").hasAttribute("hidden")
            && /injoignable/i.test($("#message").textContent));
    note("messageHorsLigne", $("#message").textContent.trim().replace(/\\s+/g, "_"));
    note("catalogueIntact", $("#versionCatalogue").textContent.trim() === avantHorsLigne);
    note("boutonEncoreUtilisable", !$("#forcerCatalogue").disabled);
    vue().fetch = vraiFetch;
"""


@pytest.fixture()
def serveur():
    """L'application, un catalogue non vide, et trois crochets de test.

    Les crochets ne vivent que dans ce fichier : le livre n'a ni `/__requetes`
    ni `/__version`. Ils servent a observer ce que le SERVEUR recoit, ce qu'un
    espion pose dans la page ne prouverait pas.
    """
    from flask import Response, jsonify, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-versions-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import creer_app
    from climbcontest.config import Config
    from climbcontest.extensions import db
    from climbcontest.models import (
        Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant,
    )

    class ConfigVersions(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "v.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigVersions)

    with app.app_context():
        comp = Competition(nom="Contest de test", date=date.today(),
                           statut=EN_COURS, active=True)
        db.session.add(comp)
        db.session.flush()
        circuit = Circuit(competition_id=comp.id, nom="U13")
        db.session.add(circuit)
        db.session.flush()
        for i, tag in enumerate(["ZJ6", "ZJ7", "DV21"], 1):
            b = Bloc(competition_id=comp.id, tag=tag, numero=i, zone=tag[0],
                     couleur="Jaune")
            db.session.add(b)
            db.session.flush()
            db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=circuit.id))
        for i, nom in enumerate(["Dupont", "Martin"], 1):
            db.session.add(Participant(competition_id=comp.id, nom=nom,
                                       prenom="Lea", club="Les Lezards",
                                       categorie="U13 F", dossard=i,
                                       present=True))
        db.session.commit()

    verdict = {"texte": None}
    journal = []
    faux = {"version": None}

    @app.before_request
    def _noter():
        if request.path == "/api/v2/catalog":
            journal.append({
                "query": request.query_string.decode(),
                "si_none_match": request.headers.get("If-None-Match"),
                "appareil": request.headers.get("X-Device-Id"),
            })

    @app.after_request
    def _mentir_sur_la_version(reponse):
        # Le seul moyen honnete de jouer « le serveur a une version d'avance »
        # sans reconstruire une release : le client ne connait la version du
        # serveur que par cet en-tete.
        if request.path == "/api/v2/catalog" and faux["version"]:
            reponse.headers["X-Server-Version"] = faux["version"]
        return reponse

    @app.get("/__requetes")
    def _lire():
        return jsonify(journal)

    @app.delete("/__requetes")
    def _vider():
        journal.clear()
        return "", 204

    @app.get("/__version/<v>")
    def _poser_version(v):
        faux["version"] = v
        return "", 204

    @app.post("/__verdict")
    def _poser():
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    @app.get("/__harnais")
    def _harnais():
        return Response(page_harnais("/juge", SONDE), mimetype="text/html")

    url, arreter = servir(app)
    try:
        yield url, verdict
    finally:
        arreter()
        shutil.rmtree(dossier, ignore_errors=True)


def _mesures(rendu):
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestLesDeuxSectionsDesReglages:

    def test_le_cablage_complet(self, serveur):
        url, verdict = serveur
        m = _mesures(piloter(f"{url}/__harnais", verdict))

        # --- A4 ------------------------------------------------------------
        assert m["numero"] == "n°_1", (
            f"le numero de catalogue affiche est « {m['numero']} » : la section "
            "Catalogue ne recoit plus ce que le module lui donne")
        assert m["verdictCatalogue"] == "Identique_au_serveur", m["verdictCatalogue"]
        assert "2_grimpeurs" in m["contenu"] and "3_blocs" in m["contenu"], (
            f"le contenu annonce est « {m['contenu'] } », alors que le catalogue "
            "servi porte 2 grimpeurs et 3 blocs")

        # --- A5 et A8, coquille a jour --------------------------------------
        assert m["versionApp"] == "dev"
        assert m["majCachee"] == "true"
        assert m["majDisplay"] == "none", (
            "« Mettre a jour et redemarrer » est calcule en "
            f"`display: {m['majDisplay']}` alors que la coquille est a jour : "
            "une regle d'auteur bat le `[hidden]` global, et le bouton propose "
            "une mise a jour qui n'existe pas")
        assert m["majHauteur"] == "0"

        # --- A6 : la requete forcee -----------------------------------------
        assert m["forceSansEtag"] == "true", (
            "« Reteecharger maintenant » a envoye un `If-None-Match` : le "
            "serveur repondra `304` et le bouton ne retelechargera RIEN, tout "
            "en affichant que tout va bien")
        assert m["forceSansDepuis"] == "true", (
            "la requete forcee porte une chaine de requete : elle demande un "
            "catalogue partiel la ou le bouton promet un catalogue entier")
        assert m["forceAnnonce"] == "true", (
            "la requete forcee n'annonce plus le telephone : la console "
            "cesserait de le voir a chaque fois qu'un juge appuie sur ce bouton")

        # --- A5 et A8, coquille en retard -----------------------------------
        assert "9.9.9" in m["verdictApp"], m["verdictApp"]
        assert m["majVisibleQuandEnRetard"] == "true", (
            "le serveur sert une autre version et le bouton de mise a jour "
            "reste cache : le juge n'a aucun geste a sa portee")

        # --- A7 : hors ligne -------------------------------------------------
        assert "injoignable" in m["messageHorsLigne"].lower(), m["messageHorsLigne"]
        assert m["catalogueIntact"] == "true", (
            "un retelechargement rate a modifie le catalogue local : hors ligne, "
            "le telephone doit garder ce qu'il a")
        assert m["boutonEncoreUtilisable"] == "true"
