"""La salle d'attente vue de la console — spec 008, lot 6.

Les quatre états d'une inscription décrivent un **geste physique** : trancher,
imprimer, remettre. Ce fichier vérifie que chaque bouton fait ce qu'il annonce
et, surtout, ce qu'il ne fait pas — `test_retirer_refuse_si_le_participant_a_des_reussites`
est celui qui empêche un clic d'effacer des résultats.
"""

import pytest

from climbcontest import comptes
from climbcontest.contest import enregistrer_reussite
from climbcontest.extensions import db
from climbcontest.helloasso import client as ha
from climbcontest.models import (
    A_IMPRIMER, A_TRANCHER, FAITE, IGNOREE, Inscription, MOTIF_ANNULEE,
    MOTIF_CLUB_DIFFERENT, Participant,
)

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, jeu, tmp_path):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    app.config["DOSSIER_SECRETS"] = str(tmp_path)
    comptes.creer("chef", MDP, [comptes.ADMIN])
    client.post("/admin/connexion", json={"identifiant": "chef", "mot_de_passe": MDP})
    return client


def une_inscription(comp, **champs):
    defauts = dict(article_id=1, commande_id=8868440, etat=A_TRANCHER,
                   motif=MOTIF_CLUB_DIFFERENT, nom="Brunel", prenom="Lea",
                   club="Roc N'Potes", categorie="U13 F", annee_naissance=2015,
                   etat_helloasso="Processed")
    defauts.update(champs)
    i = Inscription(competition_id=comp.id, **defauts)
    db.session.add(i)
    db.session.commit()
    return i


class TestLesPiles:
    def test_les_trois_piles(self, connecte, jeu):
        une_inscription(jeu["competition"], article_id=1, etat=A_TRANCHER)
        une_inscription(jeu["competition"], article_id=2, etat=A_IMPRIMER)
        une_inscription(jeu["competition"], article_id=3, etat=FAITE)
        d = connecte.get("/admin/inscriptions").get_json()
        assert len(d["a_trancher"]) == 1
        assert len(d["a_imprimer"]) == 1
        assert len(d["faites"]) == 1

    def test_la_pastille_compte_les_deux_piles_qui_demandent_un_geste(
            self, connecte, jeu):
        """Ne compter que « à trancher » ferait disparaître la pastille alors
        qu'il reste des dossards à imprimer et à porter."""
        une_inscription(jeu["competition"], article_id=1, etat=A_TRANCHER)
        une_inscription(jeu["competition"], article_id=2, etat=A_IMPRIMER)
        une_inscription(jeu["competition"], article_id=3, etat=FAITE)
        assert connecte.get("/admin/inscriptions").get_json()["en_attente"] == 2

    def test_le_compteur_voyage_dans_moi(self, connecte, jeu):
        une_inscription(jeu["competition"], article_id=1, etat=A_TRANCHER)
        assert connecte.get("/admin/moi").get_json()["inscriptions_en_attente"] == 1

    def test_un_cas_de_doublon_porte_la_fiche_a_comparer(self, connecte, jeu):
        db.session.add(Participant(competition_id=jeu["competition"].id,
                                   nom="Brunel", prenom="Lea",
                                   club="Annonay Escalade", categorie="U13 F",
                                   dossard=47))
        db.session.commit()
        une_inscription(jeu["competition"])
        cas = connecte.get("/admin/inscriptions").get_json()["a_trancher"][0]
        assert len(cas["ressemble_a"]) == 1
        assert cas["ressemble_a"][0]["dossard"] == 47


