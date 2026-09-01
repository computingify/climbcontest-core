"""Le consentement Google depuis la console — spec 022.

⚠️ **Aucun test ne parle à Google.** Le `Flow` est remplacé par un double ;
l'échange réel se vérifie une fois, à la main, quand l'URI de retour est
déclarée dans la Google Cloud Console.

Ce qui est protégé ici tient en trois lignes : le `state` (sans lui, n'importe
quel site pourrait faire aboutir chez nous un code obtenu ailleurs, et poser SON
compte Google comme identité du serveur), le `refresh_token` (sans lui le jeton
meurt à la première expiration, et la panne se découvre le lendemain matin), et
le fait que **rien du jeton ne sorte** — ni journal, ni réponse, ni URL.
"""
import json

import pytest

from climbcontest import comptes
from climbcontest.contest import ErreurMetier
from climbcontest.sheets import client, consentement

MDP = "un-mot-de-passe-assez-long"

CREDENTIALS = {
    "web": {
        "client_id": "faux-client.apps.googleusercontent.com",
        "project_id": "faux-projet",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_secret": "faux-secret",
    }
}


@pytest.fixture()
def secrets_dir(app, tmp_path, monkeypatch):
    """Un dossier de secrets jetable. Rien n'est écrit ailleurs."""
    monkeypatch.setitem(app.config, "DOSSIER_SECRETS", str(tmp_path))
    monkeypatch.delenv("CLIMBCONTEST_SECRETS_DIR", raising=False)
    return tmp_path


@pytest.fixture()
def avec_credentials(secrets_dir):
    (secrets_dir / "credentials.json").write_text(json.dumps(CREDENTIALS))
    return secrets_dir


class FauxFlow:
    """Le double de `google_auth_oauthlib.flow.Flow`.

    Il note ce qu'on lui demande : c'est la seule façon de vérifier
    `prompt=consent` sans appeler Google.
    """

    dernier = None

    def __init__(self, jeton=None, casse=False, uri=None):
        # `_flux` est remplace en entier : c'est donc au double de porter l'URI
        # que la vraie fonction aurait posee.
        self.redirect_uri = uri
        self.arguments = None
        self.code = None
        self._jeton = jeton if jeton is not None else {
            "token": "ya29.faux", "refresh_token": "1//faux",
            "client_id": "faux", "client_secret": "faux",
            "scopes": consentement.SCOPES,
        }
        self._casse = casse
        FauxFlow.dernier = self

    def authorization_url(self, **arguments):
        self.arguments = arguments
        return ("https://accounts.google.com/o/oauth2/auth?tout=ce-qu-il-faut",
                arguments.get("state"))

    def fetch_token(self, code=None):
        self.code = code
        if self._casse:
            raise RuntimeError("invalid_grant: code deja utilise")

    @property
    def credentials(self):
        return type("Creds", (), {"to_json": lambda _: json.dumps(self._jeton)})()


@pytest.fixture()
def faux_flux(monkeypatch):
    """Remplace le montage du `Flow` par notre double."""
    def poser(jeton=None, casse=False):
        monkeypatch.setattr(consentement, "_flux",
                            lambda uri: FauxFlow(jeton=jeton, casse=casse, uri=uri))
    return poser


# --- credentials.json -------------------------------------------------------

class TestOnSaitSiOnPeutDemanderLeConsentement:

    def test_present_et_bien_forme(self, avec_credentials):
        etat = consentement.disponible()
        assert etat["pret"] is True
        assert etat["chemin"].endswith("credentials.json")

    def test_absent(self, secrets_dir):
        """Un état NORMAL d'une installation neuve, pas une panne."""
        etat = consentement.disponible()
        assert etat["pret"] is False
        assert "credentials.json" in etat["message"]
        assert str(secrets_dir) in etat["message"]

    def test_illisible(self, secrets_dir):
        (secrets_dir / "credentials.json").write_text("{ pas du json")
        etat = consentement.disponible()
        assert etat["pret"] is False
        assert "illisible" in etat["message"]

    def test_json_valide_mais_pas_un_client_oauth(self, secrets_dir):
        (secrets_dir / "credentials.json").write_text('{"autre": 1}')
        etat = consentement.disponible()
        assert etat["pret"] is False
        assert "web" in etat["message"]

    def test_aucune_de_ces_lectures_ne_leve(self, secrets_dir):
        """La console doit pouvoir afficher son état quoi qu'il arrive."""
        for contenu in ("", "[]", "null", '{"installed": {}}'):
            (secrets_dir / "credentials.json").write_text(contenu)
            assert isinstance(consentement.disponible(), dict)


