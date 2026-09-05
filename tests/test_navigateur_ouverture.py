"""L'ecran d'ouverture, dans un vrai navigateur (specs 044 et 045).

Ce fichier existe pour ce qu'aucun test de route ne peut voir : le plan
REELLEMENT dessine, le tiroir qui s'ouvre sur la zone qu'on a touchee, le geste
de confirmation, et surtout le TIROIR D'UN COMPTE OUVREUR -- une entree de menu
qui resterait visible ne casse aucune requete, elle invite seulement a en faire
une qui sera refusee.
"""
import os
import shutil
import tempfile
from datetime import date

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")

ECRAN = (1280, 1500)
MDP = "un-mot-de-passe-assez-long"

ATTENDUES = [
    "entreesOuvreur",
    "vueOuverte",
    "planDessine",
    "zonesCliquables",
    "pastilleJ",
    "jaugeJ",
    "tiroirFerme",
    "tiroirOuvert",
    "titreZone",
    "voiesListees",
    "numeroAvant",
    "ficheOuverte",
    "jetonsCouleur",
    "prisesCourantes",
    "numeroApres",
    "pastilleApres",
    "lisereJ",
    "basculeAvant",
    "selecteursAvant",
    "selecteursApres",
    "sousRubriques",
    "nuancierResteOuvert",
    "paireChoisie",
    "apercuPaire",
    "rondBicolore",
    "libelleBicolore",
    "ligneSansMots",
    "renumTitre",
    "gesteRendu",
    "gesteEstMaintien",
]

