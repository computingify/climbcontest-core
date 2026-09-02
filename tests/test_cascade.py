"""La cascade de couleurs — spec 025.

Deux choses sont vérifiées ici, et elles ne se déduisent pas l'une de l'autre :

- **la lecture** de la règle, y compris le repli sur `validation_couleur` ;
- **le contrôle**, qui n'existe que parce que deux phrases peuvent mentir à qui
  les écrit. Elles ne peuvent pas se *contredire* — le résultat est l'union de
  celles qui tiennent, donc une phrase ne fait qu'ajouter. C'est démontré ici
  par énumération exhaustive, pas affirmé.
"""

import itertools
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from climbcontest import cascade as module
from climbcontest.classement import COULEURS, Cascade, Phrase
from climbcontest.contest import ErreurMetier


def phrase(parmi, seuil, cibles):
    return Phrase(parmi=frozenset(parmi), seuil=seuil, cibles=frozenset(cibles))


# --- La règle ne peut pas se contredire -------------------------------------

class TestUnionSeulement:
    def test_une_phrase_ne_fait_qu_ajouter(self):
        """Retirer une phrase ne peut jamais AJOUTER une validation.

        C'est ce qui rend le mot « contradiction » impropre : les phrases
        s'additionnent. Enumération exhaustive des 64 combinaisons de couleurs
        pleines — pas un echantillon.
        """
        regles = (
            phrase(["Rouge"], 1, ["Jaune", "Vert"]),
            phrase(["Rouge", "Noir"], 2, ["Jaune"]),
            phrase(["Bleu", "Mauve", "Rouge", "Noir"], 2, ["Vert"]),
        )

        def valide(phrases, pleines):
            sortie = set()
            for p in phrases:
                if p.tient(frozenset(pleines)):
                    sortie |= p.cibles
            return sortie

        for taille in range(len(COULEURS) + 1):
            for pleines in itertools.combinations(COULEURS, taille):
                complet = valide(regles, pleines)
                for k in range(len(regles)):
                    partiel = valide(regles[:k] + regles[k + 1:], pleines)
                    assert partiel <= complet


class TestImplique:
    def test_exact_sur_toutes_les_combinaisons(self):
        """`implique` doit être exact : ni faux positif, ni faux négatif.

        Chaque paire est confrontée à la vérité, obtenue par force brute sur les
        64 combinaisons. Une seule erreur, et le contrôle accuserait une règle
        vivante ou laisserait passer une règle morte.
        """
        jeux = [tuple(c) for taille in range(1, 4)
                for c in itertools.combinations(COULEURS, taille)]
        combinaisons = [frozenset(c) for taille in range(len(COULEURS) + 1)
                        for c in itertools.combinations(COULEURS, taille)]
        essais = 0
        for pa in jeux:
            for pb in jeux:
                for sa in range(1, len(pa) + 1):
                    for sb in range(1, len(pb) + 1):
                        a = phrase(pa, sa, ["Jaune"])
                        b = phrase(pb, sb, ["Jaune"])
                        reel = all(a.tient(p) for p in combinaisons if b.tient(p))
                        assert module.implique(b, a) is reel, (pa, sa, pb, sb)
                        essais += 1
        assert essais > 1000


# --- La règle du classeur ----------------------------------------------------

class TestRegleDuClasseur:
    def test_quatre_phrases(self):
        """Rouge et Noir ne sont pas validables : Rouge n'a qu'une couleur plus
        dure au-dessus de lui, et Noir aucune. Le classeur fait pareil."""
        regles = module.regle_du_classeur()
        assert len(regles) == 4
        cibles = {c for p in regles for c in p.cibles}
        assert cibles == {"Jaune", "Vert", "Bleu", "Mauve"}

    @pytest.mark.parametrize("pleines,attendu", [
        (["Rouge", "Noir"], {"Jaune", "Vert", "Bleu", "Mauve"}),   # K1
        (["Noir"], set()),                                          # K2
        (["Noir", "Bleu"], {"Jaune", "Vert"}),                      # K3
        # ⚠️ Mauve figure dans le resultat alors qu'il est deja plein : une
        # couleur pleine peut aussi etre « validee », et ca ne change rien
        # puisque ses blocs sont deja grimpes.
        (["Mauve", "Rouge", "Noir"], {"Jaune", "Vert", "Bleu", "Mauve"}),  # K4
        ([], set()),                                                # K5
    ])
    def test_les_cas_mesures_dans_le_classeur(self, pleines, attendu):
        """⚠️ Les quatre cas relevés le 02/09/2026 en activant `Listes!D29:D38`
        dans une copie jetable du classeur. Si ce test tombe, le serveur ne
        calcule plus ce que calcule le classeur."""
        obtenu = set()
        for p in module.regle_du_classeur():
            if p.tient(frozenset(pleines)):
                obtenu |= p.cibles
        assert obtenu == attendu

    def test_aucun_signalement(self):
        assert module.controler(module.regle_du_classeur()) == ([], [])

    def test_est_reconnue(self):
        casc = Cascade(phrases=module.regle_du_classeur())
        assert module.est_celle_du_classeur(casc)
        autre = Cascade(phrases=(phrase(["Rouge"], 1, ["Jaune"]),))
        assert not module.est_celle_du_classeur(autre)


