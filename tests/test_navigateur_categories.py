"""La console, telle qu'un organisateur la voit — spec 045.

Ce que les tests d'API ne peuvent pas dire : combien d'entrées porte la liste
déroulante, si « ＋ Autre… » a bien disparu, si le panneau s'ouvre sur la
catégorie en cours, et si les interrupteurs sont bien des interrupteurs.

⚠️ **Un seul harnais, un seul parcours** (`test_harnais_navigateur.py`
l'impose) : la sonde relève tout d'un coup, les tests lisent le relevé.
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

#: Toutes les mesures que la sonde doit poser. Le test de complétude s'en sert.
ATTENDUES = (
    "optionsAjout autreDansAjout premiereAjout "
    "optionsCrayon autreDansCrayon valeurCrayon horsListeEnTete "
    "libelleAccentue valeurSansAccent "
    "lignesBareme interrupteurs roleSwitch anneesU13 inscritsU13 grisees "
    "carteHorsListe texteHorsListe cibleHorsListe"
).split()

SONDE = r"""
    const doc = () => cadre.contentDocument;

    // --- Connexion ------------------------------------------------------
    await attendre("formulaire de connexion", () => $("#identifiant") !== null);
    $("#identifiant").value = "chef";
    $("#motdepasse").value = "un-mot-de-passe-assez-long";
    $("#formConnexion").dispatchEvent(new (vue().Event)("submit", {cancelable: true}));
    await attendre("liste chargee",
      () => $("#listeParticipants") && $("#listeParticipants").children.length >= 2);

    // --- 1. Le formulaire d'ajout ---------------------------------------
    const ajout = $("#pCategorie");
    note("optionsAjout", ajout.options.length);
    note("autreDansAjout", [...ajout.options].some((o) => o.value === "__autre__"));
    note("premiereAjout", ajout.options[1].value);
    // Ce qu'on AFFICHE peut differer de ce qu'on STOCKE : « Senior » en base,
    // « Senior » accentue a l'ecran.
    const senior = [...ajout.options].filter((o) => o.value === "Senior F")[0];
    note("valeurSansAccent", senior.value);
    note("libelleAccentue", senior.textContent);

    // --- 2. Le crayon, sur la ligne qui porte « U13 M » ------------------
    const ligneM = $$("#listeParticipants tr").filter(
      (tr) => tr.textContent.indexOf("Chapuis") !== -1)[0];
    ligneM.querySelector(".crayon").click();
    await attendre("ligne ouverte", () => $("#listeParticipants tr.edition") !== null);
    const ouverte = $("#listeParticipants tr.edition");
    const liste = [...ouverte.querySelectorAll("select")].filter(
      (s) => [...s.options].some((o) => o.value === "U13 F"))[0];
    note("optionsCrayon", liste.options.length);
    note("autreDansCrayon", [...liste.options].some((o) => o.value === "__creer__"));
    // ⚠️ La mesure qui compte : la valeur COURANTE est posee. Sans elle, le
    // panneau s'ouvrirait sur la premiere option et enregistrer changerait la
    // categorie de quelqu'un sans que personne ne l'ait demande.
    note("valeurCrayon", liste.value);
    note("horsListeEnTete", liste.options[1].textContent);

    // --- 3. L'ecran Categories ------------------------------------------
    $('[data-vue="categories"]').click();
    await attendre("tableau charge",
      () => $("#listeBareme") && $("#listeBareme").children.length > 0);
    note("lignesBareme", $$("#listeBareme tr").length);
    note("interrupteurs", $$('#listeBareme td.col-genre input[type="checkbox"]').length);
    note("roleSwitch",
      $$('#listeBareme td.col-genre input[role="switch"]').length);

    const ligneU13 = $$("#listeBareme tr").filter(
      (tr) => tr.children[0].textContent.trim() === "U13")[0];
    note("anneesU13", ligneU13.children[1].textContent.replace(/\s/g, ""));
    note("inscritsU13", ligneU13.children[3].textContent);
    // Ce que l'edition ne fait pas grimper est grise : sans ca, « U9 jusqu'a
    // 8 ans » et « U11 jusqu'a 10 ans » se lisent comme deux regles qui se
    // contredisent.
    note("grisees", $$("#listeBareme tr.sans-bareme").length);

    // --- 4. La carte de rattrapage ---------------------------------------
    note("carteHorsListe", !$("#carteHorsListe").hidden);
    const premiere = $("#listeHorsListe").children[0];
    note("texteHorsListe", premiere.children[0].textContent);
    note("cibleHorsListe", premiere.children[1].textContent.replace(/\s/g, ""));
