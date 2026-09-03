"""L'application juge s'ouvre en CLAIR — spec 039.

⚠️ Ce fichier verifie ce qu'un test Python peut verifier honnetement d'un
gabarit : la STRUCTURE des deux jeux de couleurs, et le fait que le clair soit
le defaut. Il ne verifie pas ce que ca donne a l'ecran -- c'est
`tests/test_navigateur_juge_claire.py` qui mesure les contrastes calcules,
cascade appliquee, et `specs/039-pwa-claire/maquettes/index.html` qui montre les
seize captures.

La meme honnetete qu'en tete de `test_console_lisible.py`, et pour la meme
raison : un test qui pretend verifier une couleur en lisant une chaine de
caracteres donne une fausse assurance.
"""
import json
import re
from pathlib import Path

import pytest

GABARIT = (Path(__file__).resolve().parents[1] / "climbcontest" / "templates"
           / "juge.html")
STATIQUE = Path(__file__).resolve().parents[1] / "climbcontest" / "static" / "juge"

# Le fond clair, celui qui doit se retrouver a l'identique dans le manifeste.
FOND_CLAIR = "#F3EEE3"
FOND_SOMBRE = "#15161B"


def _style(page: str) -> str:
    """Le contenu du `<style>` en ligne, sans le reste de la page."""
    bloc = re.search(r"<style>(.*?)</style>", page, re.S)
    assert bloc, "le gabarit n'a plus de feuille de style en ligne"
    return bloc.group(1)


def _span_accolades(texte: str, depart: int) -> tuple[int, int]:
    """Les bornes du bloc `{...}` qui suit `depart`, accolades comptees.

    ⚠️ Une expression rationnelle ne sait pas faire ca : le bloc de la requete
    media CONTIENT un `:root { … }`, et `.*?\\}` s'arreterait sur la premiere
    accolade fermante -- au milieu, donc, en donnant l'illusion d'avoir lu le
    bloc entier.
    """
    ouverture = texte.index("{", depart)
    profondeur, i = 0, ouverture
    while i < len(texte):
        if texte[i] == "{":
            profondeur += 1
        elif texte[i] == "}":
            profondeur -= 1
            if profondeur == 0:
                return ouverture, i
        i += 1
    raise AssertionError("bloc d'accolades jamais ferme")


@pytest.fixture()
def page(client_sans_cle):
    r = client_sans_cle.get("/juge")
    assert r.status_code == 200
    return r.data.decode()


@pytest.fixture()
def style(page):
    return _style(page)


@pytest.fixture()
def blocs(style):
    """`(clair, sombre, partage)` — le texte de chacun des trois blocs.

    `clair` est ce qui precede la requete media, `partage` ce qui suit le
    sombre : c'est l'ORDRE qui fait le defaut, et le test le lit dans cet
    ordre-la.

    ⚠️ Depuis la spec 040, le sombre est ecrit DEUX fois -- une fois sous la
    requete media (le telephone le demande), une fois sous
    `:root[data-theme="sombre"]` (le juge l'a demande dans les Reglages). Le
    second bloc n'est pas rendu ici : ce fichier verifie le DEFAUT, et le
    defaut ne connait pas l'attribut. Ce qui garantit que les deux copies ne
    divergent pas est dans `test_theme_au_choix.py`, qui les compare propriete
    par propriete. `partage` commence donc apres le SECOND bloc, sans quoi
    toutes les couleurs sombres y seraient comptees deux fois.
    """
    depart_sombre = style.index("@media (prefers-color-scheme: dark)")
    ouverture, fermeture = _span_accolades(style, depart_sombre)
    depart_impose = style.index('  :root[data-theme="sombre"] {', fermeture)
    _, fin_impose = _span_accolades(style, depart_impose)
    return (style[:depart_sombre],
            style[ouverture:fermeture],
            style[fin_impose:])


def _proprietes(texte: str) -> dict[str, str]:
    return {nom: valeur.strip()
            for nom, valeur in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;}]+)", texte)}


