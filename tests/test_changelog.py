"""Le changelog doit toujours offrir un endroit où écrire.

Né d'un défaut du 03/09/2026, arrivé **deux fois dans la même soirée**. En
publiant la `v0.18.1`, la section `## [Non publié]` a été renommée en
`## [0.18.1]` sans rien laisser derrière — c'était la pratique du dépôt. Les
deux PR suivantes, écrites dans des sessions parallèles, ont donc ajouté leur
entrée dans la **première section venue**, c'est-à-dire une version **déjà
publiée** :

- la spec 036 § 2 ter (#113) s'est décrite dans `[0.18.1]` ;
- la spec 039 (#109) s'est décrite dans `[0.18.0]`.

Rien n'a protesté. Ni git — les ajouts sont additifs et ne conflictent pas —,
ni la CI, ni `extract_changelog.py`, qui trouvait bien une section pour la
version taguée. Le fichier annonçait simplement deux fonctionnalités dans des
releases qui ne les contiennent pas, et dont le corps publié est **figé** : le
changelog et GitHub racontaient deux histoires différentes.

Le garde-fou est l'inverse de l'ancienne pratique : on **laisse toujours** un
`## [Non publié]`, même vide. Une PR qui cherche où écrire trouve une section
qui lui appartient, en haut du fichier, avant toute version publiée.
"""
import re
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
TITRES = re.compile(r"^## \[([^\]]+)\]", re.M)


def sections() -> list[str]:
    return TITRES.findall(CHANGELOG.read_text(encoding="utf-8"))


def test_une_section_non_publiee_existe_toujours():
    """Sans elle, la prochaine PR écrit dans une version déjà publiée."""
    assert "Non publié" in sections(), (
        "CHANGELOG.md n'a pas de section « ## [Non publié] ». La prochaine PR "
        "ajoutera son entrée dans la première section venue — une version déjà "
        "publiée, dont le corps de release est figé. En publiant une version, "
        "renommer [Non publié] en [X.Y.Z] ET recréer un [Non publié] vide."
    )


def test_elle_est_la_premiere_de_toutes():
    """En haut, sinon elle ne sert pas : on écrit dans ce qu'on voit d'abord."""
    assert sections()[0] == "Non publié", (
        f"la première section est « {sections()[0]} » et non « Non publié » : "
        "une entrée ajoutée en tête du fichier atterrirait dans une version publiée"
    )


def test_chaque_version_a_son_lien_de_bas_de_page():
    """Huit étaient morts avant la 0.16.0, celui de la 0.17.0 jusqu'à la 0.18.0.

    Ils s'oublient à chaque release, parce qu'ils vivent à 2000 lignes de la
    section qu'on vient d'écrire.
    """
    texte = CHANGELOG.read_text(encoding="utf-8")
    manquants = [v for v in sections()
                 if v != "Non publié" and f"\n[{v}]: " not in texte]
    assert not manquants, f"lien de bas de page manquant pour : {manquants}"
