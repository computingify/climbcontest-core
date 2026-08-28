#!/usr/bin/env python3
"""Peuple la base de développement avec une compétition réaliste.

Reprend la **structure** de l'édition de novembre 2025 — 4 circuits, 8
catégories, des blocs répartis par zone avec leurs couleurs — avec des noms
fictifs. Assez proche du réel pour que les écrans de l'application ressemblent à
ce qu'ils afficheront le jour J, sans manipuler de données personnelles.

Idempotent : relançable sans rien dupliquer.

Les QR codes suivent la vraie convention : lettre de zone + numéro dans la zone
(`ZJ6`, `DV21`…), ce qui permet de tester avec de vraies étiquettes imprimées.
"""

import os
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from climbcontest import creer_app                      # noqa: E402
from climbcontest.extensions import db                  # noqa: E402
from climbcontest.models import (                       # noqa: E402
    Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant, SOURCE_CLASSEUR,
)

CIRCUITS = ["U11", "U13", "U15", "U17"]
GENRES = ["F", "H"]
ZONES = ["Z", "D", "M", "A", "B"]
COULEURS = ["Jaune", "Vert", "Bleu", "Mauve", "Rouge", "Noir"]
CLUBS = ["Les Lezards Vagabonds", "La Grimpe", "Roc N'Potes",
         "Annonay Escalade", "Vertic'Ardeche"]
NOMS = ["Renou", "Lecomte", "Nieuviarts", "Lambert", "Bastide", "Weill",
        "Auffret", "Chabert", "Vernet", "Delorme", "Faure", "Sabatier",
        "Gonnet", "Marchand", "Perrin", "Vialle", "Chomel", "Ruel"]
PRENOMS = ["Lea", "Tom", "Camille", "Martin", "Erine", "Sacha", "Adele",
           "Elsa", "Simon", "Lilian", "Romy", "Theo", "Manon", "Noe",
           "Jade", "Ilan", "Zoe", "Gabin"]


def peupler() -> None:
    alea = random.Random(20251115)          # graine fixe : jeu reproductible

    comp = Competition.query.filter_by(nom="Developpement").first()
    if comp:
        print(f"  competition deja presente : {Participant.query.count()} participants, "
              f"{Bloc.query.count()} blocs")
        return

    comp = Competition(nom="Developpement", date=date(2026, 11, 15),
                       statut=EN_COURS, active=True,
                       spreadsheet_id="classeur-fictif-de-developpement")
    db.session.add(comp)
    db.session.commit()

    circuits = {}
    for nom in CIRCUITS:
        c = Circuit(competition_id=comp.id, nom=nom)
        db.session.add(c)
        circuits[nom] = c
    db.session.flush()

    # 67 blocs, comme en novembre 2025, repartis sur 5 zones.
    numero = 1
    for zone in ZONES:
        for rang in range(1, 15):
            if numero > 67:
                break
            couleur = COULEURS[min(rang // 3, len(COULEURS) - 1)]
            bloc = Bloc(competition_id=comp.id,
                        tag=f"{zone}{couleur[0]}{rang}",   # ex : ZJ6
                        numero=numero, zone=zone, couleur=couleur)
            db.session.add(bloc)
            db.session.flush()
            # Un bloc appartient a un ou deux circuits voisins, comme au reel.
            debut = alea.randrange(len(CIRCUITS))
            for nom in CIRCUITS[debut:debut + alea.choice([1, 2])]:
                db.session.add(BlocCircuit(bloc_id=bloc.id,
                                           circuit_id=circuits[nom].id))
            numero += 1

    # 98 participants, comme en novembre 2025.
    for dossard in range(1, 99):
        circuit = CIRCUITS[dossard % len(CIRCUITS)]
        genre = GENRES[dossard % 2]
        db.session.add(Participant(
            competition_id=comp.id,
            nom=NOMS[dossard % len(NOMS)],
            prenom=PRENOMS[(dossard * 7) % len(PRENOMS)],
            club=CLUBS[dossard % len(CLUBS)],
            categorie=f"{circuit} {genre}",
            dossard=dossard,
            present=True,
            source=SOURCE_CLASSEUR,
        ))

    # Deux cas limites, pour qu'ils soient testables sans les fabriquer :
    #  - un inscrit absent, sans dossard : celui dont on peut reprendre le numero
    db.session.add(Participant(competition_id=comp.id, nom="Absent", prenom="Paul",
                               club=CLUBS[0], categorie="U11 H", dossard=None))
    #  - un homonyme dans un autre club : le cas qui cassait tout l'import
    db.session.add(Participant(competition_id=comp.id, nom=NOMS[1], prenom=PRENOMS[1],
                               club=CLUBS[3], categorie="U13 F", dossard=99))

    db.session.commit()
    print(f"  competition « {comp.nom} » : {Participant.query.count()} participants, "
          f"{Bloc.query.count()} blocs, {Circuit.query.count()} circuits")
    exemples = Bloc.query.order_by(Bloc.numero).limit(4).all()
    print(f"  QR codes de bloc  : {', '.join(b.tag for b in exemples)} …")
    print(f"  QR codes grimpeur : 1, 2, 3 … 98  (dossards)")


if __name__ == "__main__":
    os.environ.setdefault("CLIMBCONTEST_SHEETS_ACTIF", "0")
    app = creer_app()
    with app.app_context():
        peupler()
