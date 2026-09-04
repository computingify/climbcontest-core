"""Le barème appliqué aux inscrits — spec 008, lot 2.

`test_categories.py` prouve que la **règle** est juste. Ici on vérifie ce que le
bouton « Appliquer à tous les inscrits » fait et, surtout, **ce qu'il ne fait
pas** : quatre familles de participants doivent traverser l'opération intactes,
et chacune pour une raison qu'on peut dire à voix haute.

La compétition des fixtures est datée du 15/11/2026 : saison 2026-2027, année de
référence **2027**. Donc U13 = 2015-2016.
"""

import pytest

from climbcontest import bareme
from climbcontest.contest import ErreurMetier
from climbcontest.extensions import db
from climbcontest.models import Participant


def poser(comp, nom, categorie, annee=None, dossard=None, forcee=None):
    p = Participant(competition_id=comp.id, nom=nom, categorie=categorie,
                    annee_naissance=annee, dossard=dossard,
                    categorie_forcee=forcee)
    db.session.add(p)
    db.session.commit()
    return p


class TestLaReference:
    def test_la_competition_de_novembre_2026_est_en_2027(self, app, competition):
        assert bareme.reference(competition) == 2027

    def test_la_saison_est_affichee(self, app, competition):
        assert bareme.apercu(competition)["saison"] == "2026-2027"


class TestLesUnders:
    def test_ils_viennent_des_participants(self, app, competition):
        poser(competition, "A", "U13 F")
        poser(competition, "B", "U11 H")
        poser(competition, "C", "Senior H")
        assert bareme.unders(competition) == [11, 13]

    def test_une_edition_vide_n_invente_rien(self, app, competition):
        assert bareme.unders(competition) == []


class TestCeQuiChange:
    def test_une_categorie_perimee_est_recalculee(self, app, competition):
        """Le classeur disait U15, l'année dit U13. Le barème tranche."""
        poser(competition, "Brunel", "U15 F", annee=2015, dossard=47)
        poser(competition, "Autre", "U13 F", annee=2016)      # pour que U13 existe
        rapport = bareme.apercu(competition)
        assert [c["nom"] for c in rapport["changements"]] == ["Brunel"]
        assert rapport["changements"][0]["avant"] == "U15 F"
        assert rapport["changements"][0]["apres"] == "U13 F"

    def test_le_genre_est_conserve(self, app, competition):
        poser(competition, "Garcon", "U15 H", annee=2015)
        poser(competition, "Fille", "U13 F", annee=2016)
        rapport = bareme.apercu(competition)
        assert rapport["changements"][0]["apres"] == "U13 H"

    def test_appliquer_ecrit_vraiment(self, app, competition):
        p = poser(competition, "Brunel", "U15 F", annee=2015)
        poser(competition, "Autre", "U13 F", annee=2016)
        bareme.appliquer(competition, par="orga")
        db.session.refresh(p)
        assert p.categorie == "U13 F"

    def test_appliquer_deux_fois_ne_change_rien_la_seconde(self, app, competition):
        poser(competition, "Brunel", "U15 F", annee=2015)
        poser(competition, "Autre", "U13 F", annee=2016)
        assert len(bareme.appliquer(competition)["changements"]) == 1
        assert bareme.appliquer(competition)["changements"] == []

    def test_le_catalogue_est_incremente(self, app, competition):
        """Les téléphones doivent revoir la liste : la catégorie décide du
        circuit affiché au juge."""
        poser(competition, "Brunel", "U15 F", annee=2015)
        poser(competition, "Autre", "U13 F", annee=2016)
        avant = competition.catalogue_version
        bareme.appliquer(competition)
        db.session.refresh(competition)
        assert competition.catalogue_version > avant


class TestLApercuNEcritRien:
    def test_aucune_categorie_ne_bouge(self, app, competition):
        p = poser(competition, "Brunel", "U15 F", annee=2015)
        poser(competition, "Autre", "U13 F", annee=2016)
        bareme.apercu(competition)
        db.session.refresh(p)
        assert p.categorie == "U15 F"

    def test_l_apercu_annonce_exactement_ce_qui_sera_ecrit(self, app, competition):
        poser(competition, "Un", "U15 F", annee=2015)
        poser(competition, "Deux", "U15 H", annee=2016)
        poser(competition, "Trois", "U13 F", annee=2016)
        annonce = bareme.apercu(competition)["changements"]
        fait = bareme.appliquer(competition)["changements"]
        assert annonce == fait


