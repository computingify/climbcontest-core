#!/usr/bin/env python3
"""Simulateur de juges — une compétition entière depuis le Mac.

Vingt-cinq juges qui scannent un dossard, un bloc, et appuient sur « Envoyer »,
au rythme d'une vraie compétition. Pour voir arriver les réussites dans la
console, sur la page de résultats et dans le classeur, sans réunir vingt-cinq
bénévoles et cent grimpeurs.

    python3 tools/simulateur_juges.py

Le panneau s'ouvre sur http://127.0.0.1:8765. Y coller le **lien juge** que
donne la console (onglet « App juge ») suffit : l'adresse et la clé en sont
tirées toutes seules.

    python3 tools/simulateur_juges.py --url https://climbcontest.adn-dev.fr --cle …
    python3 tools/simulateur_juges.py --port 9000 --pas-ouvrir

⚠️ **CE SCRIPT ÉCRIT VRAIMENT.** Les réussites partent sur `/api/v3/successes`,
elles entrent en base et le miroir les recopie dans le classeur relié à la
compétition ACTIVE. Le panneau affiche donc en permanence le nom de cette
compétition, et demande confirmation quand ce n'est pas une compétition de
test. Pour régler la cadence sans rien écrire, la case « À blanc ».

De quoi partir d'une compétition jetable :

    python3 tools/semer_competition_test.py <id_classeur_jetable>   # 8 grimpeurs, 24 blocs
    python3 tools/kit_de_test_qr.py > kit.html                      # les vrais QR à scanner

Ce que le simulateur n'est pas : `tools/charge.py`. Celui-là ne fait que LIRE,
depuis une machine hors du réseau de la salle, pour vérifier qu'aucune adresse
n'est bannie. Les deux se complètent et ne se remplacent pas.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.simulateur.serveur import lancer   # noqa: E402


def main() -> int:
    analyseur = argparse.ArgumentParser(
        description="Simule des juges qui scannent, depuis un panneau local.")
    analyseur.add_argument("--url", default=os.environ.get("CLIMBCONTEST_SIM_URL", ""),
                           help="adresse du backend, ou le lien juge complet")
    analyseur.add_argument("--cle", default=os.environ.get("CLIMBCONTEST_API_KEY", ""),
                           help="clé d'API des juges (jamais écrite sur le disque)")
    analyseur.add_argument("--port", type=int, default=8765)
    analyseur.add_argument("--pas-ouvrir", action="store_true",
                           help="ne pas ouvrir le navigateur")
    args = analyseur.parse_args()

    lancer(port=args.port, ouvrir=not args.pas_ouvrir,
           serveur=args.url, cle=args.cle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
