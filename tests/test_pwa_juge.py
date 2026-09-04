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


class TestHiddenCacheVraiment:
    """La regle de cascade qui a laisse un bouton mort sur l'ecran Reglages.

    Une regle d'AUTEUR qui pose `display` bat le `[hidden] { display: none }`
    de la feuille du NAVIGATEUR : l'origine auteur l'emporte sur l'origine
    agent-utilisateur, quelle que soit la specificite. Sept rustines locales
    corrigeaient le defaut element par element, et il en manquait toujours une
    -- `.ligne { display: flex }` rendait `#ligneRefus` visible en permanence,
    donc « 0 refusees » et un bouton « Renvoyer » qui ne fait rien.

    Le COMPORTEMENT se verifie dans un vrai navigateur
    (`test_navigateur_juge_reglages.py`) ; ce test-ci garde la regle, et tourne
    meme sans navigateur installe.
    """

    def test_la_regle_globale_est_la(self, client_sans_cle):
        page = client_sans_cle.get("/juge").get_data(as_text=True)
        assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", page), (
            "la regle globale `[hidden] { display: none !important }` a "
            "disparu : n'importe quelle regle posant `display` rendra a "
            "nouveau visible un element cache")

    def test_aucune_rustine_locale_ne_revient(self, client_sans_cle):
        """Une rustine par element, c'est le motif qui a produit le defaut.

        Elle donne l'impression que le sujet est traite, et laisse le prochain
        `display` sans garde. La regle globale les rend toutes inutiles ; si
        l'une reapparait, c'est que quelqu'un a retrouve le defaut sans
        retrouver sa cause.
        """
        page = client_sans_cle.get("/juge").get_data(as_text=True)
        style = page.split("</style>")[0]
        rustines = re.findall(r"^\s*([#.]?[\w.-]+)\[hidden\]\s*\{", style, re.M)
        assert not rustines, (
            f"rustines locales revenues : {rustines} — la regle globale "
            "`[hidden]` les couvre deja")


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


class TestJetonDansLeLien:
    """Le jeton survit a l'installation (spec 014).

    Le defaut corrige : `start_url` valait « /juge » nu, donc l'application
    lancee depuis son icone ne pouvait retrouver sa cle que dans son stockage
    local. Sur iPhone, ce stockage est cloisonne -- separe de Safari : elle
    demarrait vide et affichait « cette application a besoin du lien fourni par
    l'organisateur ».
    """

    def test_le_manifeste_nu_est_inchange(self, client_sans_cle):
        """Sans jeton, la reponse doit etre EXACTEMENT celle d'avant.

        Un visiteur de passage, un robot d'indexation ou un navigateur qui
        demande le manifeste sans contexte ne doivent rien voir d'anormal.
        """
        d = json.loads(client_sans_cle.get("/juge/manifest.webmanifest")
                       .get_data(as_text=True))
        assert d["start_url"] == "/juge"
        assert d["scope"] == "/juge"

    def test_le_jeton_entre_dans_start_url(self, client_sans_cle):
        """Le coeur du correctif : c'est de la que l'application installee
        tirera sa cle, a chaque lancement."""
        d = json.loads(client_sans_cle.get("/juge/manifest.webmanifest?j=ABC123")
                       .get_data(as_text=True))
        assert d["start_url"] == "/juge?j=ABC123"

    def test_le_scope_reste_nu(self, client_sans_cle):
        """`scope` est le PERIMETRE de l'application, pas son point d'entree.

        Porteur d'une requete, il restreindrait l'application a cette seule
        adresse -- et la navigation sortirait du scope des le premier ecran.
        """
        d = json.loads(client_sans_cle.get("/juge/manifest.webmanifest?j=ABC123")
                       .get_data(as_text=True))
        assert d["scope"] == "/juge"

    def test_un_jeton_vide_vaut_pas_de_jeton(self, client_sans_cle):
        d = json.loads(client_sans_cle.get("/juge/manifest.webmanifest?j=")
                       .get_data(as_text=True))
        assert d["start_url"] == "/juge"

    def test_le_jeton_est_echappe(self, client_sans_cle):
        """Sans echappement, un `&` couperait l'adresse en deux parametres et le
        jeton arriverait tronque -- l'application repondrait 401 sans dire
        pourquoi."""
        r = client_sans_cle.get("/juge/manifest.webmanifest?j=a b%26c")
        d = json.loads(r.get_data(as_text=True))
        assert d["start_url"] == "/juge?j=a%20b%26c"

    def test_le_manifeste_reste_du_json_valide(self, client_sans_cle):
        """Le gabarit est commente en Jinja : les commentaires doivent DISPARAITRE
        au rendu, sinon le JSON est casse et l'installation echoue."""
        r = client_sans_cle.get("/juge/manifest.webmanifest?j=ABC123")
        assert "manifest" in r.headers["Content-Type"]
        texte = r.get_data(as_text=True)
        assert "{#" not in texte and "#}" not in texte
        json.loads(texte)                      # leve si le rendu a casse le JSON

    def test_la_coquille_transmet_le_jeton_au_manifeste(self, client_sans_cle):
        """C'est CE manifeste-la que le navigateur lit quand il propose
        d'installer. Sans le suffixe, il lirait le manifeste nu et
        l'installation naitrait sans jeton."""
        html = client_sans_cle.get("/juge?j=ABC123").get_data(as_text=True)
        assert 'href="/juge/manifest.webmanifest?j=ABC123"' in html

    def test_la_coquille_sans_jeton_lie_le_manifeste_nu(self, client_sans_cle):
        html = client_sans_cle.get("/juge").get_data(as_text=True)
        assert 'href="/juge/manifest.webmanifest"' in html

    def test_le_service_worker_ne_met_pas_le_manifeste_en_cache(self, client_sans_cle):
        """Mis en cache sous une URL fixe, il servirait le manifeste d'un AUTRE
        jeton -- ou un manifeste nu a une application qui en attend un porteur."""
        sw = client_sans_cle.get("/juge/sw.js").get_data(as_text=True)
        debut = sw.index("const COQUILLE")
        assert "manifest.webmanifest" not in sw[debut:sw.index("]", debut)]


