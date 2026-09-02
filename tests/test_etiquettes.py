"""Les étiquettes de blocs à coller au mur — spec 024.

Le juge scanne DEUX QR : celui du grimpeur, puis celui du bloc réussi. Le second
est collé au mur, à côté du départ. Ce fichier protège ce qui rend cette
étiquette utilisable : le bon contenu dans le QR, l'ordre du `Plan`, une zone
par page, et le fait qu'un bloc **rattaché à aucun circuit** le dise — c'est le
dernier moment où on peut rattraper l'anomalie, avant de le coller.
"""
import re

import pytest

from climbcontest import comptes, fiches, qr
from climbcontest.extensions import db
from climbcontest.models import Bloc, BlocCircuit, Circuit, Participant

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte_orga(client, app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


def _bloc(comp, tag, zone, numero, couleur="Jaune", prises="Blanc", circuits=()):
    b = Bloc(competition_id=comp.id, tag=tag, zone=zone, numero=numero,
             couleur=couleur, couleur_prises=prises)
    db.session.add(b)
    db.session.flush()
    for c in circuits:
        db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=c.id))
    return b


@pytest.fixture()
def salle(competition):
    """Trois zones, six blocs, deux circuits — et un bloc orphelin."""
    u11 = Circuit(competition_id=competition.id, nom="U11")
    u13 = Circuit(competition_id=competition.id, nom="U13")
    db.session.add_all([u11, u13])
    db.session.flush()
    # `numero` = la ligne dans l'onglet Import, qui suit le Plan : c'est lui qui
    # donne l'ordre, et il range les blocs zone par zone.
    _bloc(competition, "ZJ6", "Z", 1, circuits=[u11, u13])
    _bloc(competition, "ZJ9", "Z", 2, couleur="Vert", circuits=[u11])
    _bloc(competition, "DV21", "D", 3, couleur="Vert", prises="Rose", circuits=[u13])
    _bloc(competition, "DB2", "D", 4, couleur="Bleu", circuits=[u11, u13])
    _bloc(competition, "CM4", "C", 5, couleur="Mauve", circuits=[])   # orphelin
    _bloc(competition, "CN1", "C", 6, couleur="Noir", prises=None, circuits=[u13])
    db.session.commit()
    return competition


class TestLOrdreEtLeRegroupement:

    def test_l_ordre_est_celui_du_plan(self, salle):
        planche = fiches.etiquettes(salle)
        assert [e["tag"] for e in planche] == [
            "ZJ6", "ZJ9", "DV21", "DB2", "CM4", "CN1"]

    def test_les_zones_restent_groupees_dans_l_ordre(self, salle):
        """Le saut de page par zone a disparu, mais le regroupement PHYSIQUE
        demeure : les blocs sortent dans l'ordre du `Plan`, donc zone par zone.
        C'est ce qui permet de coller une zone d'affilée sans rien trier."""
        assert [e["zone"] for e in fiches.etiquettes(salle)] == [
            "Z", "Z", "D", "D", "C", "C"]


class TestLesFiltres:

    def test_une_zone(self, salle):
        planche = fiches.etiquettes(salle, zone="D")
        assert [e["tag"] for e in planche] == ["DV21", "DB2"]

    def test_une_zone_inconnue(self, salle):
        """Une page vide qui nomme la zone, pas une exception."""
        assert fiches.etiquettes(salle, zone="Q") == []

    def test_un_seul_bloc(self, salle):
        """Le cas de l'étiquette décollée ou perdue en pleine compétition."""
        planche = fiches.etiquettes(salle, tag="ZJ9")
        assert len(planche) == 1 and planche[0]["tag"] == "ZJ9"

    def test_un_bloc_inconnu(self, salle):
        assert fiches.etiquettes(salle, tag="ZJ99") == []

    def test_le_bloc_prime_sur_la_zone(self, salle):
        """Le plus précis gagne, comme `?dossard=` prime sur `?categorie=`."""
        planche = fiches.etiquettes(salle, zone="C", tag="ZJ6")
        assert [e["tag"] for e in planche] == ["ZJ6"]


