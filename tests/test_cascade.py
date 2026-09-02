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
import random
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

    Deux copies d'une même règle finissent toujours par diverger. Ce test est ce
    qui l'empêche : il extrait le bloc « contrôle pur » du gabarit et le
    confronte à `cascade.analyser` — **le contrôle entier**, pas seulement le
    test d'implication. On compare les constats bruts, pas les messages : les
    seconds sont traduits d'un côté et pas de l'autre, et ça ne prouverait rien.
    """

    GABARIT = (Path(__file__).resolve().parent.parent
               / "climbcontest" / "templates" / "admin.html")

    def _bloc_pur(self) -> str:
        source = self.GABARIT.read_text(encoding="utf-8")
        debut = source.index("/* ===== debut du controle pur")
        fin = source.index("/* ===== fin du controle pur")
        return source[debut:fin]

    def _jeux(self, combien: int) -> list:
        """Des jeux de phrases tirés au hasard, seuils absurdes compris."""
        alea = random.Random(20260902)
        jeux = []
        for _ in range(combien):
            regles = []
            for _ in range(alea.randint(1, 4)):
                parmi = [c for c in COULEURS if alea.random() < 0.45]
                cibles = [c for c in COULEURS if alea.random() < 0.3]
                seuil = alea.randint(0, 4)
                regles.append({"parmi": parmi, "seuil": seuil, "cibles": cibles})
            jeux.append(regles)
        return jeux

    def test_les_constats_sont_identiques(self):
        jeux = self._jeux(600)
        script = """
        %s
        const jeux = %s;
        console.log(JSON.stringify(jeux.map(analyserRegles)));
        """ % (self._bloc_pur(), json.dumps(jeux))

        sortie = subprocess.run(["node", "--input-type=module", "-e", script],
                                capture_output=True, text=True, timeout=120)
        assert sortie.returncode == 0, sortie.stderr
        cote_navigateur = json.loads(sortie.stdout)
        assert len(cote_navigateur) == len(jeux)

        ecarts = []
        for regles, js in zip(jeux, cote_navigateur):
            phrases = tuple(
                phrase(r["parmi"], r["seuil"], r["cibles"]) for r in regles)
            py = module.analyser(phrases)
            # Les codes bloquants, dans le meme ordre.
            if [(b[0], b[1]) for b in py["bloquants"]] != [
                    (b[0], b[1]) for b in js["bloquants"]]:
                ecarts.append(("bloquants", regles, py, js))
                continue
            if [tuple(m) for m in py["mortes"]] != [tuple(m) for m in js["mortes"]]:
                ecarts.append(("mortes", regles, py, js))
                continue
            if [(c[0], c[1], list(c[2])) for c in py["communes"]] != [
                    [c[0], c[1], list(c[2])] for c in js["communes"]]:
                ecarts.append(("communes", regles, py, js))
        assert not ecarts, ecarts[:2]

    def test_le_test_d_implication_est_identique(self):
        """Toutes les paires possibles, seuils hors bornes compris."""
        script = """
        %s
        const C = COULEURS_DIF;
        const cas = [];
        for (let m = 1; m < 64; m++) {
          const parmi = C.filter((_, i) => m & (1 << i));
          for (let s = 0; s <= parmi.length + 1; s++) cas.push({parmi, seuil: s});
        }
        const out = [];
        for (const a of cas) for (const b of cas) {
          out.push([a.parmi.join("|"), a.seuil, b.parmi.join("|"), b.seuil,
                    implique(b, a) ? 1 : 0].join(";"));
        }
        console.log(out.join("\\n"));
        """ % self._bloc_pur()
        sortie = subprocess.run(["node", "--input-type=module", "-e", script],
                                capture_output=True, text=True, timeout=120)
        assert sortie.returncode == 0, sortie.stderr

        lignes = sortie.stdout.strip().splitlines()
        assert len(lignes) > 50000
        for ligne in lignes:
            pa, sa, pb, sb, r = ligne.split(";")
            a = phrase(pa.split("|"), int(sa), ["Jaune"])
            b = phrase(pb.split("|"), int(sb), ["Jaune"])
            assert module.implique(b, a) == (r == "1"), ligne


class TestRepliExact:
    """⚠️ Le critère A3 : une édition d'avant la spec 025 doit se classer
    EXACTEMENT comme avant.

    L'ancien moteur a été supprimé par ce commit ; on le rejoue donc ici, épinglé
    tel qu'il était, et on le confronte à sa réécriture en phrases. Sans ce test,
    l'affirmation « la conversion est exacte » ne serait qu'une relecture.
    """

    COULEURS_ORDONNEES = list(COULEURS)

    def _ancien(self, pleines: set, n: int) -> set:
        """`_valider_par_couleur` d'avant la spec 025, réduit à sa décision.

        « Les N couleurs pleines les plus dures ; la plus FACILE d'entre elles
        fixe un seuil ; tout ce qui est plus facile est validé. »
        """
        ordre = self.COULEURS_ORDONNEES
        dures_en_premier = [c for c in reversed(ordre) if c in pleines]
        if len(dures_en_premier) < n:
            return set()
        seuil = min(ordre.index(c) for c in dures_en_premier[:n])
        return {c for c in ordre if ordre.index(c) < seuil}

    def _nouveau(self, pleines: set, n: int) -> set:
        valides = set()
        for phrase in module.regle_du_classeur(n):
            if phrase.tient(frozenset(pleines)):
                valides |= phrase.cibles
        return valides

    def _comptees(self, valide, pleines: set, n: int) -> set:
        """Les couleurs dont les blocs comptent au classement.

        ⚠️ C'est LA bonne unité de comparaison. Les deux écritures ne
        s'accordent pas sur le fait de re-nommer une couleur déjà pleine — la
        nouvelle le fait, l'ancienne non — et ça ne change rien : ses blocs sont
        déjà comptés. Comparer les seules couleurs « ajoutées » ferait échouer
        le test sur une différence qui n'existe pas au classement.
        """
        return set(pleines) | valide(pleines, n)

    def test_la_conversion_est_exacte(self):
        """Toutes les combinaisons de couleurs pleines, pour N = 1, 2 et 3."""
        essais = ecarts = 0
        for taille in range(len(COULEURS) + 1):
            for pleines in itertools.combinations(COULEURS, taille):
                for n in (1, 2, 3):
                    essais += 1
                    avant = self._comptees(self._ancien, set(pleines), n)
                    apres = self._comptees(self._nouveau, set(pleines), n)
                    if avant != apres:
                        ecarts += 1
        assert essais == 192, essais
        assert ecarts == 0

    def test_sur_les_donnees_reelles_de_novembre_2025(self):
        """Le même contrôle, sur les couleurs vraiment présentes en 2025 —
        aucun circuit n'y avait de Noir."""
        reelles = ["Jaune", "Vert", "Bleu", "Mauve", "Rouge"]
        for taille in range(len(reelles) + 1):
            for pleines in itertools.combinations(reelles, taille):
                for n in (1, 2, 3):
                    assert (self._comptees(self._ancien, set(pleines), n)
                            == self._comptees(self._nouveau, set(pleines), n))


