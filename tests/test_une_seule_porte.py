"""Aucun chemin n'écrit une catégorie sans passer par le formatage — spec 045.

⚠️ **C'est le seul test de cette spec qui empêche le défaut de revenir une
quatrième fois.** Les autres vérifient que la règle est bonne ; celui-ci
vérifie qu'aucun code ne la contourne.

L'histoire justifie le prix : la spec 013 a mis des listes déroulantes, la 008 a
étendu le formatage à toutes les sources, et « U13 M » est quand même resté en
base — chaque fois parce que la règle était **à côté** du chemin d'écriture, et
qu'il suffisait d'un chemin qui ne l'appelait pas.

Ce test relit le code source. Ce n'est pas élégant, et c'est assumé : une règle
qui ne tient qu'à la vigilance ne tient pas.
"""

import pathlib
import re

RACINE = pathlib.Path(__file__).resolve().parent.parent / "climbcontest"

#: Une affectation de la colonne : `p.categorie = ...`, `participant.categorie = ...`.
#: Les comparaisons (`==`) et les mots-clés (`categorie=`) ne sont pas visés.
_AFFECTATION = re.compile(r"^\s*(\w+)\.categorie\s*=\s*(.+?)\s*$")

#: Ce dont une catégorie a le droit de venir. Toutes ces expressions passent par
#: `formatage.categorie`, directement ou par une fonction qui l'appelle.
_SOURCES_SURES = (
    "formatage.categorie(",
    "propre",                       # `bareme.regler_a_la_main` : deja formate
    'par_identifiant[p.id]["apres"]',   # `bareme.appliquer` : sort du bareme
    "a_faire[p.categorie]",             # `bareme.rattacher_hors_liste` : une cible officielle
)

#: Les fichiers ou l'affectation est le sujet meme, et donc legitime.
_FICHIERS_AUTORISES = {"formatage.py"}


def _lignes_qui_ecrivent():
    for fichier in sorted(RACINE.rglob("*.py")):
        if fichier.name in _FICHIERS_AUTORISES:
            continue
        for n, ligne in enumerate(
                fichier.read_text(encoding="utf-8").splitlines(), start=1):
            trouve = _AFFECTATION.match(ligne)
            if trouve:
                yield fichier.relative_to(RACINE), n, trouve.group(2)


class TestLaPorteEstUnique:
    def test_toute_ecriture_passe_par_le_formatage(self):
        suspectes = [
            f"{fichier}:{n} — categorie = {valeur}"
            for fichier, n, valeur in _lignes_qui_ecrivent()
            if not any(sure in valeur for sure in _SOURCES_SURES)
        ]
        assert not suspectes, (
            "Une categorie s'ecrit sans passer par `formatage.categorie` :\n  "
            + "\n  ".join(suspectes)
            + "\n\nSi c'est volontaire, ajoutez la source a `_SOURCES_SURES` "
              "en expliquant pourquoi elle est deja formatee."
        )

    def test_le_test_verrait_une_ecriture_brute(self):
        """Un test de garde qui ne garde rien passerait au vert pour toujours.

        On lui donne donc une ligne fautive à trouver — sinon une refonte qui
        casserait l'expression régulière rendrait ce fichier silencieux.
        """
        assert _AFFECTATION.match("        p.categorie = corps['categorie']")
        assert not _AFFECTATION.match("        if p.categorie == 'U13 F':")
        assert not _AFFECTATION.match("        Participant(categorie=brut)")

    def test_au_moins_une_ecriture_est_trouvee(self):
        """Et qu'il regarde bien un code qui existe."""
        assert list(_lignes_qui_ecrivent())