class TestCeQuePorteLEtiquette:

    def test_le_qr_contient_le_tag_COMPLET(self, salle):
        """`ZJ6`, zone + numéro collés : c'est ce que l'application juge attend
        et ce que `bloc_par_tag()` sait relire. Pas un caractère de plus."""
        e = fiches.etiquettes(salle, tag="ZJ6")[0]
        attendu = qr.svg("ZJ6", cote_mm=fiches.COTE_QR_ETIQUETTE_MM)
        assert e["qr"] == attendu

    def test_le_qr_de_l_etiquette_est_plus_grand_que_celui_d_une_fiche(self):
        """Il est collé au mur, souvent en hauteur, et scanné d'un bras tendu."""
        assert fiches.COTE_QR_ETIQUETTE_MM > fiches.COTE_QR_MM

    def test_il_reste_au_dessus_du_plancher_de_lisibilite(self):
        taille = qr.taille_de_module_mm("ZJ6", fiches.COTE_QR_ETIQUETTE_MM)
        assert taille >= qr.MODULE_MINI_MM

    def test_le_numero_est_sans_sa_zone(self, salle):
        """Le numéro écrit sur le mur, pas le contenu du QR."""
        e = fiches.etiquettes(salle, tag="DV21")[0]
        assert e["numero"] == "V21"
        assert e["tag"] == "DV21"

    def test_la_couleur_des_prises(self, salle):
        assert fiches.etiquettes(salle, tag="DV21")[0]["couleur_prises"] == "Rose"

    def test_un_bloc_sans_couleur_de_prises(self, salle):
        """La ligne disparaît, l'étiquette garde sa mise en page."""
        assert fiches.etiquettes(salle, tag="CN1")[0]["couleur_prises"] is None

    def test_les_circuits_sont_tries(self, salle):
        assert fiches.etiquettes(salle, tag="ZJ6")[0]["circuits"] == ["U11", "U13"]

    def test_un_bloc_orphelin_le_dit(self, salle):
        """L'anomalie que la vue Circuits traque (spec 019). Sur le papier qu'on
        va coller, c'est le dernier moment pour la rattraper."""
        assert fiches.etiquettes(salle, tag="CM4")[0]["circuits"] == []

    def test_un_bloc_sans_zone(self, competition):
        _bloc(competition, "J6", None, 1)
        db.session.commit()
        e = fiches.etiquettes(competition)[0]
        assert e["zone"] is None
        assert e["numero"] == "J6"
        assert "J6" in e["qr"] or e["qr"] == qr.svg("J6", cote_mm=45.0)


class TestLeBudgetDeRequetes:

    def test_il_ne_depend_pas_du_nombre_de_blocs(self, app, competition):
        from sqlalchemy import event

        u11 = Circuit(competition_id=competition.id, nom="U11")
        db.session.add(u11)
        db.session.flush()
        for i in range(1, 61):
            _bloc(competition, f"Z{i}", "Z", i, circuits=[u11])
        db.session.commit()

        def compter(**filtres):
            requetes = []
            moteur = db.session.get_bind()
            noter = lambda *a, **k: requetes.append(1)      # noqa: E731
            event.listen(moteur, "before_cursor_execute", noter)
            try:
                fiches.etiquettes(competition, **filtres)
            finally:
                event.remove(moteur, "before_cursor_execute", noter)
            return len(requetes)

        compter()                       # passe à blanc : amorce de transaction
        assert compter(tag="Z1") == compter() == 3


