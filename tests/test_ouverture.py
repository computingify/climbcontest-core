"""La préparation des ouvreurs — le calcul, sans client HTTP (spec 044)."""
import pytest

from climbcontest import ouverture, sans_classeur
from climbcontest.classement import COULEURS
from climbcontest.extensions import db
from climbcontest.models import (Bloc, BlocCircuit, Circuit, EN_COURS,
                                 PREPARATION, Participant, Success)


@pytest.fixture()
def prete(app, competition):
    """Une édition en préparation, classeur débranché : la saisie est ouverte."""
    competition.statut = PREPARATION
    db.session.add(competition)
    for nom in ("U11", "U13"):
        db.session.add(Circuit(competition_id=competition.id, nom=nom))
    db.session.commit()
    sans_classeur.basculer(True, par="test")
    return competition


def _voie(comp, zone, couleur=None, circuits=()):
    bloc = ouverture.creer(comp, zone)
    if couleur or circuits:
        ouverture.modifier(comp, bloc, couleur=couleur, circuits=list(circuits))
    return bloc


# --- Les initiales ----------------------------------------------------------

class TestLesInitiales:
    def test_elles_couvrent_exactement_les_six_couleurs(self):
        assert set(ouverture.INITIALES) == set(COULEURS)

    def test_elles_sont_deux_a_deux_distinctes(self):
        """Sinon deux couleurs fabriqueraient le meme tag, et `uq_bloc_tag`
        transformerait une saisie ordinaire en erreur 500."""
        valeurs = list(ouverture.INITIALES.values())
        assert len(set(valeurs)) == len(valeurs)


# --- Les garde-fous ---------------------------------------------------------

class TestCeQuiEstInterdit:
    def test_sans_le_mode_sans_classeur_rien_ne_s_ecrit(self, app, competition):
        competition.statut = PREPARATION
        db.session.commit()
        with pytest.raises(ouverture.ErreurOuverture) as e:
            ouverture.creer(competition, "J")
        assert "consultation" in e.value.message

    def test_une_competition_en_cours_est_en_lecture_seule(self, prete):
        prete.statut = EN_COURS
        db.session.commit()
        with pytest.raises(ouverture.ErreurOuverture) as e:
            ouverture.creer(prete, "J")
        assert "preparation" in e.value.message

    def test_une_voie_avec_reussite_ne_change_pas_de_couleur(self, prete):
        bloc = _voie(prete, "J", "Vert", ["U11"])
        p = Participant(competition_id=prete.id, nom="Test", dossard=1)
        db.session.add(p)
        db.session.flush()
        db.session.add(Success(participant_id=p.id, bloc_id=bloc.id))
        db.session.commit()
        with pytest.raises(ouverture.ErreurOuverture) as e:
            ouverture.modifier(prete, bloc, couleur="Bleu")
        assert "1 reussite" in e.value.message

    def test_une_voie_avec_reussite_ne_se_supprime_pas(self, prete):
        bloc = _voie(prete, "J", "Vert", ["U11"])
        p = Participant(competition_id=prete.id, nom="Test", dossard=1)
        db.session.add(p)
        db.session.flush()
        db.session.add(Success(participant_id=p.id, bloc_id=bloc.id))
        db.session.commit()
        with pytest.raises(ouverture.ErreurOuverture):
            ouverture.supprimer(prete, bloc)

    def test_une_couleur_hors_des_six_est_refusee(self, prete):
        bloc = _voie(prete, "J")
        with pytest.raises(ouverture.ErreurOuverture) as e:
            ouverture.modifier(prete, bloc, couleur="Turquoise")
        assert e.value.code == 400


# --- L'attribution du nom ---------------------------------------------------

