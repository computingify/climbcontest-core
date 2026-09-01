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

    def test_le_tableau_reprend_le_podium(self, client, jeu):
        """Adrien, 01/09 : « mets les participants qui sont sur le podium aussi
        dans le tableau en dessous ».

        Le tableau commençait au rang 4 : pour savoir ce qu'avait fait le
        premier, il fallait remonter les yeux à l'autre bout de l'écran — et à
        quatre ex aequo, la marche ne le disait plus. Un classement se lit d'un
        bloc, de 1 a N ; la marche est le projecteur qu'on braque dessus, pas un
        morceau qu'on lui retire.
        """
        page = client.get("/").data.decode()
        assert "var suite = lignes;" in page
        assert "lignes.slice(tete.length)" not in page, \
            "le tableau ne doit plus sauter les grimpeurs du podium"

    def test_un_grimpeur_du_podium_a_deux_noeuds_donc_deux_cles(self, client, jeu):
        """La condition du mouvement, une fois le podium repris dans le tableau.

        Carte et ligne coexistent a l'ecran. Sous une seule cle, chaque repeinte
        detruisait celui que l'autre venait de creer, et l'animation — qui ne
        deplace que ce qui survit d'une repeinte a l'autre — ne partait jamais.
        """
        page = client.get("/").data.decode()
        assert "function clePodium(" in page
        assert 'return "pod:" + l.cle;' in page
        assert "vivants[clePodium(l)]" in page, \
            "une carte doit sortir de la table quand son grimpeur quitte la marche"

    def test_la_carte_de_podium_ne_repete_pas_les_colonnes_du_tableau(self, client, jeu):
        """« Si besoin, dans l'affichage du podium tu peux retirer quelques
        informations » (Adrien, 01/09).

        Le compte de blocs et l'ecart vivaient sur la carte sans etiquette, a
        cote d'un score deux fois plus gros : « 7 blocs −199 » se dechiffrait au
        lieu de se lire. Ils sont maintenant deux lignes plus bas, sous un
        en-tete qui les nomme — et la largeur qu'ils prenaient revient au nom,
        qui en manque des que deux ex aequo se partagent une marche.
        """
        page = client.get("/").data.decode()
        assert ".pod .blocs" not in page and ".pod .ecart" not in page, \
            "la carte n'affiche plus ni blocs ni ecart"
        # Le nom et le score, jamais : ce sont les deux choses qu'on vient lire.
        assert ".pod .nom {" in page
        assert ".pod .score {" in page

    def test_le_podium_reste_marque_dans_le_tableau(self, client, jeu):
        """Le lisere de medaille, TOUJOURS.

        Il etait supprime des que la page pouvait montrer une marche — donc
        presque partout, y compris sur un telephone qui n'en affiche jamais : les
        trois premiers y passaient inapercus. C'est lui qui relie la ligne 1 a la
        carte en or juste au-dessus.
        """
        page = client.get("/").data.decode()
        assert ".ligne.p1 { box-shadow: inset 5px 0 0 var(--or); }" in page
        assert "l.rang > 0 && l.rang <= 3 ? \" p\" + l.rang" in page
        assert "!avecPodium ? \" p\" + l.rang" not in page, \
            "le marquage ne depend plus de la presence d'une marche"

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
        assert "--grille-ligne: calc(var(--h)" in page

    def test_le_temps_d_affichage_decoule_du_defilement(self, client, jeu):
        """Adrien, 01/09 : « calcule le temps nécessaire pour faire une descente
        puis une remontée avant de passer à la catégorie suivante, avec un temps
        minimum pour les petites catégories ». C'est le défilement qui commande
        la rotation, et non l'inverse."""
        page = client.get("/").data.decode()
        assert "VITESSE_DEFILEMENT" in page
        assert "DUREE_MIN_MS" in page
        assert "etat.dureeAffichage" in page

    def test_le_defilement_survit_a_un_rafraichissement(self, client, jeu):
        """Les données sont relues toutes les 15 s : en recréant l'animation à
        chaque fois, elle repartait du haut et ne remontait jamais."""
        page = client.get("/").data.decode()
        assert "signatureDefilement" in page

    def test_les_titres_de_colonnes_ne_peuvent_pas_se_chevaucher(self, client, jeu):
        """Ils grandissaient avec la hauteur de ligne — qui monte quand la
        catégorie est petite — pendant que les colonnes se resserraient avec la
        fenêtre. Vu par Adrien sur une catégorie à un grimpeur : « GRIMPEUR » et
        « BLOCS » l'un sur l'autre."""
        page = client.get("/").data.decode()
        assert "clamp(0.6rem, calc(var(--h, 64px) * .2), 1.05rem)" in page
        assert ".entete span { overflow: hidden;" in page

    def test_la_densite_se_mesure_en_hauteurs_de_ligne(self, client, jeu):
        """Sur le mur tout est proportionnel à la hauteur de ligne : la place
        laissée au nom doit se mesurer dans cette unité, pas en pixels."""
        page = client.get("/").data.decode()
        assert "COUT_CHIFFRES" in page
        assert "pourLeNom" in page

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


