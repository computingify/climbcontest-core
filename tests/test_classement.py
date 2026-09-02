"""Le moteur de classement reproduit le classeur, ou il ne sert à rien.

Le test qui décide est `test_reproduit_novembre_2025` : 196 scores et rangs
réels, issus des formules du classeur Google, sur 1003 réussites. Le reste
couvre les cas limites qu'un jeu réel ne contient pas forcément.
"""

import json
from pathlib import Path

import pytest

from climbcontest.cascade import regle_du_classeur
from climbcontest.classement import (
    BlocCalcul, Cascade, ParticipantCalcul, Phrase, calculer_clubs,
    calculer_groupe, calculer_scratch, calculer_tout,
)


def cascade_classeur(seuil=2, eteintes=()):
    """La regle du classeur, telle qu'elle se lisait avant en un entier."""
    return Cascade(phrases=regle_du_classeur(seuil),
                   categories_eteintes=frozenset(eteintes))

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
                            {1: {3, 5}}, cascade=cascade_classeur(2))   # il manque le 4
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
                            {1: {2, 3}}, cascade=cascade_classeur(2))
        assert c.lignes[0].blocs_reussis == 1, \
            "seul le Vert est plein dans le circuit : deux couleurs ne sont pas atteintes"

    def test_bloc_sans_couleur_ne_fait_pas_planter(self):
        """Une ligne d'import sans couleur ne doit pas casser la page publique.

        Et elle doit COMPTER si elle est grimpee : un bloc dont le classeur n'a
        pas rempli la couleur reste un bloc que le grimpeur a fait.
        """
        blocs = {1: b(1, couleur=""), 2: b(2, couleur="Vert")}
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {1, 2}}, cascade=cascade_classeur(1))
        assert c.lignes[0].blocs_reussis == 2
        assert c.lignes[0].blocs_credites == 0

    def test_deux_couleurs_pleines_validentles_plus_faciles(self):
        """Vert et Bleu entièrement réussis → les Jaunes sont validés."""
        blocs = self._jeu()
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {3, 4, 5}}, cascade=cascade_classeur(2))
        assert c.lignes[0].blocs_reussis == 5      # les 2 jaunes en plus

    def test_une_seule_couleur_pleine_ne_suffit_pas(self):
        blocs = self._jeu()
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {5}}, cascade=cascade_classeur(2))   # Bleu seul
        assert c.lignes[0].blocs_reussis == 1

    def test_variante_a_une_couleur(self):
        """Le classeur documente plusieurs variantes : le nombre est réglable."""
        blocs = self._jeu()
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {5}}, cascade=cascade_classeur(1))
        assert c.lignes[0].blocs_reussis == 5      # Bleu plein valide vert+jaune

    def test_les_blocs_valides_comptent_dans_le_denominateur(self):
        """Un bloc validé par couleur baisse la valeur du bloc pour tout le monde."""
        blocs = self._jeu()
        sans = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2)], blocs,
                               {1: {1}, 2: {3, 4, 5}})
        avec = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2)], blocs,
                               {1: {1}, 2: {3, 4, 5}}, cascade=cascade_classeur(2))
        # Sans l'option, le grimpeur 1 est seul sur le bloc 1 : il vaut 1000.
        assert next(l for l in sans.lignes if l.dossard == 1).score == 1000
        # Avec, le grimpeur 2 l'obtient aussi : le bloc ne vaut plus que 500.
        assert next(l for l in avec.lignes if l.dossard == 1).score == 500


class TestAucuneReussite:
    def test_tout_le_monde_a_zero(self):
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1), p(2), p(3)], BLOCS, {})
        assert [l.score for l in c.lignes] == [0, 0, 0]
        assert [l.rang for l in c.lignes] == [1, 1, 1]


