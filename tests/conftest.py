"""Fixtures de test. Base en memoire, aucun acces reseau."""
import os
from datetime import date

import pytest

os.environ["CLIMBCONTEST_TEST"] = "1"

from climbcontest import creer_app                       # noqa: E402
from climbcontest.config import ConfigTest               # noqa: E402
from climbcontest.extensions import db                   # noqa: E402
from climbcontest.models import (                        # noqa: E402
    Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant,
)


@pytest.fixture(autouse=True)
def _cache_propre():
    """Le cache de classement est un global de module : sans ce nettoyage, un
    test verrait le classement calcule par le precedent."""
    from climbcontest import classement_service
    classement_service.invalider()
    yield
    classement_service.invalider()


@pytest.fixture()
def app():
    app = creer_app(ConfigTest)
    with app.app_context():
        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def competition(app):
    c = Competition(nom="Test 2026", date=date(2026, 11, 15),
                    statut=EN_COURS, active=True, spreadsheet_id="fictif")
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture()
def jeu(app, competition):
    """Une compétition minimale : 2 circuits, 3 blocs, 3 participants.

    Volontairement petite et lisible : chaque test doit pouvoir dire de tete ce
    qui est attendu.
    """
    u11 = Circuit(competition_id=competition.id, nom="U11")
    u13 = Circuit(competition_id=competition.id, nom="U13")
    db.session.add_all([u11, u13])
    db.session.flush()

    blocs = []
    for i, (tag, couleur, circuits) in enumerate(
        [("ZJ6", "Jaune", [u11, u13]), ("ZJ7", "Vert", [u11]), ("DV21", "Bleu", [u13])], 1
    ):
        b = Bloc(competition_id=competition.id, tag=tag, numero=i,
                 zone=tag[0], couleur=couleur)
        db.session.add(b)
        db.session.flush()
        for c in circuits:
            db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=c.id))
        blocs.append(b)

    participants = [
        Participant(competition_id=competition.id, nom="Dupont", prenom="Lea",
                    club="Les Lezards", categorie="U11 F", dossard=1, present=True),
        Participant(competition_id=competition.id, nom="Martin", prenom="Tom",
                    club="La Grimpe", categorie="U13 H", dossard=2, present=True),
        # Inscrit qui n'est pas venu : pas de dossard. C'est le cas qui justifie
        # que l'identite soit l'id et non le dossard.
        Participant(competition_id=competition.id, nom="Absent", prenom="Paul",
                    categorie="U11 H", dossard=None),
    ]
    db.session.add_all(participants)
    db.session.commit()
    return {"competition": competition, "blocs": blocs,
            "participants": participants, "circuits": [u11, u13]}