SONDE = r"""
    const doc = () => cadre.contentDocument;
    const visible = (el) => !!(el && el.offsetParent !== null);

    // --- Connexion d'un OUVREUR ------------------------------------------
    await attendre("formulaire de connexion", () => $("#identifiant") !== null);
    $("#identifiant").value = "marc";
    $("#motdepasse").value = "un-mot-de-passe-assez-long";
    $("#formConnexion").dispatchEvent(new (vue().Event)("submit", {cancelable: true}));
    await attendre("console ouverte", () => visible($("#console")));

    // --- 1. Son tiroir n'a QU'UNE entree ---------------------------------
    // ⚠️ La mesure qui compte de tout ce fichier. Une entree oubliee ne casse
    // aucune requete -- le serveur repond 403 -- mais elle invite a en faire
    // une, et c'est exactement ce qu'un role restreint doit empecher.
    await attendre("vue d'ouverture", () => visible($("#vueOuvreurs")));
    note("entreesOuvreur", $$("#tiroir [data-vue]").filter(visible)
                             .map((b) => b.getAttribute("data-vue")).join(","));
    note("vueOuverte", visible($("#vueOuvreurs")));

    // --- 2. Le plan est dessine, et cliquable ----------------------------
    await attendre("plan monte", () => $("#ouvreursPlan svg") !== null);
    note("planDessine", $$("#ouvreursPlan svg > g[data-zone]").length);
    note("zonesCliquables",
      $$("#ouvreursPlan svg > g[data-zone]").filter(
        (g) => vue().getComputedStyle(g).cursor === "pointer").length);
    // La pastille de la zone J : « complètes / déclarées ». Deux voies
    // posees, une complete.
    const compteJ = $$("#ouvreursPlan .compteurs-zone [data-zone]").filter(
      (g) => g.getAttribute("data-zone") === "J")[0];
    note("pastilleJ", compteJ ? compteJ.querySelector(".compte-zone").textContent : "absent");
    note("jaugeJ", compteJ ? compteJ.querySelector(".remplit-compte").getAttribute("width") : "absent");

    // --- 3. La zone s'ouvre par-dessus le plan ---------------------------
    note("tiroirFerme", visible($("#ouvreursTiroir")));
    const panJ = $$("#ouvreursPlan svg > g[data-zone]").filter(
      (g) => g.getAttribute("data-zone") === "J")[0];
    panJ.dispatchEvent(new (vue().MouseEvent)("click", {bubbles: true}));
    await attendre("tiroir ouvert", () => visible($("#ouvreursTiroir")));
    note("tiroirOuvert", visible($("#ouvreursTiroir")));
    note("titreZone", $("#ouvreursTiroirTitre").firstChild.nodeValue.trim()
                    .replace("Zone ", ""));
    note("voiesListees", $$("#ouvreursListe .ouvreurs-voie").length);

    // --- 4. La fiche, et le numero qui s'attribue ------------------------
    const nue = $$("#ouvreursListe .ouvreurs-voie.incomplete")[0];
    note("numeroAvant", nue.querySelector(".ouvreurs-num").textContent);
    nue.click();
    await attendre("fiche ouverte", () => $("#ouvreursListe .ouvreurs-fiche") !== null);
    note("ficheOuverte", 1);
    note("jetonsCouleur",
      $$("#ouvreursListe .ouvreurs-fiche > div:first-child .ouvreurs-jeton").length);
    note("prisesCourantes",
      $$("#ouvreursListe .ouvreurs-fiche > div:nth-child(2)"
         + " > .ouvreurs-jetons:not(.ouvreurs-nuancier) .ouvreurs-jeton").length);

    // On choisit « Vert » : le numero doit s'attribuer sans rechargement.
    const vert = $$("#ouvreursListe .ouvreurs-jeton").filter(
      (j) => j.textContent.trim() === "Vert")[0];
    vert.click();
    await attendre("numero attribue",
      () => $("#ouvreursListe .ouvreurs-attribue b") !== null);
    note("numeroApres", $("#ouvreursListe .ouvreurs-attribue b").textContent);

    // La pastille de la zone a bouge : deux voies, deux couleurs, mais la
    // seconde n'a pas de categorie -- elle reste incomplete.
    const apres = $$("#ouvreursPlan .compteurs-zone [data-zone]").filter(
      (g) => g.getAttribute("data-zone") === "J")[0];
    note("pastilleApres", apres.querySelector(".compte-zone").textContent);
    // Le liseré ambre : la voie qu'on vient de colorer n'a toujours pas de
    // catégorie, la zone reste « à compléter ».
    note("lisereJ", $$("#ouvreursPlan .cadre-zone").filter(
      (c) => c.getAttribute("data-zone") === "J"
          && c.classList.contains("ouvreurs-a-completer")).length === 1);

    // --- 4 bis. Les prises : l'interrupteur, puis deux selecteurs --------
    const bloc = () => $("#ouvreursListe .ouvreurs-fiche > div:nth-child(2)");
    // ⚠️ On RE-INTERROGE le DOM apres chaque envoi : la fiche est reconstruite
    // a chaque reponse du serveur, et une reference prise avant pointe ensuite
    // sur un noeud detache dont le clic ne fait rien.
    // ⚠️ Et on SCOPE au groupe des prises : « Bleu », « Rouge », « Jaune »,
    // « Noir » et « Vert » existent DEUX FOIS dans la fiche -- en difficulte et
    // en prises. Non scope, le selecteur prenait le premier du DOM.
    const rangs = () => [...bloc().querySelectorAll(".ouvreurs-rang-prise")];
    const dedans = (hote, sel) => [...hote.querySelectorAll(sel)];
    const jetonRang = (indice, mot) =>
      dedans(rangs()[indice], ".ouvreurs-jeton")
        .filter((j) => j.textContent.trim() === mot)[0];

    note("basculeAvant", bloc().querySelector(".ouvreurs-bascule input").checked);
    note("selecteursAvant",
      bloc().querySelectorAll(".ouvreurs-rang-prise").length);

    // Une seule couleur d'abord, dans le premier selecteur.
    jetonRang(0, "Blanc").click();
    await attendre("blanc pose", () => {
      const j = jetonRang(0, "Blanc");
      return j && j.classList.contains("choisi");
    });

    // L'interrupteur ouvre le SECOND selecteur.
    bloc().querySelector(".ouvreurs-bascule input").click();
    await attendre("second selecteur",
      () => bloc().querySelectorAll(".ouvreurs-rang-prise").length === 2);
    note("selecteursApres",
      bloc().querySelectorAll(".ouvreurs-rang-prise").length);
    note("sousRubriques", dedans(bloc(), ".ouvreurs-sous-rub")
      .map((n) => n.textContent.replace(/ /g, "~")).join("+"));

    // DEUX COULEURS PERSONNALISEES : chacune dans son nuancier, et les
    // nuanciers doivent RESTER ouverts entre les deux choix.
    dedans(rangs()[1], ".ouvreurs-jeton")
      .filter((j) => j.textContent.indexOf("Personnaliser") !== -1)[0].click();
    await attendre("nuancier du second ouvert",
      () => !rangs()[1].querySelector(".ouvreurs-nuancier").hidden);
    jetonRang(1, "Marron").click();
    await attendre("marron pose", () => {
      const j = jetonRang(1, "Marron");
      return j && j.classList.contains("choisi");
    });
    note("nuancierResteOuvert",
      !rangs()[1].querySelector(".ouvreurs-nuancier").hidden);
    note("paireChoisie", dedans(bloc(), ".ouvreurs-jeton.choisi")
      .map((j) => j.textContent.trim())
      .filter((t) => t.indexOf("Personnaliser") === -1).join("+"));
    note("apercuPaire", bloc().querySelector(".ouvreurs-valeur-prise")
      .textContent.replace(/ /g, "~"));

    // --- 4 ter. Ce que la LIGNE montre, une fois la fiche refermee --------
    $("#ouvreursListe .ouvreurs-fiche .ouvreurs-actions button.secondaire").click();
    await attendre("retour a la zone",
      () => $("#ouvreursListe .ouvreurs-voie") !== null);
    // On remonte de la pastille a SA ligne : filtrer les lignes sur le titre de
    // leur pastille demanderait un `querySelector` par ligne, et une ligne sans
    // prise n'en a pas.
    const rondBi = $$("#ouvreursListe .ouvreurs-rond-prise").filter(
      (r) => (r.getAttribute("title") || "") === "Prises : Blanc et Marron")[0];
    const bicolore = rondBi.closest(".ouvreurs-voie");
    note("rondBicolore", vue().getComputedStyle(rondBi)
      .backgroundImage.indexOf("linear-gradient") === 0);
    note("libelleBicolore", rondBi.getAttribute("title").replace(/ /g, "~"));
    // La ligne ne doit porter AUCUNE couleur en toutes lettres, ni le contenu
    // du QR : « ca n'apporte rien ici » (05/09).
    note("ligneSansMots", ["Blanc", "Marron", "Vert", "QR "].filter(
      (m) => bicolore.textContent.indexOf(m) !== -1).join(",") || "aucun");

    // --- 5. Le geste de confirmation -------------------------------------
    $("#ouvreursFermerTiroir").click();
    await attendre("tiroir referme", () => !visible($("#ouvreursTiroir")));
    $("#ouvreursRenumeroter").click();
    await attendre("boite ouverte",
      () => $("#ouvreursDlgRenum") && $("#ouvreursDlgRenum").open);
    note("renumTitre", $("#ouvreursRenumTitre").textContent.indexOf("Renuméroter") === 0);
    note("gesteRendu", $("#ouvreursRenumGeste").children.length);
    // Le navigateur de test a une souris : c'est le MAINTIEN qui doit sortir,
    // pas le glissement. C'est le pointeur qui decide, pas la largeur.
    note("gesteEstMaintien",
      $("#ouvreursRenumGeste button.detruire") !== null);
"""


