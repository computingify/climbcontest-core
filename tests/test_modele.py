"""Le modèle encaisse ce que le terrain lui envoie.

Chaque test ici correspond à un cas réel qui casse la version actuelle.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from climbcontest.contest import (
    ErreurMetier, enregistrer_reussite, reaffecter_dossard,
)
from climbcontest.extensions import db
from climbcontest.models import Competition, Participant, Success


class TestHomonymes:
    def test_deux_homonymes_coexistent(self, app, competition):
        """Le modèle actuel impose `name UNIQUE` : le second insert échoue et
        fait tomber TOUT l'import (risque R5). Le classeur, lui, prévoit le cas
        avec ses colonnes « Erreur » et « A si doublon autorisé »."""
        db.session.add_all([
            Participant(competition_id=competition.id, nom="Martin", prenom="Lea",
                        club="Les Lezards", categorie="U11 F", dossard=10),
            Participant(competition_id=competition.id, nom="Martin", prenom="Lea",
                        club="La Grimpe", categorie="U11 F", dossard=11),
        ])
        db.session.commit()
        assert Participant.query.filter_by(nom="Martin").count() == 2


class TestParticipantIncomplet:
    def test_sans_club_ni_categorie(self, app, competition):
        """Google Sheets tronque les cellules vides de fin : une ligne à 4
        colonnes au lieu de 6. La version actuelle ignore ce grimpeur **sans
        message** — il n'existe simplement pas le jour J."""
        db.session.add(Participant(competition_id=competition.id,
                                   nom="Sansclub", dossard=20))
        db.session.commit()
        p = Participant.query.filter_by(nom="Sansclub").one()
        assert p.club is None and p.categorie is None

    def test_sans_dossard(self, app, competition):
        """Un inscrit qui n'est pas venu peut céder son dossard : il reste en
        base, sans dossard. C'est ce qui impose que l'identité soit l'id."""
        db.session.add(Participant(competition_id=competition.id, nom="Absent"))
        db.session.commit()
        assert Participant.query.filter_by(nom="Absent").one().dossard is None

    def test_plusieurs_participants_sans_dossard(self, app, competition):
        """La contrainte d'unicité ne doit pas se déclencher sur des NULL."""
        db.session.add_all([
            Participant(competition_id=competition.id, nom="A"),
            Participant(competition_id=competition.id, nom="B"),
        ])
        db.session.commit()
        assert Participant.query.filter(Participant.dossard.is_(None)).count() == 2


class TestUniciteDossard:
    def test_meme_dossard_deux_competitions(self, app, competition):
        """La base est multi-compétition : le dossard 1 existe dans chacune."""
        autre = Competition(nom="Autre edition", active=False)
        db.session.add(autre)
        db.session.commit()
        db.session.add_all([
            Participant(competition_id=competition.id, nom="X", dossard=1),
            Participant(competition_id=autre.id, nom="Y", dossard=1),
        ])
        db.session.commit()
        assert Participant.query.filter_by(dossard=1).count() == 2

    def test_meme_dossard_meme_competition_refuse(self, app, competition):
        db.session.add_all([
            Participant(competition_id=competition.id, nom="X", dossard=5),
            Participant(competition_id=competition.id, nom="Y", dossard=5),
        ])
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


class TestCircuit:
    @pytest.mark.parametrize("categorie,attendu", [
        ("U11 F", "U11"), ("U13 H", "U13"), ("SN F", "SN"),
        ("U17", "U17"), (None, None),
    ])
    def test_derivation(self, app, competition, categorie, attendu):
        p = Participant(competition_id=competition.id, nom="X", categorie=categorie)
        assert p.circuit == attendu


class TestIdempotence:
    def test_deux_appels_une_seule_reussite(self, app, jeu):
        p, b = jeu["participants"][0], jeu["blocs"][0]
        r1, neuve1 = enregistrer_reussite(p, b)
        r2, neuve2 = enregistrer_reussite(p, b)
        assert neuve1 is True and neuve2 is False
        assert r1.id == r2.id
        assert Success.query.count() == 1

    def test_contrainte_en_base(self, app, jeu):
        """La garantie ne repose pas sur une vérification préalable mais sur la
        contrainte : entre un SELECT et un INSERT, deux requêtes concurrentes
        passeraient toutes les deux."""
        p, b = jeu["participants"][0], jeu["blocs"][0]
        db.session.add_all([
            Success(participant_id=p.id, bloc_id=b.id),
            Success(participant_id=p.id, bloc_id=b.id),
        ])
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


class TestReaffectationDossard:
    def test_dossard_vierge_reaffectable(self, app, jeu):
        """Le cas réel : un inscrit ne vient pas, un arrivant prend son dossard."""
        absent = jeu["participants"][2]
        libre = jeu["participants"][1]           # dossard 2, aucune réussite
        reaffecter_dossard(absent, 2)
        assert absent.dossard == 2
        assert libre.dossard is None

    def test_dossard_avec_reussite_refuse(self, app, jeu):
        """Règle tranchée le 28/08 : jamais sur un dossard en cours de
        participation. C'est ce qui évite d'avoir à démêler des réussites."""
        porteur, bloc = jeu["participants"][0], jeu["blocs"][0]   # dossard 1
        enregistrer_reussite(porteur, bloc)
        absent = jeu["participants"][2]
        with pytest.raises(ErreurMetier) as e:
            reaffecter_dossard(absent, 1)
        assert "reussites" in str(e.value).lower()
        assert porteur.dossard == 1               # rien n'a bougé

    def test_incremente_le_catalogue(self, app, jeu):
        avant = jeu["competition"].catalogue_version
        reaffecter_dossard(jeu["participants"][2], 2)
        assert jeu["competition"].catalogue_version > avant


class TestCompetitionActive:
    def test_sans_competition_active(self, app, client):
        """Sans compétition active, on répond 409 avec un message clair plutôt
        que de laisser une erreur obscure remonter."""
        r = client.post("/api/v2/contest/success", json={"bib": "1", "bloc": "ZJ6"})
        assert r.status_code == 409
        assert "competition" in r.get_json()["message"].lower()


class TestSante:
    def test_expose_les_reussites_en_attente(self, client, jeu):
        client.post("/api/v2/contest/success", json={"bib": "1", "bloc": "ZJ6"})
        corps = client.get("/health").get_json()
        assert corps["status"] == "ok"
        assert corps["reussites_en_attente"] == 1