class TestTrancher:
    def test_la_meme_personne_ne_duplique_pas(self, connecte, jeu):
        p = Participant(competition_id=jeu["competition"].id, nom="Brunel",
                        prenom="Lea", club="Annonay Escalade",
                        categorie="U13 F", dossard=47)
        db.session.add(p)
        db.session.commit()
        i = une_inscription(jeu["competition"])
        avant = Participant.query.count()
        r = connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                          json={"choix": "meme_personne", "participant_id": p.id})
        assert r.status_code == 200
        assert Participant.query.count() == avant
        db.session.refresh(i)
        assert i.etat == A_IMPRIMER and i.participant_id == p.id

    def test_deux_personnes_cree_un_participant(self, connecte, jeu):
        i = une_inscription(jeu["competition"])
        avant = Participant.query.count()
        connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                      json={"choix": "deux_personnes"})
        assert Participant.query.count() == avant + 1
        db.session.refresh(i)
        cree = db.session.get(Participant, i.participant_id)
        assert cree.dossard is not None and cree.annee_naissance == 2015

    def test_ranger_une_categorie_marque_le_geste(self, connecte, jeu):
        """Décision D10 : « Appliquer le barème » ne défera pas ce choix."""
        i = une_inscription(jeu["competition"], motif="annee_hors_bareme",
                            categorie=None)
        connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                      json={"choix": "categorie", "categorie": "senior f"})
        db.session.refresh(i)
        cree = db.session.get(Participant, i.participant_id)
        # ⚠️ « Senior F » et non « SENIOR F » : depuis la spec 045, le
        # formatage ne se contente plus de mettre en capitales, il RATTACHE a
        # la categorie officielle. C'est la meme fonction, la meme porte -- et
        # c'est ce qui fait que « senior f » tape a la volee un samedi matin
        # tombe sur la meme valeur que celle du formulaire d'ajout.
        assert cree.categorie == "Senior F" and cree.categorie_forcee is True

    def test_ranger_sans_categorie_est_refuse(self, connecte, jeu):
        i = une_inscription(jeu["competition"])
        r = connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                          json={"choix": "categorie"})
        assert r.status_code == 400

    def test_ignorer(self, connecte, jeu):
        i = une_inscription(jeu["competition"])
        connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                      json={"choix": "ignorer"})
        db.session.refresh(i)
        assert i.etat == IGNOREE and Participant.query.filter_by(nom="Brunel").count() == 0

    def test_trancher_deux_fois_est_refuse(self, connecte, jeu):
        """Deux organisateurs devant le même écran, c'est le cas normal.

        Le second doit apprendre que le premier est passé, pas écraser son choix.
        """
        i = une_inscription(jeu["competition"])
        connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                      json={"choix": "ignorer"})
        r = connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                          json={"choix": "deux_personnes"})
        assert r.status_code == 409

    def test_un_choix_inconnu(self, connecte, jeu):
        i = une_inscription(jeu["competition"])
        r = connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                          json={"choix": "danser"})
        assert r.status_code == 400

    def test_inscription_inconnue(self, connecte, jeu):
        r = connecte.post("/admin/inscriptions/999999/trancher",
                          json={"choix": "ignorer"})
        assert r.status_code == 404


class TestLAnnulation:
    def test_retirer_supprime_le_participant_mais_pas_l_inscription(
            self, connecte, jeu):
        """L'inscription reste : sinon le relevé suivant recréerait tout,
        l'article étant redevenu inconnu."""
        p = Participant(competition_id=jeu["competition"].id, nom="Brunel",
                        prenom="Lea", dossard=47)
        db.session.add(p)
        db.session.commit()
        i = une_inscription(jeu["competition"], etat=A_TRANCHER,
                            motif=MOTIF_ANNULEE, participant_id=p.id)
        connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                      json={"choix": "retirer"})
        assert db.session.get(Participant, p.id) is None
        assert Inscription.query.count() == 1

    def test_retirer_refuse_si_le_participant_a_des_reussites(self, connecte, jeu):
        """Un clic ne doit pas pouvoir effacer des résultats."""
        p = Participant.query.filter_by(
            competition_id=jeu["competition"].id, dossard=1).one()
        enregistrer_reussite(p, jeu["blocs"][0])
        db.session.commit()
        i = une_inscription(jeu["competition"], etat=A_TRANCHER,
                            motif=MOTIF_ANNULEE, participant_id=p.id)
        r = connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                          json={"choix": "retirer"})
        assert r.status_code == 409
        assert db.session.get(Participant, p.id) is not None

    def test_garder_clot_sans_rien_toucher(self, connecte, jeu):
        p = Participant(competition_id=jeu["competition"].id, nom="Brunel",
                        dossard=47)
        db.session.add(p)
        db.session.commit()
        i = une_inscription(jeu["competition"], etat=A_TRANCHER,
                            motif=MOTIF_ANNULEE, participant_id=p.id)
        connecte.post(f"/admin/inscriptions/{i.id}/trancher",
                      json={"choix": "garder"})
        db.session.refresh(i)
        assert i.etat == FAITE
        assert db.session.get(Participant, p.id) is not None


class TestLaRemise:
    def test_marquer_remis(self, connecte, jeu):
        i = une_inscription(jeu["competition"], etat=A_IMPRIMER, motif=None)
        connecte.post(f"/admin/inscriptions/{i.id}/remise")
        db.session.refresh(i)
        assert i.etat == FAITE and i.traitee_par == "chef"

    def test_les_dossards_a_imprimer(self, connecte, jeu):
        p = Participant(competition_id=jeu["competition"].id, nom="Un",
                        dossard=77)
        db.session.add(p)
        db.session.commit()
        une_inscription(jeu["competition"], etat=A_IMPRIMER, motif=None,
                        participant_id=p.id)
        d = connecte.get("/admin/inscriptions").get_json()
        assert d["a_imprimer_dossards"] == [77]