class TestScratchsQuiTraversentLesCircuits:
    """Spec 017 — « un scratch où il y a tout le monde, et un scratch homme, un
    autre femme » (Adrien, 31/08).

    La règle ne change pas : chaque grimpeur reste jugé sur les blocs de SON
    circuit, et la valeur d'un bloc reste relative au groupe classé. Ce qui
    change, c'est la taille du groupe.
    """

    def jeu(self):
        """Deux circuits, deux genres, un bloc partagé entre les deux circuits.

        Le bloc partagé n'est pas un détail : 51 des 67 blocs de novembre 2025
        appartiennent à plus d'un circuit. C'est lui qui fait qu'un scratch ne
        rend pas les scores des catégories.
        """
        participants = [
            ParticipantCalcul(id=1, dossard=1, categorie="U11 F"),
            ParticipantCalcul(id=2, dossard=2, categorie="U11 H"),
            ParticipantCalcul(id=3, dossard=3, categorie="U13 F"),
            ParticipantCalcul(id=4, dossard=4, categorie="U13 H"),
        ]
        blocs = {
            1: BlocCalcul(id=1, tag="A1", couleur=None, circuits=frozenset({"U11"})),
            2: BlocCalcul(id=2, tag="A2", couleur=None, circuits=frozenset({"U13"})),
            3: BlocCalcul(id=3, tag="A3", couleur=None, circuits=frozenset({"U11", "U13"})),
        }
        reussites = {1: {1, 3}, 2: {1}, 3: {2, 3}, 4: {2}}
        return participants, blocs, reussites

    def test_les_trois_scratchs_sont_produits(self):
        tous = calculer_tout(*self.jeu())
        scratchs = {g for g, c in tous.items() if c.type == "scratch"}
        assert scratchs == {"Scratch", "Scratch F", "Scratch H"}

    def test_le_scratch_general_contient_tout_le_monde(self):
        tous = calculer_tout(*self.jeu())
        assert {l.participant_id for l in tous["Scratch"].lignes} == {1, 2, 3, 4}

    def test_les_scratchs_genres_ne_melangent_pas(self):
        tous = calculer_tout(*self.jeu())
        assert {l.participant_id for l in tous["Scratch F"].lignes} == {1, 3}
        assert {l.participant_id for l in tous["Scratch H"].lignes} == {2, 4}

    def test_chacun_reste_juge_sur_les_blocs_de_son_circuit(self):
        """Un U11 n'a jamais pu essayer les blocs U13 : ils ne doivent pas
        entrer dans son compte, même quand le groupe les traverse."""
        participants, blocs, reussites = self.jeu()
        reussites[1] = {1, 2, 3}            # une réussite U13 pour une U11
        tous = calculer_tout(participants, blocs, reussites)
        ligne = next(l for l in tous["Scratch"].lignes if l.participant_id == 1)
        assert ligne.blocs_reussis == 2     # le bloc 2 (U13) ne compte pas

    def test_un_bloc_partage_fait_diverger_le_scratch_de_la_categorie(self):
        """La propriété que j'avais annoncée à l'envers, et que la fixture de
        novembre a démentie : avec un bloc partagé, le dénominateur du scratch
        n'est pas celui de la catégorie."""
        tous = calculer_tout(*self.jeu())
        # Bloc 3, partagé U11/U13 : réussi par la fille U11 et la fille U13.
        # En catégorie « U11 F » elle est seule -> le bloc vaut 1000.
        # Au scratch F elles sont deux -> il vaut 500.
        en_categorie = next(l for l in tous["U11 F"].lignes if l.participant_id == 1)
        au_scratch = next(l for l in tous["Scratch F"].lignes if l.participant_id == 1)
        assert en_categorie.score == 2000
        assert au_scratch.score == 1500

    def test_aucun_scratch_avec_un_seul_circuit(self):
        """Il répéterait mot pour mot le classement juste à côté."""
        participants = [ParticipantCalcul(id=1, dossard=1, categorie="U11 F"),
                        ParticipantCalcul(id=2, dossard=2, categorie="U11 H")]
        blocs = {1: BlocCalcul(id=1, tag="A1", couleur=None,
                               circuits=frozenset({"U11"}))}
        tous = calculer_tout(participants, blocs, {1: {1}, 2: {1}})
        assert not [c for c in tous.values() if c.type == "scratch"]

    def test_aucun_scratch_genre_si_un_seul_genre(self):
        participants = [ParticipantCalcul(id=1, dossard=1, categorie="U11 F"),
                        ParticipantCalcul(id=2, dossard=2, categorie="U13 F")]
        blocs = {1: BlocCalcul(id=1, tag="A1", couleur=None, circuits=frozenset({"U11"})),
                 2: BlocCalcul(id=2, tag="A2", couleur=None, circuits=frozenset({"U13"}))}
        tous = calculer_tout(participants, blocs, {1: {1}, 2: {2}})
        scratchs = {g for g, c in tous.items() if c.type == "scratch"}
        assert scratchs == {"Scratch"}

    def test_une_categorie_sans_genre_figure_au_general_pas_aux_genres(self):
        participants = [
            ParticipantCalcul(id=1, dossard=1, categorie="U11 F"),
            ParticipantCalcul(id=2, dossard=2, categorie="U13 H"),
            ParticipantCalcul(id=3, dossard=3, categorie="U11"),   # sans genre
        ]
        blocs = {1: BlocCalcul(id=1, tag="A1", couleur=None, circuits=frozenset({"U11"})),
                 2: BlocCalcul(id=2, tag="A2", couleur=None, circuits=frozenset({"U13"}))}
        tous = calculer_tout(participants, blocs, {1: {1}, 2: {2}, 3: {1}})
        assert 3 in {l.participant_id for l in tous["Scratch"].lignes}
        assert 3 not in {l.participant_id for l in tous["Scratch F"].lignes}
        assert 3 not in {l.participant_id for l in tous["Scratch H"].lignes}

    def test_le_classement_club_ignore_les_scratchs(self):
        """Il additionne les CATÉGORIES : compter aussi les scratchs
        compterait chaque grimpeur trois fois de plus."""
        participants = [
            ParticipantCalcul(id=1, dossard=1, categorie="U11 F", club="Annonay"),
            ParticipantCalcul(id=2, dossard=2, categorie="U13 H", club="Annonay"),
        ]
        blocs = {1: BlocCalcul(id=1, tag="A1", couleur=None, circuits=frozenset({"U11"})),
                 2: BlocCalcul(id=2, tag="A2", couleur=None, circuits=frozenset({"U13"}))}
        tous = calculer_tout(participants, blocs, {1: {1}, 2: {2}})
        club = calculer_clubs(tous, participants)
        attendu = (next(l for l in tous["U11 F"].lignes).score
                   + next(l for l in tous["U13 H"].lignes).score)
        assert club.lignes[0].score == attendu


