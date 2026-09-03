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
    """Le mur d'Annonay, relevé par Adrien le 02/09/2026 : c'est la salle, pas
    une donnée de compétition. D'où une constante, et non une table.
    """

    def test_dix_sept_murs(self):
        assert len(fiches.PLAN["murs"]) == 17

    def test_dix_sept_zones(self):
        """Le classeur en compte vingt ; U, V et W n'ont jamais porté de bloc et
        ne sont pas dessinées. C'est justement ce que `hors_plan` rattrape."""
        assert len(fiches.ZONES_DU_PLAN) == 17
        assert {"U", "V", "W"}.isdisjoint(fiches.ZONES_DU_PLAN)

    def test_les_zones_sont_deduites_du_plan_pas_recopiees(self):
        attendu = {m["zone"] for m in fiches.PLAN["murs"] if m["zone"]}
        assert fiches.ZONES_DU_PLAN == attendu

    @pytest.mark.parametrize("zone", list("ABCDEFGHIJKLMNXYZ"))
    def test_chaque_zone_dessinee_apparait_une_fois(self, zone):
        compte = sum(1 for m in fiches.PLAN["murs"] if m["zone"] == zone)
        assert compte == 1, f"la zone {zone} apparait {compte} fois"

    def test_chaque_mur_est_un_polygone_ferme(self):
        """Trois points au moins : en dessous, ce n'est pas une surface."""
        for m in fiches.PLAN["murs"]:
            assert len(m["points"]) >= 3, m["zone"]
            assert all(len(pt) == 2 for pt in m["points"]), m["zone"]

    def test_tous_les_profils_sont_connus(self):
        for m in fiches.PLAN["murs"]:
            assert m["profil"] in fiches.PAR_PROFIL, m["zone"]

    def test_les_profils_vont_du_moins_au_plus_deversant(self):
        """L'ordre EST l'information : la trame se densifie et le gris fonce à
        mesure qu'on descend la liste. Un jour où quelqu'un réordonnera la
        constante par commodité, ce test le dira.
        """
        assert [p["cle"] for p in fiches.PROFILS] == [
            "dalle", "vertical", "incline", "devers", "surplomb", "toit"]

    def test_les_reperes_ne_sont_pas_des_zones(self):
        plan = fiches.plan_pour(set())
        assert [r["texte"] for r in plan["reperes"]] == ["Escalier", "Haut", "Bas"]
        assert "Escalier" not in fiches.ZONES_DU_PLAN

    def test_les_zones_du_grimpeur_s_allument(self):
        plan = fiches.plan_pour({"Z", "D", "A"})
        allumees = {m["zone"] for m in plan["murs"] if m["sienne"]}
        assert allumees == {"Z", "D", "A"}

    def test_aucune_zone_ne_s_allume_sans_bloc(self):
        plan = fiches.plan_pour(set())
        assert not any(m["sienne"] for m in plan["murs"])

    def test_une_zone_inconnue_n_allume_rien(self):
        """Un bloc en zone « Q » ne doit allumer aucun mur — il part dans
        `hors_plan`, pas dans le dessin."""
        plan = fiches.plan_pour({"Q"})
        assert not any(m["sienne"] for m in plan["murs"])


class TestLeCadrageNeRogneAucunTrait:
    """⚠️ Sept murs d'Annonay touchent le bord du dessin — L, M, N à gauche,
    X et Y en haut, E à droite. Sans marge, la moitié de leur trait sort du
    cadre. Le défaut ne se voit qu'à l'affichage, jamais à la lecture.
    """

    def test_le_cadrage_deborde_la_vue_de_chaque_cote(self):
        plan = fiches.plan_pour(set())
        x, y, l, h = (float(v) for v in plan["cadrage"].split())
        largeur, hauteur = fiches.PLAN["vue"]
        m = fiches.MARGE_PLAN
        assert (x, y) == (-m, -m)
        assert (l, h) == (largeur + 2 * m, hauteur + 2 * m)

    def test_des_murs_touchent_bien_le_bord(self):
        """Si ce test tombe un jour, c'est que le relevé a changé — et la marge
        mérite alors d'être rediscutée plutôt que gardée par habitude."""
        largeur, hauteur = fiches.PLAN["vue"]
        touchent = [m["zone"] for m in fiches.PLAN["murs"]
                    if any(x in (0, largeur) or y in (0, hauteur)
                           for x, y in m["points"])]
        assert sorted(touchent) == ["E", "L", "M", "N", "X", "Y"]

    def test_aucun_point_ne_sort_de_la_vue(self):
        largeur, hauteur = fiches.PLAN["vue"]
        for m in fiches.PLAN["murs"]:
            for x, y in m["points"]:
                assert 0 <= x <= largeur, f"{m['zone']} sort en x"
                assert 0 <= y <= hauteur, f"{m['zone']} sort en y"


