"""Le classeur se règle depuis la console — spec 015.

Ce que ces tests protègent : **le geste le plus dangereux de la console.**
Relier un autre classeur décide où partiront les réussites, et l'un des trois
modes efface des données des deux côtés. Chaque garde-fou est donc vérifié en
le franchissant : mauvais mot de confirmation, compétition en cours, Google qui
refuse — et à chaque fois, on regarde que la base n'a PAS bougé.

Aucun accès réseau : `ClasseurGoogle` est remplacé dans le module de
paramétrage par un double qui note ce qu'on lui demande.
"""

import json
import os
import stat

import pytest

from climbcontest import comptes
from climbcontest.contest import ErreurMetier, enregistrer_reussite
from climbcontest.extensions import db
from climbcontest.models import (
    Bloc, Circuit, EN_COURS, Participant, PREPARATION, ReaffectationDossard, Success,
)
from climbcontest.sheets import parametrage
from climbcontest.sheets.client import ClasseurGoogle, ErreurClasseur

JETON = {"token": "ya29.court", "refresh_token": "1//refresh",
         "client_id": "id.apps.googleusercontent.com", "client_secret": "secret",
         "scopes": ["https://www.googleapis.com/auth/spreadsheets"]}


MDP = "un-mot-de-passe-assez-long"
ID_CLASSEUR = "1h3e8QUSXnCJLSYSFyB8X92cppDubeDx0yi8mn3NSh5s"
LIEN = f"https://docs.google.com/spreadsheets/d/{ID_CLASSEUR}/edit#gid=1826372"


# --- Le double du classeur --------------------------------------------------

class ClasseurDouble:
    """Ce que `parametrage` attend d'un classeur, et rien de plus."""

    def __init__(self, identifiant, feuilles=None):
        self.identifiant = identifiant
        registre = ClasseurDouble.registre
        registre["identifiants"].append(identifiant)
        self._options = registre["options"]

    def titre(self):
        return self._options.get("titre", "U11 U15 Novembre 2026")

    def onglets(self):
        return list(self._options.get("onglets", ("Import", "Listes", "Plan")))

    def grille(self, onglet):
        if onglet not in self.onglets():
            raise ErreurClasseur(f"Onglet « {onglet} » absent du classeur")
        return {"id": 0, "lignes": self._options.get("lignes", 60),
                "colonnes": self._options.get("colonnes", 123)}

    def plages_protegees(self, onglet):
        return list(self._options.get("plages_protegees", ()))

    def essai_ecriture(self, onglet="Import"):
        ClasseurDouble.registre["essais"] += 1
        return dict(self._options.get("essai_ecriture", {
            "tentee": True, "onglet": onglet, "cellule": f"{onglet}!DS60",
            "ecriture": True, "restauree": True, "plages_protegees": [],
            "message": f"Ecriture confirmee sur {onglet}!DS60, puis effacee."}))

    def vider_matrice(self, onglet="Import"):
        if self._options.get("vidage_refuse"):
            raise ErreurClasseur("Google refuse le vidage (simule)")
        ClasseurDouble.registre["vidages"] += 1
        return {"plage": "D2:DS51", "lignes": 50, "colonnes": 120}


@pytest.fixture()
def classeur(monkeypatch, tmp_path):
    """Une installation qui MARCHE : un jeton posé, et Google qui répond.

    Le jeton fait partie du décor — sans lui, `tester()` s'arrête avant même
    d'appeler le classeur, et c'est exactement ce que vérifie
    `test_sans_jeton_le_message_dit_quoi_faire`.
    """
    (tmp_path / "token.json").write_text(json.dumps(JETON))
    monkeypatch.setattr(ClasseurGoogle, "_dossiers_de_jeton",
                        staticmethod(lambda: [tmp_path]))
    ClasseurDouble.registre = {"identifiants": [], "vidages": 0, "essais": 0,
                               "options": {}}
    monkeypatch.setattr(parametrage, "ClasseurGoogle", ClasseurDouble)
    return ClasseurDouble.registre


