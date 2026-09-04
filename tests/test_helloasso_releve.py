"""Le relevé HelloAsso — spec 008, lot 5.

Le réseau est doublé : `ClientDouble` rend les articles qu'on lui donne. Ce
qu'on vérifie ici est ce qui se voit le jour J et jamais avant.

Deux tests portent tout le fichier :

- `test_le_meme_article_releve_dix_fois` — le fil repasse toutes les soixante
  secondes, avec un recouvrement volontaire de cinq minutes. Sans l'idempotence,
  chaque tour créerait des doublons ;
- `test_une_commande_deux_enfants` — une commande peut porter deux inscrits.
  C'est le cas nominal d'une fratrie, et celui qu'un import « par commande »
  raterait.
"""

from datetime import datetime

import pytest

from climbcontest.extensions import db
from climbcontest.helloasso import releve
from climbcontest.helloasso.client import ErreurHelloAsso
from climbcontest.models import (
    A_IMPRIMER, A_TRANCHER, Circuit, Inscription, MOTIF_ANNEE_ABSENTE,
    MOTIF_ANNEE_HORS_BAREME, MOTIF_ANNEE_ILLISIBLE, MOTIF_ANNULEE,
    MOTIF_GENRE_INDETERMINE,
    MOTIF_SANS_NOM, Participant, SOURCE_CLASSEUR, SOURCE_HELLOASSO,
)
from climbcontest.cycle import ecrire_options, regler_sources


class ClientDouble:
    def __init__(self, articles):
        self._articles = articles
        self.appels = []

    def articles(self, slug, type_de_formulaire, slug_formulaire, depuis=None):
        self.appels.append({"depuis": depuis})
        yield from self._articles


CONFIG = {
    "organisation": "annonay-escalade",
    "form_type": "Event",
    "form_slug": "bloc-party-2026",
    "champs": {"naissance": "Date de naissance", "genre": "Sexe",
               "club": "Votre club"},
    "genre_valeurs": {"Fille": "F", "Garçon": "H", "F": "F"},
}


def article(identifiant=1, nom="Brunel", prenom="Lea", annee="12/04/2015",
            sexe="Fille", club="Annonay Escalade", etat="Processed",
            commande=8868440, maj="2026-11-15T09:12:00+01:00"):
    champs = []
    if annee is not None:
        champs.append({"name": "Date de naissance", "answer": annee})
    if sexe is not None:
        champs.append({"name": "Sexe", "answer": sexe})
    if club is not None:
        champs.append({"name": "Votre club", "answer": club})
    return {
        "id": identifiant,
        "state": etat,
        "user": ({"firstName": prenom, "lastName": nom} if nom else None),
        "customFields": champs,
        "meta": {"updatedAt": maj},
        "order": {"id": commande, "payer": {"firstName": "Parent",
                                            "lastName": "Payeur",
                                            "email": "parent@example.org",
                                            "address": "23 rue du marechal"}},
    }


@pytest.fixture()
def edition(app, competition):
    """Une édition qui déclare HelloAsso comme source, et ses circuits.

    ⚠️ `regler_sources` n'est pas un détail de fixture : depuis le 04/09, une
    édition qui n'a pas déclaré HelloAsso **refuse** le relevé. C'est ce qui
    empêche des inscrits d'entrer dans une compétition qui a dit ne pas s'en
    servir — et personne n'aurait compris d'où ils venaient.
    """
    for nom in ("U11", "U13", "U15"):
        db.session.add(Circuit(competition_id=competition.id, nom=nom))
    db.session.commit()
    ecrire_options(competition, helloasso=CONFIG)
    regler_sources(competition, [SOURCE_CLASSEUR, SOURCE_HELLOASSO])
    return competition


def relever(edition, articles, tout=False):
    return releve.relever(edition, client=ClientDouble(articles), tout=tout)


class TestLeCasNominal:
    def test_un_article_cree_une_inscription_et_un_participant(self, edition):
        rapport = relever(edition, [article()])
        assert rapport.nouvelles == 1
        i = Inscription.query.one()
        assert i.etat == A_IMPRIMER and i.motif is None
        p = db.session.get(Participant, i.participant_id)
        assert p.nom == "Brunel" and p.categorie == "U13 F"
        assert p.annee_naissance == 2015
        assert p.source == SOURCE_HELLOASSO
        assert p.dossard is not None

    def test_la_categorie_vient_de_l_annee_pas_du_tarif(self, edition):
        """Ne 2015, reference 2027 : douze ans, donc U13."""
        relever(edition, [article(annee="2015")])
        assert Participant.query.one().categorie == "U13 F"

    def test_le_genre_vient_du_champ(self, edition):
        relever(edition, [article(sexe="Garçon")])
        assert Participant.query.one().categorie == "U13 H"

    def test_le_formatage_s_applique(self, edition):
        relever(edition, [article(nom="BRUNEL", prenom="léa",
                                  club="roc n'potes")])
        p = Participant.query.one()
        assert p.nom == "Brunel" and p.prenom == "Léa"
        assert p.club == "Roc N'Potes"

    def test_le_catalogue_est_incremente(self, edition):
        avant = edition.catalogue_version
        relever(edition, [article()])
        db.session.refresh(edition)
        assert edition.catalogue_version > avant