class TestLesAcces:
    def test_sans_session(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/inscriptions").status_code == 401
        assert client.get("/admin/helloasso").status_code == 401

    def test_un_organisateur_ne_regle_pas_la_cle(self, client, app, jeu, tmp_path):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        app.config["DOSSIER_SECRETS"] = str(tmp_path)
        comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
        client.post("/admin/connexion",
                    json={"identifiant": "orga", "mot_de_passe": MDP})
        assert client.get("/admin/helloasso").status_code == 403
        assert client.post("/admin/helloasso/cle", json={}).status_code == 403
        # …mais il voit et traite les inscriptions : c'est lui qui imprime les
        # dossards et les porte.
        assert client.get("/admin/inscriptions").status_code == 200


class TestLaCleParLaRoute:
    def test_une_cle_refusee_ne_reste_pas_posee(self, connecte, jeu, monkeypatch):
        """Sinon le fil démarrerait sur une clé morte et brûlerait le quota."""
        class Reponse:
            status_code = 401

            def json(self):
                return {}
        monkeypatch.setattr(ha.requests, "post", lambda *a, **k: Reponse())
        r = connecte.post("/admin/helloasso/cle",
                          json={"client_id": "x", "client_secret": "y"})
        assert r.status_code == 400
        assert ha.lire_secret() is None

    def test_l_etat_ne_rend_jamais_le_secret(self, connecte, jeu, monkeypatch):
        class Reponse:
            status_code = 200

            def json(self):
                return {"access_token": "A", "refresh_token": "R",
                        "expires_in": 1799}
        monkeypatch.setattr(ha.requests, "post", lambda *a, **k: Reponse())
        connecte.post("/admin/helloasso/cle",
                      json={"client_id": "identifiant-de-test-3715",
                            "client_secret": "tres-secret"})
        corps = connecte.get("/admin/helloasso").get_data(as_text=True)
        assert "tres-secret" not in corps
        assert "identifiant-de-test-3715" not in corps

    def test_les_champs_refusent_l_absence_d_annee(self, connecte, jeu):
        r = connecte.post("/admin/helloasso/champs",
                          json={"champs": {"genre": "Sexe"}})
        assert r.status_code == 400
        assert "categorie" in r.get_json()["message"]

    def test_les_champs_s_enregistrent(self, connecte, jeu):
        r = connecte.post("/admin/helloasso/champs", json={
            "champs": {"naissance": "Date de naissance", "genre": "Sexe",
                       "club": "Votre club"},
            "genre_valeurs": {"Fille": "F"}})
        assert r.status_code == 200
        assert r.get_json()["formulaire"]["champs"]["naissance"] == "Date de naissance"


class TestLEffacement:
    def test_effacer_les_donnees_emporte_les_inscriptions(self, connecte, jeu):
        """Une salle d'attente qui survivrait ferait revenir des gens qu'on
        vient d'effacer."""
        une_inscription(jeu["competition"])
        r = connecte.post("/admin/donnees/effacer",
                          json={"confirmation": "EFFACER", "forcer": True})
        assert r.status_code == 200, r.get_json()
        assert Inscription.query.count() == 0


class TestRelierEnUnGeste:
    """« Un truc simple, et que l'utilisateur puisse vérifier que ça marche. »

    Demandé par Adrien le 04/09. Deux acquis, vérifiés ici :

    - **le nom court de l'association ne se saisit plus.** La clé le connaît,
      par `/users/me/organizations` — vérifié le 04/09 contre le vrai bac à
      sable, qui rend `annonay-escalade` tout seul. Un champ à remplir à la
      main aurait sa faute de frappe, et le symptôme aurait été « aucun
      formulaire trouvé », qui n'accuse personne ;
    - **« Tester » nomme le club.** Un verdict qui dit seulement « relié » ne
      prouve rien : il pourrait désigner la mauvaise association.
    """

    def _brancher(self, monkeypatch, organisations=None, formulaires=None,
                  articles=None):
        class Reponse:
            def __init__(self, code, donnees):
                self.status_code, self._d = code, donnees

            def json(self):
                return self._d

        monkeypatch.setattr(ha.requests, "post",
                            lambda *a, **k: Reponse(200, {
                                "access_token": "A", "refresh_token": "R",
                                "expires_in": 1799}))

        def faux_get(url, params=None, **k):
            if "/users/me/organizations" in url:
                return Reponse(200, organisations if organisations is not None
                               else [{"organizationSlug": "annonay-escalade",
                                      "name": "ANNONAY ESCALADE"}])
            if url.endswith("/forms"):
                return Reponse(200, {"data": formulaires if formulaires is not None
                                     else [{"title": "Bloc Party",
                                            "formType": "Event",
                                            "formSlug": "bloc-party"}]})
            if url.endswith("/items"):
                return Reponse(200, {"data": articles or []})
            return Reponse(200, {})
        monkeypatch.setattr(ha.requests, "get", faux_get)

    def _poser_la_cle(self, connecte):
        return connecte.post("/admin/helloasso/cle",
                             json={"client_id": "a", "client_secret": "b",
                                   "environnement": "sandbox"})

    def test_poser_la_cle_decouvre_l_association(self, connecte, jeu, monkeypatch):
        self._brancher(monkeypatch)
        d = self._poser_la_cle(connecte).get_json()
        assert d["organisations"][0]["nom"] == "ANNONAY ESCALADE"
        assert d["formulaires"][0]["slug"] == "bloc-party"

    def test_les_formulaires_ne_demandent_aucun_parametre(self, connecte, jeu,
                                                          monkeypatch):
        self._brancher(monkeypatch)
        self._poser_la_cle(connecte)
        d = connecte.get("/admin/helloasso/formulaires").get_json()
        assert d["formulaires"][0]["nom"] == "Bloc Party"

    def test_choisir_un_formulaire_sans_donner_l_association(self, connecte, jeu,
                                                             monkeypatch):
        self._brancher(monkeypatch)
        self._poser_la_cle(connecte)
        r = connecte.post("/admin/helloasso/formulaire",
                          json={"form_type": "Event", "form_slug": "bloc-party"})
        assert r.status_code == 200
        assert r.get_json()["formulaire"]["organisation"] == "annonay-escalade"

    def test_tester_nomme_le_club(self, connecte, jeu, monkeypatch):
        self._brancher(monkeypatch)
        self._poser_la_cle(connecte)
        d = connecte.post("/admin/helloasso/tester").get_json()
        assert d["association"] == "ANNONAY ESCALADE"
        assert d["formulaires"] == 1

    def test_tester_compte_les_inscriptions_du_formulaire_choisi(
            self, connecte, jeu, monkeypatch):
        """Le fait le plus parlant : « j'ai bien mes trois inscrits »."""
        self._brancher(monkeypatch, articles=[{"id": 1}, {"id": 2}, {"id": 3}])
        self._poser_la_cle(connecte)
        connecte.post("/admin/helloasso/formulaire",
                      json={"form_type": "Event", "form_slug": "bloc-party"})
        d = connecte.post("/admin/helloasso/tester").get_json()
        assert d["formulaire"] == "bloc-party"
        assert d["inscriptions"] == 3

    def test_une_cle_sans_association(self, connecte, jeu, monkeypatch):
        self._brancher(monkeypatch, organisations=[])
        self._poser_la_cle(connecte)
        r = connecte.post("/admin/helloasso/tester")
        assert r.status_code == 409
        assert "aucune association" in r.get_json()["message"]

    def test_tester_est_reserve_aux_administrateurs(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        comptes.creer("orga2", MDP, [comptes.ORGANISATEUR])
        client.post("/admin/connexion",
                    json={"identifiant": "orga2", "mot_de_passe": MDP})
        assert client.post("/admin/helloasso/tester").status_code == 403

    def test_la_decouverte_qui_echoue_laisse_la_cle_posee(self, connecte, jeu,
                                                          monkeypatch):
        """Une découverte ratée ne doit pas défaire ce qui vient de marcher :
        le jeton a été obtenu, la clé est bonne."""
        class Reponse:
            def __init__(self, code, donnees):
                self.status_code, self._d = code, donnees

            def json(self):
                return self._d
        monkeypatch.setattr(ha.requests, "post",
                            lambda *a, **k: Reponse(200, {
                                "access_token": "A", "refresh_token": "R",
                                "expires_in": 1799}))
        monkeypatch.setattr(ha.requests, "get",
                            lambda *a, **k: Reponse(500, {}))
        d = self._poser_la_cle(connecte).get_json()
        assert d["success"] is True
        assert d["organisations"] == []
        assert ha.lire_secret() is not None
