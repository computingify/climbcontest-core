"""La route de lot — le versant serveur de la spec 003.

Le plan de test de cette spec a été écrit AVANT l'implémentation
(`specs/003-offline-first-judge-app/plan.md`). Ce fichier en est la traduction,
scénario par scénario.

La règle qui structure tout : **un lot n'échoue jamais en bloc**. Si un élément
sur cinq est mauvais, les quatre autres passent. Sinon un seul QR mal imprimé
bloquerait la file d'un juge pour toute la journée.
"""
from datetime import datetime, timedelta

import pytest

from climbcontest.auth import compteurs
from climbcontest.contest import (
    enregistrer_reussite, reussites_suspectes,
)
from climbcontest.extensions import db
from climbcontest.models import Participant, ReaffectationDossard, Success

ROUTE = "/api/v3/successes"


def envoyer(client, items, **kw):
    return client.post(ROUTE, json={"items": items}, **kw)


def etats(reponse):
    return [r["etat"] for r in reponse.get_json()["resultats"]]


class TestLotNominal:

    def test_trois_valides(self, client, jeu):
        r = envoyer(client, [
            {"ref": "a", "bib": "1", "bloc": "ZJ6"},
            {"ref": "b", "bib": "1", "bloc": "ZJ7"},
            {"ref": "c", "bib": "2", "bloc": "DV21"},
        ])
        assert r.status_code == 200
        assert etats(r) == ["enregistree"] * 3
        assert Success.query.count() == 3

    def test_les_ref_reviennent_a_l_identique(self, client, jeu):
        """L'application s'en sert pour savoir quoi retirer de sa file."""
        r = envoyer(client, [{"ref": "xyz-42", "bib": "1", "bloc": "ZJ6"}])
        assert [x["ref"] for x in r.get_json()["resultats"]] == ["xyz-42"]

    def test_un_doublon_d_une_reussite_existante(self, client, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])
        assert etats(r) == ["deja_connue"]
        assert Success.query.count() == 1, "aucune seconde ligne"

    def test_le_meme_couple_deux_fois_dans_le_lot(self, client, jeu):
        """Le juge a appuye deux fois : les deux ref sont acquittees, une ligne."""
        r = envoyer(client, [
            {"ref": "a", "bib": "1", "bloc": "ZJ6"},
            {"ref": "b", "bib": "1", "bloc": "ZJ6"},
        ])
        assert etats(r) == ["enregistree", "deja_connue"]
        assert Success.query.count() == 1

    def test_le_lot_vide_est_accepte(self, client, jeu):
        """Ce n'est pas une erreur : l'application peut envoyer une file vide."""
        r = envoyer(client, [])
        assert r.status_code == 200
        assert r.get_json()["resultats"] == []

    def test_la_version_du_catalogue_voyage_avec_la_reponse(self, client, jeu):
        """Gratuit : l'application apprend son retard sans requete de plus."""
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])
        assert r.get_json()["catalogue_version"] == jeu["competition"].catalogue_version


class TestLotPartiellementMauvais:
    """Le coeur de la spec : un mauvais element n'entraine pas les autres."""

    def test_trois_valides_et_un_dossard_inconnu(self, client, jeu):
        r = envoyer(client, [
            {"ref": "a", "bib": "1", "bloc": "ZJ6"},
            {"ref": "b", "bib": "999", "bloc": "ZJ6"},
            {"ref": "c", "bib": "1", "bloc": "ZJ7"},
            {"ref": "d", "bib": "2", "bloc": "DV21"},
        ])
        assert r.status_code == 200
        assert etats(r) == ["enregistree", "refusee", "enregistree", "enregistree"]
        assert Success.query.count() == 3, "les trois valides doivent etre passes"

    def test_un_bloc_inconnu_est_refuse_avec_un_message(self, client, jeu):
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "PAS_UN_BLOC"}])
        verdict = r.get_json()["resultats"][0]
        assert verdict["etat"] == "refusee"
        assert verdict["message"], "un refus doit dire pourquoi"

    def test_un_participant_sans_dossard_est_refuse_proprement(self, client, jeu):
        """L'inscrit absent : il existe, mais aucun QR ne le designe."""
        r = envoyer(client, [{"ref": "a", "bib": None, "bloc": "ZJ6"}])
        assert r.status_code == 200
        assert etats(r) == ["refusee"]


