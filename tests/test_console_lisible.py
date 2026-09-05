"""La console d'administration — spec 021.

⚠️ Ce fichier verifie ce qu'un test Python PEUT verifier honnetement du
gabarit, et rien de plus. Le script de `admin.html` est EN LIGNE : il n'est pas
importable, et `tests/js/` ne teste que les modules de la PWA juge. Le
comportement du tiroir epingle, du bouton a maintenir et des deux themes est du
CSS et du JavaScript de page -- le simuler ici donnerait une fausse assurance.
Il se verifie au navigateur, et le plan de la spec porte cette liste-la.

C'est la meme honnetete qu'en tete de `test_page_resultats.py`.
"""
import re

import pytest


@pytest.fixture()
def page(client):
    """Le gabarit de la console. Servi sans session : il ne porte aucune donnee.

    C'est le choix de `routes/pages.py` -- la page est une coquille, tout ce
    qu'elle affiche arrive ensuite par `fetch` sur des routes protegees.
    """
    reponse = client.get("/console")
    assert reponse.status_code == 200
    return reponse.data.decode()


class TestServie:

    def test_la_console_repond_du_html(self, client):
        r = client.get("/console")
        assert r.status_code == 200
        assert r.headers["Content-Type"].startswith("text/html")
        assert "<!doctype html>" in r.data.decode().lower()


class TestAucuneDependanceExterieure:
    """Non-regression de la regle posee aux specs 005 et 016.

    Une console qu'on ouvre le matin d'une competition ne peut pas attendre un
    CDN, ni echouer parce que le wifi de la salle rame.
    """

    def test_aucune_ressource_distante(self, page):
        # Le `xmlns` du SVG est une URL de specification, jamais telechargee.
        restant = page.replace("http://www.w3.org/2000/svg", "")
        assert "https://" not in restant
        assert "http://" not in restant

    def test_aucune_police_telechargee(self, page):
        assert "@font-face" not in page
        assert "fonts.googleapis" not in page


class TestLaPageClasseurPorteUnSeulNom:
    """A1. Le tiroir annoncait « Classeur », la barre et le titre disaient
    « Classeur Google ». Un menu qui ne mene pas au titre qu'il annonce fait
    douter d'avoir clique au bon endroit -- et ce doute coute le plus cher le
    matin d'une competition, quand on cherche vite.
    """

    def test_le_titre_de_la_vue_est_classeur(self, page):
        assert "<h1>Classeur</h1>" in page

    def test_la_barre_annonce_le_meme_nom(self, page):
        assert 'titre: "Classeur",' in page

    def test_plus_aucun_titre_classeur_google(self, page):
        assert "Classeur Google</h1>" not in page
        assert 'titre: "Classeur Google"' not in page

    def test_le_sous_titre_dit_toujours_que_c_est_google(self, page):
        """Le nom raccourcit, l'information ne se perd pas : elle descend d'un
        cran, la ou elle a sa place."""
        assert "feuille Google" in page


class TestImporterNExistePlusEnDouble:
    """A2. Deux boutons du meme nom, deux comportements : celui-ci partait sans
    mode (mise a jour implicite), celui de la vue Competition fait choisir. Le
    plus faible etait le plus visible.
    """

    def test_le_bouton_a_disparu(self, page):
        assert "btnImporterClasseur" not in page

    def test_le_vrai_bouton_reste(self, page):
        assert 'id="btnImporter"' in page

    def test_les_deux_cartes_vivent_dans_le_meme_ecran(self, page):
        """Depuis F7, « Importer » a rejoint la vue Classeur : la carte du haut
        n'a plus a renvoyer ailleurs, la suivante est juste en dessous."""
        vue = page.split('id="vueClasseur"')[1].split("</section>")[0]
        assert "<h2>Importer le classeur</h2>" in vue
        assert "Compétition → Importer" not in page