class TestLaLettreTientDansSonMur:
    """⚠️ Mesuré dans le navigateur, halo compris : à 9 unités fixes, aucune des
    17 zones ne débordait — mais la marge n'était que de 0,25 unité. Une zone à
    deux caractères la crevait. Ça tenait par chance, pas par construction.
    """

    def test_les_zones_d_annonay_gardent_la_taille_maximale(self):
        """Le calcul ne doit mordre que là où il le faut : le rendu d'Annonay
        est inchangé."""
        plan = fiches.plan_pour(set())
        assert {m["taille"] for m in plan["murs"]} == {fiches.LETTRE_MAXI}

    @pytest.mark.parametrize("texte", ["A", "A1", "NM", "MK", "WW", "Z12", "MMM"])
    def test_la_lettre_tient_dans_sa_boite_au_pire_glyphe(self, texte):
        """⚠️ Ce test rejouait 0,62 -- la constante de l'implémentation --
        contre elle-même : il valait « 12 ≤ 15 » quoi que fasse la police, et
        ne pouvait pas tomber. Il est mesuré au navigateur qu'il mentait :
        onze combinaisons de deux caractères sur trente-neuf débordaient.

        Il borne désormais par la largeur du PIRE glyphe, celle que
        l'implémentation utilise pour se protéger — et les cas éprouvés sont
        ceux qui débordaient réellement : « NM », « MK », « WW ».
        """
        carre = ((0, 0), (15, 0), (15, 15), (0, 15))
        taille = fiches.taille_lettre(carre, texte)
        au_pire = taille * fiches.LARGEUR_CAPITALE * len(texte)
        assert au_pire <= 15, f"« {texte} » deborde : {au_pire:.1f}"

    def test_la_largeur_de_capitale_borne_au_lieu_de_moyenner(self):
        """Une moyenne ne borne rien. Si quelqu'un ramène cette constante vers
        la moyenne d'une capitale (~0,62) pour gagner en taille de police, ce
        test le dira -- et le débordement reviendra sur du papier distribué."""
        assert fiches.LARGEUR_CAPITALE >= 0.8

    def test_le_releve_d_annonay_garde_sa_taille(self):
        """Le correctif ne doit mordre que là où il le faut : les dix-sept
        zones du club n'ont qu'une lettre, leur rendu est inchangé."""
        plan = fiches.plan_pour(set(), fiches.PLAN)
        assert {m["taille"] for m in plan["murs"]} == {fiches.LETTRE_MAXI}

    def test_un_mur_minuscule_garde_une_lettre_lisible(self):
        """Mieux vaut une lettre serrée qu'une lettre absente : le plancher
        vaut 1,06 mm sur la colonne de 37 mm."""
        minuscule = ((0, 0), (2, 0), (2, 2), (0, 2))
        assert fiches.taille_lettre(minuscule, "A") == fiches.LETTRE_MINI

    def test_un_polygone_degenere_ne_fait_pas_tomber_le_calcul(self):
        aplati = ((0, 0), (10, 0), (20, 0))
        assert fiches.taille_lettre(aplati, "A") > 0


class TestLaLettreVaAuCentreDeSurface:

    def test_le_centre_d_un_rectangle(self):
        plan = fiches.plan_pour(set())
        x = next(m for m in plan["murs"] if m["zone"] == "X")
        assert x["etiquette"] == (70.0, 7.5)

    def test_une_etiquette_explicite_gagne_sur_le_centroide(self):
        """Un polygone concave peut avoir son centroïde hors de lui-même ; le
        relevé doit alors pouvoir imposer la position."""
        original = fiches.PLAN["murs"]
        force = dict(original[0])
        force["etiquette"] = (5, 5)
        fiches.PLAN["murs"] = (force,) + original[1:]
        try:
            place = fiches.plan_pour(set())["murs"][0]["etiquette"]
            assert place == (5, 5)
        finally:
            fiches.PLAN["murs"] = original