class TestCorpsMalforme:
    """Un corps inattendu doit donner 400, jamais 500.

    Un 500 est indistinguable d'une vraie panne : l'application le traiterait
    comme « reessaie », et boucherait indefiniment.
    """

    @pytest.mark.parametrize("corps", ['[1,2]', '"x"', '42', 'null', 'true'])
    def test_un_json_qui_n_est_pas_un_objet(self, client, jeu, corps):
        r = client.post(ROUTE, data=corps, content_type="application/json")
        assert r.status_code == 400

    def test_items_absent(self, client, jeu):
        r = client.post(ROUTE, json={"autre": 1})
        assert r.status_code == 400

    def test_items_qui_n_est_pas_une_liste(self, client, jeu):
        assert client.post(ROUTE, json={"items": "abc"}).status_code == 400

    def test_un_element_qui_n_est_pas_un_objet(self, client, jeu):
        r = client.post(ROUTE, json={"items": [{"ref": "a", "bib": "1", "bloc": "ZJ6"}, 42]})
        assert r.status_code == 400

    def test_un_corps_illisible(self, client, jeu):
        r = client.post(ROUTE, data="<xml/>", content_type="application/json")
        assert r.status_code == 400

    def test_un_lot_enorme_est_refuse_clairement(self, client, jeu):
        """500 elements viendraient d'un bogue. On refuse, on ne plante pas.

        Traiter un lot enorme bloquerait un worker sur les quatre pendant la
        competition.
        """
        r = envoyer(client, [{"ref": str(i), "bib": "1", "bloc": "ZJ6"} for i in range(500)])
        assert r.status_code == 413
        assert "maximum" in r.get_json()["message"].lower()
        assert Success.query.count() == 0, "rien ne doit avoir ete ecrit"


class TestCleApi:

    def setup_method(self):
        for k in compteurs:
            compteurs[k] = 0

    def test_sans_cle_le_defaut_refuse(self, client_sans_cle, jeu):
        """Le regime par defaut est STRICT depuis la spec 012.

        Et surtout : rien n'est ecrit. La file du telephone reste intacte, donc
        les reussites repartiront des que la cle sera bonne.
        """
        r = envoyer(client_sans_cle, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])
        assert r.status_code == 401
        assert Success.query.count() == 0

    def test_sans_cle_en_mode_tolere(self, client_sans_cle, jeu, app):
        """La porte de sortie du plan de repli : le gel V3.1.4 n'envoie rien."""
        app.config["API_KEY_STRICTE"] = False
        try:
            r = envoyer(client_sans_cle, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])
            assert r.status_code == 200
            assert compteurs["sans_cle"] == 1, "l'appel doit etre compte"
        finally:
            app.config["API_KEY_STRICTE"] = True

    def test_avec_la_bonne_cle(self, client, jeu):
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])
        assert r.status_code == 200

    def test_avec_une_mauvaise_cle(self, client_sans_cle, jeu):
        r = envoyer(client_sans_cle, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}],
                    headers={"X-Api-Key": "pas-la-bonne"})
        assert r.status_code == 401
        assert Success.query.count() == 0

    def test_un_en_tete_vide_est_une_mauvaise_cle(self, client_sans_cle, jeu):
        """Ce n'est PAS la meme chose qu'une absence d'en-tete."""
        r = envoyer(client_sans_cle, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}],
                    headers={"X-Api-Key": ""})
        assert r.status_code == 401


class TestSansCompetition:
    def test_409_pour_que_l_application_garde_sa_file(self, client, app):
        """400 se lirait comme « ta requete est mauvaise », donc jetable.

        409 dit « pas maintenant » : l'application doit reessayer plus tard, pas
        vider sa file.
        """
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])
        assert r.status_code == 409


class TestHorodatageClient:
    """L'heure du telephone est indicative. Elle ne doit jamais rien casser."""

    def test_une_heure_valide_est_conservee(self, client, jeu):
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                          "at": "2026-11-15T09:41:02Z"}])
        s = Success.query.one()
        assert s.scanne_le is not None
        assert s.scanne_le.year == 2026

    @pytest.mark.parametrize("valeur", ["pas une date", "", 42, None, "2026-13-45"])
    def test_une_heure_absurde_n_empeche_pas_l_enregistrement(self, client, jeu, valeur):
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6", "at": valeur}])
        assert etats(r) == ["enregistree"], "la reussite compte plus que son horodatage"
        assert Success.query.one().scanne_le is None

    def test_l_horodatage_serveur_fait_toujours_foi(self, client, jeu):
        """Une horloge de telephone peut etre fausse de plusieurs heures."""
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                          "at": "2001-01-01T00:00:00Z"}])
        s = Success.query.one()
        assert s.horodatage.year >= 2026, "le serveur pose sa propre heure"