class TestConfirmerSeMaintient:
    """A4. Sept caracteres a frapper, sur un ordinateur pose sur un coin de
    table dans une salle d'escalade. Ce que le mot apportait -- l'ARRET -- est
    garde ; c'est la frappe qui part.
    """

    def test_plus_de_champ_a_frapper(self, page):
        assert 'id="dlgMot"' not in page
        assert "Écris <code>EFFACER</code>" not in page

    def test_le_bouton_est_la_avec_sa_jauge(self, page):
        assert 'id="dlgOk"' in page
        assert 'id="dlgRemplissage"' in page

    def test_le_bouton_n_est_pas_un_bouton_de_soumission(self, page):
        """Dans un `<form method="dialog">`, un bouton de soumission fermerait
        la fenetre au premier clic -- exactement ce que le maintien empeche."""
        bouton = re.search(r'<button[^>]*id="dlgOk"[^>]*>', page).group(0)
        assert 'type="button"' in bouton
        assert 'value="ok"' not in bouton

    def test_la_consigne_est_rattachee_au_bouton(self, page):
        """A6 : un bouton qui demande un geste inhabituel doit le DIRE, et le
        dire a un lecteur d'ecran aussi."""
        assert 'aria-describedby="dlgAide"' in page
        assert 'id="dlgAide"' in page

    def test_la_duree_du_maintien_n_est_ecrite_qu_une_fois(self, page, client):
        """Le CSS recoit sa duree du script : deux valeurs a tenir synchrones a
        la main finiraient par diverger, et la jauge mentirait.

        ⚠️ Depuis l'extraction du geste (spec 044), la duree n'appartient plus
        au gabarit : elle vit dans `static/console/confirmer.js`, avec la
        mecanique que cette fenetre PARTAGE desormais avec l'ecran d'ouverture.
        Le gabarit n'en garde qu'une copie pour ECRIRE le libelle -- et c'est
        justement ce que ce test surveille : une seule definition du minuteur.
        """
        assert "var MAINTIEN_MS" not in page
        assert "transition-duration" not in page.split("<script>")[0]

        module = client.get("/static/console/confirmer.js").data.decode()
        assert module.count("MAINTIEN_MS = 2000") == 1

    def test_le_geste_du_dialogue_est_CELUI_du_module(self, page):
        """⚠️ Le defaut que l'extraction ferme : quatre-vingt-dix lignes de
        maintien vivaient en double dans le depot -- ici et dans le module de
        l'ecran d'ouverture. Deux implementations d'un meme geste divergent,
        c'est la lecon de `cascade.py` et de son test miroir.

        Le gabarit ne doit donc plus porter AUCUN morceau de la mecanique.
        """
        for morceau in ("onpointerdown", "e.repeat", "strokeDashoffset",
                        "classList.add(\"tenu\")"):
            assert morceau not in page, morceau
        assert "window.poserMaintien(bouton" in page

    def test_le_marqueur_part_toujours_au_serveur(self, page):
        """Le mot n'est plus un geste humain, il reste un marqueur de protocole
        -- et le serveur continue de l'exiger."""
        assert 'var MARQUEUR_CONFIRMATION = "EFFACER";' in page


class TestLeTiroirSEpingle:
    """A10-A12. Sur un ecran de 1920 px, il restait 1600 px vides a droite du
    tiroir : le recouvrir puis le refermer n'avait aucun sens.
    """

    def test_le_seuil_est_une_requete_media(self, page):
        """Et non un test JavaScript : la mise en page ne doit pas attendre
        l'execution d'un script."""
        assert page.count("@media (min-width: 1080px)") == 1

    def test_le_voile_et_le_burger_disparaissent(self, page):
        """Un bouton qui n'ouvre rien est pire qu'un bouton absent.

        La regle doit vivre DANS la requete media -- hors d'elle, elle
        masquerait le burger sur telephone, ou il est la seule facon d'ouvrir
        le menu. On verifie donc l'ordre, pas seulement la presence.
        """
        regle = ".voile, .burger { display: none; }"
        assert regle in page
        assert page.index("@media (min-width: 1080px)") < page.index(regle)
        assert page.index(regle) < page.index("--- Le contenu ---")

    def test_le_script_ne_connait_le_seuil_qu_une_fois(self, page):
        assert page.count('matchMedia("(min-width: 1080px)")') == 1
        assert "function tiroirEpingle()" in page

    def test_ouvrir_le_tiroir_ne_fait_rien_quand_il_est_epingle(self, page):
        """Sans cette sortie, un clic d'entree laisserait
        `aria-expanded="false"` sur un menu visible en permanence."""
        assert "if (tiroirEpingle()) return;" in page


