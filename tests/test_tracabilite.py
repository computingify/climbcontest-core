"""Qui a envoyé quoi — spec 011.

Le plan de test a été écrit avant l'implémentation
(`specs/011-tracabilite-des-scans/plan.md`). Ce fichier en est la traduction.

Deux règles structurent l'ensemble, et ce sont elles que ces tests protègent :

1. **Une identité mal formée est ignorée, jamais rejetée.** Perdre une réussite
   parce qu'un nom de téléphone contient un caractère inattendu serait le pire
   des échanges — et un juge n'aurait aucun moyen de comprendre le refus.
2. **On trace un appareil, pas une personne.** `saisie_par` continue seul
   d'identifier quelqu'un, et seulement pour une saisie manuelle.
"""
import pytest

from climbcontest import comptes
from climbcontest.contest import enregistrer_reussite, identite_appareil
from climbcontest.models import Success

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def organisateur(client, app, jeu):
    """Un organisateur connecte : c'est lui qui consulte la page de controle."""
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion",
                json={"identifiant": "orga", "mot_de_passe": MDP})
    return client

ROUTE = "/api/v3/successes"

APPAREIL = {"id": "8f3c1d20-aaaa-bbbb-cccc-ddddeeeeffff", "nom": "Mur jaune"}


def envoyer(client, items, appareil=None, **kw):
    corps = {"items": items}
    if appareil is not None:
        corps["appareil"] = appareil
    return client.post(ROUTE, json=corps, **kw)


class TestLecture:
    """`identite_appareil` — la lecture du champ, isolée du reste."""

    def test_une_identite_complete(self):
        assert identite_appareil(APPAREIL) == {
            "id": APPAREIL["id"], "nom": "Mur jaune",
        }

    def test_sans_nom(self):
        assert identite_appareil({"id": "abc"}) == {"id": "abc", "nom": None}

    def test_un_nom_blanc_revient_a_pas_de_nom(self):
        assert identite_appareil({"id": "abc", "nom": "   "})["nom"] is None

    @pytest.mark.parametrize("valeur", [
        None, "", "une chaine", 42, [], ["a"], {"nom": "sans id"}, {"id": ""},
        {"id": "   "}, {"id": 42},
    ])
    def test_tout_ce_qui_n_est_pas_exploitable_donne_None(self, valeur):
        assert identite_appareil(valeur) is None

    def test_un_nom_trop_long_est_coupe(self):
        lu = identite_appareil({"id": "abc", "nom": "x" * 500})
        assert len(lu["nom"]) == 60

    def test_un_identifiant_trop_long_est_coupe(self):
        lu = identite_appareil({"id": "y" * 500})
        assert len(lu["id"]) == 40


