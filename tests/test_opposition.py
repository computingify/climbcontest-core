"""Spec 043 — le droit d'opposition (art. 21 RGPD), rendu exercable.

La CNIL le formule ainsi pour le sport amateur : le sportif, ou son
representant legal s'il est mineur, doit pouvoir s'opposer SIMPLEMENT a la
publication de ses resultats, et la structure retire alors ce qui est en ligne.

Ce que ces tests tiennent, dans l'ordre d'importance :

1. **Le rang ne bouge pas.** C'est la propriete, et elle ne se voit qu'en
   comparant la charge avec et sans opposition sur le meme jeu de donnees. Un
   test qui n'affirmerait que le nom passerait au vert sur une implementation
   qui RETIRE la ligne -- ce qui decalerait tout le monde, et ferait d'un rang
   qui saute une information sur celui qui manque.
2. La fiche du grimpeur suit la meme regle, sinon le reglage se contourne en
   touchant une ligne du classement.
3. L'archive fige le VRAI nom : elle est servie derriere la session
   organisateur, et une archive amputee serait irreparable.
"""

import json

import pytest

from climbcontest import comptes
from climbcontest.classement_service import charge_publique, nom_publie
from climbcontest.contest import enregistrer_reussite
from climbcontest.extensions import db
from climbcontest.models import Participant

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, jeu):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


def _lignes(charge, groupe):
    for c in charge["classements"]:
        if c["groupe"] == groupe:
            return c["lignes"]
    raise AssertionError(f"groupe {groupe} absent")


class TestLaColonne:

    def test_elle_vaut_faux_par_defaut(self, jeu):
        """On publie SAUF refus : le vide n'est pas un doute.

        Nommee `diffusion_autorisee`, la colonne aurait fait taire tous ceux qui
        n'ont rien exprime -- c'est-a-dire presque tous.
        """
        for p in jeu["participants"]:
            assert p.publication_refusee is False


class TestLeNomPublie:

    def test_sans_opposition_le_vrai_nom(self, jeu):
        assert nom_publie(jeu["participants"][0]) == "Dupont Lea"

    def test_avec_opposition_le_dossard(self, jeu):
        p = jeu["participants"][0]
        p.publication_refusee = True
        assert nom_publie(p) == "Dossard 1"

    def test_sans_dossard_un_repli_lisible(self, jeu):
        """`dossard` est nullable -- c'est ainsi qu'un inscrit absent existe.

        Sans ce repli, la page projetee afficherait « Dossard None ».
        """
        p = jeu["participants"][2]
        assert p.dossard is None
        p.publication_refusee = True
        assert nom_publie(p) == "Participant"

    def test_anonymiser_faux_rend_le_vrai_nom(self, jeu):
        p = jeu["participants"][0]
        p.publication_refusee = True
        assert nom_publie(p, anonymiser=False) == "Dupont Lea"


