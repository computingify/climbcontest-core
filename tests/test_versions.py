"""Les versions se voient, et le catalogue se force (spec 030).

Ce que ces tests protègent tient en une phrase : **un téléphone en retard doit
être discernable d'un téléphone à jour**, et rien de ce qui sert à le savoir ne
doit pouvoir faire échouer une requête de catalogue.

⚠️ Le test le plus important du fichier est
`test_l_annonce_est_enregistree_meme_sur_un_304`. Le `304` est le cas
**majoritaire** le jour J : la PWA revalide toutes les trente secondes et le
catalogue ne bouge presque jamais. Une annonce enregistrée après la garde du
`304` ne montrerait dans la console que les téléphones en retard — l'exact
inverse de ce qu'on cherche à voir.

Le second par ordre d'importance est `TestPasDeCache`. La route du catalogue
est devenue un `GET` avec effet de bord : elle n'est acceptable que parce que la
requête atteint réellement l'application à chaque appel. Un cache posé devant
elle viderait le tableau des appareils sans qu'aucun test fonctionnel ne
bronche — d'où un test sur l'en-tête lui-même.
"""

from datetime import datetime, timedelta

import pytest

from climbcontest import comptes
from climbcontest import contest
from climbcontest.contest import appareils, enregistrer_annonce
from climbcontest.extensions import db
from climbcontest.models import Appareil
from climbcontest.version import VERSION

MDP = "un-mot-de-passe-assez-long"
TELEPHONE = "aaaa-1111-bbbb-2222"


@pytest.fixture()
def connecte(client, app, jeu):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga",
                                          "mot_de_passe": MDP})
    return client


def annonce(client, identifiant=TELEPHONE, nom=None, version="v9.9.9",
            si_none_match=None):
    """Une requête de catalogue qui porte les en-têtes d'annonce."""
    entetes = {"X-Device-Id": identifiant, "X-App-Version": version}
    if nom is not None:
        entetes["X-Device-Name"] = nom
    if si_none_match is not None:
        entetes["If-None-Match"] = f'"{si_none_match}"'
    return client.get("/api/v2/catalog", headers=entetes)