class TestUnProfilInconnuNeCassePasUneImpression:

    def test_le_repli_est_le_vertical(self):
        original = fiches.PLAN["murs"]
        casse = dict(original[0])
        casse["profil"] = "trampoline"
        fiches.PLAN["murs"] = (casse,) + original[1:]
        try:
            assert fiches.plan_pour(set())["murs"][0]["profil"] == "vertical"
        finally:
            fiches.PLAN["murs"] = original


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
        assert not any(m["sienne"] for m in fiche["plan"]["murs"])
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

        # Les blocs, les circuits, les liens, et LE PLAN (spec 029, il vient
        # de la base depuis qu'il se dessine dans la console). Pas plus -- et
        # surtout, pas plus pour soixante grimpeurs que pour trois.
        #
        # ⚠️ Le plan est lu UNE FOIS pour toute la planche et passe a chaque
        # fiche. Sans ca, `plan_pour` etant appele par grimpeur, cent vingt
        # fiches auraient fait cent vingt lectures du meme plan. C'est ce test
        # qui l'a rattrape, pas une relecture.
        assert compter(peu) == 4
        assert compter(beaucoup) == 4


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


class TestLeFormatDuPapier:
    """A4 PAYSAGE, deux fiches en largeur, trois en hauteur — six par feuille.

    Le format a ete refait quatre fois avant d'arriver la, chaque fois en le
    REGARDANT. Ces trois assertions ne prouvent pas qu'il est joli ; elles
    prouvent qu'on ne l'a pas remis en portrait sans s'en rendre compte.
    """

    @pytest.fixture()
    def page(self, connecte_orga, competition):
        _grimpeur(competition, 1, "U11 F")
        db.session.commit()
        return connecte_orga.get("/admin/dossards").data.decode()

    def test_la_feuille_est_un_a4_paysage(self, page):
        assert "@page { size: A4 landscape; margin: 10mm; }" in page

    def test_deux_fiches_en_largeur(self, page):
        assert "grid-template-columns: repeat(2, var(--fiche-largeur))" in page

    def test_la_geometrie_tient_dans_quelques_variables(self, page):
        """C'est ce qui a permis d'essayer 2x2 et 2x3 sans rien rebatir, et de
        choisir sur pieces."""
        for valeur in ("--fiche-largeur: 138mm", "--fiche-hauteur: 62mm",
                       "--feuille-hauteur: 186mm", "--qr: 24mm"):
            assert valeur in page, valeur

    def test_la_feuille_est_plus_PETITE_que_la_page(self, page):
        """⚠️ LE defaut du PDF du 02/09, et il n'avait aucun test.

        La feuille faisait 285 x 198 mm sur une page utile de 285 x 198 : la
        surface EXACTE, zero marge d'erreur. Aucune imprimante ne rend cette
        surface-la -- le pilote applique la zone imprimable du papier -- et le
        moteur coupait donc chaque feuille en deux, posant la derniere ligne de
        la rangee du bas seule sur la page suivante. Vingt feuilles sortaient
        en quarante pages.

        Ce test tient l'INVARIANT, pas les nombres : quoi qu'on change, la
        feuille doit rester strictement plus petite que ce que la page offre,
        avec de la marge pour l'arrondi des millimetres en pixels.
        """
        import re

        def mm(nom):
            trouve = re.search(nom + r":\s*([0-9.]+)mm", page)
            assert trouve, nom
            return float(trouve.group(1))

        marge = mm("@page \{ size: A4 landscape; margin")
        utile_h, utile_l = 210 - 2 * marge, 297 - 2 * marge
        assert mm("--feuille-hauteur") <= utile_h - 2, "pas de marge en hauteur"
        assert mm("--feuille-largeur") <= utile_l - 1, "pas de marge en largeur"
        # Et la feuille contient bien ce qu'on y range.
        assert (mm("--fiche-hauteur") * 3) <= mm("--feuille-hauteur")
        assert (mm("--fiche-largeur") * 2) <= mm("--feuille-largeur")

    def test_la_feuille_elle_meme_est_insecable(self, page):
        """La deuxieme ligne de defense : si la zone imprimable etait quand
        meme trop courte, la feuille entiere partirait a la page suivante --
        on perdrait une page, on ne couperait pas une rangee en deux."""
        bloc = page.split("  .feuille {")[1].split("}")[0]
        assert "break-inside: avoid" in bloc

    def test_une_fiche_n_est_jamais_coupee(self, page):
        assert "break-inside: avoid" in page

    def test_les_colonnes_viennent_du_serveur(self, page):
        """`auto-fit` choisissait ses colonnes d'apres la LARGEUR, sans rien
        savoir du nombre de LIGNES que ca produirait : quand un groupe de
        couleur passait sur deux lignes, la fiche debordait et ses cadres
        chevauchaient. Signale par Adrien le 02/09."""
        assert "repeat(var(--cols, 7), minmax(0, 1fr))" in page
        assert "repeat(auto-fit" not in page and "repeat(auto-fill" not in page
        assert "--cols:" in page          # pose sur chaque fiche

    def test_la_grille_de_blocs_ne_peut_pas_deborder_de_sa_colonne(self, page):
        """⚠️ `1fr` vaut `minmax(auto, 1fr)` : une piste ne descend JAMAIS sous
        la largeur de son texte. Neuf colonnes de « M52 » faisaient soixante-dix
        millimetres de grille dans une colonne de soixante, et les dernieres
        cases se peignaient par-dessus le plan du mur -- sur les 120 fiches de
        la planche, mesure du 02/09. Le format d'origine avait deja le defaut ;
        il n'avait aucun test parce que rien ne regardait la LARGEUR."""
        assert "repeat(var(--cols, 7), 1fr)" not in page
        assert "minmax(0, 1fr)" in page
        # La taille du numero vient du serveur : sans elle, borner la piste ne
        # ferait que tronquer le texte au lieu de le peindre a cote.
        assert "font-size: var(--case, 3mm)" in page
        assert "--case:" in page

    def test_une_fiche_ne_peut_pas_deborder_sur_sa_voisine(self, page):
        bloc = page.split("  .fiche {")[1].split("}")[0]
        assert "overflow: hidden" in bloc

    def test_la_pagination_est_faite_en_python(self, page):
        """Une grille dont les elements portent `break-inside: avoid` est
        fragmentee « au mieux » : une fiche se retrouvait a cheval sur deux
        feuilles. Le saut de page porte maintenant sur la FEUILLE."""
        assert ".feuille + .feuille { break-before: page" in page
        assert 'class="feuille"' in page