@pytest.fixture()
def secret(app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    return app


@pytest.fixture()
def connecte(client, secret):
    comptes.creer("chef", MDP, [comptes.ADMIN])
    client.post("/admin/connexion", json={"identifiant": "chef", "mot_de_passe": MDP})
    return client


@pytest.fixture()
def organisateur(client, secret):
    comptes.creer("benevole", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion",
                json={"identifiant": "benevole", "mot_de_passe": MDP})
    return client


@pytest.fixture()
def secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(ClasseurGoogle, "_dossiers_de_jeton",
                        staticmethod(lambda: [tmp_path]))
    return tmp_path


# --- A4, A5 : ce qu'on colle ------------------------------------------------

class TestExtraireIdentifiant:
    """Ce qu'on colle vient d'une barre d'adresse. C'est cette forme-là qui doit
    marcher sans réfléchir, un dimanche matin."""

    @pytest.mark.parametrize("colle", [
        LIEN,
        f"https://docs.google.com/spreadsheets/d/{ID_CLASSEUR}",
        f"https://docs.google.com/spreadsheets/d/{ID_CLASSEUR}/edit?usp=sharing",
        f"  {ID_CLASSEUR}  ",
        ID_CLASSEUR,
    ])
    def test_les_formes_acceptees(self, colle):
        assert parametrage.extraire_identifiant(colle) == ID_CLASSEUR

    @pytest.mark.parametrize("colle", ["", "   ", "https://exemple.fr/rien",
                                       "spreadsheets/d/trop-court", "mon classeur"])
    def test_les_formes_refusees_disent_quoi_coller(self, colle):
        with pytest.raises(ErreurMetier) as e:
            parametrage.extraire_identifiant(colle)
        assert "lien" in e.value.message.lower() or "spreadsheets" in e.value.message


# --- L'état affiché ---------------------------------------------------------

class TestEtat:

    def test_dit_le_classeur_relie_et_les_compteurs(self, connecte, jeu, secrets):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        r = connecte.get("/admin/classeur")
        assert r.status_code == 200
        etat = r.get_json()
        assert etat["classeur"] == {"relie": True, "identifiant": "fictif",
                                    "url": "https://docs.google.com/spreadsheets/"
                                           "d/fictif/edit"}
        assert etat["compteurs"]["reussites"] == 1
        assert etat["compteurs"]["reussites_en_attente"] == 1
        assert etat["compteurs"]["dossard_max"] == 2

    def test_sans_competition_active_repond_quand_meme(self, connecte, secrets):
        r = connecte.get("/admin/classeur")
        assert r.status_code == 200
        assert r.get_json()["competition"] is None

    def test_sans_jeton_l_etat_le_dit(self, connecte, competition, secrets):
        assert connecte.get("/admin/classeur").get_json()["jeton"]["present"] is False

    def test_le_jeton_n_est_jamais_renvoye(self, connecte, competition, secrets):
        (secrets / "token.json").write_text(json.dumps(JETON))
        corps = connecte.get("/admin/classeur").get_data(as_text=True)
        assert "1//refresh" not in corps and "secret" not in corps


# --- A6 : tester avant de relier -------------------------------------------

class TestTester:

    def test_dit_le_titre_les_onglets_et_la_grille(self, connecte, jeu, classeur):
        r = connecte.post("/admin/classeur/test", json={"lien": LIEN})
        assert r.status_code == 200
        rapport = r.get_json()["rapport"]
        assert rapport["identifiant"] == ID_CLASSEUR
        assert rapport["titre"] == "U11 U15 Novembre 2026"
        assert rapport["onglets_manquants"] == []
        assert rapport["grille"]["colonnes"] == 123
        assert rapport["dossard_max_sans_agrandir"] == 120

    def test_un_onglet_manquant_est_signale_sans_bloquer(self, connecte, jeu, classeur):
        classeur["options"]["onglets"] = ("Import", "Plan")
        rapport = connecte.post("/admin/classeur/test",
                                json={"lien": LIEN}).get_json()["rapport"]
        assert rapport["onglets_manquants"] == ["Listes"]
        assert any("Listes" in a for a in rapport["avertissements"])

    def test_sans_onglet_import_on_s_arrete_la(self, connecte, jeu, classeur):
        classeur["options"]["onglets"] = ("Listes",)
        rapport = connecte.post("/admin/classeur/test",
                                json={"lien": LIEN}).get_json()["rapport"]
        assert rapport["grille"] is None

    def test_teste_le_classeur_relie_quand_aucun_lien_n_est_donne(
            self, connecte, jeu, classeur):
        r = connecte.post("/admin/classeur/test", json={})
        assert r.status_code == 200
        assert classeur["identifiants"] == ["fictif"]

    def test_sans_classeur_relie_ni_lien_c_est_409(self, connecte, competition,
                                                   classeur):
        competition.spreadsheet_id = None
        db.session.commit()
        assert connecte.post("/admin/classeur/test", json={}).status_code == 409

    def test_un_dossard_au_dela_des_formules_est_signale(self, connecte, jeu,
                                                         classeur):
        """Agrandir la grille fait aboutir l'écriture ; ça ne fait pas entrer le
        grimpeur dans les formules du classeur. Il faut le DIRE."""
        jeu["participants"][0].dossard = 145
        db.session.commit()
        rapport = connecte.post("/admin/classeur/test",
                                json={"lien": LIEN}).get_json()["rapport"]
        assert any("145" in a for a in rapport["avertissements"])

    def test_sans_jeton_le_message_dit_quoi_faire(self, connecte, jeu, secrets):
        """Le client, lui, enumere les six chemins ou il a cherche : c'est ce
        qu'il faut dans un journal, pas a l'ecran."""
        r = connecte.post("/admin/classeur/test", json={"lien": LIEN})
        assert r.status_code == 409
        message = r.get_json()["message"]
        assert "Jeton Google" in message and "token.pickle" not in message

    def test_google_qui_refuse_donne_502_et_son_message(self, connecte, jeu,
                                                        secrets, monkeypatch):
        """502 et pas 500 : la panne est chez Google, ou dans le partage de la
        feuille. Son message est repris tel quel — c'est lui qui distingue
        « feuille introuvable » de « acces refuse »."""
        (secrets / "token.json").write_text(json.dumps(JETON))

        def refuse(*a, **kw):
            raise ErreurClasseur("Lecture du classeur : 404 Requested entity "
                                 "was not found.")
        monkeypatch.setattr(parametrage, "ClasseurGoogle", refuse)
        r = connecte.post("/admin/classeur/test", json={"lien": LIEN})
        assert r.status_code == 502
        assert "404" in r.get_json()["message"]


# --- A4, A7, A8, A9 : relier ------------------------------------------------

def _synchronisees():
    return Success.query.filter(Success.sheet_synced_at.isnot(None)).count()


@pytest.fixture()
def trois_reussites_envoyees(jeu):
    """Trois réussites déjà parties vers l'ANCIEN classeur."""
    from datetime import datetime
    for participant, bloc in ((jeu["participants"][0], jeu["blocs"][0]),
                              (jeu["participants"][0], jeu["blocs"][1]),
                              (jeu["participants"][1], jeu["blocs"][0])):
        reussite, _ = enregistrer_reussite(participant, bloc)
        reussite.sheet_synced_at = datetime.now()
        db.session.add(reussite)
    db.session.commit()
    return jeu


class TestRelierSeulement:

    def test_le_lien_devient_celui_de_la_competition(self, connecte, jeu, classeur):
        r = connecte.post("/admin/classeur", json={"lien": LIEN, "mode": "relier"})
        assert r.status_code == 200
        assert jeu["competition"].spreadsheet_id == ID_CLASSEUR
        assert r.get_json()["effets"]["ancien"] == "fictif"

    def test_rien_d_autre_ne_bouge(self, connecte, trois_reussites_envoyees, classeur):
        connecte.post("/admin/classeur", json={"lien": LIEN, "mode": "relier"})
        assert _synchronisees() == 3
        assert Participant.query.count() == 3

    def test_le_mode_par_defaut_est_relier(self, connecte, jeu, classeur):
        r = connecte.post("/admin/classeur", json={"lien": LIEN})
        assert r.get_json()["effets"]["mode"] == "relier"

    def test_un_lien_invalide_ne_change_rien(self, connecte, jeu, classeur):
        r = connecte.post("/admin/classeur", json={"lien": "https://exemple.fr"})
        assert r.status_code == 400
        assert jeu["competition"].spreadsheet_id == "fictif"

    def test_un_mode_inconnu_est_refuse(self, connecte, jeu, classeur):
        r = connecte.post("/admin/classeur", json={"lien": LIEN, "mode": "efface-tout"})
        assert r.status_code == 400
        assert jeu["competition"].spreadsheet_id == "fictif"

    def test_un_corps_qui_n_est_pas_un_objet_donne_400(self, connecte, jeu, classeur):
        assert connecte.post("/admin/classeur", json=["lien"]).status_code == 400


class TestMemeCompetitionAutreFeuille:

    def test_toutes_les_reussites_repartent(self, connecte, trois_reussites_envoyees,
                                            classeur):
        r = connecte.post("/admin/classeur", json={"lien": LIEN, "mode": "rejouer"})
        assert r.status_code == 200
        assert r.get_json()["effets"]["reussites_reprogrammees"] == 3
        assert _synchronisees() == 0
        assert Success.query.count() == 3            # rien n'est perdu

    def test_les_participants_et_les_blocs_restent(self, connecte,
                                                   trois_reussites_envoyees, classeur):
        connecte.post("/admin/classeur", json={"lien": LIEN, "mode": "rejouer"})
        assert Participant.query.count() == 3
        assert Bloc.query.count() == 3

    def test_autorise_en_pleine_competition(self, connecte, trois_reussites_envoyees,
                                            classeur):
        """C'est justement la réparation d'urgence du jour J."""
        assert trois_reussites_envoyees["competition"].statut == EN_COURS
        r = connecte.post("/admin/classeur", json={"lien": LIEN, "mode": "rejouer"})
        assert r.status_code == 200


class TestNouvelleCompetition:

    @pytest.fixture(autouse=True)
    def en_preparation(self, jeu):
        jeu["competition"].statut = PREPARATION
        db.session.commit()
        return jeu

    def test_sans_le_mot_de_confirmation_rien_n_est_touche(self, connecte,
                                                           trois_reussites_envoyees,
                                                           classeur):
        r = connecte.post("/admin/classeur",
                          json={"lien": LIEN, "mode": "reinitialiser"})
        assert r.status_code == 400
        assert "EFFACER" in r.get_json()["message"]
        assert Success.query.count() == 3
        assert classeur["vidages"] == 0

    def test_un_mauvais_mot_de_confirmation_ne_suffit_pas(self, connecte, jeu,
                                                          classeur):
        r = connecte.post("/admin/classeur", json={
            "lien": LIEN, "mode": "reinitialiser", "confirmation": "effacer"})
        assert r.status_code == 400          # la casse compte
        assert Participant.query.count() == 3

    def test_la_base_et_la_matrice_sont_videes(self, connecte,
                                               trois_reussites_envoyees, classeur):
        r = connecte.post("/admin/classeur", json={
            "lien": LIEN, "mode": "reinitialiser", "confirmation": "EFFACER"})
        assert r.status_code == 200
        assert classeur["vidages"] == 1
        assert Success.query.count() == 0
        assert Participant.query.count() == 0
        assert Bloc.query.count() == 0
        assert Circuit.query.count() == 0
        assert trois_reussites_envoyees["competition"].spreadsheet_id == ID_CLASSEUR

    def test_les_telephones_sont_obliges_de_retelecharger(self, connecte, jeu,
                                                          classeur):
        """Sinon ils affichent les grimpeurs de l'édition précédente sur des
        dossards désormais libres — le correctif du 30/08."""
        avant = jeu["competition"].catalogue_version
        connecte.post("/admin/classeur", json={
            "lien": LIEN, "mode": "reinitialiser", "confirmation": "EFFACER"})
        assert jeu["competition"].catalogue_version > avant

    def test_les_reaffectations_de_dossard_ne_bloquent_pas_la_suppression(
            self, connecte, jeu, classeur):
        """Elles pointent vers des participants par clé étrangère, et SQLite
        applique l'intégrité référentielle."""
        db.session.add(ReaffectationDossard(
            competition_id=jeu["competition"].id, dossard=1,
            ancien_participant_id=jeu["participants"][0].id,
            nouveau_participant_id=jeu["participants"][1].id))
        db.session.commit()
        r = connecte.post("/admin/classeur", json={
            "lien": LIEN, "mode": "reinitialiser", "confirmation": "EFFACER"})
        assert r.status_code == 200
        assert ReaffectationDossard.query.count() == 0

    def test_sans_jeton_on_refuse_avant_de_toucher_a_quoi_que_ce_soit(
            self, connecte, jeu, secrets):
        """Le mode destructeur ECRIT dans la feuille : sans jeton, il ne peut
        pas la vider, et on ne veut surtout pas d'une base effacee face a un
        classeur reste plein."""
        r = connecte.post("/admin/classeur", json={
            "lien": LIEN, "mode": "reinitialiser", "confirmation": "EFFACER"})
        assert r.status_code == 409
        assert "Jeton Google" in r.get_json()["message"]
        assert Participant.query.count() == 3

    def test_en_pleine_competition_c_est_refuse(self, connecte, jeu, classeur):
        jeu["competition"].statut = EN_COURS
        db.session.commit()
        r = connecte.post("/admin/classeur", json={
            "lien": LIEN, "mode": "reinitialiser", "confirmation": "EFFACER"})
        assert r.status_code == 409
        assert Participant.query.count() == 3

    def test_si_google_refuse_le_vidage_la_base_ne_bouge_pas(
            self, connecte, trois_reussites_envoyees, classeur):
        """Le classeur AVANT la base : l'ordre inverse laisserait une base vide
        et un classeur plein, c'est-à-dire le pire des deux."""
        classeur["options"]["vidage_refuse"] = True
        r = connecte.post("/admin/classeur", json={
            "lien": LIEN, "mode": "reinitialiser", "confirmation": "EFFACER"})
        assert r.status_code == 502
        assert "rien n'a ete modifie" in r.get_json()["message"]
        assert Success.query.count() == 3
        assert Participant.query.count() == 3
        assert trois_reussites_envoyees["competition"].spreadsheet_id == "fictif"


# --- A10, A11 : le jeton ----------------------------------------------------

class TestJeton:

    def test_un_jeton_complet_est_ecrit_en_0600(self, connecte, secrets):
        r = connecte.post("/admin/classeur/jeton", json={"jeton": json.dumps(JETON)})
        assert r.status_code == 200
        cible = secrets / "token.json"
        assert json.loads(cible.read_text())["refresh_token"] == "1//refresh"
        assert stat.S_IMODE(os.stat(cible).st_mode) == 0o600
        assert r.get_json()["jeton"]["present"] is True

    def test_le_precedent_est_conserve(self, connecte, secrets):
        connecte.post("/admin/classeur/jeton", json={"jeton": json.dumps(JETON)})
        autre = dict(JETON, refresh_token="1//nouveau")
        connecte.post("/admin/classeur/jeton", json={"jeton": json.dumps(autre)})
        garde = json.loads((secrets / "token.json.precedent").read_text())
        assert garde["refresh_token"] == "1//refresh"

    @pytest.mark.parametrize("mauvais", [
        "",
        "pas du json",
        '["une", "liste"]',
        '{"token": "ya29.court"}',                      # sans refresh_token
        '{"refresh_token": "1//x", "client_id": "id"}',  # sans client_secret
    ])
    def test_un_jeton_douteux_ne_remplace_rien(self, connecte, secrets, mauvais):
        (secrets / "token.json").write_text(json.dumps(JETON))
        r = connecte.post("/admin/classeur/jeton", json={"jeton": mauvais})
        assert r.status_code == 400
        assert json.loads((secrets / "token.json").read_text()) == JETON

    def test_le_jeton_n_est_pas_renvoye_dans_la_reponse(self, connecte, secrets):
        r = connecte.post("/admin/classeur/jeton", json={"jeton": json.dumps(JETON)})
        assert "1//refresh" not in r.get_data(as_text=True)

    def test_un_corps_vide_donne_400(self, connecte, secrets):
        assert connecte.post("/admin/classeur/jeton").status_code == 400


# --- A13 : qui a le droit ---------------------------------------------------

CHEMINS = [("get", "/admin/classeur", None),
           ("post", "/admin/classeur/test", {"lien": LIEN}),
           ("post", "/admin/classeur", {"lien": LIEN}),
           ("post", "/admin/classeur/jeton", {"jeton": "{}"})]


class TestAcces:

    @pytest.mark.parametrize("methode,chemin,corps", CHEMINS)
    def test_un_organisateur_ne_peut_pas(self, organisateur, jeu, classeur,
                                         methode, chemin, corps):
        """Ces routes décident OÙ vont les données et AVEC QUELLE identité
        Google. L'import, lui, reste organisateur."""
        r = getattr(organisateur, methode)(chemin, json=corps)
        assert r.status_code == 403

    @pytest.mark.parametrize("methode,chemin,corps", CHEMINS)
    def test_sans_session_c_est_401(self, client, secret, jeu, classeur,
                                    methode, chemin, corps):
        r = getattr(client, methode)(chemin, json=corps)
        assert r.status_code == 401

    @pytest.mark.parametrize("methode,chemin,corps", CHEMINS)
    def test_sans_secret_key_la_console_est_fermee(self, client, jeu, classeur,
                                                   methode, chemin, corps):
        """Avec la clé de développement, un cookie de session se forge en trois
        lignes : mieux vaut une console indisponible qu'une console ouverte."""
        r = getattr(client, methode)(chemin, json=corps)
        assert r.status_code == 503


# --- A1→A6 : le test d'accès en ÉCRITURE, vu de la route (spec 018) ---------

class TestTesterEnEcriture:

    def test_par_defaut_rien_n_est_ecrit(self, connecte, jeu, classeur):
        """A6. Le test d'avant n'a pas bougé : il ne fait toujours que lire."""
        r = connecte.post("/admin/classeur/test", json={"lien": LIEN})
        assert r.status_code == 200
        assert r.get_json()["rapport"]["essai_ecriture"] is None
        assert classeur["essais"] == 0

    def test_avec_le_drapeau_l_essai_a_lieu(self, connecte, jeu, classeur):
        """A1. C'est un bouton distinct dans la console : l'un écrit, l'autre
        pas, et ça doit se voir avant de cliquer."""
        r = connecte.post("/admin/classeur/test",
                          json={"lien": LIEN, "ecriture": True})
        assert r.status_code == 200
        essai = r.get_json()["rapport"]["essai_ecriture"]
        assert essai["ecriture"] is True
        assert classeur["essais"] == 1

    def test_un_echec_d_ecriture_remonte_en_avertissement(
            self, connecte, jeu, classeur):
        """A2. Le cas « feuille partagée en lecture seule » : la route répond
        200 — le classeur EST joignable — et l'avertissement dit le reste."""
        classeur["options"]["essai_ecriture"] = {
            "tentee": True, "cellule": "Import!DS60", "ecriture": False,
            "restauree": None, "plages_protegees": [],
            "message": "Google a refuse l'ecriture : partage en lecture seule."}

        r = connecte.post("/admin/classeur/test",
                          json={"lien": LIEN, "ecriture": True})
        assert r.status_code == 200
        rapport = r.get_json()["rapport"]
        assert rapport["essai_ecriture"]["ecriture"] is False
        assert any("lecture seule" in a for a in rapport["avertissements"])

    def test_une_restauration_ratee_remonte_aussi(self, connecte, jeu, classeur):
        """A4."""
        classeur["options"]["essai_ecriture"] = {
            "tentee": True, "cellule": "Import!DS60", "ecriture": True,
            "restauree": False, "plages_protegees": [],
            "message": "La cellule Import!DS60 n'a PAS pu etre effacee."}

        rapport = connecte.post("/admin/classeur/test",
                                json={"lien": LIEN, "ecriture": True}
                                ).get_json()["rapport"]
        assert any("Import!DS60" in a for a in rapport["avertissements"])

    def test_les_plages_protegees_sont_dites_meme_en_lecture(
            self, connecte, jeu, classeur):
        """A5. Gratuit : les métadonnées sont déjà chargées."""
        classeur["options"]["plages_protegees"] = ["Matrice verrouillée"]
        rapport = connecte.post("/admin/classeur/test",
                                json={"lien": LIEN}).get_json()["rapport"]
        assert any("Matrice verrouillée" in a for a in rapport["avertissements"])

    def test_un_organisateur_ne_peut_pas_tester(self, organisateur, jeu, classeur):
        """A13 de la spec 015 : la route reste réservée aux administrateurs."""
        r = organisateur.post("/admin/classeur/test",
                              json={"lien": LIEN, "ecriture": True})
        assert r.status_code == 403
        assert classeur["essais"] == 0