# --- Le rejeu d'une archive (spec 018) --------------------------------------
#
# Le pari de la spec : PAS de seconde page de résultats à maintenir. Le même
# gabarit, une source de données différente. Ces tests vérifient la seule
# chose que Python puisse honnêtement vérifier — ce que le serveur rend — et
# laissent le comportement JavaScript à la vérification au navigateur.

class TestRejeuArchive:

    @pytest.fixture()
    def archive(self, app, jeu):
        from climbcontest import cycle
        from climbcontest.contest import enregistrer_reussite

        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        archive, _ = cycle.archiver(jeu["competition"], "chef")
        return archive

    def test_la_racine_lit_le_classement_en_direct(self, client, jeu):
        """A25. La page publique ne change pas d'un octet."""
        page = client.get("/").data.decode()
        assert 'data-source="/api/public/classement"' in page
        assert 'data-archive=""' in page

    def test_la_page_d_archive_pointe_l_archive(self, client, archive):
        """A24."""
        page = client.get(f"/console/archives/{archive.id}/resultats").data.decode()
        assert f'data-source="/admin/archives/{archive.id}/classement"' in page
        assert 'data-archive="2026-11-15"' in page

    def test_c_est_le_meme_gabarit(self, client, archive):
        """Pas de seconde page : podium, colonnes et scratchs viennent du même
        fichier. Une divergence d'affichage entre le direct et l'archive est
        donc structurellement impossible."""
        directe = client.get("/").data.decode()
        rejeu = client.get(f"/console/archives/{archive.id}/resultats").data.decode()
        for marqueur in ("id=\"podium\"", "id=\"barre\"", "id=\"defile\""):
            assert marqueur in directe and marqueur in rejeu

    def test_le_rafraichissement_est_coupe_sur_une_archive(self, client, archive):
        """A26, la moitié vérifiable en Python.

        L'autre moitié — compter les requêtes réelles — se fait au navigateur :
        `test_page_resultats` dit déjà pourquoi on ne simule pas le JavaScript
        ici. Ce test garantit au moins que la condition existe et porte sur la
        bonne variable.
        """
        page = client.get("/").data.decode()
        assert "if (!ARCHIVE) setInterval(charger, PERIODE_MS);" in page

    def test_une_archive_inconnue_donne_404(self, client, jeu):
        assert client.get("/console/archives/999/resultats").status_code == 404

    def test_la_page_est_servie_mais_ses_donnees_sont_fermees(
            self, app, client, archive):
        """La page ne contient aucune donnée — comme `/console`. Ce sont les
        noms qui sont protégés, et ils vivent derrière la session."""
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get(
            f"/console/archives/{archive.id}/resultats").status_code == 200
        assert client.get(
            f"/admin/archives/{archive.id}/classement").status_code == 401


