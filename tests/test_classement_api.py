"""Le classement servi par l'API, et son cache.

Le cache n'est pas un détail : le jour d'une compétition, ~60 spectateurs
rafraîchissent toutes les 15 s. Sans lui, chaque rafraîchissement relancerait le
calcul complet.
"""

import json

import pytest

from climbcontest import cascade as cascade_module
from climbcontest import classement_service
from climbcontest.contest import enregistrer_reussite
from climbcontest.extensions import db


class _Horloge:
    """Le temps que voit le cache, et que le test fait avancer lui-meme.

    ⚠️ **Pourquoi une horloge fausse plutot qu'un `sleep` plus long.** Ces
    tests raccourcissaient `FRAICHEUR_S` a 0,05 s puis dormaient 0,08 s. Le
    piege n'est pas le sommeil : c'est l'assertion d'AVANT, « pendant la
    fraicheur, l'ancien resultat tient ». Elle exige que tout ce qui la precede
    -- une ecriture en base comprise -- tienne dans les 50 ms de la fenetre. Sur
    une machine au repos c'est vrai ; sur une machine chargee, l'ecriture seule
    peut les depasser, le cache a deja expire, et le test echoue en accusant le
    cache d'avoir mal garde.

    Constate le 04/09 : **une fois sur trente-sept**, et seulement depuis que la
    suite tourne en parallele -- c'est-a-dire depuis que la machine est chargee.
    Le defaut, lui, etait la depuis toujours.

    Allonger le sommeil ne repare rien : la fenetre du milieu resterait aussi
    etroite, et le test deviendrait seulement plus lent a echouer. On enleve
    donc l'horloge murale du raisonnement. Ce qui est verifie ne change pas --
    le cache tient tant que la fraicheur n'est pas ecoulee, et recalcule apres
    -- mais « ecoule » est desormais decide par le test, pas par la charge de
    la machine.
    """

    def __init__(self):
        self.instant = 1_000_000.0

    def time(self):
        return self.instant

    def monotonic(self):
        return self.instant

    def sleep(self, secondes):
        self.instant += secondes

    def avancer(self, secondes):
        self.instant += secondes


@pytest.fixture()
def horloge(monkeypatch):
    """Remplace l'horloge que lit `classement_service`, et elle seule."""
    fausse = _Horloge()
    monkeypatch.setattr(classement_service, "time", fausse)
    return fausse