@pytest.fixture(scope="module")
def serveur():
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-044-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import comptes, creer_app, ouverture, sans_classeur
    from climbcontest.config import Config
    from climbcontest.extensions import db
    from climbcontest.models import Circuit, Competition, PREPARATION

    class ConfigConsole(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "console.db")
        SHEETS_ACTIF = False
        API_KEY_STRICTE = False
        SESSION_COOKIE_SECURE = False

    app = creer_app(ConfigConsole)
    app.config["SECRET_KEY"] = "une-cle-de-test-suffisamment-longue"

    with app.app_context():
        comptes.creer("marc", MDP, [comptes.OUVREUR])
        comp = Competition(nom="Bloc Party 2026", date=date(2026, 11, 15),
                           statut=PREPARATION, active=True)
        db.session.add(comp)
        db.session.commit()
        db.session.add(Circuit(competition_id=comp.id, nom="U11"))
        db.session.commit()
        sans_classeur.basculer(True, par="test")
        # Zone J : une voie complete, une voie nue. La pastille doit dire 1/2.
        faite = ouverture.creer(comp, "J")
        ouverture.modifier(comp, faite, couleur="Jaune", couleur_prises="Fluo",
                           circuits=["U11"])
        ouverture.creer(comp, "J")

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
    url, verdict = serveur
    rendu = piloter(f"{url}/__harnais", verdict)
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestLeReleveEstComplet:
    def test_toutes_les_mesures_sont_la(self, mesures):
        """Sans lui, une sonde qui casse a mi-parcours rendrait un verdict
        court et tous les tests suivants passeraient en silence."""
        assert sorted(mesures) == sorted(ATTENDUES)


