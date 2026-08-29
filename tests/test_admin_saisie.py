"""Saisie manuelle d'une reussite (spec 005, IT3).

Un QR illisible, un telephone a plat, un juge qui a oublie d'envoyer. Sans
cette route, la reussite est perdue pour de bon -- et personne ne s'en apercoit
avant le depouillement, quand il est trop tard pour demander au grimpeur.
"""
import pytest

from climbcontest import classement_service, comptes
from climbcontest.contest import enregistrer_reussite
from climbcontest.extensions import db
from climbcontest.models import SOURCE_MANUEL, SOURCE_SCAN, Success

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, jeu):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


class TestSaisie:

    def test_une_reussite_est_enregistree(self, connecte, jeu):
        r = connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        assert r.status_code == 201
        assert r.get_json()["nouvelle"] is True
        assert Success.query.count() == 1

    def test_elle_porte_la_source_manuelle(self, connecte, jeu):
        connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        assert Success.query.one().source == SOURCE_MANUEL

    def test_elle_porte_le_nom_de_qui_l_a_saisie(self, connecte, jeu):
        """Le jour ou un score est conteste, savoir qu'une reussite a ete
        ajoutee a la main par untel est la seule chose qui permette de
        trancher."""
        connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        assert Success.query.one().saisie_par == "orga"

    def test_un_scan_ne_porte_aucun_saisisseur(self, connecte, jeu):
        """Le juge n'est pas identifie, et il n'y a aucune raison qu'il le
        devienne : ce qu'on trace, c'est l'intervention humaine sur les
        donnees."""
        connecte.post("/api/v2/contest/success", json={"bib": "1", "bloc": "ZJ6"})
        s = Success.query.one()
        assert s.source == SOURCE_SCAN
        assert s.saisie_par is None

    def test_saisir_deux_fois_ne_cree_qu_une_reussite(self, connecte, jeu):
        connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        r = connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        assert r.status_code == 201
        assert r.get_json()["nouvelle"] is False
        assert Success.query.count() == 1

    def test_completer_un_scan_ne_le_duplique_pas(self, connecte, jeu):
        """Le cas reel : un organisateur ressaisit par precaution ce qu'un juge
        avait deja envoye."""
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        assert Success.query.count() == 1

    def test_un_dossard_inconnu_est_refuse(self, connecte, jeu):
        r = connecte.post("/admin/reussites", json={"bib": "999", "bloc": "ZJ6"})
        assert r.status_code == 400
        assert Success.query.count() == 0

    def test_un_bloc_inconnu_est_refuse(self, connecte, jeu):
        assert connecte.post("/admin/reussites",
                             json={"bib": "1", "bloc": "PASUNBLOC"}).status_code == 400

    def test_un_corps_qui_n_est_pas_un_objet_donne_400(self, connecte, jeu):
        r = connecte.post("/admin/reussites", data="[1,2]",
                          content_type="application/json")
        assert r.status_code == 400


class TestElleCompteCommeUnScan:
    """Si le classement l'ignorait, le grimpeur serait penalise pour un
    probleme d'impression -- et personne ne le verrait, puisque la reussite EST
    en base."""

    def setup_method(self):
        classement_service.invalider()

    def test_elle_rapporte_des_points(self, connecte, jeu):
        connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        classement_service.invalider()
        tous, _ = classement_service.classements(jeu["competition"])
        ligne = next(l for l in tous["U11 F"].lignes if l.dossard == 1)
        assert ligne.score > 0

    def test_elle_apparait_sur_la_page_publique(self, connecte, jeu):
        connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        classement_service.invalider()
        d = connecte.get("/api/public/classement?groupe=U11 F").get_json()
        assert d["classements"][0]["lignes"][0]["score"] > 0

    def test_elle_part_au_classeur_comme_les_autres(self, connecte, jeu):
        """Le miroir ne fait aucune difference selon l'origine."""
        connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        assert Success.query.filter(Success.sheet_synced_at.is_(None)).count() == 1


class TestSuppression:

    def test_une_reussite_est_supprimee(self, connecte, jeu):
        r = connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        identifiant = r.get_json()["reussite"]["id"]

        s = connecte.delete(f"/admin/reussites/{identifiant}")

        assert s.status_code == 200
        assert Success.query.count() == 0

    def test_la_suppression_laisse_une_trace(self, connecte, jeu, caplog):
        """Un score qui change entre deux consultations serait autrement
        inexplicable."""
        import logging
        identifiant = connecte.post("/admin/reussites",
                                    json={"bib": "1", "bloc": "ZJ6"}
                                    ).get_json()["reussite"]["id"]
        with caplog.at_level(logging.WARNING):
            connecte.delete(f"/admin/reussites/{identifiant}")

        assert "SUPPRESSION" in caplog.text
        assert "orga" in caplog.text, "qui"
        assert "ZJ6" in caplog.text, "quoi"

    def test_la_reponse_dit_ce_qui_a_ete_supprime(self, connecte, jeu):
        identifiant = connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"}
                                    ).get_json()["reussite"]["id"]
        d = connecte.delete(f"/admin/reussites/{identifiant}").get_json()
        assert d["supprimee"]["bloc"] == "ZJ6"
        assert "Dupont" in d["supprimee"]["participant"]

    def test_supprimer_ce_qui_n_existe_pas_donne_404(self, connecte, jeu):
        r = connecte.delete("/admin/reussites/99999")
        assert r.status_code == 404
        assert "inconnue" in r.get_json()["message"].lower()

    def test_on_peut_supprimer_un_scan_aussi(self, connecte, jeu):
        """Un juge peut se tromper de grimpeur : la correction doit etre
        possible quelle que soit l'origine."""
        s, _ = enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        assert connecte.delete(f"/admin/reussites/{s.id}").status_code == 200

    def test_le_classement_en_tient_compte(self, connecte, jeu):
        identifiant = connecte.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"}
                                    ).get_json()["reussite"]["id"]
        connecte.delete(f"/admin/reussites/{identifiant}")
        classement_service.invalider()
        tous, _ = classement_service.classements(jeu["competition"])
        assert next(l for l in tous["U11 F"].lignes if l.dossard == 1).score == 0


class TestAccesRefuse:

    @pytest.mark.parametrize("methode,chemin", [
        ("post", "/admin/reussites"),
        ("delete", "/admin/reussites/1"),
    ])
    def test_sans_session_c_est_refuse(self, client, app, jeu, methode, chemin):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert getattr(client, methode)(chemin, json={}).status_code == 401

    def test_et_rien_n_est_ecrit(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        client.post("/admin/reussites", json={"bib": "1", "bloc": "ZJ6"})
        assert Success.query.count() == 0

    def test_et_rien_n_est_supprime(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        s, _ = enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        client.delete(f"/admin/reussites/{s.id}")
        assert Success.query.count() == 1
