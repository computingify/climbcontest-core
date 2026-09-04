"""La matiere imprimee de l'application juge — spec 041.

⚠️ La meme honnetete qu'en tete de `test_pwa_claire.py` : un test Python ne
peut pas juger un rendu. Ce fichier ne verifie donc PAS que la matiere est
belle, ni meme visible — c'est `specs/041-matiere-imprimee/maquettes/` qui le
montre, et les mesures au navigateur consignees dans son plan.

Il ferme deux pieges que la fusion du 03/09 a reellement ouverts, et que rien
n'aurait signale autrement.
"""
import re
from pathlib import Path

import pytest

GABARIT = (Path(__file__).resolve().parents[1] / "climbcontest" / "templates"
           / "juge.html")


@pytest.fixture(scope="module")
def style() -> str:
    """Le `<style>` en ligne du gabarit juge."""
    bloc = re.search(r"<style>(.*?)</style>", GABARIT.read_text(encoding="utf-8"), re.S)
    assert bloc, "le gabarit n'a plus de feuille de style en ligne"
    return bloc.group(1)


class TestAucunJetonNeSurvitASonDernierLecteur:
    """Le piege que la fusion des specs 040 et 041 a ouvert SANS conflit.

    La 041 a supprime `--trait-circuit`, devenue sans lecteur une fois la carte
    du bloc cerclee d'encre. La 040, partie d'un master anterieur, a recopie le
    bloc sombre pour en faire `:root[data-theme="sombre"]` — avec la variable
    dedans. Git a garde les deux gestes et n'a rien signale : la variable est
    revenue dans UN bloc sur trois, ou elle se lisait comme un reglage propre au
    theme impose.

    Une variable qui survit a son dernier lecteur n'est pas du code mort inerte:
    elle ment. La prochaine lecture croit que le bord de la carte suit le
    circuit, change la valeur, et ne voit rien bouger.
    """

    def test_toute_variable_declaree_est_lue_quelque_part(self, style):
        declarees = set(re.findall(r"^\s*(--[\w-]+)\s*:", style, re.M))
        lues = set(re.findall(r"var\(\s*(--[\w-]+)", style))
        # `--circuit` et `--encre-circuit` sont posees en JS par `redessiner()`,
        # jamais declarees dans la feuille : elles ne peuvent pas etre orphelines.
        orphelines = sorted(declarees - lues)
        assert orphelines == [], (
            "des variables CSS n'ont plus aucun lecteur, et une variable sans "
            f"lecteur ment a la prochaine lecture : {orphelines}")


@pytest.fixture(scope="module")
def souffle(style) -> str:
    """Le corps des images-cles `souffle`."""
    bloc = re.search(r"@keyframes souffle\s*\{(.*?)\n  \}", style, re.S)
    assert bloc, "les images-cles `souffle` ont disparu du gabarit"
    return bloc.group(1)


class TestLeSouffleNEffacePasLOmbre:
    """L'ombre du bouton disparaissait deux fois par seconde.

    `box-shadow` est une propriete UNIQUE : les images-cles du souffle (spec
    007) la reecrivaient entierement, effacant l'ombre imprimee a chaque
    battement. Le defaut ne se voyait ni a la relecture ni sur une capture
    fixe — seulement a l'oeil, sur l'ecran, en mouvement.

    Ce test fige la reparation : chaque etape du souffle doit reporter l'ombre,
    et pas seulement la lueur du circuit.
    """

    def test_chaque_etape_reporte_l_ombre_imprimee(self, souffle):
        etapes = [e for e in re.findall(r"box-shadow:(.*?);", souffle, re.S)]
        assert len(etapes) >= 2, "le souffle n'a plus ses deux etapes"
        for i, etape in enumerate(etapes):
            # L'ombre imprimee est la seule des trois couches qui soit posee sur
            # l'ENCRE ; la lueur qui pulse, elle, est posee sur le circuit.
            assert "--encre" in etape, (
                f"l'etape {i} du souffle ne reporte pas l'ombre imprimee : elle "
                "l'effacera a chaque battement, comme avant la spec 041")

    def test_seule_la_lueur_du_circuit_varie(self, souffle):
        etapes = re.findall(r"box-shadow:(.*?);", souffle, re.S)
        # Ce qui pulse doit etre le RAYON de la lueur, pas la presence de
        # l'ombre : les deux etapes citent le circuit, avec deux rayons.
        rayons = [re.search(r"0 0 (\d+)px color-mix\(in srgb, var\(--circuit\)", e)
                  for e in etapes]
        assert all(rayons), "la lueur du circuit a quitte une des etapes"
        valeurs = {r.group(1) for r in rayons}
        assert len(valeurs) > 1, (
            "les deux etapes ont le meme rayon de lueur : le bouton ne respire "
            "plus, et la pulsation de la spec 007 est perdue")