class TestLIdempotence:
    def test_le_meme_article_releve_dix_fois(self, edition):
        """Le fil repasse toutes les soixante secondes, avec recouvrement."""
        for _ in range(10):
            relever(edition, [article()], tout=True)
        assert Inscription.query.count() == 1
        assert Participant.query.count() == 1

    def test_le_second_releve_ne_recree_pas_le_participant(self, edition):
        relever(edition, [article()])
        premier = Participant.query.one().id
        rapport = relever(edition, [article()], tout=True)
        assert rapport.deja_connues == 1 and rapport.nouvelles == 0
        assert Participant.query.one().id == premier

    def test_deux_articles_de_la_meme_personne_ne_font_qu_un_participant(self, edition):
        """Quelqu'un s'inscrit deux fois en ligne. Le rapprochement rattrape."""
        relever(edition, [article(identifiant=1)])
        relever(edition, [article(identifiant=2)], tout=True)
        assert Inscription.query.count() == 2
        assert Participant.query.count() == 1


class TestLaFratrie:
    def test_une_commande_deux_enfants(self, edition):
        """Une commande, deux articles : un import « par commande » perdrait
        le second, silencieusement."""
        rapport = relever(edition, [
            article(identifiant=1, nom="Peyron", prenom="Jade", sexe="Fille"),
            article(identifiant=2, nom="Peyron", prenom="Sacha", sexe="Garçon",
                    annee="2013"),
        ])
        assert rapport.nouvelles == 2
        assert Participant.query.count() == 2
        assert {p.categorie for p in Participant.query} == {"U13 F", "U15 H"}


class TestCeQuiPasseEnAttente:
    def test_sans_annee(self, edition):
        relever(edition, [article(annee=None)])
        i = Inscription.query.one()
        assert i.etat == A_TRANCHER and i.motif == MOTIF_ANNEE_ABSENTE
        assert Participant.query.count() == 0

    def test_annee_hors_bareme(self, edition):
        relever(edition, [article(annee="1990")])
        assert Inscription.query.one().motif == MOTIF_ANNEE_HORS_BAREME

    def test_une_annee_illisible_se_distingue_d_une_annee_absente(self, edition):
        """« 2916 » pour « 2016 » : le champ n'est pas vide, il est faux.

        Dire « année absente » enverrait chercher au mauvais endroit.
        """
        relever(edition, [article(annee="2916")])
        assert Inscription.query.one().motif == MOTIF_ANNEE_ILLISIBLE

    def test_un_adulte_est_hors_bareme(self, edition):
        relever(edition, [article(annee="1990", identifiant=9)])
        assert Inscription.query.one().motif == MOTIF_ANNEE_HORS_BAREME

    def test_genre_inconnu(self, edition):
        """Une réponse absente de la table ne vaut JAMAIS « H » par défaut."""
        relever(edition, [article(sexe="Ne se prononce pas")])
        assert Inscription.query.one().motif == MOTIF_GENRE_INDETERMINE
        assert Participant.query.count() == 0

    def test_sans_genre_du_tout(self, edition):
        relever(edition, [article(sexe=None)])
        assert Inscription.query.one().motif == MOTIF_GENRE_INDETERMINE

    def test_sans_user_on_retombe_sur_le_payeur_et_on_attend(self, edition):
        relever(edition, [article(nom=None, prenom=None)])
        i = Inscription.query.one()
        assert i.motif == MOTIF_SANS_NOM
        assert i.nom == "Payeur"          # repli, mais mis en attente
        assert Participant.query.count() == 0

    def test_un_club_different_attend_un_humain(self, edition):
        db.session.add(Participant(competition_id=edition.id, nom="Brunel",
                                   prenom="Lea", club="CAF Vivarais",
                                   categorie="U13 F", dossard=5))
        db.session.commit()
        relever(edition, [article()])
        assert Inscription.query.one().etat == A_TRANCHER
        assert Participant.query.count() == 1