class TestLeNomDUneVoie:
    def test_une_voie_nue_n_a_pas_de_nom(self, prete):
        bloc = _voie(prete, "J")
        assert ouverture.nom_de(bloc) is None
        assert bloc.tag.startswith("J?")           # le tag de reserve

    def test_poser_une_couleur_attribue_le_premier_rang_libre(self, prete):
        for _ in range(6):
            _voie(prete, "A", "Vert")
        bloc = _voie(prete, "J")
        ouverture.modifier(prete, bloc, couleur="Vert")
        assert ouverture.nom_de(bloc) == "V7"
        assert bloc.tag == "JV7"

    def test_apres_une_suppression_le_rang_ne_se_reutilise_pas(self, prete):
        """⚠️ `max + 1` et non `count + 1` : sinon le rang libere serait rendu
        une seconde fois, et `uq_bloc_tag` ferait echouer la saisie."""
        voies = [_voie(prete, "A", "Vert") for _ in range(6)]
        ouverture.supprimer(prete, voies[3])       # la V4 s'en va
        bloc = _voie(prete, "J")
        ouverture.modifier(prete, bloc, couleur="Vert")
        assert ouverture.nom_de(bloc) == "V7"

    def test_changer_de_couleur_change_le_nom_et_le_tag(self, prete):
        bloc = _voie(prete, "J", "Vert")
        assert bloc.tag == "JV1"
        ouverture.modifier(prete, bloc, couleur="Bleu")
        assert bloc.tag == "JB1"
        assert ouverture.nom_de(bloc) == "B1"

    def test_retirer_la_couleur_rend_la_voie_a_completer(self, prete):
        bloc = _voie(prete, "J", "Vert", ["U11"])
        ouverture.modifier(prete, bloc, couleur=None)
        assert bloc.numero_couleur is None
        assert ouverture.nom_de(bloc) is None
        assert bloc.tag.startswith("J?")

    def test_une_prise_bicolore_se_range_dans_un_ordre_CANONIQUE(self, prete):
        """⚠️ Sans ordre canonique, la meme prise physique s'ecrit
        « Bleu/Blanc » chez l'un et « Blanc/Bleu » chez l'autre : deux chaines
        pour un objet, et tout ce qui compare voit deux couleurs."""
        bloc = _voie(prete, "J", "Vert")
        ouverture.modifier(prete, bloc, couleur_prises=["Bleu", "Blanc"])
        assert bloc.couleur_prises == "Blanc/Bleu"
        ouverture.modifier(prete, bloc, couleur_prises=["Blanc", "Bleu"])
        assert bloc.couleur_prises == "Blanc/Bleu"

    def test_une_couleur_inconnue_survit_et_passe_apres(self, prete):
        """« Mint » existe dans un vrai classeur, une seule fois. Une couleur
        ecrite une fois est une couleur qu'on doit pouvoir relire."""
        bloc = _voie(prete, "J", "Vert")
        ouverture.modifier(prete, bloc, couleur_prises=["Turquoise", "Mint"])
        assert bloc.couleur_prises == "Turquoise/Mint"
        ouverture.modifier(prete, bloc, couleur_prises=["Zebre", "Blanc"])
        assert bloc.couleur_prises == "Blanc/Zebre"

    def test_trois_couleurs_sont_refusees(self, prete):
        bloc = _voie(prete, "J", "Vert")
        with pytest.raises(ouverture.ErreurOuverture) as e:
            ouverture.modifier(prete, bloc,
                               couleur_prises=["Blanc", "Bleu", "Rouge"])
        assert e.value.code == 400

    def test_une_couleur_repetee_ne_compte_qu_une_fois(self, prete):
        bloc = _voie(prete, "J", "Vert")
        ouverture.modifier(prete, bloc, couleur_prises=["Bleu", "Bleu"])
        assert bloc.couleur_prises == "Bleu"

    def test_une_chaine_du_classeur_se_relit_telle_quelle(self, prete):
        """L'import pose une CHAINE ; l'ecran envoie une LISTE. Les deux
        ressortent rangees de la meme facon."""
        bloc = _voie(prete, "J", "Vert")
        ouverture.modifier(prete, bloc, couleur_prises="Bleu/Blanc")
        assert bloc.couleur_prises == "Blanc/Bleu"
        assert ouverture.prises_de(bloc) == ["Blanc", "Bleu"]

    def test_une_couleur_ne_peut_pas_porter_le_separateur(self, prete):
        """Sinon « Bleu/Blanc » saisi comme UNE couleur en fabriquerait deux au
        rechargement, sans que rien ne le dise."""
        bloc = _voie(prete, "J", "Vert")
        with pytest.raises(ouverture.ErreurOuverture):
            ouverture.modifier(prete, bloc, couleur_prises=["Bleu/Blanc x"])

    def test_l_inventaire_rend_la_chaine_ET_la_liste(self, prete):
        bloc = _voie(prete, "J", "Vert", ["U11"])
        ouverture.modifier(prete, bloc, couleur_prises=["Blanc", "Bleu"])
        voie = ouverture.inventaire(prete)["zones"]["J"][0]
        assert voie["couleur_prises"] == "Blanc/Bleu"
        assert voie["couleurs_prises"] == ["Blanc", "Bleu"]

    def test_les_prises_se_vident(self, prete):
        """`...` veut dire « ne touche pas », `None` veut dire « vide »."""
        bloc = _voie(prete, "J", "Vert")
        ouverture.modifier(prete, bloc, couleur_prises="Fluo")
        assert bloc.couleur_prises == "Fluo"
        ouverture.modifier(prete, bloc, couleur_prises=None)
        assert bloc.couleur_prises is None


