"""Le juge choisit son thème dans les Réglages — spec 040.

⚠️ Ce fichier garde **trois duplications volontaires**, et c'est tout son
objet. Elles ne sont pas des maladresses qu'on nettoiera : chacune est le prix
d'une contrainte qui n'a pas d'autre solution, et chacune se paierait un jour
en divergence silencieuse si personne ne la surveillait.

1. **Le thème sombre est écrit deux fois** dans le gabarit — une fois sous
   `@media (prefers-color-scheme: dark)`, une fois sous
   `:root[data-theme="sombre"]`. CSS ne sait pas partager un jeu de valeurs
   entre une requête media et un sélecteur d'attribut. L'alternative était de
   tout résoudre en JavaScript avant la peinture, ce qui aurait rendu le choix
   du SYSTÈME dépendant d'un script — un recul sur la spec 039.
2. **Le nom de la clé de rangement est écrit deux fois** — dans `theme.js` et
   dans le script en ligne du `<head>`, qui ne peut pas importer un module de
   façon synchrone.
3. **Le fond sombre est écrit dans le gabarit et dans ce fichier**, comme dans
   `test_pwa_claire.py` : un test qui lirait la valeur depuis le gabarit
   qu'il vérifie ne vérifierait rien.

Ce que ce fichier ne fait PAS : mesurer des couleurs à l'écran. C'est
`test_navigateur_theme_au_choix.py` qui bascule le thème dans un vrai
navigateur, cascade appliquée, et vérifie que le choix survit au relancement.
"""
import re
from pathlib import Path

import pytest

# ⚠️ Les trois outils d'analyse du `<style>` viennent de `test_pwa_claire.py`,
# et ne sont pas recopiés : le comptage d'accolades est exactement le genre de
# code qu'on ne veut pas voir diverger entre deux fichiers qui lisent le MÊME
# gabarit. Le commentaire de `_span_accolades` explique pourquoi une expression
# rationnelle ne suffit pas.
from tests.test_pwa_claire import _proprietes, _span_accolades, _style

STATIQUE = Path(__file__).resolve().parents[1] / "climbcontest" / "static" / "juge"

FOND_CLAIR = "#F3EEE3"
FOND_SOMBRE = "#15161B"
CLE = "climbcontest-theme"

# Le sélecteur de la requête media après la spec 040. Le `:not` est ce qui
# permet au juge d'imposer le CLAIR sur un téléphone en sombre.
SELECTEUR_MEDIA = ':root:not([data-theme="clair"])'
SELECTEUR_IMPOSE = ':root[data-theme="sombre"]'


@pytest.fixture()
def page(client_sans_cle):
    r = client_sans_cle.get("/juge")
    assert r.status_code == 200
    return r.data.decode()


@pytest.fixture()
def style(page):
    return _style(page)


def _bloc_apres(texte: str, marqueur: str) -> str:
    """Le contenu du `{...}` qui suit `marqueur`."""
    assert marqueur in texte, f"introuvable dans le gabarit : {marqueur}"
    ouverture, fermeture = _span_accolades(texte, texte.index(marqueur))
    return texte[ouverture:fermeture]


class TestLesDeuxSombresNePeuventPasDiverger:
    """L'invariant qui rend la duplication acceptable.

    Sans lui, une retouche du sombre — un fond réchauffé, un vert ajusté —
    s'appliquerait au téléphone qui demande le sombre et PAS au juge qui l'a
    demandé, ou l'inverse. Deux thèmes sombres légèrement différents selon la
    façon dont on y est arrivé : personne ne le verrait, et personne ne
    saurait le reproduire.
    """

    def test_le_theme_impose_existe(self, style):
        assert SELECTEUR_IMPOSE in style, (
            "le bloc du sombre imposé a disparu : le réglage « Sombre » "
            "n'aurait plus aucun effet sur un téléphone en clair")

    def test_les_deux_blocs_declarent_exactement_les_memes_couleurs(self, style):
        systeme = _proprietes(_bloc_apres(style, SELECTEUR_MEDIA))
        impose = _proprietes(_bloc_apres(style, SELECTEUR_IMPOSE))
        assert systeme == impose, (
            "les deux écritures du thème sombre ont divergé. Ce qui diffère : "
            f"{sorted(set(systeme.items()) ^ set(impose.items()))}")

    def test_et_ce_sont_bien_des_couleurs_pas_un_bloc_vide(self, style):
        """Un contre-test : deux blocs vides sont égaux, et le test ci-dessus
        passerait au vert sur une feuille de style amputée."""
        impose = _proprietes(_bloc_apres(style, SELECTEUR_IMPOSE))
        assert impose.get("--fond") == FOND_SOMBRE
        assert len(impose) >= 12


