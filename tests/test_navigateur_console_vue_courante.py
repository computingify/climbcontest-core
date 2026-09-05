"""La console garde la vue qu'on regarde quand la page se recharge.

⚠️ **Le defaut que ce fichier ferme.** `montrerConsole()` finissait par un
`montrerVue("participants")` en dur : quelle que soit la vue ouverte, un F5 --
ou un onglet que le navigateur reveille apres l'avoir mis en veille -- ramenait
sur « Participants ». Le jour J, la console est ouverte sur les Reussites ou
sur les Telephones pendant des heures ; retrouver l'accueil a chaque
rechargement fait refaire trois clics, et fait douter d'avoir vu ce qu'on
venait de voir.

La vue vit desormais dans l'adresse (`/console#telephones`). Ce fichier mesure
les cinq situations ou ca se joue, dans un VRAI navigateur -- aucune ne se
prouve sans lui : le dieze, l'historique et le rechargement n'existent pas
ailleurs.

| Situation | Ce qui doit se passer |
| --- | --- |
| Ouverture ordinaire | Participants, adresse **nue** |
| Clic sur une entree | La vue s'ouvre, l'adresse la nomme |
| **F5** | La meme vue, pas l'accueil |
| Bouton **Retour** | La vue precedente |
| Dieze illisible (`#toString`) | Accueil, et l'adresse se nettoie |
| Vue reservee, compte sans le role | Accueil |

Les deux dernieres lignes sont les pieges. `#toString` repond vrai a un
`VUES[nom]` naif -- tout objet JavaScript en herite -- et la console partirait
afficher une vue qui n'existe pas. `#classeur` tape par un organisateur
ouvrirait « un ecran qui ne repond que des refus », celui-la meme que le tiroir
prend soin de cacher.
"""
import os
import shutil
import tempfile
from datetime import date

import pytest

from tests.navigateur import CHROME, page_harnais, piloter, servir

pytestmark = pytest.mark.skipif(
    CHROME is None, reason="aucun navigateur : ce test se saute, il n'echoue pas")

MDP = "un-mot-de-passe-assez-long"

# ⚠️ Un ECRAN, pas un telephone : le tiroir n'est epingle qu'au-dela de 1080 px
# (spec 021), et la sonde clique dans ses entrees. Meme constante, pour la meme
# raison, que `test_navigateur_console_versions.py`.
ECRAN = (1440, 900)


# Les outils communs aux deux sondes. `rechargerVraiment` est le seul morceau
# qui demande une explication : voir son commentaire.
COMMUN = r"""
    const vueVisible = () => {
      const s = $(".vue:not([hidden])");
      return s ? s.id : "aucune";
    };
    const diese = () => vue().location.hash || "(vide)";
    const consoleOuverte = () => {
      const c = $("#console");
      return c && !c.hasAttribute("hidden");
    };

    async function connecter(qui) {
      await attendre("formulaire de connexion", () => $("#formConnexion"));
      $("#identifiant").value = qui;
      $("#motdepasse").value = "un-mot-de-passe-assez-long";
      // `requestSubmit()` declenche le vrai evenement `submit`, celui que la
      // console ecoute -- `submit()` le contournerait.
      $("#formConnexion").requestSubmit();
      await attendre("console ouverte", consoleOuverte);
    }

    // ⚠️ **Attendre le NOUVEAU document, et le prouver.** Le drapeau est pose
    // sur l'objet global de la page ; apres une navigation, le nouveau global
    // ne l'a pas. Sans lui, la sonde lirait l'ANCIEN document -- qui affiche
    // deja la bonne vue, console ouverte -- et le test passerait au vert sans
    // qu'aucun rechargement ait eu lieu.
    //
    // Ce n'est pas qu'une question de justesse : `calme()` prend le
    // `requestAnimationFrame` de la fenetre courante, et celui d'une fenetre
    // qu'on est en train de remplacer n'est JAMAIS appele. La sonde restait
    // suspendue la, sans meme rendre un echec -- c'est le defaut qui a coute
    // le premier passage de ce fichier.
    async function attendreNouvellePage(quoi) {
      await attendre(quoi, () => {
        const fen = vue(), doc = cadre.contentDocument;
        return fen && !fen.__ancienne && doc && doc.readyState === "complete"
            && consoleOuverte();
      });
    }

    /** Un VRAI rechargement -- ce que fait F5. */
    async function rechargerVraiment(quoi) {
      vue().__ancienne = true;
      vue().location.reload();
      await attendreNouvellePage(quoi);
    }

    /** Une arrivee neuve sur `/console` + ce qu'on lui accroche.

        ⚠️ Toujours une RECHERCHE dans la queue, jamais un dieze seul : si seul
        le dieze changeait, le navigateur ne rechargerait RIEN -- on mesurerait
        une navigation interne au lieu d'une arrivee. Elle sert au passage a
        verifier que la console nettoie ce qu'elle laisse dans l'adresse. */
    async function arriverSur(queue, quoi) {
      vue().__ancienne = true;
      cadre.src = "/console" + queue;
      await attendreNouvellePage(quoi);
    }
"""