# --- La renumérotation ------------------------------------------------------

class TestLaRenumerotation:
    def _salle(self, comp):
        """Trois vertes posées dans le désordre des zones, plus deux bleues."""
        _voie(comp, "N", "Vert")                   # V1, zone N
        _voie(comp, "A", "Vert")                   # V2, zone A
        _voie(comp, "G", "Vert")                   # V3, zone G
        _voie(comp, "K", "Bleu")                   # B1, zone K
        _voie(comp, "C", "Bleu")                   # B2, zone C

    def test_par_couleur_les_zones_sont_parcourues_de_A_a_Z(self, prete):
        self._salle(prete)
        ouverture.renumeroter(prete)
        par_tag = {b.zone: b.tag for b in Bloc.query.all()}
        assert par_tag["A"] == "AV1"
        assert par_tag["G"] == "GV2"
        assert par_tag["N"] == "NV3"
        assert par_tag["C"] == "CB1"
        assert par_tag["K"] == "KB2"

    def test_relancee_elle_ne_change_plus_rien(self, prete):
        """Une action qui donne un resultat different a chaque appel est une
        action qu'on n'ose pas lancer la veille d'une competition."""
        self._salle(prete)
        ouverture.renumeroter(prete)
        assert ouverture.renumeroter(prete) == []

    def test_l_apercu_n_ecrit_rien(self, prete):
        self._salle(prete)
        avant = sorted(b.tag for b in Bloc.query.all())
        changements = ouverture.renumeroter(prete, apercu=True)
        assert changements
        assert sorted(b.tag for b in Bloc.query.all()) == avant

    def test_une_permutation_circulaire_passe(self, prete):
        """⚠️ Le piege de toute renumerotation sous contrainte d'unicite :
        « AV2 » prend la place de « AV1 » qui n'est pas encore liberee. Sans
        l'ecriture en deux passes, `uq_bloc_tag` claque en cours de route."""
        a = _voie(prete, "A", "Vert")              # AV1
        b = _voie(prete, "A", "Vert")              # AV2
        # On inverse leur rang a la main : la renumerotation doit les remettre
        # dans l'ordre, ce qui echange leurs deux tags.
        a.numero_couleur, a.tag = 2, "AV2x"
        b.numero_couleur, b.tag = 1, "AV1x"
        db.session.commit()
        ouverture.renumeroter(prete)
        assert {x.tag for x in Bloc.query.all()} == {"AV1", "AV2"}

    def test_les_voies_sans_couleur_ne_bougent_pas(self, prete):
        nue = _voie(prete, "J")
        avant = nue.tag
        _voie(prete, "A", "Vert")
        ouverture.renumeroter(prete)
        assert nue.tag == avant

    def test_refusee_des_qu_une_reussite_existe_ailleurs(self, prete):
        """Le geste est GLOBAL, il se juge globalement."""
        touchee = _voie(prete, "A", "Vert")
        autre = _voie(prete, "N", "Bleu")
        p = Participant(competition_id=prete.id, nom="Test", dossard=1)
        db.session.add(p)
        db.session.flush()
        db.session.add(Success(participant_id=p.id, bloc_id=autre.id))
        db.session.commit()
        with pytest.raises(ouverture.ErreurOuverture) as e:
            ouverture.renumeroter(prete)
        assert "1 reussite" in e.value.message
        assert touchee.tag == "AV1"

    def test_le_numero_d_import_ne_bouge_jamais(self, prete):
        """`numero` est la ligne du bloc dans l'onglet `Import`. La
        renumerotation ne touche que le rang de couleur."""
        self._salle(prete)
        avant = {b.id: b.numero for b in Bloc.query.all()}
        ouverture.renumeroter(prete)
        assert {b.id: b.numero for b in Bloc.query.all()} == avant


# --- L'inventaire -----------------------------------------------------------