class TestLaChargePublique:

    def test_le_nom_change_mais_le_rang_et_le_score_ne_bougent_pas(self, app, jeu):
        """⚠️ LE test de la spec. On compare deux charges du meme jeu."""
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        comp = jeu["competition"]

        avant = _lignes(charge_publique(comp, forcer=True), "U11 F")
        temoin = [(l["participant_id"], l["rang"], l["score"], l["dossard"])
                  for l in avant]
        assert avant[0]["nom"] == "Dupont Lea"

        jeu["participants"][0].publication_refusee = True
        db.session.commit()

        apres = _lignes(charge_publique(comp, forcer=True), "U11 F")
        assert apres[0]["nom"] == "Dossard 1"
        assert [(l["participant_id"], l["rang"], l["score"], l["dossard"])
                for l in apres] == temoin
        assert len(apres) == len(avant), "la ligne reste, elle n'est pas retiree"

    def test_le_club_et_la_categorie_restent(self, app, jeu):
        """Decision du 04/09 : ils sont necessaires pour lire le classement et
        ne nomment personne. Ce choix est ecrit dans la page de
        confidentialite plutot que passe sous silence."""
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        jeu["participants"][0].publication_refusee = True
        db.session.commit()

        ligne = _lignes(charge_publique(jeu["competition"], forcer=True), "U11 F")[0]
        assert ligne["club"] == "Les Lezards"
        assert ligne["categorie"] == "U11 F"

    def test_la_forme_de_la_charge_ne_change_pas(self, app, jeu):
        """Aucun champ de plus ne sort : seule la VALEUR de `nom` change."""
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        comp = jeu["competition"]
        avant = set(_lignes(charge_publique(comp, forcer=True), "U11 F")[0])

        jeu["participants"][0].publication_refusee = True
        db.session.commit()

        apres = set(_lignes(charge_publique(comp, forcer=True), "U11 F")[0])
        assert avant == apres

    def test_par_l_api(self, client_sans_cle, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        jeu["participants"][0].publication_refusee = True
        db.session.commit()

        d = client_sans_cle.get("/api/public/classement?groupe=U11 F").get_json()
        assert d["classements"][0]["lignes"][0]["nom"] == "Dossard 1"


class TestLaFicheDuGrimpeur:

    def test_elle_porte_le_meme_nom(self, client_sans_cle, jeu):
        """Sinon le reglage se contourne en touchant une ligne du classement."""
        p = jeu["participants"][0]
        enregistrer_reussite(p, jeu["blocs"][0])
        p.publication_refusee = True
        db.session.commit()

        d = client_sans_cle.get(f"/api/public/grimpeur/{p.id}").get_json()
        assert d["participant"]["nom"] == "Dossard 1"


class TestLArchive:

    def test_elle_fige_le_vrai_nom(self, app, jeu):
        """Elle est servie derriere la session organisateur : usage interne
        legitime du club. On fige complet, on rend anonymise."""
        from climbcontest import cycle

        p = jeu["participants"][0]
        enregistrer_reussite(p, jeu["blocs"][0])
        p.publication_refusee = True
        db.session.commit()

        archive, _ = cycle.archiver(jeu["competition"], par="orga")
        fige = json.loads(archive.contenu)
        assert _lignes(fige["classement"], "U11 F")[0]["nom"] == "Dupont Lea"


class TestLaRouteDeLaConsole:

    def test_elle_bascule_et_l_etat_survit(self, connecte, jeu):
        p = jeu["participants"][0]
        r = connecte.post(f"/admin/participants/{p.id}/publication",
                          json={"refusee": True})
        assert r.status_code == 200
        assert r.get_json()["participant"]["publication_refusee"] is True

        db.session.expire_all()
        assert db.session.get(Participant, p.id).publication_refusee is True

    def test_elle_revient_en_arriere(self, connecte, jeu):
        p = jeu["participants"][0]
        connecte.post(f"/admin/participants/{p.id}/publication", json={"refusee": True})
        connecte.post(f"/admin/participants/{p.id}/publication", json={"refusee": False})
        db.session.expire_all()
        assert db.session.get(Participant, p.id).publication_refusee is False

    def test_le_champ_est_exige(self, connecte, jeu):
        p = jeu["participants"][0]
        assert connecte.post(f"/admin/participants/{p.id}/publication",
                             json={}).status_code == 400

    def test_participant_inconnu(self, connecte):
        assert connecte.post("/admin/participants/9999/publication",
                             json={"refusee": True}).status_code == 404

    def test_sans_session(self, client, app, jeu):
        """⚠️ La SECRET_KEY est posee sur `app.config` et pas dans une classe de
        configuration : gitleaks refuse un secret ecrit dans le depot, meme de
        test. Sans elle, la route repond 503 « administration desactivee » -- ce
        qui passerait pour un refus alors que c'est une panne."""
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        p = jeu["participants"][0]
        r = client.post(f"/admin/participants/{p.id}/publication",
                        json={"refusee": True})
        assert r.status_code == 401

    def test_la_liste_porte_l_etat(self, connecte, jeu):
        p = jeu["participants"][0]
        connecte.post(f"/admin/participants/{p.id}/publication", json={"refusee": True})
        liste = connecte.get("/admin/participants").get_json()["participants"]
        par_id = {x["id"]: x for x in liste}
        assert par_id[p.id]["publication_refusee"] is True
        # La console montre TOUJOURS le vrai nom : c'est elle qui sert a
        # retrouver la personne au telephone.
        assert par_id[p.id]["nom"] == "Dupont Lea"

    def test_le_cache_est_invalide(self, connecte, client_sans_cle, jeu):
        """Sans ca, l'organisateur qui vient de raccrocher avec un parent
        regarderait un ecran qui n'obeit pas pendant cinq secondes."""
        p = jeu["participants"][0]
        enregistrer_reussite(p, jeu["blocs"][0])
        # On peuple le cache.
        client_sans_cle.get("/api/public/classement")

        connecte.post(f"/admin/participants/{p.id}/publication", json={"refusee": True})

        d = client_sans_cle.get("/api/public/classement?groupe=U11 F").get_json()
        assert d["classements"][0]["lignes"][0]["nom"] == "Dossard 1"