SONDE_ADMIN = COMMUN + r"""
    await connecter("orga");

    // 1. L'ouverture ordinaire ne change pas : l'accueil, et une adresse NUE.
    //    `/console` reste `/console` -- on ne veut pas d'un `#participants`
    //    decoratif dans la barre d'adresse ni dans les favoris.
    note("arriveeVue", vueVisible());
    note("arriveeDiese", diese());

    // 2. Un clic ouvre la vue ET la nomme dans l'adresse.
    [...$$(".tiroir nav button")]
      .find((b) => /Téléphones/.test(b.textContent)).click();
    await calme();
    note("clicVue", vueVisible());
    note("clicDiese", diese());

    // 3. LE DEFAUT. F5 sur les Telephones rendait les Participants.
    await rechargerVraiment("console rechargée sur les téléphones");
    note("f5Vue", vueVisible());
    note("f5Diese", diese());

    // 4. Le bouton Retour ramene a la vue precedente -- il quittait la console.
    vue().history.back();
    await attendre("retour arrière", () => vueVisible() === "vueParticipants");
    note("retourVue", vueVisible());
    note("retourDiese", diese());

    // 5. Une adresse tapee a la main : l'ecran suit, sans rechargement.
    vue().location.hash = "#reglages";
    await attendre("réglages à la main", () => vueVisible() === "vueReglages");
    note("mainVue", vueVisible());

    // 6. Et un F5 par-dessus retombe bien sur les Reglages.
    await rechargerVraiment("console rechargée sur les réglages");
    note("f5ReglagesVue", vueVisible());

    // 7. Un dieze illisible ne casse rien -- et il se nettoie, pour qu'un
    //    favori fautif ne le reproduise pas a chaque ouverture.
    //    ⚠️ `#toString` et non `#nimportequoi` : c'est le nom qui repond VRAI
    //    a un `VUES[nom]` naif, puisque tout objet en herite.
    vue().location.hash = "#toString";
    await attendre("rattrapage du dièse", () => vueVisible() === "vueParticipants");
    note("bidonVue", vueVisible());
    note("bidonDiese", diese());

    // 8. Un administrateur, lui, arrive bien sur le Classeur par l'adresse.
    await arriverSur("?x=1#classeur", "arrivée directe sur le classeur");
    await calme();
    note("directVue", vueVisible());
    note("directDiese", diese());
    note("directRecherche", vue().location.search || "(vide)");

    // 9. Le retour du consentement Google. Trois choses au meme endroit :
    //    l'ecran s'ouvre, le message RESTE lisible, et `?jeton=pose` disparait
    //    -- sinon un rechargement rejouerait la phrase d'un consentement qui
    //    date d'une heure.
    await arriverSur("?jeton=pose", "retour du consentement Google");
    await calme();
    note("jetonVue", vueVisible());
    note("jetonRecherche", vue().location.search || "(vide)");
    const message = $("#message");
    note("jetonMessage", message && !message.hasAttribute("hidden")
      ? message.textContent.slice(0, 14) : "(effacé)");
"""