# --- L'URL de consentement --------------------------------------------------

class TestLUrlDeConsentement:

    def test_elle_demande_ce_qu_il_faut(self, avec_credentials, faux_flux):
        faux_flux()
        url, etat = consentement.url_de_consentement("https://exemple/retour")
        assert url.startswith("https://accounts.google.com/")
        arguments = FauxFlow.dernier.arguments
        assert arguments["access_type"] == "offline"
        assert arguments["include_granted_scopes"] == "true"
        assert arguments["state"] == etat

    def test_prompt_consent_est_obligatoire(self, avec_credentials, faux_flux):
        """LE piège. Sans lui, Google ne redonne PAS de refresh_token à un
        compte qui a déjà consenti : on reposerait un jeton qui meurt dans
        l'heure, et la panne se découvrirait le lendemain matin."""
        faux_flux()
        consentement.url_de_consentement("https://exemple/retour")
        assert FauxFlow.dernier.arguments["prompt"] == "consent"

    def test_l_uri_de_retour_est_transmise_telle_quelle(self, avec_credentials,
                                                        faux_flux):
        """Google l'exige au caractère près."""
        faux_flux()
        consentement.url_de_consentement("https://exemple/admin/retour")
        assert FauxFlow.dernier.redirect_uri == "https://exemple/admin/retour"

    def test_le_scope_est_spreadsheets_et_rien_de_plus(self):
        """Pas de Drive : le jeton n'a jamais eu à lister ni supprimer des
        fichiers."""
        assert consentement.SCOPES == [
            "https://www.googleapis.com/auth/spreadsheets"]

    def test_deux_appels_donnent_deux_etats_differents(self, avec_credentials,
                                                       faux_flux):
        faux_flux()
        _, a = consentement.url_de_consentement("https://exemple/retour")
        _, b = consentement.url_de_consentement("https://exemple/retour")
        assert a != b
        assert len(a) >= 32

    def test_sans_credentials_ca_refuse_proprement(self, secrets_dir):
        with pytest.raises(ErreurMetier) as leve:
            consentement.url_de_consentement("https://exemple/retour")
        assert leve.value.code == 409


# --- L'échange --------------------------------------------------------------

class TestLEchange:

    def test_un_jeton_complet_est_rendu(self, avec_credentials, faux_flux):
        faux_flux()
        rendu = json.loads(consentement.echanger("code-google",
                                                 "https://exemple/retour"))
        assert rendu["refresh_token"] == "1//faux"
        assert FauxFlow.dernier.code == "code-google"

    def test_sans_refresh_token_c_est_refuse(self, avec_credentials, faux_flux):
        """Même garde que le collage (spec 015) : un jeton sans rafraîchissement
        meurt à la première expiration."""
        faux_flux(jeton={"token": "ya29.faux", "client_id": "x"})
        with pytest.raises(ErreurMetier) as leve:
            consentement.echanger("code", "https://exemple/retour")
        assert "refresh_token" in leve.value.message

    def test_un_code_vide_est_refuse_avant_tout_appel(self, avec_credentials,
                                                      faux_flux):
        faux_flux()
        with pytest.raises(ErreurMetier):
            consentement.echanger("   ", "https://exemple/retour")

    def test_un_refus_de_google_devient_un_message_lisible(self, avec_credentials,
                                                           faux_flux):
        """Le message brut de Google est journalisé, pas renvoyé : il est
        parfois bavard et contient l'URI complète."""
        faux_flux(casse=True)
        with pytest.raises(ErreurMetier) as leve:
            consentement.echanger("code", "https://exemple/retour")
        assert leve.value.code == 502
        assert "invalid_grant" not in leve.value.message


# --- Le state ---------------------------------------------------------------

