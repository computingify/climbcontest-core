"""L'ecran d'ouverture et le mode sans classeur, cotes routes (specs 044, 046).

Le coeur de ce fichier est la MATRICE DES ROLES. `ouvreur` est le premier role
restreint du depot : les deux autres s'empilent, celui-ci n'ouvre qu'un ecran.
Ce qui le tient, ce n'est pas l'affichage de la console -- c'est `exige_role`,
et c'est ici qu'on le verifie.
"""
import pytest

from climbcontest import comptes, ouverture, sans_classeur
from climbcontest.cycle import regler_sources
from climbcontest.extensions import db
from climbcontest.models import (Bloc, Circuit, PREPARATION, SOURCE_HELLOASSO,
                                 Participant, Success)

MDP = "un-mot-de-passe-assez-long"


def _connecter(client, app, identifiant, roles):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer(identifiant, MDP, roles)
    r = client.post("/admin/connexion",
                    json={"identifiant": identifiant, "mot_de_passe": MDP})
    assert r.status_code == 200, r.get_json()
    return client


@pytest.fixture()
def prete(app, competition):
    competition.statut = PREPARATION
    db.session.add(competition)
    db.session.add(Circuit(competition_id=competition.id, nom="U11"))
    db.session.commit()
    sans_classeur.basculer(True, par="test")
    return competition


@pytest.fixture()
def ouvreur(client, app, prete):
    return _connecter(client, app, "marc", [comptes.OUVREUR])


# --- La matrice des roles ---------------------------------------------------

class TestLaMatriceDesRoles:
    """Un ouvreur n'ouvre QUE son ecran. Un organisateur ouvre aussi le sien."""

    FERMEES = ["/admin/participants", "/admin/comptes", "/admin/circuits",
               "/admin/dossards", "/admin/classeur"]

    def test_l_ouvreur_entre_dans_son_ecran(self, ouvreur):
        assert ouvreur.get("/admin/ouverture").status_code == 200

    @pytest.mark.parametrize("route", FERMEES)
    def test_l_ouvreur_est_refuse_partout_ailleurs(self, ouvreur, route):
        assert ouvreur.get(route).status_code == 403, route

    def test_l_ouvreur_ne_redessine_pas_le_plan(self, ouvreur):
        """Decision du 04/09. Le plan part sur cent vingt dossards imprimes."""
        assert ouvreur.post("/admin/plan", json={"vue": [100, 100],
                                                 "murs": []}).status_code == 403

    def test_l_ouvreur_change_son_mot_de_passe(self, ouvreur):
        """`exige_role()` sans argument : c'est voulu pour cette route-la."""
        r = ouvreur.post("/admin/mon-mot-de-passe",
                         json={"actuel": MDP, "nouveau": "un-autre-assez-long"})
        assert r.status_code == 200, r.get_json()

    def test_l_ouvreur_se_reconnait(self, ouvreur):
        r = ouvreur.get("/admin/moi")
        assert r.status_code == 200
        assert r.get_json()["roles"] == ["ouvreur"]

    def test_l_identite_dit_si_le_classeur_est_debranche(self, ouvreur):
        """C'est ce fait qui retire l'entree « Classeur » du tiroir, et il doit
        etre lisible par un role qui n'a pas acces au reglage."""
        assert ouvreur.get("/admin/moi").get_json()["mode_sans_classeur"] is True

    def test_l_organisateur_entre_AUSSI_dans_l_ecran(self, client, app, prete):
        """⚠️ Le test qui attrape l'oubli de le nommer dans `exige_role` :
        le decorateur n'accorde rien par anciennete."""
        orga = _connecter(client, app, "orga", [comptes.ORGANISATEUR])
        assert orga.get("/admin/ouverture").status_code == 200

    def test_l_admin_entre_partout(self, client, app, prete):
        chef = _connecter(client, app, "chef", [comptes.ADMIN])
        assert chef.get("/admin/ouverture").status_code == 200
        assert chef.get("/admin/mode-sans-classeur").status_code == 200

    def test_sans_session_tout_est_401(self, client, app, prete):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/ouverture").status_code == 401

    def test_l_ouvreur_ne_bascule_pas_le_mode(self, ouvreur):
        """C'est une decision d'administrateur, pas un geste de preparation."""
        assert ouvreur.get("/admin/mode-sans-classeur").status_code == 403
        assert ouvreur.post("/admin/mode-sans-classeur",
                            json={"actif": False}).status_code == 403

    def test_l_organisateur_ne_bascule_pas_le_mode(self, client, app, prete):
        orga = _connecter(client, app, "orga", [comptes.ORGANISATEUR])
        assert orga.post("/admin/mode-sans-classeur",
                         json={"actif": False}).status_code == 403