class TestLesClassementsSontDesInterrupteurs:
    """F6, demande d'Adrien pendant l'implementation.

    Une case a cocher dit « je consens » ; ces lignes-la disent « c'est allume
    ou c'est eteint ». Ce n'est pas la meme question.
    """

    def test_la_glissiere_existe(self, page):
        assert ".glissiere {" in page
        assert "label.bascule {" in page

    def test_la_case_native_est_conservee(self, page):
        """Invisible, jamais `display: none` : elle garde le clavier, le focus,
        l'etat et le lecteur d'ecran."""
        assert 'interrupteur.type = "checkbox";' in page
        assert "label.bascule input { position: absolute; opacity: 0;" in page
        assert "label.bascule input { display: none" not in page

    def test_le_lecteur_d_ecran_entend_un_interrupteur(self, page):
        assert 'interrupteur.setAttribute("role", "switch");' in page

    def test_le_visuel_est_un_frere_pas_un_pseudo_element_sur_l_input(self, page):
        """Un `::after` sur un element remplace tient de la tolerance des
        navigateurs. Cette console doit marcher le matin d'une competition, pas
        « en general »."""
        assert "label.bascule input:checked + .glissiere" in page

    def test_le_focus_clavier_se_voit(self, page):
        assert "label.bascule input:focus-visible + .glissiere" in page

    def test_le_texte_d_aide_parle_d_allumer(self, page):
        """« Decoche » ne veut plus rien dire quand il n'y a plus de case."""
        assert "Éteins un classement" in page
        assert "Décoche un classement" not in page


class TestClairEtSombre:
    """A13-A14. Les couleurs etaient figees et rien ne regardait le systeme :
    sur un Mac regle en clair, en plein jour, on lisait un ecran noir.
    """

    def test_le_clair_est_le_defaut_pas_un_cas_particulier(self, page):
        """`--fond` doit etre defini HORS de toute requete media. C'est ce qui
        fait qu'un navigateur sans `prefers-color-scheme` affiche du clair."""
        avant_media = page.split("@media (prefers-color-scheme: dark)")[0]
        assert "--fond: #FBFAF8;" in avant_media

    def test_le_sombre_existe_et_suit_le_systeme(self, page):
        assert page.count("@media (prefers-color-scheme: dark)") == 1

    def test_les_controles_natifs_suivent_aussi(self, page):
        """Sans `color-scheme`, les cases a cocher, les <dialog> et les barres
        de defilement natives resteraient claires sur un fond sombre."""
        assert "color-scheme: light dark;" in page

    def test_aucun_reglage_de_theme_dans_la_console(self, page):
        """Le systeme decide, et c'est tout : rien a regler, rien a memoriser,
        rien qui puisse rester coince sur un mauvais choix."""
        assert "prefers-color-scheme" in page
        assert "localStorage" not in page

    def test_plus_aucune_trace_du_mauve(self, page):
        for mauve in ("#A87FC7", "#7A4F99", "accent-fonce"):
            assert mauve not in page

    def test_l_accent_du_logo_dans_les_deux_themes(self, page):
        assert "--accent: #B5761C;" in page          # clair
        assert "--accent: #E0A94A;" in page          # sombre

    @pytest.mark.parametrize("en_dur", ["#17111f", "rgba(13, 15, 20", "--carte2"])
    def test_plus_de_couleur_ecrite_en_dur(self, page, en_dur):
        """`--carte2` n'a JAMAIS existe : le fond du message d'erreur de
        connexion etait donc transparent depuis toujours."""
        assert en_dur not in page

    def test_ce_qu_on_ecrit_sur_un_aplat_bascule_avec_le_theme(self, page):
        """L'or du logo est trop clair pour ecrire dessus en blanc ; le saumon
        du theme sombre aussi. D'ou deux variables, pas une couleur figee."""
        assert "--sur-accent" in page
        assert "--sur-alerte" in page

    def test_une_case_a_cocher_reste_une_case(self, page):
        """Signale par Adrien le 01/09 : dans « Ce qu'affiche la page de
        resultats », les categories sortaient du cadre.

        La regle globale donnait aux cases a cocher `width: 100%`, un fond, une
        bordure et 10 px de rembourrage : une case s'etalait sur toute la
        largeur de sa carte et rejetait son libelle dehors. Le meme defaut
        deformait la case « Effacer quand meme » de la fenetre de confirmation.
        Une seule cause, corrigee a la racine.
        """
        assert 'input:not([type="checkbox"]):not([type="radio"])' in page
        # Et surtout : plus aucune regle nue qui ratisserait tous les `input`.
        assert "\n  input, select, textarea {" not in page

    def test_un_lien_bouton_masque_reste_masque(self, page):
        """N'importe quel `display` d'auteur bat le `[hidden]` du navigateur.

        Sans regle, « Ouvrir le classeur » (`a.secondaire`, en
        `display: inline-block`) s'affichait alors qu'aucun classeur n'est
        relie, et proposait d'ouvrir un lien vide.

        La rustine etait locale, et il en fallait une par element : quatre
        avaient ete posees, et la cinquieme manquait toujours -- c'est ce qui a
        laisse `#console` s'afficher sans session. Une seule regle globale les
        remplace, et ce test garde celle-la. Le detail est dans
        `test_console_fermee.py`.
        """
        assert "[hidden] { display: none !important; }" in page

    def test_le_qr_reste_sur_du_blanc(self, page):
        """Un QR sur fond sombre ne se lit pas. Le cadre reste blanc dans les
        deux themes, et un trait le detoure pour qu'il ne se fonde pas dans une
        surface claire."""
        assert ".qr-cadre { background: #fff;" in page


