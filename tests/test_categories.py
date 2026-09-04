"""La règle FFME des catégories d'âge — spec 008, lot 1.

Aucune base, aucun réseau, aucune application : trois fonctions pures et une
table de cas. C'est le test qui prouve quelque chose ; tout le reste de la
spec 008 n'est que de la plomberie autour de lui.

Le cas central est `TestLeTableauPublie` : il rejoue **le tableau de la FFME
pour la saison 2025-2026**, ligne pour ligne. Si un jour ce test tombe, ce n'est
pas le test qu'il faut corriger — c'est que la règle a changé, et il faut aller
lire la nouvelle avant de toucher au code.
"""

from datetime import date

import pytest

from climbcontest import categories


# Le tableau publie pour la saison 2025-2026 : annee de reference 2026.
#
# U9 y figure parce que le tableau le suppose : sans lui, « le plus petit Under
# l'emporte » ferait de U11 la categorie de TOUS les plus jeunes, et sa borne
# basse serait ouverte. C'est correct, mais ce n'est pas ce que le tableau
# publie montre -- et c'est ce tableau qu'on verifie ici.
UNDERS_FFME = [9, 11, 13, 15, 17, 19, 21]

TABLEAU_2025_2026 = {
    "U9": (2018, 2019),
    "U11": (2016, 2017),
    "U13": (2014, 2015),
    "U15": (2012, 2013),
    "U17": (2010, 2011),
    "U19": (2008, 2009),
    "U21": (2006, 2007),
}


class TestLeTableauPublie:
    """Le calcul reproduit le tableau de la fédération, sans exception."""

    def test_le_bareme_entier(self):
        tranches = categories.bareme(2026, UNDERS_FFME)
        obtenu = {t.circuit: (t.annee_min, t.annee_max) for t in tranches}
        # La plus petite categorie est ouverte vers les plus jeunes : on ne
        # compare que sa borne haute, qui est celle que le tableau donne.
        assert obtenu["U9"][0] == TABLEAU_2025_2026["U9"][0]
        assert obtenu["U9"][1] is None
        for nom, attendu in TABLEAU_2025_2026.items():
            if nom == "U9":
                continue
            assert obtenu[nom] == attendu, nom

    @pytest.mark.parametrize("nom,annees", sorted(TABLEAU_2025_2026.items()))
    def test_chaque_annee_du_tableau_tombe_dans_sa_categorie(self, nom, annees):
        for annee in range(annees[0], annees[1] + 1):
            assert categories.circuit(annee, 2026, UNDERS_FFME) == nom


class TestLAnneeDeReference:
    """La saison va du 1er septembre au 31 août. La référence est sa fin."""

    @pytest.mark.parametrize("jour,attendu", [
        (date(2026, 11, 15), 2027),      # la competition visee
        (date(2027, 3, 15), 2027),       # meme saison, autre annee civile
        (date(2026, 9, 1), 2027),        # le jour de la bascule
        (date(2026, 8, 31), 2026),       # la veille : saison precedente
        (date(2026, 1, 1), 2026),
        (date(2026, 12, 31), 2027),
    ])
    def test_reference(self, jour, attendu):
        assert categories.annee_de_reference(jour) == attendu

    def test_novembre_et_mars_donnent_le_meme_bareme(self):
        """Un grimpeur ne change pas de catégorie au milieu de sa saison."""
        assert (categories.bareme(categories.annee_de_reference(date(2026, 11, 15)),
                                  UNDERS_FFME)
                == categories.bareme(categories.annee_de_reference(date(2027, 3, 15)),
                                     UNDERS_FFME))


class TestLePlusPetitUnderLEmporte:
    def test_douze_ans_est_u13_jamais_u15(self):
        assert categories.circuit(2015, 2027, [11, 13, 15]) == "U13"

    def test_dix_ans_est_u11(self):
        assert categories.circuit(2017, 2027, [11, 13, 15]) == "U11"

    def test_une_categorie_sautee_elargit_la_suivante(self):
        """Sans U13, un grimpeur de 12 ans est U15. C'est la règle, pas un bug."""
        assert categories.circuit(2015, 2027, [11, 15]) == "U15"
        assert categories.circuit(2014, 2027, [11, 15]) == "U15"

    def test_la_plus_petite_categorie_prend_les_plus_jeunes(self):
        """Un enfant de 6 ans, dans une édition qui commence à U11, est U11.

        C'est là qu'il grimpera : le mettre en attente n'apprendrait rien à
        personne.
        """
        assert categories.circuit(2021, 2027, [11, 13, 15]) == "U11"