class TestLeStateFermeLaPorte:

    def test_identiques_ca_passe(self):
        consentement.verifier_etat("abc", "abc")

    @pytest.mark.parametrize("attendu,recu", [
        (None, "abc"), ("abc", None), ("abc", "def"), ("", ""), (None, None),
    ])
    def test_tout_le_reste_est_refuse(self, attendu, recu):
        with pytest.raises(ErreurMetier):
            consentement.verifier_etat(attendu, recu)


# --- Les routes -------------------------------------------------------------

@pytest.fixture()
def admin(client, app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("chef", MDP, [comptes.ADMIN])
    client.post("/admin/connexion", json={"identifiant": "chef", "mot_de_passe": MDP})
    return client


@pytest.fixture()
def orga(client, app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("benevole", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion",
                json={"identifiant": "benevole", "mot_de_passe": MDP})
    return client


class TestLesRoutesSontReservees:

    def test_anonyme(self, client, app):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/classeur/google/consentement").status_code == 401
        assert client.get("/admin/classeur/google/retour").status_code == 401

    def test_organisateur(self, orga):
        assert orga.get("/admin/classeur/google/consentement").status_code == 403
        assert orga.get("/admin/classeur/google/retour").status_code == 403


class TestLAllerChezGoogle:

    def test_redirige_et_range_le_state(self, admin, avec_credentials, faux_flux):
        faux_flux()
        r = admin.get("/admin/classeur/google/consentement")
        assert r.status_code == 302
        assert r.headers["Location"].startswith("https://accounts.google.com/")
        with admin.session_transaction() as s:
            assert len(s[consentement.CLE_ETAT]) >= 32

    def test_le_state_ne_sort_jamais_dans_la_reponse(self, admin, avec_credentials,
                                                     faux_flux):
        faux_flux()
        r = admin.get("/admin/classeur/google/consentement")
        with admin.session_transaction() as s:
            etat = s[consentement.CLE_ETAT]
        # Il est dans l'URL de Google (c'est son role) mais pas dans le corps.
        assert etat not in r.data.decode()

    def test_sans_credentials_le_bouton_repond_409(self, admin, secrets_dir):
        r = admin.get("/admin/classeur/google/consentement")
        assert r.status_code == 409
        assert "credentials.json" in r.get_json()["message"]


class TestLeRetour:

    @staticmethod
    def _armer(client_, etat="abc"):
        with client_.session_transaction() as s:
            s[consentement.CLE_ETAT] = etat

    def test_nominal(self, admin, avec_credentials, faux_flux, secrets_dir):
        faux_flux()
        self._armer(admin)
        r = admin.get("/admin/classeur/google/retour?state=abc&code=xyz")
        assert r.status_code == 302
        assert r.headers["Location"] == "/console?jeton=pose"
        pose = json.loads((secrets_dir / "token.json").read_text())
        assert pose["refresh_token"] == "1//faux"

    def test_l_ancien_jeton_est_conserve(self, admin, avec_credentials, faux_flux,
                                         secrets_dir):
        """Non-régression de la spec 015 : un jeton écrasé par erreur se
        rattrape depuis la console suivante, sans SSH."""
        (secrets_dir / "token.json").write_text('{"refresh_token": "ancien"}')
        faux_flux()
        self._armer(admin)
        admin.get("/admin/classeur/google/retour?state=abc&code=xyz")
        garde = json.loads((secrets_dir / "token.json.precedent").read_text())
        assert garde["refresh_token"] == "ancien"

    def test_state_absent_n_ecrit_rien(self, admin, avec_credentials, faux_flux,
                                       secrets_dir):
        faux_flux()
        r = admin.get("/admin/classeur/google/retour?state=abc&code=xyz")
        assert r.headers["Location"].startswith("/console?jeton=erreur")
        assert not (secrets_dir / "token.json").exists()

    def test_state_different_n_ecrit_rien(self, admin, avec_credentials, faux_flux,
                                          secrets_dir):
        faux_flux()
        self._armer(admin, "attendu")
        r = admin.get("/admin/classeur/google/retour?state=autre&code=xyz")
        assert r.headers["Location"].startswith("/console?jeton=erreur")
        assert not (secrets_dir / "token.json").exists()

    def test_le_state_ne_se_rejoue_pas(self, admin, avec_credentials, faux_flux,
                                       secrets_dir):
        """Un code d'autorisation ne se rejoue pas, et le `state` non plus : il
        est retiré de la session dès la première lecture."""
        faux_flux()
        self._armer(admin)
        premier = admin.get("/admin/classeur/google/retour?state=abc&code=xyz")
        second = admin.get("/admin/classeur/google/retour?state=abc&code=xyz")
        assert premier.headers["Location"] == "/console?jeton=pose"
        assert second.headers["Location"].startswith("/console?jeton=erreur")

    def test_consentement_refuse(self, admin, avec_credentials, secrets_dir):
        """Ce n'est pas une panne, c'est une réponse."""
        self._armer(admin)
        r = admin.get("/admin/classeur/google/retour?error=access_denied&state=abc")
        assert r.headers["Location"] == "/console?jeton=refuse"
        assert not (secrets_dir / "token.json").exists()

    def test_sans_refresh_token_rien_n_est_ecrit(self, admin, avec_credentials,
                                                 faux_flux, secrets_dir):
        faux_flux(jeton={"token": "ya29.faux"})
        self._armer(admin)
        r = admin.get("/admin/classeur/google/retour?state=abc&code=xyz")
        assert r.headers["Location"].startswith("/console?jeton=erreur")
        assert not (secrets_dir / "token.json").exists()

    def test_le_jeton_ne_part_jamais_dans_l_url(self, admin, avec_credentials,
                                                faux_flux):
        faux_flux()
        self._armer(admin)
        r = admin.get("/admin/classeur/google/retour?state=abc&code=xyz")
        assert "1//faux" not in r.headers["Location"]
        assert "ya29" not in r.headers["Location"]

    def test_le_journal_nomme_l_auteur_pas_le_jeton(self, admin, avec_credentials,
                                                    faux_flux, caplog):
        faux_flux()
        self._armer(admin)
        with caplog.at_level("INFO"):
            admin.get("/admin/classeur/google/retour?state=abc&code=xyz")
        journal = caplog.text
        assert "chef" in journal
        assert "1//faux" not in journal and "ya29" not in journal


class TestCeQueLaConsoleAffiche:

    def test_l_etat_porte_le_consentement(self, admin, avec_credentials, competition):
        jeton = admin.get("/admin/classeur").get_json()["jeton"]
        assert jeton["consentement"]["pret"] is True
        assert jeton["consentement"]["uri_retour"].endswith(
            "/admin/classeur/google/retour")

    def test_sans_credentials_le_bouton_se_desactive(self, admin, secrets_dir,
                                                     competition):
        jeton = admin.get("/admin/classeur").get_json()["jeton"]
        assert jeton["consentement"]["pret"] is False
        assert jeton["consentement"]["message"]

    def test_l_uri_de_retour_est_celle_que_la_route_construit(self, admin,
                                                              avec_credentials,
                                                              competition):
        """Elle s'affiche dans la console pour être copiée chez Google : si les
        deux divergeaient, on déclarerait une URI qui ne sert jamais."""
        from climbcontest.routes.admin import uri_de_retour
        with admin.application.test_request_context("/", base_url="http://localhost"):
            attendue = uri_de_retour()
        jeton = admin.get("/admin/classeur").get_json()["jeton"]
        assert jeton["consentement"]["uri_retour"] == attendue


class TestLeCollageResteUnRepli:
    """Le flux OAuth dépend de trois choses hors de notre code. S'il lâche le
    matin de la compétition, le serveur doit garder un moyen de recevoir un
    jeton — sinon les réussites s'empilent toute la journée.
    """

    def test_la_route_de_collage_existe_toujours(self, admin, secrets_dir):
        jeton = json.dumps({"refresh_token": "1//x", "client_id": "a",
                            "client_secret": "b", "token": "ya29.x"})
        r = admin.post("/admin/classeur/jeton", json={"jeton": jeton})
        assert r.status_code == 200
        assert (secrets_dir / "token.json").exists()

    def test_le_message_d_erreur_du_client_mene_a_la_console(self):
        """Il disait « refaire le consentement depuis une machine avec
        navigateur » — une consigne que rien ne permettait d'exécuter."""
        import inspect
        # La chaine est coupee sur deux lignes dans la source : on recolle.
        source = " ".join(
            inspect.getsource(client.ClasseurGoogle._identifiants).split())
        assert "Connecter le " in source and "compte Google" in source
        assert "machine avec navigateur" not in source