class TestLOrdreDesClassementsVientDuServeur:
    """⚠️ La console réimplémentait cette règle métier en JavaScript, alors que
    `classement_service.ordre` l'appliquait déjà à la page publique.

    Deux versions d'une même règle, dans deux langages, divergent toujours —
    et elles divergeaient déjà : sur un circuit absent (`""` côté serveur,
    `g.nom` côté JS) et sur la comparaison des chaînes (point de code contre
    `localeCompare`). Ce test verrouille l'ordre à sa source.
    """

    def test_la_regle_est_celle_de_la_page_publique(self):
        """Scratchs généraux, puis chaque circuit suivi de ses catégories, puis
        les clubs — sans jamais séparer un circuit de sa famille."""
        from types import SimpleNamespace

        from climbcontest import classement_service

        def c(type_, groupe, circuit=None):
            return SimpleNamespace(type=type_, groupe=groupe, circuit=circuit)

        melange = [
            c("club", "Les Lezards"),
            c("categorie", "U13 H", "U13"),
            c("scratch", "General F"),
            c("circuit", "U11", "U11"),
            c("categorie", "U11 F", "U11"),
            c("circuit", "U13", "U13"),
            c("scratch", "General H"),
            c("categorie", "U13 F", "U13"),
            c("categorie", "U11 H", "U11"),
        ]
        ordonne = [x.groupe for x in sorted(melange, key=classement_service.ordre)]
        assert ordonne == [
            "General F", "General H",
            "U11", "U11 F", "U11 H",
            "U13", "U13 F", "U13 H",
            "Les Lezards",
        ]

    def test_un_circuit_absent_ne_fait_pas_tomber_le_tri(self):
        """Un classement sans circuit -- donnee incomplete, ou scratch general
        mal type -- doit se ranger sans lever."""
        from types import SimpleNamespace

        from climbcontest import classement_service

        sans = SimpleNamespace(type="categorie", groupe="U15 F", circuit=None)
        avec = SimpleNamespace(type="circuit", groupe="U11", circuit="U11")
        assert sorted([avec, sans], key=classement_service.ordre)[0] is sans

    def test_la_console_ne_reordonne_plus_rien(self, page):
        """Le JavaScript ne doit plus porter de copie de la regle."""
        assert "function ordonner(" not in page