class TestAnnonce:
    """Ce que le téléphone dit de lui en téléchargeant le catalogue."""

    def test_sans_en_tete_rien_ne_change(self, client, jeu):
        """Le contrat d'avant la spec 030, mot pour mot.

        L'application Android du Play Store n'envoie aucun de ces en-têtes.
        Elle doit continuer de fonctionner sans qu'on republie quoi que ce soit.
        """
        r = client.get("/api/v2/catalog")
        assert r.status_code == 200
        assert r.get_json()["version"] == jeu["competition"].catalogue_version
        assert r.headers["ETag"] == f'"{jeu["competition"].catalogue_version}"'
        assert Appareil.query.count() == 0

    def test_un_telephone_qui_s_annonce_est_enregistre(self, client, jeu):
        assert annonce(client, nom="Mur%20jaune").status_code == 200

        a = db.session.get(Appareil, TELEPHONE)
        assert a is not None
        assert a.nom == "Mur jaune"
        assert a.version_app == "v9.9.9"
        assert a.catalogue_version == jeu["competition"].catalogue_version
        assert a.catalogue_vu_le is not None

    def test_l_annonce_est_enregistree_meme_sur_un_304(self, client, jeu):
        """⚠️ LE test de ce fichier.

        `catalogue()` fait un retour anticipé sur le `304` : tout ce qui suit la
        garde n'est jamais atteint quand le téléphone est déjà à jour. Or c'est
        le cas normal. Enregistrer l'annonce après cette garde ferait
        disparaître de la console tous les téléphones qui vont bien.
        """
        version = jeu["competition"].catalogue_version

        r = annonce(client, si_none_match=version)

        assert r.status_code == 304, "prerequis : le telephone est deja a jour"
        a = db.session.get(Appareil, TELEPHONE)
        assert a is not None, ("un telephone A JOUR doit se voir dans la console ; "
                              "l'annonce est posee AVANT la garde du 304")
        assert a.catalogue_version == version

    def test_deux_passages_ne_font_qu_une_ligne(self, client, jeu):
        annonce(client)
        premiere = db.session.get(Appareil, TELEPHONE).premiere_vue_le
        annonce(client)

        assert Appareil.query.count() == 1
        a = db.session.get(Appareil, TELEPHONE)
        assert a.premiere_vue_le == premiere
        assert a.vu_le >= premiere

    def test_un_nom_mal_encode_coute_le_nom_jamais_la_requete(self, client, jeu):
        """Un `%ZZ` ne doit pas rendre un catalogue impossible à télécharger."""
        r = annonce(client, nom="Mur%ZZjaune")
        assert r.status_code == 200
        assert db.session.get(Appareil, TELEPHONE) is not None

    def test_une_version_fantaisiste_est_tronquee(self, client, jeu):
        annonce(client, version="v" + "9" * 300)
        assert len(db.session.get(Appareil, TELEPHONE).version_app) == 20

    def test_un_identifiant_vide_n_annonce_rien(self, client, jeu):
        assert client.get("/api/v2/catalog",
                          headers={"X-Device-Id": "   "}).status_code == 200
        assert Appareil.query.count() == 0

    def test_une_annonce_qui_echoue_ne_casse_pas_le_catalogue(
            self, client, jeu, monkeypatch):
        """L'invariant qui compte le jour J.

        Une colonne vide dans la console rend Adrien aveugle sur un point ; un
        catalogue qui n'arrive pas arrête les scans de vingt-cinq juges. Les
        deux ne se comparent pas — donc l'annonce ne peut jamais lever.
        """
        def explose(*a, **kw):
            raise RuntimeError("base verrouillee")

        monkeypatch.setattr(db.session, "get", explose)

        r = annonce(client)
        assert r.status_code == 200
        assert len(r.get_json()["participants"]) == 2


class TestEntetesDeReponse:
    def test_la_version_du_serveur_sur_les_deux_branches(self, client, jeu):
        """Le `304` construit sa réponse à part : c'est l'endroit exact où un
        en-tête ajouté au chemin `200` s'oublie."""
        version = jeu["competition"].catalogue_version

        plein = client.get("/api/v2/catalog")
        vide = client.get(f"/api/v2/catalog?depuis={version}")

        assert vide.status_code == 304
        assert plein.headers["X-Server-Version"] == VERSION
        assert vide.headers["X-Server-Version"] == VERSION


class TestPasDeCache:
    """⚠️ Le verrou de F8.

    La route enregistre une annonce à chaque appel. Ça n'est acceptable que
    parce qu'aucun intermédiaire n'a le droit de servir cette réponse à sa
    place : `private` interdit à un cache PARTAGÉ de la stocker. Le retirer ne
    casserait aucun test fonctionnel — d'où celui-ci.
    """

    def test_no_cache_et_private_sur_les_deux_branches(self, client, jeu):
        version = jeu["competition"].catalogue_version

        plein = client.get("/api/v2/catalog")
        vide = client.get(f"/api/v2/catalog?depuis={version}")

        assert vide.status_code == 304
        for r in (plein, vide):
            entete = r.headers["Cache-Control"]
            assert "no-cache" in entete
            assert "private" in entete, (
                "sans `private`, un cache partage pourrait servir cette reponse "
                "a la place du serveur : plus aucune annonce n'arriverait, et la "
                "console montrerait des telephones absents pendant qu'ils "
                "grimpent")


