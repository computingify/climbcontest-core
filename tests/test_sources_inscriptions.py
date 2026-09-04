"""D'où viennent les inscrits — spec 008, demande du 04/09.

« Je voudrais pouvoir paramétrer si on récupère les informations des
participants depuis la fiche Google Sheet ou HelloAsso ou les 2 [...] si
HelloAsso n'est pas sélectionné je ne veux voir aucun paramétrage HelloAsso
dans ma console. Attention si on fait le setting pour se connecter à HelloAsso
puis qu'on le désactive, je veux qu'on conserve les informations de connexion
et settings. »

Le test qui porte tout le fichier est
`test_desactiver_ne_perd_rien` : un réglage qui efface en se désactivant n'est
pas un interrupteur, c'est un piège.
"""

import pytest

from climbcontest import comptes
from climbcontest.contest import ErreurMetier
from climbcontest.cycle import (
    SOURCES_PAR_DEFAUT, ecrire_options, lire_options, regler_sources,
    source_active, sources_inscriptions,
)
from climbcontest.extensions import db
from climbcontest.helloasso import client as ha, planificateur, releve
from climbcontest.helloasso.client import ErreurHelloAsso
from climbcontest.models import (
    Circuit, EN_COURS, Participant, SOURCE_CLASSEUR, SOURCE_HELLOASSO,
)
from climbcontest.sheets.importer import Rapport, importer_participants

MDP = "un-mot-de-passe-assez-long"

CONFIG = {
    "organisation": "annonay-escalade", "form_type": "Event",
    "form_slug": "bloc-party",
    "champs": {"naissance": "Date de naissance", "genre": "Sexe", "club": "Club"},
    "genre_valeurs": {"Femme": "F", "Homme": "H"},
}


@pytest.fixture()
def connecte(client, app, jeu, tmp_path):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    app.config["DOSSIER_SECRETS"] = str(tmp_path)
    comptes.creer("chef", MDP, [comptes.ADMIN])
    client.post("/admin/connexion", json={"identifiant": "chef", "mot_de_passe": MDP})
    return client


class TestLeDefaut:
    def test_le_classeur_seul(self, app, competition):
        """Une édition qui existait avant ce réglage ne change pas de
        comportement le jour où le code arrive."""
        assert sources_inscriptions(competition) == list(SOURCES_PAR_DEFAUT)
        assert sources_inscriptions(competition) == [SOURCE_CLASSEUR]

    def test_une_valeur_abimee_retombe_sur_le_defaut(self, app, competition):
        ecrire_options(competition, sources_inscriptions="pas une liste")
        assert sources_inscriptions(competition) == [SOURCE_CLASSEUR]

    def test_une_source_inconnue_est_ignoree(self, app, competition):
        ecrire_options(competition,
                       sources_inscriptions=["helloasso", "telepathie"])
        assert sources_inscriptions(competition) == [SOURCE_HELLOASSO]


class TestRegler:
    def test_les_deux(self, app, competition):
        assert regler_sources(competition, [SOURCE_CLASSEUR, SOURCE_HELLOASSO]) \
            == [SOURCE_CLASSEUR, SOURCE_HELLOASSO]

    def test_helloasso_seul(self, app, competition):
        regler_sources(competition, [SOURCE_HELLOASSO])
        assert source_active(competition, SOURCE_HELLOASSO)
        assert not source_active(competition, SOURCE_CLASSEUR)

    def test_aucune_source_est_refuse(self, app, competition):
        """Sans source, aucun inscrit ne peut entrer dans l'édition."""
        with pytest.raises(ErreurMetier):
            regler_sources(competition, [])

    def test_une_liste_qui_n_en_est_pas_une(self, app, competition):
        with pytest.raises(ErreurMetier):
            regler_sources(competition, "helloasso")


class TestDesactiverNePerdRien:
    def test_desactiver_ne_perd_rien(self, app, competition, tmp_path):
        """LE test de ce fichier.

        On règle tout, on désactive, on réactive : la clé, le formulaire et la
        correspondance doivent être exactement là où on les avait laissés.
        """
        app.config["DOSSIER_SECRETS"] = str(tmp_path)
        ha.ecrire_secret("un-identifiant", "un-secret", ha.BAC_A_SABLE)
        ecrire_options(competition, helloasso=CONFIG)
        regler_sources(competition, [SOURCE_HELLOASSO])

        regler_sources(competition, [SOURCE_CLASSEUR])          # on desactive

        assert ha.lire_secret() is not None
        assert ha.etat()["configure"] is True
        assert lire_options(competition)["helloasso"] == CONFIG

        regler_sources(competition, [SOURCE_HELLOASSO])          # on reactive

        assert releve.reglages(competition)["form_slug"] == "bloc-party"
        assert releve.reglages(competition)["genre_valeurs"] == {"Femme": "F",
                                                                 "Homme": "H"}

    def test_debrancher_efface_vraiment(self, app, competition, tmp_path):
        """La distinction : « désactiver » masque, « débrancher » efface."""
        app.config["DOSSIER_SECRETS"] = str(tmp_path)
        ha.ecrire_secret("un-identifiant", "un-secret", ha.BAC_A_SABLE)
        ha.effacer_secret()
        assert ha.lire_secret() is None


