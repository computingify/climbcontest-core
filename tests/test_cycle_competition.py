"""Le cycle de vie d'une édition — spec 018.

Statut, import à deux modes, effacement, archivage, consultation. Aucun accès
réseau : le classeur est un double qui compte ce qu'on lui demande.

Le fil rouge de ce fichier est **l'ordre des opérations**. Presque tous les
pièges du cycle sont des pièges d'ordre : lire avant d'effacer, vérifier le mot
avant de regarder la case, archiver avant que les données partent. Les tests
qui comptent ici sont ceux qui vérifient qu'une panne au mauvais moment ne
laisse pas la base à moitié détruite.
"""

import json
from datetime import date

import pytest

from climbcontest import comptes, cycle
from climbcontest.extensions import db
from climbcontest.models import (
    Archive, Bloc, Circuit, Competition, EN_COURS, PREPARATION, Participant,
    ReaffectationDossard, Success, TERMINEE, Utilisateur,
)
from climbcontest.sheets import parametrage
from climbcontest.sheets.client import ErreurClasseur

MDP = "un-mot-de-passe-assez-long"


# --- Le double du classeur --------------------------------------------------

class ClasseurDouble:
    """Ce que l'import attend d'un classeur, et rien de plus.

    Il ENREGISTRE ses appels : c'est ce qui permet de prouver qu'un
    remplacement complet ne touche pas au classeur (A11), et qu'un effacement
    ne l'appelle jamais (A19).
    """

    registre = None

    def __init__(self, identifiant, feuilles=None):
        self.identifiant = identifiant
        ClasseurDouble.registre["classeurs"] += 1
        if ClasseurDouble.registre.get("lecture_refusee"):
            self.refuse = True
        else:
            self.refuse = False

    def lire(self, onglet, plage):
        ClasseurDouble.registre["lectures"].append(onglet)
        if self.refuse:
            raise ErreurClasseur("Google ne repond pas (simule)")
        return ClasseurDouble.registre["donnees"][onglet]

    # Toute écriture passe par l'une de ces trois-là. Aucune ne doit être
    # appelée par les gestes de la spec 018.
    def marquer_reussites(self, couples):
        ClasseurDouble.registre["ecritures"] += 1
        return len(couples)

    def vider_matrice(self, onglet="Import"):
        ClasseurDouble.registre["ecritures"] += 1
        return {"plage": "D2:F4", "lignes": 3, "colonnes": 3}

    def essai_ecriture(self, onglet="Import"):
        ClasseurDouble.registre["ecritures"] += 1
        return {"tentee": True, "ecriture": True, "restauree": True}


def _ligne_plan(zone, couleur, circuits, numero_zone, numero_import):
    ligne = [""] * 22
    ligne[0], ligne[2] = zone, couleur
    for i, actif in zip((6, 8, 10), circuits):
        ligne[i] = "1" if actif else ""
    ligne[16], ligne[21] = numero_zone, str(numero_import)
    return ligne


PLAN_ENTETE = [""] * 22
PLAN_ENTETE[6], PLAN_ENTETE[8], PLAN_ENTETE[10] = "U11", "U13", "U15"

DONNEES_TYPE = {
    "Plan": [
        PLAN_ENTETE,
        _ligne_plan("Z", "Jaune", (True, True, False), "J6", 1),
        _ligne_plan("Z", "Vert", (True, False, False), "J7", 2),
    ],
    # Volontairement DIFFERENT du jeu de la fixture : le dossard 1 change de
    # nom, le 2 disparait, le 7 apparait. C'est ce qui rend visible la
    # difference entre « mise a jour » et « remplacement ».
    "Listes": [
        ["Dupont Lea", "1", "Dupont", "Lea", "Les Lezards", "U11 F"],
        ["Nouveau Zoe", "7", "Nouveau", "Zoe", "Les Lezards", "U13 F"],
    ],
}


@pytest.fixture()
def classeur(monkeypatch):
    ClasseurDouble.registre = {"classeurs": 0, "lectures": [], "ecritures": 0,
                               "donnees": {k: list(v) for k, v in DONNEES_TYPE.items()}}
    monkeypatch.setattr(parametrage, "ClasseurGoogle", ClasseurDouble)
    return ClasseurDouble.registre