class TestCeQuiNaPasDeCategorie:
    def test_un_adulte(self):
        assert categories.circuit(1990, 2027, UNDERS_FFME) is None

    def test_une_edition_sans_aucun_under(self):
        assert categories.circuit(2015, 2027, []) is None
        assert categories.bareme(2027, []) == []

    def test_une_annee_trop_ancienne(self):
        assert categories.circuit(1015, 2027, UNDERS_FFME) is None

    def test_une_annee_dans_le_futur(self):
        """2916 pour 2016 : l'âge est négatif, donc « inférieur à 11 ».

        Sans la garde, la faute de frappe la plus banale rangerait quelqu'un en
        U11 au lieu de se signaler.
        """
        assert categories.circuit(2916, 2027, UNDERS_FFME) is None

    @pytest.mark.parametrize("valeur", [None, "", "  ", "abc", "20a5"])
    def test_une_annee_illisible(self, valeur):
        assert categories.circuit(valeur, 2027, UNDERS_FFME) is None

    def test_une_annee_en_texte_passe(self):
        """Un champ HelloAsso rend du texte : « 2015 » doit marcher."""
        assert categories.circuit(" 2015 ", 2027, [11, 13, 15]) == "U13"


class TestLireLesUnders:
    @pytest.mark.parametrize("nom,attendu", [
        ("U13 F", 13), ("U13 H", 13), ("U13", 13), ("u9", 9),
        ("U 15 F", 15), ("U21", 21),
        ("Senior", None), ("Adulte", None), ("Veteran 1", None),
        ("", None), (None, None), ("Universel", None),
    ])
    def test_under(self, nom, attendu):
        assert categories.under(nom) == attendu

    def test_unders_distincts_et_croissants(self):
        assert categories.unders_de(
            ["U13 F", "U13 H", "U11 F", "Senior", "U11 H", None]) == [11, 13]

    def test_aucune_categorie(self):
        assert categories.unders_de([]) == []
        assert categories.unders_de(None) == []


class TestLeSensInverse:
    """Choisir une catégorie dit quelles années on attend — décision D8."""

    def test_une_categorie_du_milieu(self):
        assert categories.annees_attendues("U13 F", 2027, [11, 13, 15]) == (2015, 2016)

    def test_la_plus_petite_est_ouverte(self):
        assert categories.annees_attendues("U11 F", 2027, [11, 13, 15]) == (2017, None)

    def test_une_categorie_hors_bareme(self):
        assert categories.annees_attendues("Senior", 2027, [11, 13]) is None

    def test_une_categorie_absente_de_l_edition(self):
        assert categories.annees_attendues("U17 F", 2027, [11, 13]) is None

    def test_aller_retour(self):
        """Ce que le sens inverse annonce, le sens direct le confirme."""
        for tranche in categories.bareme(2027, UNDERS_FFME):
            debut, fin = categories.annees_attendues(
                tranche.circuit, 2027, UNDERS_FFME)
            assert categories.circuit(debut, 2027, UNDERS_FFME) == tranche.circuit
            if fin is not None:
                assert categories.circuit(fin, 2027, UNDERS_FFME) == tranche.circuit


class TestLeBaremeEstContinu:
    def test_aucun_trou_entre_deux_tranches(self):
        """Chaque année entre la plus jeune et la plus âgée a une catégorie."""
        tranches = categories.bareme(2027, UNDERS_FFME)
        plus_agee = min(t.annee_min for t in tranches)
        plus_jeune = 2027
        for annee in range(plus_agee, plus_jeune + 1):
            assert categories.circuit(annee, 2027, UNDERS_FFME) is not None, annee

    def test_aucun_recouvrement(self):
        """Une année n'appartient qu'à une tranche."""
        tranches = categories.bareme(2027, UNDERS_FFME)
        for annee in range(2005, 2028):
            portee = [t for t in tranches
                      if t.annee_min <= annee
                      and (t.annee_max is None or annee <= t.annee_max)]
            assert len(portee) <= 1, (annee, [t.circuit for t in portee])