class TestLEnTeteDeLApplication:
    """« La roue de configuration, son logo ne va pas avec le reste, trouve une
    roue plus sobre et simple. En plus je veux que ce logo soit celui de tout à
    droite. » — Adrien, 03/09 (spec 033, R9).

    Deux défauts en un : « ⚙ » (U+2699) est un caractère à présentation EMOJI —
    il sort en couleur sur iOS et Android, dans un style qui n'est pas celui du
    voyant juste à côté — et il était placé AVANT le voyant, donc ce n'est pas
    lui qui terminait la barre.

    ⚠️ La PWA seulement : « on parle uniquement de la PWA, car l'app Android va
    être supprimée » (Adrien, 03/09).
    """

    @pytest.fixture()
    def entete(self, client_sans_cle):
        page = client_sans_cle.get("/juge").data.decode()
        return page.split("<header>")[1].split("</header>")[0]

    def test_l_engrenage_n_est_plus_un_caractere(self, entete):
        """Dans le BOUTON : le commentaire cite le caractère qu'on a retiré, et
        c'est lui qui empêchera de le remettre."""
        bouton = entete.split('id="ouvrirReglages"')[1].split("</button>")[0]
        assert "⚙" not in bouton, bouton

    def test_il_est_dessine_au_MEME_trait_que_le_voyant(self, entete):
        bouton = entete.split('id="ouvrirReglages"')[1].split("</button>")[0]
        assert "<svg" in bouton, bouton
        assert 'stroke-width="2.1"' in bouton, bouton
        assert 'stroke="currentColor"' in bouton, bouton

    def test_il_est_le_DERNIER_element_de_la_barre(self, entete):
        assert entete.index('id="ouvrirReglages"') > entete.index('id="voyant"'), (
            "l'engrenage doit terminer la barre, a la droite du voyant")
        apres = entete.split('id="ouvrirReglages"')[1]
        assert "<button" not in apres and "<svg id=" not in apres, apres

    def test_il_a_la_meme_taille_que_le_voyant(self, client_sans_cle):
        """Deux icônes voisines de tailles différentes se lisent comme deux
        composants sans rapport."""
        page = client_sans_cle.get("/juge").data.decode()
        assert "#ouvrirReglages svg { display: block; width: 22px; height: 22px; }" in page
        assert "#voyant { width: 22px; height: 22px; }" in page


