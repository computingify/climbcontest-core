"""Les QR de poste posés sur la table du juge — spec 034.

Le juge arrive à sa table, ouvre l'application, scanne le carton posé devant
lui : son téléphone s'appelle « Zone C ». Il n'a rien tapé.

Ce fichier protège quatre choses, et chacune casserait en silence :

1. **les zones viennent du plan**, jamais d'une liste tenue à la main — une
   liste qui divergerait ferait imprimer un carton pour une zone disparue ;
2. **le préfixe `CCPOSTE:` est le même des deux côtés.** Il est écrit deux
   fois, en Python et en JavaScript. Le jour où les deux divergent, *tous* les
   QR imprimés cessent d'être lus sans qu'une ligne ait l'air fausse — et ça
   se découvre le samedi matin, cartons déjà posés ;
3. **la planche est paginée en Python**, jamais par le CSS. Une planche qui
   occupe la surface utile exacte sort en double de pages sur une vraie
   imprimante (leçon payée par la spec 032) ;
4. **la page marche sans compétition active.** On imprime ces cartons la veille
   au soir, avant même d'avoir importé le classeur.
"""
import re
from pathlib import Path

import pytest

from climbcontest.comptes import _hacher as hacher

from climbcontest import comptes, contest, fiches, plan_du_mur, qr
from climbcontest.extensions import db
from climbcontest.models import Utilisateur

MDP = "un-mot-de-passe-assez-long"

try:
    import cv2
    import numpy as np
    DECODEUR = True
except ImportError:                                   # pragma: no cover
    DECODEUR = False

POSTE_JS = Path(__file__).resolve().parents[1] / "climbcontest" / "static" / "juge" / "poste.js"
GABARIT = Path(__file__).resolve().parents[1] / "climbcontest" / "templates" / "postes.html"


