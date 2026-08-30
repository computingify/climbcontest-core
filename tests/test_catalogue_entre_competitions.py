"""Le catalogue d'une compétition ne doit JAMAIS être servi pour une autre.

Trouvé le 30/08 en préparant les tests d'Adrien, et c'est un scénario
**certain** : on répète le jour J sur une compétition de test, puis on crée
celle de novembre. Les téléphones qui ont servi à la répétition gardaient la
liste de test.

Le mécanisme : les téléphones valident leur catalogue avec un simple entier
(`If-None-Match: "3"`), et `catalogue_version` repartait à 1 à chaque
compétition. Deux compétitions portaient donc le même numéro, et le serveur
répondait 304 — « tu es à jour » — sur une liste qui n'était pas la sienne.

La conséquence n'est pas une corruption de données : le serveur enregistre bien
la réussite sur la bonne compétition. C'est **le contrôle humain** qui saute —
le juge lit le nom affiché pour vérifier qu'il a le bon grimpeur, et il lisait
le nom d'un grimpeur de test.
"""
import pytest

from climbcontest import contest
from climbcontest.extensions import db
from climbcontest.models import EN_COURS, Competition, prochaine_version_catalogue


def _competition(nom, participants):
    for autre in Competition.query.filter_by(active=True).all():
        autre.active = False
    c = Competition(nom=nom, statut=EN_COURS, active=True)
    db.session.add(c)
    db.session.commit()
    for dossard, (nom_p, prenom) in enumerate(participants, start=1):
        contest.ajouter_participant(nom=nom_p, prenom=prenom,
                                    categorie="U11 F", dossard=dossard)
    db.session.refresh(c)
    return c


class TestNumerosJamaisReutilises:

    def test_deux_competitions_n_ont_jamais_le_meme_numero(self, app, jeu):
        a = _competition("Répétition", [("Réglette", "Test"), ("Bidoigt", "Test")])
        b = _competition("Novembre", [("Dupont", "Vrai"), ("Martin", "Vrai")])
        assert a.catalogue_version != b.catalogue_version, (
            "deux compétitions portent le même numéro de catalogue : un "
            "téléphone passera de l'une à l'autre sans s'en apercevoir"
        )
        assert b.catalogue_version > a.catalogue_version

    def test_le_numero_ne_repart_pas_a_un(self, app, jeu):
        _competition("Répétition", [("Réglette", "Test")])
        b = _competition("Novembre", [("Dupont", "Vrai")])
        assert b.catalogue_version > 1

    def test_la_toute_premiere_competition_part_bien_de_un(self, app):
        # Base vierge : rien à éviter, on ne complique pas pour rien.
        assert prochaine_version_catalogue() == 1


class TestPasDe304EntreCompetitions:

    def test_un_telephone_de_la_repetition_recoit_la_vraie_liste(
            self, client, app, jeu):
        """Le test qui ferme le trou, joué comme le jour J."""
        a = _competition("Répétition", [("Réglette", "Test"), ("Bidoigt", "Test")])
        version_repetition = a.catalogue_version

        b = _competition("Novembre", [("Dupont", "Vrai"), ("Martin", "Vrai")])

        # Le téléphone annonce ce qu'il a : la version de la répétition.
        r = client.get("/api/v2/catalog",
                       headers={"If-None-Match": f'"{version_repetition}"'})
        assert r.status_code == 200, (
            "304 : le téléphone garde la liste de la répétition, et affichera "
            "un nom de test pour un dossard bien réel"
        )
        noms = {p["nom"] for p in r.get_json()["participants"]}
        assert noms == {"Dupont Vrai", "Martin Vrai"}
        assert r.get_json()["version"] == b.catalogue_version

    def test_un_numero_plus_grand_que_la_version_courante_n_est_pas_a_jour(
            self, client, app, jeu):
        """`?depuis=` répondait 304 dès que le numéro était supérieur ou égal.

        Un numéro plus grand ne veut pas dire « à jour » : il vient d'ailleurs —
        d'une autre compétition, ou d'une base restaurée depuis une sauvegarde.
        """
        c = Competition.query.filter_by(active=True).first()
        assert client.get(
            f"/api/v2/catalog?depuis={c.catalogue_version + 5}"
        ).status_code == 200

    def test_le_304_marche_toujours_dans_le_cas_normal(self, client, app, jeu):
        """La correction ne doit pas coûter les 15 ko économisés à chaque sondage."""
        c = Competition.query.filter_by(active=True).first()
        v = c.catalogue_version
        assert client.get(f"/api/v2/catalog?depuis={v}").status_code == 304
        assert client.get("/api/v2/catalog",
                          headers={"If-None-Match": f'"{v}"'}).status_code == 304