class TestCarteCascade:
    """La carte de la cascade de couleurs est servie — spec 025.

    Un test de gabarit ne prouve pas que l'écran marche ; il prouve qu'il est
    LÀ. Le reste se vérifie au navigateur, et la spec le dit.
    """

    def test_la_carte_est_dans_la_vue_general(self, page):
        assert 'id="carteCascade"' in page
        assert "Cascade de couleurs" in page

    def test_les_trois_prereglages(self, page):
        for valeur in ("aucune", "classeur", "mesure"):
            assert 'value="%s"' % valeur in page

    def test_les_ancrages_du_script(self, page):
        for identifiant in ("reglesCascade", "controleCascade", "apercuCascade",
                            "porteeCascade", "avertCascade", "btnCascade"):
            assert 'id="%s"' % identifiant in page

    def test_l_avertissement_du_classeur_part_masque(self, page):
        """Il ne doit crier qu'une fois la règle écartée de celle du classeur."""
        assert 'id="avertCascade" hidden' in page

    def test_une_seule_table_de_teintes(self, page):
        """⚠️ Deux `var TEINTES` dans la meme portee, c'est legal en JavaScript
        et silencieux : la derniere ecrite gagne.

        Le cas s'est produit : la spec 025 et la spec 027 ont chacune ajoute la
        sienne, a des endroits differents du fichier. Git les a fusionnees sans
        conflit, et la table de la cascade -- qui ne porte que les six couleurs
        de difficulte -- a efface celle de « Circuits », qui porte aussi les
        couleurs de PRISES. Rien ne cassait : les pastilles de prises devenaient
        seulement hachurees, comme des couleurs inconnues.
        """
        assert page.count("var TEINTES") == 1
        # Et elle porte bien les deux familles.
        for couleur in ("jaune", "noir", "blanc", "fluo"):
            assert '"%s":' % couleur in page

    def test_sans_cascade_la_carte_ne_montre_pas_de_regle(self, page):
        """Demande d'Adrien du 02/09 : « je veux que la partie règle ne soit
        pas affichée si Aucune cascade est sélectionné ».

        La carte offrait « + Ajouter une règle » sous un titre qui ne
        s'appliquait à rien. Les phrases, le contrôle et l'aperçu s'en vont
        ensemble : un seul `hidden` sur le groupe, pas trois.
        """
        assert 'id="blocRegleCascade"' in page
        assert '$("blocRegleCascade").hidden = sansCascade;' in page
        # Le titre est DEDANS, sinon il resterait seul au-dessus du vide.
        bloc = page.split('id="blocRegleCascade"')[1].split("</div>\n\n")[0]
        for ancre in ("La règle", "reglesCascade", "controleCascade",
                      "apercuCascade"):
            assert ancre in bloc, ancre

    def test_sans_cascade_la_carte_ne_montre_pas_NON_PLUS_la_portee(self, page):
        """« Si on sélectionne aucune cascade, je ne veux même pas voir la
        partie où on sélectionne sur quelle catégorie ça s'applique. » — Adrien,
        03/09 (spec 033, R1).

        Le regroupement de la spec 032 s'était arrêté une carte trop tôt :
        l'interrupteur par catégorie restait affiché sous un titre qui promet
        d'appliquer une règle qui n'existe pas.
        """
        assert 'id="blocPorteeCascade"' in page
        bloc = page.split('id="blocPorteeCascade"')[1].split("</section>")[0]
        for ancre in ("Où elle s'applique", "rapideCascade", "porteeCascade"):
            assert ancre in bloc, ancre

    def test_les_deux_groupes_obeissent_a_UNE_seule_condition(self, page):
        """Deux conditions écrites séparément finissent par diverger : c'est le
        défaut même que ce lot corrige, une carte plus bas."""
        assert 'var sansCascade = (quoi === "aucune");' in page
        assert '$("blocRegleCascade").hidden = sansCascade;' in page
        assert '$("blocPorteeCascade").hidden = sansCascade;' in page

    def test_le_bouton_coche_se_voit(self, page):
        """« Lorsqu'elle est sélectionnée, le petit rond n'est pas visible. Il
        faut que ce soit plus clair pour l'utilisateur. » — Adrien, 03/09
        (spec 033, R2).

        Les boutons étaient des radios NATIFS, sans `accent-color` : point bleu
        système en clair, et en sombre un point dont le clair est presque celui
        des cercles vides. La pastille est désormais dessinée, et la carte
        cochée prend un fond teinté — deux signaux, dont un qui ne dépend pas
        de la teinte.
        """
        assert 'fieldset.choix input[type="radio"] {' in page
        assert "appearance: none" in page
        # L'anneau ET le point, tous deux a l'accent de la console.
        bloc = page.split('fieldset.choix input[type="radio"]:checked {')[1] \
                   .split("}")[0]
        assert "border-color: var(--accent)" in bloc, bloc
        assert 'fieldset.choix input[type="radio"]:checked::before { transform: scale(1); }' in page
        # Et la carte entiere, pour que le choix se lise sans viser la pastille.
        assert re.search(
            r"fieldset\.choix label:has\(input:checked\) \{[^}]*background:",
            page), "la carte cochee ne prend aucun fond"

    def test_le_choix_reste_lisible_sans_couleur(self, page):
        """Un signal de plus que la teinte : la bordure interne. Environ 8 %
        des hommes distinguent mal certaines couleurs, et il y a des
        organisateurs hommes."""
        bloc = page.split("fieldset.choix label:has(input:checked) {")[1].split("}")[0]
        assert "box-shadow: inset" in bloc, bloc

    def test_sur_mesure_est_selectionnable_depuis_comme_le_classeur(self, page):
        """⚠️ Le second défaut du 02/09 : « si je sélectionne Comme le classeur
        puis Sur mesure, ce dernier n'est pas sélectionnable, il faut repasser
        par Aucune cascade ».

        Le bouton coché était DÉDUIT des phrases : vide → « aucune », égales à
        celles du classeur → « classeur », sinon → « sur mesure ». Cliquer
        « Sur mesure » en venant de « Comme le classeur » ne changeait aucune
        phrase, la déduction rendait toujours « classeur », et le bouton se
        décochait sous le doigt.

        Partir des phrases du classeur pour les retoucher est le cas NORMAL :
        c'est une intention, elle ne se lit pas dans les phrases. La carte la
        mémorise donc.
        """
        assert "surMesure: false" in page
        assert 'cascade.surMesure = (radio.value === "mesure");' in page
        assert "cascade.surMesure ? \"mesure\"" in page

    def test_l_avertissement_reste_calcule_sur_les_phrases(self, page):
        """⚠️ Et pas sur le bouton coché. Il dit si le CLASSEUR saura suivre la
        règle — une question sur les phrases, pas sur l'intention. Le brancher
        sur `surMesure` le ferait crier sur une règle que le classeur sait
        parfaitement reproduire."""
        assert '$("avertCascade").hidden = !ecarte;' in page
        assert ("var ecarte = cascade.regles.length > 0\n"
                "              && !memesRegles(cascade.regles, cascade.reference);"
                in page)
        # Et surtout PAS sur le bouton coche.
        assert '$("avertCascade").hidden = (quoi !== "mesure");' not in page