class TestLaHauteurDUneFiche:
    """⚠️ Le cœur technique de la correction du 02/09, et il n'avait AUCUN test.

    Le commentaire du module affirmait pourtant que « `tests/test_fiches.py`
    vérifie la cohérence du calcul » : c'était faux, aucun test n'appelait ces
    fonctions. Les seuls tests présents cherchaient des chaînes CSS dans le
    HTML rendu, ce qui passe quel que soit le calcul.

    Les constantes, elles, restent MESURÉES dans le navigateur : ces tests
    vérifient la cohérence du calcul, pas l'accord des constantes avec le CSS.
    """

    def test_un_groupe_qui_tient_sur_une_ligne(self):
        assert fiches.hauteur_mm([5], 7) == pytest.approx(fiches.HAUTEUR_LIGNE_MM)

    def test_une_ligne_de_plus_coute_le_supplement(self):
        une = fiches.hauteur_mm([7], 7)
        deux = fiches.hauteur_mm([8], 7)
        assert deux - une == pytest.approx(fiches.HAUTEUR_LIGNE_SUP_MM)

    def test_les_groupes_paient_une_marge_entre_eux(self):
        seul = fiches.hauteur_mm([5], 7)
        deux = fiches.hauteur_mm([5, 5], 7)
        assert deux - 2 * seul == pytest.approx(fiches.MARGE_GROUPE_MM)

    def test_plus_de_colonnes_ne_rend_jamais_plus_haut(self):
        """La monotonie est ce qui rend la recherche du minimum correcte : si
        elle tombe, `colonnes_qui_tiennent` peut renvoyer un nombre trop petit.
        """
        tailles = [20, 10, 10, 21, 8]
        hauteurs = [fiches.hauteur_mm(tailles, c)
                    for c in range(fiches.COLONNES_MINI, fiches.COLONNES_MAXI + 1)]
        assert hauteurs == sorted(hauteurs, reverse=True)

    def test_aucun_bloc_ne_coute_rien(self):
        assert fiches.hauteur_mm([], 7) == 0