class TestLaRoute:

    @pytest.fixture()
    def page(self, connecte_orga, salle):
        return connecte_orga.get("/admin/etiquettes").data.decode()

    def test_elle_rend_du_html(self, connecte_orga, salle):
        r = connecte_orga.get("/admin/etiquettes")
        assert r.status_code == 200
        assert r.headers["Content-Type"].startswith("text/html")

    def test_une_etiquette_par_bloc(self, page):
        assert page.count('class="etiquette"') == 6

    def test_les_etiquettes_sont_paginees_en_feuilles(self, page):
        """Six blocs tiennent sur UNE feuille : plus de saut de page par zone,
        qui laissait des feuilles a moitie vides."""
        assert page.count('class="feuille"') == 1

    def test_le_contenu_est_la(self, page):
        for morceau in ("Zone Z", ">V21<", "Prises :", "Rose", "U11 · U13"):
            assert morceau in page, morceau

    def test_l_orphelin_se_voit(self, page):
        assert "ne compte pour" in page
        assert "orphelin" in page

    def test_le_filtre_par_zone(self, connecte_orga, salle):
        page = connecte_orga.get("/admin/etiquettes?zone=D").data.decode()
        assert page.count('class="etiquette"') == 2
        assert page.count('class="feuille"') == 1

    def test_le_filtre_par_bloc(self, connecte_orga, salle):
        page = connecte_orga.get("/admin/etiquettes?bloc=ZJ6").data.decode()
        assert page.count('class="etiquette"') == 1

    def test_une_zone_inconnue_donne_une_page_lisible(self, connecte_orga, salle):
        r = connecte_orga.get("/admin/etiquettes?zone=Q")
        assert r.status_code == 200
        assert "la zone Q" in r.data.decode()

    def test_aucun_bloc_renvoie_vers_l_import(self, connecte_orga, competition):
        page = connecte_orga.get("/admin/etiquettes").data.decode()
        assert "Importer" in page

    def test_aucune_competition_active(self, connecte_orga, app):
        assert connecte_orga.get("/admin/etiquettes").status_code == 409

    def test_sans_session_c_est_refuse(self, client, app, salle):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/etiquettes").status_code == 401

    def test_aucune_dependance_exterieure(self, page):
        """On imprime la veille au soir, parfois sans réseau. Le classeur, lui,
        appelle api.qrserver.com pour ces QR-là."""
        externes = [u for u in re.findall(r'https?://[^\s"\'<>)]+', page)
                    if u != "http://www.w3.org/2000/svg"]
        assert not externes, f"ressources externes : {externes}"

    def test_une_etiquette_n_est_jamais_coupee(self, page):
        assert "break-inside: avoid" in page

    def test_le_saut_de_page_porte_sur_la_feuille(self, page):
        """Et non sur un element de grille : une grille fragmentee « au mieux »
        coupait des etiquettes en deux, et le saut par zone gaspillait des
        feuilles entieres."""
        assert ".feuille + .feuille { break-before: page" in page
        assert ".zone + .zone { break-before: page" not in page

    def test_une_feuille_se_remplit(self, connecte_orga, salle):
        """Huit etiquettes par A4 : une zone de cinq n'en gaspille plus trois,
        la suivante continue sur la meme feuille.

        ⚠️ Ce test comparait `ETIQUETTES_PAR_FEUILLE >= 6` — une constante a
        elle-meme. Il passait avec une pagination totalement cassee. Il compte
        desormais les feuilles REELLEMENT rendues : six etiquettes reparties
        sur trois zones tiennent sur UNE seule feuille."""
        page = connecte_orga.get("/admin/etiquettes").data.decode()
        assert page.count('class="etiquette"') == 6
        assert page.count('class="feuille"') == 1

    def test_huit_par_page_et_la_geometrie_en_variables(self, page):
        """Des variables, ce qui a permis de rendre trois densites et de
        choisir en les regardant."""
        for valeur in ("--etiquette-largeur: 94mm", "--etiquette-hauteur: 68mm",
                       "--feuille-hauteur: 272mm", "--qr: 42mm"):
            assert valeur in page, valeur

    def test_la_feuille_est_plus_PETITE_que_la_page(self, page):
        """⚠️ LE defaut du PDF du 02/09, et il n'avait aucun test.

        La feuille faisait 198 x 285 mm sur une page utile de 198 x 285 : la
        surface EXACTE. Sur une vraie imprimante, dont la zone imprimable est
        plus petite, le moteur coupait chaque feuille en deux et posait la
        derniere ligne de la rangee du bas -- « U11 · U13 · U15 » -- seule sur
        la page suivante. Sept feuilles sortaient en quatorze pages.

        Ce test tient l'INVARIANT, pas les nombres.
        """
        import re

        def mm(nom):
            trouve = re.search(nom + r":\s*([0-9.]+)mm", page)
            assert trouve, nom
            return float(trouve.group(1))

        marge = mm("@page \{ size: A4 portrait; margin")
        utile_h, utile_l = 297 - 2 * marge, 210 - 2 * marge
        assert mm("--feuille-hauteur") <= utile_h - 2, "pas de marge en hauteur"
        assert mm("--feuille-largeur") <= utile_l - 1, "pas de marge en largeur"
        assert (mm("--etiquette-hauteur") * 4) <= mm("--feuille-hauteur")
        assert (mm("--etiquette-largeur") * 2) <= mm("--feuille-largeur")

    def test_la_feuille_elle_meme_est_insecable(self, page):
        bloc = page.split("  .feuille {")[1].split("}")[0]
        assert "break-inside: avoid" in bloc

    def test_la_disposition_est_horizontale(self, page):
        """QR a gauche, texte a droite. Une etiquette se colle au-dessus du
        depart d'un bloc, ou la place est large et basse : empiler
        verticalement gaspillait la moitie de la hauteur."""
        etiquette = page.split('class="etiquette"')[1].split("</div>\n    </div>")[0]
        assert etiquette.index('class="qr"') < etiquette.index('class="quoi"')

    def test_le_qr_reste_au_dessus_du_plancher_a_cette_taille(self):
        """40 mm sur un tag de trois caracteres : largement au-dessus."""
        assert qr.taille_de_module_mm("ZJ6", 40.0) >= qr.MODULE_MINI_MM

    def test_le_journal_dit_qui_et_combien(self, connecte_orga, salle, caplog):
        with caplog.at_level("INFO"):
            connecte_orga.get("/admin/etiquettes?zone=D")
        assert "2 etiquette(s)" in caplog.text
        assert "orga" in caplog.text


