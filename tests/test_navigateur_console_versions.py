"""Le pied du tiroir de la console, et la phrase du rattrapage — criteres A9 et
A18 de la spec 030, dans un vrai navigateur.

⚠️ **Le defaut que ce fichier ferme.** A9 promet que le pied du tiroir affiche
la version **et le numero de catalogue**, « sur tous les ecrans ». Ce n'etait
vrai qu'apres avoir ouvert l'ecran « Telephones » : le numero vient de
`/admin/versions`, que seule la fonction de cet ecran appelait. Un organisateur
qui ouvrait la console et restait sur « Participants » lisait un pied a moitie
rempli -- et rien ne lui disait ou aller le chercher.

Le test mesure donc **sans jamais ouvrir l'ecran Telephones**. C'est tout
l'interet : un test qui commencerait par cliquer partout ne verrait rien.

A18 tient la formulation. La phrase du rattrapage doit NOMMER le geste qui
debloque un telephone en veille -- « rallumer son ecran ». Une phrase qui se
contenterait de dire « ca se repare tout seul » serait fausse pour la moitie
des telephones concernes : la boucle de l'application ne tourne pas quand
l'ecran est eteint, et ceux-la attendent quelqu'un.
"""
import os
import shutil
import tempfile
from datetime import date, datetime, timedelta

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")

MDP = "un-mot-de-passe-assez-long"

# ⚠️ Un ECRAN, pas un telephone : le tiroir -- donc son pied -- n'est epingle
# qu'au-dela de 1080 px (spec 021). Meme constante que
# `test_navigateur_console_fermee.py`, pour la meme raison.
ECRAN = (1440, 900)


SONDE = """
    await attendre("formulaire de connexion", () => $("#formConnexion"));
    $("#identifiant").value = "orga";
    $("#motdepasse").value = "un-mot-de-passe-assez-long";
    // `requestSubmit()` declenche le vrai evenement `submit`, celui que la
    // console ecoute -- `submit()` le contournerait, et un `new Event` doit se
    // construire dans la fenetre du cadre, pas dans celle du pilote.
    $("#formConnexion").requestSubmit();
    await attendre("console ouverte",
      () => $("#console") && !$("#console").hasAttribute("hidden"));

    // ⚠️ On ne clique NULLE PART. C'est la situation d'un organisateur qui vient
    // d'entrer son mot de passe et regarde son ecran d'arrivee.
    note("vueDArrivee", $(".vue:not([hidden])") ? $(".vue:not([hidden])").id : "aucune");

    const pied = () => $("#versionConsole").textContent.trim().replace(/\\s+/g, "_");
    note("piedTouteDeSuite", pied());
    // ⚠️ On ATTEND sans exiger. Une attente qui leve rendrait « delai sur pied
    // complet » -- vrai, mais muet : c'est l'assertion Python qui doit dire ce
    // qu'elle a lu et pourquoi ca compte. Huit secondes suffisent largement
    // pour une requete locale de 200 octets.
    let complet = false;
    for (let i = 0; i < 80 && !complet; i++) {
      await new Promise((r) => setTimeout(r, 100));
      complet = /catalogue/.test($("#versionConsole").textContent);
    }
    note("piedApresChargement", pied());
    note("ecranTelephonesJamaisOuvert",
      $("#vueAppareils") === null || $("#vueAppareils").hasAttribute("hidden"));

    // --- A18 : la phrase du rattrapage nomme le geste ----------------------
    [...$$(".tiroir nav button")].find((b) => /Téléphones/.test(b.textContent)).click();
    let phrase = "";
    for (let i = 0; i < 80 && !phrase; i++) {
      await new Promise((r) => setTimeout(r, 100));
      const p = $("#rattrapageAnnonces");
      if (p && !p.hasAttribute("hidden")) phrase = p.textContent.trim();
    }
    note("rattrapage", phrase.replace(/\\s+/g, "_") || "aucune");
"""