class TestCascadeParPhrases:
    """Ce que la forme « phrases » apporte, et ce qu'elle ne doit PAS faire."""

    def _six_couleurs(self):
        """Le circuit de la simulation du 02/09 : le seul terrain complet.

        Jaune 7, Vert 10, Bleu 9, Mauve 7, Rouge 2, Noir 1 — 36 blocs.
        """
        blocs, i = {}, 0
        for couleur, combien in (("Jaune", 7), ("Vert", 10), ("Bleu", 9),
                                 ("Mauve", 7), ("Rouge", 2), ("Noir", 1)):
            for _ in range(combien):
                i += 1
                blocs[i] = b(i, couleur=couleur)
        return blocs

    def _ids(self, blocs, couleurs):
        return {i for i, bloc in blocs.items() if bloc.couleur in couleurs}

    @pytest.mark.parametrize("pleines,attendu", [
        (["Rouge", "Noir"], 36),                 # K1 : deux couleurs suffisent
        (["Noir"], 1),                           # K2 : une seule ne fait rien
        (["Noir", "Bleu"], 27),                  # K3 : Jaune et Vert seulement
        (["Mauve", "Rouge", "Noir"], 36),        # K4
    ])
    def test_les_quatre_cas_mesures_dans_le_classeur(self, pleines, attendu):
        """⚠️ Les nombres de BLOCS relevés le 02/09/2026 en activant
        `Listes!D29:D38` dans une copie jetable du classeur. Si ce test tombe,
        le serveur ne compte plus ce que compte le classeur."""
        blocs = self._six_couleurs()
        c = calculer_groupe("U15 F", "categorie", "U11", [p(1)], blocs,
                            {1: self._ids(blocs, pleines)},
                            cascade=cascade_classeur(2))
        assert c.lignes[0].blocs_reussis == attendu

    def test_une_couleur_creditee_n_en_declenche_pas_une_autre(self):
        """**Décision D2**, et c'est le seul test qui la protège.

        « Noir → Rouge » puis « Rouge → Jaune » : avec un enchaînement, le seul
        Noir emporterait tout le circuit. Les déclencheurs se lisent sur les
        blocs RÉELLEMENT grimpés, en une seule passe.
        """
        blocs = self._six_couleurs()
        enchainement = Cascade(phrases=(
            Phrase(parmi=frozenset({"Noir"}), seuil=1, cibles=frozenset({"Rouge"})),
            Phrase(parmi=frozenset({"Rouge"}), seuil=1, cibles=frozenset({"Jaune"})),
        ))
        c = calculer_groupe("U15 F", "categorie", "U11", [p(1)], blocs,
                            {1: self._ids(blocs, ["Noir"])}, cascade=enchainement)
        # 1 Noir grimpe + 2 Rouge credites. Les 7 Jaune ne suivent PAS.
        assert c.lignes[0].blocs_reussis == 3
        assert c.lignes[0].blocs_credites == 2

    def test_deux_phrases_sur_la_meme_cible_s_additionnent(self):
        """Il suffit que l'une tienne — c'est une union, pas une intersection."""
        blocs = self._six_couleurs()
        deux = Cascade(phrases=(
            Phrase(parmi=frozenset({"Rouge"}), seuil=1, cibles=frozenset({"Jaune"})),
            Phrase(parmi=frozenset({"Noir"}), seuil=1, cibles=frozenset({"Jaune"})),
        ))
        c = calculer_groupe("U15 F", "categorie", "U11", [p(1)], blocs,
                            {1: self._ids(blocs, ["Noir"])}, cascade=deux)
        assert c.lignes[0].blocs_reussis == 8      # 1 Noir + 7 Jaune

    def test_une_phrase_dont_les_declencheurs_sont_absents_ne_tient_jamais(self):
        """Un circuit n'a pas à porter les six couleurs — aucun de ceux de
        novembre 2025 n'avait de Noir."""
        blocs = {1: b(1, couleur="Jaune"), 2: b(2, couleur="Vert")}
        sur_le_noir = Cascade(phrases=(
            Phrase(parmi=frozenset({"Noir"}), seuil=1, cibles=frozenset({"Jaune"})),
        ))
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {2}}, cascade=sur_le_noir)
        assert c.lignes[0].blocs_reussis == 1
        assert c.lignes[0].blocs_credites == 0