class TestBandeauDeMessage:
    """Le minuteur de masquage doit être annulé avant d'en poser un autre.

    Trouvé en pilotant la console, pas par un test : après un archivage, la
    console disait le succès puis l'avertissement. Le message « ok » programme
    un masquage à six secondes ; ce minuteur survivait au message suivant et
    faisait **disparaître l'avertissement** tout seul. Un avertissement qui
    s'efface est pire que pas d'avertissement du tout — on croit avoir lu de
    travers.

    Comme le reste du JavaScript de la console, ça ne se simule pas ici : ce
    test vérifie que le garde-fou est présent, la vérification réelle s'est
    faite au navigateur (40 s d'observation).
    """

    def test_le_minuteur_precedent_est_annule(self, client, jeu):
        page = client.get("/console").data.decode()
        assert "clearTimeout(minuteurMessage);" in page

    def test_seuls_les_messages_ok_s_effacent_seuls(self, client, jeu):
        page = client.get("/console").data.decode()
        assert 'minuteurMessage = genre === "ok"' in page

    def test_l_archivage_ne_dit_qu_une_chose(self, client, jeu):
        """Deux appels successifs à `dire` s'écraseraient l'un l'autre — et on
        perdrait justement celui qui prévient."""
        page = client.get("/console").data.decode()
        assert 'avertissements.length ? "attention" : "ok"' in page


class TestPodiumExAequo:
    """Le podium ne doit ni déborder de ses cartes, ni couper un nombre.

    Trouvé par Adrien en regardant l'écran, pas par un test : sur un groupe où
    plusieurs grimpeurs sont ex æquo, « ça dépasse au niveau du podium ».

    Deux causes distinctes, et la seconde est la vraie :

    1. Le mobilier de la carte — le gros numéro de place, les marges, la taille
       du nom — ne rétrécissait pas quand la marche se divisait entre N ex
       æquo. À six, il restait moins de la moitié de la place pour le nom.
    2. **La colonne de contenu était un `1fr` nu.** Le `min-width` par défaut
       d'une piste de grille vaut `auto` : elle ne peut donc jamais devenir
       plus étroite que son contenu. Or `.chiffres` est en `nowrap`. La grille
       réclamait 404 px dans une carte de 373, et le nom, le club et les
       chiffres sortaient de 9 px **par la droite, par-dessus le bord arrondi**.

    Comme le reste du JavaScript de cette page, la mise en page ne se simule
    pas ici. Ces tests verrouillent les garde-fous ; la vérification s'est faite
    au navigateur, à 1280 et à 1920, sur six ex æquo et sur trois rangs
    distincts.
    """

    def test_la_colonne_de_contenu_peut_retrecir(self, client, jeu):
        """`1fr` nu = la carte déborde. C'est LE défaut."""
        page = client.get("/").data.decode()
        assert "clamp(56px, 5.6vw, 100px) minmax(0, 1fr)" in page
        # …et le `1fr` nu ne doit pas revenir par la petite porte.
        assert "clamp(56px, 5.6vw, 100px) 1fr" not in page

    def test_les_chiffres_se_rognent_au_lieu_de_pousser(self, client, jeu):
        page = client.get("/").data.decode()
        bloc = page[page.index(".pod .chiffres"):page.index(".pod .score")]
        assert "min-width: 0" in bloc and "overflow: hidden" in bloc

    def test_un_nombre_ne_se_coupe_jamais_en_deux(self, client, jeu):
        """Un « −1700 » rogné en « −17 » se lit comme un écart de dix-sept
        points. Un nom coupé sur une ellipse, lui, se comprend.

        La garde etait une requete de conteneur : l'ecart disparaissait sous
        430 px de carte, les blocs sous 330. Elle n'a plus d'objet — la carte ne
        porte plus ces deux nombres du tout, ils sont dans le tableau juste en
        dessous, sous un en-tete qui les nomme (voir
        `test_la_carte_de_podium_ne_repete_pas_les_colonnes_du_tableau`). Ce qui
        reste a tenir, c'est qu'ils ne reviennent pas sur la carte sans elle.
        """
        page = client.get("/").data.decode()
        assert ".pod .ecart" not in page and ".pod .blocs" not in page, \
            "un nombre sans etiquette n'a pas sa place sur la carte"
        # Le score, lui, ne se rogne pas : c'est le mobilier qui cede avant.
        assert ".groupe.c6 .pod .score" in page

    def test_la_carte_de_podium_garde_sa_propre_typographie(self, client, jeu):
        """`.nom`, `.club` et `.score` existent des DEUX cotes — ligne de
        tableau et carte de podium.

        `body.mur .nom` l'emportait donc sur `.pod .nom` : meme nombre de
        classes, mais un `body` en plus. Une carte se dessinait a la taille
        d'une ligne de tableau — 16,72 px la ou elle demandait 40 — et le podium
        etait regle sur la hauteur du classement, pas sur la sienne, depuis la
        spec 016. Invisible tant que TOUTES les cartes tombaient dedans ;
        flagrant des que `.groupe.cN` en a sorti les marches a plusieurs ex
        aequo : une marche a une seule carte se retrouvait deux fois plus petite
        que sa voisine.
        """
        page = client.get("/").data.decode()
        for classe in ("rang", "nom", "club", "score", "blocs", "ecart"):
            assert f"body.mur .ligne .{classe} {{" in page
            assert f"body.mur .{classe} {{" not in page, \
                f"« body.mur .{classe} » retombe sur la carte de podium"

    def test_le_mobilier_suit_le_nombre_d_ex_aequo(self, client, jeu):
        page = client.get("/").data.decode()
        assert '+ " c" + Math.min(6, m.lignes.length);' in page
        for palier in ("c2", "c3", "c4"):
            assert f".groupe.{palier} .pod" in page

    def test_les_paliers_couvrent_ce_que_le_podium_accepte(self, client, jeu):
        """`peindre()` supprime le podium au-delà de six cartes : les paliers
        doivent donc aller jusqu'à six, et pas plus loin."""
        page = client.get("/").data.decode()
        assert "surLePodium.length > 6" in page
        assert ".groupe.c6 .pod" in page
        assert ".groupe.c7" not in page