SONDE_ORGANISATEUR = COMMUN + r"""
    await connecter("aide");

    // Le tiroir cache « Classeur » : les quatre routes sont reservees a un
    // administrateur, le serveur repond 403.
    note("entreeMasquee", $("#navClasseur").hidden);

    // L'adresse ne doit pas rouvrir la porte que le menu ferme.
    await arriverSur("?x=1#classeur", "arrivée sur une vue réservée");
    await calme();
    note("interditVue", vueVisible());
    note("interditDiese", diese());
"""


@pytest.fixture(scope="module")
def serveur():
    """Une console, et DEUX comptes : un administrateur, un organisateur.

    Le second n'est pas un decor : c'est lui qui prouve qu'une vue reservee ne
    s'ouvre pas parce qu'on en connait le nom.
    """
    from flask import Response

    dossier = tempfile.mkdtemp(prefix="climbcontest-vue-")
    os.environ["CLIMBCONTEST_TEST"] = "1"

    from climbcontest import comptes, creer_app
    from climbcontest.config import Config
    from climbcontest.extensions import db
    from climbcontest.models import Competition, EN_COURS, Participant

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
        comptes.creer("orga", MDP, [comptes.ADMIN])
        comptes.creer("aide", MDP, [comptes.ORGANISATEUR])
        db.session.commit()

    verdict = {"texte": None}

    @app.post("/__verdict")
    def _poser():
        from flask import request
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    @app.get("/__harnais/<qui>")
    def _harnais(qui):
        sonde = SONDE_ADMIN if qui == "admin" else SONDE_ORGANISATEUR
        return Response(page_harnais("/console", sonde, taille=ECRAN),
                        mimetype="text/html")

    url, arreter = servir(app)
    try:
        yield url, verdict
    finally:
        arreter()
        shutil.rmtree(dossier, ignore_errors=True)


@pytest.fixture(scope="module")
def admin(serveur):
    """Un SEUL parcours pour tout ce que voit un administrateur.

    Le cout dominant d'un test navigateur est le demarrage du navigateur, pas
    le parcours : rejouer les huit etapes pour lire huit mesures les paierait
    huit fois. Le releve est en lecture seule -- aucun test ne le modifie.
    Meme motif que `test_navigateur_console_versions.py`.
    """
    url, verdict = serveur
    rendu = piloter(f"{url}/__harnais/admin", verdict, taille=ECRAN)
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


@pytest.fixture(scope="module")
def organisateur(serveur):
    """Le parcours du compte sans le role admin. Un contexte navigateur neuf --
    donc une session vierge : sans ca, le cookie de l'administrateur ferait
    passer ce parcours pour ce qu'il n'est pas."""
    url, verdict = serveur
    rendu = piloter(f"{url}/__harnais/organisateur", verdict, taille=ECRAN)
    assert rendu.startswith("OK "), rendu
    return dict(x.split("=", 1) for x in rendu[3:].split(" ") if "=" in x)


class TestLOuvertureOrdinaireNeChangePas:

    def test_l_accueil_garde_une_adresse_nue(self, admin):
        assert admin["arriveeVue"] == "vueParticipants"
        assert admin["arriveeDiese"] == "(vide)", (
            f"l'adresse d'arrivee porte « {admin['arriveeDiese']} » : "
            "`/console` doit rester `/console`. Un `#participants` decoratif "
            "finirait dans les favoris et dans les liens qu'on s'envoie")


