"""Les trois gestes de la liste, dans un vrai navigateur — spec 008.

⚠️ **Ce que ce fichier ferme, et qu'aucun test de route ne peut voir.** Les
trois gestes de la spec 008 côté console sont *visuels* : une pastille de
source colorée, un mode de sélection qui doit se reconnaître sans qu'une phrase
l'explique, une ligne qui s'ouvre sur place. Un test de route dirait que
`/admin/participants` rend bien `sources: ["classeur"]` — et la pastille
pourrait n'avoir aucun fond.

Ce n'est pas une hypothèse : c'est arrivé le 04/09 pendant l'écriture. La classe
CSS était déduite de la première lettre du nom de la source, or « classeur »
commence par un `c` et donnait `.src.c`, qui n'existe pas. La pastille `G`
s'affichait sans fond, et **tous les tests passaient**.

## Un seul parcours, qui mesure tout

La sonde traverse les trois écrans **en une passe** et poste un verdict unique ;
les tests ne font que lire le dictionnaire. C'est ce qui rend la portée
`module` légitime au regard de `test_harnais_navigateur.py` : on ne partage pas
un parcours qui devrait varier, on fait un relevé unique.

Un test dédié vérifie qu'aucune mesure ne **manque** du verdict. Sans lui, une
sonde qui casse à mi-parcours rendrait un verdict court, et tous les tests
suivants passeraient en silence sur les mesures déjà là.
"""
import os
import shutil
import tempfile
from datetime import date

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")

ECRAN = (1280, 1400)
MDP = "un-mot-de-passe-assez-long"

#: Toutes les mesures que la sonde doit poser. Le test de completude s'en sert.
ATTENDUES = (
    "fondG fondH fondM lettresLea "
    "selectionAvant selectionApres bandeVisible casesVisibles "
    "toutCoche prisesTeintees "
    "editionOuverte champsDansLaLigne bordureOcre "
    "baremeReference baremeU13 apercuChangements"
).split()

SONDE = r"""
    const doc = () => cadre.contentDocument;
    const fond = (el) => el ? vue().getComputedStyle(el).backgroundColor : "absent";
    const visible = (el) => !!(el && el.offsetParent !== null);

    // --- Connexion ------------------------------------------------------
    await attendre("formulaire de connexion", () => $("#identifiant") !== null);
    $("#identifiant").value = "chef";
    $("#motdepasse").value = "un-mot-de-passe-assez-long";
    $("#formConnexion").dispatchEvent(new (vue().Event)("submit", {cancelable: true}));
    await attendre("liste chargee",
      () => $("#listeParticipants") && $("#listeParticipants").children.length >= 3);

    // --- 1. Les pastilles de source ------------------------------------
    // On lit le FOND CALCULE, pas la classe : c'est la seule mesure qui aurait
    // attrape le defaut du 04/09.
    note("fondG", fond($("#listeParticipants .src.g")));
    note("fondH", fond($("#listeParticipants .src.h")));
    note("fondM", fond($("#listeParticipants .src.m")));
    const ligneLea = $$("#listeParticipants tr").filter(
      (tr) => tr.textContent.indexOf("Brunel") !== -1)[0];
    // ⚠️ `$$` du harnais ne prend QU'UN selecteur : lui passer un element en
    // second argument ne scope rien, et la legende du bas se retrouvait dans
    // le compte. On interroge la ligne elle-meme.
    note("lettresLea", [...ligneLea.querySelectorAll(".src")]
                       .map((s) => s.textContent).join(""));

    // --- 2. Le mode selection -------------------------------------------
    note("selectionAvant", visible($("#bandeSelection")));
    $("#btnSelection").click();
    await attendre("bande affichee", () => visible($("#bandeSelection")));
    note("selectionApres", visible($("#btnSelection")));
    note("bandeVisible", visible($("#bandeSelection")));
    note("casesVisibles", $$('#listeParticipants input[type="checkbox"]').length);

    $("#toutSelectionner").click();
    await attendre("tout coche", () => $$("#listeParticipants tr.prise").length > 0);
    note("toutCoche", $$("#listeParticipants tr.prise").length);
    // La teinte de la ligne retenue : c'est elle qui dit ce qui partira a
    // l'impression, avec la case.
    note("prisesTeintees",
      fond($("#listeParticipants tr.prise td")) !== "rgba(0, 0, 0, 0)");
    $("#btnAnnulerSelection").click();
    await attendre("bande fermee", () => !visible($("#bandeSelection")));

    // --- 3. Le crayon ouvre la ligne ------------------------------------
    $("#listeParticipants .crayon").click();
    await attendre("ligne ouverte", () => $("#listeParticipants tr.edition") !== null);
    const ouverte = $("#listeParticipants tr.edition");
    note("editionOuverte", 1);
    note("champsDansLaLigne", ouverte.querySelectorAll("input, select").length);
    // Le lisere ocre a gauche : de loin, on voit LAQUELLE est modifiee.
    note("bordureOcre",
      vue().getComputedStyle(ouverte.querySelector("td")).boxShadow !== "none");

    // --- 4. Le bareme ----------------------------------------------------
    $('[data-vue="categories"]').click();
    await attendre("bareme charge",
      () => $("#listeBareme") && $("#listeBareme").children.length > 0);
    note("baremeReference", $("#etatBareme").textContent.indexOf("2027") !== -1);
    const lignes = $$("#listeBareme tr").map((tr) => tr.textContent);
    note("baremeU13", lignes.filter((t) => t.indexOf("2015") !== -1
                                        && t.indexOf("2016") !== -1).length);

    $("#btnApercuBareme").click();
    await attendre("apercu rendu",
      () => $("#apercuBareme") && !$("#apercuBareme").hidden
         && $("#apercuBareme").textContent.length > 20);
    note("apercuChangements", $$("#apercuBareme tbody tr").length);
"""


