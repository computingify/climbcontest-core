"""L'inventaire des circuits et son contrôle de cohérence (spec 019).

Ce que ces tests protègent tient en une phrase : **les trois anomalies sont
silencieuses**. Un bloc rattaché à aucun circuit ne compte pour personne, un
circuit sans bloc rend un classement vide, une catégorie dont le circuit
n'existe pas fait compter chaque réussite pour zéro — et rien, aujourd'hui, ne
le dit avant la remise des prix.

Le cas n'est pas théorique : le correctif du 01/09 (colonnes de circuit figées à
trois au lieu de cinq) a laissé 37 blocs orphelins et un circuit entier absent
sur le classeur de novembre 2025.
"""
import pytest

from climbcontest import comptes
from climbcontest.circuits import inventaire
from climbcontest.extensions import db
from climbcontest.models import Bloc, BlocCircuit, Circuit, Participant

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, jeu):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


class TestInventaire:
    """Le jeu de test : U11 (ZJ6, ZJ7), U13 (ZJ6, DV21), 3 participants."""

    def test_un_bloc_par_ligne_avec_ses_circuits(self, app, jeu):
        inv = inventaire(jeu["competition"])
        par_tag = {b["tag"]: b for b in inv["blocs"]}
        assert set(par_tag) == {"ZJ6", "ZJ7", "DV21"}
        assert par_tag["ZJ6"]["circuits"] == ["U11", "U13"]
        assert par_tag["DV21"]["circuits"] == ["U13"]

    def test_les_blocs_sortent_dans_l_ordre_du_classeur(self, app, jeu):
        """`numero` est la ligne dans l'onglet Import : c'est l'ordre du mur."""
        inv = inventaire(jeu["competition"])
        assert [b["numero"] for b in inv["blocs"]] == [1, 2, 3]

    def test_les_deux_couleurs_sont_distinctes(self, app, jeu):
        bloc = Bloc.query.filter_by(tag="ZJ6").one()
        bloc.couleur_prises = "Fluo"
        db.session.commit()
        inv = inventaire(jeu["competition"])
        zj6 = next(b for b in inv["blocs"] if b["tag"] == "ZJ6")
        assert zj6["couleur"] == "Jaune"          # difficulté
        assert zj6["couleur_prises"] == "Fluo"    # prises

    def test_les_categories_viennent_des_participants(self, app, jeu):
        """Le jeu porte « U11 F », « U11 H » et « U13 H » — pas « U13 F »."""
        inv = inventaire(jeu["competition"])
        par_tag = {b["tag"]: b for b in inv["blocs"]}
        # ZJ6 est dans les deux circuits : l'union des deux.
        assert par_tag["ZJ6"]["categories"] == ["U11 F", "U11 H", "U13 H"]
        assert par_tag["DV21"]["categories"] == ["U13 H"]

    def test_on_n_invente_pas_une_categorie_que_personne_ne_porte(self, app, jeu):
        """« U13 » n'engendre pas « U13 F » : personne ne l'est.

        Afficher une catégorie vide ferait chercher des grimpeurs qui
        n'existent pas.
        """
        inv = inventaire(jeu["competition"])
        toutes = {c for b in inv["blocs"] for c in b["categories"]}
        assert "U13 F" not in toutes

    def test_les_compteurs_par_circuit(self, app, jeu):
        inv = inventaire(jeu["competition"])
        par_nom = {c["nom"]: c for c in inv["circuits"]}
        assert par_nom["U11"]["blocs"] == 2          # ZJ6, ZJ7
        assert par_nom["U13"]["blocs"] == 2          # ZJ6, DV21
        # Dupont (U11 F) et Absent (U11 H) sont sur U11, Martin (U13 H) sur U13.
        assert par_nom["U11"]["participants"] == 2
        assert par_nom["U13"]["participants"] == 1


class TestAnomalies:

    def test_rien_a_signaler_quand_tout_va_bien(self, app, jeu):
        """Le bloc de contrôle ne doit pas s'afficher sans raison."""
        a = inventaire(jeu["competition"])["anomalies"]
        assert a == {"blocs_sans_circuit": [], "circuits_sans_bloc": [],
                     "categories_sans_circuit": []}

    def test_un_bloc_sans_circuit_est_nomme(self, app, jeu):
        """Le cas de novembre 2025 : 37 blocs rattachés à rien."""
        orphelin = Bloc(competition_id=jeu["competition"].id, tag="MX9",
                        numero=9, zone="M", couleur="Noir")
        db.session.add(orphelin)
        db.session.commit()
        a = inventaire(jeu["competition"])["anomalies"]
        assert a["blocs_sans_circuit"] == ["MX9"]

    def test_un_circuit_sans_bloc_est_nomme(self, app, jeu):
        """Son classement sortira vide sur « aucun bloc n'appartient »."""
        db.session.add(Circuit(competition_id=jeu["competition"].id, nom="U17"))
        db.session.commit()
        a = inventaire(jeu["competition"])["anomalies"]
        assert a["circuits_sans_bloc"] == ["U17"]

    def test_une_categorie_sans_circuit_est_nommee(self, app, jeu):
        """Le plus coûteux des trois : ces grimpeurs scannent normalement et
        chacune de leurs réussites compte pour zéro."""
        db.session.add(Participant(
            competition_id=jeu["competition"].id, nom="Vieux", prenom="Jean",
            categorie="U19 F", dossard=9))
        db.session.commit()
        a = inventaire(jeu["competition"])["anomalies"]
        assert a["categories_sans_circuit"] == ["U19 F"]

    def test_un_participant_sans_categorie_n_est_pas_une_anomalie(self, app, jeu):
        """Le classeur en produit (risque R5) et l'import les garde exprès."""
        db.session.add(Participant(
            competition_id=jeu["competition"].id, nom="Sans", prenom="Categorie",
            categorie=None, dossard=8))
        db.session.commit()
        a = inventaire(jeu["competition"])["anomalies"]
        assert a["categories_sans_circuit"] == []

    def test_une_competition_vide_ne_signale_rien(self, app, competition):
        """Avant l'import, tout est vide — ce n'est pas une anomalie."""
        inv = inventaire(competition)
        assert inv["blocs"] == [] and inv["circuits"] == []
        assert all(not v for v in inv["anomalies"].values())


class TestRoute:

    def test_un_organisateur_lit_l_inventaire(self, connecte, jeu):
        r = connecte.get("/admin/circuits")
        assert r.status_code == 200
        d = r.get_json()
        assert d["success"] is True
        assert len(d["blocs"]) == 3
        assert [c["nom"] for c in d["circuits"]] == ["U11", "U13"]

    def test_sans_session_c_est_refuse(self, client, app, jeu):
        # Sans `SECRET_KEY`, toute la console repond 503 : ce n'est pas ce
        # qu'on mesure ici. On la pose, puis on n'ouvre PAS de session.
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/circuits").status_code == 401

    def test_sans_competition_active(self, connecte, app):
        from climbcontest.models import Competition
        for c in Competition.query.all():
            c.active = False
        db.session.commit()
        r = connecte.get("/admin/circuits")
        assert r.status_code == 409

    def test_les_anomalies_sont_dans_la_reponse(self, connecte, jeu):
        db.session.add(Bloc(competition_id=jeu["competition"].id, tag="MX9",
                            numero=9, zone="M"))
        db.session.commit()
        d = connecte.get("/admin/circuits").get_json()
        assert d["anomalies"]["blocs_sans_circuit"] == ["MX9"]
