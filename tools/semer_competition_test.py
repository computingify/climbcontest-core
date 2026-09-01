"""Sème une compétition de TEST — 8 grimpeurs fictifs, 24 blocs, six couleurs.

Pour répéter le jour J avant le jour J : scanner de vrais QR sur de vrais
téléphones, voir arriver les réussites dans la console, sur la page de
résultats, et dans un classeur JETABLE — sans toucher à une vraie compétition.

Sur la VM (le service peut tourner pendant ce temps, la base est en WAL) :

    sudo -u climbcontest bash -c 'set -a; . /opt/climbcontest/shared/secrets/env; set +a;
      CLIMBCONTEST_DATA_DIR=/opt/climbcontest/shared/data CLIMBCONTEST_SHEETS_ACTIF=0
      /opt/climbcontest/current/.venv/bin/python /opt/climbcontest/current/tools/semer_competition_test.py <id_classeur_jetable>'

En local : python3 tools/semer_competition_test.py <id_classeur_jetable>

La compétition devient l'active ; les autres sont désactivées, jamais
effacées. Relancer le script est sans effet si elle existe déjà.
"""
import sys

from climbcontest import creer_app
from climbcontest.extensions import db
from climbcontest.models import Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant

NOM = "Test septembre 2026"
COULEURS = ["Jaune", "Vert", "Bleu", "Mauve", "Rouge", "Noir"]
# Des zones du VRAI mur d'Annonay (cf. `climbcontest/fiches.py`) : le plan de la
# salle imprimé sur les fiches ne veut rien dire si tout est dans la même.
ZONES = ["Z", "D", "C", "A", "E"]
# La couleur des PRISES, celle qu'on cherche des yeux au pied du bloc. Reprise
# de `Listes!C41:C50` du classeur. Elle n'est ordonnée par rien et n'entre dans
# aucun calcul — voir le commentaire de `Bloc.couleur_prises`.
COULEURS_PRISES = ["Blanc", "Jaune", "Orange", "Rouge", "Rose", "Violet",
                   "Bleu", "Mint", "Vert", "Gris"]
# Des noms VOLONTAIREMENT fictifs, empruntés au vocabulaire de l'escalade :
# le classeur du club contient des noms de mineurs, on n'en recopie aucun.
GRIMPEURS = [("Réglette", "Camille", "U11 F"), ("Bidoigt", "Yanis", "U11 H"),
             ("Dülfer", "Lou", "U13 F"), ("Magnésie", "Noé", "U13 H"),
             ("Verrou", "Sacha", "U15 F"), ("Surplomb", "Andrea", "U15 H"),
             ("Dévers", "Charlie", "U11 F"), ("Arqué", "Morgan", "U11 H")]


def semer(spreadsheet_id: str | None) -> Competition:
    if existante := Competition.query.filter_by(nom=NOM).first():
        print(f"« {NOM} » existe déjà (id {existante.id}) — rien à faire.")
        return existante
    for autre in Competition.query.filter_by(active=True).all():
        autre.active = False
    c = Competition(nom=NOM, statut=EN_COURS, active=True, spreadsheet_id=spreadsheet_id)
    db.session.add(c)
    db.session.commit()

    circuits = {n: Circuit(competition_id=c.id, nom=n) for n in ("U11", "U13", "U15")}
    db.session.add_all(circuits.values())
    db.session.flush()
    for i in range(1, 25):
        couleur = COULEURS[(i - 1) // 4]
        # ⚠️ Cinq zones, et une couleur de PRISES sur chaque bloc.
        #
        # Les 24 blocs étaient tous en zone « Z » et sans couleur de prises. Deux
        # conséquences, et la seconde a fait croire à un bug : la colonne
        # « Prises » de la vue Circuits affichait « — » partout (signalé par
        # Adrien le 01/09), alors que l'import la lit correctement depuis la
        # colonne H du `Plan` depuis la spec 019 — c'est la donnée SEMÉE qui
        # n'existait pas. Et une seule zone rendait le plan de la salle des
        # fiches (spec 023) invérifiable.
        zone = ZONES[(i - 1) % len(ZONES)]
        b = Bloc(competition_id=c.id, tag=f"{zone}{couleur[0]}{i}", numero=i,
                 zone=zone, couleur=couleur,
                 couleur_prises=COULEURS_PRISES[(i - 1) % len(COULEURS_PRISES)])
        db.session.add(b)
        db.session.flush()
        for circuit in circuits.values():
            db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=circuit.id))
    for dossard, (nom, prenom, categorie) in enumerate(GRIMPEURS, start=1):
        db.session.add(Participant(competition_id=c.id, nom=nom, prenom=prenom,
                                   club="Annonay Escalade", categorie=categorie,
                                   dossard=dossard, present=True))
    db.session.commit()
    print(f"« {NOM} » (id {c.id}) est active : {len(GRIMPEURS)} grimpeurs, 24 blocs, "
          f"classeur {spreadsheet_id or 'AUCUN'}.")
    return c


if __name__ == "__main__":
    app = creer_app()
    with app.app_context():
        semer(sys.argv[1] if len(sys.argv) > 1 else None)