class TestReaffectationEtFileDAttente:
    """Le cas que la file d'attente rend possible, et la decision d'Adrien.

    Un juge scanne le dossard 42 ; la reussite reste quelques secondes dans le
    telephone ; entre-temps le dossard 42 a change de main. La reussite arrive
    et se colle au nouveau porteur.

    Decision du 28/08 : **on autorise**, sans barriere. Ces tests verifient donc
    deux choses distinctes : que ca passe (la decision est respectee), et que ca
    laisse une trace (le cas ne disparait pas en silence).

    ⚠️ Depuis le 05/09, la console ne peut plus reaffecter un dossard :
    `reaffecter_dossard()` a ete supprimee. Ces tests ne verifient donc plus
    l'ECRITURE de la trace -- il n'y a plus personne pour l'ecrire -- mais sa
    LECTURE, qui reste necessaire : les bases de production portent deja des
    lignes posees avant cette date, et une reussite suspecte doit continuer a
    se voir. Le montage pose donc l'etat qu'une reaffectation passee a laisse.
    """

    def _reaffecter(self, jeu, vers_index=2, dossard=1):
        """L'etat laisse par une reaffectation d'avant le 05/09."""
        nouveau = jeu["participants"][vers_index]
        ancien = next((p for p in jeu["participants"]
                       if p.dossard == dossard and p.id != nouveau.id), None)
        if ancien is not None:
            ancien.dossard = None
            db.session.add(ancien)
            db.session.flush()
        nouveau.dossard = dossard
        db.session.add(nouveau)
        db.session.add(ReaffectationDossard(
            competition_id=jeu["competition"].id,
            dossard=dossard,
            ancien_participant_id=ancien.id if ancien is not None else None,
            nouveau_participant_id=nouveau.id,
            effectuee_le=datetime.now(),
        ))
        db.session.commit()

    def test_la_reussite_en_retard_est_acceptee(self, client, jeu):
        scan = datetime.now() - timedelta(seconds=30)
        self._reaffecter(jeu)                       # le dossard 1 change de main

        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                              "at": scan.isoformat()}])

        assert etats(r) == ["enregistree"], "aucune barriere : c'est la decision"

    def test_elle_est_attribuee_au_nouveau_porteur(self, client, jeu):
        scan = datetime.now() - timedelta(seconds=30)
        nouveau = jeu["participants"][2]
        self._reaffecter(jeu)

        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                          "at": scan.isoformat()}])

        assert Success.query.one().participant_id == nouveau.id

    def test_mais_elle_est_signalee(self, client, jeu):
        """La contrepartie : le cas doit etre retrouvable, pas invisible."""
        scan = datetime.now() - timedelta(seconds=30)
        self._reaffecter(jeu)
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                          "at": scan.isoformat()}])

        suspectes = reussites_suspectes(jeu["competition"])

        assert len(suspectes) == 1
        assert suspectes[0]["dossard"] == 1
        assert suspectes[0]["bloc"] == "ZJ6"
        assert "reaffectation" in suspectes[0]["message"].lower()

    def test_une_reussite_normale_n_est_pas_signalee(self, client, jeu):
        """Sinon le signalement serait du bruit, et personne ne le lirait."""
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                          "at": datetime.now().isoformat()}])
        assert reussites_suspectes(jeu["competition"]) == []

    def test_une_reussite_scannee_APRES_la_reaffectation_n_est_pas_signalee(self, client, jeu):
        """Elle concerne bien le nouveau porteur : rien d'anormal."""
        self._reaffecter(jeu)
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                          "at": datetime.now().isoformat()}])
        assert reussites_suspectes(jeu["competition"]) == []

    def test_sans_aucune_reaffectation_rien_n_est_signale(self, client, jeu):
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])
        assert reussites_suspectes(jeu["competition"]) == []

    def test_plus_aucun_dossard_ne_change_de_main(self, client, jeu):
        """La regle du 28/08 -- « jamais un dossard qui porte des reussites » --
        n'a plus rien a garder : depuis le 05/09, aucun dossard ne change de
        main. Ce test garde la porte fermee."""
        from climbcontest import contest
        assert not hasattr(contest, "reaffecter_dossard")