class TestLeTableauEtSesTitresSontAlignes:
    """Un tableau dont les titres ne sont pas au-dessus de leurs colonnes n'est
    pas un tableau.

    Signale par Adrien sur telephone : « SCORE » sortait de l'ecran et l'etoile
    tombait a la ligne. Deux causes distinctes, toutes deux dans la meme
    propriete heritee, `--grille-ligne` — et toutes deux presentes depuis la
    spec 016.

    Elle se resout PAR ELEMENT : les lignes l'heritent de `#liste`, les titres
    de `#entetes`. Il suffit donc que les deux ne lisent pas la meme chose pour
    que les deux grilles divergent, sans qu'aucune regle ne paraisse fausse.

    Comme le reste de la mise en page, elle ne se simule pas ici. Ces tests
    verrouillent les deux garde-fous ; les largeurs ont ete relevees au
    navigateur par sonde CDP, de 320 a 1920 px.
    """

    def test_la_grille_ne_se_declare_que_sur_main(self, client, jeu):
        """`#liste` portait sa propre valeur, et un `id` l'emporte sur tout.

        Les lignes recevaient donc cinq colonnes en `em` pendant que les titres
        en recevaient six en `--h` ou en `rem`. Sur le mur, la colonne « Blocs »
        du titre faisait 27 px pour 54 px de contenu ; sur telephone, l'etoile
        n'avait pas de colonne du tout et retombait a la ligne suivante.

        Effet de bord : les largeurs en `--h` de la spec 016 n'ont jamais
        atteint les lignes, restees sur les `em` que `#liste` figeait.
        """
        page = client.get("/").data.decode()
        debut = page.index("  #liste {")
        assert "--grille-ligne" not in page[debut:page.index("}", debut)], \
            "seul `main` declare --grille-ligne"
        for mort in ("#liste.d2", "#liste.d3", "#liste.d4"):
            assert mort not in page, \
                f"« {mort} » ne peut pas s'appliquer : les densites vivent sur `main`"

    def test_hors_du_mur_la_grille_est_en_rem(self, client, jeu):
        """`em` se resout sur l'element qui s'en sert : 16 px pour une ligne,
        10,88 px pour un titre en `0.68rem`. La meme valeur donnait deux
        grilles — 38 px de colonne « Rang » sur la ligne, 26 px sur son titre,
        qui sortait en « RAN ». En `rem`, les deux tombent l'une sur l'autre.
        """
        page = client.get("/").data.decode()
        for densite in ("main", "main.d1", "main.d2", "main.d3", "main.d4"):
            ligne = [l for l in page.splitlines()
                     if l.strip().startswith(f"body:not(.mur) {densite} {{")]
            assert ligne, f"regle « body:not(.mur) {densite} » attendue"
            assert "em " not in ligne[0].replace("rem ", ""), \
                f"« body:not(.mur) {densite} » doit se mesurer en rem : {ligne[0].strip()}"

    def test_une_colonne_peut_toujours_contenir_son_titre(self, client, jeu):
        """« Blocs » est la colonne la plus etroite, et la seule qui n'y arrivait
        pas : son titre cesse de retrecir a 0,6 rem pendant que la colonne, elle,
        continue de suivre `--h`. Sous 62 px de hauteur de ligne, « BLOCS »
        sortait en « BLOC »."""
        page = client.get("/").data.decode()
        assert "max(calc(var(--h) * .62), 2.4rem)" in page

    def test_la_densite_compte_ce_qui_reste_vraiment_au_nom(self, client, jeu):
        """Les seuils portaient sur la largeur TOTALE et ignoraient l'etoile,
        les gouttieres et le rembourrage. A 470 px de fenetre, la page choisissait
        la densite 3 en laissant 75 px au nom — « Vialle Jade » en demande 88, et
        « Nieuviarts Martin » 139 (mesure au canevas)."""
        page = client.get("/").data.decode()
        assert "COUT_TELEPHONE" in page
        assert "LARGEUR_NOM" in page
        assert "largeur >= 520 ? 1" not in page, \
            "l'ancien seuil sur la largeur totale ne doit pas revenir"


