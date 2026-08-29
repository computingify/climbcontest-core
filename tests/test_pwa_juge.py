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

    def test_la_coquille_n_est_pas_mise_en_cache(self, client_sans_cle):
        """⚠️ Constate en developpant : le navigateur gardait la page precedente
        et ignorait les modifications. En production, ca voudrait dire publier un
        correctif et voir vingt-cinq telephones tourner sur l'ancienne version --
        sans que personne ne comprenne pourquoi le correctif « ne marche pas »."""
        cache = client_sans_cle.get("/juge").headers.get("Cache-Control", "")
        assert "no-cache" in cache

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


class TestLeServiceWorker:
    """IT4. Ce qui rend l'application utilisable sans reseau."""

    def test_il_est_servi_depuis_juge_et_pas_depuis_static(self, client_sans_cle):
        """Sa PORTEE est le dossier d'ou il est servi. Depuis
        `/static/juge/sw.js`, il ne pourrait controler que `/static/juge/` --
        donc pas `/juge`, donc pas l'application."""
        r = client_sans_cle.get("/juge/sw.js")
        assert r.status_code == 200
        assert "javascript" in r.headers["Content-Type"]

    def test_sa_portee_couvre_l_application_elle_meme(self, client_sans_cle):
        """⚠️ Sans cet en-tete, la PWA s'installe mais ne fonctionne JAMAIS hors
        ligne -- et rien ne le dit.

        Par defaut, un script servi depuis `/juge/` ne peut controler que
        `/juge/`, avec la barre finale. Or l'application vit a `/juge`, SANS
        barre, qui n'est pas sous `/juge/`. Le navigateur refuse alors
        l'enregistrement. Trouve en essayant pour de vrai :

            The path of the provided scope ('/juge') is not under the max scope
            allowed ('/juge/').
        """
        r = client_sans_cle.get("/juge/sw.js")
        assert r.headers.get("Service-Worker-Allowed") == "/juge"

    def test_il_n_est_jamais_mis_en_cache(self, client_sans_cle):
        """Un service worker mis en cache est un service worker qu'on ne peut
        plus corriger."""
        cache = client_sans_cle.get("/juge/sw.js").headers.get("Cache-Control", "")
        assert "no-cache" in cache

    def test_il_ne_touche_JAMAIS_aux_appels_api(self):
        """⚠️ La regle la plus importante de ce fichier.

        Un service worker qui rejouerait un POST creerait des doublons ;
        l'idempotence du serveur les absorberait, mais la file du telephone se
        croirait videe pendant qu'une reussite y reste. La file est geree par
        l'application, et elle seule decide de ce qui part.
        """
        sw = (STATIQUE / "sw.js").read_text(encoding="utf-8")
        assert 'requete.method !== "GET"' in sw
        assert 'url.pathname.startsWith("/api/")' in sw

    def test_la_coquille_prechargee_existe_vraiment(self, client_sans_cle):
        """Un chemin errone dans la liste laisserait l'application sans
        hors-ligne, en silence."""
        import re
        sw = (STATIQUE / "sw.js").read_text(encoding="utf-8")
        debut = sw.index("const COQUILLE = [")
        liste = sw[debut:sw.index("]", debut)]
        chemins = re.findall(r'"(/[^"]+)"', liste)
        assert chemins, "la coquille ne doit pas etre vide"
        for chemin in chemins:
            assert client_sans_cle.get(chemin).status_code == 200, chemin

    def test_jsqr_n_est_pas_precharge(self):
        """250 ko qui ne servent qu'a Safari. Les precharger ferait payer a tout
        le monde ce dont seuls certains ont besoin ; il entre au cache au
        premier scan, sur les appareils qui en ont besoin."""
        sw = (STATIQUE / "sw.js").read_text(encoding="utf-8")
        debut = sw.index("const COQUILLE = [")
        assert "jsqr.js" not in sw[debut:sw.index("]", debut)]

    def test_l_echec_d_un_seul_fichier_n_empeche_pas_l_installation(self):
        """`addAll` echoue en bloc si UN fichier manque. Mieux vaut une coquille
        incomplete qu'un service worker qui ne s'installe pas du tout."""
        sw = (STATIQUE / "sw.js").read_text(encoding="utf-8")
        # `.addAll(` et non `addAll` : le mot apparait dans le commentaire qui
        # explique justement pourquoi on ne l'utilise pas.
        assert ".addAll(" not in sw
        assert "cache.add(url).catch" in sw

    def test_son_echec_n_empeche_pas_l_application_de_marcher(self):
        """Un juge dont le navigateur refuse les service workers -- mode prive,
        reglage d'entreprise -- doit pouvoir travailler quand meme."""
        juge = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        assert 'navigator.serviceWorker.register("/juge/sw.js"' in juge
        assert ".catch(" in juge[juge.index("serviceWorker.register"):]


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

    def test_un_nouveau_lien_remet_le_retrait_a_zero(self):
        """Apres une serie de refus, le retrait exponentiel atteint une minute.

        Or l'organisateur envoie un nouveau lien PRECISEMENT pour debloquer la
        situation : faire attendre le juge une minute de plus apres ca n'aurait
        aucun sens, la cause des echecs vient d'etre traitee.

        Verifie a l'ecran : jeton revoque, cinq reussites bloquees, nouveau
        lien, et elles repartent en moins de trois secondes.
        """
        juge = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        assert "echecsConsecutifs = 0" in juge

    def test_le_jeton_voyage_dans_le_fragment_pas_la_requete(self):
        """Un fragment n'est pas envoye au serveur : il n'entre ni dans les
        journaux de Caddy, ni dans ceux de gunicorn, ni dans un `Referer`."""
        jeton = (STATIQUE / "jeton.js").read_text(encoding="utf-8")
        assert "location.search" not in jeton
        assert "fragment" in jeton


