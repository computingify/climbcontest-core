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

    def test_la_carte_renvoie_vers_le_bon_endroit(self, page):
        assert "Compétition → Importer le classeur" in page


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

    def test_la_duree_du_maintien_n_est_ecrite_qu_une_fois(self, page):
        """Le CSS recoit sa duree du script : deux valeurs a tenir synchrones a
        la main finiraient par diverger, et la jauge mentirait."""
        assert "var MAINTIEN_MS = 2000;" in page
        assert "transition-duration" not in page.split("<script>")[0]

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

    def test_le_qr_reste_sur_du_blanc(self, page):
        """Un QR sur fond sombre ne se lit pas. Le cadre reste blanc dans les
        deux themes, et un trait le detoure pour qu'il ne se fonde pas dans une
        surface claire."""
        assert ".qr-cadre { background: #fff;" in page