class TestPorteeParCategorie:
    """La règle est un paramètre du GRIMPEUR, résolu par sa catégorie."""

    def _jeu(self):
        return {1: b(1, couleur="Jaune"), 2: b(2, couleur="Vert")}

    def _cascade(self, eteintes=()):
        return Cascade(
            phrases=(Phrase(parmi=frozenset({"Vert"}), seuil=1,
                            cibles=frozenset({"Jaune"})),),
            categories_eteintes=frozenset(eteintes))

    def test_seule_la_categorie_eteinte_perd_la_cascade(self):
        blocs = self._jeu()
        membres = [p(1, cat="U11 F"), p(2, cat="U11 H")]
        c = calculer_groupe("U11", "circuit", "U11", membres, blocs,
                            {1: {2}, 2: {2}}, cascade=self._cascade(["U11 F"]))
        par_dossard = {l.dossard: l for l in c.lignes}
        assert par_dossard[1].blocs_reussis == 1      # eteinte
        assert par_dossard[2].blocs_reussis == 2      # allumee, le Jaune tombe

    def test_le_scratch_suit_la_regle_de_CHACUN(self):
        """⚠️ Le scratch mélange les catégories. Chaque grimpeur y garde SA
        règle — c'est ce que fait `Inter!DJ19`, calculé ligne par ligne."""
        blocs = self._jeu()
        membres = [p(1, cat="U11 F"), p(2, cat="U11 H")]
        c = calculer_scratch("Scratch", membres, blocs, {1: {2}, 2: {2}},
                             cascade=self._cascade(["U11 F"]))
        par_dossard = {l.dossard: l for l in c.lignes}
        assert par_dossard[1].blocs_reussis == 1
        assert par_dossard[2].blocs_reussis == 2

    def test_une_categorie_inconnue_de_la_liste_est_allumee(self):
        """Une inscription à chaud crée « U15 F » l'après-midi : elle doit
        suivre la règle, pas en être exclue en silence."""
        blocs = self._jeu()
        c = calculer_groupe("U15 F", "categorie", "U11", [p(1, cat="U15 F")],
                            blocs, {1: {2}}, cascade=self._cascade(["U11 F"]))
        assert c.lignes[0].blocs_reussis == 2