class TestLaRequeteMediaLaisseLaMainAuJuge:
    """Le sens de la spec : le juge décide APRÈS le téléphone, dans les deux
    sens. Sans le `:not`, forcer le clair serait impossible sur un téléphone
    réglé en sombre — c'est-à-dire la moitié de la demande d'Adrien.
    """

    def test_la_requete_media_s_efface_devant_le_clair_impose(self, style):
        depart = style.index("@media (prefers-color-scheme: dark)")
        entete = style[depart:style.index("{", style.index("{", depart) + 1)]
        assert SELECTEUR_MEDIA in entete, (
            "la requête media vise `:root` tout court : elle gagnerait contre "
            "le clair imposé, et « Clair » n'aurait aucun effet sur un "
            f"téléphone en sombre. Trouvé : {entete.strip()}")

    def test_le_clair_reste_le_defaut_sans_attribut(self, style):
        """Le défaut de la spec 039, intact : aucun attribut, aucun choix
        rangé, et c'est le papier sable qui s'applique."""
        avant = style[:style.index("@media (prefers-color-scheme: dark)")]
        assert _proprietes(avant).get("--fond") == FOND_CLAIR


class TestLeThemeEstPoseAvantLaPeinture:
    """Le clignotement, et pourquoi il ne peut pas revenir sans qu'on le voie.

    Un thème appliqué par un module ES est appliqué APRÈS la première peinture :
    l'application s'ouvre en clair, puis bascule en sombre sous les yeux du
    juge, à chaque lancement. Le seul remède est un script EN LIGNE, dans le
    `<head>`, avant tout le reste.
    """

    def test_le_script_est_en_ligne_dans_l_entete(self, page):
        entete = page[:page.index("</head>")]
        assert f'localStorage.getItem("{CLE}")' in entete, (
            "le thème n'est plus lu dans le `<head>` : il sera appliqué après "
            "la première peinture, et l'application clignotera à chaque "
            "lancement")

    def test_il_precede_tout_module(self, page):
        pose = page.index(f'localStorage.getItem("{CLE}")')
        premier_module = page.index('<script type="module"')
        assert pose < premier_module

    def test_il_ne_depend_d_aucun_fichier_a_telecharger(self, page):
        """Un `<script src=…>`, même non différé, est une requête de plus avant
        la peinture — et hors ligne, un fichier de plus qui peut manquer."""
        entete = page[:page.index("</head>")]
        bloc = entete[entete.rindex("<script", 0, entete.index(
            f'localStorage.getItem("{CLE}")')):]
        assert "src=" not in bloc.split(">", 1)[0]

    def test_il_pose_l_attribut_sur_la_racine(self, page):
        entete = page[:page.index("</head>")]
        assert "document.documentElement.dataset.theme = choix" in entete

    def test_un_rangement_refuse_ne_casse_pas_le_demarrage(self, page):
        """Navigation privée : `localStorage` LÈVE au lieu de rendre `null`.
        Sans le `try`, l'application ne s'ouvre pas du tout."""
        entete = page[:page.index("</head>")]
        bloc = entete[entete.index("(function () {", entete.index(
            f'localStorage.getItem("{CLE}")') - 400):]
        assert "try {" in bloc[:bloc.index("localStorage")]


class TestLaCleEstLaMemeDesDeuxCotes:
    """La duplication n° 2. Deux clés différentes donneraient une application
    qui range le choix quelque part et le relit ailleurs : le réglage marche à
    l'écran et n'est jamais retrouvé au lancement suivant.
    """

    def test_le_module_et_le_gabarit_nomment_la_meme_cle(self, page):
        source = (STATIQUE / "theme.js").read_text(encoding="utf-8")
        declaree = re.search(r'export const CLE_THEME = "([^"]+)";', source)
        assert declaree, "`CLE_THEME` a disparu de theme.js"
        assert declaree.group(1) == CLE
        assert f'localStorage.getItem("{CLE}")' in page


