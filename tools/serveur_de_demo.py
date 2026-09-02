"""Un serveur de démonstration, avec une compétition jouable. Spec 026.

    python3 tools/serveur_de_demo.py [port]

Sert la page de résultats sur une base **temporaire**, remplie d'un jeu qui
ressemble à une vraie compétition : un circuit complet, des réussites, une zone
terminée et une autre à peine entamée. C'est ce qui permet de regarder la fiche
du grimpeur dans un navigateur sans toucher à la base d'une compétition.

⚠️ Ne se connecte à AUCUN classeur et n'écrit dans aucune base existante : la
base est un fichier jeté à l'arrêt.
"""
import os
import sys
import tempfile
from datetime import date

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

# ⚠️ `CLIMBCONTEST_DATA_DIR`, et POSEE AVANT D'IMPORTER `config` : elle est lue
# a l'import du module, pas a la creation de l'application. Une variable posee
# trop tard laisse l'outil ecrire dans la base de developpement.
DOSSIER = tempfile.mkdtemp(prefix="climbcontest-demo-")
BASE = os.path.join(DOSSIER, "climbcontest.db")
os.environ["CLIMBCONTEST_TEST"] = "1"
os.environ["CLIMBCONTEST_DATA_DIR"] = DOSSIER
os.environ["CLIMBCONTEST_SHEETS_ACTIF"] = "0"

from climbcontest import creer_app                                  # noqa: E402
from climbcontest.config import Config                              # noqa: E402
from climbcontest.extensions import db                              # noqa: E402
from climbcontest.fiches import PLAN                                # noqa: E402
from climbcontest.models import (                                   # noqa: E402
    Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant, Success,
)

# Un circuit qui ressemble au vrai : des blocs répartis sur cinq zones du plan,
# dans les six couleurs. Les tags suivent la convention « zone + couleur + n° ».
CIRCUIT = [
    ("Z", "Jaune", 1), ("Z", "Jaune", 2), ("Z", "Vert", 4), ("Z", "Bleu", 7),
    ("Z", "Rouge", 13),
    ("D", "Vert", 3), ("D", "Vert", 4), ("D", "Bleu", 7), ("D", "Bleu", 8),
    ("D", "Rouge", 12), ("D", "Rouge", 14),
    ("M", "Vert", 5), ("M", "Mauve", 10), ("M", "Mauve", 11), ("M", "Rouge", 14),
    ("A", "Jaune", 1), ("A", "Jaune", 2), ("A", "Vert", 3), ("A", "Mauve", 9),
    ("A", "Mauve", 10), ("A", "Rouge", 12), ("A", "Rouge", 13),
    ("B", "Jaune", 2), ("B", "Bleu", 6),
]
LETTRE = {"Jaune": "J", "Vert": "V", "Bleu": "B", "Mauve": "M",
          "Rouge": "R", "Noir": "N"}

# La zone Z est TERMINÉE, la zone B aussi : sans au moins deux zones finies, le
# contour vert ne se voit jamais — celle qu'on regarde porte déjà l'anneau.
REUSSIS = {"ZJ1", "ZJ2", "ZV4", "ZB7", "ZR13", "BJ2", "BB6",
           "DV3", "DV4", "DB7", "MV5", "AJ1", "AJ2", "AV3"}

NOMS = [("Bernard", "Camille"), ("Roux", "Anais"), ("Martin", "Lea"),
        ("Garnier", "Zoe"), ("Faure", "Manon"), ("Perrin", "Jade"),
        ("Morel", "Sarah"), ("Leroy", "Eva")]


def semer(app):
    with app.app_context():
        db.create_all()
        comp = Competition(nom="Contest de demonstration", date=date.today(),
                           statut=EN_COURS, active=True)
        db.session.add(comp)
        db.session.flush()

        circuit = Circuit(competition_id=comp.id, nom="U13")
        db.session.add(circuit)
        db.session.flush()

        blocs = {}
        for i, (zone, couleur, numero) in enumerate(CIRCUIT, 1):
            tag = f"{zone}{LETTRE[couleur]}{numero}"
            b = Bloc(competition_id=comp.id, tag=tag, numero=i, zone=zone,
                     couleur=couleur, couleur_prises=None)
            db.session.add(b)
            db.session.flush()
            db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=circuit.id))
            blocs[tag] = b

        grimpeurs = []
        for i, (nom, prenom) in enumerate(NOMS, 1):
            p = Participant(competition_id=comp.id, nom=nom, prenom=prenom,
                            club="Les Lezards" if i % 2 else "Annonay Escalade",
                            categorie="U13 F", dossard=40 + i, present=True)
            db.session.add(p)
            grimpeurs.append(p)
        db.session.flush()

        # Le troisième — dossard 43 — porte le jeu complet : c'est celui qu'on
        # regarde. Les autres n'ont que de quoi faire un classement crédible.
        for tag in REUSSIS:
            db.session.add(Success(participant_id=grimpeurs[2].id,
                                   bloc_id=blocs[tag].id))
        for rang, p in enumerate(grimpeurs):
            if rang == 2:
                continue
            for tag in list(REUSSIS)[: max(1, 12 - rang)]:
                db.session.add(Success(participant_id=p.id, bloc_id=blocs[tag].id))

        db.session.commit()
        print(f"base   : {BASE}")
        print(f"zones du plan : {len(PLAN['murs'])} murs")
        print(f"a regarder    : dossard {grimpeurs[2].dossard}, "
              f"id {grimpeurs[2].id} -> /#g={grimpeurs[2].id}")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5100
    app = creer_app(Config)
    semer(app)
    print(f"page   : http://127.0.0.1:{port}/")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
