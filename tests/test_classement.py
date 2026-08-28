"""Le moteur de classement reproduit le classeur, ou il ne sert à rien.

Le test qui décide est `test_reproduit_novembre_2025` : 196 scores et rangs
réels, issus des formules du classeur Google, sur 1003 réussites. Le reste
couvre les cas limites qu'un jeu réel ne contient pas forcément.
"""

import json
from pathlib import Path

import pytest

from climbcontest.classement import (
    BlocCalcul, ParticipantCalcul, calculer_groupe, calculer_tout,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "contest-nov2025.json"


# --- Le test de référence ----------------------------------------------------

@pytest.fixture(scope="module")
def nov2025():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class TestDonneesReelles:
    def test_reproduit_novembre_2025(self, nov2025):
        """196 scores ET rangs, 8 catégories, 4 circuits, 1003 réussites.

        Si ce test tombe, le moteur ne calcule pas ce que calcule le classeur —
        et le classement affiché aux grimpeurs serait faux.
        """
        participants = [
            ParticipantCalcul(id=p["bib"], dossard=p["bib"], categorie=p["category"])
            for p in nov2025["climbers"]
        ]
        blocs = {
            b["number"]: BlocCalcul(id=b["number"], tag=b["tag"],
                                    couleur=b["color"], circuits=frozenset(b["circuits"]))
            for b in nov2025["blocs"]
        }
        reussites: dict[int, set[int]] = {}
        for t in nov2025["tops"]:
            reussites.setdefault(t["bib"], set()).add(t["bloc"])

        obtenus = calculer_tout(participants, blocs, reussites)

        attendus = {**nov2025["expected"]["by_category"],
                    **nov2025["expected"]["by_circuit"]}

        ecarts, verifies = [], 0
        for groupe, lignes_attendues in attendus.items():
            assert groupe in obtenus, f"groupe « {groupe} » absent du calcul"
            par_dossard = {l.dossard: l for l in obtenus[groupe].lignes}
            for attendue in lignes_attendues:
                verifies += 1
                obtenue = par_dossard.get(attendue["bib"])
                if obtenue is None:
                    ecarts.append(f"{groupe} dossard {attendue['bib']} : absent")
                elif (obtenue.score, obtenue.rang) != (attendue["score"], attendue["rank"]):
                    ecarts.append(
                        f"{groupe} dossard {attendue['bib']} : "
                        f"classeur score={attendue['score']} rang={attendue['rank']} | "
                        f"moteur score={obtenue.score} rang={obtenue.rang}")

        assert verifies == 196, f"196 lignes attendues, {verifies} verifiees"
        assert not ecarts, "ecarts avec le classeur :\n  " + "\n  ".join(ecarts[:12])

    def test_le_filtre_par_circuit_est_indispensable(self, nov2025):
        """Sans lui, 17 grimpeurs sur 98 ont un score trop élevé.

        On le prouve en retirant le filtre — c'est-à-dire en mettant tous les
        blocs dans tous les circuits — et en constatant que le résultat diverge.
        """
        participants = [
            ParticipantCalcul(id=p["bib"], dossard=p["bib"], categorie=p["category"])
            for p in nov2025["climbers"]
        ]
        tous_circuits = frozenset({c for b in nov2025["blocs"] for c in b["circuits"]})
        blocs_sans_filtre = {
            b["number"]: BlocCalcul(id=b["number"], tag=b["tag"],
                                    couleur=b["color"], circuits=tous_circuits)
            for b in nov2025["blocs"]
        }
        reussites: dict[int, set[int]] = {}
        for t in nov2025["tops"]:
            reussites.setdefault(t["bib"], set()).add(t["bloc"])

        obtenus = calculer_tout(participants, blocs_sans_filtre, reussites)

        divergents = 0
        for groupe, attendues in nov2025["expected"]["by_category"].items():
            par_dossard = {l.dossard: l for l in obtenus[groupe].lignes}
            for a in attendues:
                o = par_dossard.get(a["bib"])
                if o and o.score != a["score"]:
                    divergents += 1
        assert divergents > 0, (
            "sans filtre par circuit le resultat devrait diverger : "
            "si ce test passe, le filtre n'est pas reellement applique")

    def test_rapide(self, nov2025):
        """Moins d'une seconde pour les 12 groupes."""
        import time
        participants = [
            ParticipantCalcul(id=p["bib"], dossard=p["bib"], categorie=p["category"])
            for p in nov2025["climbers"]
        ]
        blocs = {
            b["number"]: BlocCalcul(id=b["number"], tag=b["tag"], couleur=b["color"],
                                    circuits=frozenset(b["circuits"]))
            for b in nov2025["blocs"]
        }
        reussites: dict[int, set[int]] = {}
        for t in nov2025["tops"]:
            reussites.setdefault(t["bib"], set()).add(t["bloc"])

        debut = time.monotonic()
        calculer_tout(participants, blocs, reussites)
        duree = time.monotonic() - debut
        assert duree < 1.0, f"calcul trop lent : {duree:.2f}s"


# --- Les cas limites ---------------------------------------------------------

def p(id_, cat="U11 F", dossard=None):
    return ParticipantCalcul(id=id_, dossard=dossard if dossard is not None else id_,
                             categorie=cat)


def b(id_, circuits=("U11",), couleur="Jaune"):
    return BlocCalcul(id=id_, tag=f"B{id_}", couleur=couleur,
                      circuits=frozenset(circuits))


BLOCS = {i: b(i) for i in range(1, 5)}


class TestValeurDesBlocs:
    def test_un_seul_grimpeur_le_bloc_vaut_1000(self):
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2)], BLOCS, {1: {1}})
        assert c.lignes[0].score == 1000
        assert c.lignes[1].score == 0

    def test_deux_grimpeurs_le_bloc_vaut_500_chacun(self):
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2)], BLOCS,
                            {1: {1}, 2: {1}})
        assert [l.score for l in c.lignes] == [500, 500]

    def test_trois_grimpeurs_arrondi(self):
        """1000/3 = 333,33 → arrondi à l'entier, comme ROUND() du classeur."""
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2), p(3)], BLOCS,
                            {1: {1}, 2: {1}, 3: {1}})
        assert all(l.score == 333 for l in c.lignes)

    def test_bloc_que_personne_n_a_reussi(self):
        """Pas de division par zéro, et il ne rapporte rien."""
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], BLOCS, {})
        assert c.lignes[0].score == 0

    def test_participant_sans_reussite_figure_au_classement(self):
        """Il est venu : il doit apparaître, avec 0."""
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2)], BLOCS, {1: {1}})
        assert len(c.lignes) == 2
        assert c.lignes[1].score == 0