class TestLaGardeDuReleve:
    def _edition(self, competition):
        for nom in ("U11", "U13", "U15"):
            db.session.add(Circuit(competition_id=competition.id, nom=nom))
        db.session.commit()
        ecrire_options(competition, helloasso=CONFIG)

    def test_le_releve_refuse_si_la_source_est_eteinte(self, app, competition):
        """La garde est dans le métier, pas seulement dans la route : un relevé
        qui passerait par un troisième chemin ferait entrer des inscrits dans
        une édition qui a dit ne pas s'en servir."""
        self._edition(competition)
        regler_sources(competition, [SOURCE_CLASSEUR])
        with pytest.raises(ErreurHelloAsso) as e:
            releve.relever(competition, client=object())
        assert e.value.code == 409
        assert "source" in e.value.message

    def test_le_releve_passe_si_la_source_est_active(self, app, competition):
        self._edition(competition)
        regler_sources(competition, [SOURCE_HELLOASSO])

        class ClientDouble:
            def articles(self, *a, **k):
                return iter([])
        assert releve.relever(competition, client=ClientDouble()).vus == 0


class TestLaGardeDuFil:
    def test_le_fil_ne_releve_pas_une_source_eteinte(self, app, competition,
                                                     monkeypatch):
        """Ce n'est pas une panne, c'est un choix : le fil se tait."""
        regler_sources(competition, [SOURCE_CLASSEUR])
        monkeypatch.setattr(planificateur, "configure", lambda: True)
        monkeypatch.setattr(planificateur, "relever",
                            lambda c: pytest.fail("le releve ne doit pas partir"))
        assert planificateur._un_tour(app) == planificateur.CADENCE_LENTE


class TestLaGardeDeLImport:
    def test_le_classeur_n_importe_pas_les_participants_s_il_n_est_pas_source(
            self, app, competition):
        regler_sources(competition, [SOURCE_HELLOASSO])
        rapport = Rapport()
        importer_participants(competition, None, rapport, [
            ["Dupont Lea", "10", "Dupont", "Lea", "Annonay Escalade", "U13 F"]])
        assert Participant.query.count() == 0
        assert any("pas une source" in a for a in rapport.avertissements)

    def test_l_import_des_blocs_n_est_pas_intercepte(self, app, competition):
        """Le réglage porte sur les PARTICIPANTS, et sur eux seuls.

        Le classeur peut cesser de fournir les inscrits tout en restant la
        **carte du mur** : blocs, circuits, couleurs. Le confondre reviendrait
        à perdre le mur en décochant une case qui ne parle pas de lui.

        La preuve est indirecte mais nette : avec HelloAsso pour seule source,
        `importer_blocs` va jusqu'à sa **propre** validation de structure — donc
        la garde de source n'est pas sur son chemin. Si elle y était, la
        fonction serait sortie sans rien dire.
        """
        from climbcontest.sheets.client import ErreurClasseur
        from climbcontest.sheets.importer import importer_blocs
        regler_sources(competition, [SOURCE_HELLOASSO])
        with pytest.raises(ErreurClasseur) as e:
            importer_blocs(competition, None, Rapport(), [["Zone", "Numero"]])
        assert "circuit" in e.value.args[0].lower()

    def test_le_classeur_importe_quand_il_est_source(self, app, competition):
        regler_sources(competition, [SOURCE_CLASSEUR])
        rapport = Rapport()
        importer_participants(competition, None, rapport, [
            ["Dupont Lea", "10", "Dupont", "Lea", "Annonay Escalade", "U13 F"]])
        assert Participant.query.count() == 1


class TestLaConsoleSuitLeReglage:
    def test_moi_porte_les_sources(self, connecte, jeu):
        d = connecte.get("/admin/moi").get_json()
        assert d["sources_inscriptions"] == [SOURCE_CLASSEUR]

    def test_la_route_regle(self, connecte, jeu):
        r = connecte.post("/admin/competition/sources",
                          json={"sources": ["classeur", "helloasso"]})
        assert r.status_code == 200
        assert connecte.get("/admin/moi").get_json()["sources_inscriptions"] \
            == [SOURCE_CLASSEUR, SOURCE_HELLOASSO]

    def test_aucune_source_est_refusee_par_la_route(self, connecte, jeu):
        r = connecte.post("/admin/competition/sources", json={"sources": []})
        assert r.status_code == 400

    def test_l_etat_de_la_competition_les_rend(self, connecte, jeu):
        assert connecte.get("/admin/competition").get_json()[
            "sources_inscriptions"] == [SOURCE_CLASSEUR]

    def test_reglee_par_un_administrateur_seulement(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
        client.post("/admin/connexion",
                    json={"identifiant": "orga", "mot_de_passe": MDP})
        assert client.post("/admin/competition/sources",
                           json={"sources": ["classeur"]}).status_code == 403
