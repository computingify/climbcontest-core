"""Les deux routes de la cascade de couleurs — spec 025.

Ce qui se joue ici n'est pas « la route rend 200 ». C'est :

- qu'une règle **refusée n'écrive rien** — une compétition à moitié réglée est
  pire qu'une compétition pas réglée ;
- qu'une règle acceptée se voie **immédiatement** dans le classement, sans
  attendre les cinq secondes du cache — sinon on la croit sans effet et on
  recommence ;
- qu'écrire la cascade **n'efface pas les autres options** de l'édition.
"""

import json

import pytest

from climbcontest import classement_service, comptes
from climbcontest.contest import enregistrer_reussite
from climbcontest.extensions import db

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def secret(app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    return app


@pytest.fixture()
def admin(client, secret):
    comptes.creer("chef", MDP, [comptes.ADMIN])
    client.post("/admin/connexion", json={"identifiant": "chef", "mot_de_passe": MDP})
    return client


@pytest.fixture()
def anonyme(client, secret):
    """Un client qui n'a PAS ouvert de session. La cle secrete est posee : sans
    elle la reponse serait 503, et le test ne dirait rien de la fermeture."""
    return client


@pytest.fixture()
def organisateur(client, secret):
    comptes.creer("benevole", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion",
                json={"identifiant": "benevole", "mot_de_passe": MDP})
    return client


REGLE_VERT = {"parmi": ["Vert"], "seuil": 1, "cibles": ["Jaune"]}


class TestAcces:
    def test_lecture_sans_session(self, anonyme, jeu):
        assert anonyme.get("/admin/competition/cascade").status_code == 401

    def test_lecture_par_un_organisateur(self, organisateur, jeu):
        """La carte est ADMIN : ce reglage change le CLASSEMENT, pas son
        affichage."""
        assert organisateur.get("/admin/competition/cascade").status_code == 403

    def test_ecriture_par_un_organisateur(self, organisateur, jeu):
        r = organisateur.post("/admin/competition/cascade",
                              json={"actif": False, "regles": []})
        assert r.status_code == 403


class TestLecture:
    def test_ce_que_la_console_recoit(self, admin, jeu):
        d = admin.get("/admin/competition/cascade").get_json()
        assert d["success"]
        assert d["couleurs"][0] == "Jaune" and d["couleurs"][-1] == "Noir"
        assert d["categories"] == ["U11 F", "U11 H", "U13 H"]
        # De quoi peindre l'apercu : les blocs par couleur ET par circuit, parce
        # qu'une couleur absente d'un circuit ne peut pas etre pleine (D3).
        par_nom = {c["nom"]: c for c in d["circuits"]}
        assert par_nom["U11"]["couleurs"] == {"Jaune": 1, "Vert": 1}
        assert par_nom["U13"]["couleurs"] == {"Jaune": 1, "Bleu": 1}
        assert par_nom["U11"]["blocs"] == 2
        assert d["cascade"]["actif"] is False
        assert len(d["regle_du_classeur"]["regles"]) == 4


    def test_un_bloc_sans_couleur_est_compte_a_part(self, admin, jeu):
        """Il compte au classement, mais aucune cascade ne le credite : le taire
        ferait mentir le denominateur de l'apercu."""
        from climbcontest.models import Bloc, BlocCircuit
        muet = Bloc(competition_id=jeu["competition"].id, tag="ZZ1", numero=42,
                    couleur=None)
        db.session.add(muet)
        db.session.flush()
        db.session.add(BlocCircuit(bloc_id=muet.id,
                                   circuit_id=jeu["circuits"][0].id))
        db.session.commit()
        d = admin.get("/admin/competition/cascade").get_json()
        u11 = {c["nom"]: c for c in d["circuits"]}["U11"]
        assert u11["sans_couleur"] == 1
        assert u11["blocs"] == 3

    def test_une_couleur_en_minuscules_est_rapprochee(self, admin, jeu):
        """Le classeur ecrit « rouge » aussi bien que « Rouge » ; l'apercu doit
        compter comme le moteur compte."""
        from climbcontest.models import Bloc, BlocCircuit
        autre = Bloc(competition_id=jeu["competition"].id, tag="ZZ2", numero=43,
                     couleur="  jaune ")
        db.session.add(autre)
        db.session.flush()
        db.session.add(BlocCircuit(bloc_id=autre.id,
                                   circuit_id=jeu["circuits"][0].id))
        db.session.commit()
        d = admin.get("/admin/competition/cascade").get_json()
        u11 = {c["nom"]: c for c in d["circuits"]}["U11"]
        assert u11["couleurs"]["Jaune"] == 2

    def test_un_circuit_sans_bloc_colore_reste_dans_l_apercu(self, admin, jeu):
        """Sinon il disparait du menu et se regle a l'aveugle."""
        from climbcontest.models import Circuit
        db.session.add(Circuit(competition_id=jeu["competition"].id, nom="U17"))
        db.session.commit()
        d = admin.get("/admin/competition/cascade").get_json()
        par_nom = {c["nom"]: c for c in d["circuits"]}
        assert par_nom["U17"] == {"nom": "U17", "couleurs": {}, "blocs": 0,
                                 "sans_couleur": 0}

    def test_les_blocs_d_une_autre_edition_ne_comptent_pas(self, admin, jeu):
        """L'apercu doit voir ce que voit le moteur, qui borne ses blocs a la
        competition. Un lien croise donnerait deux comptes differents."""
        from climbcontest.models import Bloc, BlocCircuit, Competition
        from datetime import date
        autre = Competition(nom="Autre", date=date(2025, 11, 1))
        db.session.add(autre)
        db.session.flush()
        intrus = Bloc(competition_id=autre.id, tag="XX9", numero=99,
                      couleur="Noir")
        db.session.add(intrus)
        db.session.flush()
        db.session.add(BlocCircuit(bloc_id=intrus.id,
                                   circuit_id=jeu["circuits"][0].id))
        db.session.commit()
        d = admin.get("/admin/competition/cascade").get_json()
        par_nom = {c["nom"]: c for c in d["circuits"]}
        assert "Noir" not in par_nom["U11"]["couleurs"]


class TestEcriture:
    def test_regle_enregistree(self, admin, jeu):
        r = admin.post("/admin/competition/cascade", json={
            "actif": True, "regles": [REGLE_VERT], "categories_eteintes": []})
        assert r.status_code == 200
        d = r.get_json()
        assert d["cascade"]["regles"] == [REGLE_VERT]
        assert d["avertissements"] == []
        options = json.loads(jeu["competition"].options)
        assert options["cascade"]["actif"] is True

    def test_les_autres_options_survivent(self, admin, jeu):
        """`ecrire_options` fusionne : ecrire la cascade ne doit pas faire
        disparaitre les classements masques."""
        jeu["competition"].options = json.dumps({"groupes_masques": ["U11 H"]})
        db.session.commit()
        admin.post("/admin/competition/cascade", json={
            "actif": True, "regles": [REGLE_VERT]})
        options = json.loads(jeu["competition"].options)
        assert options["groupes_masques"] == ["U11 H"]
        assert options["cascade"]["actif"] is True

    def test_regle_qui_remonte_refusee_sans_rien_ecrire(self, admin, jeu):
        avant = jeu["competition"].options
        r = admin.post("/admin/competition/cascade", json={
            "actif": True,
            "regles": [{"parmi": ["Jaune"], "seuil": 1, "cibles": ["Rouge"]}]})
        assert r.status_code == 400
        assert "ne remonte pas" in r.get_json()["message"]
        assert jeu["competition"].options == avant

    def test_regle_morte_avertit_sans_bloquer(self, admin, jeu):
        d = admin.get("/admin/competition/cascade").get_json()
        regles = d["regle_du_classeur"]["regles"] + [
            {"parmi": ["Rouge", "Noir"], "seuil": 2, "cibles": ["Jaune"]}]
        r = admin.post("/admin/competition/cascade",
                       json={"actif": True, "regles": regles})
        assert r.status_code == 200
        assert any("sans effet" in a for a in r.get_json()["avertissements"])

    def test_categorie_inconnue_acceptee(self, admin, jeu):
        """Elle peut reapparaitre au prochain import."""
        r = admin.post("/admin/competition/cascade", json={
            "actif": False, "regles": [], "categories_eteintes": ["U19 F"]})
        assert r.status_code == 200
        assert r.get_json()["cascade"]["categories_eteintes"] == ["U19 F"]

    def test_une_cle_absente_n_efface_pas_la_portee(self, admin, jeu):
        """⚠️ Une cle ABSENTE ne vaut pas une liste vide : sinon un appel qui
        omet `categories_eteintes` rallume toutes les categories, et recredite
        leurs blocs, en repondant 200."""
        admin.post("/admin/competition/cascade", json={
            "actif": True, "regles": [REGLE_VERT],
            "categories_eteintes": ["U11 F"]})
        r = admin.post("/admin/competition/cascade",
                       json={"actif": True, "regles": [REGLE_VERT]})
        assert r.status_code == 200
        assert r.get_json()["cascade"]["categories_eteintes"] == ["U11 F"]

    def test_la_portee_survit_a_une_regle_videe(self, admin, jeu):
        """On efface ses phrases pour en reecrire d'autres : les huit
        interrupteurs ne doivent pas partir avec."""
        admin.post("/admin/competition/cascade", json={
            "actif": True, "regles": [REGLE_VERT],
            "categories_eteintes": ["U11 F"]})
        admin.post("/admin/competition/cascade", json={
            "actif": False, "regles": [], "categories_eteintes": ["U11 F"]})
        d = admin.get("/admin/competition/cascade").get_json()
        assert d["cascade"]["categories_eteintes"] == ["U11 F"]

    def test_trop_de_regles_est_refuse(self, admin, jeu):
        """Sans plafond, 20 000 regles s'ecrivent en base et font passer un
        recalcul de 22 ms a 2,2 s -- durablement."""
        trop = [dict(REGLE_VERT) for _ in range(50)]
        r = admin.post("/admin/competition/cascade",
                       json={"actif": True, "regles": trop})
        assert r.status_code == 400
        assert "au maximum" in r.get_json()["message"]

    def test_un_nombre_non_fini_ne_fait_pas_un_500(self, admin, jeu):
        """`json.loads` accepte `Infinity`, et `int(inf)` leve OverflowError."""
        r = admin.post("/admin/competition/cascade",
                       data='{"actif": true, "regles": [{"parmi": ["Vert"], '
                            '"seuil": Infinity, "cibles": ["Jaune"]}]}',
                       content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["success"] is False

    def test_corps_illisible(self, admin, jeu):
        r = admin.post("/admin/competition/cascade",
                       data="pas du json", content_type="application/json")
        assert r.status_code == 400


class TestEffetImmediat:
    def test_le_classement_suit_sans_attendre_le_cache(self, admin, jeu):
        """⚠️ Sans la purge du cache, le reglage ne se verrait qu'au bout de cinq
        secondes — assez pour qu'on le croie sans effet et qu'on recommence."""
        lea = jeu["participants"][0]          # U11 F, circuit U11
        vert = jeu["blocs"][1]                # ZJ7, le seul Vert du circuit U11
        enregistrer_reussite(lea, vert)

        avant, _ = classement_service.classements(jeu["competition"])
        assert avant["U11 F"].lignes[0].blocs_reussis == 1

        admin.post("/admin/competition/cascade", json={
            "actif": True, "regles": [REGLE_VERT]})

        apres, _ = classement_service.classements(jeu["competition"])
        # Le Vert est plein : le Jaune du circuit est credite.
        assert apres["U11 F"].lignes[0].blocs_reussis == 2

    def test_une_categorie_eteinte_ne_credite_rien(self, admin, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][1])

        admin.post("/admin/competition/cascade", json={
            "actif": True, "regles": [REGLE_VERT],
            "categories_eteintes": ["U11 F"]})

        apres, _ = classement_service.classements(jeu["competition"])
        assert apres["U11 F"].lignes[0].blocs_reussis == 1