class TestLeNomDuPosteEstAffiche:
    """« Il faut que si le nom du téléphone est setté, il faut l'afficher en
    haut de l'application mobile. » — Adrien, 03/09.

    Le nom désigne un ENDROIT de la salle (« Mur jaune »), jamais une personne :
    c'est la règle d'`identite.js`, et c'est ce nom que la console affiche à
    côté des réussites.
    """

    def test_l_emplacement_existe_et_part_masque(self, client_sans_cle):
        entete = client_sans_cle.get("/juge").data.decode() \
            .split("<header>")[1].split("</header>")[0]
        assert 'id="nomPoste" hidden' in entete, entete

    def test_il_se_pose_au_demarrage_ET_au_renommage(self):
        js = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        assert "function afficherLeNomDuPoste()" in js
        # Au demarrage : sinon le nom n'apparait qu'apres etre passe par les
        # reglages, c'est-a-dire jamais pour un poste deja nomme.
        assert js.count("afficherLeNomDuPoste();") >= 2, js.count(
            "afficherLeNomDuPoste();")

    def test_un_poste_sans_nom_ne_laisse_pas_de_trou(self):
        js = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        corps = js.split("function afficherLeNomDuPoste()")[1].split("\n}")[0]
        assert "noeud.hidden = !nom;" in corps, corps

    def test_le_nom_n_est_jamais_du_balisage(self):
        """Il est saisi à la main dans les réglages du téléphone."""
        js = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        corps = js.split("function afficherLeNomDuPoste()")[1].split("\n}")[0]
        assert "textContent" in corps and "innerHTML" not in corps


class TestLaCategorieSurLaCarteDuGrimpeur:
    """« Quand on scanne le grimpeur, on voit son nom prénom, tu as mis aussi
    son dossard, mais il faudrait aussi que tu mettes sa catégorie. En plus
    gros, je veux dire la taille du nom prénom. […] Je la verrais bien plutôt
    sur la partie droite de la case grimpeur. » — Adrien, 03/09 (spec 033, R10).
    """

    @pytest.fixture()
    def page(self, client_sans_cle):
        return client_sans_cle.get("/juge").data.decode()

    def test_la_carte_a_une_colonne_de_droite(self, page):
        carte = page.split('id="carteGrimpeur"')[1].split("</button>")[0]
        assert 'id="categorieGrimpeur"' in carte, carte
        # L'identite a gauche, la categorie a droite : c'est l'ordre du DOM.
        assert carte.index('class="identite"') < carte.index('id="categorieGrimpeur"')

    def test_elle_est_a_LA_TAILLE_DU_NOM(self, page):
        """Pas « un peu plus gros que le dossard » : la taille du nom, c'est ce
        qui a été demandé."""
        nom = re.search(r"\.carte \.valeur \{[^}]*font-size: ([0-9.]+)rem", page)
        categorie = re.search(
            r"#carteGrimpeur \.categorie \{[^}]*font-size: ([0-9.]+)rem", page,
            re.S)
        assert nom and categorie, (nom, categorie)
        assert nom.group(1) == categorie.group(1), (nom.group(1), categorie.group(1))

    def test_sans_categorie_la_colonne_disparait(self, page):
        assert 'id="categorieGrimpeur" hidden' in page

    def test_elle_vient_du_catalogue_LOCAL(self):
        """Un scan ne doit pas attendre le réseau pour afficher ce que le juge
        vérifie."""
        js = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        assert "catalogue.categorie(etat.dossard)" in js
        assert "caseCategorie.hidden = !categorie;" in js

    def test_le_catalogue_garde_la_categorie_et_change_de_format(self):
        """⚠️ La forme 3 ne gardait que le circuit, par minimisation. Le
        marqueur de format est ce qui fait retélécharger les téléphones : sans
        lui, un `c` valant « U11 » serait affiché là où on annonce une
        catégorie."""
        cat = (STATIQUE / "catalogue.js").read_text(encoding="utf-8")
        assert "export const FORMAT = 4;" in cat
        assert "categorie(dossard) {" in cat
        # Le circuit se DEDUIT : deux champs qui disent la meme chose finissent
        # par se contredire.
        assert "return circuitDe(this.categorie(dossard));" in cat