class TestLeNombreDeColonnes:

    def _groupes(self, *tailles):
        return [{"blocs": [{"numero": str(i)} for i in range(n)]} for n in tailles]

    def test_sans_bloc_on_garde_le_plancher(self):
        assert fiches.colonnes_qui_tiennent([]) == fiches.COLONNES_MINI
        assert fiches.colonnes_qui_tiennent(self._groupes(0)) == fiches.COLONNES_MINI

    def test_peu_de_blocs_gardent_les_cases_les_plus_grandes(self):
        """Le plus PETIT nombre de colonnes donne les cases les plus lisibles."""
        assert fiches.colonnes_qui_tiennent(self._groupes(3)) == fiches.COLONNES_MINI

    def test_le_choix_fait_reellement_tenir_la_fiche(self):
        """La propriété qui compte : quel que soit le cas, le nombre choisi
        rentre dans la hauteur utile — sauf à saturer le plafond."""
        for tailles in ([43], [20, 10, 10, 21, 8], [7, 4, 4, 11, 2, 3, 9],
                        [1] * 6, [12, 12, 12], [30, 13]):
            c = fiches.colonnes_qui_tiennent(self._groupes(*tailles))
            assert fiches.COLONNES_MINI <= c <= fiches.COLONNES_MAXI
            if c < fiches.COLONNES_MAXI:
                assert fiches.hauteur_mm(tailles, c) <= fiches.HAUTEUR_UTILE_MM
            # ... et c'est bien le PLUS PETIT qui tient. Au plancher il n'y a
            # rien en dessous a essayer : `COLONNES_MINI` n'est pas un choix,
            # c'est la limite en dessous de laquelle les cases s'etirent.
            if c > fiches.COLONNES_MINI:
                assert fiches.hauteur_mm(tailles, c - 1) > fiches.HAUTEUR_UTILE_MM

    def test_un_cas_impossible_sature_le_plafond_sans_exploser(self):
        """Trois cents blocs ne tiennent sur aucune fiche : on rend le maximum
        plutôt que de lever une exception en pleine impression."""
        assert fiches.colonnes_qui_tiennent(self._groupes(300)) == fiches.COLONNES_MAXI

    def test_les_quarante_trois_blocs_qui_debordaient(self):
        """Le cas signalé par Adrien le 02/09 : la fiche débordait sur sa
        voisine. Avec le calcul, elle tient."""
        c = fiches.colonnes_qui_tiennent(self._groupes(43))
        assert fiches.hauteur_mm([43], c) <= fiches.HAUTEUR_UTILE_MM


class TestLeDecoupageEnFeuilles:
    """⚠️ Aucun test ne paginait au-delà d'UNE feuille : les assertions
    existantes passaient avec `PAR_FEUILLE = 1000`."""

    def test_une_liste_vide_ne_fait_aucune_feuille(self):
        assert fiches.en_feuilles([], 6) == []

    def test_le_compte_exact_ne_laisse_pas_de_feuille_vide(self):
        assert len(fiches.en_feuilles(list(range(12)), 6)) == 2

    def test_la_derniere_feuille_est_incomplete(self):
        feuilles = fiches.en_feuilles(list(range(17)), 8)
        assert [len(f) for f in feuilles] == [8, 8, 1]

    def test_aucun_element_n_est_perdu_ni_duplique(self):
        source = list(range(53))
        feuilles = fiches.en_feuilles(source, fiches.ETIQUETTES_PAR_FEUILLE)
        assert [x for f in feuilles for x in f] == source

    def test_les_chiffres_annonces_par_la_spec(self):
        """120 fiches sur 20 feuilles, 53 étiquettes sur 7."""
        assert len(fiches.en_feuilles(list(range(120)),
                                      fiches.FICHES_PAR_FEUILLE)) == 20
        assert len(fiches.en_feuilles(list(range(53)),
                                      fiches.ETIQUETTES_PAR_FEUILLE)) == 7

    def test_un_seul_element_tient_sur_une_feuille(self):
        assert fiches.en_feuilles([1], 6) == [[1]]