# --- Le contrôle -------------------------------------------------------------

class TestControle:
    def test_phrase_sans_declencheur(self):
        bloquants, _ = module.controler((phrase([], 1, ["Jaune"]),))
        assert bloquants and "declencheur" in bloquants[0]

    def test_phrase_sans_cible(self):
        bloquants, _ = module.controler((phrase(["Rouge"], 1, []),))
        assert bloquants and "valider" in bloquants[0]

    def test_cascade_qui_remonte(self):
        """« toutes les Jaune → valider les Rouge » : ça bloque.

        Une matrice l'interdirait par construction ; une phrase, non. C'est le
        seul défaut que la forme « phrase » introduit, donc le seul qui bloque.
        """
        bloquants, _ = module.controler((phrase(["Jaune"], 1, ["Rouge"]),))
        assert bloquants and "ne remonte pas" in bloquants[0]

    def test_seuil_plus_grand_que_le_choix(self):
        bloquants, _ = module.controler((phrase(["Rouge"], 2, ["Jaune"]),))
        assert bloquants

    def test_regle_morte(self):
        """LE piège : on écrit une condition qu'on croit plus stricte, et une
        autre phrase, plus facile à satisfaire, a déjà tout donné."""
        regles = module.regle_du_classeur() + (phrase(["Rouge", "Noir"], 2, ["Jaune"]),)
        bloquants, avertis = module.controler(regles)
        assert bloquants == []
        assert len(avertis) == 1
        assert avertis[0].startswith("Regle 5 sans effet")

    def test_deux_phrases_equivalentes_ne_s_accusent_pas(self):
        """Sinon chacune accuse l'autre et on ne sait pas laquelle retirer."""
        deux = (phrase(["Rouge"], 1, ["Jaune"]), phrase(["Rouge"], 1, ["Jaune"]))
        _, avertis = module.controler(deux)
        assert len([a for a in avertis if "sans effet" in a]) == 1

    def test_deux_phrases_sur_la_meme_couleur(self):
        """Ce n'est pas une faute : elles s'additionnent. Mais celui qui écrit
        la seconde croit souvent remplacer la première."""
        deux = (phrase(["Rouge"], 1, ["Jaune"]), phrase(["Noir"], 1, ["Jaune"]))
        bloquants, avertis = module.controler(deux)
        assert bloquants == []
        assert any("s'additionnent" in a for a in avertis)

    def test_une_erreur_masque_les_avertissements(self):
        """Tant qu'une phrase ne veut rien dire, chercher les règles mortes ne
        rendrait qu'un bruit qu'on ne peut pas corriger."""
        regles = (phrase(["Jaune"], 1, ["Rouge"]), phrase(["Rouge"], 1, ["Jaune"]))
        bloquants, avertis = module.controler(regles)
        assert bloquants and avertis == []


# --- La lecture et l'écriture ------------------------------------------------

class TestLecture:
    def test_absente(self):
        assert not module.depuis_options({})

    def test_inactive(self):
        casc = module.depuis_options({"cascade": {"actif": False, "regles": [
            {"parmi": ["Rouge"], "seuil": 1, "cibles": ["Jaune"]}]}})
        assert not casc

    def test_lue(self):
        casc = module.depuis_options({"cascade": {
            "actif": True,
            "regles": [{"parmi": ["Rouge", "Noir"], "seuil": 2, "cibles": ["Jaune"]}],
            "categories_eteintes": ["U11 F"],
        }})
        assert len(casc.phrases) == 1
        assert casc.phrases[0].seuil == 2
        assert casc.categories_eteintes == frozenset({"U11 F"})

    def test_document_abime_rend_une_cascade_vide(self):
        """Le classement doit sortir le jour d'une compétition, même dégradé."""
        assert not module.depuis_options({"cascade": {
            "actif": True, "regles": [{"parmi": ["Rose"], "seuil": 1, "cibles": ["Jaune"]}]}})

    def test_repli_sur_l_ancienne_option(self):
        """⚠️ Compatibilité : `validation_couleur = N` vaut EXACTEMENT
        « au moins N parmi les couleurs plus dures »."""
        casc = module.depuis_options({"validation_couleur": 2})
        assert casc.phrases == module.regle_du_classeur(2)

    def test_repli_a_zero(self):
        assert not module.depuis_options({"validation_couleur": 0})

    def test_repli_illisible(self):
        assert not module.depuis_options({"validation_couleur": "beaucoup"})

    def test_aller_retour(self):
        casc = Cascade(phrases=module.regle_du_classeur(),
                       categories_eteintes=frozenset({"U11 F"}))
        relu = module.depuis_options({"cascade": module.en_json(casc)})
        assert set(relu.phrases) == set(casc.phrases)
        assert relu.categories_eteintes == casc.categories_eteintes