class TestLaDemandeDeScanEtLeGeste:
    """« Si le juge set manuellement le nom de son téléphone il faut retirer la
    demande de scan du qrcode de paramétrage. » — Adrien, 03/09 (spec 042).

    Ce qui s'en va, c'est la DEMANDE : l'aplat bleu pleine largeur et son
    explication. Le GESTE reste, en lien discret, parce qu'un téléphone change
    parfois de table en cours de journée.

    ⚠️ Ces tests-ci gardent la STRUCTURE. Le comportement -- ce que le
    navigateur calcule vraiment, cascade appliquée -- est dans
    `test_navigateur_juge_reglages.py`, et c'est lui qui compte : le gabarit a
    déjà dit la vérité pendant qu'un bouton mort trônait sur cet écran.
    """

    @pytest.fixture()
    def page(self, client_sans_cle):
        return client_sans_cle.get("/juge").data.decode()

    def test_un_seul_noeud_porte_le_geste(self, page):
        """Deux nœuds -- un bouton, un lien, l'un caché -- ce serait deux
        gestionnaires de clic et deux libellés à garder identiques."""
        reglages = page.split('id="ecranReglages"', 1)[1].split("</section>", 1)[0]
        assert reglages.count('id="btnScannerPoste"') == 1
        assert reglages.count("Scanner le QR de mon poste") == 1

    def test_l_habit_de_depart_est_la_demande(self, page):
        """Un téléphone qui n'a pas encore de nom voit l'aplat bleu."""
        assert '<button class="action pleine" id="btnScannerPoste"' in page

    def test_la_largeur_n_est_plus_ecrite_en_ligne(self, page):
        """⚠️ Le piège que cette spec ferme. Un `width: 100%` posé en ligne
        survivrait au changement de classe, et le lien discret ferait toute la
        largeur de l'écran avec 12 px de marge au-dessus."""
        bouton = re.search(r"<button[^>]*id=\"btnScannerPoste\"[^>]*>", page)
        assert bouton, "le bouton de scan a disparu du gabarit"
        assert "style=" not in bouton.group(0), bouton.group(0)
        assert re.search(r"\.action\.pleine \{[^}]*width: 100%", page)

    def test_l_explication_est_designable(self, page):
        """Elle s'éteint avec la demande : sans `id`, personne ne peut
        l'atteindre, et elle resterait seule sous un lien discret."""
        assert 'id="expliquerScanPoste"' in page

    def test_une_seule_fonction_decide_des_deux_surfaces(self):
        """⚠️ L'écran d'accueil et les Réglages bougent ENSEMBLE.

        Deux endroits qui poseraient l'état eux-mêmes finiraient par n'en
        éteindre qu'un : la demande partirait de l'accueil et resterait dans les
        Réglages, ou l'inverse.
        """
        js = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        corps = js.split("function proposerDeNommerLePoste()", 1)[1] \
                  .split("\n}", 1)[0]
        assert '$("poste").hidden' in corps
        assert '$("btnScannerPoste").className' in corps
        assert '$("expliquerScanPoste").hidden' in corps

    def test_les_deux_habits_s_excluent(self):
        """`className` et non `classList.toggle` : une bascule laisserait un
        jour les deux classes posées, un lien sur un aplat bleu."""
        js = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        corps = js.split("function proposerDeNommerLePoste()", 1)[1] \
                  .split("\n}", 1)[0]
        assert 'nomme ? "lien" : "action pleine"' in corps

    def test_l_ouverture_des_reglages_pose_l_etat_de_depart(self):
        """⚠️ Sans cet appel, un téléphone nommé au démarrage -- le cas de tous
        les matins -- ouvrirait ses Réglages avec la demande encore allumée.
        Elle ne s'éteignait qu'à la première frappe dans le champ."""
        js = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        corps = js.split("async function ouvrirLesReglages()", 1)[1] \
                  .split("\n}", 1)[0]
        assert "proposerDeNommerLePoste()" in corps