class TestAnnonceDepuisUnLot:
    """La redondance : un `POST` n'est jamais mis en cache."""

    def test_un_lot_enregistre_la_version(self, client, jeu):
        r = client.post("/api/v3/successes", json={
            "appareil": {"id": TELEPHONE, "nom": "Mur bleu", "app": "v9.9.9"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })
        assert r.status_code == 200

        a = db.session.get(Appareil, TELEPHONE)
        assert a.version_app == "v9.9.9"
        assert a.nom == "Mur bleu"

    def test_un_lot_ne_renseigne_JAMAIS_le_catalogue(self, client, jeu):
        """Recevoir un lot prouve que le téléphone est vivant, pas qu'il détient
        le catalogue courant. Écrire le numéro ici afficherait « à jour » un
        téléphone qui ne s'est pas synchronisé depuis des heures."""
        client.post("/api/v3/successes", json={
            "appareil": {"id": TELEPHONE, "app": "v9.9.9"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })

        a = db.session.get(Appareil, TELEPHONE)
        assert a.catalogue_version is None
        assert a.catalogue_vu_le is None

    def test_un_lot_sans_appareil_se_comporte_comme_avant(self, client, jeu):
        r = client.post("/api/v3/successes", json={
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}]})
        assert r.status_code == 200
        assert Appareil.query.count() == 0