class TestValider:
    def test_regle_correcte(self):
        doc, avertis = module.valider({
            "actif": True,
            "regles": [{"parmi": ["Rouge", "Noir"], "seuil": 2, "cibles": ["Jaune"]}],
            "categories_eteintes": ["U11 F"],
        })
        assert doc["actif"] is True
        assert doc["categories_eteintes"] == ["U11 F"]
        assert avertis == []

    def test_regle_qui_remonte_est_refusee(self):
        with pytest.raises(ErreurMetier):
            module.valider({"actif": True, "regles": [
                {"parmi": ["Jaune"], "seuil": 1, "cibles": ["Rouge"]}]})

    def test_couleur_inconnue(self):
        with pytest.raises(ErreurMetier):
            module.valider({"actif": True, "regles": [
                {"parmi": ["Rose"], "seuil": 1, "cibles": ["Jaune"]}]})

    def test_inactif_jette_les_regles(self):
        doc, _ = module.valider({"actif": False, "regles": [
            {"parmi": ["Rouge"], "seuil": 1, "cibles": ["Jaune"]}]})
        assert doc["actif"] is False and doc["regles"] == []

    def test_categorie_inconnue_est_acceptee(self):
        """Elle peut réapparaître au prochain import ; le silence serait pire."""
        doc, _ = module.valider({"actif": False, "regles": [],
                                 "categories_eteintes": ["U19 F"]})
        assert doc["categories_eteintes"] == ["U19 F"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
class TestLesDeuxControlesDisentPareil:
    """Le contrôle existe en DOUBLE : en Python, qui fait autorité, et en
    JavaScript, pour que la console réponde sans aller-retour.

    Deux copies d'une même règle finissent toujours par diverger. Ce test est
    ce qui l'empêche : il extrait la fonction du gabarit et la confronte à celle
    du serveur sur **toutes** les paires possibles — 36 864 — pas sur un
    échantillon.
    """

    GABARIT = (Path(__file__).resolve().parent.parent
               / "climbcontest" / "templates" / "admin.html")

    def test_implique_est_identique(self):
        source = self.GABARIT.read_text(encoding="utf-8")
        bloc = re.search(r"function implique\(b, a\) \{[\s\S]*?\n  \}", source)
        assert bloc, "la fonction `implique` a disparu du gabarit"

        script = """
        %s
        const C = ["Jaune","Vert","Bleu","Mauve","Rouge","Noir"];
        const cas = [];
        for (let m = 1; m < 64; m++) {
          const parmi = C.filter((_, i) => m & (1 << i));
          for (let s = 1; s <= parmi.length; s++) cas.push({parmi, seuil: s});
        }
        const out = [];
        for (const a of cas) for (const b of cas) {
          out.push([a.parmi.join("|"), a.seuil, b.parmi.join("|"), b.seuil,
                    implique(b, a) ? 1 : 0].join(";"));
        }
        console.log(out.join("\\n"));
        """ % bloc.group(0)

        sortie = subprocess.run(["node", "--input-type=module", "-e", script],
                                capture_output=True, text=True, timeout=60)
        assert sortie.returncode == 0, sortie.stderr

        ecarts = 0
        lignes = sortie.stdout.strip().splitlines()
        for ligne in lignes:
            pa, sa, pb, sb, r = ligne.split(";")
            a = phrase(pa.split("|"), int(sa), ["Jaune"])
            b = phrase(pb.split("|"), int(sb), ["Jaune"])
            if module.implique(b, a) != (r == "1"):
                ecarts += 1
        assert len(lignes) > 30000
        assert ecarts == 0, f"{ecarts} desaccord(s) entre les deux controles"