class TestPlusAucuneCaseACocherNue:
    """« Toutes les coches pour le paramétrage que tu trouves tu les remplaces
    par un interrupteur comme dans toutes les applications mobiles. » — Adrien,
    03/09 (spec 042).

    Le test est écrit sur « toutes », pas sur celle d'aujourd'hui : il n'y en
    avait qu'une, et la prochaine doit naître interrupteur.
    """

    @pytest.fixture()
    def reglages(self, client_sans_cle):
        page = client_sans_cle.get("/juge").data.decode()
        return page.split('id="ecranReglages"', 1)[1].split("</section>", 1)[0]

    def test_chaque_case_est_habillee_en_interrupteur(self, reglages):
        cases = re.findall(r'<input[^>]*type="checkbox"[^>]*>', reglages)
        assert cases, "plus aucune case a cocher dans les Reglages ?"
        for case in cases:
            bloc = reglages.split(case, 1)[0]
            ouvert = bloc.rfind('class="bascule"')
            ferme = bloc.rfind("</label>")
            assert ouvert > ferme, (
                f"case a cocher nue dans les Reglages : {case}")

    def test_l_ordre_des_freres_est_respecte(self, reglages):
        """⚠️ `input:checked + .glissiere` est un sélecteur de frère ADJACENT.
        Un élément glissé entre les deux éteindrait l'interrupteur sans qu'aucune
        ligne n'ait l'air fausse."""
        for bascule in re.findall(r'<label class="bascule">(.*?)</label>',
                                  reglages, re.S):
            case = re.search(r'<input[^>]*type="checkbox"[^>]*>', bascule)
            assert case, bascule
            suite = bascule[case.end():].lstrip()
            assert suite.startswith('<span class="glissiere"'), suite[:80]

    def test_la_case_native_est_conservee_et_annoncee(self, reglages):
        """Rendue invisible, pas remplacée : elle garde le clavier, le focus,
        l'état et le lecteur d'écran. `role="switch"` la fait annoncer
        « interrupteur, activé » plutôt que « case à cocher, cochée »."""
        assert re.search(r'<input type="checkbox" id="garderGrimpeur" '
                         r'role="switch">', reglages)

    def test_la_glissiere_est_invisible_au_lecteur_d_ecran(self, reglages):
        """Elle ne porte aucune information : c'est l'`<input>` qui parle."""
        assert '<span class="glissiere" aria-hidden="true"></span>' in reglages


class TestLeNomDuCacheEtSaRaisonSePosentEnsemble:
    """⚠️ La coquille porte `/juge`, donc tout le CSS et tout le gabarit.

    Un changement d'écran qui ne change pas le NOM du cache ne parvient jamais
    aux téléphones déjà installés : `activate` ne supprime que les caches dont
    le nom diffère. C'est exactement ce que les v4, v5 et v6 ont corrigé, chaque
    fois après coup.

    Ce test ne peut pas deviner qu'un écran a changé. Il garde ce qu'il peut :
    que le numéro du cache et la ligne qui dit pourquoi il a bougé ne partent
    jamais l'un sans l'autre.
    """

    def test_le_numero_du_cache_est_celui_de_la_derniere_raison(self):
        sw = (STATIQUE / "sw.js").read_text(encoding="utf-8")
        constante = re.search(r'const CACHE = "climbcontest-juge-v(\d+)"', sw)
        assert constante, "le nom du cache n'a plus la forme attendue"
        raisons = re.findall(r"^// v(\d+) le ", sw, re.M)
        assert raisons, "plus aucune ligne n'explique un changement de cache"
        assert raisons[-1] == constante.group(1), (
            f"le cache est en v{constante.group(1)} mais la derniere raison "
            f"ecrite porte sur la v{raisons[-1]} : l'un des deux a ete oublie")