class TestLaVueCircuitsNeMontreQueLaPastille:
    """Demande d'Adrien du 02/09 : « sur la page Circuits, retire le texte pour
    la difficulté et les prises, je ne veux conserver que la pastille de
    couleur ».

    Deux colonnes de mots répétés soixante fois poussaient « Circuits » et
    « Catégories » hors de l'écran — c'est-à-dire exactement ce que la vue sert
    à vérifier (spec 019).
    """

    def test_la_cellule_ne_pose_plus_le_nom_a_cote_de_la_pastille(self, page):
        corps = page.split("function celluleTeinte(")[1].split("\n  }")[0]
        assert "lu-seulement" in corps, (
            "le nom doit rester lisible par un lecteur d'ecran")
        assert "texte.textContent = nom;" not in corps, (
            "le nom est encore ecrit a cote de la pastille")

    def test_le_nom_reste_atteignable_autrement(self, page):
        """Une pastille seule, sans son nom accessible, serait une information
        réservée à ceux qui distinguent les couleurs."""
        corps = page.split("function celluleTeinte(")[1].split("\n  }")[0]
        assert "span.title = nom;" in corps          # au survol
        assert "lu.textContent = nom;" in corps      # pour les lecteurs d'ecran
        assert ".lu-seulement {" in page
        assert "clip-path: inset(50%)" in page

    def test_les_en_tetes_de_colonne_restent(self, page):
        """Ce sont eux qui disent ce que les deux pastilles signifient."""
        assert "<th>Difficulté</th>" in page
        assert "<th>Prises</th>" in page