class TestFiltreCircuit:
    def test_bloc_dans_aucun_circuit_ne_compte_nulle_part(self):
        """Il reste au catalogue — un juge peut le scanner — mais il ne rapporte rien.

        Le cas arrive vraiment : un bloc pose puis retire du format, ou une
        ligne d'import a laquelle personne n'a affecte de circuit. Il ne doit ni
        planter le calcul, ni gonfler un score.
        """
        blocs = {1: b(1, circuits=("U11",)), 2: b(2, circuits=())}
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs, {1: {1, 2}})
        assert c.lignes[0].score == 1000
        assert c.lignes[0].blocs_reussis == 1, "le bloc sans circuit ne doit pas compter"

    def test_bloc_hors_circuit_ne_compte_pas(self):
        """La réussite est réelle et stockée, mais elle ne rapporte rien.

        C'est ce que fait le classeur : l'onglet Import la contient, les
        formules l'ignorent.
        """
        blocs = {1: b(1, circuits=("U11",)), 2: b(2, circuits=("U13",))}
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs, {1: {1, 2}})
        assert c.lignes[0].score == 1000        # seul le bloc 1 compte
        assert c.lignes[0].blocs_reussis == 1

    def test_un_bloc_dans_deux_circuits_compte_dans_les_deux(self):
        blocs = {1: b(1, circuits=("U11", "U13"))}
        for circuit, cat in [("U11", "U11 F"), ("U13", "U13 F")]:
            c = calculer_groupe(cat, "categorie", circuit, [p(1, cat)], blocs, {1: {1}})
            assert c.lignes[0].score == 1000

    def test_sans_circuit_classement_vide_et_signale(self):
        c = calculer_groupe("Inconnue", "categorie", None, [p(1)], BLOCS, {1: {1}})
        assert c.lignes == []
        assert c.avertissements