class TestLeClairEstLeDefaut:
    """Le coeur de la spec. « par defaut elle s'ouvre en claire » (Adrien)."""

    def test_le_fond_clair_est_declare_avant_la_requete_media(self, style):
        assert FOND_CLAIR in style, "le fond clair a disparu du gabarit"
        assert style.index(FOND_CLAIR) < style.index("@media (prefers-color-scheme: dark)"), (
            "le fond clair est declare APRES la requete media : le clair "
            "redeviendrait un cas particulier, et l'ordre le rendrait meme "
            "inatteignable en sombre")

    def test_le_fond_sombre_n_est_jamais_pose_par_defaut(self, blocs):
        """⚠️ Depuis la spec 040 le fond sombre existe a un SECOND endroit --
        `:root[data-theme="sombre"]`, l'attribut que pose le reglage. Ce qui
        compte n'a pas bouge : il ne doit se trouver ni avant la requete media,
        ni apres, c'est-a-dire nulle part ou il s'appliquerait sans que
        personne l'ait demande."""
        clair, sombre, partage = blocs
        assert FOND_SOMBRE in sombre
        assert FOND_SOMBRE not in clair, (
            "le fond sombre est declare hors de la requete media : "
            "l'application se rouvrirait en sombre sans qu'on le demande")
        assert FOND_SOMBRE not in partage

    def test_le_navigateur_sait_que_la_page_connait_les_deux(self, style):
        """`color-scheme` habille les cases a cocher, les champs et les barres
        de defilement NATIVES. Sans lui, la case des Reglages reste sombre sur
        le papier -- et c'est un vrai `<input type=checkbox>`, pas un dessin."""
        assert "color-scheme: light dark" in style


class TestAucuneCouleurNExisteDansUnSeulTheme:
    """L'invariant qui compte, et le seul qu'un test statique attrape vraiment.

    Un role defini UNIQUEMENT dans la requete media n'existe pas en clair : la
    regle qui s'en sert tombe sur `unset` et l'element se peint en transparent
    ou en noir, selon la propriete. C'est le defaut classique de ce genre de
    refonte, et il ne se voit pas a la relecture.
    """

    def test_tout_ce_que_le_sombre_redefinit_existe_aussi_en_clair(self, blocs):
        clair, sombre, _ = blocs
        manquants = sorted(set(_proprietes(sombre)) - set(_proprietes(clair)))
        assert not manquants, (
            "ces roles n'existent QUE en theme sombre, donc pas du tout par "
            f"defaut : {manquants}")

    def test_le_bloc_partage_ne_croise_jamais_le_sombre(self, blocs):
        """⚠️ Le troisieme bloc vient APRES la requete media. Une propriete
        ecrite dans les deux gagnerait la, dans les DEUX themes -- et la valeur
        sombre serait morte sans que rien ne le dise."""
        _, sombre, partage = blocs
        croisement = sorted(set(_proprietes(partage)) & set(_proprietes(sombre)))
        assert not croisement, (
            "ces roles sont poses apres la requete media ET dedans : la valeur "
            f"sombre ne s'appliquera jamais : {croisement}")

    def test_les_deux_themes_definissent_le_meme_nombre_de_couleurs(self, blocs):
        """Un garde-fou de volume, pas de valeur : si un jeu grossit sans que
        l'autre suive, c'est qu'une couleur a ete ajoutee d'un seul cote."""
        clair, sombre, _ = blocs
        # `color-scheme` et les deux `color-mix` de teinte ne sont pas des
        # couleurs de theme comptables : on compare ce qui l'est.
        assert len(_proprietes(sombre)) >= 12
        assert len(_proprietes(clair)) >= len(_proprietes(sombre))


class TestPlusAucuneCouleurEcriteEnDurDansLesRegles:
    """Dix couleurs etaient calees sur le fond sombre, hors de `:root` : la
    puce du numero d'etape, l'encre de « Envoyer quand meme », les voiles des
    pastilles, le bleu des actions, l'ombre de la bulle. Elles n'auraient pas
    suivi le theme, et rien ne l'aurait dit.
    """

    def test_le_seul_litteral_restant_est_le_noir_du_viseur(self, blocs):
        clair, sombre, partage = blocs
        # On ne regarde QUE les regles : les trois blocs de `:root` sont, eux,
        # faits pour porter des valeurs.
        regles = partage[partage.index("* { box-sizing"):]
        # ⚠️ La borne de mot a droite n'est pas une precaution : `#effacer` est
        # un SELECTEUR dont les six premieres lettres sont toutes des chiffres
        # hexadecimaux. Sans elle, le test accusait une couleur qui n'existe
        # pas -- et on cherche longtemps.
        litteraux = re.findall(
            r"(?<![\w#])(#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})"
            r"(?![0-9A-Za-z_-])|rgba?\([^)]*\))", regles)
        assert litteraux == ["#000"], (
            "une couleur est ecrite en dur dans une regle : elle ne suivra pas "
            f"le theme. Trouve : {litteraux}")

    def test_le_viseur_reste_noir_et_le_dit(self, blocs):
        """Ce n'est pas du decor : c'est l'image de la camera. Un cadre clair
        autour d'un flux video eblouit dans la penombre et fait fermer l'iris
        du capteur."""
        _, _, partage = blocs
        assert "#viseur { position: fixed; inset: 0; background: #000;" in partage
        assert "NOIR dans les deux themes" in partage


