"""Sans session, la console ne repond RIEN et ne montre RIEN.

Deux verrous, et il en faut deux.

**Le serveur** refuse : c'est le seul qui protege vraiment, et il est deja
teste route par route ailleurs (`test_comptes_et_session.py`). Ce qui manquait
etait le BALAYAGE : trois routes y sont nommees a la main, sur cinquante. Une
route ajoutee sans `@exige_role` passait donc au vert. Le test ci-dessous lit
`url_map` et n'en laisse aucune de cote.

**La page** ne montre rien : la console part `hidden` et `inert`, et ne
s'affiche qu'apres un `/admin/moi` qui reussit. Ce verrou-la avait lache. La
mise en grille des grands ecrans posait `display: grid` sur `#console`, ce qui
BAT le `[hidden] { display: none }` du navigateur -- l'origine auteur l'emporte
sur l'origine agent-utilisateur, quelle que soit la specificite. Deconnecte,
sur un ecran de 1080 px ou plus, on voyait la connexion en haut et la console
entiere en dessous, cliquable : tiroir, formulaires, bouton d'effacement des
donnees. Chaque clic partait vers un serveur qui refusait -- mais la page
invitait a cliquer, et rien ne disait pourquoi ca ne marchait pas.

Le comportement a l'ecran se verifie dans un vrai navigateur
(`test_navigateur_console_fermee.py`) : c'est du CSS, et aucune lecture de
chaine ne peut en repondre. Ici on tient ce qu'un test Python tient
honnetement -- le refus du serveur, et les deux attributs de depart.
"""
import re

import pytest

from climbcontest import comptes

MDP = "un-mot-de-passe-assez-long"

# Les deux seules routes de `/admin` ouvertes, et pourquoi.
#
# `connexion` : c'est la porte. L'exempter est la definition meme d'une porte.
# `deconnexion` : elle ne fait que vider la session. La fermer obligerait a
# etre connecte pour se deconnecter -- et n'importe qui peut deja vider SON
# propre cookie.
OUVERTES = {"/admin/connexion", "/admin/deconnexion"}


def chemins_admin(app):
    """Chaque route de `/admin`, avec ses parametres remplis.

    On lit `url_map` plutot qu'une liste ecrite a la main : une liste, on
    oublie de la completer le jour ou on ajoute une route, et c'est
    exactement ce jour-la que le test devrait parler.
    """
    for regle in app.url_map.iter_rules():
        if not str(regle.rule).startswith("/admin"):
            continue
        chemin = re.sub(r"<[^>]*>", "1", str(regle.rule))
        for methode in sorted(regle.methods - {"HEAD", "OPTIONS"}):
            yield chemin, methode, str(regle.rule)


@pytest.fixture()
def secret(app):
    """Sans SECRET_KEY reelle, l'administration repond 503 et non 401.

    C'est voulu (`auth_session`), mais ca testerait le mauvais refus : on veut
    verifier le controle d'acces, pas le garde-fou de configuration.
    """
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    return app


class TestAucuneRouteAdminNeRepondSansSession:

    def test_le_balayage_couvre_bien_toutes_les_routes(self, secret):
        """Un test qui ne balaie rien passerait au vert en silence.

        On compte les couples methode+route et non les routes : `/admin/plan`
        repond a GET, POST et DELETE, et ce sont trois portes distinctes.
        """
        couples = list(chemins_admin(secret))
        assert len(couples) > 40, (
            f"seulement {len(couples)} portes vues : le balayage ne trouve "
            "plus l'essentiel de la console, il ne protege plus rien")
        assert OUVERTES <= {r for _, _, r in couples}, (
            "les routes exemptees n'existent plus sous ce nom : revoir OUVERTES")

    def test_toutes_refusent(self, client, secret):
        """401 sur tout, sauf la porte. Sans exception, et sans liste a tenir."""
        fautives = []
        for chemin, methode, regle in chemins_admin(secret):
            if regle in OUVERTES:
                continue
            code = client.open(chemin, method=methode).status_code
            if code != 401:
                fautives.append(f"{methode} {regle} -> {code}")
        assert not fautives, (
            "ces routes d'administration repondent autre chose que 401 sans "
            "session :\n  " + "\n  ".join(fautives) +
            "\nUne route de /admin sans @exige_role est ouverte sur Internet.")

    def test_la_cle_des_juges_n_ouvre_pas_la_console(self, client, secret):
        """La lecon du 28/08, ecrite en tete de `auth_session`.

        `client` porte la cle d'API, comme l'application des juges. Cette cle
        s'extrait d'un APK public en quelques minutes : si elle ouvrait la
        console, elle ouvrirait l'effacement des donnees. Le mode TOLERE du
        garde-fou de cle avait justement contamine la console, et
        `GET /admin/import/rapport` repondait 200 depuis Internet.
        """
        assert client.get("/admin/import/rapport").status_code == 401
        assert client.get("/admin/participants").status_code == 401
        assert client.post("/admin/donnees/effacer").status_code == 401

    def test_une_session_ouverte_passe(self, client, secret):
        """Le contre-test. Sans lui, un `return 401` en dur passerait tout."""
        comptes.creer("chef", MDP, [comptes.ADMIN])
        assert client.post("/admin/connexion",
                           json={"identifiant": "chef",
                                 "mot_de_passe": MDP}).status_code == 200
        assert client.get("/admin/moi").status_code == 200
        # `/admin/comptes` et non `/admin/participants` : la seconde repond 409
        # quand aucune competition n'est active, ce qui n'a rien a voir avec le
        # controle d'acces et ferait echouer ce test pour la mauvaise raison.
        assert client.get("/admin/comptes").status_code == 200


class TestLaPagePartFermee:
    """Ce que le gabarit garantit AVANT que la moindre ligne de script tourne.

    La page est servie sans session -- c'est le choix de `routes/pages.py`, et
    il tient : elle ne porte aucune donnee. Mais elle porte les COMMANDES, et
    elles doivent etre cachees et debranchees tant que personne n'est connecte.
    """

    @pytest.fixture()
    def page(self, client):
        r = client.get("/console")
        assert r.status_code == 200
        return r.data.decode()

    def test_la_console_part_cachee_et_debranchee(self, page):
        balise = re.search(r"<div id=\"console\"[^>]*>", page)
        assert balise, "le conteneur #console a change de nom"
        assert "hidden" in balise.group(0), (
            "la console ne part plus cachee : deconnecte, on la verrait")
        assert "inert" in balise.group(0), (
            "la console ne part plus inerte : une regle de style qui la rend "
            "visible la rendrait du meme coup cliquable")

    def test_hidden_cache_vraiment(self, page):
        """La regle qui a manque, et qui manquerait a nouveau sans ce test.

        Elle ne se deduit d'aucun comportement testable en Python : c'est une
        regle de cascade. On verifie donc qu'elle est LA, et le navigateur
        verifie qu'elle marche.
        """
        assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important",
                         page), (
            "la regle globale `[hidden] { display: none !important }` a "
            "disparu : n'importe quelle regle posant `display` rendra a "
            "nouveau visible un element cache, #console le premier")

    def test_le_formulaire_de_connexion_est_dehors(self, page):
        """La connexion ne doit pas vivre DANS le bloc qu'on desactive.

        Sinon `inert` la debrancherait elle aussi, et plus personne ne pourrait
        se connecter -- une facon spectaculaire de fermer la console.
        """
        debut_console = page.index('<div id="console"')
        assert page.index('id="formConnexion"') < debut_console