@pytest.fixture()
def secret(app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    return app


@pytest.fixture()
def admin(client, secret):
    comptes.creer("chef", MDP, [comptes.ADMIN])
    client.post("/admin/connexion", json={"identifiant": "chef", "mot_de_passe": MDP})
    return client


@pytest.fixture()
def organisateur(client, secret):
    comptes.creer("benevole", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion",
                json={"identifiant": "benevole", "mot_de_passe": MDP})
    return client


@pytest.fixture()
def peuple(jeu):
    """Le jeu de base, plus deux réussites et une réaffectation de dossard.

    La réaffectation est là parce que c'est elle qui casse un effacement écrit
    dans le mauvais ordre : elle porte une clé étrangère vers un participant,
    et SQLite applique l'intégrité référentielle.
    """
    from climbcontest.contest import enregistrer_reussite

    enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
    enregistrer_reussite(jeu["participants"][1], jeu["blocs"][2])
    db.session.add(ReaffectationDossard(
        competition_id=jeu["competition"].id, dossard=1,
        ancien_participant_id=jeu["participants"][2].id,
        nouveau_participant_id=jeu["participants"][0].id))
    db.session.commit()
    return jeu


def _preparation(comp):
    """La compétition n'est plus « en cours » : la garde ne se déclenche pas."""
    comp.statut = PREPARATION
    db.session.add(comp)
    db.session.commit()
    return comp


def _compte(comp):
    return (Participant.query.filter_by(competition_id=comp.id).count(),
            Bloc.query.filter_by(competition_id=comp.id).count(),
            Success.query.count())


# --- Le statut (A32, A33, A37, A38) -----------------------------------------

class TestStatut:

    @pytest.mark.parametrize("valeur", [PREPARATION, EN_COURS, TERMINEE])
    def test_les_trois_valeurs_sont_ecrites(self, admin, competition, valeur):
        r = admin.post("/admin/competition/statut", json={"statut": valeur})
        assert r.status_code == 200
        assert r.get_json()["statut"] == valeur
        assert db.session.get(Competition, competition.id).statut == valeur

    @pytest.mark.parametrize("valeur", ["demarree", "", "EN_COURS", None])
    def test_une_valeur_inconnue_est_refusee_sans_rien_changer(
            self, admin, competition, valeur):
        avant = competition.statut
        r = admin.post("/admin/competition/statut", json={"statut": valeur})
        assert r.status_code == 400
        assert db.session.get(Competition, competition.id).statut == avant

    def test_un_corps_absent_donne_400_pas_500(self, admin, competition):
        assert admin.post("/admin/competition/statut").status_code == 400

    def test_la_console_affiche_le_statut_reel(self, admin, competition):
        admin.post("/admin/competition/statut", json={"statut": TERMINEE})
        d = admin.get("/admin/classeur").get_json()
        assert d["competition"]["statut"] == TERMINEE

    def test_un_organisateur_peut_regler_le_statut(self, organisateur, competition):
        """C'est le geste de celui qui ouvre la journee : il ne detruit rien."""
        r = organisateur.post("/admin/competition/statut",
                              json={"statut": PREPARATION})
        assert r.status_code == 200

    def test_sans_session_c_est_401(self, client, secret, competition):
        assert client.post("/admin/competition/statut",
                           json={"statut": PREPARATION}).status_code == 401

    def test_un_scan_ne_change_pas_le_statut(self, app, jeu):
        """A38. Le statut n'est JAMAIS deduit de l'activite (spec 018 § 7).

        Un benevole qui essaie son telephone le jeudi soir armerait sinon le
        garde-fou, et une pause dejeuner le desarmerait.
        """
        from climbcontest.contest import enregistrer_reussite
        comp = _preparation(jeu["competition"])
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        assert db.session.get(Competition, comp.id).statut == PREPARATION


# --- L'import à deux modes (A7→A12) -----------------------------------------

class TestImportModes:

    def test_sans_mode_c_est_une_mise_a_jour(self, admin, classeur, peuple):
        """A7, A12. Le comportement d'avant, et il reste le defaut."""
        r = admin.post("/admin/import/sheet", json={})
        assert r.status_code == 200
        rapport = r.get_json()["rapport"]
        assert rapport["mode"] == "mise_a_jour"
        assert rapport["efface"] is None
        # Le dossard 2 n'est PAS dans le classeur : la mise a jour le garde.
        assert Participant.query.filter_by(dossard=2).first() is not None
        assert Participant.query.filter_by(dossard=7).first() is not None
        assert Success.query.count() == 2

    def test_un_mode_inconnu_est_refuse(self, admin, classeur, peuple):
        r = admin.post("/admin/import/sheet", json={"mode": "ecraser"})
        assert r.status_code == 400
        assert classeur["classeurs"] == 0        # meme pas de connexion tentee

    def test_remplacer_sans_confirmation_ne_touche_a_rien(
            self, admin, classeur, peuple):
        """A8. Et surtout : AUCUN appel reseau avant le refus."""
        avant = _compte(peuple["competition"])
        r = admin.post("/admin/import/sheet", json={"mode": "remplacer"})
        assert r.status_code == 400
        assert _compte(peuple["competition"]) == avant
        assert classeur["classeurs"] == 0

    def test_remplacer_vide_puis_repeuple(self, admin, classeur, peuple):
        """A9. Le dossard 2 disparait, le 7 arrive, les reussites partent."""
        _preparation(peuple["competition"])
        r = admin.post("/admin/import/sheet",
                       json={"mode": "remplacer", "confirmation": "EFFACER"})
        assert r.status_code == 200

        rapport = r.get_json()["rapport"]
        assert rapport["mode"] == "remplacer"
        assert rapport["efface"]["reussites"] == 2

        assert Participant.query.filter_by(dossard=2).first() is None
        assert Participant.query.filter_by(dossard=7).first() is not None
        assert Success.query.count() == 0
        assert ReaffectationDossard.query.count() == 0

    def test_remplacer_lit_le_classeur_avant_d_effacer(
            self, admin, classeur, peuple):
        """A10. LE test qui compte.

        Si la lecture echoue APRES l'effacement, on se retrouve avec une base
        vide et un import qui n'a jamais eu lieu -- sans retour possible. C'est
        exactement ce que `lire_tout()` existe pour empecher.
        """
        _preparation(peuple["competition"])
        classeur["lecture_refusee"] = True
        avant = _compte(peuple["competition"])

        r = admin.post("/admin/import/sheet",
                       json={"mode": "remplacer", "confirmation": "EFFACER"})
        assert r.status_code == 502
        assert "rien n'a ete modifie" in r.get_json()["message"]
        assert _compte(peuple["competition"]) == avant

    def test_remplacer_n_ecrit_jamais_dans_le_classeur(
            self, admin, classeur, peuple):
        """A11. On efface le SERVEUR, jamais la feuille."""
        _preparation(peuple["competition"])
        admin.post("/admin/import/sheet",
                   json={"mode": "remplacer", "confirmation": "EFFACER"})
        assert classeur["ecritures"] == 0

    def test_remplacer_est_refuse_a_un_organisateur(
            self, organisateur, classeur, peuple):
        """A30. Le role suit le MODE : c'est le seul endroit du produit."""
        _preparation(peuple["competition"])
        avant = _compte(peuple["competition"])
        r = organisateur.post("/admin/import/sheet",
                              json={"mode": "remplacer", "confirmation": "EFFACER"})
        assert r.status_code == 403
        assert _compte(peuple["competition"]) == avant
        assert classeur["classeurs"] == 0

    def test_la_mise_a_jour_reste_ouverte_a_un_organisateur(
            self, organisateur, classeur, peuple):
        """A31. C'est le geste du samedi matin, il ne detruit rien."""
        assert organisateur.post("/admin/import/sheet", json={}).status_code == 200

    def test_remplacer_sur_une_competition_en_cours_sans_forcage(
            self, admin, classeur, peuple):
        avant = _compte(peuple["competition"])
        r = admin.post("/admin/import/sheet",
                       json={"mode": "remplacer", "confirmation": "EFFACER"})
        assert r.status_code == 409
        assert _compte(peuple["competition"]) == avant

    def test_remplacer_sur_une_competition_en_cours_avec_forcage(
            self, admin, classeur, peuple):
        r = admin.post("/admin/import/sheet",
                       json={"mode": "remplacer", "confirmation": "EFFACER",
                             "forcer": True})
        assert r.status_code == 200
        assert Success.query.count() == 0


# --- L'effacement (A13→A19, A34, A35) ---------------------------------------

class TestEffacer:

    def test_efface_ce_qui_decrit_l_edition(self, admin, peuple):
        """A13."""
        comp = _preparation(peuple["competition"])
        r = admin.post("/admin/donnees/effacer", json={"confirmation": "EFFACER"})
        assert r.status_code == 200
        assert _compte(comp) == (0, 0, 0)
        assert Circuit.query.filter_by(competition_id=comp.id).count() == 0
        assert ReaffectationDossard.query.count() == 0

    def test_n_efface_ni_les_autres_competitions_ni_les_comptes_ni_les_archives(
            self, admin, peuple):
        """A14. Ce qu'on n'efface pas est aussi important que ce qu'on efface."""
        comp = _preparation(peuple["competition"])

        autre = Competition(nom="Novembre 2025", date=date(2025, 11, 16),
                            statut=TERMINEE, active=False)
        db.session.add(autre)
        db.session.flush()
        db.session.add(Participant(competition_id=autre.id, nom="Ancien",
                                   categorie="U15 H", dossard=42))
        db.session.add(Archive(competition_id=autre.id, nom="Novembre 2025",
                               date=autre.date, participants=1, blocs=0,
                               reussites=0, contenu="{}"))
        db.session.commit()

        admin.post("/admin/donnees/effacer", json={"confirmation": "EFFACER"})

        assert Participant.query.filter_by(competition_id=autre.id).count() == 1
        assert Competition.query.count() == 2
        assert Utilisateur.query.count() == 1
        assert Archive.query.count() == 1
        assert _compte(comp) == (0, 0, 0)

    @pytest.mark.parametrize("corps", [
        {}, {"confirmation": ""}, {"confirmation": "effacer"},
        {"confirmation": "EFFACE"}, {"forcer": True},
    ])
    def test_sans_le_mot_rien_n_est_touche(self, admin, peuple, corps):
        """A15, A35. Le forcage ne remplace PAS la confirmation."""
        comp = _preparation(peuple["competition"])
        avant = _compte(comp)
        r = admin.post("/admin/donnees/effacer", json=corps)
        assert r.status_code == 400
        assert _compte(comp) == avant

    def test_une_competition_en_cours_est_refusee(self, admin, peuple):
        """A16. Et le message dit quoi faire."""
        avant = _compte(peuple["competition"])
        r = admin.post("/admin/donnees/effacer", json={"confirmation": "EFFACER"})
        assert r.status_code == 409
        assert "rchive" in r.get_json()["message"]
        assert _compte(peuple["competition"]) == avant

    def test_le_forcage_passe_outre(self, admin, peuple):
        """A34. Demande d'Adrien (01/09) : « je veux pouvoir le forcer »."""
        r = admin.post("/admin/donnees/effacer",
                       json={"confirmation": "EFFACER", "forcer": True})
        assert r.status_code == 200
        assert _compte(peuple["competition"]) == (0, 0, 0)

    def test_forcer_une_competition_qui_n_est_pas_en_cours_ne_change_rien(
            self, admin, peuple):
        """A34. Forcer une garde qui ne se declenche pas est sans effet."""
        comp = _preparation(peuple["competition"])
        r = admin.post("/admin/donnees/effacer",
                       json={"confirmation": "EFFACER", "forcer": True})
        assert r.status_code == 200
        assert _compte(comp) == (0, 0, 0)

    def test_la_version_du_catalogue_n_a_jamais_servi(self, admin, peuple):
        """A17. Le correctif du 30/08, applique ici mot pour mot.

        Sans lui, les vingt-cinq telephones gardent la liste de l'edition
        precedente et affichent un nom d'an dernier sur un dossard tout neuf.
        """
        comp = _preparation(peuple["competition"])
        plafond = max(c.catalogue_version for c in Competition.query.all())
        admin.post("/admin/donnees/effacer", json={"confirmation": "EFFACER"})
        assert db.session.get(Competition, comp.id).catalogue_version > plafond

    def test_le_classement_relu_juste_apres_est_vide(self, admin, peuple):
        """A18. Sans invalidation, le cache tiendrait jusqu'a 5 s."""
        comp = _preparation(peuple["competition"])
        avant = admin.get("/api/public/classement").get_json()
        assert any(c["lignes"] for c in avant["classements"])

        admin.post("/admin/donnees/effacer", json={"confirmation": "EFFACER"})

        apres = admin.get("/api/public/classement").get_json()
        assert not any(c["lignes"] for c in apres["classements"])

    def test_aucun_appel_au_classeur(self, admin, classeur, peuple):
        """A19. Le classeur Google n'est pas touche, pas meme joint."""
        _preparation(peuple["competition"])
        admin.post("/admin/donnees/effacer", json={"confirmation": "EFFACER"})
        assert classeur["classeurs"] == 0
        assert classeur["ecritures"] == 0

    def test_le_classeur_reste_relie(self, admin, peuple):
        """On efface le plus souvent pour reimporter la MEME feuille."""
        comp = _preparation(peuple["competition"])
        admin.post("/admin/donnees/effacer", json={"confirmation": "EFFACER"})
        assert db.session.get(Competition, comp.id).spreadsheet_id == "fictif"

    def test_un_organisateur_ne_peut_pas_effacer(self, organisateur, peuple):
        """A30."""
        _preparation(peuple["competition"])
        avant = _compte(peuple["competition"])
        r = organisateur.post("/admin/donnees/effacer",
                              json={"confirmation": "EFFACER"})
        assert r.status_code == 403
        assert _compte(peuple["competition"]) == avant


# --- L'archivage (A20→A23, A28, A29) ----------------------------------------

class TestArchiver:

    def test_l_archive_porte_le_classement_complet(self, admin, peuple):
        """A20. Les memes rangs que ce que sert la page de resultats."""
        attendu = admin.get("/api/public/classement").get_json()

        r = admin.post("/admin/archives")
        assert r.status_code == 200

        archive = db.session.get(Archive, r.get_json()["archive"]["id"])
        contenu = json.loads(archive.contenu)
        assert contenu["format"] == 1
        assert contenu["cree_par"] == "chef"

        def rangs(charge):
            return {c["groupe"]: [(l["rang"], l.get("nom"), l["score"])
                                  for l in c["lignes"]]
                    for c in charge["classements"]}

        assert rangs(contenu["classement"]) == rangs(attendu)

    def test_les_compteurs_sont_recopies_et_justes(self, admin, peuple):
        """A20, A23. La liste les lit SANS ouvrir le JSON."""
        admin.post("/admin/archives")
        a = Archive.query.first()
        assert (a.participants, a.blocs, a.reussites) == (3, 3, 2)

    def test_les_donnees_brutes_sont_la(self, admin, peuple):
        """La matiere premiere : sans elle, l'archive est une capture d'ecran."""
        admin.post("/admin/archives")
        donnees = json.loads(Archive.query.first().contenu)["donnees"]
        assert len(donnees["participants"]) == 3
        assert len(donnees["blocs"]) == 3
        assert len(donnees["reussites"]) == 2
        assert sorted(donnees["blocs"][0]["circuits"]) == ["U11", "U13"]

    def test_archiver_clot_sans_rien_effacer(self, admin, peuple):
        """A21."""
        comp = peuple["competition"]
        avant = _compte(comp)
        admin.post("/admin/archives")
        assert db.session.get(Competition, comp.id).statut == TERMINEE
        assert _compte(comp) == avant

    def test_une_competition_sans_reussite_est_archivee_avec_un_avertissement(
            self, admin, jeu):
        """A22. On n'empeche pas, on previent."""
        r = admin.post("/admin/archives")
        assert r.status_code == 200
        assert r.get_json()["avertissements"]

    def test_archiver_deux_fois_donne_deux_lignes(self, admin, peuple):
        admin.post("/admin/archives")
        admin.post("/admin/archives")
        assert Archive.query.count() == 2
        liste = admin.get("/admin/archives").get_json()["archives"]
        assert [a["id"] for a in liste] == sorted(
            (a["id"] for a in liste), reverse=True)

    def test_le_calcul_est_force_pas_repris_du_cache(self, admin, peuple):
        """Archiver un cache vieux de 5 s figerait un classement faux.

        On peuple le cache, on ajoute une reussite, on archive : l'archive doit
        porter la reussite ajoutee.
        """
        from climbcontest.contest import enregistrer_reussite
        admin.get("/api/public/classement")             # le cache est chaud
        enregistrer_reussite(peuple["participants"][0], peuple["blocs"][1])

        admin.post("/admin/archives")
        contenu = json.loads(Archive.query.first().contenu)
        assert contenu["compteurs"]["reussites"] == 3

    def test_un_organisateur_ne_peut_pas_archiver(self, organisateur, peuple):
        """A30."""
        assert organisateur.post("/admin/archives").status_code == 403
        assert Archive.query.count() == 0


class TestConsulterEtSupprimer:

    @pytest.fixture()
    def archivee(self, admin, peuple):
        admin.post("/admin/archives")
        return Archive.query.first()

    def test_la_liste_ne_charge_pas_le_contenu(self, admin, archivee):
        """A23."""
        d = admin.get("/admin/archives").get_json()
        assert len(d["archives"]) == 1
        ligne = d["archives"][0]
        assert "contenu" not in ligne
        assert ligne["participants"] == 3
        assert ligne["lisible"] is True

    def test_le_classement_archive_a_la_forme_du_classement_public(
            self, admin, archivee):
        """A24. La page de resultats consomme les deux sans le savoir."""
        public = admin.get("/api/public/classement").get_json()
        archive = admin.get(
            f"/admin/archives/{archivee.id}/classement").get_json()
        for cle in ("competition", "calcule_le", "reussites", "classements"):
            assert cle in archive
        assert {c["groupe"] for c in archive["classements"]} == \
               {c["groupe"] for c in public["classements"]}

    def test_consulter_ne_touche_ni_la_base_ni_la_competition_active(
            self, admin, archivee, peuple):
        """A25."""
        avant = _compte(peuple["competition"])
        admin.get(f"/admin/archives/{archivee.id}/classement")
        assert _compte(peuple["competition"]) == avant
        actif = admin.get("/api/public/classement").get_json()
        assert actif["competition"]["id"] == peuple["competition"].id

    def test_le_fichier_est_un_json_date(self, admin, archivee):
        """A28."""
        r = admin.get(f"/admin/archives/{archivee.id}/fichier")
        assert r.status_code == 200
        assert "2026-11-15" in r.headers["Content-Disposition"]
        assert r.headers["Content-Disposition"].startswith("attachment")
        assert json.loads(r.data)["format"] == 1

    def test_une_archive_introuvable_donne_404(self, admin, secret):
        assert admin.get("/admin/archives/999/classement").status_code == 404
        assert admin.get("/admin/archives/999/fichier").status_code == 404

    def test_un_format_inconnu_refuse_la_consultation_pas_le_telechargement(
            self, admin, archivee):
        """§ 5. Un changement de format ne rend pas les vieilles archives
        illisibles : il desactive « Revoir », et le dit."""
        archivee.format = 99
        db.session.commit()

        assert admin.get(
            f"/admin/archives/{archivee.id}/classement").status_code == 409
        assert admin.get(f"/admin/archives/{archivee.id}/fichier").status_code == 200
        assert admin.get("/admin/archives").get_json()["archives"][0]["lisible"] is False

    def test_un_organisateur_consulte_et_telecharge(
            self, client, secret, peuple, archivee):
        """A31."""
        client.post("/admin/deconnexion")
        comptes.creer("benevole", MDP, [comptes.ORGANISATEUR])
        client.post("/admin/connexion",
                    json={"identifiant": "benevole", "mot_de_passe": MDP})
        assert client.get("/admin/archives").status_code == 200
        assert client.get(
            f"/admin/archives/{archivee.id}/classement").status_code == 200
        assert client.get(f"/admin/archives/{archivee.id}/fichier").status_code == 200

    def test_sans_session_tout_est_ferme(self, client, secret, archivee):
        """A31."""
        client.post("/admin/deconnexion")
        for chemin in ("/admin/archives",
                       f"/admin/archives/{archivee.id}/classement",
                       f"/admin/archives/{archivee.id}/fichier"):
            assert client.get(chemin).status_code == 401

    def test_supprimer_exige_le_mot(self, admin, archivee):
        """A29."""
        assert admin.delete(f"/admin/archives/{archivee.id}",
                            json={}).status_code == 400
        assert Archive.query.count() == 1

        r = admin.delete(f"/admin/archives/{archivee.id}",
                         json={"confirmation": "EFFACER"})
        assert r.status_code == 200
        assert Archive.query.count() == 0

    def test_un_organisateur_ne_peut_pas_supprimer(
            self, client, secret, peuple, archivee):
        """A29, A30."""
        client.post("/admin/deconnexion")
        comptes.creer("benevole", MDP, [comptes.ORGANISATEUR])
        client.post("/admin/connexion",
                    json={"identifiant": "benevole", "mot_de_passe": MDP})
        r = client.delete(f"/admin/archives/{archivee.id}",
                          json={"confirmation": "EFFACER"})
        assert r.status_code == 403
        assert Archive.query.count() == 1


# --- Le cycle complet — A27 -------------------------------------------------

class TestCycleComplet:
    """Le test qui compte : celui qui vérifie que l'archive tient quand tout
    le reste a disparu."""

    def test_archiver_puis_effacer_laisse_l_archive_intacte(self, admin, peuple):
        comp = peuple["competition"]
        attendu = admin.get("/api/public/classement").get_json()

        admin.post("/admin/archives")
        archive_id = Archive.query.first().id

        r = admin.post("/admin/donnees/effacer",
                       json={"confirmation": "EFFACER", "forcer": True})
        assert r.status_code == 200
        assert _compte(comp) == (0, 0, 0)

        # L'archive survit a la disparition de ce qu'elle decrit. C'est
        # exactement ce que l'absence de cle etrangere garantit.
        assert Archive.query.count() == 1
        fige = admin.get(f"/admin/archives/{archive_id}/classement").get_json()

        def rangs(charge):
            return {c["groupe"]: [(l["rang"], l.get("nom")) for l in c["lignes"]]
                    for c in charge["classements"]}

        assert rangs(fige) == rangs(attendu)
        assert any(c["lignes"] for c in fige["classements"])

        # …et la page publique, elle, montre bien une base vide.
        vivant = admin.get("/api/public/classement").get_json()
        assert not any(c["lignes"] for c in vivant["classements"])

    def test_puis_reimporter_une_autre_edition(self, admin, classeur, peuple):
        """A27. L'archive ne bouge pas quand la base se repeuple."""
        admin.post("/admin/archives")
        empreinte = Archive.query.first().contenu

        admin.post("/admin/import/sheet",
                   json={"mode": "remplacer", "confirmation": "EFFACER",
                         "forcer": True})

        assert Participant.query.filter_by(dossard=7).first() is not None
        assert Archive.query.count() == 1
        assert Archive.query.first().contenu == empreinte


# --- Le module, sans passer par les routes ----------------------------------

class TestModule:

    def test_la_garde_et_la_confirmation_sont_partagees_avec_relier(
            self, app, peuple):
        """A36. Une seule regle, deux portes d'entree.

        `relier(mode=reinitialiser)` et `effacer_donnees()` appellent la MEME
        fonction. Ecrite en double, elle finirait par diverger -- et c'est sur
        l'action la plus destructrice du produit.
        """
        from climbcontest.contest import ErreurMetier

        comp = peuple["competition"]           # elle est « en cours »
        with pytest.raises(ErreurMetier) as refus:
            parametrage.relier(comp, "autre-classeur", mode="reinitialiser",
                               confirmation="EFFACER", classeur=ClasseurDouble("x"))
        assert refus.value.code == 409

    def test_relier_accepte_le_forcage(self, app, classeur, peuple):
        """A36."""
        comp = peuple["competition"]
        effets = parametrage.relier(
            comp, "un-autre-classeur-de-quarante-quatre-caracteres",
            mode="reinitialiser", confirmation="EFFACER", forcer=True,
            classeur=ClasseurDouble("x"))
        assert effets["efface"]["reussites"] == 2
        assert _compte(comp) == (0, 0, 0)

    def test_effacer_ne_valide_pas_la_transaction(self, app, peuple):
        """`effacer_donnees()` ne fait que `flush()` : c'est l'appelant qui
        commit, parce que lui seul sait ce qu'il y a d'autre dans la
        transaction. Un rollback doit donc tout ramener."""
        comp = _preparation(peuple["competition"])
        avant = _compte(comp)

        cycle.effacer_donnees(comp, "EFFACER")
        db.session.rollback()

        assert _compte(comp) == avant


# --- Le nom du fichier téléchargé -------------------------------------------

class TestNomDeFichier:
    """`Content-Disposition` ne doit porter que de l'ASCII.

    Écrit après coup : le code réduisait le nom avec `str.isalnum()`, qui est
    **vrai pour « é »**. Une compétition nommée « Compétition d'été » aurait
    donc produit un en-tête non-ASCII, là où le commentaire promettait le
    contraire. Trouvé en relisant le diff, pas par un test — d'où celui-ci.
    """

    @pytest.mark.parametrize("nom,attendu", [
        ("Test septembre 2026", "test-septembre-2026"),
        ("Compétition d'été 2026", "comp-tition-d-t-2026"),
        ('Guillemets " et \\n saut', "guillemets-et-n-saut"),
        ("///", "archive-sans-nom"),
    ])
    def test_le_nom_est_ascii_et_sans_caractere_dangereux(
            self, admin, peuple, nom, attendu):
        peuple["competition"].nom = nom
        db.session.commit()
        admin.post("/admin/archives")
        archive = Archive.query.first()

        r = admin.get(f"/admin/archives/{archive.id}/fichier")
        entete = r.headers["Content-Disposition"]

        assert entete.isascii()
        # Une seule paire de guillemets : le nom ne peut pas s'en échapper.
        assert entete.count('"') == 2
        assert attendu in entete


# --- Nommer l'edition et regler ce qu'on affiche (spec 020) ------------------

class TestNommerLEdition:
    """Le nom part sur un ECRAN PUBLIC et dans le nom de fichier des archives.

    Aucune route ne le changeait : il restait celui donné à la création, et la
    compétition de production portait le nom de ce qui avait servi à la créer.
    """

    def test_renommer(self, admin, jeu):
        r = admin.post("/admin/competition",
                       json={"nom": "Contest Annonay novembre 2026"})
        assert r.status_code == 200
        assert jeu["competition"].nom == "Contest Annonay novembre 2026"

    def test_le_nom_arrive_sur_la_page_de_resultats(self, admin, jeu):
        admin.post("/admin/competition", json={"nom": "Open de printemps"})
        d = admin.get("/api/public/classement").get_json()
        assert d["competition"]["nom"] == "Open de printemps"

    def test_la_date_aussi(self, admin, jeu):
        admin.post("/admin/competition", json={"date": "2026-11-15"})
        assert jeu["competition"].date == date(2026, 11, 15)

    def test_un_nom_vide_est_refuse(self, admin, jeu):
        avant = jeu["competition"].nom
        r = admin.post("/admin/competition", json={"nom": "   "})
        assert r.status_code == 400
        assert jeu["competition"].nom == avant

    def test_un_nom_trop_long_est_refuse_avant_troncature(self, admin, jeu):
        """SQLite tronquerait en silence, et le nom coupé s'afficherait tel quel
        sur le vidéoprojecteur sans que personne sache pourquoi."""
        avant = jeu["competition"].nom
        r = admin.post("/admin/competition", json={"nom": "x" * 121})
        assert r.status_code == 400
        assert jeu["competition"].nom == avant

    def test_une_date_invalide_n_ecrit_PAS_le_nom_non_plus(self, admin, jeu):
        """Rien n'est écrit si l'un des deux est invalide.

        Un nom accepté et une date refusée dans le même appel laisserait une
        compétition à moitié renommée, sans moyen de savoir laquelle est passée.
        """
        avant = jeu["competition"].nom
        r = admin.post("/admin/competition",
                       json={"nom": "Un nom parfaitement valide",
                             "date": "le 15 novembre"})
        assert r.status_code == 400
        assert jeu["competition"].nom == avant

    def test_un_organisateur_ne_renomme_pas(self, organisateur, jeu):
        assert organisateur.post("/admin/competition",
                                 json={"nom": "X"}).status_code == 403

    def test_l_etat_se_lit_en_organisateur(self, organisateur, jeu):
        r = organisateur.get("/admin/competition")
        assert r.status_code == 200
        d = r.get_json()
        assert d["competition"]["nom"] == jeu["competition"].nom
        assert isinstance(d["groupes"], list)


class TestClassementsAffiches:
    """On range ce qu'on CACHE, jamais ce qu'on montre.

    Une catégorie créée en cours de journée — une inscription à chaud — doit
    s'afficher par défaut. Avec une liste de « ce qu'on montre », elle
    disparaîtrait en silence.
    """

    def test_masquer_un_classement(self, admin, jeu):
        r = admin.post("/admin/competition/affichage",
                       json={"groupes_masques": ["U11 F"]})
        assert r.status_code == 200
        assert cycle.groupes_masques(jeu["competition"]) == ["U11 F"]

    def test_la_charge_publique_les_annonce_ET_sert_tout(self, admin, jeu):
        """Un réglage d'AFFICHAGE, pas un filtre.

        Tous les classements restent servis : c'est ce que `cycle.archiver`
        fige, et démasquer l'après-midi ne doit rien recalculer.
        """
        avant = len(admin.get("/api/public/classement").get_json()["classements"])
        admin.post("/admin/competition/affichage",
                   json={"groupes_masques": ["U11 F"]})
        d = admin.get("/api/public/classement").get_json()
        assert d["competition"]["groupes_masques"] == ["U11 F"]
        assert len(d["classements"]) == avant

    def test_l_ecriture_n_ecrase_pas_les_autres_options(self, admin, jeu):
        """`options` est un seul JSON partagé. Y écrire en remplaçant tout
        ferait disparaître `validation_couleur` — et le classement changerait
        sans que personne n'ait touché au classement."""
        jeu["competition"].options = json.dumps({"validation_couleur": 3})
        db.session.commit()

        admin.post("/admin/competition/affichage",
                   json={"groupes_masques": ["U11 F"]})

        options = cycle.lire_options(jeu["competition"])
        assert options["validation_couleur"] == 3
        assert options["groupes_masques"] == ["U11 F"]

    def test_un_groupe_inconnu_est_accepte_et_range(self, admin, jeu):
        """Il peut réapparaître au prochain import : le silence serait pire."""
        admin.post("/admin/competition/affichage",
                   json={"groupes_masques": ["U19 F"]})
        assert cycle.groupes_masques(jeu["competition"]) == ["U19 F"]

    def test_tout_demasquer(self, admin, jeu):
        admin.post("/admin/competition/affichage", json={"groupes_masques": ["U11 F"]})
        admin.post("/admin/competition/affichage", json={"groupes_masques": []})
        assert cycle.groupes_masques(jeu["competition"]) == []

    def test_les_doublons_et_les_blancs_sont_nettoyes(self, admin, jeu):
        admin.post("/admin/competition/affichage",
                   json={"groupes_masques": ["U11 F", "U11 F", "  ", " U13 H "]})
        assert cycle.groupes_masques(jeu["competition"]) == ["U11 F", "U13 H"]

    def test_ce_qui_n_est_pas_une_liste_est_refuse(self, admin, jeu):
        r = admin.post("/admin/competition/affichage",
                       json={"groupes_masques": "U11 F"})
        assert r.status_code == 400

    def test_un_organisateur_ne_regle_pas_l_affichage(self, organisateur, jeu):
        assert organisateur.post("/admin/competition/affichage",
                                 json={"groupes_masques": []}).status_code == 403

    def test_des_options_abimees_ne_font_pas_tomber_la_page(self, app, jeu):
        jeu["competition"].options = "{pas du json"
        db.session.commit()
        assert cycle.groupes_masques(jeu["competition"]) == []
