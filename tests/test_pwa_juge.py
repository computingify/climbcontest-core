"""La PWA juge (spec 007).

Un benevole qui arrive avec un iPhone ne peut pas juger : l'application est
Android, et l'App Store coute 99 $/an. Cette PWA leve la contrainte.

Ce que ces tests protegent, et c'est la partie qu'on ne peut PAS verifier a
l'ecran : que rien de secret ne parte dans une page publique, et que rien ne
soit charge depuis un serveur tiers le matin d'une competition.

⚠️ Le scan lui-meme ne se teste pas ici. Il demande une camera, Safari iOS, et
un vrai iPhone -- c'est le point du plan de test qui revient a Adrien.
"""
import json
import re
from pathlib import Path

import pytest

STATIQUE = Path(__file__).resolve().parents[1] / "climbcontest" / "static" / "juge"


class TestLaPageEstServie:

    def test_la_coquille_repond(self, client_sans_cle):
        r = client_sans_cle.get("/juge")
        assert r.status_code == 200
        assert r.headers["Content-Type"].startswith("text/html")

    def test_avec_ou_sans_barre_finale(self, client_sans_cle):
        assert client_sans_cle.get("/juge/").status_code == 200

    def test_elle_est_publique(self, client_sans_cle):
        """Volontairement : une coquille ne contient aucun secret, et un
        service worker ne s'installe pas depuis une page protegee par un
        cookie. Ce qui est garde, c'est l'API."""
        assert client_sans_cle.get("/juge").status_code == 200

    def test_le_manifeste_est_servi_avec_le_bon_type(self, client_sans_cle):
        r = client_sans_cle.get("/juge/manifest.webmanifest")
        assert r.status_code == 200
        assert "manifest" in r.headers["Content-Type"]
        d = json.loads(r.get_data(as_text=True))
        # `scope` decide de ce que la PWA controle une fois installee. Trop
        # large, elle avalerait la console et la page de resultats.
        assert d["scope"] == "/juge"
        assert d["start_url"] == "/juge"
        assert d["display"] == "standalone"

    def test_les_icones_du_manifeste_existent(self, client_sans_cle):
        d = json.loads(client_sans_cle.get("/juge/manifest.webmanifest")
                       .get_data(as_text=True))
        for icone in d["icons"]:
            r = client_sans_cle.get(icone["src"])
            assert r.status_code == 200, icone["src"]


class TestRienNeFuit:
    """La page est publique. Tout ce qu'elle contient l'est aussi."""

    def test_aucun_secret_dans_la_page(self, client, jeu, app):
        page = client.get("/juge").get_data(as_text=True)
        assert app.config["API_KEYS"][0] not in page
        assert "cle-de-test" not in page
        assert app.config["SECRET_KEY"] not in page

    def test_aucune_donnee_de_competition(self, client, jeu):
        """Tout arrive par l'API, qui exige une cle. La page, elle, ne sait rien."""
        page = client.get("/juge").get_data(as_text=True)
        for participant in jeu["participants"]:
            assert participant.nom not in page

    def test_aucune_ressource_exterieure(self, client_sans_cle):
        """Meme regle que la page de resultats et la console : rien ne doit
        dependre d'un CDN le matin d'une competition."""
        page = client_sans_cle.get("/juge").get_data(as_text=True)
        externes = [u for u in re.findall(r'https?://[^\s"\'<>)]+', page)
                    if not u.startswith("http://www.w3.org/")]
        assert not externes, f"ressources externes : {externes}"

    def test_les_scripts_aussi_sont_locaux(self):
        for fichier in STATIQUE.glob("*.js"):
            if fichier.name == "jsqr.js":
                continue      # bibliotheque versee, verifiee a part
            texte = fichier.read_text(encoding="utf-8", errors="replace")
            externes = [u for u in re.findall(r'https?://[^\s"\'<>)]+', texte)
                        if not u.startswith(("http://www.w3.org/",
                                             "https://github.com/cozmo/jsQR",
                                             "http://www.apache.org/"))]
            assert not externes, f"{fichier.name} : {externes}"