@pytest.fixture()
def serveur():
    """Une console, un compte, et un telephone en train de rattraper.

    Le telephone porte un numero de catalogue **anterieur** a celui du serveur
    et s'est annonce il y a une minute : c'est exactement l'etat de toute une
    flotte dans les minutes qui suivent un import ou un plan redessine.
    """
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-console-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import comptes, creer_app
    from climbcontest.config import Config
    from climbcontest.extensions import db
    from climbcontest.models import Appareil, Competition, EN_COURS, Participant

    class ConfigConsole(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "c.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigConsole)
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"

    with app.app_context():
        comp = Competition(nom="Contest de test", date=date.today(),
                           statut=EN_COURS, active=True)
        db.session.add(comp)
        db.session.flush()
        db.session.add(Participant(competition_id=comp.id, nom="Dupont",
                                   prenom="Lea", club="Les Lezards",
                                   categorie="U13 F", dossard=1, present=True))
        maintenant = datetime.now()
        db.session.add(Appareil(
            id="aaaa-1111-bbbb-2222", nom="Zone A", version_app="dev",
            catalogue_version=comp.catalogue_version - 1,
            catalogue_vu_le=maintenant - timedelta(minutes=1),
            vu_le=maintenant - timedelta(minutes=1),
            premiere_vue_le=maintenant - timedelta(hours=2)))
        comptes.creer("orga", MDP, [comptes.ADMIN])
        db.session.commit()

    verdict = {"texte": None}

    @app.post("/__verdict")
    def _poser():
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    @app.get("/__harnais")
    def _harnais():
        # ⚠️ Un ECRAN, pas un telephone : le tiroir -- donc son pied -- n'est
        # epingle qu'au-dela de 1080 px (spec 021). Dans un cadre de 390 px, ce
        # test mesurerait un element qui n'est pas affiche.
        return Response(page_harnais("/console", SONDE, taille=ECRAN),
                        mimetype="text/html")

    url, arreter = servir(app)
    try:
        yield url, verdict
    finally:
        arreter()
        shutil.rmtree(dossier, ignore_errors=True)


def _mesures(rendu):
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestLePiedDuTiroirEstCompletDesLOuverture:

    def test_le_numero_de_catalogue_sans_passer_par_les_telephones(self, serveur):
        url, verdict = serveur
        m = _mesures(piloter(f"{url}/__harnais", verdict, taille=ECRAN))

        assert m["ecranTelephonesJamaisOuvert"] == "true", (
            "le test a ouvert l'ecran Telephones avant de mesurer : il ne "
            "prouve plus rien, puisque c'est cet ecran qui remplissait le pied")
        assert "catalogue" in m["piedApresChargement"], (
            f"le pied du tiroir dit « {m['piedApresChargement']} » : le numero "
            "de catalogue n'arrive pas sans passer par l'ecran Telephones. "
            "C'est le defaut du 04/09 -- `chargerVersions()` n'est appelee qu'a "
            "l'ouverture de cet ecran-la")
        assert "ClimbContest" in m["piedApresChargement"]
        assert "n°" in m["piedApresChargement"]


class TestLaPhraseDuRattrapageNommeLeGeste:

    def test_elle_dit_quoi_faire_pour_un_telephone_en_veille(self, serveur):
        url, verdict = serveur
        m = _mesures(piloter(f"{url}/__harnais", verdict, taille=ECRAN))

        phrase = m["rattrapage"].replace("_", " ")
        assert "rallume" in phrase, (
            f"la phrase du rattrapage est « {phrase} » : elle ne nomme plus le "
            "geste qui debloque un telephone en veille. Une phrase qui promet "
            "que « ca se repare tout seul » est fausse pour la moitie des "
            "telephones concernes -- ecran eteint, la boucle ne tourne pas")
        assert "écran" in phrase or "ecran" in phrase
