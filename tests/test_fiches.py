"""La fiche du grimpeur — spec 023.

La logique est ici : l'ordre des blocs, le plan de la salle, et les quatre
façons dont une fiche peut n'avoir rien à dire. La mise en page, elle, se
vérifie au papier — on ne prouve pas des millimètres avec `assert`.
"""
import pytest

from climbcontest import comptes, fiches
from climbcontest.classement import COULEURS
from climbcontest.extensions import db
from climbcontest.models import Bloc, BlocCircuit, Circuit, Participant


def _bloc(comp, tag, zone, couleur, numero, circuits=()):
    b = Bloc(competition_id=comp.id, tag=tag, zone=zone, couleur=couleur,
             numero=numero)
    db.session.add(b)
    db.session.flush()
    for c in circuits:
        db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=c.id))
    return b


MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte_orga(client, app):
    """Un organisateur connecté. `/admin/dossards` lui est ouvert."""
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion",
                json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


def _grimpeur(comp, dossard, categorie, nom="Réglette", prenom="Camille"):
    p = Participant(competition_id=comp.id, nom=nom, prenom=prenom,
                    club="Annonay Escalade", categorie=categorie,
                    dossard=dossard, present=True)
    db.session.add(p)
    db.session.flush()
    return p


class TestLePlanEstUneConstanteDeLaSalle:
    """Le même texte dans les trois classeurs archivés, de 2024 à mars 2026 :
    c'est le mur d'Annonay, pas une donnée de compétition.
    """

    def test_huit_lignes_de_sept_cases(self):
        assert len(fiches.PLAN) == 8
        assert all(len(ligne) == 7 for ligne in fiches.PLAN)

    def test_dix_sept_zones(self):
        """Le classeur en compte vingt ; U, V et W n'ont jamais porté de bloc et
        ne sont pas dessinées. C'est justement ce que `hors_plan` rattrape."""
        assert len(fiches.ZONES_DU_PLAN) == 17
        assert {"U", "V", "W"}.isdisjoint(fiches.ZONES_DU_PLAN)

    def test_les_zones_sont_deduites_du_plan_pas_recopiees(self):
        attendu = {c for ligne in fiches.PLAN for c in ligne if isinstance(c, str)}
        assert fiches.ZONES_DU_PLAN == attendu

    @pytest.mark.parametrize("zone", list("ABCDEFGHIJKLMNXYZ"))
    def test_chaque_zone_dessinee_apparait_une_fois(self, zone):
        compte = sum(ligne.count(zone) for ligne in fiches.PLAN)
        assert compte == 1, f"la zone {zone} apparait {compte} fois"

    def test_chaque_ligne_fait_sept_colonnes_a_l_affichage(self):
        """Un repère tient sur trois cases. S'il n'absorbait pas les deux vides
        qui le suivent, la ligne en compterait neuf et tout le plan glisserait.
        """
        for ligne in fiches.plan_pour(set()):
            assert sum(case["colonnes"] for case in ligne) == 7

    def test_les_reperes_ne_sont_pas_des_zones(self):
        plan = fiches.plan_pour(set())
        reperes = [c["repere"] for ligne in plan for c in ligne if c["repere"]]
        assert sorted(reperes) == ["Escalier", "Haut"]
        assert all(c["zone"] is None for ligne in plan for c in ligne if c["repere"])

    def test_les_zones_du_grimpeur_s_allument(self):
        plan = fiches.plan_pour({"Z", "D", "A"})
        allumees = {c["zone"] for ligne in plan for c in ligne if c["sienne"]}
        assert allumees == {"Z", "D", "A"}

    def test_aucune_zone_ne_s_allume_sans_bloc(self):
        plan = fiches.plan_pour(set())
        assert not any(c["sienne"] for ligne in plan for c in ligne)


class TestLeNumeroSansSaZone:

    def test_le_tag_perd_son_prefixe(self, competition):
        assert fiches.numero(Bloc(tag="ZJ6", zone="Z")) == "J6"

    def test_une_zone_de_deux_lettres(self, competition):
        """Rien ne garantit qu'une zone tiendra toujours sur une lettre — d'où
        `removeprefix` et non une découpe à un caractère."""
        assert fiches.numero(Bloc(tag="AB12", zone="AB")) == "12"

    def test_sans_zone_on_garde_le_tag(self, competition):
        assert fiches.numero(Bloc(tag="J6", zone=None)) == "J6"

    def test_un_tag_reduit_a_sa_zone_garde_le_tag(self, competition):
        """Mieux vaut un libellé redondant qu'une case vide sur le papier."""
        assert fiches.numero(Bloc(tag="Z", zone="Z")) == "Z"