class TestPodiumEtColonnesSuiventLaLargeur:
    """Le podium et les tableaux côte à côte ne dépendent plus du mode mur.

    Adrien, 01/09 : « je veux toujours avoir le podium mais en plus je veux que
    les participants du podium soient dans le tableau en dessous. Et je veux
    toujours ton système pour afficher plusieurs tableaux en même temps côte à
    côte **lorsque la page le permet** ».

    « Lorsque la page le permet » est une condition de LARGEUR, pas de mode. Les
    deux étaient pourtant réservés à `?mur` depuis la spec 016 : sur le portable
    de la salle, et sur la relecture d'une archive depuis la console — la même
    page, sans le paramètre — il n'y avait ni marche ni colonnes, juste un
    tableau d'une colonne au milieu de 1 800 px.

    C'est le même écran et la même page : ce qui doit trancher, c'est la place
    disponible. Le téléphone, lui, ne change pas — sous `LARGEUR_PODIUM` il n'y
    a toujours ni podium ni colonnes, et un podium y mangerait tout l'écran.

    La mise en page ne se simule pas ici : ces tests verrouillent les garde-fous,
    la vérification s'est faite au navigateur à 1920, 1280, 880 et 390 px.
    """

    def test_le_podium_ne_depend_plus_du_mode_mur(self, client, jeu):
        page = client.get("/").data.decode()
        assert "  #podium.visible { display: flex; }" in page
        assert "body.mur #podium.visible" not in page

    def test_le_podium_depend_de_la_largeur(self, client, jeu):
        """`LARGEUR_PODIUM` reste le seul juge : au-dessus il s'affiche, en
        dessous — un téléphone — jamais."""
        page = client.get("/").data.decode()
        assert "var podium = avecPodium && lignes.length > 3" in page
        assert "var podium = MUR &&" not in page
        assert "window.innerWidth >= LARGEUR_PODIUM" in page

    def test_les_colonnes_ne_dependent_plus_du_mode_mur(self, client, jeu):
        """`colonnesPour()` est appelée sans condition, et `.colonnes` porte la
        grille hors du mur."""
        page = client.get("/").data.decode()
        assert "var colonnes = colonnesPour(suite.length);" in page
        assert 'el.liste.classList.toggle("colonnes", colonnes > 1);' in page
        assert "body.mur #liste, #liste.colonnes {" in page

    def test_une_colonne_coute_plus_cher_hors_du_mur(self, client, jeu):
        """Le gabarit hors du mur porte une colonne DE PLUS — l'étoile des
        favoris — et se mesure en `rem`, pas en multiples de la hauteur de
        ligne : 389 px de mobilier avant le nom. À 430 px il en resterait 41
        pour « Nieuviarts Martin ».

        Ce coût n'est pas recopié : il se DÉDUIT des deux constantes dont
        `regler_densite()` se sert déjà. Écrit en dur, il divergerait le jour où
        l'une des deux bouge.
        """
        page = client.get("/").data.decode()
        assert "function minColonne(" in page
        assert ("COUT_TELEPHONE[1].rem * unRem() + COUT_TELEPHONE[1].px + LARGEUR_NOM"
                in page)
        assert "var MIN_COLONNE_MUR = 430;" in page

    def test_un_rem_se_lit_au_lieu_d_etre_suppose(self, client, jeu):
        """Le lecteur qui grossit la police de son navigateur élargit d'autant
        le gabarit. Les deux calculs qui s'en servent — la densité et le nombre
        de colonnes — lisent la même valeur, au même endroit."""
        page = client.get("/").data.decode()
        assert "function unRem(" in page
        assert page.count("getComputedStyle(document.documentElement).fontSize") == 1

    def test_le_tableau_reprend_toujours_le_podium(self, client, jeu):
        """Ce que la 0.13.0 a apporté ne doit pas repartir : les trois premiers
        restent dans le tableau, sous la marche."""
        page = client.get("/").data.decode()
        assert "var suite = lignes;" in page
        assert "lignes.slice(tete.length)" not in page

    def test_le_classement_par_club_a_des_cles_distinctes(self, client, jeu):
        """`participant_id` vaut **0** pour toutes les lignes du classement par
        club — un club n'est pas un participant. Or la clé apparie une ligne à
        son nœud d'une repeinture à l'autre : à clé partagée, les cinq clubs se
        disputaient le même nœud, déplacé de l'un à l'autre. Le classement des
        clubs n'affichait qu'UNE ligne, la dernière — et, depuis que le podium
        existe hors du mur, deux marches vides à côté d'une troisième.
        """
        page = client.get("/").data.decode()
        assert "function cleDe(" in page
        assert 'l.participant_id ? String(l.participant_id) : "nom:" + l.nom' in page
        assert "cle: String(l.participant_id)" not in page
        assert 'cle: c.groupe + "-" + l.participant_id' not in page

    def test_ni_la_recherche_ni_les_favoris_n_ont_de_podium(self, client, jeu):
        """Ces deux vues rassemblent des lignes prises dans dix classements :
        leurs rangs ne se comparent pas entre eux. Trois « 1er » de trois
        catégories y feraient trois cartes d'or côte à côte, et un favori sorti
        du classement (rang 0) une marche sans médaille."""
        page = client.get("/").data.decode()
        assert "peindre(lignes, !q && !surFavoris);" in page