class TestEnvoi:

    def test_les_trois_colonnes_sont_renseignees(self, client, jeu):
        envoyer(client, [{"ref": "xyz-42", "bib": "1", "bloc": "ZJ6"}], APPAREIL)

        reussite = Success.query.one()
        assert reussite.appareil_id == APPAREIL["id"]
        assert reussite.appareil_nom == "Mur jaune"
        assert reussite.ref_client == "xyz-42"

    def test_sans_appareil_rien_ne_change(self, client, jeu):
        """Les 25 telephones ne seront pas tous a jour le matin de la competition."""
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])

        assert r.status_code == 200
        reussite = Success.query.one()
        assert reussite.appareil_id is None
        assert reussite.appareil_nom is None
        # La ref, elle, est toujours enregistree : elle vient de `items`.
        assert reussite.ref_client == "a"

    @pytest.mark.parametrize("appareil", [
        "pas un objet", 42, [], {"nom": "sans identifiant"}, {"id": ""},
        {"id": "abc", "nom": {"pas": "une chaine"}},
    ])
    def test_une_identite_mal_formee_n_empeche_jamais_l_enregistrement(
        self, client, jeu, appareil
    ):
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}], appareil)

        assert r.status_code == 200, "la reussite doit passer quoi qu'il arrive"
        assert Success.query.count() == 1

    def test_un_nom_trop_long_ne_fait_pas_echouer_l_envoi(self, client, jeu):
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}],
                    {"id": "abc", "nom": "x" * 500})

        assert r.status_code == 200
        assert len(Success.query.one().appareil_nom) == 60

    def test_le_double_envoi_reste_idempotent(self, client, jeu):
        item = {"ref": "a", "bib": "1", "bloc": "ZJ6"}
        envoyer(client, [item], APPAREIL)
        r = envoyer(client, [item], APPAREIL)

        assert r.get_json()["resultats"][0]["etat"] == "deja_connue"
        assert Success.query.count() == 1

    def test_un_deuxieme_telephone_ne_reecrit_pas_le_premier(self, client, jeu):
        """La reussite garde l'appareil qui l'a REELLEMENT apportee."""
        item = {"ref": "a", "bib": "1", "bloc": "ZJ6"}
        envoyer(client, [item], APPAREIL)
        envoyer(client, [item], {"id": "autre-telephone", "nom": "Mur bleu"})

        assert Success.query.one().appareil_id == APPAREIL["id"]

    def test_renommer_le_telephone_ne_reecrit_pas_l_histoire(self, client, jeu):
        """Le nom est fige a l'envoi : c'est ce qui etait vrai a ce moment-la."""
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}], APPAREIL)
        envoyer(client, [{"ref": "b", "bib": "1", "bloc": "ZJ7"}],
                {"id": APPAREIL["id"], "nom": "Mur vert"})

        noms = {r.ref_client: r.appareil_nom for r in Success.query.all()}
        assert noms == {"a": "Mur jaune", "b": "Mur vert"}

    def test_un_refus_n_enregistre_rien_mais_n_arrete_pas_le_lot(self, client, jeu):
        r = envoyer(client, [
            {"ref": "a", "bib": "1", "bloc": "ZJ6"},
            {"ref": "b", "bib": "99999", "bloc": "ZJ7"},
        ], APPAREIL)

        etats = [x["etat"] for x in r.get_json()["resultats"]]
        assert etats == ["enregistree", "refusee"]
        assert Success.query.one().ref_client == "a"


class TestSaisieManuelle:
    """Une saisie manuelle n'a pas d'appareil, et ne doit pas en inventer un."""

    def test_pas_d_appareil_sur_une_saisie_manuelle(self, client, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0],
                             saisie_par="adrien")

        reussite = Success.query.one()
        assert reussite.saisie_par == "adrien"
        assert reussite.appareil_id is None
        assert reussite.appareil_nom is None
        assert reussite.ref_client is None