class TestControleExhaustif:
    """Le contrôle attrape-t-il TOUTES les phrases sans effet ?

    Un test par paires en laissait passer : une phrase peut être tuée par la
    RÉUNION de plusieurs autres. On confronte ici `controler` à la vérité,
    obtenue en retirant réellement chaque phrase.
    """

    def _sortie(self, phrases, pleines):
        s = set()
        for p in phrases:
            if p.tient(pleines):
                s |= p.cibles
        return frozenset(s)

    def _combinaisons(self):
        return [frozenset(c) for n in range(len(COULEURS) + 1)
                for c in itertools.combinations(COULEURS, n)]

    def test_une_phrase_tuee_par_la_reunion_de_deux_autres(self):
        """Aucun test par paires ne voit celle-ci : ni la 1 ni la 3 n'implique
        la 2 à elle seule."""
        regles = (
            phrase(["Rouge"], 1, ["Jaune"]),
            phrase(["Vert", "Mauve", "Rouge", "Noir"], 2, ["Jaune"]),
            phrase(["Vert", "Bleu", "Noir"], 1, ["Jaune"]),
        )
        bloquants, avertis = module.controler(regles)
        assert bloquants == []
        assert any(a.startswith("Regle 2 sans effet") for a in avertis)

    def test_aucune_phrase_signalee_a_tort(self):
        """Retirer tout ce que le contrôle signale ne doit RIEN changer."""
        combinaisons = self._combinaisons()
        jeux = [
            module.regle_du_classeur(),
            (phrase(["Rouge"], 1, ["Jaune"]), phrase(["Noir"], 1, ["Jaune"])),
            (phrase(["Rouge"], 1, ["Jaune", "Vert"]),
             phrase(["Rouge", "Noir"], 2, ["Jaune"])),
            (phrase(["Vert", "Bleu"], 1, ["Jaune"]),
             phrase(["Bleu"], 1, ["Jaune"]),
             phrase(["Vert"], 1, ["Jaune"])),
        ]
        for regles in jeux:
            _, avertis = module.controler(regles)
            mortes = {int(a.split()[1]) - 1 for a in avertis if "sans effet" in a}
            restantes = tuple(r for i, r in enumerate(regles) if i not in mortes)
            for c in combinaisons:
                assert self._sortie(restantes, c) == self._sortie(regles, c)

    def test_deux_phrases_identiques_ne_s_excusent_pas_mutuellement(self):
        """Si on les retirait toutes les deux, la sortie changerait : une seule
        doit être signalée."""
        deux = (phrase(["Rouge"], 1, ["Jaune"]), phrase(["Rouge"], 1, ["Jaune"]))
        _, avertis = module.controler(deux)
        assert len([a for a in avertis if "sans effet" in a]) == 1


