"""La page de resultats — ce que le serveur doit en rendre.

Le comportement de la page elle-meme (rotation, recherche, degradation quand le
backend tombe) se verifie dans un navigateur : c'est du JavaScript, et le
simuler ici donnerait une fausse assurance. Ce fichier verifie ce qu'un test
Python PEUT verifier honnetement, et rien de plus.
"""
import re

import pytest


class TestServie:

    def test_resultats_repond_du_html(self, client, jeu):
        r = client.get("/resultats")
        assert r.status_code == 200
        assert r.headers["Content-Type"].startswith("text/html")

    def test_la_racine_sert_la_page_pas_un_json(self, client, jeu):
        """Un visiteur qui tape l'adresse du service doit voir le classement."""
        r = client.get("/")
        assert r.status_code == 200
        assert b"<!doctype html>" in r.data.lower()

    def test_le_mode_mur_sert_la_meme_page(self, client, jeu):
        """Le mode est choisi par la page, pas par le serveur : un seul fichier."""
        assert client.get("/resultats?mur").data == client.get("/resultats").data

    def test_servie_meme_sans_competition_active(self, client, app):
        """C'est la PAGE qui gere le cas, pas le serveur.

        Repondre 409 ici afficherait une erreur de navigateur au lieu d'un
        message lisible.
        """
        assert client.get("/resultats").status_code == 200


class TestAucuneDependanceExterieure:
    """Critere A1, et la raison d'etre de tout le fichier.

    Une page projetee pendant une competition ne peut pas dependre d'un CDN ni
    d'un service de polices. Si la box Internet tombe a 10 h, l'ecran de la
    salle doit continuer -- le backend, lui, est sur le reseau local.
    """

    # La SEULE exception admise, et elle n'est pas une ressource : c'est
    # l'espace de noms XML du SVG. Un navigateur ne le telecharge jamais -- il
    # sert a identifier le dialecte, comme un numero de version. Verifie dans
    # un navigateur : zero requete sortante (voir le journal de la PR).
    NAMESPACE_SVG = "http://www.w3.org/2000/svg"

    def test_aucune_url_externe(self, client, jeu):
        page = client.get("/resultats").data.decode()
        externes = [u for u in re.findall(r'https?://[^\s"\'<>)]+', page)
                    if u != self.NAMESPACE_SVG]
        assert not externes, f"la page charge des ressources externes : {externes}"

    def test_aucune_balise_qui_va_chercher_quelque_chose_dehors(self, client, jeu):
        page = client.get("/resultats").data.decode()
        for balise in re.findall(r"<(?:script|link|img|iframe)[^>]*>", page):
            for url in re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)', balise):
                assert url.startswith("data:") or url.startswith("/"), \
                    f"ressource distante : {url}"

    def test_aucune_police_telechargee(self, client, jeu):
        page = client.get("/resultats").data.decode()
        assert "@font-face" not in page
        assert "fonts.googleapis" not in page


class TestSecuriteDeLaPage:

    def test_aucune_donnee_n_est_injectee_dans_le_html(self, client, jeu):
        """La page va chercher le classement elle-meme.

        Deux raisons : elle peut se rafraichir sans rechargement, et surtout
        elle peut GARDER le dernier classement connu quand le serveur tombe.
        Un nom injecte au rendu serait aussi une surface d'injection de plus.
        """
        from climbcontest.contest import enregistrer_reussite
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])

        page = client.get("/resultats").data.decode()

        assert "Dupont" not in page, "aucun nom ne doit figurer dans le HTML servi"

    def test_les_noms_sont_inseres_par_textContent(self, client, jeu):
        """Les noms viennent de la base : jamais d'innerHTML sur eux."""
        page = client.get("/resultats").data.decode()
        assert "nom.textContent" in page

        # innerHTML ne doit servir qu'a VIDER un conteneur, jamais a injecter
        # une donnee. On cherche donc les AFFECTATIONS -- pas les lignes qui
        # mentionnent le mot, sinon un commentaire suffirait a faire tomber le
        # test (c'est arrive en l'ecrivant).
        affectations = re.findall(r"innerHTML\s*=\s*([^;]+);", page)
        assert affectations, "le test doit trouver les affectations qu'il verifie"
        for valeur in affectations:
            assert valeur.strip() in ('""', "''"), \
                f"innerHTML utilise autrement que pour vider : {valeur.strip()}"