class TestRangs:
    def test_ex_aequo_partagent_le_rang_et_le_suivant_saute(self):
        """Deux premiers, pas de deuxième, le suivant est troisième.

        C'est le comportement de RANK() dans le classeur.
        """
        blocs = {1: b(1), 2: b(2)}
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2), p(3)], blocs,
                            {1: {1}, 2: {1}, 3: set()})
        rangs = [(l.dossard, l.score, l.rang) for l in c.lignes]
        assert rangs == [(1, 500, 1), (2, 500, 1), (3, 0, 3)]

    def test_ordre_stable_a_score_egal(self):
        """À score égal, l'ordre suit le dossard : le classement ne doit pas
        changer d'un rafraîchissement à l'autre."""
        c1 = calculer_groupe("U11 F", "categorie", "U11", [p(3), p(1), p(2)], BLOCS, {})
        c2 = calculer_groupe("U11 F", "categorie", "U11", [p(2), p(3), p(1)], BLOCS, {})
        assert [l.dossard for l in c1.lignes] == [l.dossard for l in c2.lignes]

    def test_participant_sans_dossard_ne_casse_pas_le_tri(self):
        membres = [ParticipantCalcul(id=9, dossard=None, categorie="U11 F"), p(1)]
        c = calculer_groupe("U11 F", "categorie", "U11", membres, BLOCS, {9: {1}})
        assert c.lignes[0].participant_id == 9      # meilleur score d'abord


class TestScratchParCircuit:
    def test_filles_et_garcons_ensemble(self):
        """Le « scratch » du classeur est par circuit, pas toutes catégories."""
        membres = [p(1, "U11 F"), p(2, "U11 H"), p(3, "U13 F")]
        blocs = {1: b(1, circuits=("U11", "U13"))}
        tous = calculer_tout(membres, blocs, {1: {1}, 2: {1}, 3: {1}})

        # En U11, deux grimpeurs ont le bloc : il vaut 500.
        assert {l.score for l in tous["U11"].lignes} == {500}
        # En U11 F, une seule : il vaut 1000. Le même bloc, deux valeurs.
        assert tous["U11 F"].lignes[0].score == 1000
        # U13 est un circuit distinct, jamais mélangé.
        assert [l.dossard for l in tous["U13"].lignes] == [3]


class TestParticipantsIncomplets:
    """Des lignes incompletes arrivent du classeur et de la saisie manuelle.

    Aucune ne doit faire disparaitre un grimpeur ni lever une exception : la
    page resultats est publique, elle ne peut pas afficher une erreur 500 devant
    cent spectateurs.
    """

    def test_participant_sans_categorie_absent_des_classements_par_categorie(self):
        sans = ParticipantCalcul(id=9, dossard=99, categorie=None)
        tous = calculer_tout([p(1), sans], BLOCS, {1: {1}, 9: {1}})
        classes = {l.participant_id for c in tous.values() for l in c.lignes}
        assert 9 not in classes, "sans categorie, on ne sait pas dans quel groupe le mettre"
        assert 1 in classes, "les autres restent classes"

    def test_participant_sans_categorie_ne_fait_pas_planter(self):
        sans = ParticipantCalcul(id=9, dossard=99, categorie="")
        calculer_tout([p(1), sans], BLOCS, {1: {1}})      # ne doit rien lever

    def test_participant_sans_dossard_est_compte_s_il_a_des_reussites(self):
        """Le cas de la saisie manuelle : quelqu'un qui grimpe sans dossard imprime."""
        anonyme = ParticipantCalcul(id=9, dossard=None, categorie="U11 F")
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1), anonyme], BLOCS,
                            {9: {1}})
        ligne = next(l for l in c.lignes if l.participant_id == 9)
        assert ligne.score == 1000, "une reussite compte, dossard ou pas"
        assert ligne.rang == 1