class TestLOrdreDuClasseur:
    """`Plan!AM` trie sur `Listes!B41:B46 + COUNTIF(...)` : la difficulté
    d'abord, le numéro ensuite. La fiche et le classeur doivent lire dans le
    même ordre.
    """

    @pytest.fixture()
    def circuit(self, competition):
        c = Circuit(competition_id=competition.id, nom="U11")
        db.session.add(c)
        db.session.flush()
        return c

    def test_la_difficulte_avant_le_numero(self, competition, circuit):
        _bloc(competition, "ZB1", "Z", "Bleu", 1, [circuit])
        _bloc(competition, "ZJ9", "Z", "Jaune", 2, [circuit])
        _bloc(competition, "ZV3", "Z", "Vert", 3, [circuit])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert [g["couleur"] for g in fiche["groupes"]] == ["Jaune", "Vert", "Bleu"]

    def test_le_tri_se_fait_sur_la_chaine(self, competition, circuit):
        """« J10 » avant « J9 » : le classeur trie du texte, pas des nombres. On
        reproduit, on ne corrige pas — sinon les deux listes divergeraient."""
        _bloc(competition, "ZJ9", "Z", "Jaune", 1, [circuit])
        _bloc(competition, "ZJ10", "Z", "Jaune", 2, [circuit])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert [b["numero"] for b in fiche["groupes"][0]["blocs"]] == ["J10", "J9"]

    def test_un_bloc_sans_couleur_passe_en_dernier(self, competition, circuit):
        """Il est douteux : il ne doit pas ouvrir la liste."""
        _bloc(competition, "ZX1", "Z", None, 1, [circuit])
        _bloc(competition, "ZN2", "Z", "Noir", 2, [circuit])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert [g["couleur"] for g in fiche["groupes"]] == ["Noir", None]

    def test_une_couleur_inconnue_du_classement_compte_comme_absente(
            self, competition, circuit):
        _bloc(competition, "ZZ1", "Z", "Turquoise", 1, [circuit])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert fiche["groupes"][0]["couleur"] is None

    def test_l_echelle_des_couleurs_n_est_pas_recopiee(self):
        """Deux listes qui divergeraient trieraient la fiche autrement que le
        classement."""
        assert fiches.COULEURS is COULEURS


class TestSeulsLesBlocsDeSonCircuit:

    def test_un_bloc_hors_circuit_est_absent(self, competition):
        u11 = Circuit(competition_id=competition.id, nom="U11")
        u13 = Circuit(competition_id=competition.id, nom="U13")
        db.session.add_all([u11, u13])
        db.session.flush()
        _bloc(competition, "ZJ1", "Z", "Jaune", 1, [u11])
        _bloc(competition, "ZJ2", "Z", "Jaune", 2, [u13])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert fiche["total"] == 1
        assert fiche["groupes"][0]["blocs"][0]["numero"] == "J1"

    def test_les_deux_genres_grimpent_le_meme_circuit(self, competition):
        u11 = Circuit(competition_id=competition.id, nom="U11")
        db.session.add(u11)
        db.session.flush()
        _bloc(competition, "ZJ1", "Z", "Jaune", 1, [u11])
        db.session.commit()
        elle = _grimpeur(competition, 1, "U11 F")
        lui = _grimpeur(competition, 2, "U11 H", nom="Bidoigt", prenom="Yanis")
        a, b = fiches.construire(competition, [elle, lui])
        assert a["total"] == b["total"] == 1
        assert a["circuit"] == b["circuit"] == "U11"


class TestCeQuiManqueSeDit:
    """La fiche s'imprime TOUJOURS : c'est elle qui porte le QR, et sans QR le
    grimpeur ne peut pas être scanné. Ce qui manque se dit, en toutes lettres.
    """

    def test_sans_categorie(self, competition):
        db.session.commit()
        p = _grimpeur(competition, 1, None)
        [fiche] = fiches.construire(competition, [p])
        assert fiche["circuit"] is None
        assert fiche["groupes"] == []
        assert "Aucune catégorie" in fiche["manque"]
        assert fiche["qr"].startswith("<svg")

    def test_circuit_inconnu_en_base(self, competition):
        """Le classeur n'a pas encore été importé."""
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert "inconnu" in fiche["manque"]

    def test_circuit_connu_mais_sans_bloc(self, competition):
        """Un message différent : les deux ne se réparent pas au même endroit."""
        db.session.add(Circuit(competition_id=competition.id, nom="U11"))
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert "Aucun bloc" in fiche["manque"]
        assert "inconnu" not in fiche["manque"]

    def test_rien_ne_manque_quand_tout_va_bien(self, competition):
        u11 = Circuit(competition_id=competition.id, nom="U11")
        db.session.add(u11)
        db.session.flush()
        _bloc(competition, "ZJ1", "Z", "Jaune", 1, [u11])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert fiche["manque"] is None


