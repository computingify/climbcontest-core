"""La version qui tourne : le tag git, et depuis quand il est pose.

Le fichier `VERSION` est ecrit par la CI au moment de construire la release
(`.github/workflows/release.yml`) et copie a la racine du dossier installe. Il
n'existe donc PAS dans le depot : en developpement, la version vaut « dev », et
c'est la bonne reponse -- pas une valeur par defaut a corriger.

Lu **une seule fois**, au chargement du module. Le contenu ne peut pas changer
sous les pieds d'un processus : une nouvelle release, c'est un nouveau dossier
et un redemarrage du service.

⚠️ Ce module ne connait ni Flask, ni la base. Il est importe par la sonde de
sante, par la console et par la route du catalogue -- trois endroits qui n'ont
rien a se dire. C'est ce qui evite qu'il redevienne, comme avant, une fonction
privee de `routes/sante.py` que les autres ne pouvaient pas atteindre.
"""

from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "VERSION"

# Ce qu'on affiche quand aucun fichier n'a ete pose. Ce n'est pas une erreur :
# c'est l'etat normal d'un poste de developpement.
DEV = "dev"


def _lire() -> str:
    try:
        return FICHIER.read_text(encoding="utf-8").strip() or DEV
    except OSError:
        return DEV


def _posee_le() -> str | None:
    """Quand la release a ete posee sur la machine, en ISO. `None` en dev.

    C'est la date de modification du fichier, c'est-a-dire le moment ou le
    dossier de release a ete ecrit par l'agent de deploiement. Elle repond a
    une question qu'on se pose vraiment un matin de competition : « est-ce que
    la VM a bien tire la derniere version, ou est-ce qu'elle tourne encore sur
    celle d'avant-hier ? »
    """
    try:
        return datetime.fromtimestamp(FICHIER.stat().st_mtime).isoformat(
            timespec="seconds")
    except OSError:
        return None


VERSION = _lire()
POSEE_LE = _posee_le()


def resume() -> dict:
    """Ce que la console et la sonde affichent."""
    return {"version": VERSION, "posee_le": POSEE_LE}