class TestLaVueSeLitDansLAdresse:

    def test_un_clic_nomme_la_vue(self, admin):
        assert admin["clicVue"] == "vueTelephones"
        assert admin["clicDiese"] == "#telephones", (
            f"apres un clic sur « Telephones », l'adresse porte "
            f"« {admin['clicDiese']} » : elle ne dit pas ou l'on est, donc "
            "elle ne pourra pas le redire apres un rechargement")

    def test_le_rechargement_garde_la_vue(self, admin):
        assert admin["f5Vue"] == "vueTelephones", (
            f"apres un F5 sur les Telephones, la console affiche "
            f"« {admin['f5Vue']} ». C'est LE defaut : `montrerConsole()` "
            "ouvrait « participants » en dur, et le jour J la console est "
            "ouverte des heures sur un autre ecran")
        assert admin["f5Diese"] == "#telephones"

    def test_le_bouton_retour_ramene_a_la_vue_precedente(self, admin):
        assert admin["retourVue"] == "vueParticipants", (
            f"« Retour » rend « {admin['retourVue']} » : la vue precedente "
            "n'est pas revenue. Sans entree d'historique, ce bouton quittait "
            "la console -- c'est ce qu'il faisait avant")
        assert admin["retourDiese"] == "(vide)"

    def test_une_adresse_tapee_a_la_main_ouvre_la_vue(self, admin):
        assert admin["mainVue"] == "vueReglages"
        assert admin["f5ReglagesVue"] == "vueReglages"

    def test_une_arrivee_directe_ouvre_la_vue_et_nettoie_la_recherche(self, admin):
        assert admin["directVue"] == "vueClasseur", (
            "une adresse partagee `/console#classeur` doit ouvrir le classeur "
            f"chez un administrateur, pas « {admin['directVue']} »")
        assert admin["directDiese"] == "#classeur"
        assert admin["directRecherche"] == "(vide)", (
            f"la recherche « {admin['directRecherche']} » survit a l'ouverture. "
            "C'est ce nettoyage qui empeche `?jeton=pose` d'etre rejoue a "
            "chaque rechargement au retour du consentement Google")


class TestLeRetourDuConsentementGoogle:
    """⚠️ Un defaut repare au passage, et il vivait exactement ici.

    `lireRetourJeton` disait la phrase de retour PUIS appelait `montrerVue`,
    dont la premiere charge est de remettre la zone de message a zero. Le
    consentement aboutissait donc sans que rien ne le confirme a l'ecran : on
    revenait de chez Google sur un classeur muet, et le seul moyen de savoir si
    ca avait marche etait de tester l'acces en ecriture -- ce que la phrase
    avalee demandait justement de faire.
    """

    def test_l_ecran_s_ouvre_le_message_reste_et_l_adresse_se_nettoie(self, admin):
        assert admin["jetonVue"] == "vueClasseur"
        assert admin["jetonMessage"] != "(effacé)", (
            "le message de retour de Google est effacé aussitôt dit : "
            "`montrerVue` remet la zone de message à zéro, et il était posé "
            "AVANT elle")
        assert "Compte_Google" in admin["jetonMessage"], (
            f"le message affiché est « {admin['jetonMessage']} » : ce n'est pas "
            "la confirmation du consentement")
        assert admin["jetonRecherche"] == "(vide)", (
            f"« {admin['jetonRecherche']} » survit dans l'adresse : un "
            "rechargement rejouerait la phrase d'un consentement qui date")


class TestUneAdresseNOuvrePasCeQueLeMenuFerme:

    def test_un_diese_illisible_retombe_sur_l_accueil(self, admin):
        assert admin["bidonVue"] == "vueParticipants", (
            f"`#toString` rend « {admin['bidonVue']} ». Tout objet JavaScript "
            "herite de `toString` : un `VUES[nom]` naif repond vrai, et la "
            "console part afficher une vue qui n'existe pas")
        assert admin["bidonDiese"] == "(vide)", (
            f"le dieze illisible reste dans l'adresse (« {admin['bidonDiese']} ») : "
            "un favori fautif le rejouerait a chaque ouverture")

    def test_une_vue_reservee_ne_s_ouvre_pas_sans_le_role(self, organisateur):
        assert organisateur["entreeMasquee"] == "true", (
            "l'entree « Classeur » n'est pas masquee pour un organisateur : "
            "ce parcours ne mesure plus ce qu'il croit")
        assert organisateur["interditVue"] == "vueParticipants", (
            f"un organisateur qui ouvre `/console#classeur` voit "
            f"« {organisateur['interditVue']} ». Le tiroir cache cette entree "
            "pour ne pas offrir un ecran qui ne repondrait que des refus ; "
            "l'adresse ne doit pas rouvrir cette porte-la")
        assert organisateur["interditDiese"] == "(vide)"