class TestLaFileHorsLigne:
    """IT2. Ce qui garantit qu'une reussite validee n'est jamais perdue.

    Le detail se teste sur Node (`tests/js/file.test.mjs`) : ces tests-ci
    verifient seulement que les pieces sont branchees, et surtout que le
    stockage choisi est le bon.
    """

    def test_indexeddb_et_pas_localstorage(self):
        """`localStorage` est synchrone -- il bloque le fil pendant qu'on scanne
        --, plafonne a ~5 Mo, et surtout il ne sait pas faire de TRANSACTION. Or
        l'invariant central est une transaction : retirer de la file exactement
        ce que le serveur a acquitte, tout ou rien."""
        idb = (STATIQUE / "idb.js").read_text(encoding="utf-8")
        assert "indexedDB.open" in idb
        file = (STATIQUE / "file.js").read_text(encoding="utf-8")
        assert "localStorage" not in file

    def test_le_verrou_entre_onglets_existe(self):
        """Un juge peut avoir la PWA installee ET un onglet Safari sur la meme
        adresse ; les deux partagent le meme IndexedDB. Sans bail, les deux
        videraient la file en double."""
        juge = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        assert "peutPrendre" in juge and "bailNeuf" in juge

    def test_les_constantes_d_envoi_sont_celles_de_l_android(self):
        """Deux clients qui envoient au meme rythme font une charge previsible.
        Deux clients qui divergent font une charge qu'on ne sait plus mesurer,
        et les chiffres de la spec 003 ne vaudraient plus rien."""
        politique = (STATIQUE / "politique.js").read_text(encoding="utf-8")
        assert "LOT_PLEIN = 5" in politique
        assert "DELAI_MS = 10_000" in politique
        assert "LOT_MAX = 50" in politique
        assert "RETRAIT_MAX_MS = 60_000" in politique


class TestLaMiseAJourAtteintLesTelephones:
    """Une PWA se met a jour toute seule -- a condition qu'on la laisse.

    Trois pieges rencontres en developpant, et les trois auraient donne la meme
    chose en production : publier un correctif et voir vingt-cinq telephones
    continuer sur l'ancienne version, sans que personne ne comprenne pourquoi.
    """

    def test_les_fichiers_statiques_sont_revalides(self, client_sans_cle, app):
        """Par defaut Flask les annonce cachables douze heures."""
        assert app.config["SEND_FILE_MAX_AGE_DEFAULT"] == 0
        r = client_sans_cle.get("/static/juge/juge.js")
        assert "no-cache" in r.headers.get("Cache-Control", "")
        # Un ETag reste envoye : la revalidation coute un 304 de quelques octets.
        assert r.headers.get("ETag")

    def test_le_catalogue_range_porte_un_marqueur_de_format(self):
        """Un telephone peut recevoir un nouveau code en gardant un catalogue
        range par l'ancien. Le serveur repondant 304 tant que la version ne
        bouge pas, il ne serait JAMAIS remplace -- et le juge scannerait dans le
        vide jusqu'a la competition suivante."""
        cat = (STATIQUE / "catalogue.js").read_text(encoding="utf-8")
        assert "export const FORMAT" in cat
        assert "donnees.format !== FORMAT" in cat


class TestLeCatalogueALaFormeDuServeur:
    """⚠️ Le defaut le plus couteux de cette spec, et il n'a ete vu qu'en
    parlant au VRAI serveur.

    J'avais ecrit le module en supposant que `/api/v2/catalog` renvoyait des
    dictionnaires dossard -> nom. Il renvoie des TABLEAUX d'objets. Le catalogue
    local ne correspondait donc jamais, et chaque scan repassait par le reseau --
    exactement ce que l'iteration pretendait supprimer. Mes tests d'alors
    verifiaient ma classe contre ma propre supposition.
    """

    def test_la_route_renvoie_bien_des_tableaux(self, client, jeu):
        """Le contrat, ecrit noir sur blanc : si le serveur change de forme, ce
        test tombe AVANT que la PWA ne se taise en silence."""
        d = client.get("/api/v2/catalog").get_json()
        assert isinstance(d["participants"], list)
        assert isinstance(d["blocs"], list)
        assert {"dossard", "nom"} <= set(d["participants"][0])
        assert "tag" in d["blocs"][0]

    def test_la_pwa_lit_cette_forme_la(self):
        cat = (STATIQUE / "catalogue.js").read_text(encoding="utf-8")
        assert "depuisReponseServeur" in cat
        assert "Array.isArray(corps.participants)" in cat


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
