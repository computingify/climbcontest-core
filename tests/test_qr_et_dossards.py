"""Le QR des dossards, et la planche a imprimer (spec 005, IT4 ; spec 023).

Le test qui compte est `TestVraimentLisible` : il DECODE ce qu'on produit,
avec un decodeur independant de l'encodeur. Un QR d'allure correcte mais
indechiffrable est exactement ce qui se decouvre le jour J, sur un parking,
avec 120 dossards deja imprimes.

C'est arrive pendant l'ecriture de ce module : un encodeur maison produisait
des matrices parfaitement plausibles que rien ne lisait.
"""
import re

import pytest

from climbcontest import comptes, qr

MDP = "un-mot-de-passe-assez-long"

try:
    import cv2
    import numpy as np
    DECODEUR = True
except ImportError:                                   # pragma: no cover
    DECODEUR = False


@pytest.fixture()
def connecte(client, app, jeu):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


class TestPasUnMicroQr:
    """LE piege, et il coute cher.

    `segno.make()` choisit tout seul un MICRO QR pour des donnees courtes --
    13x13, une symbologie que la plupart des scanners de telephone ne lisent
    pas. Un dossard fait un a quatre chiffres : on tombe dedans a tous les
    coups, et le QR a l'air parfaitement normal a l'oeil.
    """

    @pytest.mark.parametrize("dossard", ["1", "42", "120", "9999"])
    def test_ce_n_est_jamais_un_micro_qr(self, dossard):
        assert qr.code(dossard).is_micro is False

    @pytest.mark.parametrize("dossard", ["1", "42", "120", "9999"])
    def test_la_matrice_fait_au_moins_21_modules(self, dossard):
        """Un QR standard commence a 21x21. En dessous, c'est un Micro QR."""
        m = qr.matrice(dossard)
        assert len(m) >= 21, f"{len(m)}x{len(m)} : c'est un Micro QR"
        assert len(m) == len(m[0]), "une matrice carree"


@pytest.mark.skipif(not DECODEUR, reason="opencv absent")
class TestVraimentLisible:
    """On decode ce qu'on produit. C'est le seul test qui prouve quelque chose."""

    @staticmethod
    def _image(dossard, echelle=10, marge=4):
        m = qr.matrice(dossard)
        n = len(m)
        total = n + 2 * marge
        img = np.ones((total, total), np.uint8) * 255
        for y in range(n):
            for x in range(n):
                if m[y][x]:
                    img[y + marge, x + marge] = 0
        return cv2.resize(img, (total * echelle,) * 2,
                          interpolation=cv2.INTER_NEAREST)

    @pytest.mark.parametrize("dossard", ["1", "2", "7", "42", "99", "120", "500",
                                         "1234", "9999"])
    def test_un_decodeur_independant_relit_le_dossard(self, dossard):
        lu, _, _ = cv2.QRCodeDetector().detectAndDecode(self._image(dossard))
        assert lu == dossard, f"produit {dossard}, relu {lu!r}"

    def test_le_harnais_lui_meme_est_fiable(self, ):
        """Un harnais qui echoue toujours ferait passer un bon encodeur pour
        mauvais -- et c'est exactement ce que j'ai cru pendant un moment. On
        verifie donc qu'il sait AUSSI dire non.
        """
        blanc = np.ones((200, 200), np.uint8) * 255
        lu, _, _ = cv2.QRCodeDetector().detectAndDecode(blanc)
        assert lu == "", "une image vide ne doit rien rendre"


