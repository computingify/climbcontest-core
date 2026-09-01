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

    def test_une_coupure_a_chaque_changement_de_zone(self, salle):
        planche = fiches.etiquettes(salle)
        assert [e["coupure"] for e in planche] == [
            False, False, True, False, True, False]

    def test_pas_de_coupure_sur_la_toute_premiere(self, salle):
        """Sinon la planche commencerait par une page blanche."""
        assert fiches.etiquettes(salle)[0]["coupure"] is False

    def test_le_regroupement_suit_les_coupures(self, salle):
        groupes = fiches.par_zone(fiches.etiquettes(salle))
        assert [g["zone"] for g in groupes] == ["Z", "D", "C"]
        assert [len(g["etiquettes"]) for g in groupes] == [2, 2, 2]

    def test_une_liste_vide_ne_fait_aucun_groupe(self, competition):
        assert fiches.par_zone(fiches.etiquettes(competition)) == []


class TestLesFiltres:

    def test_une_zone(self, salle):
        planche = fiches.etiquettes(salle, zone="D")
        assert [e["tag"] for e in planche] == ["DV21", "DB2"]

    def test_une_zone_filtree_n_a_aucune_coupure(self, salle):
        """Une seule zone tient sur une page : il n'y a rien à couper."""
        assert not any(e["coupure"] for e in fiches.etiquettes(salle, zone="D"))

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

    def test_une_grille_par_zone(self, page):
        assert page.count('class="zone"') == 3

    def test_le_contenu_est_la(self, page):
        for morceau in ("Zone Z", ">V21<", "Prises :", "Rose", "U11 · U13"):
            assert morceau in page, morceau

    def test_l_orphelin_se_voit(self, page):
        assert "ne compte pour" in page
        assert "orphelin" in page

    def test_le_filtre_par_zone(self, connecte_orga, salle):
        page = connecte_orga.get("/admin/etiquettes?zone=D").data.decode()
        assert page.count('class="etiquette"') == 2
        assert page.count('class="zone"') == 1

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

    def test_une_zone_par_page(self, page):
        assert ".zone + .zone { break-before: page" in page

    def test_le_journal_dit_qui_et_combien(self, connecte_orga, salle, caplog):
        with caplog.at_level("INFO"):
            connecte_orga.get("/admin/etiquettes?zone=D")
        assert "2 etiquette(s)" in caplog.text
        assert "orga" in caplog.text