@pytest.fixture(scope="module")
def serveur():
    """La console, avec trois participants de trois origines différentes.

    ⚠️ PORTÉE MODULE. La sonde ne fait qu'un seul parcours et le relevé est lu
    en lecture seule par tous les tests : en portée fonction, chacun
    relancerait un chromium pour rejouer exactement le même parcours — le
    défaut que `test_harnais_navigateur.py` interdit.
    """
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-008-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import comptes, creer_app
    from climbcontest.config import Config
    from climbcontest.extensions import db
    from climbcontest.models import (
        A_IMPRIMER, Circuit, Competition, EN_COURS, Inscription, Participant,
        SOURCE_CLASSEUR, SOURCE_HELLOASSO, SOURCE_MANUEL,
    )

    class ConfigConsole(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "console.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigConsole)
    app.config["SECRET_KEY"] = "une-cle-de-test-suffisamment-longue"

    with app.app_context():
        comptes.creer("chef", MDP, [comptes.ADMIN])
        comp = Competition(nom="Bloc Party 2026", date=date(2026, 11, 15),
                           statut=EN_COURS, active=True)
        db.session.add(comp)
        db.session.commit()
        for nom in ("U11", "U13", "U15"):
            db.session.add(Circuit(competition_id=comp.id, nom=nom))
        # Lea vient du classeur, et une inscription HelloAsso s'est rattachee
        # a elle : DEUX pastilles sur sa ligne, ce qui est la preuve visible
        # que le rapprochement a fait son travail.
        #
        # Son annee dit U13, sa categorie dit U15 -- c'est elle que l'apercu du
        # bareme doit proposer de recalculer.
        db.session.add_all([
            Participant(competition_id=comp.id, nom="Brunel", prenom="Lea",
                        club="Annonay Escalade", categorie="U15 F", dossard=47,
                        annee_naissance=2015, source=SOURCE_CLASSEUR),
            Participant(competition_id=comp.id, nom="Chapuis", prenom="Nino",
                        club="Annonay Escalade", categorie="U11 H", dossard=128,
                        annee_naissance=2018, source=SOURCE_HELLOASSO),
            Participant(competition_id=comp.id, nom="Peyron", prenom="Sacha",
                        club="CAF Vivarais", categorie="U15 H", dossard=131,
                        annee_naissance=2013, source=SOURCE_MANUEL),
        ])
        db.session.commit()

        lea = Participant.query.filter_by(nom="Brunel").one()
        db.session.add(Inscription(
            competition_id=comp.id, article_id=8868047, commande_id=8868440,
            etat=A_IMPRIMER, participant_id=lea.id, nom="Brunel", prenom="Lea",
            club="Annonay Escalade", categorie="U13 F", annee_naissance=2015,
            etat_helloasso="Processed"))
        db.session.commit()

    verdict = {"texte": None}

    @app.post("/__verdict")
    def poser():
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    @app.get("/__harnais")
    def harnais():
        return Response(page_harnais("/console", SONDE, taille=ECRAN),
                        mimetype="text/html")

    url, arreter = servir(app)
    try:
        yield url, verdict
    finally:
        arreter()
        shutil.rmtree(dossier, ignore_errors=True)


@pytest.fixture(scope="module")
def mesures(serveur):
    """Le parcours des trois écrans, joué UNE FOIS pour tout le fichier."""
    url, verdict = serveur
    rendu = piloter(f"{url}/__harnais", verdict)
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestLeReleveEstComplet:
    def test_aucune_mesure_ne_manque(self, mesures):
        """Sans ce test, une sonde qui casse à mi-parcours rendrait un verdict
        court et tous les tests suivants passeraient en silence."""
        manquantes = [nom for nom in ATTENDUES if nom not in mesures]
        assert not manquantes, f"la sonde s'est arretee : {manquantes}"


class TestLesPastillesDeSource:
    """Le défaut du 04/09 : une classe déduite du nom, donc `.src.c`."""

    @pytest.mark.parametrize("mesure", ["fondG", "fondH", "fondM"])
    def test_chaque_pastille_a_un_fond(self, mesures, mesure):
        fond = mesures[mesure]
        assert fond not in ("absent", "rgba(0, 0, 0, 0)", "transparent"), (
            f"{mesure} sans fond : la pastille est illisible")

    def test_les_trois_fonds_sont_differents(self, mesures):
        """Trois sources, trois couleurs : sinon la colonne n'apprend rien."""
        assert len({mesures["fondG"], mesures["fondH"], mesures["fondM"]}) == 3

    def test_deux_sources_sur_une_meme_ligne(self, mesures):
        """Le rapprochement a fait son travail : cette personne n'a pas été
        dupliquée, et ça se voit."""
        assert mesures["lettresLea"] == "GH"


class TestLeModeSelection:
    def test_la_bande_est_cachee_au_depart(self, mesures):
        assert mesures["selectionAvant"] == "false"

    def test_le_bouton_laisse_la_place_a_la_bande(self, mesures):
        assert mesures["selectionApres"] == "false"
        assert mesures["bandeVisible"] == "true"

    def test_une_case_par_ligne(self, mesures):
        assert int(mesures["casesVisibles"]) == 3

    def test_tout_selectionner_prend_tout_l_affiche(self, mesures):
        assert int(mesures["toutCoche"]) == 3

    def test_les_lignes_retenues_sont_teintees(self, mesures):
        """La teinte et la case disent ensemble ce qui partira à l'impression.
        Aucune phrase ne l'explique — un mode se montre."""
        assert mesures["prisesTeintees"] == "true"


class TestLeCrayon:
    def test_la_ligne_s_ouvre_sur_place(self, mesures):
        assert mesures["editionOuverte"] == "1"

    def test_les_champs_sont_dans_la_ligne(self, mesures):
        """Dossard, nom, année, club, catégorie : cinq champs, pas une fenêtre."""
        assert int(mesures["champsDansLaLigne"]) >= 5

    def test_la_ligne_ouverte_porte_son_lisere(self, mesures):
        assert mesures["bordureOcre"] == "true"


class TestLeBareme:
    def test_la_saison_est_celle_qui_finit(self, mesures):
        """Compétition de novembre 2026 : la référence est 2027."""
        assert mesures["baremeReference"] == "true"

    def test_u13_couvre_2015_et_2016(self, mesures):
        """La correction du 04/09 : le barème prenait l'année où la saison
        commence, et se trompait donc d'un an."""
        assert int(mesures["baremeU13"]) == 1

    def test_l_apercu_montre_la_ligne_a_recalculer(self, mesures):
        """Léa est en U15 F et son année dit U13 : une seule ligne change."""
        assert int(mesures["apercuChangements"]) == 1