class TestUneZoneHorsPlanSeDit:
    """Un bloc qu'on ne peut pas situer doit SE DIRE, pas disparaître."""

    @pytest.fixture()
    def circuit(self, competition):
        c = Circuit(competition_id=competition.id, nom="U11")
        db.session.add(c)
        db.session.flush()
        return c

    def test_une_zone_absente_du_plan(self, competition, circuit):
        _bloc(competition, "UJ1", "U", "Jaune", 1, [circuit])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert fiche["hors_plan"] == ["U"]

    def test_rien_a_signaler_quand_tout_est_sur_le_plan(self, competition, circuit):
        _bloc(competition, "ZJ1", "Z", "Jaune", 1, [circuit])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert fiche["hors_plan"] == []

    def test_un_bloc_sans_zone_n_allume_rien(self, competition, circuit):
        _bloc(competition, "J1", None, "Jaune", 1, [circuit])
        db.session.commit()
        p = _grimpeur(competition, 1, "U11 F")
        [fiche] = fiches.construire(competition, [p])
        assert fiche["hors_plan"] == []
        assert not any(c["sienne"] for ligne in fiche["plan"] for c in ligne)
        assert fiche["groupes"][0]["blocs"][0]["numero"] == "J1"


class TestLeBudgetDeRequetes:
    """Cent fiches ne doivent pas coûter cent requêtes. Même budget que
    `circuits.inventaire()` : le regroupement se fait une fois, en mémoire.
    """

    def test_le_nombre_de_requetes_ne_depend_pas_du_nombre_de_grimpeurs(
            self, app, competition):
        from sqlalchemy import event

        u11 = Circuit(competition_id=competition.id, nom="U11")
        db.session.add(u11)
        db.session.flush()
        for i in range(1, 21):
            _bloc(competition, f"ZJ{i}", "Z", "Jaune", i, [u11])
        peu = [_grimpeur(competition, i, "U11 F") for i in range(1, 4)]
        beaucoup = peu + [_grimpeur(competition, i, "U11 F") for i in range(4, 61)]
        db.session.commit()

        def compter(participants):
            # Les participants arrivent CHARGES, comme dans la route : elle les
            # a lus d'un `Participant.query...all()` juste avant. Sans ce
            # rechauffement, on mesurerait le rafraichissement que SQLAlchemy
            # fait apres un `commit()` -- un artefact du test, pas du produit.
            for p in participants:
                p.categorie, p.dossard, p.nom, p.club

            requetes = []
            moteur = db.session.get_bind()

            def noter(*args, **kwargs):
                requetes.append(1)

            event.listen(moteur, "before_cursor_execute", noter)
            try:
                fiches.construire(competition, participants)
            finally:
                event.remove(moteur, "before_cursor_execute", noter)
            return len(requetes)

        # Une passe a blanc d'abord : la toute premiere mesure d'une session
        # porte une amorce de transaction qui n'a rien a voir avec le sujet.
        compter(beaucoup)

        # Les blocs, les circuits, les liens. Pas plus -- et surtout, pas plus
        # pour soixante grimpeurs que pour trois.
        assert compter(peu) == 3
        assert compter(beaucoup) == 3


class TestLaPlanche:
    """Ce que la route rend, vu de la page."""

    @pytest.fixture()
    def page(self, connecte_orga, competition):
        u11 = Circuit(competition_id=competition.id, nom="U11")
        db.session.add(u11)
        db.session.flush()
        _bloc(competition, "ZJ6", "Z", "Jaune", 1, [u11])
        _bloc(competition, "DV21", "D", "Vert", 2, [u11])
        _grimpeur(competition, 7, "U11 F")
        db.session.commit()
        return connecte_orga.get("/admin/dossards").data.decode()

    def test_l_identite_est_la(self, page):
        assert "Réglette Camille" in page
        assert "Annonay Escalade" in page
        assert "U11 F" in page
        assert "circuit U11" in page

    def test_les_blocs_et_leurs_zones_sont_la(self, page):
        for morceau in (">J6<", ">V21<", ">Z<", ">D<"):
            assert morceau in page, morceau

    def test_le_plan_de_la_salle_est_la(self, page):
        assert "Escalier" in page
        assert "Haut" in page

    def test_le_papier_dit_combien_de_blocs(self, page):
        assert "Tes 2 blocs" in page