class TestCeQuiNEstJamaisTouche:
    """Quatre familles traversent l'opération intactes."""

    def test_sans_annee_de_naissance(self, app, competition):
        p = poser(competition, "Sansannee", "U15 F")
        poser(competition, "Autre", "U13 F", annee=2016)
        rapport = bareme.appliquer(competition)
        db.session.refresh(p)
        assert p.categorie == "U15 F"
        assert rapport["ignores"]["sans_annee"] == 1

    def test_sans_categorie_de_depart(self, app, competition):
        """Le genre est inconnu : « U13 » à côté de « U13 F » fragmenterait
        le classement."""
        p = poser(competition, "Sanscat", None, annee=2015)
        poser(competition, "Autre", "U13 F", annee=2016)
        rapport = bareme.appliquer(competition)
        db.session.refresh(p)
        assert p.categorie is None
        assert rapport["ignores"]["sans_categorie"] == 1

    def test_hors_bareme(self, app, competition):
        p = poser(competition, "Adulte", "Senior H", annee=1990)
        poser(competition, "Autre", "U13 F", annee=2016)
        rapport = bareme.appliquer(competition)
        db.session.refresh(p)
        assert p.categorie == "Senior H"
        assert rapport["ignores"]["hors_bareme"] == 1

    def test_une_annee_aberrante_ne_range_personne(self, app, competition):
        """2916 pour 2016 : l'âge est négatif. Sans la garde de
        `categories.circuit`, ce participant partirait dans la plus petite
        catégorie."""
        p = poser(competition, "Fautedefrappe", "U15 F", annee=2916)
        poser(competition, "Autre", "U13 F", annee=2016)
        rapport = bareme.appliquer(competition)
        db.session.refresh(p)
        assert p.categorie == "U15 F"
        assert rapport["ignores"]["hors_bareme"] == 1

    def test_une_categorie_corrigee_a_la_main(self, app, competition):
        """Décision D10 : quelqu'un connaissait le cas particulier."""
        p = poser(competition, "Range", "U15 F", annee=2015, forcee=True)
        poser(competition, "Autre", "U13 F", annee=2016)
        rapport = bareme.appliquer(competition)
        db.session.refresh(p)
        assert p.categorie == "U15 F"
        assert rapport["ignores"]["corrigees_a_la_main"] == 1

    def test_le_forcage_passe_outre(self, app, competition):
        p = poser(competition, "Range", "U15 F", annee=2015, forcee=True)
        poser(competition, "Autre", "U13 F", annee=2016)
        bareme.appliquer(competition, forcer=True)
        db.session.refresh(p)
        assert p.categorie == "U13 F"

    def test_le_forcage_ne_leve_pas_la_marque(self, app, competition):
        """Sinon la fois suivante défairait le travail sans plus rien pour
        prévenir."""
        p = poser(competition, "Range", "U15 F", annee=2015, forcee=True)
        poser(competition, "Autre", "U13 F", annee=2016)
        bareme.appliquer(competition, forcer=True)
        db.session.refresh(p)
        assert p.categorie_forcee is True


class TestLeBaremeAffiche:
    def test_une_ligne_par_under(self, app, competition):
        poser(competition, "A", "U11 F", annee=2018)
        poser(competition, "B", "U13 F", annee=2015)
        lignes = bareme.tranches(competition)
        assert [l["circuit"] for l in lignes] == ["U11", "U13"]

    def test_les_annees_sont_celles_de_la_saison(self, app, competition):
        poser(competition, "A", "U11 F")
        poser(competition, "B", "U13 F")
        par_circuit = {l["circuit"]: l for l in bareme.tranches(competition)}
        assert (par_circuit["U13"]["annee_min"], par_circuit["U13"]["annee_max"]) \
            == (2015, 2016)

    def test_la_plus_petite_est_ouverte_vers_les_jeunes(self, app, competition):
        poser(competition, "A", "U11 F")
        poser(competition, "B", "U13 F")
        par_circuit = {l["circuit"]: l for l in bareme.tranches(competition)}
        assert par_circuit["U11"]["annee_max"] is None

    def test_les_categories_hors_bareme_figurent_quand_meme(self, app, competition):
        """Les taire donnerait l'impression qu'elles n'existent pas, alors
        qu'elles portent des grimpeurs."""
        poser(competition, "A", "U13 F")
        poser(competition, "B", "Senior H")
        lignes = {l["circuit"]: l for l in bareme.tranches(competition)}
        assert lignes["Senior H"]["hors_bareme"] is True
        assert lignes["Senior H"]["inscrits"] == 1

    def test_les_inscrits_sont_comptes(self, app, competition):
        poser(competition, "A", "U13 F")
        poser(competition, "B", "U13 H")
        poser(competition, "C", "U13 F")
        lignes = {l["circuit"]: l for l in bareme.tranches(competition)}
        assert lignes["U13"]["inscrits"] == 3
        assert lignes["U13"]["categories"] == ["U13 F", "U13 H"]


