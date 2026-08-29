"""Le classement par club (spec 010).

Regle tranchee par Adrien le 29/08 : SOMME des scores de tous les grimpeurs du
club. Il a choisi en connaissance de cause -- un club qui vient a quinze passera
presque toujours devant un club qui vient a quatre. C'est ce que la regle mesure.

La question que sa decision ne tranchait pas : un grimpeur a DEUX scores, celui
de sa categorie et celui du scratch. Les additionner le compterait deux fois.
C'est la CATEGORIE qui compte -- son resultat officiel, celui du podium.
"""
import pytest

from climbcontest import classement_service
from climbcontest.classement import (
    BlocCalcul, ParticipantCalcul, calculer_clubs, calculer_tout,
)
from climbcontest.contest import enregistrer_reussite


def p(id_, cat="U11 F", club="Les Lezards"):
    return ParticipantCalcul(id=id_, dossard=id_, categorie=cat, club=club)


def b(id_, circuits=("U11",)):
    return BlocCalcul(id=id_, tag=f"B{id_}", couleur="Jaune", circuits=frozenset(circuits))


BLOCS = {i: b(i) for i in range(1, 7)}


def clubs_de(participants, reussites, blocs=None):
    tous = calculer_tout(participants, blocs or BLOCS, reussites)
    return calculer_clubs(tous, participants)


class TestLaRegle:

    def test_le_score_d_un_club_est_la_somme_des_siens(self):
        # Deux grimpeurs du meme club, seuls sur leurs blocs : 1000 chacun.
        c = clubs_de([p(1), p(2)], {1: {1}, 2: {2}})
        assert c.lignes[0].score == 2000

    def test_un_club_nombreux_passe_devant_un_club_fort(self):
        """La consequence assumee de la regle -- rendue explicite ici, pour que
        quiconque changerait l'agregation un jour voie ce qu'il change."""
        participants = [
            p(1, club="Petit"), p(2, club="Gros"), p(3, club="Gros"), p(4, club="Gros"),
        ]
        # Le grimpeur du petit club reussit DEUX blocs ; ceux du gros un seul
        # chacun, mais des blocs DIFFERENTS -- donc chacun vaut 1000.
        c = clubs_de(participants, {1: {1, 2}, 2: {3}, 3: {4}, 4: {5}})

        premier = c.lignes[0]
        assert premier.libelle == "Gros", "3 x 1000 > 2 x 1000"
        assert premier.score == 3000

    def test_MAIS_s_agglutiner_sur_les_memes_blocs_ne_rapporte_presque_rien(self):
        """La nuance qui tempere la regle, et qu'on ne voit pas au premier abord.

        Un bloc vaut 1000 divise par le nombre de gens du groupe qui l'ont
        reussi. Trois grimpeurs du meme club qui font tous le meme bloc facile
        gagnent 333 chacun -- moins, a eux trois, qu'un seul grimpeur ayant fait
        deux blocs que personne d'autre n'a tenus.

        Autrement dit : « le gros club gagne » est vrai a niveau egal, pas dans
        l'absolu. Le bareme protege deja en partie de l'effet redoute.
        """
        participants = [
            p(1, club="Petit"), p(2, club="Gros"), p(3, club="Gros"), p(4, club="Gros"),
        ]
        c = clubs_de(participants, {1: {1, 2}, 2: {3}, 3: {3}, 4: {3}})

        par_nom = {l.libelle: l for l in c.lignes}
        assert par_nom["Petit"].score == 2000
        assert par_nom["Gros"].score == 999, "3 x 333, et non 3 x 1000"
        assert c.lignes[0].libelle == "Petit"

    def test_le_nombre_de_grimpeurs_est_affiche(self):
        """Sans lui, le classement serait illisible vu la regle retenue."""
        c = clubs_de([p(1), p(2), p(3, club="Autre")], {1: {1}})
        par_nom = {l.libelle: l for l in c.lignes}
        assert par_nom["Les Lezards"].membres == 2
        assert par_nom["Autre"].membres == 1

    def test_le_total_de_blocs_est_cumule(self):
        c = clubs_de([p(1), p(2)], {1: {1, 2}, 2: {3}})
        assert c.lignes[0].blocs_reussis == 3


class TestChaqueGrimpeurNeCompteQuUneFois:
    """La question que la decision ne tranchait pas."""

    def test_le_scratch_n_est_pas_additionne(self):
        """Un grimpeur figure dans « U11 F » ET dans « U11 ». Additionner les
        deux le compterait deux fois, et doublerait le score de son club."""
        participants = [p(1, cat="U11 F"), p(2, cat="U11 H")]
        tous = calculer_tout(participants, BLOCS, {1: {1}, 2: {2}})

        assert "U11" in tous, "le scratch existe bien"
        assert tous["U11"].type == "circuit"

        c = calculer_clubs(tous, participants)
        # Chacun est seul sur son bloc dans SA CATEGORIE : 1000 chacun.
        # Avec le scratch en plus, on obtiendrait davantage.
        assert c.lignes[0].score == 2000

    def test_seuls_les_classements_de_categorie_sont_lus(self):
        participants = [p(1, cat="U11 F")]
        tous = calculer_tout(participants, BLOCS, {1: {1}})
        categorie_seule = {k: v for k, v in tous.items() if v.type == "categorie"}

        avec_tout = calculer_clubs(tous, participants)
        avec_categories = calculer_clubs(categorie_seule, participants)

        assert avec_tout.lignes[0].score == avec_categories.lignes[0].score