class TestContratAvecLApi:
    """La page consomme des champs precis. S'ils changent, elle casse en silence."""

    @pytest.mark.parametrize("champ", ["classements", "competition", "calcule_le"])
    def test_la_reponse_porte_les_champs_racine_attendus(self, client, jeu, champ):
        assert champ in client.get("/api/public/classement").get_json()

    @pytest.mark.parametrize("champ", ["groupe", "lignes"])
    def test_chaque_classement_porte_ses_champs(self, client, jeu, champ):
        d = client.get("/api/public/classement").get_json()
        assert all(champ in c for c in d["classements"])

    @pytest.mark.parametrize("champ", ["rang", "score", "blocs", "nom", "dossard"])
    def test_chaque_ligne_porte_les_champs_affiches(self, client, jeu, champ):
        from climbcontest.contest import enregistrer_reussite
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement").get_json()
        lignes = [l for c in d["classements"] for l in c["lignes"]]
        assert lignes, "il doit y avoir des lignes a verifier"
        assert all(champ in l for l in lignes), f"champ « {champ} » attendu par la page"

    def test_la_page_utilise_bien_ces_champs(self, client, jeu):
        """Le pendant du test precedent : si la page cessait de les lire, le
        contrat ci-dessus ne protegerait plus rien."""
        page = client.get("/resultats").data.decode()
        for champ in ("l.rang", "l.score", "l.blocs", "l.nom", "l.dossard"):
            assert champ in page, f"la page ne lit pas {champ}"


class TestAvantLaPremiereReussite:
    """Le premier quart d'heure de chaque competition, sur l'ecran de la salle.

    Tout le monde est a zero et ex aequo. Le classement est juste, mais projete
    sur un mur il se lit comme un ecran fige. La page doit le DIRE -- tout en
    gardant la liste, parce que voir les inscrits affiches rassure sur le fait
    que le systeme tourne.
    """

    def test_l_api_rend_bien_tout_le_monde_a_zero(self, client, jeu):
        d = client.get("/api/public/classement").get_json()
        lignes = [l for c in d["classements"] for l in c["lignes"]]
        assert lignes, "les inscrits doivent apparaitre avant toute reussite"
        assert all(l["score"] == 0 for l in lignes)

    def test_la_page_prevoit_ce_cas(self, client, jeu):
        page = client.get("/resultats").data.decode()
        assert "toutAZero" in page, "la page doit distinguer « rien encore » de « fige »"
        assert "En attente des premi" in page