class TestLaNormeDuQr:
    """L'ISO/IEC 18004 exige une zone de silence de QUATRE modules autour d'un
    QR Code. Nous en posions DEUX. Ca marche sur un fond parfaitement blanc, et
    ca lache des que le code touche autre chose -- une bordure de case, le trait
    de coupe voisin : le decodeur les lit comme des modules noirs.

    Le defaut est devenu urgent le 01/09, quand la planche est passee a six
    fiches par A4 : c'est exactement le moment ou le voisinage se rapproche.
    """

    def test_la_zone_de_silence_fait_quatre_modules(self):
        assert qr.ZONE_DE_SILENCE == 4

    @pytest.mark.parametrize("dossard", ["1", "42", "120", "9999"])
    def test_le_svg_porte_vraiment_cette_marge(self, dossard):
        """Le `viewBox` compte les modules ET la marge : n + 2 x 4."""
        cote = len(qr.matrice(dossard))
        viewbox = re.search(r'viewBox="0 0 (\d+) (\d+)"', qr.svg(dossard)).groups()
        assert viewbox == (str(cote + 8), str(cote + 8))

    @pytest.mark.parametrize("dossard", ["1", "9999"])
    def test_un_module_reste_au_dessus_du_plancher(self, dossard):
        """Un module trop petit n'est plus lu de facon fiable par un appareil
        photo de telephone, quelle que soit la qualite du code."""
        from climbcontest import fiches
        taille = qr.taille_de_module_mm(dossard, fiches.COTE_QR_MM)
        assert taille >= qr.MODULE_MINI_MM, f"{taille:.2f} mm par module"

    @pytest.mark.skipif(not DECODEUR, reason="opencv absent")
    def test_il_se_relit_a_la_taille_de_la_fiche(self):
        """Le vrai test : on rend le QR a la taille qu'il aura SUR LE PAPIER, en
        300 points par pouce, et on le relit avec un decodeur independant."""
        from climbcontest import fiches
        dossard = "9999"
        modules = len(qr.matrice(dossard)) + 2 * qr.ZONE_DE_SILENCE
        # 300 ppp : la resolution d'une imprimante de bureau.
        cote_px = int(fiches.COTE_QR_MM / 25.4 * 300)
        echelle = max(1, cote_px // modules)
        image = TestVraimentLisible._image(dossard, echelle=echelle,
                                           marge=qr.ZONE_DE_SILENCE)
        lu, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        assert lu == dossard


class TestSvg:

    def test_la_taille_est_en_millimetres(self):
        """C'est la taille PHYSIQUE sur le papier qui compte, pas les pixels."""
        s = qr.svg("42", cote_mm=22)
        assert 'width="22mm"' in s or 'width="22.0mm"' in s

    def test_la_taille_est_reglable(self):
        assert "30mm" in qr.svg("42", cote_mm=30)

    def test_aucun_appel_reseau_dans_le_svg(self):
        """Le classeur appelle api.qrserver.com. Pas nous."""
        s = qr.svg("42")
        assert "http://" not in s.replace("http://www.w3.org/2000/svg", "")
        assert "qrserver" not in s

    def test_le_svg_est_du_svg(self):
        s = qr.svg("42")
        assert s.lstrip().startswith("<svg")
        assert s.rstrip().endswith("</svg>")


class TestPageDossards:

    def test_la_page_sort_du_html(self, connecte, jeu):
        r = connecte.get("/admin/dossards")
        assert r.status_code == 200
        assert r.headers["Content-Type"].startswith("text/html")

    def test_une_fiche_par_participant_numerote(self, connecte, jeu):
        """Deux des trois participants du jeu portent un numero."""
        page = connecte.get("/admin/dossards").data.decode()
        assert page.count('class="fiche"') == 2

    def test_le_nom_et_le_numero_sont_la(self, connecte, jeu):
        """Sans le nom, impossible de donner le bon papier a la bonne personne."""
        page = connecte.get("/admin/dossards").data.decode()
        assert "Dupont Lea" in page
        assert "U11 F" in page

    def test_un_seul_dossard(self, connecte, jeu):
        """Le cas de l'arrivant de derniere minute."""
        page = connecte.get("/admin/dossards?dossard=1").data.decode()
        assert page.count('class="fiche"') == 1
        assert "Dupont Lea" in page

    def test_un_lot_par_categorie(self, connecte, jeu):
        page = connecte.get("/admin/dossards?categorie=U11 F").data.decode()
        assert page.count('class="fiche"') == 1

    def test_les_dossards_sont_tries(self, connecte, jeu):
        page = connecte.get("/admin/dossards").data.decode()
        assert page.index(">1<") < page.index(">2<")

    def test_aucun_participant_numerote_donne_une_page_lisible(self, client, app,
                                                               competition):
        """Avant tout import : une page qui explique, pas un plantage.

        Volontairement sans la fixture `jeu` -- elle cree des participants,
        ce qui rendrait ce test incapable de verifier ce qu'il annonce.
        """
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        comptes.creer("orga2", MDP, [comptes.ORGANISATEUR])
        client.post("/admin/connexion",
                    json={"identifiant": "orga2", "mot_de_passe": MDP})

        page = client.get("/admin/dossards").data.decode()

        assert "Aucune fiche" in page

    def test_la_page_ne_charge_rien_de_l_exterieur(self, connecte, jeu):
        import re
        page = connecte.get("/admin/dossards").data.decode()
        externes = [u for u in re.findall(r'https?://[^\s"\'<>)]+', page)
                    if u != "http://www.w3.org/2000/svg"]
        assert not externes, f"ressources externes : {externes}"

    def test_une_fiche_ne_peut_pas_etre_coupee_par_un_saut_de_page(self, connecte, jeu):
        """Le grimpeur se retrouverait avec un demi-QR."""
        page = connecte.get("/admin/dossards").data.decode()
        assert "break-inside: avoid" in page

    def test_sans_session_c_est_refuse(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/dossards").status_code == 401