class TestCouleurTelleQueLeClasseurLEcrit:
    """⚠️ `sheets/importer.py` ne fait qu'un `strip()` sur la couleur d'un bloc.

    « rouge » et « Rouge » arrivent donc tels quels, et sont deux couleurs pour
    un dictionnaire. Sans rapprochement, la couleur passe pour PLEINE alors
    qu'il reste un bloc à faire, et la cascade se déclenche à tort.
    """

    def test_une_variante_de_casse_ne_rend_pas_la_couleur_pleine(self):
        blocs = {
            1: b(1, couleur="Jaune"),
            2: b(2, couleur="Rouge"),
            3: b(3, couleur="rouge"),      # le meme mur, la meme couleur
        }
        regle = Cascade(phrases=(
            Phrase(parmi=frozenset({"Rouge"}), seuil=1, cibles=frozenset({"Jaune"})),
        ))
        # Le grimpeur n'a fait qu'UN des deux blocs rouges du circuit.
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {2}}, cascade=regle)
        assert c.lignes[0].blocs_reussis == 1, "le Rouge n'est pas plein"

    def test_la_variante_est_credite_comme_les_autres(self):
        blocs = {
            1: b(1, couleur="jaune"),      # minuscule cote mur
            2: b(2, couleur="Rouge"),
        }
        regle = Cascade(phrases=(
            Phrase(parmi=frozenset({"Rouge"}), seuil=1, cibles=frozenset({"Jaune"})),
        ))
        c = calculer_groupe("U11 F", "categorie", "U11", [p(1)], blocs,
                            {1: {2}}, cascade=regle)
        assert c.lignes[0].blocs_reussis == 2
        assert c.lignes[0].blocs_credites == 1


class TestClubsEtCascade:
    def test_le_classement_des_clubs_reporte_les_blocs_credites(self):
        """Sinon la ligne du club affiche « 36 blocs » sans l'astérisque, alors
        qu'une partie n'a été grimpée par personne."""
        blocs = {1: b(1, couleur="Jaune"), 2: b(2, couleur="Vert")}
        regle = Cascade(phrases=(
            Phrase(parmi=frozenset({"Vert"}), seuil=1, cibles=frozenset({"Jaune"})),
        ))
        membres = [ParticipantCalcul(id=1, dossard=1, categorie="U11 F",
                                     club="Les Lezards")]
        par_categorie = {"U11 F": calculer_groupe(
            "U11 F", "categorie", "U11", membres, blocs, {1: {2}}, cascade=regle)}
        clubs = calculer_clubs(par_categorie, membres)
        assert clubs.lignes[0].blocs_reussis == 2
        assert clubs.lignes[0].blocs_credites == 1