# --- La saisie --------------------------------------------------------------

class TestLaSaisie:
    def test_une_voie_se_cree_puis_se_complete(self, ouvreur, prete):
        r = ouvreur.post("/admin/ouverture/voies", json={"zone": "J"})
        assert r.status_code == 201, r.get_json()
        identifiant = r.get_json()["id"]

        r = ouvreur.post(f"/admin/ouverture/voies/{identifiant}",
                         json={"couleur": "Vert", "couleur_prises": "Fluo",
                               "circuits": ["U11"]})
        assert r.status_code == 200, r.get_json()
        voie = r.get_json()["zones"]["J"][0]
        assert (voie["nom"], voie["tag"], voie["complete"]) == ("V1", "JV1", True)

    def test_une_cle_absente_ne_touche_a_rien(self, ouvreur, prete):
        """Absente et nulle ne disent pas la meme chose."""
        identifiant = ouvreur.post("/admin/ouverture/voies",
                                   json={"zone": "J"}).get_json()["id"]
        ouvreur.post(f"/admin/ouverture/voies/{identifiant}",
                     json={"couleur": "Vert", "couleur_prises": "Fluo"})
        r = ouvreur.post(f"/admin/ouverture/voies/{identifiant}",
                         json={"circuits": ["U11"]})
        assert r.get_json()["zones"]["J"][0]["couleur_prises"] == "Fluo"

    def test_une_cle_nulle_vide_le_champ(self, ouvreur, prete):
        identifiant = ouvreur.post("/admin/ouverture/voies",
                                   json={"zone": "J"}).get_json()["id"]
        ouvreur.post(f"/admin/ouverture/voies/{identifiant}",
                     json={"couleur_prises": "Fluo"})
        r = ouvreur.post(f"/admin/ouverture/voies/{identifiant}",
                         json={"couleur_prises": None})
        assert r.get_json()["zones"]["J"][0]["couleur_prises"] is None

    def test_une_voie_d_une_autre_edition_est_introuvable(self, ouvreur, prete, app):
        from datetime import date
        from climbcontest.models import Competition
        autre = Competition(nom="Autre", date=date(2025, 11, 1))
        db.session.add(autre)
        db.session.flush()
        bloc = Bloc(competition_id=autre.id, tag="XX1", numero=1, zone="X")
        db.session.add(bloc)
        db.session.commit()
        assert ouvreur.delete(
            f"/admin/ouverture/voies/{bloc.id}").status_code == 404

    def test_l_ecran_porte_le_plan_de_la_salle(self, ouvreur, prete):
        """Le MEME document que la page de resultats, meme estampille."""
        from climbcontest.suivi import FORMAT_PLAN
        plan = ouvreur.get("/admin/ouverture").get_json()["plan"]
        assert plan["format"] == FORMAT_PLAN
        assert plan["murs"]

    def test_l_apercu_de_renumerotation_n_ecrit_rien(self, ouvreur, prete):
        for zone in ("N", "A"):
            identifiant = ouvreur.post("/admin/ouverture/voies",
                                       json={"zone": zone}).get_json()["id"]
            ouvreur.post(f"/admin/ouverture/voies/{identifiant}",
                         json={"couleur": "Vert"})
        avant = sorted(b.tag for b in Bloc.query.all())
        r = ouvreur.post("/admin/ouverture/renumeroter?apercu=1")
        assert r.status_code == 200
        assert r.get_json()["combien"] == 2
        assert sorted(b.tag for b in Bloc.query.all()) == avant

    def test_en_lecture_seule_l_ecran_s_ouvre_mais_refuse(self, ouvreur, prete):
        sans_classeur.basculer(False, par="test")
        assert ouvreur.get("/admin/ouverture").status_code == 200
        r = ouvreur.post("/admin/ouverture/voies", json={"zone": "J"})
        assert r.status_code == 409
        assert "consultation" in r.get_json()["message"]


# --- Le mode sans classeur --------------------------------------------------

