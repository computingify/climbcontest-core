"""Ce que le simulateur retient d'une session à l'autre.

L'adresse du serveur et la clé d'API, pour ne pas les ressaisir à chaque
ouverture — plus les derniers réglages, qui se retrouvent tels quels au
lancement suivant.

⚠️ **CE FICHIER CONTIENT UN SECRET**, et c'est pour ça qu'il vit **hors du
dépôt**, sous `~/.config/climbcontest/`. Le ranger dans le dépôt et compter sur
une ligne de `.gitignore` serait une protection d'un seul caractère : une ligne
supprimée, un `git add -f`, un `.gitignore` réécrit, et la clé part sur un dépôt
**public**. Hors du dépôt, aucune commande git ne peut l'atteindre — il n'y a
plus de geste à ne pas faire.

Le fichier est en `0600` et son dossier en `0700` : sur un Mac partagé, un autre
compte ne le lit pas.

Pour l'oublier : supprimer le fichier. Son chemin est affiché au démarrage.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DOSSIER = Path.home() / ".config" / "climbcontest"
CHEMIN = DOSSIER / "simulateur-juges.json"


def lire() -> dict:
    """Ce qui a été retenu. Un dictionnaire vide si rien, ou si c'est abîmé.

    Ne lève jamais : un fichier illisible doit coûter une ressaisie, pas un
    outil qui refuse de démarrer.
    """
    try:
        donnees = json.loads(CHEMIN.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning("memoire illisible (%s), on repart de zero", e)
        return {}
    return donnees if isinstance(donnees, dict) else {}


def ecrire(**champs) -> None:
    """Met à jour les champs donnés, sans toucher aux autres.

    Écriture par fichier temporaire puis remplacement atomique : une coupure au
    milieu ne laisse pas un JSON tronqué que la prochaine lecture jetterait.
    """
    donnees = lire()
    donnees.update({c: v for c, v in champs.items() if v is not None})
    try:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        os.chmod(DOSSIER, 0o700)
        provisoire = CHEMIN.with_suffix(".json.tmp")
        # Les droits AVANT d'écrire : un fichier créé en 0644 puis resserré a
        # été lisible par tout le monde, le temps d'une fenêtre.
        descripteur = os.open(provisoire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descripteur, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2)
        os.replace(provisoire, CHEMIN)
    except OSError as e:
        # Un disque plein ou un dossier en lecture seule ne doit pas arrêter une
        # simulation en cours : on perd la mémoire, pas la session.
        logger.warning("memoire non enregistree : %s", e)


def oublier() -> None:
    CHEMIN.unlink(missing_ok=True)