class TestLaBarreDuNavigateurEtCelleDIOS:

    def test_deux_theme_color_le_clair_en_premier(self, page):
        """⚠️ L'ordre est le repli : un navigateur qui ignore `media` -- les iOS
        anterieurs a 15.4, donc des telephones de benevoles -- garde la
        premiere."""
        metas = re.findall(
            r'<meta name="theme-color" content="(#[0-9A-Fa-f]{6})"'
            r' media="\(prefers-color-scheme: (light|dark)\)">', page)
        assert metas == [(FOND_CLAIR, "light"), (FOND_SOMBRE, "dark")], metas

    def test_la_barre_ios_n_est_plus_translucide_sur_du_noir(self, page):
        """`black-translucent` ecrivait l'heure et la batterie en BLANC, et sur
        un fond clair c'etait illisible. `default` laisse iOS choisir."""
        assert ('<meta name="apple-mobile-web-app-status-bar-style" '
                'content="default">') in page
        assert 'content="black-translucent"' not in page, (
            "la barre d'etat iOS est redevenue translucide sur du noir : "
            "l'heure et la batterie s'ecriront en blanc sur du papier sable")


class TestLeManifesteNeDerivePasDuFond:
    """L'ecran de demarrage de l'application INSTALLEE. Un manifeste n'a pas de
    requete media : il porte le theme par defaut. Deux valeurs a tenir egales a
    la main finiraient par diverger, et ca se verrait comme un lisere au
    demarrage.
    """

    def test_le_manifeste_porte_le_fond_clair(self, client_sans_cle):
        d = json.loads(client_sans_cle.get("/juge/manifest.webmanifest")
                       .data.decode())
        assert d["background_color"] == FOND_CLAIR
        assert d["theme_color"] == FOND_CLAIR

    def test_et_c_est_exactement_le_fond_du_gabarit(self, client_sans_cle, blocs):
        """⚠️ Le fond du bloc CLAIR, pas celui du gabarit en general : `--fond`
        est declare deux fois, et c'est le premier -- le defaut -- que
        l'application installee doit raccorder."""
        d = json.loads(client_sans_cle.get("/juge/manifest.webmanifest")
                       .data.decode())
        clair, _, _ = blocs
        fond = _proprietes(clair)["--fond"]
        assert d["background_color"] == fond.split()[0], (
            "le fond du manifeste et celui du gabarit ont divergé : "
            "l'ecran de demarrage ne raccordera plus l'application")


class TestLeCircuitNoirSuitLeTheme:
    """La question laissee ouverte par la spec 035. La craie n'etait pas un
    choix de couleur : c'etait une rustine du fond sombre.

    Le comportement lui-meme est teste en JavaScript
    (`tests/js/couleurs.test.mjs`), la ou le module vit. Ici, on protege ce
    qu'un test Python peut protéger : que les deux valeurs existent, et que la
    coquille hors-ligne emporte bien le module qui a change.
    """

    def test_les_deux_valeurs_du_noir_sont_declarees(self):
        source = (STATIQUE / "couleurs.js").read_text(encoding="utf-8")
        assert 'export const NOIR = { clair: "#22201B", sombre: "#E8EBF0" };' in source

    def test_couleur_de_circuit_prend_le_theme_en_parametre(self):
        source = (STATIQUE / "couleurs.js").read_text(encoding="utf-8")
        assert "export function couleurDeCircuit(nom, sombre = enSombre())" in source

    def test_la_coquille_hors_ligne_emporte_les_couleurs(self):
        """`couleurs.js` a change : s'il n'etait pas dans la coquille, un
        telephone hors ligne garderait l'ancien module."""
        sw = (STATIQUE / "sw.js").read_text(encoding="utf-8")
        assert '"/static/juge/couleurs.js"' in sw