class TestRoutesDeControle:
    """Les deux routes de lecture, et la page de contrôle qu'elles servent."""

    def test_la_liste_des_appareils_exige_un_compte(self, client, app, jeu):
        # Sans `SECRET_KEY`, toute la console repond 503 : ce n'est pas ce qu'on
        # veut mesurer ici. On la pose, puis on n'ouvre PAS de session.
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/appareils").status_code == 401

    def test_la_recherche_exige_un_compte(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/reussites-tracees?ref=abc").status_code == 401

    def test_deux_appareils_apparaissent_separement(self, client, jeu, organisateur):
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}], APPAREIL)
        envoyer(client, [{"ref": "b", "bib": "2", "bloc": "DV21"}],
                {"id": "autre", "nom": "Mur bleu"})

        liste = organisateur.get("/admin/appareils").get_json()["appareils"]

        assert {a["id"] for a in liste} == {APPAREIL["id"], "autre"}
        assert {a["reussites"] for a in liste} == {1}

    def test_un_appareil_regroupe_ses_reussites(self, client, jeu, organisateur):
        envoyer(client, [
            {"ref": "a", "bib": "1", "bloc": "ZJ6"},
            {"ref": "b", "bib": "1", "bloc": "ZJ7"},
        ], APPAREIL)

        liste = organisateur.get("/admin/appareils").get_json()["appareils"]

        assert len(liste) == 1
        assert liste[0]["reussites"] == 2

    def test_le_nom_affiche_est_le_dernier_connu(self, client, jeu, organisateur):
        """Un telephone renomme ne doit pas apparaitre deux fois."""
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}], APPAREIL)
        envoyer(client, [{"ref": "b", "bib": "1", "bloc": "ZJ7"}],
                {"id": APPAREIL["id"], "nom": "Mur vert"})

        liste = organisateur.get("/admin/appareils").get_json()["appareils"]

        assert len(liste) == 1, "regroupe par identifiant, pas par nom"
        assert liste[0]["nom"] == "Mur vert"

    def test_une_saisie_manuelle_ne_cree_pas_d_appareil(self, client, jeu, organisateur):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0],
                             saisie_par="adrien")

        assert organisateur.get("/admin/appareils").get_json()["appareils"] == []

    def test_un_appareil_muet_est_signale(self, client, jeu, organisateur):
        """C'est la seule information urgente de la page : un juge bloque."""
        from datetime import datetime, timedelta

        from climbcontest.contest import SILENCE_S, appareils as lire_appareils
        from climbcontest.extensions import db
        from climbcontest.models import Competition

        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}], APPAREIL)
        db.session.commit()

        comp = Competition.query.filter_by(active=True).one()
        recent = lire_appareils(comp)
        assert recent[0]["silencieux"] is False

        plus_tard = datetime.now() + timedelta(seconds=SILENCE_S + 60)
        muet = lire_appareils(comp, maintenant=plus_tard)
        assert muet[0]["silencieux"] is True
        assert muet[0]["silence_s"] >= SILENCE_S

    def test_chercher_une_reference_connue(self, client, jeu, organisateur):
        envoyer(client, [{"ref": "a1b2c3d4-suite", "bib": "1", "bloc": "ZJ6"}],
                APPAREIL)

        r = organisateur.get("/admin/reussites-tracees?ref=a1b2c3").get_json()

        assert r["trouvee"] is True
        ligne = r["reussites"][0]
        assert ligne["ref_client"] == "a1b2c3d4-suite"
        assert ligne["appareil_nom"] == "Mur jaune"
        assert ligne["bloc"] == "ZJ6"
        assert ligne["grimpeur"]

    def test_la_recherche_se_fait_par_prefixe(self, client, jeu, organisateur):
        """L'ecran du juge ne montre que six caracteres : il dictera ceux-la."""
        envoyer(client, [{"ref": "8f3c1d20-aaaa-bbbb", "bib": "1", "bloc": "ZJ6"}],
                APPAREIL)

        r = organisateur.get("/admin/reussites-tracees?ref=8f3c1d").get_json()

        assert r["trouvee"] is True

    def test_une_reference_inconnue_le_dit_clairement(self, client, jeu, organisateur):
        """« Rien trouve » et « je n'ai pas compris » ne doivent pas se ressembler."""
        r = organisateur.get("/admin/reussites-tracees?ref=jamais-vue").get_json()

        assert r["success"] is True
        assert r["trouvee"] is False
        assert r["reussites"] == []

    def test_filtrer_par_appareil(self, client, jeu, organisateur):
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}], APPAREIL)
        envoyer(client, [{"ref": "b", "bib": "2", "bloc": "DV21"}],
                {"id": "autre", "nom": "Mur bleu"})

        r = organisateur.get(
            f"/admin/reussites-tracees?appareil={APPAREIL['id']}"
        ).get_json()

        assert [x["ref_client"] for x in r["reussites"]] == ["a"]

    def test_sans_reference_ni_appareil_on_liste_tout(self, client, jeu, organisateur):
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}], APPAREIL)

        r = organisateur.get("/admin/reussites-tracees").get_json()

        assert len(r["reussites"]) == 1
        assert r["trouvee"] is None, "aucune question posee, aucune reponse oui/non"

    def test_une_limite_absurde_ne_fait_pas_tomber_la_route(self, client, jeu, organisateur):
        for chemin in ("?limite=abc", "?limite=-5", "?limite=999999"):
            r = organisateur.get(f"/admin/reussites-tracees{chemin}")
            assert r.status_code == 200