class TestLaLargeurDUneFiche:
    """⚠️ L'AXE QUI N'ÉTAIT PAS CALCULÉ, et le second défaut du 02/09.

    `colonnes_qui_tiennent` ne regardait que la hauteur. La largeur n'était
    bornée par rien : `repeat(var(--cols), 1fr)` vaut `minmax(auto, 1fr)`, et
    une piste de grille ne descend jamais sous la largeur de son texte. Neuf
    colonnes de « M52 » faisaient soixante-dix millimètres de grille dans une
    colonne de soixante, et les dernières cases se peignaient PAR-DESSUS le
    plan du mur. Mesure au navigateur : les 120 fiches de la planche
    débordaient, toutes, de 5,75 mm — avant même le changement de format.

    Ces tests tiennent le CALCUL. Les constantes, elles, restent mesurées dans
    le navigateur : aucun test ne peut vérifier qu'elles décrivent encore le
    CSS.
    """

    def _groupes(self, tailles, longueur=3):
        return [{"blocs": [{"numero": "X" * longueur} for _ in range(n)]}
                for n in tailles]

    def test_la_grille_tient_dans_la_colonne_quoi_qu_il_arrive(self):
        """La propriété qui compte, sur les vrais circuits du 02/09 et sur des
        cas extrêmes."""
        cas = [[7, 10, 9, 7, 2, 1],        # U15, 36 blocs
               [13, 12, 7, 3, 1],          # U13, 36 blocs
               [22, 12, 2],                # U11, 36 blocs
               [8] * 6, [43], [1] * 6, [300]]
        for tailles in cas:
            for longueur in (1, 2, 3, 4):
                groupes = self._groupes(tailles, longueur)
                colonnes, taille = fiches.mise_en_page_blocs(groupes)
                largeur_case = (
                    (fiches.LARGEUR_BLOCS_MM
                     - (colonnes - 1) * fiches.GOUTTIERE_CASE_MM) / colonnes)
                texte = longueur * fiches.CHASSE_CASE * taille
                tient = texte <= largeur_case - fiches.HABILLAGE_CASE_MM + 0.01
                # Sous le plancher on ne descend plus : la case tronque
                # proprement (`overflow: hidden`) plutot que d'imprimer du 1 mm.
                # C'est le seul cas ou le texte peut ne pas tenir, et il ne se
                # produit pas sur les circuits reels -- `numero()` retire la
                # zone, le plus long du classeur fait trois caracteres.
                assert tient or taille == fiches.TAILLE_CASE_MINI_MM, (
                    tailles, longueur, colonnes, taille)

    def test_les_vrais_circuits_du_02_09_tiennent_sans_troncature(self):
        """Les trois circuits du PDF envoyé par Adrien, avec les vrais numéros
        du classeur : « J11 », « V21 », « N2 » — trois caractères au plus."""
        for tailles in ([7, 10, 9, 7, 2, 1], [13, 12, 7, 3, 1], [22, 12, 2]):
            colonnes, taille = fiches.mise_en_page_blocs(
                self._groupes(tailles, 3))
            largeur_case = (
                (fiches.LARGEUR_BLOCS_MM
                 - (colonnes - 1) * fiches.GOUTTIERE_CASE_MM) / colonnes)
            texte = 3 * fiches.CHASSE_CASE * taille
            assert texte <= largeur_case - fiches.HABILLAGE_CASE_MM + 0.01, (
                tailles, colonnes, taille)

    def test_une_case_ne_peut_pas_mordre_sur_sa_voisine(self, connecte_orga,
                                                        competition):
        """La ceinture, quand le plancher a joué : la case tronque chez elle."""
        _grimpeur(competition, 1, "U11 F")
        db.session.commit()
        page = connecte_orga.get("/admin/dossards").data.decode()
        bloc = page.split("  .case {")[1].split("}")[0]
        assert "overflow: hidden" in bloc

    def test_un_numero_plus_long_donne_un_texte_plus_petit(self):
        """C'est la seule variable qu'on ait : le nombre de colonnes est
        imposé par la hauteur."""
        court = fiches.taille_case_mm(9, 2)
        long = fiches.taille_case_mm(9, 4)
        assert long < court

    def test_on_ne_descend_jamais_sous_le_plancher(self):
        """Une fiche pleine vaut mieux qu'un numéro illisible : sous le
        plancher, on préfère laisser la case tronquer proprement — `.case` a
        son `overflow: hidden` — plutôt que d'imprimer du 1 mm."""
        assert fiches.taille_case_mm(12, 12) == fiches.TAILLE_CASE_MINI_MM

    def test_le_couple_choisi_fait_bien_tenir_la_hauteur(self):
        for tailles in ([7, 10, 9, 7, 2, 1], [13, 12, 7, 3, 1], [22, 12, 2],
                        [8] * 6, [43]):
            colonnes, taille = fiches.mise_en_page_blocs(
                self._groupes(tailles))
            if colonnes < fiches.COLONNES_MAXI:
                assert (fiches.hauteur_mm(tailles, colonnes, taille)
                        <= fiches.HAUTEUR_UTILE_MM), (tailles, colonnes, taille)

    def test_c_est_le_plus_gros_texte_qui_tient(self):
        """On parcourt les colonnes du plus petit nombre au plus grand : peu de
        colonnes donne des cases larges et un gros texte. Le premier couple qui
        tient est donc celui qui garde le texte le plus lisible."""
        tailles = [7, 10, 9, 7, 2, 1]
        colonnes, taille = fiches.mise_en_page_blocs(self._groupes(tailles))
        if colonnes > fiches.COLONNES_MINI:
            precedent = colonnes - 1
            assert (fiches.hauteur_mm(tailles, precedent,
                                      fiches.taille_case_mm(precedent, 3))
                    > fiches.HAUTEUR_UTILE_MM)

    def test_une_ligne_coute_moins_cher_quand_le_texte_est_plus_petit(self):
        """La hauteur d'une ligne se DÉDUIT de la taille du texte : sans ça, le
        calcul refuserait des mises en page qui tiennent en vrai."""
        assert fiches.hauteur_ligne_mm(2.0) < fiches.hauteur_ligne_mm(3.0)

    def test_les_deux_constantes_historiques_restent_coherentes(self):
        """Elles sont maintenant DÉDUITES de la formule, à la taille de
        référence. Mesures d'origine : 7,3 et 8,0."""
        assert fiches.HAUTEUR_LIGNE_MM == pytest.approx(7.3, abs=0.1)
        assert fiches.HAUTEUR_LIGNE_SUP_MM == pytest.approx(
            fiches.HAUTEUR_LIGNE_MM + fiches.GOUTTIERE_CASE_MM)

    def test_la_planche_porte_la_taille_de_chaque_fiche(self, connecte_orga,
                                                        competition):
        _grimpeur(competition, 1, "U11 F")
        db.session.commit()
        page = connecte_orga.get("/admin/dossards").data.decode()
        assert "--case:" in page