@pytest.fixture()
def connecte_orga(client, app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


def _plan(*zones, doublon=None, sans_zone=False):
    """Un plan minimal qui porte exactement ces zones."""
    murs = [{"zone": z, "profil": "vertical",
             "points": [[0, 0], [10, 0], [10, 10], [0, 10]], "etiquette": None}
            for z in zones]
    if doublon:
        murs.append({"zone": doublon, "profil": "dalle",
                     "points": [[20, 20], [30, 20], [30, 30], [20, 30]],
                     "etiquette": None})
    if sans_zone:
        murs.append({"zone": None, "profil": "vertical",
                     "points": [[40, 40], [50, 40], [50, 50], [40, 50]],
                     "etiquette": None})
    return {"vue": [120, 150], "contour": None, "murs": murs, "reperes": []}


# --- La planche, sans passer par HTTP ----------------------------------------


class TestLesZonesViennentDuPlan:

    def test_une_affiche_par_zone_du_plan_d_usine(self, app):
        planche = fiches.postes(plan=fiches.PLAN)
        assert len(planche) == len(fiches.ZONES_DU_PLAN)
        assert {p["zone"] for p in planche} == set(fiches.ZONES_DU_PLAN)

    def test_deux_murs_de_la_meme_zone_ne_font_qu_une_affiche(self, app):
        planche = fiches.postes(plan=_plan("A", "B", doublon="A"))
        assert [p["zone"] for p in planche] == ["A", "B"]

    def test_un_mur_sans_zone_ne_produit_aucune_affiche(self, app):
        planche = fiches.postes(plan=_plan("A", sans_zone=True))
        assert [p["zone"] for p in planche] == ["A"]

    def test_l_ordre_est_alphabetique(self, app):
        # Pas l'ordre du plan : le plan range les murs comme on les a dessines,
        # ce qui est arbitraire pour qui cherche « M » dans une pile de feuilles.
        planche = fiches.postes(plan=_plan("M", "A", "Z", "C"))
        assert [p["zone"] for p in planche] == ["A", "C", "M", "Z"]

    def test_un_plan_sans_aucune_zone_rend_une_liste_vide(self, app):
        assert fiches.postes(plan=_plan()) == []

    def test_le_plan_dessine_dans_la_console_l_emporte(self, app):
        """Le plan COURANT, pas celui d'usine : c'est tout l'objet de la spec 029."""
        plan_du_mur.ecrire(_plan("Q", "R"), par="orga")
        planche = fiches.postes()
        assert [p["zone"] for p in planche] == ["Q", "R"]

    def test_sans_plan_dessine_c_est_celui_d_usine(self, app):
        planche = fiches.postes()
        assert {p["zone"] for p in planche} == set(fiches.ZONES_DU_PLAN)


class TestLeContenuDuQr:

    def test_le_qr_porte_le_prefixe_et_la_zone(self, app):
        planche = fiches.postes(plan=_plan("C"))
        assert planche[0]["texte"] == "CCPOSTE:C"

    def test_le_prefixe_est_celui_de_la_constante(self, app):
        assert fiches.texte_qr_poste("C") == fiches.PREFIXE_QR_POSTE + "C"

    def test_un_qr_de_poste_ne_ressemble_a_aucun_autre_qr(self, app):
        """⚠️ LA raison d'etre du prefixe.

        Sans lui, un juge qui scanne un bloc par erreur depuis cet ecran
        renommerait son poste « ZJ6 » sans s'en apercevoir.
        """
        texte = fiches.texte_qr_poste("Z")
        assert texte != "Z"          # pas un nom de zone nu
        assert texte != "ZJ6"        # pas un tag de bloc
        assert not texte.isdigit()   # pas un dossard
        assert "://" not in texte    # pas un lien d'organisateur

    def test_le_qr_se_relit_a_sa_taille_d_impression(self, app):
        """Un module doit rester au-dessus du plancher lisible."""
        planche = fiches.postes(plan=_plan("ABC"))
        module = qr.taille_de_module_mm(planche[0]["texte"], fiches.COTE_QR_POSTE_MM)
        assert module > qr.MODULE_MINI_MM

    def test_ce_n_est_jamais_un_micro_qr(self, app):
        """⚠️ `segno.make()` choisirait un MICRO QR pour des donnees courtes.

        La plupart des scanners de telephone ne les lisent pas. Le piege est
        documente en tete de `qr.py` ; il vaut aussi pour les QR de poste.
        """
        code = qr.code(fiches.texte_qr_poste("A"))
        assert code.is_micro is False

    def test_le_svg_est_dimensionne_en_millimetres(self, app):
        planche = fiches.postes(plan=_plan("A"))
        assert f'width="{fiches.COTE_QR_POSTE_MM}mm"' in planche[0]["qr"]


@pytest.mark.skipif(not DECODEUR, reason="opencv absent")
class TestVraimentLisible:
    """On decode ce qu'on produit, avec un decodeur INDEPENDANT de l'encodeur.

    C'est le seul test qui prouve quelque chose : un QR d'allure correcte que
    personne ne lit passerait toutes les autres verifications, et se
    decouvrirait le samedi matin avec les cartons deja poses. Meme harnais que
    `test_qr_et_dossards.py`.
    """

    @staticmethod
    def _image(texte, echelle=10, marge=4):
        m = qr.matrice(texte)
        n = len(m)
        total = n + 2 * marge
        img = np.ones((total, total), np.uint8) * 255
        for y in range(n):
            for x in range(n):
                if m[y][x]:
                    img[y + marge, x + marge] = 0
        return cv2.resize(img, (total * echelle,) * 2,
                          interpolation=cv2.INTER_NEAREST)

    @pytest.mark.parametrize("zone", ["A", "C", "Z", "ABC", "M1", "Mur jaune"])
    def test_un_decodeur_independant_relit_le_qr_de_poste(self, zone):
        texte = fiches.texte_qr_poste(zone)
        lu, _, _ = cv2.QRCodeDetector().detectAndDecode(self._image(texte))
        assert lu == texte, f"produit {texte!r}, relu {lu!r}"

    def test_ce_qui_est_relu_redonne_le_nom_de_la_zone(self):
        """La boucle complete : on imprime, un decodeur lit, la regle de
        `poste.js` retrouve « C ». Le prefixe est verifie ici sur le texte
        REELLEMENT encode, pas sur une constante."""
        lu, _, _ = cv2.QRCodeDetector().detectAndDecode(
            self._image(fiches.texte_qr_poste("C")))
        assert lu.startswith(fiches.PREFIXE_QR_POSTE)
        assert lu[len(fiches.PREFIXE_QR_POSTE):] == "C"


class TestLaTailleDuNom:

    def test_un_nom_court_prend_la_taille_maximale(self, app):
        assert fiches.taille_nom_poste_mm("C") == fiches.TAILLE_NOM_POSTE_MAXI_MM

    def test_un_nom_long_retrecit_pour_tenir(self, app):
        # `white-space: nowrap` dans le gabarit : ce qui ne tient pas serait
        # COUPE, et une zone dont le nom est coupe ne sert plus a rien.
        long = "Z" * 40
        largeur = fiches.geometrie_postes()["largeur_nom_mm"]
        assert fiches.taille_nom_poste_mm(long) < fiches.TAILLE_NOM_POSTE_MAXI_MM
        assert len(long) * fiches.CHASSE_NOM_POSTE * \
            fiches.taille_nom_poste_mm(long) <= largeur

    def test_deux_noms_de_meme_longueur_ont_la_meme_taille(self, app):
        assert fiches.taille_nom_poste_mm("ABC") == fiches.taille_nom_poste_mm("XYZ")

    def test_la_planche_porte_la_taille(self, app):
        planche = fiches.postes(plan=_plan("A"))
        assert planche[0]["taille_nom"] == fiches.taille_nom_poste_mm("A")

    def test_la_largeur_disponible_suit_la_densite(self, app):
        """⚠️ Elle n'est PAS une constante.

        Ecrite en dur, elle mentirait des qu'on repasse de huit affiches par
        feuille a six -- une seule colonne au lieu de deux double la largeur
        d'une affiche.
        """
        deux = fiches.geometrie_postes(par_feuille=8, par_ligne=2)
        une = fiches.geometrie_postes(par_feuille=8, par_ligne=1)
        assert une["largeur_nom_mm"] > deux["largeur_nom_mm"]


class TestLeFiltreParZone:

    def test_une_seule_zone(self, app):
        planche = fiches.postes(zone="C", plan=_plan("A", "B", "C"))
        assert [p["zone"] for p in planche] == ["C"]

    def test_une_zone_absente_du_plan_rend_une_liste_vide(self, app):
        # Pas une exception : la page doit pouvoir NOMMER la zone demandee.
        assert fiches.postes(zone="Q", plan=_plan("A", "B")) == []


class TestLaPagination:

    def test_huit_affiches_par_feuille(self, app):
        """⚠️ Huit, pas trois.

        Adrien, le 03/09 apres relecture : « lors de l'impression tu m'en
        rentres beaucoup plus sur une feuille -- a quatre, j'en voudrais au
        moins six, voire huit ». On prend le haut de la fourchette.

        L'historique en dit long sur ce qui se paie a l'ecran : deux par
        feuille en colonne (le mode d'emploi sortait COUPE), puis trois a
        l'horizontale, puis huit en deux colonnes une fois le mode d'emploi
        parti dans l'application.
        """
        assert fiches.POSTES_PAR_FEUILLE == 8

    def test_les_dix_sept_zones_du_plan_d_usine_tiennent_sur_trois_feuilles(self, app):
        """« Je me retrouve avec des pages vides » etait le reproche du 02/09."""
        planche = fiches.postes(plan=fiches.PLAN)
        feuilles = fiches.en_feuilles(planche, fiches.POSTES_PAR_FEUILLE)
        assert len(feuilles) == 3

    def test_la_derniere_feuille_peut_etre_incomplete(self, app):
        planche = fiches.postes(plan=_plan("A", "B", "C", "D", "E", "F", "G",
                                           "H", "I"))
        feuilles = fiches.en_feuilles(planche, fiches.POSTES_PAR_FEUILLE)
        assert [len(f) for f in feuilles] == [8, 1]

    def test_aucune_affiche_ne_se_perd(self, app):
        planche = fiches.postes(plan=fiches.PLAN)
        feuilles = fiches.en_feuilles(planche, fiches.POSTES_PAR_FEUILLE)
        assert sum(len(f) for f in feuilles) == len(planche)


class TestLaGeometrieSuitLaDensite:
    """⚠️ **Une seule valeur commande la planche.**

    Adrien arbitre entre six et huit affiches par A4. Repasser a six doit etre
    une valeur a changer — `fiches.POSTES_PAR_FEUILLE` — et pas une refonte du
    CSS. Ces tests tiennent cette promesse : la geometrie se DEDUIT, elle ne
    s'ecrit nulle part deux fois.
    """

    def test_huit_par_feuille_font_deux_colonnes_de_quatre(self, app):
        geo = fiches.geometrie_postes(par_feuille=8)
        assert (geo["colonnes"], geo["lignes"]) == (2, 4)

    def test_six_par_feuille_font_deux_colonnes_de_trois(self, app):
        geo = fiches.geometrie_postes(par_feuille=6)
        assert (geo["colonnes"], geo["lignes"]) == (2, 3)
        # Et les affiches sont PLUS HAUTES : c'est tout ce qui change.
        assert geo["hauteur_mm"] > fiches.geometrie_postes(par_feuille=8)["hauteur_mm"]
        assert geo["largeur_mm"] == fiches.geometrie_postes(par_feuille=8)["largeur_mm"]

    def test_les_affiches_remplissent_la_feuille_exactement(self, app):
        for par_feuille in (4, 6, 8, 10):
            geo = fiches.geometrie_postes(par_feuille=par_feuille)
            assert geo["colonnes"] * geo["largeur_mm"] == \
                pytest.approx(fiches.LARGEUR_FEUILLE_POSTES_MM, abs=0.05)
            assert geo["lignes"] * geo["hauteur_mm"] == \
                pytest.approx(fiches.HAUTEUR_FEUILLE_POSTES_MM, abs=0.05)

    def test_le_qr_reste_au_dessus_du_plancher_mesure(self, app):
        """⚠️ 42 mm est le plancher, et il est MESURE.

        C'est la taille des etiquettes de blocs de la spec 024, qui se scannent
        a bout de bras. Densifier la planche ne doit jamais passer sous cette
        barre : un QR qu'on ne lit pas rend le carton inutile, et ca se
        decouvre le samedi matin.
        """
        assert fiches.COTE_QR_POSTE_MM >= 42.0

    def test_le_qr_et_son_rembourrage_tiennent_dans_l_affiche(self, app):
        for par_feuille in (6, 8):
            geo = fiches.geometrie_postes(par_feuille=par_feuille)
            plein = geo["cote_qr_mm"] + 2 * geo["rembourrage_mm"]
            assert plein <= geo["hauteur_mm"], f"{par_feuille} par feuille"
            assert plein + geo["gouttiere_mm"] + geo["largeur_nom_mm"] == \
                pytest.approx(geo["largeur_mm"], abs=0.05)

    def test_le_nom_garde_de_la_place(self, app):
        """Un QR qui mange toute l'affiche laisserait un nom illisible."""
        for par_feuille in (6, 8):
            geo = fiches.geometrie_postes(par_feuille=par_feuille)
            # Trois caracteres -- le plafond de `plan_du_mur.ZONE_MAXI`.
            assert fiches.taille_nom_poste_mm("ABC", geo) >= 10.0


# --- Le préfixe partagé entre Python et JavaScript ---------------------------


class TestLePrefixePartage:
    """⚠️ Le seul lien entre la console qui imprime et le téléphone qui lit.

    Huit caractères, écrits deux fois, dans deux langages. Le jour où ils
    divergent, tous les QR imprimés cessent d'être lus — et rien n'a l'air
    faux. Ce test rend le piège **détectable**, plutôt que de le documenter.
    """

    def test_le_prefixe_js_est_celui_de_python(self):
        source = POSTE_JS.read_text(encoding="utf-8")
        trouve = re.search(r'export const PREFIXE_POSTE = "([^"]+)";', source)
        assert trouve, "PREFIXE_POSTE introuvable dans poste.js"
        assert trouve.group(1) == fiches.PREFIXE_QR_POSTE

    def test_le_mot_zone_js_est_celui_de_python(self):
        """⚠️ Le deuxieme lien entre le carton et la console (retouche du 03/09).

        Le carton imprime « ZONE » au-dessus de la lettre ; le telephone
        compose « Zone A » et l'envoie a la console. Si les deux mots
        divergent, le carton pose sur la table cesse de designer la ligne
        qu'on lit dans « Qui envoie quoi » -- sans qu'une ligne ait l'air
        fausse, exactement comme le prefixe.
        """
        source = POSTE_JS.read_text(encoding="utf-8")
        trouve = re.search(r'export const MOT_ZONE = "([^"]+)";', source)
        assert trouve, "MOT_ZONE introuvable dans poste.js"
        assert trouve.group(1) == fiches.MOT_ZONE

    def test_le_qr_ne_porte_PAS_le_mot_zone(self):
        """⚠️ Le QR reste minimal : la lettre seule, le libelle se compose.

        Adrien : « dans le nom qu'on envoie a la console, je veux que ce soit
        "zone" et la lettre de la zone ». Il ne l'a pas demande DANS le QR --
        et l'y mettre couterait cinq caracteres de plus par symbole, donc des
        modules plus petits, pour un libelle qu'on ne pourrait plus changer
        sans reimprimer dix-sept affiches.
        """
        assert fiches.texte_qr_poste("A") == "CCPOSTE:A"
        assert fiches.MOT_ZONE.lower() not in fiches.texte_qr_poste("A").lower()

    def test_le_prefixe_ne_peut_pas_etre_un_tag_de_bloc(self):
        # Un tag de bloc est fait de lettres et de chiffres : le deux-points
        # rend la collision impossible, pas seulement improbable.
        assert ":" in fiches.PREFIXE_QR_POSTE
        assert not fiches.PREFIXE_QR_POSTE.isalnum()


# --- La route ----------------------------------------------------------------


class TestLaRoute:

    def test_anonyme_refuse(self, client, app):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/postes").status_code == 401

    def test_role_insuffisant_refuse(self, client, app):
        """Connecte ne suffit pas : il faut le role organisateur.

        Le compte est cree directement en base -- `comptes.creer` refuse un
        compte sans role, et c'est tres bien ainsi.
        """
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        db.session.add(Utilisateur(identifiant="sans-role",
                                   mot_de_passe_hache=hacher(MDP),
                                   actif=True))
        db.session.commit()
        client.post("/admin/connexion",
                    json={"identifiant": "sans-role", "mot_de_passe": MDP})
        assert client.get("/admin/postes").status_code == 403

    def test_une_affiche_par_zone(self, connecte_orga, app):
        plan_du_mur.ecrire(_plan("A", "B", "C"), par="orga")
        reponse = connecte_orga.get("/admin/postes")
        assert reponse.status_code == 200
        html = reponse.get_data(as_text=True)
        assert html.count('class="affiche"') == 3
        for zone in ("A", "B", "C"):
            assert f'<div class="nom">{zone}</div>' in html

    def test_elle_marche_sans_competition_active(self, connecte_orga):
        """⚠️ La seule page d'impression qui ne rend PAS 409, et c'est voulu.

        Le plan ne depend d'aucune edition, et on imprime ces cartons la veille
        au soir -- avant meme d'avoir importe le classeur.
        """
        reponse = connecte_orga.get("/admin/postes")
        assert reponse.status_code == 200
        assert 'class="affiche"' in reponse.get_data(as_text=True)

    def test_le_filtre_par_zone(self, connecte_orga, app):
        plan_du_mur.ecrire(_plan("A", "B", "C"), par="orga")
        html = connecte_orga.get("/admin/postes?zone=B").get_data(as_text=True)
        assert html.count('class="affiche"') == 1
        assert '<div class="nom">B</div>' in html

    def test_une_zone_inconnue_nomme_ce_qu_on_a_demande(self, connecte_orga, app):
        plan_du_mur.ecrire(_plan("A"), par="orga")
        reponse = connecte_orga.get("/admin/postes?zone=Q")
        assert reponse.status_code == 200          # pas une 404
        html = reponse.get_data(as_text=True)
        assert 'class="affiche"' not in html
        assert "Q" in html
        assert "/admin/plan" in html               # le geste qui repare

    def test_un_plan_sans_zone_renvoie_vers_le_dessin(self, connecte_orga, app):
        plan_du_mur.ecrire(_plan(), par="orga")
        reponse = connecte_orga.get("/admin/postes")
        assert reponse.status_code == 200
        html = reponse.get_data(as_text=True)
        assert "aucune zone" in html
        assert "/admin/plan" in html

    def test_le_qr_est_dans_la_page(self, connecte_orga, app):
        plan_du_mur.ecrire(_plan("A"), par="orga")
        html = connecte_orga.get("/admin/postes").get_data(as_text=True)
        assert "<svg" in html

    def test_la_pagination_est_faite_en_python(self, connecte_orga, app):
        zones = [chr(ord("A") + i) for i in range(fiches.POSTES_PAR_FEUILLE + 1)]
        plan_du_mur.ecrire(_plan(*zones), par="orga")
        html = connecte_orga.get("/admin/postes").get_data(as_text=True)
        # Une affiche de plus qu'une feuille : le decoupage vient du serveur.
        assert html.count('class="feuille"') == 2

    def test_la_page_pose_la_geometrie_du_serveur(self, connecte_orga, app):
        """La densite doit se lire dans le HTML rendu, pas seulement en Python."""
        plan_du_mur.ecrire(_plan("A"), par="orga")
        html = connecte_orga.get("/admin/postes").get_data(as_text=True)
        geo = fiches.geometrie_postes()
        assert f"--colonnes: {geo['colonnes']};" in html
        assert f"--affiche-hauteur: {geo['hauteur_mm']}mm;" in html
        assert f"--qr: {geo['cote_qr_mm']}mm;" in html


# --- Le gabarit --------------------------------------------------------------


class TestLeGabarit:

    def test_aucune_ressource_exterieure(self):
        """On imprime parfois sans reseau, la veille au soir."""
        source = GABARIT.read_text(encoding="utf-8")
        assert "http://" not in source
        assert "https://" not in source
        assert "//cdn" not in source

    def test_la_page_est_un_a4_a_dix_millimetres_de_marge(self):
        source = GABARIT.read_text(encoding="utf-8")
        assert "@page { size: A4 portrait; margin: 10mm; }" in source

    def test_la_feuille_est_plus_petite_que_la_surface_utile(self):
        """⚠️ La lecon de la spec 032.

        Une feuille qui occupe la surface utile EXACTE (190 x 277) sort en
        DOUBLE de pages sur une vraie imprimante. Sept feuilles etaient sorties
        en quatorze pages.
        """
        source = GABARIT.read_text(encoding="utf-8")
        assert "--feuille-largeur: 188mm;" in source
        assert "--feuille-hauteur: 270mm;" in source

    def test_le_saut_de_page_porte_sur_la_feuille(self):
        source = GABARIT.read_text(encoding="utf-8")
        assert ".feuille + .feuille { break-before: page;" in source

    def test_les_aplats_s_impriment(self):
        """Sans `print-color-adjust`, un navigateur ne pose aucun fond."""
        source = GABARIT.read_text(encoding="utf-8")
        assert "print-color-adjust: exact" in source

    def test_le_contenu_tient_dans_la_hauteur_de_l_affiche(self):
        """⚠️ Le defaut trouve a l'ecran, mesure ici.

        Le QR plus le rembourrage doivent tenir dans la hauteur de l'affiche.
        La premiere version empilait QR (80) + nom (34) + mode d'emploi en
        COLONNE dans 136 mm : 164 mm de contenu, et le mode d'emploi sortait
        coupe. En horizontal, c'est le QR qui dicte la hauteur.
        """
        geo = fiches.geometrie_postes()
        assert geo["cote_qr_mm"] + 2 * geo["rembourrage_mm"] <= geo["hauteur_mm"]
        # Et la planche entiere tient sur la surface utile d'un A4.
        assert geo["lignes"] * geo["hauteur_mm"] <= 277

    def test_la_geometrie_ne_s_ecrit_pas_dans_le_gabarit(self):
        """⚠️ Elle vient du SERVEUR, et c'est ce qui rend la densite reglable.

        Adrien arbitre entre six et huit par feuille. Ecrite en dur ici, la
        geometrie obligerait a rejouer une demi-douzaine de millimetres a
        chaque changement -- et c'est exactement comme ca que le CSS et
        `POSTES_PAR_FEUILLE` ont diverge la premiere fois.
        """
        source = GABARIT.read_text(encoding="utf-8")
        for variable in ("--affiche-largeur", "--affiche-hauteur", "--qr",
                         "--colonnes"):
            assert f"{variable}: {{{{ geo." in source, variable

    def test_l_affiche_ne_porte_plus_de_mode_d_emploi(self):
        """⚠️ La retouche du 03/09.

        Adrien : « sur ces planches qui sont imprimees, tu n'as pas besoin de
        mettre le texte qui permet de comprendre comment est-ce qu'il faut le
        scanner ». La marche a suivre est partie DANS L'APPLICATION, ou elle
        arrive au bon moment. Il ne reste sur le carton que ce qui sert a la
        table : le QR et le nom de la zone.
        """
        source = GABARIT.read_text(encoding="utf-8")
        assert "mode-emploi" not in source
        affiche = source.split('<div class="affiche"', 1)[1].split("{% endfor %}", 1)[0]
        assert "Réglages" not in affiche
        assert "Scanner" not in affiche
        # Ce qui reste : le QR, et le nom de la zone.
        assert "p.qr" in affiche and "p.zone" in affiche

    def test_l_affiche_ecrit_le_mot_que_le_telephone_composera(self):
        """Le carton dit « ZONE C », le telephone se nomme « Zone C »."""
        source = GABARIT.read_text(encoding="utf-8")
        assert "{{ mot_zone }}" in source


# --- Les referentiels de la console ------------------------------------------


class TestLesZonesDansLesReferentiels:

    def test_les_zones_sont_rendues(self, connecte_orga, app, competition):
        plan_du_mur.ecrire(_plan("A", "B"), par="orga")
        corps = connecte_orga.get("/admin/referentiels").get_json()
        assert corps["zones"] == ["A", "B"]

    def test_les_zones_sont_la_meme_sans_competition_active(self, connecte_orga, app):
        """⚠️ Elles viennent du PLAN, qui ne depend d'aucune edition.

        Les calculer apres la garde priverait la console de sa liste de zones
        au moment precis ou on imprime les cartons : la veille au soir.
        """
        plan_du_mur.ecrire(_plan("A", "B"), par="orga")
        reponse = connecte_orga.get("/admin/referentiels")
        assert reponse.status_code == 200
        corps = reponse.get_json()
        assert corps["success"] is True
        assert corps["zones"] == ["A", "B"]
        # Spec 045 : les categories ne dependent d'aucune edition non plus --
        # elles viennent de la federation. Ce qui se vide, ce sont les clubs.
        assert corps["clubs"] == []

    def test_les_zones_ne_sont_pas_celles_des_blocs(self, connecte_orga, app, jeu):
        """Une zone existe pour le plan meme si aucun bloc n'y est importe."""
        plan_du_mur.ecrire(_plan("A", "B"), par="orga")
        corps = connecte_orga.get("/admin/referentiels").get_json()
        # `jeu` pose des blocs en zones « Z » et « D » : elles ne doivent PAS
        # remonter, et « A »/« B » doivent remonter bien qu'elles n'aient
        # aucun bloc.
        assert corps["zones"] == ["A", "B"]


# --- Les deux moities se rejoignent ------------------------------------------


class TestLaCoutureAvecLApplicationJuge:
    """Ce qu'aucun des deux cotes ne peut verifier seul."""

    def test_le_geste_existe_dans_les_reglages(self):
        source = (Path(__file__).resolve().parents[1] / "climbcontest" /
                  "templates" / "juge.html").read_text(encoding="utf-8")
        assert 'id="btnScannerPoste"' in source
        # Dans l'ecran des REGLAGES, pas ailleurs.
        reglages = source.split('id="ecranReglages"', 1)[1].split("</section>", 1)[0]
        assert 'id="btnScannerPoste"' in reglages

    def test_le_geste_est_aussi_sur_l_ecran_d_accueil(self):
        """⚠️ La retouche du 03/09.

        Adrien : « Lorsque le juge arrive a sa table, il va ouvrir
        l'application et dans l'application, on va lui afficher un petit texte
        en haut [...] on aura encore un petit bouton au milieu sur la page
        d'accueil ». C'est la contrepartie du mode d'emploi retire du carton :
        il fallait qu'il reapparaisse quelque part, et au bon moment.

        Le MEME motif que `#relier` (spec 014), volontairement : un bloc cache
        sous l'en-tete, revele au demarrage quand il manque quelque chose.
        """
        source = (Path(__file__).resolve().parents[1] / "climbcontest" /
                  "templates" / "juge.html").read_text(encoding="utf-8")
        assert 'id="btnPoste"' in source
        # Hors des ecrans (`.ecran`) : sur l'accueil, comme `#relier`.
        avant = source.split('id="ecranReglages"', 1)[0]
        assert 'id="poste" hidden' in avant
        assert 'id="btnPoste"' in avant
        # Et il porte son petit texte : un bouton nu ne dit pas ce qu'il fait.
        bloc = source.split('<p id="poste" hidden>', 1)[1].split("</p>", 1)[0]
        assert "carton" in bloc

    def test_le_bouton_d_accueil_est_cache_par_defaut(self):
        """⚠️ Il ne doit apparaitre QUE si le poste n'est pas nomme.

        Le juge scanne son carton une fois le matin. Un bandeau qui resterait
        toute la journee au-dessus des cartes de scan volerait de la place a ce
        qu'on touche cent fois.
        """
        source = (Path(__file__).resolve().parents[1] / "climbcontest" /
                  "templates" / "juge.html").read_text(encoding="utf-8")
        assert '<p id="poste" hidden>' in source

    def test_une_seule_fonction_decide_de_l_affichage_du_bloc(self):
        """⚠️ Trois appelants, une seule decision.

        Le bloc se montre au demarrage, se cache apres un scan reussi, et
        revient si le champ du nom est vide a la main. Trois endroits qui
        poseraient `hidden` eux-memes laisseraient tot ou tard le bloc affiche
        sur un telephone deja nomme.
        """
        source = (Path(__file__).resolve().parents[1] / "climbcontest" /
                  "static" / "juge" / "juge.js").read_text(encoding="utf-8")
        assert source.count('$("poste").hidden') == 1
        assert source.count("proposerDeNommerLePoste()") >= 4  # 1 def + 3 appels

    def test_le_scan_rafraichit_le_nom_affiche_dans_l_en_tete(self):
        """⚠️ La couture entre DEUX branches ecrites en parallele.

        `#nomPoste` dans l'en-tete vient de `fix/revue-du-03-09` ; le scan du
        QR de poste vient de la spec 034. Elles ne se touchent pas -- elles ont
        donc fusionne SANS conflit, et sans que rien rappelle que le scan est
        le seul chemin qui renomme le telephone hors du champ de saisie.

        Sans cet appel, un juge qui scanne son carton verrait le bloc de
        l'accueil disparaitre et l'en-tete rester vide jusqu'au prochain
        demarrage : un poste nomme qui ne le dit pas.
        """
        source = (Path(__file__).resolve().parents[1] / "climbcontest" /
                  "static" / "juge" / "juge.js").read_text(encoding="utf-8")
        corps = source.split("async function scannerMonPoste", 1)[1] \
                      .split("\nfunction proposerDeNommerLePoste", 1)[0]
        assert "afficherLeNomDuPoste()" in corps
        assert "proposerDeNommerLePoste()" in corps

    def test_le_geste_n_est_pas_dans_l_en_tete(self):
        """⚠️ L'en-tete est refondu en parallele (fix/revue-du-03-09).

        Deux branches qui reecrivent le meme bloc fusionnent SANS CONFLIT et en
        silence -- c'est deja arrive sur ce depot (spec 032, deux fonctions du
        meme nom). Ce test survit au merge : il dit ou le geste a sa place,
        pas ce qu'une branche a change.
        """
        source = (Path(__file__).resolve().parents[1] / "climbcontest" /
                  "templates" / "juge.html").read_text(encoding="utf-8")
        entete = source.split("<header>", 1)[1].split("</header>", 1)[0]
        assert "btnScannerPoste" not in entete
        assert "btnPoste" not in entete

    def test_le_module_est_dans_la_coquille_hors_ligne(self):
        """Sans ca, le bouton planterait au premier appui hors reseau."""
        sw = (Path(__file__).resolve().parents[1] / "climbcontest" / "static" /
              "juge" / "sw.js").read_text(encoding="utf-8")
        coquille = sw.split("const COQUILLE = [", 1)[1].split("];", 1)[0]
        assert "/static/juge/poste.js" in coquille

    def test_la_carte_est_dans_la_vue_telephones(self):
        source = (Path(__file__).resolve().parents[1] / "climbcontest" /
                  "templates" / "admin.html").read_text(encoding="utf-8")
        vue = source.split('id="vueTelephones"', 1)[1].split("</section>", 1)[0]
        assert 'id="btnPostes"' in vue
        assert 'id="pZone"' in vue


# --- Plusieurs téléphones sur la même zone ------------------------------------


class TestDeuxTelephonesSurLaMemeZone:
    """⚠️ **Le nom d'un poste n'est plus unique, et c'est voulu.**

    Adrien, le 03/09 : « il peut y avoir plusieurs téléphones par zone. Dans ce
    cas-là, les juges vont tous les deux scanner le même QR code, ce qui fait
    que les téléphones vont porter le même nom. Moi, ce que je veux, c'est que
    tu sois capable de les distinguer côté console. »

    La donnée existait déjà — `appareil_id`, l'UUID posé par `identite.js`
    depuis la spec 011, que la vue « Téléphones » montre dans une colonne à
    part. Ce qui manquait n'était pas un identifiant, c'était de la
    **lisibilité** : deux lignes « Zone A » côte à côte ne disent pas laquelle
    est laquelle.

    ⚠️ Une **seule** fonction compose ce libellé, `contest.libelle_poste`.
    Toutes les vues l'appellent. La forme exacte est encore en arbitrage : elle
    doit rester une modification d'un seul endroit.
    """

    def test_le_libelle_porte_le_nom_puis_le_code(self):
        assert contest.libelle_poste("Zone A", "3f9a1c2b-dead-beef") == \
            "Zone A (3f9a1c2b)"

    def test_deux_telephones_du_meme_nom_ne_se_ressemblent_pas(self):
        """⚠️ LE test de cette retouche."""
        un = contest.libelle_poste("Zone A", "3f9a1c2b-0000-1111")
        deux = contest.libelle_poste("Zone A", "7e40aa91-0000-1111")
        assert un != deux

    def test_le_code_fait_huit_caracteres(self):
        """Ce que l'application affiche dans ses réglages, et que le juge dicte."""
        libelle = contest.libelle_poste("Zone A", "0123456789abcdef")
        assert libelle == "Zone A (01234567)"
        assert contest.CODE_APPAREIL_CARACTERES == 8

    def test_un_telephone_sans_nom_reste_designable(self):
        assert contest.libelle_poste(None, "3f9a1c2b-x") == "Sans nom (3f9a1c2b)"
        assert contest.libelle_poste("   ", "3f9a1c2b-x") == "Sans nom (3f9a1c2b)"

    def test_une_saisie_manuelle_n_a_pas_de_libelle(self):
        """⚠️ `None`, pas « Sans nom » : lui inventer un appareil serait faux.

        L'appelant sait quoi dire à la place — « saisie de adrien ».
        """
        assert contest.libelle_poste(None, None) is None
        assert contest.libelle_poste(None, "") is None

    def test_un_nom_sans_appareil_reste_lui_meme(self):
        assert contest.libelle_poste("Zone A", None) == "Zone A"

    def test_ce_que_le_carton_nomme_est_ce_que_la_console_affiche(self, app):
        """La chaîne complète, du plan au libellé de la console.

        Le carton de la zone « A » porte `CCPOSTE:A`, le téléphone compose
        « Zone A » (`poste.js`), et la console montre « Zone A (…) ».
        """
        planche = fiches.postes(plan=_plan("A"))
        assert planche[0]["texte"] == "CCPOSTE:A"
        assert planche[0]["libelle"] == "Zone A"
        assert contest.libelle_poste(planche[0]["libelle"], "3f9a1c2b-x") \
            .startswith("Zone A (")

    def test_la_console_affiche_le_libelle_partout(self):
        """Les deux vues qui nomment un poste passent par la même clé."""
        source = (Path(__file__).resolve().parents[1] / "climbcontest" /
                  "templates" / "admin.html").read_text(encoding="utf-8")
        assert "a.libelle" in source            # « Qui envoie quoi »
        assert "r.appareil_libelle" in source   # la colonne « Téléphone »
        # ⚠️ Trois vues, pas deux : « Les dernières réussites » (spec 033) et
        # son menu de filtrage sont arrivés en parallèle et nomment le même
        # poste. Deux entrées « Zone A » dans un menu déroulant ne se
        # choisissent pas.
        assert source.count("r.appareil_libelle") == 2
        assert source.count("a.libelle") == 2
        # Et plus jamais le nom brut, qui ne distingue pas deux « Zone A ».
        assert "r.appareil_nom" not in source
        assert 'o.textContent = a.nom' not in source