class TestCeQueVoitUnOuvreur:
    def test_son_tiroir_n_a_qu_une_entree(self, mesures):
        """⚠️ La mesure qui compte. `ouvreur` est le premier role RESTREINT du
        depot : tout le reste doit disparaitre, pas seulement etre refuse."""
        assert mesures["entreesOuvreur"] == "ouvreurs"

    def test_l_ecran_d_ouverture_s_ouvre_seul(self, mesures):
        assert mesures["vueOuverte"] == "true"


class TestLePlan:
    def test_les_dix_sept_zones_sont_dessinees(self, mesures):
        assert int(mesures["planDessine"]) == 17

    def test_chaque_zone_est_cliquable(self, mesures):
        assert int(mesures["zonesCliquables"]) == 17

    def test_la_pastille_compte_les_voies_declarees(self, mesures):
        """⚠️ UN COMPTE, PAS UN AVANCEMENT (05/09). Deux voies en zone J : la
        pastille dit « 2 ». Elle disait « 1/2 » et se remplissait de vert --
        une jauge suppose un total connu d'avance, et les ouvreurs ne savent
        pas ce qu'ils vont ouvrir ni ou."""
        assert mesures["pastilleJ"] == "2"

    def test_la_jauge_verte_a_disparu(self, mesures):
        assert mesures["jaugeJ"] == "0"


class TestLeTiroir:
    def test_il_est_ferme_au_depart(self, mesures):
        assert mesures["tiroirFerme"] == "false"

    def test_toucher_une_zone_l_ouvre_sur_elle(self, mesures):
        assert mesures["tiroirOuvert"] == "true"
        assert mesures["titreZone"] == "J"

    def test_il_liste_les_voies_de_la_zone(self, mesures):
        assert int(mesures["voiesListees"]) == 2