class TestLesTroisPositionsDuReglage:
    """« Système » n'est pas une commodité : c'est ce qui rend le réglage
    RÉVERSIBLE. Un interrupteur à deux positions ne sait pas revenir à « suis
    le téléphone », et le juge qui a forcé le clair le matin ne peut plus
    rendre la main le soir.
    """

    @pytest.mark.parametrize("choix", ["auto", "clair", "sombre"])
    def test_les_trois_pastilles_sont_la(self, page, choix):
        assert f'data-choix="{choix}"' in page

    def test_une_seule_est_allumee_au_depart_et_c_est_systeme(self, page):
        groupe = page[page.index('id="choixTheme"'):]
        groupe = groupe[:groupe.index("</div>")]
        allumees = re.findall(
            r'data-choix="([a-z]+)" aria-pressed="true"', groupe)
        assert allumees == ["auto"], allumees

    def test_le_reglage_vit_dans_l_ecran_reglages(self, page):
        """Pas dans l'en-tête : ce n'est pas un geste de compétition, c'est un
        réglage qu'on pose une fois le matin."""
        reglages = page[page.index('id="ecranReglages"'):
                        page.index('id="ecranScans"')]
        assert 'id="choixTheme"' in reglages


class TestLaCoquilleHorsLigne:
    """Le gabarit a changé, et un module s'ajoute. Sans changement de NOM de
    cache, un téléphone déjà installé rouvre l'ancienne page — sans le réglage,
    et sans le module qui va avec.
    """

    def test_le_module_est_dans_la_coquille(self):
        sw = (STATIQUE / "sw.js").read_text(encoding="utf-8")
        coquille = sw[sw.index("const COQUILLE = ["):sw.index("];")]
        assert '"/static/juge/theme.js"' in coquille

    def test_le_nom_du_cache_a_change(self):
        """⚠️ Écrit en « ce n'est plus v6 » et pas en « c'est v7 » : la version
        bougera encore, et un test qui épingle un numéro devient un test qu'on
        met à jour sans le lire."""
        sw = (STATIQUE / "sw.js").read_text(encoding="utf-8")
        nom = re.search(r'const CACHE = "([^"]+)";', sw).group(1)
        assert nom != "climbcontest-juge-v6", (
            "le gabarit et les modules ont changé mais le cache porte le même "
            "nom : les téléphones déjà installés garderont l'ancienne coquille")

    def test_juge_js_branche_le_module(self):
        source = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        assert 'from "./theme.js"' in source
        assert "brancherLeTheme()" in source


class TestLeCircuitNoirSuitLeThemeImpose:
    """Le défaut d'intégration de cette spec, et le plus vicieux : le circuit
    « Noir » prend l'encre du thème (spec 039), mais `enSombre()` lisait
    `matchMedia`, c'est-à-dire le TÉLÉPHONE. Un juge qui force le sombre sur un
    téléphone en clair aurait eu un aplat presque noir sur un fond presque
    noir : il n'aurait pas su s'il avait scanné.

    Le comportement se teste en JavaScript (`tests/js/couleurs.test.mjs`), là
    où le module vit. Ici, on protège le fait que la lecture soit la bonne.
    """

    def test_en_sombre_lit_le_theme_impose_avant_le_telephone(self):
        source = (STATIQUE / "couleurs.js").read_text(encoding="utf-8")
        assert "globalThis.document?.documentElement?.dataset?.theme" in source, (
            "`enSombre()` ne lit plus l'attribut posé par le réglage : le "
            "circuit « Noir » redeviendra invisible pour un juge qui impose un "
            "thème contraire à celui de son téléphone")

    def test_la_teinte_est_redessinee_au_changement(self):
        """Le CSS suit tout seul ; la teinte du circuit est posée en variable
        en ligne et ne suit pas."""
        source = (STATIQUE / "juge.js").read_text(encoding="utf-8")
        bloc = source[source.index("function brancherLeTheme()"):]
        bloc = bloc[:bloc.index("\nasync function ")]
        assert "redessiner();" in bloc