"""


@pytest.fixture(scope="module")
def serveur():
    """La console, avec un grimpeur qui porte « U13 M » — le cas du 30/08.

    ⚠️ PORTÉE MODULE : la sonde ne fait qu'un parcours, et le relevé est lu en
    lecture seule par tous les tests.
    """
    from flask import Response, request

    dossier = tempfile.mkdtemp(prefix="climbcontest-045-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import comptes, creer_app
    from climbcontest.config import Config
    from climbcontest.extensions import db
    from climbcontest.models import (
        Circuit, Competition, EN_COURS, Participant, SOURCE_CLASSEUR)

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
        for nom in ("U11", "U13"):
            db.session.add(Circuit(competition_id=comp.id, nom=nom))
        db.session.add_all([
            Participant(competition_id=comp.id, nom="Brunel", prenom="Lea",
                        club="Annonay Escalade", categorie="U13 F", dossard=47,
                        annee_naissance=2015, source=SOURCE_CLASSEUR),
            # ⚠️ Ecrit DIRECTEMENT en base, sans passer par le formatage : on
            # rejoue une base d'avant la spec 045, pas une saisie d'aujourd'hui.
            Participant(competition_id=comp.id, nom="Chapuis", prenom="Nino",
                        club="Annonay Escalade", categorie="U13 M", dossard=128,
                        annee_naissance=2015, source=SOURCE_CLASSEUR),
        ])
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


def texte(mesures, cle):
    """La valeur d'une mesure, espaces rendus.

    ⚠️ Le harnais separe les mesures par des ESPACES : il remplace donc ceux
    qu'une valeur contient par des « _ ». « U13 M » revient « U13_M ». Comparer
    sans le savoir donne un echec incomprehensible.
    """
    return mesures[cle].replace("_", " ")


@pytest.fixture(scope="module")
def mesures(serveur):
    url, verdict = serveur
    rendu = piloter(f"{url}/__harnais", verdict)
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestLeReleveEstComplet:
    def test_aucune_mesure_ne_manque(self, mesures):
        manquantes = [nom for nom in ATTENDUES if nom not in mesures]
        assert not manquantes, f"la sonde s'est arretee : {manquantes}"


class TestLeFormulaireDAjout:
    def test_dix_huit_categories_plus_le_vide(self, mesures):
        assert int(mesures["optionsAjout"]) == 19

    def test_plus_d_autre(self, mesures):
        """C'est « ＋ Autre… » qui a laissé naître « U13 M »."""
        assert mesures["autreDansAjout"] == "false"

    def test_l_ordre_est_celui_de_la_federation(self, mesures):
        """U9 d'abord — pas l'ordre alphabétique, qui mettrait U11 après
        Senior et U9 après U21."""
        assert texte(mesures, "premiereAjout") == "U9 F"

    def test_accentue_a_l_ecran_sans_accent_en_base(self, mesures):
        assert texte(mesures, "valeurSansAccent") == "Senior F"
        assert texte(mesures, "libelleAccentue") == "Sénior F"


class TestLeCrayon:
    def test_la_meme_liste_plus_la_valeur_hors_liste(self, mesures):
        """18 officielles + le vide + « U13 M » que ce grimpeur porte."""
        assert int(mesures["optionsCrayon"]) == 20

    def test_plus_de_creation(self, mesures):
        assert mesures["autreDansCrayon"] == "false"

    def test_il_s_ouvre_sur_la_categorie_en_cours(self, mesures):
        """⚠️ La mesure la plus importante du fichier.

        Sans `select.value` posé avant l'affichage, le panneau s'ouvrirait sur
        la première option — et enregistrer changerait la catégorie de ce
        grimpeur sans que personne ne l'ait demandé.
        """
        assert texte(mesures, "valeurCrayon") == "U13 M"

    def test_et_elle_est_marquee(self, mesures):
        assert texte(mesures, "horsListeEnTete") == "U13 M (hors liste)"


class TestLEcranCategories:
    def test_neuf_lignes(self, mesures):
        assert int(mesures["lignesBareme"]) == 9

    def test_dix_huit_interrupteurs(self, mesures):
        """Deux par ligne, dans le MÊME tableau que les années : c'est la
        fusion des deux cartes demandée le 05/09."""
        assert int(mesures["interrupteurs"]) == 18

    def test_ce_sont_des_interrupteurs_pas_des_cases(self, mesures):
        """`role="switch"` : le lecteur d'écran annonce « interrupteur ».
        La case native reste dessous, avec le clavier et le focus."""
        assert int(mesures["roleSwitch"]) == 18

    def test_les_annees_sont_celles_de_la_saison(self, mesures):
        """Compétition du 15/11/2026 → référence 2027 → U13 = 2015-2016."""
        assert mesures["anneesU13"] == "2015–2016"

    def test_le_compte_d_inscrits_est_dans_la_meme_ligne(self, mesures):
        """« U13 F » et « U13 M » : deux personnes, une seule ligne U13."""
        assert mesures["inscritsU13"] == "1"


class TestCeQueLEditionNeFaitPasGrimper:
    def test_les_lignes_eteintes_sont_grisees(self, mesures):
        """Deux circuits (U11, U13) et deux categories portees (U13 F, U13 M) :
        le bareme de cette edition tient en U11 et U13. Les sept autres lignes
        montrent ce qu'elles DEVIENDRAIENT, et le disent en grise."""
        assert int(mesures["grisees"]) == 7


class TestLaCarteDeRattrapage:
    def test_elle_parait_puisqu_il_y_a_de_quoi(self, mesures):
        assert mesures["carteHorsListe"] == "true"

    def test_elle_nomme_la_valeur_et_sa_cible(self, mesures):
        assert texte(mesures, "texteHorsListe") == "U13 M"
        assert mesures["cibleHorsListe"] == "→U13H"