class TestEntreesHostiles:
    """Ce qui est RANGÉ est contrôlé comme ce qui est saisi.

    Un document écrit à la main ou venu d'une version future passerait sinon
    derrière tous les garde-fous.
    """

    @pytest.mark.parametrize("regle", [
        {"parmi": [], "seuil": 0, "cibles": ["Jaune", "Vert"]},
        {"parmi": ["Rouge", "Noir"], "seuil": False, "cibles": ["Jaune"]},
        {"parmi": ["Noir"], "seuil": -1, "cibles": ["Jaune"]},
        {"parmi": ["Jaune"], "seuil": 1, "cibles": ["Noir"]},      # remonte
        {"parmi": ["Rouge"], "seuil": 2.9, "cibles": ["Jaune"]},
        {"parmi": ["Rouge"], "seuil": "3", "cibles": ["Jaune"]},
    ])
    def test_une_regle_rangee_invalide_est_ignoree(self, regle):
        """Un seuil nul ou négatif rend `len(parmi & pleines) >= seuil` toujours
        vrai : la cascade validerait les six couleurs pour TOUT LE MONDE."""
        casc = module.depuis_options(
            {"cascade": {"actif": True, "regles": [regle]}})
        assert not casc

    def test_un_nombre_non_fini_ne_leve_pas(self):
        """`json.loads` accepte `Infinity`, et `int(inf)` leve OverflowError —
        que personne ne rattrapait. Le classement doit sortir quand meme."""
        options = json.loads(
            '{"cascade": {"actif": true, "regles": [{"parmi": ["Rouge"], '
            '"seuil": Infinity, "cibles": ["Jaune"]}]}}')
        assert not module.depuis_options(options)
        assert not module.depuis_options(json.loads('{"validation_couleur": Infinity}'))

    def test_l_ancienne_option_a_vrai_n_est_pas_un_compte(self):
        """`int(True)` vaut 1, donc un booleen passerait pour la regle la plus
        agressive — celle qui change 264 rangs sur 392."""
        assert not module.depuis_options({"validation_couleur": True})

    def test_trop_de_regles(self):
        trop = [{"parmi": ["Rouge"], "seuil": 1, "cibles": ["Jaune"]}] * 50
        with pytest.raises(ErreurMetier):
            module.depuis_json(trop)

    def test_la_portee_survit_a_une_regle_eteinte(self):
        """Sinon un aller-retour par une liste vide efface les interrupteurs."""
        casc = module.depuis_options({"cascade": {
            "actif": False, "regles": [], "categories_eteintes": ["U11 F"]}})
        assert casc.categories_eteintes == frozenset({"U11 F"})

    def test_l_aller_retour_est_fidele(self):
        document, _ = module.valider({
            "actif": False, "regles": [], "categories_eteintes": ["U11 F", "U13 F"]})
        relu = module.depuis_options({"cascade": document})
        assert relu.categories_eteintes == frozenset({"U11 F", "U13 F"})

    def test_les_categories_sont_nettoyees_a_la_lecture(self):
        """Un document ecrit a la main donne sinon un interrupteur inerte."""
        casc = module.depuis_options({"cascade": {
            "actif": False, "categories_eteintes": ["  U11 F  ", "", "   "]}})
        assert casc.categories_eteintes == frozenset({"U11 F"})

    def test_une_cascade_qui_n_est_pas_un_objet(self):
        assert not module.depuis_options({"cascade": "pas un objet"})

    def test_une_couleur_hostile_ne_part_pas_entiere_dans_le_message(self):
        with pytest.raises(ErreurMetier) as e:
            module.depuis_json([{"parmi": ["Rouge\n2026 ERROR fausse ligne de journal"],
                                 "seuil": 1, "cibles": ["Jaune"]}])
        assert "\n" not in e.value.message
        assert len(e.value.message) < 200


class TestEstCelleDuClasseur:
    def test_une_phrase_sans_effet_ajoutee_ne_change_rien(self):
        """⚠️ On compare ce que les phrases CALCULENT, pas leur ecriture.
        Sinon l'ecran crie « le classeur ne saura pas suivre » alors qu'il
        suit parfaitement — et on apprend a ne plus lire l'avertissement."""
        avec_morte = Cascade(phrases=module.regle_du_classeur()
                             + (phrase(["Rouge", "Noir"], 2, ["Jaune"]),))
        assert module.est_celle_du_classeur(avec_morte)

    def test_une_vraie_difference_est_vue(self):
        autre = Cascade(phrases=(phrase(["Rouge"], 1, ["Jaune"]),))
        assert not module.est_celle_du_classeur(autre)


class TestRegleDuClasseurBornes:
    def test_un_seuil_absurde_est_refuse(self):
        """Sans garde, « au moins 0 parmi [] » se declenche sur RIEN et valide
        les six couleurs pour tout le monde."""
        for mauvais in (0, -1):
            with pytest.raises(ValueError):
                module.regle_du_classeur(mauvais)