class TestCasLimites:

    def test_un_grimpeur_sans_club_ne_cree_pas_de_club_fantome(self):
        c = clubs_de([p(1, club=None), p(2, club="Reel")], {1: {1}, 2: {2}})
        assert [l.libelle for l in c.lignes] == ["Reel"]

    def test_un_club_vide_non_plus(self):
        c = clubs_de([p(1, club="   "), p(2, club="Reel")], {2: {2}})
        assert [l.libelle for l in c.lignes] == ["Reel"]

    def test_un_grimpeur_sans_categorie_ne_compte_pour_aucun_club(self):
        """Il n'apparait deja dans aucun classement : il ne doit pas apparaitre
        ici par une porte derobee."""
        sans = ParticipantCalcul(id=9, dossard=9, categorie=None, club="Les Lezards")
        c = clubs_de([p(1), sans], {1: {1}, 9: {2}})
        assert c.lignes[0].membres == 1

    def test_aucun_club_du_tout_rend_None(self):
        """Un classement vide n'apprend rien : autant ne pas l'afficher."""
        assert clubs_de([p(1, club=None)], {1: {1}}) is None

    def test_deux_orthographes_font_deux_clubs(self):
        """On n'invente pas de rapprochement. Le jour ou ca genera, ce sera une
        decision -- pas une heuristique posee en douce ici."""
        c = clubs_de([p(1, club="La Grimpe"), p(2, club="la grimpe")], {1: {1}, 2: {2}})
        assert len(c.lignes) == 2

    def test_tout_le_monde_a_zero_ne_plante_pas(self):
        c = clubs_de([p(1), p(2, club="Autre")], {})
        assert all(l.score == 0 for l in c.lignes)

    def test_un_seul_club(self):
        c = clubs_de([p(1), p(2)], {1: {1}})
        assert len(c.lignes) == 1


class TestRangs:

    def test_les_ex_aequo_partagent_le_rang(self):
        participants = [p(1, club="A"), p(2, club="B"), p(3, club="C")]
        # A et B a egalite, C derriere.
        c = clubs_de(participants, {1: {1}, 2: {1}, 3: {2}})
        rangs = {l.libelle: l.rang for l in c.lignes}
        assert rangs["A"] == rangs["B"]

    def test_le_suivant_saute_les_places(self):
        participants = [p(1, club="A"), p(2, club="B"), p(3, club="C")]
        c = clubs_de(participants, {1: {1}, 2: {1}, 3: set()})
        rangs = sorted(l.rang for l in c.lignes)
        assert rangs == [1, 1, 3]

    def test_l_ordre_est_stable_a_score_egal(self):
        """Sinon le classement changerait a chaque rafraichissement de la page."""
        participants = [p(1, club="Zebre"), p(2, club="Alpha")]
        premier = [l.libelle for l in clubs_de(participants, {}).lignes]
        second = [l.libelle for l in clubs_de(participants, {}).lignes]
        assert premier == second == ["Alpha", "Zebre"]


class TestParLApi:

    def setup_method(self):
        classement_service.invalider()

    def test_le_classement_club_apparait(self, client, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        classement_service.invalider()
        d = client.get("/api/public/classement").get_json()
        groupes = {c["groupe"]: c for c in d["classements"]}
        assert "Clubs" in groupes
        assert groupes["Clubs"]["type"] == "club"

    def test_les_lignes_portent_le_nom_du_club_et_le_nombre(self, client, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        classement_service.invalider()
        d = client.get("/api/public/classement?groupe=Clubs").get_json()
        ligne = d["classements"][0]["lignes"][0]
        assert ligne["nom"] == "Les Lezards"
        assert ligne["membres"] == 1
        assert ligne["dossard"] is None

    def test_il_figure_dans_la_liste_des_groupes(self, client, jeu):
        noms = {g["nom"] for g in client.get("/api/public/groupes").get_json()["groupes"]}
        assert "Clubs" in noms

    def test_les_autres_classements_sont_intacts(self, client, jeu):
        """Le classement club ne doit rien changer a ce qui existait."""
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        classement_service.invalider()
        d = client.get("/api/public/classement?groupe=U11 F").get_json()
        assert d["classements"][0]["lignes"][0]["score"] == 1000

    def test_novembre_2025_reste_a_196_sur_196(self, app):
        """Le garde-fou qui compte : le classement club ne doit pas avoir
        effleure le moteur."""
        import json
        from pathlib import Path
        fixture = Path(__file__).resolve().parent.parent / "fixtures" / "contest-nov2025.json"
        d = json.loads(fixture.read_text(encoding="utf-8"))
        participants = [ParticipantCalcul(id=x["bib"], dossard=x["bib"],
                                          categorie=x["category"])
                        for x in d["climbers"]]
        blocs = {x["number"]: BlocCalcul(id=x["number"], tag=x["tag"], couleur=x["color"],
                                        circuits=frozenset(x["circuits"]))
                 for x in d["blocs"]}
        reussites = {}
        for t in d["tops"]:
            reussites.setdefault(t["bib"], set()).add(t["bloc"])

        obtenus = calculer_tout(participants, blocs, reussites)
        attendus = {**d["expected"]["by_category"], **d["expected"]["by_circuit"]}
        ecarts = 0
        for groupe, lignes in attendus.items():
            par_dossard = {l.dossard: l for l in obtenus[groupe].lignes}
            for a in lignes:
                o = par_dossard.get(a["bib"])
                if o is None or (o.score, o.rang) != (a["score"], a["rank"]):
                    ecarts += 1
        assert ecarts == 0