class TestRouteClassement:
    def test_sans_authentification(self, client, jeu):
        """Les spectateurs n'ont pas de compte."""
        assert client.get("/api/public/classement").status_code == 200

    def test_contenu(self, client, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement").get_json()

        assert d["competition"]["nom"] == "Test 2026"
        assert d["calcule_le"] > 0
        groupes = {c["groupe"] for c in d["classements"]}
        assert "U11 F" in groupes and "U13 H" in groupes

    def test_les_lignes_portent_le_nom_et_le_club(self, client, jeu):
        """La page résultats doit pouvoir afficher autre chose qu'un numéro."""
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement?groupe=U11 F").get_json()
        ligne = d["classements"][0]["lignes"][0]
        assert ligne["nom"] == "Dupont Lea"
        assert ligne["club"] == "Les Lezards"
        assert ligne["score"] == 1000        # seule sur ce bloc dans sa categorie

    def test_la_reponse_ne_divulgue_rien_d_autre(self, client, jeu):
        """Les noms sont publics — ils sont sur les dossards et annonces au micro.

        Le reste ne l'est pas. Ces pages sont ouvertes a tout Internet et
        portent des donnees de MINEURS : chaque champ qui sort doit avoir une
        raison d'etre affiche.
        """
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement").get_json()

        # « blocs » est un COMPTE de blocs reussis, pas la liste des blocs.
        # « membres » est le nombre de grimpeurs d'un club (spec 010) : un
        # agregat, qui ne designe personne. Ajoute ICI, consciemment, parce que
        # ce test a fait son travail en le refusant d'abord.
        autorises = {"participant_id", "dossard", "nom", "club", "categorie",
                     "score", "rang", "blocs", "membres"}
        for classement in d["classements"]:
            for ligne in classement["lignes"]:
                surplus = set(ligne) - autorises
                assert not surplus, f"champ non prevu dans la reponse publique : {surplus}"
                assert isinstance(ligne["blocs"], int), "un compte, pas une liste"

    def test_un_seul_groupe(self, client, jeu):
        d = client.get("/api/public/classement?groupe=U11 F").get_json()
        assert len(d["classements"]) == 1
        assert d["classements"][0]["groupe"] == "U11 F"

    def test_groupe_inconnu(self, client, jeu):
        r = client.get("/api/public/classement?groupe=U99 X")
        assert r.status_code == 404
        assert "groupes" in r.get_json()      # on dit lesquels existent

    def test_sans_competition_active(self, client, app):
        assert client.get("/api/public/classement").status_code == 409

    def test_liste_des_groupes(self, client, jeu):
        d = client.get("/api/public/groupes").get_json()
        noms = {g["nom"] for g in d["groupes"]}
        assert {"U11 F", "U13 H"} <= noms
        assert all("type" in g and "participants" in g for g in d["groupes"])


class TestCache:
    def setup_method(self):
        classement_service.invalider()

    def test_deux_appels_rapproches_ne_calculent_qu_une_fois(self, app, jeu, monkeypatch):
        appels = {"n": 0}
        vrai = classement_service.calculer_tout

        def compter(*a, **k):
            appels["n"] += 1
            return vrai(*a, **k)

        monkeypatch.setattr(classement_service, "calculer_tout", compter)

        for _ in range(5):
            classement_service.classements(jeu["competition"])
        assert appels["n"] == 1, "le calcul doit etre mutualise"

    def test_le_cache_expire_au_bout_de_la_fraicheur(self, app, jeu, monkeypatch,
                                                     horloge):
        """Sans expiration, un spectateur verrait le classement de 9 h a 17 h.

        On garde la vraie duree de fraicheur -- cinq secondes -- et on fait
        avancer l'horloge : c'est bien le MECANISME d'expiration qui est
        exerce, pas un appel force, et sans attendre quoi que ce soit. Voir
        [_Horloge] pour ce que le sommeil coutait.
        """
        appels = {"n": 0}
        vrai = classement_service.calculer_tout

        def compter(*a, **k):
            appels["n"] += 1
            return vrai(*a, **k)

        monkeypatch.setattr(classement_service, "calculer_tout", compter)

        classement_service.classements(jeu["competition"])
        classement_service.classements(jeu["competition"])
        assert appels["n"] == 1, "deux appels rapproches : un seul calcul"

        horloge.avancer(classement_service.FRAICHEUR_S + 0.01)
        classement_service.classements(jeu["competition"])
        assert appels["n"] == 2, "passe la fraicheur, il faut recalculer"

    def test_une_reussite_arrivee_pendant_la_fraicheur_apparait_ensuite(
            self, app, jeu, horloge):
        """Jamais un classement a moitie a jour : soit l'ancien, soit le nouveau.

        Le calcul repart toujours de la base — il n'y a pas d'etat incremental a
        desynchroniser. La reussite arrivee entre-temps est donc simplement
        prise au calcul suivant, entiere.

        ⚠️ C'est le test qui a rougi une fois sur trente-sept le 04/09, et son
        assertion du milieu etait en cause -- pas le cache. Voir [_Horloge].
        """
        def score(dossard=1):
            tous, _ = classement_service.classements(jeu["competition"])
            ligne = next(l for l in tous["U11 F"].lignes if l.dossard == dossard)
            return ligne.score

        assert score() == 0, "aucune reussite au depart"

        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        assert score() == 0, "pendant la fraicheur, l'ancien resultat tient"

        horloge.avancer(classement_service.FRAICHEUR_S + 0.01)
        assert score() == 1000, "au calcul suivant, la reussite est prise"

    def test_forcer_recalcule(self, app, jeu, monkeypatch):
        appels = {"n": 0}
        vrai = classement_service.calculer_tout
        monkeypatch.setattr(classement_service, "calculer_tout",
                            lambda *a, **k: (appels.__setitem__("n", appels["n"] + 1),
                                             vrai(*a, **k))[1])
        classement_service.classements(jeu["competition"])
        classement_service.classements(jeu["competition"], forcer=True)
        assert appels["n"] == 2

    def test_invalider_force_le_recalcul(self, app, jeu, horloge):
        _, premier = classement_service.classements(jeu["competition"])
        classement_service.invalider(jeu["competition"].id)
        # Le sommeil n'etait la que pour que les deux horodatages different :
        # `time.time()` a une resolution assez fine pour que ce soit vrai la
        # plupart du temps, et pas toujours. On le DIT, plutot que d'esperer.
        horloge.avancer(0.01)
        _, second = classement_service.classements(jeu["competition"])
        assert second > premier

    def test_une_nouvelle_reussite_apparait_apres_invalidation(self, app, jeu):
        """Le cas réel : un juge valide, la page doit finir par le montrer."""
        avant, _ = classement_service.classements(jeu["competition"])
        assert avant["U11 F"].lignes[0].score == 0

        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        classement_service.invalider(jeu["competition"].id)

        apres, _ = classement_service.classements(jeu["competition"])
        assert apres["U11 F"].lignes[0].score == 1000


class TestOptionCouleur:
    """La cascade est une option PAR COMPÉTITION, vide par défaut (spec 025)."""

    def setup_method(self):
        classement_service.invalider()

    def test_desactivee_par_defaut(self, app, jeu):
        assert not classement_service.cascade(jeu["competition"])

    def test_lue_depuis_les_options_de_la_competition(self, app, jeu):
        """Deux éditions peuvent avoir des règles différentes."""
        jeu["competition"].options = json.dumps({"cascade": {
            "actif": True,
            "regles": [{"parmi": ["Rouge"], "seuil": 1, "cibles": ["Jaune"]}],
        }})
        db.session.commit()
        casc = classement_service.cascade(jeu["competition"])
        assert len(casc.phrases) == 1
        assert casc.phrases[0].cibles == frozenset({"Jaune"})

    def test_options_illisibles_ne_font_pas_planter(self, app, jeu):
        jeu["competition"].options = "pas du json"
        db.session.commit()
        assert not classement_service.cascade(jeu["competition"])

    def test_valeur_absurde_ignoree(self, app, jeu):
        jeu["competition"].options = '{"validation_couleur": "beaucoup"}'
        db.session.commit()
        assert not classement_service.cascade(jeu["competition"])

    def test_ancienne_option_lue_en_repli(self, app, jeu):
        """⚠️ Compatibilité : une édition d'avant la spec 025 ne doit pas
        changer de classement. `validation_couleur = N` se convertit en
        « au moins N parmi les couleurs plus dures », ce qui est EXACTEMENT
        l'ancienne règle."""
        jeu["competition"].options = '{"validation_couleur": 2}'
        db.session.commit()
        casc = classement_service.cascade(jeu["competition"])
        assert casc.phrases == cascade_module.regle_du_classeur(2)

    def test_cascade_prime_sur_l_ancienne_option(self, app, jeu):
        """Les deux clés présentes : la nouvelle gagne, sans quoi on ne pourrait
        jamais éteindre une règle héritée."""
        jeu["competition"].options = json.dumps({
            "validation_couleur": 2,
            "cascade": {"actif": False, "regles": []},
        })
        db.session.commit()
        assert not classement_service.cascade(jeu["competition"])


class TestSourceDesReussites:
    def test_une_reussite_saisie_a_la_main_compte_comme_un_scan(self, app, jeu):
        """La saisie manuelle existe parce qu'un QR peut etre illisible.

        Si le classement ignorait ces reussites, le grimpeur serait penalise
        pour un probleme d'impression — et personne ne le verrait, puisque la
        reussite EST bien en base.
        """
        from climbcontest.models import SOURCE_MANUEL, SOURCE_SCAN

        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0],
                             source=SOURCE_MANUEL)
        enregistrer_reussite(jeu["participants"][1], jeu["blocs"][0],
                             source=SOURCE_SCAN)

        tous, _ = classement_service.classements(jeu["competition"])

        manuel = next(l for l in tous["U11 F"].lignes
                      if l.participant_id == jeu["participants"][0].id)
        scan = next(l for l in tous["U13 H"].lignes
                    if l.participant_id == jeu["participants"][1].id)
        assert manuel.score > 0, "une reussite manuelle doit rapporter"
        assert manuel.blocs_reussis == 1
        # Chacun est seul sur ce bloc DANS SON GROUPE : meme valeur des deux
        # cotes, ce qui isole exactement la variable « source ».
        assert manuel.score == scan.score