class TestLeCircuitNoirGardeSaCarteEnPapier:
    """La regle qui distingue le seul circuit dont la teinte EST l'encre."""

    def test_la_regle_existe_et_vise_la_classe_posee_par_le_js(self, style):
        assert "#carteBloc.fait.encre" in style, (
            "la regle du circuit « Noir » a disparu : sa carte va revirer au gris")

    def test_elle_ne_compare_aucune_couleur(self, style):
        # ⚠️ Le marqueur vient du NOM du circuit, jamais de sa valeur. Une regle
        # qui citerait la valeur du noir se romprait le jour ou `NOIR.clair` et
        # l'encre du theme divergent d'un point.
        regle = re.search(r"#carteBloc\.fait\.encre\s*\{(.*?)\}", style, re.S)
        assert regle, "la regle du « Noir » a change de forme"
        assert "#" not in regle.group(1), (
            "une couleur est ecrite en dur dans la regle du « Noir » : elle ne "
            "suivra pas le theme impose par la spec 040")


@pytest.fixture(scope="module")
def sw() -> str:
    """Le service worker de l'application juge."""
    chemin = (Path(__file__).resolve().parents[1] / "climbcontest" / "static"
              / "juge" / "sw.js")
    return chemin.read_text(encoding="utf-8")


class TestLaCoquilleEstCoherenteAvecSonJournal:
    """Le numero de coquille et le commentaire qui l'explique disent la meme chose.

    ⚠️ **Trois collisions de suite sur ce numero, le meme jour.** Les specs 040
    et 041 ont toutes deux revendique `v7` ; puis les specs 030 et 041 ont
    toutes deux revendique `v8`. Chaque branche l'ecrit sans savoir l'autre, et
    git ne l'a signale que parce que les COMMENTAIRES differaient — deux
    branches qui poseraient le meme commentaire fusionneraient en silence.

    Ce qui est en jeu n'est pas cosmetique : `activate` ne supprime que les
    caches dont le NOM differe. Deux specs sous un meme numero, et les
    telephones deja installes gardent l'ancienne coquille de l'une des deux,
    sans que rien ne casse visiblement.

    Ce garde ne peut pas empecher la collision — elle nait sur deux branches a
    la fois. Il attrape sa CONSEQUENCE la plus probable : une resolution qui
    garde les deux commentaires et oublie de faire monter la constante.
    """

    def test_la_constante_porte_le_plus_haut_numero_documente(self, sw):
        documentes = [int(n) for n in re.findall(r"^// v(\d+) ", sw, re.M)]
        assert documentes, (
            "plus aucun commentaire `// vN` dans sw.js : le journal des "
            "coquilles a disparu, et avec lui le seul moyen de voir une "
            "collision de numero entre deux branches")
        constante = re.search(r'const CACHE = "climbcontest-juge-v(\d+)"', sw)
        assert constante, "le nom du cache a change de forme"
        assert int(constante.group(1)) == max(documentes), (
            f"la coquille s'appelle v{constante.group(1)} alors que son journal "
            f"documente jusqu'a v{max(documentes)}. C'est la trace d'une fusion "
            "resolue a moitie : les telephones deja installes garderont "
            "l'ancienne coquille de l'une des deux specs")

    def test_aucun_numero_n_est_revendique_deux_fois(self, sw):
        documentes = [int(n) for n in re.findall(r"^// v(\d+) ", sw, re.M)]
        doublons = sorted({n for n in documentes if documentes.count(n) > 1})
        assert doublons == [], (
            f"le journal des coquilles revendique {doublons} plus d'une fois : "
            "deux specs se sont croisees sur le meme numero et la resolution "
            "n'a fait monter aucune des deux")