class TestLaVueReussitesMontreCeQuiVientDArriver:
    """« Je viens de faire un scan manuel avec mon téléphone et je suis revenu
    sur la partie réussite. Je m'attendais à avoir une entrée ou un tableau avec
    la liste des réussites qui ont été scannées par ce téléphone. » — Adrien,
    03/09 (spec 033, R12).

    La vue savait SAISIR et RETROUVER — deux gestes qui supposent qu'on sait
    déjà ce qu'on cherche. La route `/admin/reussites-tracees` gère pourtant le
    cas « aucune référence » depuis la spec 011, sans aucun appelant.
    """

    def test_la_carte_est_dans_la_vue(self, page):
        assert "Les dernières réussites" in page
        for identifiant in ("corpsDernieres", "filtreAppareil",
                            "btnRafraichirReussites"):
            assert 'id="%s"' % identifiant in page, identifiant

    def test_elle_arrive_AVANT_la_saisie_a_la_main(self, page):
        """C'est ce qu'on vient voir en revenant d'un scan ; la saisie est le
        geste de rattrapage, pas la question."""
        assert page.index("Les dernières réussites") \
            < page.index("Saisir une réussite à la main")

    def test_elle_interroge_la_route_qui_existe_deja(self, page):
        """On ajoute l'écran, pas le serveur."""
        assert '"/admin/reussites-tracees?limite=' in page
        assert '"&appareil=" + encodeURIComponent(appareil)' in page

    def test_le_filtre_propose_tous_les_telephones(self, page):
        assert "Tous les téléphones" in page

    def test_le_minuteur_ne_tourne_que_sur_cette_vue(self, page):
        """Une console laissée ouverte sur « Réglages » ne doit pas interroger
        la base toutes les dix secondes pour un tableau que personne ne
        regarde."""
        assert "quitte: fermerReussites" in page
        assert "if (cle !== nom && VUES[cle].quitte) VUES[cle].quitte();" in page
        assert "clearInterval(minuteurDernieres)" in page

    def test_une_liste_vide_le_dit_en_toutes_lettres(self, page):
        """« Aucun résultat » et un tableau vide ne se ressemblent pas quand on
        cherche une réponse dans le feu de l'action."""
        assert "Aucune réussite pour l'instant." in page
        assert "Ce téléphone n'a encore rien envoyé." in page

    def test_une_panne_ne_crie_pas_toutes_les_dix_secondes(self, page):
        """La carte se recharge seule : un message d'erreur par cycle rendrait
        la console inutilisable pendant une coupure."""
        assert "Liste indisponible : " in page

    def test_le_hors_circuit_est_signale(self, page):
        """Le même signalement que dans la recherche par référence : « il dit
        qu'il a validé, pourquoi son score ne bouge pas ? »"""
        assert "if (r.hors_circuit) {" in page

    def test_le_tableau_ne_pousse_pas_le_reste_hors_de_l_ecran(self, page):
        """Cinquante lignes reléguaient la saisie manuelle deux écrans plus
        bas — et c'est le geste qu'on vient faire quand un scan a raté."""
        assert 'class="scroll plafonne"' in page
        assert ".scroll.plafonne { max-height:" in page