class TestLeModeSansClasseur:
    @pytest.fixture()
    def chef(self, client, app, competition):
        competition.statut = PREPARATION
        db.session.add(competition)
        db.session.commit()
        return _connecter(client, app, "chef", [comptes.ADMIN])

    def _tout_est_pret(self, comp):
        regler_sources(comp, [SOURCE_HELLOASSO])
        db.session.add(Circuit(competition_id=comp.id, nom="U11"))
        db.session.flush()
        circuit = Circuit.query.filter_by(competition_id=comp.id).first()
        bloc = Bloc(competition_id=comp.id, tag="JV1", numero=1, zone="J",
                    couleur="Vert")
        db.session.add(bloc)
        db.session.flush()
        from climbcontest.models import BlocCircuit
        db.session.add(BlocCircuit(bloc_id=bloc.id, circuit_id=circuit.id))
        db.session.commit()

    def test_par_defaut_il_est_eteint(self, chef):
        assert chef.get("/admin/mode-sans-classeur").get_json()["actif"] is False

    def test_sans_source_d_inscrits_la_bascule_est_refusee(self, chef, competition):
        self._tout_est_pret(competition)
        regler_sources(competition, ["classeur"])
        r = chef.post("/admin/mode-sans-classeur", json={"actif": True})
        assert r.status_code == 409
        assert [x["code"] for x in r.get_json()["refus"]] == ["B1"]

    def test_sans_voie_la_bascule_est_refusee(self, chef, competition):
        regler_sources(competition, [SOURCE_HELLOASSO])
        r = chef.post("/admin/mode-sans-classeur", json={"actif": True})
        assert r.status_code == 409
        assert [x["code"] for x in r.get_json()["refus"]] == ["B2"]

    def test_quand_tout_est_pret_elle_passe(self, chef, competition):
        self._tout_est_pret(competition)
        r = chef.post("/admin/mode-sans-classeur", json={"actif": True})
        assert r.status_code == 200, r.get_json()
        assert sans_classeur.actif() is True

    def test_la_phrase_sur_la_sauvegarde_s_affiche_toujours(self, chef, competition):
        self._tout_est_pret(competition)
        etat = chef.get("/admin/mode-sans-classeur").get_json()
        assert etat["peut_basculer"] is True
        assert "A4" in [a["code"] for a in etat["avertissements"]]

    def test_rallumer_le_classeur_ne_passe_pas_par_le_controle(self, chef):
        """L'asymetrie est voulue : rallumer ne perd rien."""
        sans_classeur.basculer(True, par="test")
        r = chef.post("/admin/mode-sans-classeur", json={"actif": False})
        assert r.status_code == 200
        assert sans_classeur.actif() is False

    @pytest.mark.parametrize("methode,route", [
        ("post", "/admin/import/sheet"), ("get", "/admin/import/rapport"),
        ("get", "/admin/classeur"), ("post", "/admin/classeur/test"),
        ("post", "/admin/classeur"), ("get", "/admin/classeur/google/consentement"),
        ("get", "/admin/classeur/google/retour"), ("post", "/admin/classeur/jeton"),
    ])
    def test_les_huit_routes_du_classeur_se_ferment(self, chef, methode, route):
        sans_classeur.basculer(True, par="test")
        r = getattr(chef, methode)(route, json={})
        assert r.status_code == 409, route
        assert "debranche" in r.get_json()["message"]

    def test_sans_session_le_refus_reste_401(self, client, app):
        """⚠️ L'ordre des decorateurs est l'ordre des refus : le plus general
        d'abord. Une requete sans session doit recevoir 401, pas 409."""
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        sans_classeur.basculer(True, par="test")
        assert client.get("/admin/classeur").status_code == 401


# --- Le miroir et la sonde --------------------------------------------------

class TestLeMiroirEtLaSonde:
    def test_le_miroir_ne_touche_plus_au_classeur(self, app, competition):
        from climbcontest.sheets.mirror import synchroniser
        sans_classeur.basculer(True, par="test")

        class ClasseurQuiExplose:
            def __getattr__(self, nom):
                raise AssertionError("le miroir a parle au classeur")

        r = synchroniser(classeur=ClasseurQuiExplose())
        assert r["ignoree"] is True
        assert "debranche" in r["erreur"]

    def test_la_sonde_reste_ok_et_nomme_le_mode(self, client, app, competition):
        """⚠️ Le defaut le plus cher de ce lot, et il est silencieux : deux
        compteurs a `null` signifient « base injoignable » et font repondre
        503, ce qui DESINSTALLE la version au deploiement suivant."""
        sans_classeur.basculer(True, par="test")
        r = client.get("/health")
        assert r.status_code == 200
        corps = r.get_json()
        assert corps["status"] == "ok"
        assert corps["mode_sans_classeur"] is True
        assert corps["reussites_en_attente"] is None

    def test_la_sonde_est_inchangee_quand_le_classeur_est_branche(self, client, app,
                                                                 competition):
        r = client.get("/health")
        assert r.get_json()["mode_sans_classeur"] is False
        assert r.get_json()["reussites_en_attente"] == 0