class TestLaFiche:
    def test_elle_s_ouvre_sur_la_voie_touchee(self, mesures):
        assert mesures["ficheOuverte"] == "1"

    def test_les_six_couleurs_sont_proposees(self, mesures):
        assert int(mesures["jetonsCouleur"]) == 6


    def test_une_voie_nue_n_a_pas_de_numero(self, mesures):
        assert mesures["numeroAvant"] == "—"

    def test_choisir_une_couleur_attribue_le_numero(self, mesures):
        """Sans rechargement, et la fiche reste ouverte sur la meme voie."""
        assert mesures["numeroApres"] == "V1"

    def test_la_pastille_de_la_zone_ne_bouge_pas(self, mesures):
        """Le compte ne depend pas de ce qui est rempli : deux voies restent
        deux voies."""
        assert mesures["pastilleApres"] == "2"

    def test_la_zone_porte_son_lisere_ambre(self, mesures):
        """Une voie declaree a laquelle il manque une categorie."""
        assert mesures["lisereJ"] == "true"


class TestLInterrupteurBicolore:
    """⚠️ L'interrupteur REMPLACE un plafond implicite. La premiere version
    faisait de la rangee un choix multiple plafonne a deux : au deuxieme jeton,
    tous les autres devenaient inertes. Rien n'annoncait le plafond avant de le
    heurter, on ne savait pas laquelle des deux on changeait, et rien ne disait
    qu'une prise bicolore existe."""

    def test_il_est_eteint_et_un_seul_selecteur_s_affiche(self, mesures):
        assert mesures["basculeAvant"] == "false"
        assert int(mesures["selecteursAvant"]) == 1

    def test_l_allumer_ouvre_un_SECOND_selecteur(self, mesures):
        assert int(mesures["selecteursApres"]) == 2

    def test_chaque_couleur_a_son_selecteur_nomme(self, mesures):
        """On sait toujours laquelle des deux on modifie."""
        assert mesures["sousRubriques"] == "Première~couleur+Seconde~couleur"

    def test_deux_couleurs_PERSONNALISEES_marchent(self, mesures):
        """La question du 05/09 : « est-ce que ca fonctionne le bicolore avec
        2 couleurs personnalisees ? »"""
        assert mesures["paireChoisie"] == "Blanc+Marron"

    def test_le_nuancier_reste_ouvert_entre_les_deux_choix(self, mesures):
        """⚠️ Il se refermait : chaque choix declenche un aller-retour serveur
        et reconstruit la fiche. Il fallait rouvrir « Personnaliser… » entre les
        deux -- justement dans le cas ou l'on en a le plus besoin."""
        assert mesures["nuancierResteOuvert"] == "true"

    def test_l_apercu_nomme_la_paire(self, mesures):
        assert mesures["apercuPaire"] == "Blanc~et~Marron"


class TestUnePriseBicolore:

    def test_le_disque_est_coupe_en_deux(self, mesures):
        """Une coupe FRANCHE : deux teintes qui se fondent en font une
        troisieme, et on chercherait sur le mur une couleur qui n'existe pas."""
        assert mesures["rondBicolore"] == "true"

    def test_la_pastille_nomme_les_deux_couleurs_au_survol(self, mesures):
        """La ligne ne les ECRIT plus, mais l'information ne disparait pas :
        sans `title` ni `aria-label`, la couleur ne serait plus dite QUE par la
        couleur -- illisible pour qui ne les distingue pas, muet pour un
        lecteur d'ecran."""
        assert mesures["libelleBicolore"] == "Prises~:~Blanc~et~Marron"

    def test_la_ligne_ne_porte_plus_de_couleur_ni_de_qr(self, mesures):
        """« ca n'apporte rien ici » : la pastille dit deja la couleur, et
        « V8 » porte l'initiale de sa difficulte."""
        assert mesures["ligneSansMots"] == "aucun"


class TestLeGesteDeConfirmation:
    def test_la_boite_de_renumerotation_s_ouvre(self, mesures):
        assert mesures["renumTitre"] == "true"

    def test_le_geste_est_rendu(self, mesures):
        assert int(mesures["gesteRendu"]) == 1

    def test_a_la_souris_c_est_le_maintien(self, mesures):
        """C'est le POINTEUR qui decide, pas la largeur de l'ecran."""
        assert mesures["gesteEstMaintien"] == "true"
