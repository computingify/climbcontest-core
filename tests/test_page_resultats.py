"""La page de resultats — ce que le serveur doit en rendre.

Le comportement de la page elle-meme (rotation, recherche, degradation quand le
backend tombe) se verifie dans un navigateur : c'est du JavaScript, et le
simuler ici donnerait une fausse assurance. Ce fichier verifie ce qu'un test
Python PEUT verifier honnetement, et rien de plus.
"""
import re

import pytest


class TestServie:

    def test_la_page_repond_du_html(self, client, jeu):
        r = client.get("/")
        assert r.status_code == 200
        assert r.headers["Content-Type"].startswith("text/html")

    def test_resultats_n_existe_plus(self, client, jeu):
        """Spec 016. Les deux adresses servaient la MEME vue : un doublon d'URL
        finit toujours par diverger dans les tetes. La racine reste la seule.

        Retire le meme jour du proxy (`@public path`) et du portail interne
        (`resultats.maison.adn-dev.fr`), sans quoi le doublon aurait survecu
        ailleurs.
        """
        assert client.get("/resultats").status_code == 404

    def test_la_racine_sert_la_page_pas_un_json(self, client, jeu):
        """Un visiteur qui tape l'adresse du service doit voir le classement."""
        r = client.get("/")
        assert r.status_code == 200
        assert b"<!doctype html>" in r.data.lower()

    def test_le_mode_mur_sert_la_meme_page(self, client, jeu):
        """Le mode est choisi par la page, pas par le serveur : un seul fichier."""
        assert client.get("/?mur").data == client.get("/").data

    def test_servie_meme_sans_competition_active(self, client, app):
        """C'est la PAGE qui gere le cas, pas le serveur.

        Repondre 409 ici afficherait une erreur de navigateur au lieu d'un
        message lisible.
        """
        assert client.get("/").status_code == 200


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
        page = client.get("/").data.decode()
        externes = [u for u in re.findall(r'https?://[^\s"\'<>)]+', page)
                    if u != self.NAMESPACE_SVG]
        assert not externes, f"la page charge des ressources externes : {externes}"

    def test_aucune_balise_qui_va_chercher_quelque_chose_dehors(self, client, jeu):
        page = client.get("/").data.decode()
        for balise in re.findall(r"<(?:script|link|img|iframe)[^>]*>", page):
            for url in re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)', balise):
                assert url.startswith("data:") or url.startswith("/"), \
                    f"ressource distante : {url}"

    def test_aucune_police_telechargee(self, client, jeu):
        page = client.get("/").data.decode()
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

        page = client.get("/").data.decode()

        assert "Dupont" not in page, "aucun nom ne doit figurer dans le HTML servi"

    def test_les_noms_sont_inseres_par_textContent(self, client, jeu):
        """Les noms viennent de la base : jamais d'innerHTML sur eux."""
        page = client.get("/").data.decode()
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

    @pytest.mark.parametrize("champ",
                             ["classements", "competition", "calcule_le", "reussites"])
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
        page = client.get("/").data.decode()
        for champ in ("l.rang", "l.score", "l.blocs", "l.nom", "l.dossard"):
            assert champ in page, f"la page ne lit pas {champ}"