class TestLInventaire:
    def test_une_zone_compte_ses_completes_sur_ses_declarees(self, prete):
        _voie(prete, "J", "Vert", ["U11"])
        _voie(prete, "J", "Bleu", ["U13"])
        _voie(prete, "J")                          # sans couleur
        inv = ouverture.inventaire(prete)
        voies = inv["zones"]["J"]
        assert len(voies) == 3
        assert sum(1 for v in voies if v["complete"]) == 2

    def test_une_voie_avec_couleur_mais_sans_categorie_est_incomplete(self, prete):
        _voie(prete, "J", "Vert")
        assert ouverture.inventaire(prete)["zones"]["J"][0]["complete"] is False

    def test_une_zone_sans_voie_n_apparait_pas(self, prete):
        _voie(prete, "J", "Vert", ["U11"])
        assert "K" not in ouverture.inventaire(prete)["zones"]

    def test_la_repartition_par_couleur(self, prete):
        _voie(prete, "J", "Vert")
        _voie(prete, "K", "Vert")
        _voie(prete, "L", "Noir")
        totaux = ouverture.inventaire(prete)["totaux"]
        assert totaux["par_couleur"]["Vert"] == 2
        assert totaux["par_couleur"]["Noir"] == 1
        assert totaux["par_couleur"]["Jaune"] == 0

    def test_les_voies_verrouillees_par_une_reussite_sont_annoncees(self, prete):
        bloc = _voie(prete, "J", "Vert", ["U11"])
        p = Participant(competition_id=prete.id, nom="Test", dossard=1)
        db.session.add(p)
        db.session.flush()
        db.session.add(Success(participant_id=p.id, bloc_id=bloc.id))
        db.session.commit()
        assert ouverture.inventaire(prete)["zones"]["J"][0]["reussites"] == 1

    def test_le_budget_de_requetes_ne_depend_pas_du_nombre_de_voies(self, prete):
        """Cinq requetes, que la salle porte cinq voies ou soixante.

        Ce qui compte n'est pas le chiffre mais sa CONSTANCE : c'est lui qui
        dit qu'aucune boucle ne s'est mise a interroger la base par voie.
        """
        from sqlalchemy import event

        def mesurer():
            prete.id                       # sortir la competition du cache expire
            comptees = []
            moteur = db.session.get_bind()

            def compter(*args, **kwargs):
                comptees.append(1)

            event.listen(moteur, "before_cursor_execute", compter)
            try:
                ouverture.inventaire(prete)
            finally:
                event.remove(moteur, "before_cursor_execute", compter)
            return len(comptees)

        for _ in range(5):
            _voie(prete, "A", "Vert", ["U11"])
        petite = mesurer()

        for zone in "BCDEFGHIJKL":
            for _ in range(5):
                _voie(prete, zone, "Vert", ["U11"])
        grande = mesurer()

        assert petite == grande == 5, f"{petite} puis {grande} requetes"


# --- Les catégories ---------------------------------------------------------

class TestLesCategories:
    def test_une_categorie_se_cree_et_devient_cochable(self, prete):
        ouverture.creer_circuit(prete, "U15")
        bloc = _voie(prete, "J", "Vert")
        ouverture.modifier(prete, bloc, circuits=["U15"])
        assert ouverture.inventaire(prete)["zones"]["J"][0]["circuits"] == ["U15"]

    def test_une_categorie_qui_porte_une_voie_ne_se_supprime_pas(self, prete):
        _voie(prete, "J", "Vert", ["U11"])
        u11 = Circuit.query.filter_by(nom="U11").first()
        with pytest.raises(ouverture.ErreurOuverture) as e:
            ouverture.supprimer_circuit(prete, u11)
        assert "1 voie" in e.value.message

    def test_une_categorie_vide_se_supprime(self, prete):
        u13 = Circuit.query.filter_by(nom="U13").first()
        ouverture.supprimer_circuit(prete, u13)
        assert Circuit.query.filter_by(nom="U13").first() is None

    def test_une_categorie_inconnue_est_refusee(self, prete):
        bloc = _voie(prete, "J")
        with pytest.raises(ouverture.ErreurOuverture) as e:
            ouverture.modifier(prete, bloc, circuits=["U42"])
        assert e.value.code == 400


# --- Le catalogue -----------------------------------------------------------

class TestLeCatalogue:
    def test_chaque_ecriture_previent_les_telephones(self, prete):
        avant = prete.catalogue_version
        bloc = ouverture.creer(prete, "J")
        assert prete.catalogue_version == avant + 1
        ouverture.modifier(prete, bloc, couleur="Vert")
        assert prete.catalogue_version == avant + 2
        ouverture.supprimer(prete, bloc)
        assert prete.catalogue_version == avant + 3

    def test_la_renumerotation_ne_previent_qu_une_fois(self, prete):
        for zone in "ABC":
            _voie(prete, zone, "Vert")
        avant = prete.catalogue_version
        ouverture.renumeroter(prete)
        assert prete.catalogue_version == avant + 1