class TestIsolationDesCompetitions:
    def test_les_classements_ne_se_melangent_pas(self, app, jeu):
        """La base est multi-compétition : une archive ne doit jamais polluer
        le classement du jour."""
        from climbcontest.models import Competition, Participant
        autre = Competition(nom="Archive 2025", active=False)
        db.session.add(autre)
        db.session.commit()
        db.session.add(Participant(competition_id=autre.id, nom="Ancien",
                                   categorie="U11 F", dossard=1))
        db.session.commit()

        classement_service.invalider()
        resultat, _ = classement_service.classements(jeu["competition"])
        dossards = {l.dossard for c in resultat.values() for l in c.lignes}
        noms = {l.participant_id for c in resultat.values() for l in c.lignes}
        anciens = {p.id for p in Participant.query.filter_by(competition_id=autre.id)}
        assert not (noms & anciens), "un participant d'une autre competition est apparu"


class TestOrdreDesClassements:
    """L'ordre de la réponse est l'ordre de la barre, donc l'ordre du cycle sur
    le mur : du plus général au plus précis, et chaque circuit ouvre SA famille.

        Scratch, Scratch F, Scratch H
        U11 scratch, U11 F, U11 H
        U13 scratch, U13 F, U13 H
        Clubs

    Demandé par Adrien le 01/09 : les scratchs avant leurs catégories, les
    généraux tout à gauche.
    """

    def test_les_scratchs_generaux_ouvrent_la_liste(self, client, jeu):
        from climbcontest.contest import enregistrer_reussite
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement").get_json()
        types = [c["type"] for c in d["classements"]]
        if "scratch" in types:
            assert types.index("scratch") == 0
        assert types[-1] == "club", "le cumul par club ferme la marche"

    def test_chaque_circuit_ouvre_sa_famille(self, client, jeu):
        """« U13 » vient avant « U13 F » et « U13 H », et rien d'un autre
        circuit ne s'intercale."""
        from climbcontest.contest import enregistrer_reussite
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        d = client.get("/api/public/classement").get_json()
        sportifs = [c for c in d["classements"] if c["type"] in ("circuit", "categorie")]
        circuits = [c["circuit"] for c in sportifs]
        # les circuits se suivent sans se mélanger
        assert circuits == sorted(circuits, key=lambda x: (circuits.index(x)))
        for i, c in enumerate(sportifs):
            if c["type"] == "circuit":
                continue
            precedents = [x for x in sportifs[:i] if x["circuit"] == c["circuit"]]
            assert precedents and precedents[0]["type"] == "circuit", \
                f"« {c['groupe']} » n'est pas précédé de son circuit"