class TestLeRattachement:
    def test_meme_nom_meme_club_ne_duplique_pas(self, edition):
        db.session.add(Participant(competition_id=edition.id, nom="Brunel",
                                   prenom="Lea", club="Annonay Escalade",
                                   categorie="U13 F", dossard=5))
        db.session.commit()
        rapport = relever(edition, [article()])
        assert rapport.rattachees == 1
        assert Participant.query.count() == 1
        assert Inscription.query.one().participant_id is not None

    def test_le_rattachement_complete_sans_ecraser(self, edition):
        """La console fait autorité sur ce que quelqu'un y a saisi."""
        p = Participant(competition_id=edition.id, nom="Brunel", prenom="Lea",
                        club="Annonay Escalade", categorie="U15 F", dossard=5)
        db.session.add(p)
        db.session.commit()
        relever(edition, [article()])
        db.session.refresh(p)
        assert p.annee_naissance == 2015          # complete
        assert p.categorie == "U15 F"             # jamais ecrase


class TestLAnnulation:
    def test_un_article_annule_jamais_vu_ne_cree_rien(self, edition):
        relever(edition, [article(etat="Canceled")])
        assert Inscription.query.count() == 0
        assert Participant.query.count() == 0

    def test_un_article_annule_apres_coup_remonte_sans_rien_supprimer(self, edition):
        relever(edition, [article()])
        participant = Participant.query.one().id
        relever(edition, [article(etat="Canceled")], tout=True)
        i = Inscription.query.one()
        assert i.etat == A_TRANCHER and i.motif == MOTIF_ANNULEE
        assert db.session.get(Participant, participant) is not None

    @pytest.mark.parametrize("etat", ["Refused", "Abandoned", "Deleted", "Waiting"])
    def test_les_autres_etats_ne_valent_pas_inscription(self, edition, etat):
        relever(edition, [article(etat=etat)])
        assert Participant.query.count() == 0


class TestLesDonneesDuPayeur:
    def test_rien_du_payeur_n_entre_en_base(self, edition):
        """Décision D5. Le payeur est un parent : on n'a aucun usage de ses
        coordonnées, et ce sont des données personnelles."""
        relever(edition, [article()])
        i = Inscription.query.one()
        for colonne in Inscription.__table__.columns:
            valeur = getattr(i, colonne.name)
            if isinstance(valeur, str):
                assert "parent@example.org" not in valeur
                assert "marechal" not in valeur
        assert not hasattr(i, "courriel")
        assert not hasattr(i, "detail")
        assert not hasattr(i, "tarif")

    def test_le_numero_de_commande_est_garde(self, edition):
        """Un entier ne décrit personne, et c'est par lui qu'on retrouve la
        commande dans le back-office."""
        relever(edition, [article()])
        assert Inscription.query.one().commande_id == 8868440


class TestLaLectureDUnArticle:
    @pytest.mark.parametrize("brut,attendu", [
        ("2015", 2015), ("12/04/2015", 2015), ("2015-04-12T00:00:00+02:00", 2015),
        ("", None), (None, None), ("abc", None), ("15/04", None),
    ])
    def test_l_annee_se_lit_dans_tous_les_formats(self, brut, attendu):
        assert releve.annee_de(brut) == attendu

    @pytest.mark.parametrize("brut,attendu", [
        ("Fille", "F"), ("fille", "F"), (" Garçon ", "H"), ("F", "F"),
        ("Autre", None), (None, None), ("", None),
    ])
    def test_le_genre_se_range(self, brut, attendu):
        assert releve.genre_de(brut, CONFIG["genre_valeurs"]) == attendu


class TestLeCurseur:
    def test_le_premier_releve_part_de_zero(self, edition):
        client = ClientDouble([article()])
        releve.relever(edition, client=client)
        assert client.appels[0]["depuis"] is None

    def test_le_second_repart_du_dernier_vu(self, edition):
        relever(edition, [article()])
        client = ClientDouble([])
        releve.relever(edition, client=client)
        assert client.appels[0]["depuis"] == datetime(2026, 11, 15, 9, 12)

    def test_tout_ignore_le_curseur(self, edition):
        relever(edition, [article()])
        client = ClientDouble([])
        releve.relever(edition, client=client, tout=True)
        assert client.appels[0]["depuis"] is None


class TestLaRobustesse:
    def test_un_article_qui_echoue_n_emporte_pas_les_autres(self, edition):
        casse = article(identifiant=2)
        casse["customFields"] = "pas une liste"
        rapport = relever(edition, [article(identifiant=1), casse,
                                    article(identifiant=3, nom="Vidal",
                                            prenom="Tom", sexe="Garçon")])
        assert rapport.vus == 3
        assert rapport.nouvelles == 2
        assert len(rapport.erreurs) == 1

    def test_un_article_sans_identifiant_est_signale(self, edition):
        sans = article()
        sans["id"] = None
        rapport = relever(edition, [sans])
        assert rapport.erreurs and Inscription.query.count() == 0

    def test_sans_formulaire_choisi(self, app, competition):
        with pytest.raises(ErreurHelloAsso):
            releve.relever(competition, client=ClientDouble([]))