class TestLaBibliothequeVersee:
    """jsQR est copie dans le depot. Ce qui entre dans un depot public doit etre
    trace : provenance, version, licence."""

    def test_elle_est_la(self):
        assert (STATIQUE / "jsqr.js").exists()

    def test_sa_licence_est_versee_a_cote(self):
        licence = (STATIQUE / "jsqr-LICENSE.txt").read_text(encoding="utf-8")
        assert "Apache License" in licence

    def test_son_entete_dit_d_ou_elle_vient(self):
        entete = (STATIQUE / "jsqr.js").read_text(
            encoding="utf-8", errors="replace")[:1200]
        assert "github.com/cozmo/jsQR" in entete
        assert "1.4.0" in entete
        assert "Apache-2.0" in entete

    def test_elle_n_est_pas_minifiee(self):
        """Une bibliotheque illisible dans un depot public est une bibliotheque
        que personne ne relira jamais."""
        texte = (STATIQUE / "jsqr.js").read_text(encoding="utf-8", errors="replace")
        assert texte.count("\n") > 1000

    def test_elle_n_est_pas_chargee_quand_le_navigateur_sait_faire(self):
        """250 ko qui ne partent jamais sur Chrome Android."""
        scan = (STATIQUE / "scan.js").read_text(encoding="utf-8")
        assert "BarcodeDetector" in scan
        assert "chargerJsQR" in scan


class TestLeNouveauLien:
    """Un jeton revoque se remplace en envoyant un nouveau lien.

    ⚠️ Constate a l'ecran, et rien ne le laissait deviner : passer de `/juge` a
    `/juge#j=autre` est une navigation DANS LE MEME DOCUMENT. Le navigateur ne
    recharge rien, le module ne repart pas, et le jeton n'etait pas remplace.

    C'est exactement le geste qu'on ferait si un jeton fuitait en pleine
    competition. Ce test garde le branchement en place.
    """

    def test_le_changement_de_fragment_est_ecoute(self):
        juge = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        assert "hashchange" in juge

    def test_l_adresse_est_nettoyee_apres_lecture(self):
        """Sinon le jeton reste dans la barre d'adresse, dans l'historique, et
        dans la capture d'ecran que quelqu'un fera pour montrer l'application."""
        juge = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        assert "replaceState" in juge

    def test_le_jeton_voyage_dans_le_fragment_pas_la_requete(self):
        """Un fragment n'est pas envoye au serveur : il n'entre ni dans les
        journaux de Caddy, ni dans ceux de gunicorn, ni dans un `Referer`."""
        jeton = (STATIQUE / "jeton.js").read_text(encoding="utf-8")
        assert "location.search" not in jeton
        assert "fragment" in jeton


class TestLaCleDeLaPwa:

    def test_elle_entre_dans_les_cles_acceptees(self):
        from climbcontest.config import cles_depuis_environnement as lire
        assert lire({"CLIMBCONTEST_API_KEY_PWA": "jeton-pwa"}) == ("jeton-pwa",)

    def test_elle_est_distincte_de_celle_de_l_android(self):
        """Les separer permet de revoquer la PWA sans toucher aux telephones
        Android -- et le jeton de la PWA se promene plus, puisqu'il voyage dans
        un lien qu'on donne aux benevoles."""
        from climbcontest.config import cles_depuis_environnement as lire
        cles = lire({"CLIMBCONTEST_API_KEY": "android",
                     "CLIMBCONTEST_API_KEY_PWA": "pwa"})
        assert cles == ("android", "pwa")

    def test_une_cle_pwa_vide_n_ouvre_rien(self):
        from climbcontest.config import cles_depuis_environnement as lire
        assert lire({"CLIMBCONTEST_API_KEY_PWA": ""}) == ()
