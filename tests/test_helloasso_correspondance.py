"""La reconnaissance automatique des champs — spec 008, demande du 04/09.

« Lors des imports je veux un maximum d'automatisation. »

Deux façons de reconnaître, et la seconde est celle qui sert le plus :

1. **par le nom du champ** — « Date de naissance », « Sexe », « Votre club » ;
2. **par ses réponses** — un champ dont toutes les réponses sont des écritures
   de genre connues *est* un champ de genre, quel que soit son intitulé. C'est
   le filet qui rattrape « Votre enfant est » et tous les libellés qu'aucune
   liste de mots-clés ne prévoira.

Le test le plus important est
`test_un_intrus_suffit_a_disqualifier` : reconnaître un champ à ses réponses ne
doit jamais devenir « la plupart ressemblent à des genres, donc c'en est un ».
"""

import pytest

from climbcontest.helloasso import correspondance as c


class TestLesGenresConnus:
    @pytest.mark.parametrize("brut,attendu", [
        ("Fille", "F"), ("fille", "F"), ("FILLE", "F"), ("Féminin", "F"),
        ("féminine", "F"), ("F", "F"), ("Femme", "F"), ("girl", "F"),
        ("Garçon", "H"), ("garcon", "H"), ("GARÇON", "H"), ("Masculin", "H"),
        ("H", "H"), ("M", "H"), ("Homme", "H"), ("boy", "H"),
        (" Fille ", "F"),
    ])
    def test_les_ecritures_courantes(self, brut, attendu):
        assert c.genre_connu(brut) == attendu

    @pytest.mark.parametrize("brut", [
        "Ne se prononce pas", "Autre", "", None, "Poussin", "U13", "42",
    ])
    def test_ce_qui_n_est_pas_un_genre(self, brut):
        """Jamais de valeur par défaut : une grimpeuse rangée dans un
        classement masculin ne se remarque qu'au podium."""
        assert c.genre_connu(brut) is None


class TestReconnaitreParLeNom:
    def test_les_trois_champs_habituels(self):
        champs = {"Date de naissance": ["12/04/2015"], "Sexe": ["Fille"],
                  "Votre club": ["Annonay Escalade"],
                  "Certificat médical": ["Oui"]}
        devine = c.deviner(champs)
        assert devine["champs"]["naissance"] == "Date de naissance"
        assert devine["champs"]["genre"] == "Sexe"
        assert devine["champs"]["club"] == "Votre club"
        assert sorted(devine["trouves"]) == ["club", "genre", "naissance"]

    @pytest.mark.parametrize("nom", [
        "Date de naissance", "DATE DE NAISSANCE", "Né le", "Née le",
        "Année de naissance", "Birth date", "Anniversaire",
    ])
    def test_les_ecritures_de_la_naissance(self, nom):
        assert c.deviner({nom: ["2015"]})["champs"]["naissance"] == nom

    @pytest.mark.parametrize("nom", ["Sexe", "Genre", "GENRE", "Civilité"])
    def test_les_ecritures_du_genre(self, nom):
        assert c.deviner({nom: ["Fille"]})["champs"]["genre"] == nom

    @pytest.mark.parametrize("nom", [
        "Club", "Votre club", "Association", "Structure", "Licence FFME",
    ])
    def test_les_ecritures_du_club(self, nom):
        assert c.deviner({nom: ["Annonay Escalade"]})["champs"]["club"] == nom

    def test_le_champ_ignore_reste_ignore(self):
        devine = c.deviner({"Certificat médical": ["Oui", "Non"]})
        assert devine["champs"] == {"naissance": None, "genre": None, "club": None}
        assert devine["trouves"] == []