class TestLesCouleursSImpriment:
    """⚠️ « Les impressions PDF ne sont que en noir et blanc » — Adrien, 02/09.

    Ce n'etait ni son Mac ni la bibliotheque de QR. Un navigateur ne pose AUCUN
    aplat de couleur a l'impression tant que « Graphismes d'arriere-plan » n'est
    pas coche dans sa boite de dialogue — ce que personne ne coche. Les
    pastilles de difficulte, qui sont des `background`, sortaient donc en ronds
    VIDES. `print-color-adjust: exact` est la seule chose qui le change, et rien
    dans le depot ne la portait.
    """

    @pytest.fixture()
    def page(self, connecte_orga, salle):
        return connecte_orga.get("/admin/etiquettes").data.decode()

    def test_le_gabarit_force_l_impression_des_aplats(self, page):
        assert "-webkit-print-color-adjust: exact" in page, (
            "le prefixe reste necessaire : Safari ne connait que celui-la")
        assert "print-color-adjust: exact" in page

    def test_les_six_teintes_de_difficulte_sont_bien_la(self, page):
        """Sans elles, la regle ci-dessus ne colorerait rien."""
        for teinte in ("#F2C230", "#3FA45B", "#3A7BD5",
                       "#8E5FBF", "#D0342C", "#222"):
            assert teinte in page, teinte


class TestLEtiquetteRemplitSonPapier:
    """« Il faut que ces étiquettes soient plus grosses car tu laisses beaucoup
    trop de blanc autour ; on a presque 2 cm entre le texte et le trait de
    découpage » — Adrien, 02/09.

    Mesure faite dans le navigateur sur la planche d'origine : 15,8 mm de vide
    sous le texte, et autant à sa droite. Le papier était le même, la
    lisibilité à deux mètres non.
    """

    @pytest.fixture()
    def page(self, connecte_orga, salle):
        return connecte_orga.get("/admin/etiquettes").data.decode()

    def test_le_texte_a_grossi_partout(self, page):
        """Les quatre lignes, pas seulement une : c'est leur somme qui remplit
        la hauteur."""
        for regle in (".zone-du-bloc {", ".difficulte {", ".prises {",
                      ".circuits {"):
            bloc = page.split(regle)[1].split("}")[0]
            taille = float(re.search(r"font-size: ([0-9.]+)mm", bloc).group(1))
            assert taille >= 4.0, (regle, taille)

    def test_la_pastille_suit_le_texte(self, page):
        bloc = page.split("  .pastille {")[1].split("}")[0]
        assert float(re.search(r"width: ([0-9.]+)mm", bloc).group(1)) >= 4.0

    def test_la_taille_du_numero_vient_du_serveur(self, page):
        """⚠️ Une taille fixe ne pouvait pas convenir aux deux : « J6 » a de la
        place pour 26 mm, « J32 » n'en a que pour 19,5. La colonne de texte fait
        42 mm — le CSS ne sait pas compter les caractères, le serveur si."""
        assert "font-size: var(--taille, 22mm)" in page
        assert "--taille:" in page

    def test_le_numero_tient_dans_sa_colonne(self):
        """La propriété qui compte, sur toutes les longueurs plausibles."""
        for texte in ("J6", "V21", "J32", "M100", "B1234"):
            taille = fiches.taille_numero_mm(texte)
            largeur = len(texte) * fiches.CHASSE_NUMERO * taille
            assert largeur <= fiches.LARGEUR_NUMERO_MM + 0.01, (texte, largeur)
            assert taille <= fiches.TAILLE_NUMERO_MAXI_MM

    def test_un_numero_court_prend_toute_la_place_permise(self, page):
        assert fiches.taille_numero_mm("J6") == fiches.TAILLE_NUMERO_MAXI_MM

    def test_deux_numeros_de_meme_longueur_ont_la_meme_taille(self):
        """Une planche dont les numéros dansent d'une étiquette à l'autre a
        l'air bancale : la taille est arrondie, pas calculée au micron."""
        assert fiches.taille_numero_mm("V21") == fiches.taille_numero_mm("J32")

    def test_un_numero_vide_ne_fait_pas_exploser_l_impression(self):
        assert fiches.taille_numero_mm("") == fiches.TAILLE_NUMERO_MAXI_MM
        assert fiches.taille_numero_mm(None) == fiches.TAILLE_NUMERO_MAXI_MM

    def test_la_planche_porte_la_taille_de_chaque_etiquette(self, salle):
        planche = fiches.etiquettes(salle)
        assert planche and all(e["taille_numero"] > 0 for e in planche)