class TestLesCouleursSImpriment:
    """⚠️ « Les impressions PDF ne sont que en noir et blanc » — Adrien, 02/09.

    Ce n'était ni son Mac ni la bibliothèque de QR. Un navigateur ne pose AUCUN
    aplat de couleur à l'impression tant que « Graphismes d'arrière-plan »
    n'est pas coché dans sa boîte de dialogue — ce que personne ne coche. Les
    pastilles de difficulté, qui sont des `background`, sortaient donc en ronds
    VIDES.
    """

    @pytest.fixture()
    def page(self, connecte_orga, competition):
        _grimpeur(competition, 1, "U11 F")
        db.session.commit()
        return connecte_orga.get("/admin/dossards").data.decode()

    def test_le_gabarit_force_l_impression_des_aplats(self, page):
        assert "-webkit-print-color-adjust: exact" in page, (
            "le prefixe reste necessaire : Safari ne connait que celui-la")
        assert "print-color-adjust: exact" in page

    def test_le_plan_du_mur_reste_SANS_couleur(self, page):
        """Forcer l'impression des aplats ne doit pas avoir fait entrer une
        teinte dans le plan : il s'imprime à l'encre noire sur du papier de
        couleur (spec 028 A9), et son test dédié vit dans
        `test_coherence_console_ecran.py`. Ici on tient la promesse du gabarit."""
        assert "AUCUNE COULEUR" in page