class TestConsoleAdmin:
    """La page de la console (spec 005).

    Elle avait ete OUBLIEE : j'ai livre les routes JSON et marque la spec
    « livree » alors que l'architecture prevoyait `templates/admin.html`. Un
    organisateur ne peut pas utiliser curl un dimanche matin.
    """

    def test_la_console_est_servie(self, client, jeu):
        r = client.get("/console")
        assert r.status_code == 200
        assert r.headers["Content-Type"].startswith("text/html")

    def test_elle_est_servie_sans_authentification(self, client, app, jeu):
        """C'est la PAGE qui demande la connexion.

        Proteger le HTML n'apporterait rien : il ne contient aucune donnee,
        seulement le formulaire. Et un 401 sur le HTML afficherait une erreur
        de navigateur au lieu d'un ecran de connexion.
        """
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/console").status_code == 200

    def test_elle_ne_contient_aucune_donnee(self, client, jeu):
        """Tout passe par les routes /admin/*, qui exigent une session."""
        from climbcontest.contest import enregistrer_reussite
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        page = client.get("/console").data.decode()
        assert "Dupont" not in page

    def test_aucune_ressource_externe(self, client, jeu):
        import re
        page = client.get("/console").data.decode()
        externes = [u for u in re.findall(r'https?://[^\s"\'<>)]+', page)
                    if u != "http://www.w3.org/2000/svg"]
        assert not externes, f"ressources externes : {externes}"

    def test_elle_appelle_les_bonnes_routes(self, client, jeu):
        """Si une route est renommee, la console casse en silence."""
        page = client.get("/console").data.decode()
        for route in ("/admin/connexion", "/admin/deconnexion", "/admin/moi",
                      "/admin/participants", "/admin/reussites", "/admin/dossards",
                      "/admin/comptes", "/admin/mon-mot-de-passe",
                      "/admin/appareils", "/admin/reussites-tracees"):
            assert route in page, f"la console n'appelle pas {route}"

    def test_le_suivi_des_telephones_est_la(self, client, jeu):
        """Spec 011. Les routes existaient deja quand l'onglet a ete oublie une
        premiere fois pour la spec 005 : ce test empeche la meme omission.

        La refonte du 30/08 a fondu « Appareils » et « App juge » dans une
        seule vue « Telephones » -- les deux parlaient des memes appareils.
        Le test suit le RENOMMAGE ; ce qu'il protege n'a pas change."""
        page = client.get("/console").data.decode()
        assert 'data-vue="telephones"' in page
        assert 'id="vueTelephones"' in page
        assert "chargerAppareils" in page

    def test_les_quatre_vues_existent(self, client, jeu):
        """Sept onglets ajoutes au fil des specs, regroupes en quatre. Chacune
        doit exister ET etre atteignable depuis le tiroir."""
        page = client.get("/console").data.decode()
        for vue in ("participants", "reussites", "telephones", "reglages"):
            assert f'data-vue="{vue}"' in page, f"le tiroir n'ouvre pas {vue}"
            majuscule = vue[0].upper() + vue[1:]
            assert f'id="vue{majuscule}"' in page, f"la vue {vue} n'existe pas"

    def test_le_telephone_muet_est_signale_visuellement(self, client, jeu):
        """La seule information urgente de la page. La couleur ne suffit pas :
        une bordure la double, parce que le rouge seul ne se voit pas par
        tout le monde."""
        page = client.get("/console").data.decode()
        assert "tr.muet td" in page
        assert "box-shadow: inset 3px 0 0 var(--alerte)" in page

    def test_elle_gere_la_session_expiree(self, client, jeu):
        """Une session qui expire en pleine saisie ne doit pas ressembler a une
        panne : la console doit ramener a la connexion en le disant."""
        page = client.get("/console").data.decode()
        assert "Session expir" in page

    def test_la_gestion_des_comptes_est_masquee_par_defaut(self, client, jeu):
        """Elle n'apparait que pour un administrateur.

        Le serveur refuse de toute facon (403) : masquer evite d'offrir un
        formulaire qui ne marche pas, ce n'est pas la protection.

        Depuis la refonte du 30/08 c'est un BLOC de la vue « Reglages » et non
        plus un onglet -- un organisateur non-admin y garde son mot de passe.
        """
        page = client.get("/console").data.decode()
        assert 'id="blocComptes" hidden' in page

    def test_une_faute_de_frappe_ne_deconnecte_pas(self, client, jeu):
        """Changer son mot de passe exige l'ancien, et se tromper repond 401 --
        comme une session expiree. Sans distinction, une faute de frappe
        renvoyait a l'ecran de connexion au lieu de dire ce qui n'allait pas.

        Trouve en le faisant a la main dans un navigateur : aucun test de route
        ne pouvait le voir, les deux repondent 401.
        """
        page = client.get("/console").data.decode()
        assert "motDePasseAttendu" in page

    def test_elle_gere_le_dernier_administrateur(self, client, jeu):
        """Le piege sans retour : l'unique admin se retire ses droits."""
        page = client.get("/console").data.decode()
        assert "dernier_admin" in page
        assert "Dernier administrateur" in page

    def test_elle_previent_pour_l_echelle_d_impression(self, client, jeu):
        """« Ajuster a la page » sort des QR trop petits pour etre scannes."""
        page = client.get("/console").data.decode()
        assert "100" in page and "chelle" in page
