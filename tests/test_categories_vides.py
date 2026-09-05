"""Une catégorie sans inscrit ne paraît pas sur la page de résultats — D8.

Demande d'Adrien du 05/09 : « si certaines catégories n'ont aucun participant
il faut qu'elles soient désactivées de l'affichage de la page résultat, et si
un import ajoute un participant dedans il faut la réactiver automatiquement ».

**C'est déjà le comportement, et par construction** : `classement.calculer_tout`
ne parcourt pas une liste de catégories, il parcourt les **participants** et
range chacun dans son groupe. Aucun interrupteur n'a donc été ajouté.

Ce fichier existe pour une raison précise : **c'est D7 qui pourrait le casser**.
Déclarer neuf catégories d'office, c'est exactement le changement qui ferait
paraître sept classements vides le jour où la charge publique se mettrait à
lire une liste plutôt que des inscrits.

⚠️ À ne pas confondre avec `cycle.groupes_masques` (spec 020) : celui-là masque
une catégorie **qui a des inscrits**, parce qu'un organisateur l'a décidé, et il
doit survivre à un import. Le vide, lui, ne se range nulle part — il se
constate. Mélanger les deux ferait qu'un import « démasquerait » une catégorie
délibérément cachée.
"""

import pytest

from climbcontest import classement_service, comptes, cycle
from climbcontest.extensions import db
from climbcontest.models import Participant

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, jeu):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


def groupes(client):
    return {c["groupe"] for c in
            client.get("/api/public/classement").get_json()["classements"]}


def declarer_tout(connecte):
    from climbcontest import categories
    connecte.post("/admin/categories/declarees",
                  json={"categories": list(categories.LISTE)})


class TestUneCategorieDeclareeMaisVide:
    def test_elle_n_entre_pas_dans_la_charge_publique(self, connecte, jeu):
        """Neuf catégories déclarées, deux portées par des inscrits."""
        declarer_tout(connecte)
        classement_service.invalider()
        vus = groupes(connecte)
        assert "U11 F" in vus and "U13 H" in vus
        for absente in ("U9 F", "U19 H", "U21 F", "Senior F", "Veteran H"):
            assert absente not in vus

    def test_le_bareme_les_voit_pourtant(self, connecte, jeu):
        """La console montre les neuf lignes : ce sont deux vues différentes,
        et c'est voulu. L'écran de réglage annonce, la page publique constate."""
        declarer_tout(connecte)
        tableau = connecte.get("/admin/categories").get_json()["tableau"]
        assert len(tableau) == 9
        assert [l["nom"] for l in tableau if l["inscrits"] == 0]


class TestElleReparaitTouteSeule:
    def test_au_premier_inscrit(self, connecte, jeu):
        """« Si un import ajoute un participant dedans il faut la réactiver
        automatiquement » : aucun geste, aucun réglage à toucher."""
        declarer_tout(connecte)
        classement_service.invalider()
        assert "U15 F" not in groupes(connecte)

        db.session.add(Participant(competition_id=jeu["competition"].id,
                                   nom="Neuve", categorie="U15 F", dossard=90))
        db.session.commit()
        classement_service.invalider()
        assert "U15 F" in groupes(connecte)

    def test_par_la_console_aussi(self, connecte, jeu):
        """Le chemin réel : quelqu'un s'inscrit au guichet.

        ⚠️ Le classement est recalculé au plus une fois toutes les
        `FRAICHEUR_S` secondes (5 s), et l'ajout d'un participant n'invalide
        pas ce cache — mesuré le 05/09. Le groupe paraît donc au prochain
        calcul, pas à la milliseconde. Le test le dit plutôt que de faire
        semblant : ce qui est vérifié ici, c'est qu'**aucun réglage** n'est à
        toucher, pas que l'affichage est instantané.
        """
        assert "U17 H" not in groupes(connecte)
        connecte.post("/admin/participants",
                      json={"nom": "Guichet", "categorie": "U17 H"})
        classement_service.invalider()          # ce que les 5 s feraient
        assert "U17 H" in groupes(connecte)


class TestLeMasquageManuelSurvit:
    """A15 : D8 ne démasque pas ce qu'un humain a caché."""

    def test_un_groupe_masque_le_reste_apres_un_ajout(self, connecte, jeu):
        cycle.regler_affichage(jeu["competition"], ["U11 F"])
        connecte.post("/admin/participants",
                      json={"nom": "Guichet", "categorie": "U11 F"})
        d = connecte.get("/api/public/classement").get_json()
        assert d["competition"]["groupes_masques"] == ["U11 F"]

    def test_le_masquage_ne_retire_pas_le_classement_de_la_charge(self, connecte, jeu):
        """⚠️ C'est un RÉGLAGE D'AFFICHAGE, pas un filtre — l'archive fige
        cette même charge, et une archive amputée serait irréparable."""
        cycle.regler_affichage(jeu["competition"], ["U11 F"])
        classement_service.invalider()
        assert "U11 F" in groupes(connecte)