class TestBlocsDuGrimpeur:
    """L'accesseur par grimpeur — spec 025 (F6), et contrat avec la spec 026.

    ⚠️ **Les trois ensembles sont disjoints par construction**, et la fiche du
    grimpeur (spec 026) en dépend : elle peint `grimpes | credites` et
    afficherait deux fois le même bloc s'ils se recouvraient.
    """

    def _regle_vert(self, comp):
        comp.options = json.dumps({"cascade": {
            "actif": True,
            "regles": [{"parmi": ["Vert"], "seuil": 1, "cibles": ["Jaune"]}],
        }})
        db.session.commit()

    def test_sans_cascade(self, app, jeu):
        lea, vert = jeu["participants"][0], jeu["blocs"][1]
        enregistrer_reussite(lea, vert)
        d = classement_service.blocs_du_grimpeur(jeu["competition"], lea)
        assert d["grimpes"] == {vert.id}
        assert d["credites"] == set()

    def test_avec_cascade(self, app, jeu):
        lea, jaune, vert = jeu["participants"][0], jeu["blocs"][0], jeu["blocs"][1]
        enregistrer_reussite(lea, vert)
        self._regle_vert(jeu["competition"])
        d = classement_service.blocs_du_grimpeur(jeu["competition"], lea)
        assert d["grimpes"] == {vert.id}
        assert d["credites"] == {jaune.id}

    def test_une_reussite_hors_circuit_est_servie_a_part(self, app, jeu):
        """Un juge a force l'avertissement de la spec 019 : la reussite est bien
        enregistree, elle ne compte simplement pas au classement. C'est le seul
        endroit du systeme ou elle devient visible pour la personne concernee."""
        lea, dehors = jeu["participants"][0], jeu["blocs"][2]   # DV21, circuit U13
        enregistrer_reussite(lea, dehors, hors_circuit_force=True)
        d = classement_service.blocs_du_grimpeur(jeu["competition"], lea)
        assert d["hors_circuit"] == {dehors.id}
        assert d["grimpes"] == set()
        assert d["credites"] == set()

    def test_les_trois_ensembles_sont_disjoints(self, app, jeu):
        lea = jeu["participants"][0]
        enregistrer_reussite(lea, jeu["blocs"][1])
        enregistrer_reussite(lea, jeu["blocs"][2], hors_circuit_force=True)
        self._regle_vert(jeu["competition"])
        d = classement_service.blocs_du_grimpeur(jeu["competition"], lea)
        assert d["grimpes"] & d["credites"] == set()
        assert d["grimpes"] & d["hors_circuit"] == set()
        assert d["credites"] & d["hors_circuit"] == set()

    def test_une_categorie_eteinte_ne_credite_rien(self, app, jeu):
        lea = jeu["participants"][0]
        enregistrer_reussite(lea, jeu["blocs"][1])
        jeu["competition"].options = json.dumps({"cascade": {
            "actif": True,
            "regles": [{"parmi": ["Vert"], "seuil": 1, "cibles": ["Jaune"]}],
            "categories_eteintes": ["U11 F"],
        }})
        db.session.commit()
        d = classement_service.blocs_du_grimpeur(jeu["competition"], lea)
        assert d["credites"] == set()