class TestHorsCircuit:
    """Le juge a forcé un bloc hors du circuit du grimpeur (spec 019).

    Le serveur ne refuse RIEN : il enregistre et il trace. Refuser casserait
    l'idempotence et laisserait une file bloquée sur un téléphone, pour une
    réussite que le classement ignore déjà.
    """

    def test_le_forcage_est_trace(self, client, jeu):
        # Dupont (dossard 1) est « U11 F » ; DV21 n'est que dans U13.
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "DV21",
                              "hors_circuit": True}])
        assert etats(r) == ["enregistree"]
        assert Success.query.one().hors_circuit_force is True

    def test_un_scan_verifie_et_bon_se_distingue_d_un_non_verifie(self, client, jeu):
        """`False` et `NULL` ne disent pas la même chose.

        `False` = le téléphone a vérifié et c'était bon. `NULL` = personne n'a
        vérifié. Les confondre ferait dire à la console que tout a été contrôlé
        alors que rien ne l'a été.
        """
        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                          "hors_circuit": False}])
        envoyer(client, [{"ref": "b", "bib": "1", "bloc": "ZJ7"}])
        par_ref = {s.ref_client: s.hors_circuit_force for s in Success.query.all()}
        assert par_ref["a"] is False
        assert par_ref["b"] is None

    def test_une_application_qui_n_envoie_pas_le_champ_marche_comme_avant(
            self, client, jeu):
        r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6"}])
        assert etats(r) == ["enregistree"]
        assert Success.query.one().hors_circuit_force is None

    def test_une_valeur_mal_formee_est_ignoree_jamais_rejetee(self, client, jeu):
        """Perdre une réussite pour un champ facultatif bizarre serait le pire
        des échanges — et un juge n'a aucun moyen de comprendre le refus."""
        for valeur in ["oui", 1, {}, None, []]:
            Success.query.delete()
            db.session.commit()
            r = envoyer(client, [{"ref": "a", "bib": "1", "bloc": "ZJ6",
                                  "hors_circuit": valeur}])
            assert etats(r) == ["enregistree"], valeur
            assert Success.query.one().hors_circuit_force is None, valeur

    def test_le_statut_courant_est_calcule_pas_stocke(self, client, jeu):
        """Corriger le classeur doit faire DISPARAÎTRE l'anomalie.

        `hors_circuit_force` garde ce que le juge a vu ; `hors_circuit` dit ce
        qui est vrai maintenant. Les deux divergent dès qu'on rattache le bloc
        au bon circuit — et c'est exactement ce qu'on veut voir.
        """
        from climbcontest.contest import reussites_tracees
        from climbcontest.models import BlocCircuit

        envoyer(client, [{"ref": "a", "bib": "1", "bloc": "DV21",
                          "hors_circuit": True}])
        ligne = reussites_tracees(jeu["competition"], ref="a")[0]
        assert ligne["hors_circuit_force"] is True
        assert ligne["hors_circuit"] is True

        # Le classeur est corrigé : DV21 entre dans U11.
        dv21 = next(b for b in jeu["blocs"] if b.tag == "DV21")
        u11 = next(c for c in jeu["circuits"] if c.nom == "U11")
        db.session.add(BlocCircuit(bloc_id=dv21.id, circuit_id=u11.id))
        db.session.commit()

        ligne = reussites_tracees(jeu["competition"], ref="a")[0]
        assert ligne["hors_circuit"] is False        # l'anomalie a disparu
        assert ligne["hors_circuit_force"] is True   # le geste, lui, reste

    def test_un_participant_sans_categorie_ne_tranche_rien(self, client, jeu):
        from climbcontest.contest import reussites_tracees
        sans = Participant(competition_id=jeu["competition"].id, nom="Sans",
                           categorie=None, dossard=77)
        db.session.add(sans)
        db.session.commit()
        envoyer(client, [{"ref": "z", "bib": "77", "bloc": "ZJ6"}])
        assert reussites_tracees(jeu["competition"], ref="z")[0]["hors_circuit"] is None
