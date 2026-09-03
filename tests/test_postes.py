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

from werkzeug.security import generate_password_hash

from climbcontest import comptes, fiches, plan_du_mur, qr
from climbcontest.extensions import db
from climbcontest.models import Utilisateur

MDP = "un-mot-de-passe-assez-long"

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


class TestLaTailleDuNom:

    def test_un_nom_court_prend_la_taille_maximale(self, app):
        assert fiches.taille_nom_poste_mm("C") == fiches.TAILLE_NOM_POSTE_MAXI_MM

    def test_un_nom_long_retrecit_pour_tenir(self, app):
        # `white-space: nowrap` dans le gabarit : ce qui ne tient pas serait
        # COUPE, et une zone dont le nom est coupe ne sert plus a rien.
        long = "Z" * 40
        assert fiches.taille_nom_poste_mm(long) < fiches.TAILLE_NOM_POSTE_MAXI_MM
        assert len(long) * fiches.CHASSE_NOM_POSTE * \
            fiches.taille_nom_poste_mm(long) <= fiches.LARGEUR_NOM_POSTE_MM

    def test_deux_noms_de_meme_longueur_ont_la_meme_taille(self, app):
        assert fiches.taille_nom_poste_mm("ABC") == fiches.taille_nom_poste_mm("XYZ")

    def test_la_planche_porte_la_taille(self, app):
        planche = fiches.postes(plan=_plan("A"))
        assert planche[0]["taille_nom"] == fiches.taille_nom_poste_mm("A")


class TestLeFiltreParZone:

    def test_une_seule_zone(self, app):
        planche = fiches.postes(zone="C", plan=_plan("A", "B", "C"))
        assert [p["zone"] for p in planche] == ["C"]

    def test_une_zone_absente_du_plan_rend_une_liste_vide(self, app):
        # Pas une exception : la page doit pouvoir NOMMER la zone demandee.
        assert fiches.postes(zone="Q", plan=_plan("A", "B")) == []


class TestLaPagination:

    def test_deux_affiches_par_feuille(self, app):
        assert fiches.POSTES_PAR_FEUILLE == 2

    def test_la_derniere_feuille_peut_etre_incomplete(self, app):
        planche = fiches.postes(plan=_plan("A", "B", "C"))
        feuilles = fiches.en_feuilles(planche, fiches.POSTES_PAR_FEUILLE)
        assert [len(f) for f in feuilles] == [2, 1]

    def test_aucune_affiche_ne_se_perd(self, app):
        planche = fiches.postes(plan=fiches.PLAN)
        feuilles = fiches.en_feuilles(planche, fiches.POSTES_PAR_FEUILLE)
        assert sum(len(f) for f in feuilles) == len(planche)


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
                                   mot_de_passe_hache=generate_password_hash(MDP),
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
        plan_du_mur.ecrire(_plan("A", "B", "C"), par="orga")
        html = connecte_orga.get("/admin/postes").get_data(as_text=True)
        # Deux feuilles pour trois affiches : le decoupage vient du serveur.
        assert html.count('class="feuille"') == 2


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
        assert "--feuille-hauteur: 272mm;" in source

    def test_le_saut_de_page_porte_sur_la_feuille(self):
        source = GABARIT.read_text(encoding="utf-8")
        assert ".feuille + .feuille { break-before: page;" in source

    def test_les_aplats_s_impriment(self):
        """Sans `print-color-adjust`, un navigateur ne pose aucun fond."""
        source = GABARIT.read_text(encoding="utf-8")
        assert "print-color-adjust: exact" in source

    def test_l_affiche_dit_quoi_faire(self):
        """Un benevole qui n'a pas ecoute le briefing doit trouver le geste."""
        source = GABARIT.read_text(encoding="utf-8")
        assert "Scanner le QR de mon poste" in source


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
        assert corps["categories"] == []

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