class TestFaitePourEtreProjetee:
    """Spec 016. Le reste — le rendu, le mouvement — se verifie dans un
    navigateur ; ces tests-la protegent les mecanismes qu'un oubli ferait
    disparaitre en silence."""

    def test_le_logo_du_club_est_servi_par_nous(self, client, jeu):
        page = client.get("/").data.decode()
        assert "/static/logo-club.png" in page

    def test_le_logo_existe_vraiment(self, client, jeu):
        """Un 404 sur le logo se verrait sur le mur, pas dans les tests."""
        r = client.get("/static/logo-club.png")
        assert r.status_code == 200
        assert r.data[:4] == b"\x89PNG"

    def test_les_lignes_sont_reutilisees_pas_recreees(self, client, jeu):
        """C'est la condition du mouvement : on n'anime pas ce qu'on detruit.

        La version precedente faisait `liste.innerHTML = ""` a chaque
        rafraichissement -- aucune animation n'etait possible.
        """
        page = client.get("/").data.decode()
        assert "etat.noeuds" in page
        assert ".animate(" in page, "la page doit deplacer les lignes (FLIP)"

    def test_le_fond_est_clair_par_defaut(self, client, jeu):
        """Un videoprojecteur AJOUTE de la lumiere : un fond sombre, c'est du
        mur non eclaire. Le sombre reste atteignable par ?sombre."""
        page = client.get("/").data.decode()
        debut = page.index(":root {")
        assert "--fond: #F1F4F8;" in page[debut:debut + 800]
        assert "body.sombre" in page

    def test_la_rotation_couvre_categories_et_circuits(self, client, jeu):
        page = client.get("/").data.decode()
        assert '"categorie", "circuit"' in page
        assert "programmerRotation" in page

    def test_le_plateau_qui_deborde_defile(self, client, jeu):
        page = client.get("/").data.decode()
        assert "programmerDefilement" in page

    def test_la_barre_de_categories_sert_aux_deux_modes(self, client, jeu):
        """Un seul composant, deux usages : sur le mur il dit où on en est dans
        le cycle, sur un téléphone c'est le sélecteur. Deux composants auraient
        divergé."""
        page = client.get("/").data.decode()
        assert "dessinerBarre" in page
        assert "body.mur #barre" in page, "la barre doit exister aussi en mode mur"
        assert "body.mur #barre, body.mur #recherche { display: none; }" not in page

    def test_la_jauge_de_rotation_vit_sur_la_categorie(self, client, jeu):
        """Un filet en haut de l'écran ne se relie à rien ; la jauge est posée
        là où on regarde déjà — sur le nom de la catégorie."""
        page = client.get("/").data.decode()
        assert "function jauger(" in page
        assert 'id="progression"' not in page, "l'ancienne barre du haut a disparu"

    def test_le_classement_se_lit_en_colonnes(self, client, jeu):
        """Adrien, 31/08 : « le classement en ligne n'est vraiment pas lisible,
        en colonne ce serait mieux ». Les rangs descendent, l'œil descend avec
        eux, et chaque colonne annonce sa tranche (« 4 → 10 ») — sans quoi rien
        ne dirait dans quel sens lire."""
        page = client.get("/").data.decode()
        assert "function agencer(" in page
        assert "function majEntete(" in page
        assert "gridAutoFlow" in page

    def test_les_colonnes_suivent_la_largeur(self, client, jeu):
        page = client.get("/").data.decode()
        assert "function colonnesPour(" in page
        assert "clientWidth" in page

    def test_la_page_retire_de_l_information_quand_la_place_manque(self, client, jeu):
        """Adrien, 31/08 : « quitte à supprimer des informations ou les
        redimensionner ». On n'affiche pas « Les Lezards Vagab… · n° » : on
        enlève, dans l'ordre, le dossard puis le club puis le compte de blocs.
        Le nom et le score ne partent jamais."""
        page = client.get("/").data.decode()
        assert "function regler_densite(" in page
        assert "etat.densite" in page
        assert "main.d4 .blocs" in page

    def test_le_podium_est_en_marches(self, client, jeu):
        """Premier au centre et plus haut, deuxième à gauche, troisième à droite
        et plus bas — la forme qu'on lit sans la lire."""
        page = client.get("/").data.decode()
        assert ".groupe.place-1 { order: 2;" in page
        assert ".groupe.place-2 { order: 1;" in page
        assert ".groupe.place-3 { order: 3;" in page

    def test_les_ex_aequo_partagent_leur_marche(self, client, jeu):
        """Ils sont à égalité : ils doivent être au même niveau, sur le même
        socle et avec la même médaille (Adrien, 31/08). Une marche porte donc un
        GROUPE de cartes, pas une carte."""
        page = client.get("/").data.decode()
        assert "function noeudGroupe(" in page
        assert "derniere.rang === l.rang" in page
        assert ".groupe .cartes" in page

    def test_le_classement_est_un_tableau(self, client, jeu):
        """Ce que font les services de résultats sportifs : un en-tête de
        colonnes, l'écart au premier, des chiffres tabulaires alignés."""
        page = client.get("/").data.decode()
        assert '"Rang", "Grimpeur", "Blocs", "Écart", "Score"' in page
        assert "tabular-nums" in page
        assert "function noeudEntete(" in page

    def test_les_scratchs_defilent_sur_le_mur(self, client, jeu):
        page = client.get("/").data.decode()
        assert '"categorie", "circuit", "scratch"' in page

    def test_le_spectateur_peut_suivre_des_grimpeurs(self, client, jeu):
        """Une étoile par ligne, une liste « Mes favoris », et la catégorie qui
        contient un favori se signale dans la barre."""
        page = client.get("/").data.decode()
        assert "★ Mes favoris" in page
        assert "function basculerFavori(" in page
        assert "function lignesFavorites(" in page
        assert "function categoriesAvecFavori(" in page

    def test_les_favoris_restent_sur_le_telephone(self, client, jeu):
        """Stockage LOCAL, pas cookie : un cookie repartirait dans chaque
        requête — vers une page que soixante personnes rafraîchissent toutes les
        quinze secondes — alors que ces noms n'ont rien à faire sur le réseau.
        Et ils sont liés à UNE compétition : les identifiants sont réattribués
        d'une édition à l'autre."""
        page = client.get("/").data.decode()
        assert "localStorage" in page
        assert "climbcontest.favoris" in page
        assert "document.cookie" not in page
        assert "range.competition === id" in page

    def test_les_entetes_ne_defilent_pas_avec_le_classement(self, client, jeu):
        """Dedans, ils repartaient avec les lignes et revenaient d'un à-coup à
        la fin de la remontée (Adrien, 01/09). Un tableau garde ses titres sous
        les yeux, de toute façon."""
        page = client.get("/").data.decode()
        assert 'id="entetes"' in page
        assert "function poserEntetes(" in page

    def test_la_grille_des_colonnes_suit_la_taille_du_texte(self, client, jeu):
        """En `em`, elle se calculait sur la police du conteneur (16 px) pendant
        que le contenu grandissait avec `--h` : sur une petite catégorie, le
        score sortait de sa colonne."""
        page = client.get("/").data.decode()
        assert "body.mur main.d1" in page
        assert "calc(var(--h) * 1.6)" in page

    def test_la_rotation_peut_etre_mise_en_pause(self, client, jeu):
        page = client.get("/").data.decode()
        assert 'id="pause"' in page
        assert "etat.enPause" in page
        assert "function figerJauge(" in page

    def test_le_balayage_change_de_categorie(self, client, jeu):
        page = client.get("/").data.decode()
        assert "touchstart" in page and "touchend" in page
        assert "function voisin(" in page

    def test_le_mouvement_se_coupe_si_l_utilisateur_le_demande(self, client, jeu):
        page = client.get("/").data.decode()
        assert "prefers-reduced-motion" in page
        assert "sansMouvement" in page


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
        page = client.get("/").data.decode()
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
                      "/admin/appareils", "/admin/reussites-tracees",
                      # Spec 015 : le classeur se regle depuis la console,
                      # et l'import -- dont la route existait depuis la spec
                      # 002 -- y a enfin un bouton.
                      "/admin/classeur", "/admin/classeur/test",
                      "/admin/classeur/jeton", "/admin/import/sheet"):
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