class TestListeDesAppareils:
    def test_un_telephone_annonce_sans_reussite_apparait(self, client, jeu):
        """Le contrôle du matin : les juges ouvrent l'application avant la
        première grimpe. Vérifier les versions après la première réussite, c'est
        vérifier trop tard."""
        annonce(client, nom="Entree")

        liste = appareils(jeu["competition"])
        assert len(liste) == 1
        assert liste[0]["reussites"] == 0
        assert liste[0]["nom"] == "Entree"
        assert liste[0]["annonce"] is True

    def test_un_telephone_qui_envoie_sans_s_annoncer(self, client, jeu):
        """L'application Android : ses colonnes de version restent vides, et le
        reste de sa ligne doit rester juste."""
        client.post("/api/v3/successes", json={
            "appareil": {"id": "ANDROID-77", "nom": "Android"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })

        ligne = appareils(jeu["competition"])[0]
        assert ligne["reussites"] == 1
        assert ligne["version_app"] is None
        assert ligne["annonce"] is False
        assert ligne["app_a_jour"] is None
        assert ligne["catalogue_a_jour"] is None

    def test_les_deux_sources_se_fondent_en_une_ligne(self, client, jeu):
        annonce(client, nom="Mur jaune")
        client.post("/api/v3/successes", json={
            "appareil": {"id": TELEPHONE, "nom": "Mur jaune"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })

        liste = appareils(jeu["competition"])
        assert len(liste) == 1
        assert liste[0]["reussites"] == 1
        assert liste[0]["version_app"] == "v9.9.9"

    def test_un_telephone_vu_il_y_a_trois_jours_sort_du_tableau(self, client, jeu):
        enregistrer_annonce("vieux", nom="Oublie", version_app="v0.1.0",
                            maintenant=datetime.now() - timedelta(days=3))
        assert appareils(jeu["competition"]) == []

    def test_le_catalogue_se_compare_par_EGALITE(self, client, jeu):
        """Le numéro identifie un couple (édition, état de son catalogue) : il
        saute, et il saute pour toutes les éditions à la fois quand le mur
        change. « Plus grand » ne veut rien dire."""
        enregistrer_annonce(TELEPHONE, version_app=VERSION,
                            catalogue_version=jeu["competition"].catalogue_version + 7)

        ligne = appareils(jeu["competition"])[0]
        assert ligne["catalogue_a_jour"] is False, (
            "un numero PLUS GRAND vient d'ailleurs : il n'est pas a jour")


class TestDetecteurDeCache:
    """Un téléphone qui envoie mais ne s'annonce plus : la signature d'un cache.

    C'est la seule mesure de F8 qui attrape une faute commise **hors du
    dépôt** — un module de cache activé dans la configuration de Caddy, que
    nulle CI ne relit.
    """

    def _reussite(self, client, quand=None):
        client.post("/api/v3/successes", json={
            "appareil": {"id": TELEPHONE, "nom": "Mur jaune"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })

    def test_envoie_mais_ne_s_annonce_plus(self, client, jeu):
        annonce(client)
        self._reussite(client)
        # Son annonce vieillit ; ses reussites, non.
        a = db.session.get(Appareil, TELEPHONE)
        a.catalogue_vu_le = datetime.now() - timedelta(minutes=20)
        db.session.commit()

        ligne = appareils(jeu["competition"])[0]
        assert ligne["annonce_perdue"] is True

    def test_un_telephone_simplement_eteint_n_est_pas_suspecte(self, client, jeu):
        """Il ne s'annonce plus, mais il n'envoie plus rien non plus : c'est un
        téléphone éteint, et `silencieux` le dit déjà."""
        annonce(client)
        a = db.session.get(Appareil, TELEPHONE)
        a.catalogue_vu_le = datetime.now() - timedelta(hours=1)
        db.session.commit()

        ligne = appareils(jeu["competition"])[0]
        assert ligne["annonce_perdue"] is False

    def test_un_telephone_qui_vient_de_demarrer_n_est_pas_suspecte(
            self, client, jeu):
        """Le transitoire d'allumage.

        Un téléphone qui envoie son premier lot avant d'avoir fini de
        télécharger son catalogue n'a pas encore de `catalogue_vu_le`. Sans
        délai de grâce, il déclencherait l'alerte pour quelques secondes — et
        une alerte qui crie pour rien apprend à ignorer les alertes.
        """
        client.post("/api/v3/successes", json={
            "appareil": {"id": TELEPHONE, "app": "v9.9.9"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })

        a = db.session.get(Appareil, TELEPHONE)
        assert a.catalogue_vu_le is None, "prerequis : aucun echange de catalogue"
        assert appareils(jeu["competition"])[0]["annonce_perdue"] is False

    def test_jamais_annonce_depuis_vingt_minutes_est_suspecte(self, client, jeu):
        """Le cache posé dès le départ : le téléphone envoie, il n'a JAMAIS
        téléchargé de catalogue, et ça dure."""
        client.post("/api/v3/successes", json={
            "appareil": {"id": TELEPHONE, "app": "v9.9.9"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })
        a = db.session.get(Appareil, TELEPHONE)
        a.premiere_vue_le = datetime.now() - timedelta(minutes=20)
        db.session.commit()

        assert appareils(jeu["competition"])[0]["annonce_perdue"] is True

    def test_l_application_android_n_est_jamais_suspectee(self, client, jeu):
        """Elle ne s'annonce pas : son silence est normal, pas symptomatique."""
        client.post("/api/v3/successes", json={
            "appareil": {"id": "ANDROID-77"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })

        ligne = appareils(jeu["competition"])[0]
        assert ligne["annonce_perdue"] is False


class TestRattrapage:
    """Le retard NORMAL, celui qui se répare tout seul.

    Il est devenu fréquent avec la fermeture de l'incohérence du plan :
    redessiner le mur donne un numéro neuf à **toutes** les éditions d'un coup.
    Un organisateur qui retouche le plan en pleine compétition verrait sinon
    ses vingt-cinq téléphones virer à l'ambre en même temps et croirait avoir
    tout cassé — alors qu'ils se remettent à jour dans les cinq minutes.
    """

    def test_en_retard_mais_vu_a_l_instant(self, client, jeu):
        annonce(client)
        jeu["competition"].catalogue_version += 5      # le mur est redessiné
        db.session.commit()

        ligne = appareils(jeu["competition"])[0]
        assert ligne["catalogue_a_jour"] is False
        assert ligne["rattrapage"] is True, (
            "il s'est annonce il y a dix secondes : il rattrape, il n'est pas "
            "en panne")

    def test_en_retard_depuis_une_heure_n_est_pas_un_rattrapage(self, client, jeu):
        annonce(client)
        a = db.session.get(Appareil, TELEPHONE)
        a.catalogue_vu_le = datetime.now() - timedelta(hours=1)
        db.session.commit()
        jeu["competition"].catalogue_version += 5
        db.session.commit()

        assert appareils(jeu["competition"])[0]["rattrapage"] is False

    def test_un_cache_qui_mange_les_annonces_n_est_pas_un_rattrapage(
            self, client, jeu):
        """⚠️ Le piège que les deux horodatages existent pour éviter.

        Les lots continuent d'arriver (POST, jamais mis en cache) et font
        avancer `vu_le` ; seules les annonces sont absorbées. Si le rattrapage
        se jugeait sur `vu_le`, cette panne passerait pour un retard bénin.
        """
        annonce(client)
        a = db.session.get(Appareil, TELEPHONE)
        a.catalogue_vu_le = datetime.now() - timedelta(minutes=20)
        db.session.commit()
        client.post("/api/v3/successes", json={
            "appareil": {"id": TELEPHONE, "app": "v9.9.9"},
            "items": [{"ref": "abc123", "bib": "1", "bloc": "ZJ6"}],
        })
        jeu["competition"].catalogue_version += 5
        db.session.commit()

        ligne = appareils(jeu["competition"])[0]
        assert ligne["rattrapage"] is False
        assert ligne["annonce_perdue"] is True


class TestRouteVersions:
    def test_fermee_sans_session(self, client, app, jeu):
        # La cle est posee sans se connecter : sans elle, la route repondrait
        # 503 (« administration desactivee »), ce qui ne prouverait pas qu'elle
        # est FERMEE, seulement que la configuration est incomplete.
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/versions").status_code == 401

    def test_ce_que_le_serveur_sert(self, connecte, jeu):
        d = connecte.get("/admin/versions").get_json()

        assert d["serveur"]["version"] == VERSION
        assert d["catalogue"]["version"] == jeu["competition"].catalogue_version
        assert d["catalogue"]["participants"] == 2      # le sans-dossard exclu
        assert d["catalogue"]["blocs"] == 3

    def test_les_comptes(self, connecte, jeu):
        version = jeu["competition"].catalogue_version
        enregistrer_annonce("a-jour", version_app=VERSION,
                            catalogue_version=version)
        enregistrer_annonce("en-retard", version_app="v0.0.1",
                            catalogue_version=version)

        d = connecte.get("/admin/versions").get_json()["appareils"]
        assert d["vus"] == 2
        assert d["a_jour"] == 1
        assert d["en_retard"] == 1
        assert d["annonces_perdues"] == 0

    def test_un_muet_ne_compte_ni_a_jour_ni_en_retard(self, connecte, jeu):
        """Un téléphone qui ne dit pas sa version n'est pas « en retard » : il
        est muet sur la question, et gonfler l'un des deux compteurs mentirait
        dans un sens ou dans l'autre."""
        enregistrer_annonce("android", nom="Android")

        d = connecte.get("/admin/versions").get_json()["appareils"]
        assert d["vus"] == 1
        assert d["a_jour"] == 0
        assert d["en_retard"] == 0


class TestModuleVersion:
    def test_sans_fichier_la_version_vaut_dev(self):
        """L'état normal d'un poste de développement, pas une erreur."""
        from climbcontest import version as module

        assert module.VERSION == "dev" or module.VERSION.startswith("v")

    def test_la_sonde_dit_la_meme_chose(self, client_sans_cle, jeu):
        assert client_sans_cle.get("/health").get_json()["version"] == VERSION


class TestCoquilleDeLaPwa:
    def test_la_coquille_porte_sa_version(self, client_sans_cle):
        """⚠️ Gravée dans la page, et non demandée par un appel : le service
        worker sert la coquille depuis son cache, donc ce qui tourne sur le
        téléphone peut avoir un lancement de retard sur ce que le serveur sert.
        C'est précisément ce qu'on veut afficher."""
        page = client_sans_cle.get("/juge").get_data(as_text=True)
        assert f'name="climbcontest-version" content="{VERSION}"' in page