class TestReconnaitreParLesReponses:
    """Le filet qui rattrape les intitulés qu'aucune liste ne prévoit."""

    def test_un_champ_de_genre_mal_nomme(self):
        champs = {"Votre enfant est": ["Fille", "Garçon"]}
        assert c.deviner(champs)["champs"]["genre"] == "Votre enfant est"

    def test_un_champ_d_annee_mal_nomme(self):
        champs = {"Renseignement": ["2015", "2016", "2017"]}
        assert c.deviner(champs)["champs"]["naissance"] == "Renseignement"

    def test_un_intrus_suffit_a_disqualifier(self):
        """« La plupart ressemblent à des genres » ne doit jamais suffire.

        Une reconnaissance approximative rangerait tout un formulaire de
        travers, et personne ne saurait où regarder.
        """
        champs = {"Choix": ["Fille", "Garçon", "Je ne sais pas"]}
        assert c.deviner(champs)["champs"]["genre"] is None

    def test_trop_de_valeurs_n_est_pas_un_genre(self):
        champs = {"Divers": ["F", "H", "A", "B", "C", "D", "E", "G"]}
        assert c.deviner(champs)["champs"]["genre"] is None

    def test_le_nom_l_emporte_sur_les_reponses(self):
        """Un champ nommé « Sexe » est un champ de genre même si personne n'y a
        encore répondu."""
        champs = {"Sexe": [], "Autre chose": ["Fille", "Garçon"]}
        assert c.deviner(champs)["champs"]["genre"] == "Sexe"


class TestLaTableDesReponses:
    def test_elle_se_remplit_toute_seule(self):
        champs = {"Sexe": ["Fille", "Garçon", "F"]}
        devine = c.deviner(champs)
        assert devine["genre_valeurs"] == {"Fille": "F", "Garçon": "H", "F": "F"}

    def test_les_reponses_non_reconnues_sont_signalees(self):
        """Ce sont les seules lignes qui demandent encore un geste."""
        champs = {"Sexe": ["Fille", "Garçon", "Ne se prononce pas"]}
        devine = c.deviner(champs)
        assert devine["genres_inconnus"] == ["Ne se prononce pas"]
        assert "Ne se prononce pas" not in devine["genre_valeurs"]

    def test_aucun_champ_de_genre(self):
        devine = c.deviner({"Club": ["Annonay Escalade"]})
        assert devine["genre_valeurs"] == {} and devine["genres_inconnus"] == []


class TestLireLesChampsDesArticles:
    def _article(self, champs, options=None):
        return {"customFields": champs, "options": options or []}

    def test_les_reponses_distinctes(self):
        articles = [
            self._article([{"name": "Sexe", "answer": "Fille"}]),
            self._article([{"name": "Sexe", "answer": "Garçon"}]),
            self._article([{"name": "Sexe", "answer": "Fille"}]),
        ]
        assert c.champs_du_formulaire(articles) == {"Sexe": ["Fille", "Garçon"]}

    def test_les_champs_d_une_option_comptent_aussi(self):
        articles = [self._article(
            [{"name": "Sexe", "answer": "Fille"}],
            options=[{"customFields": [{"name": "Club", "answer": "Un Club"}]}])]
        assert set(c.champs_du_formulaire(articles)) == {"Sexe", "Club"}

    def test_un_article_abime_ne_fait_pas_tomber(self):
        """Un relevé qui tombe sur un champ mal formé doit continuer : c'est
        l'organisateur devant l'écran qui attend."""
        articles = [self._article("pas une liste"),
                    self._article([{"name": "Sexe", "answer": "Fille"}])]
        assert c.champs_du_formulaire(articles) == {"Sexe": ["Fille"]}

    def test_aucun_article(self):
        assert c.champs_du_formulaire([]) == {}


class TestLeReleveUtiliseLaTableIntegree:
    """Le relevé reconnaît « Fille » même sans table réglée dans la console."""

    def test_sans_table_de_l_edition(self):
        from climbcontest.helloasso import releve
        assert releve.genre_de("Fille", {}) == "F"
        assert releve.genre_de("Garçon", None) == "H"

    def test_la_table_de_l_edition_gagne(self):
        """C'est un humain qui l'a écrite : elle l'emporte toujours."""
        from climbcontest.helloasso import releve
        assert releve.genre_de("Fille", {"Fille": "H"}) == "H"

    def test_une_reponse_inconnue_des_deux(self):
        from climbcontest.helloasso import releve
        assert releve.genre_de("Ne se prononce pas", {}) is None