class TestValidationParCouleur:
    """Option par compétition. Désactivée par défaut."""

    def _jeu(self):
        # 2 jaunes, 2 verts, 1 bleu — du plus facile au plus dur.
        return {
            1: b(1, couleur="Jaune"), 2: b(2, couleur="Jaune"),
            3: b(3, couleur="Vert"), 4: b(4, couleur="Vert"),
            5: b(5, couleur="Bleu"),
        }

    def test_desactivee_par_defaut(self):
        blocs = self._jeu()
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs, {1: {3, 4, 5}})
        assert c.lignes[0].blocs_reussis == 3      # pas d'extension

    def test_presque_toute_une_couleur_ne_valide_rien(self):
        """La regle dit 100 %, pas « presque ».

        Un grimpeur a 3 des 4 blocs verts et bleus. S'il suffisait d'etre pres du
        compte, tous les jaunes lui seraient offerts et le podium changerait.
        """
        blocs = self._jeu()
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {3, 5}}, couleurs_requises=2)   # il manque le 4
        assert c.lignes[0].blocs_reussis == 2, "aucune extension attendue"

    def test_une_couleur_hors_du_circuit_ne_compte_pas_comme_pleine(self):
        """Le decompte des couleurs pleines se fait DANS le circuit, pas dans tout le mur.

        Sinon un grimpeur U11 qui a fait, par curiosite, le seul bloc Noir du
        circuit U13 se verrait crediter une couleur pleine — et les Jaunes lui
        seraient offerts. Le cas est realiste : rien n'empeche de scanner un
        bloc d'un autre circuit, et le classeur enregistre bien la reussite.
        """
        blocs = {
            1: b(1, circuits=("U11",), couleur="Jaune"),
            2: b(2, circuits=("U11",), couleur="Vert"),
            3: b(3, circuits=("U13",), couleur="Noir"),   # hors du circuit U11
        }
        # Il tient le Vert (plein dans U11) ET le Noir (plein, mais hors circuit).
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {2, 3}}, couleurs_requises=2)
        assert c.lignes[0].blocs_reussis == 1, \
            "seul le Vert est plein dans le circuit : deux couleurs ne sont pas atteintes"

    def test_bloc_sans_couleur_ne_fait_pas_planter(self):
        """Une ligne d'import sans couleur ne doit pas casser la page publique."""
        blocs = {1: b(1, couleur=""), 2: b(2, couleur="Vert")}
        calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                        {1: {2}}, couleurs_requises=1)

    def test_deux_couleurs_pleines_validentles_plus_faciles(self):
        """Vert et Bleu entièrement réussis → les Jaunes sont validés."""
        blocs = self._jeu()
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {3, 4, 5}}, couleurs_requises=2)
        assert c.lignes[0].blocs_reussis == 5      # les 2 jaunes en plus

    def test_une_seule_couleur_pleine_ne_suffit_pas(self):
        blocs = self._jeu()
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {5}}, couleurs_requises=2)   # Bleu seul
        assert c.lignes[0].blocs_reussis == 1

    def test_variante_a_une_couleur(self):
        """Le classeur documente plusieurs variantes : le nombre est réglable."""
        blocs = self._jeu()
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {5}}, couleurs_requises=1)
        assert c.lignes[0].blocs_reussis == 5      # Bleu plein valide vert+jaune

    def test_les_blocs_valides_comptent_dans_le_denominateur(self):
        """Un bloc validé par couleur baisse la valeur du bloc pour tout le monde."""
        blocs = self._jeu()
        sans = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2)], blocs,
                               {1: {1}, 2: {3, 4, 5}})
        avec = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2)], blocs,
                               {1: {1}, 2: {3, 4, 5}}, couleurs_requises=2)
        # Sans l'option, le grimpeur 1 est seul sur le bloc 1 : il vaut 1000.
        assert next(l for l in sans.lignes if l.dossard == 1).score == 1000
        # Avec, le grimpeur 2 l'obtient aussi : le bloc ne vaut plus que 500.
        assert next(l for l in avec.lignes if l.dossard == 1).score == 500


class TestAucuneReussite:
    def test_tout_le_monde_a_zero(self):
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2), p(3)], BLOCS, {})
        assert [l.score for l in c.lignes] == [0, 0, 0]
        assert [l.rang for l in c.lignes] == [1, 1, 1]