class TestReglerALaMain:
    def test_changer_la_categorie_pose_la_marque(self, app, competition):
        p = poser(competition, "Brunel", "U13 F", annee=2015)
        bareme.regler_a_la_main(p, "U15 F")
        db.session.commit()
        assert p.categorie == "U15 F" and p.categorie_forcee is True

    def test_reecrire_la_meme_ne_pose_rien(self, app, competition):
        p = poser(competition, "Brunel", "U13 F", annee=2015)
        bareme.regler_a_la_main(p, "U13 F")
        db.session.commit()
        assert not p.categorie_forcee

    def test_le_formatage_s_applique(self, app, competition):
        p = poser(competition, "Brunel", "U13 F", annee=2015)
        bareme.regler_a_la_main(p, "u15f")
        db.session.commit()
        assert p.categorie == "U15 F"


class TestVerifierAnnee:
    @pytest.mark.parametrize("brut,attendu", [
        ("2015", 2015), (2015, 2015), (" 2015 ", 2015), ("", None), (None, None),
    ])
    def test_ce_qui_passe(self, brut, attendu):
        assert bareme.verifier_annee(brut) == attendu

    @pytest.mark.parametrize("brut", ["abc", "20a5", "1015", "2916", "-4"])
    def test_ce_qui_est_refuse(self, brut):
        with pytest.raises(ErreurMetier):
            bareme.verifier_annee(brut)


class TestCeQueLeBaremeNePeutPasRanger:
    """Le verdict d'une ligne, à l'écran des Catégories.

    ⚠️ Le contrôle de cohérence annoncé dans la maquette — recouvrement, trou,
    circuit vide — a disparu avec la saisie : un barème **dérivé** de
    l'ensemble des Under partitionne les années par construction, et un trou y
    est inexprimable. Ce qui reste vrai et utile, c'est ce qu'il ne peut pas
    ranger.
    """

    def test_personne_a_ranger(self, app, competition):
        poser(competition, "A", "U13 F", annee=2015)
        assert bareme.hors_de_portee(competition) == {
            "sans_annee": 0, "hors_bareme": 0}

    def test_sans_annee(self, app, competition):
        poser(competition, "A", "U13 F", annee=2015)
        poser(competition, "B", "U13 F")
        assert bareme.hors_de_portee(competition)["sans_annee"] == 1

    def test_hors_bareme(self, app, competition):
        poser(competition, "A", "U13 F", annee=2015)
        poser(competition, "B", "Senior H", annee=1990)
        assert bareme.hors_de_portee(competition)["hors_bareme"] == 1

    def test_le_bareme_derive_ne_peut_pas_avoir_de_trou(self, app, competition):
        """La preuve par la construction : chaque année entre la plus âgée et
        la plus jeune tombe dans exactement une tranche."""
        poser(competition, "A", "U11 F", annee=2018)
        poser(competition, "B", "U15 H", annee=2013)
        tranches = bareme.tranches(competition)
        couvertes = [t for t in tranches if not t["hors_bareme"]]
        plus_agee = min(t["annee_min"] for t in couvertes)
        for annee in range(plus_agee, 2028):
            portee = [t for t in couvertes
                      if t["annee_min"] <= annee
                      and (t["annee_max"] is None or annee <= t["annee_max"])]
            assert len(portee) == 1, (annee, [t["circuit"] for t in portee])
