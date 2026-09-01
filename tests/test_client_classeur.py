"""Le classeur vu du client : la grille s'agrandit, le jeton se lit (spec 015).

Le scénario qui justifie ce fichier tient en une phrase : **un dossard attribué
à chaud sort de la largeur préparée dans l'onglet `Import`, Google refuse
l'écriture, et le miroir la retente pour toujours.** Aucun test ne pouvait le
voir jusqu'ici — le client n'était testé que par le miroir, avec un faux
classeur qui n'a pas de grille.

Aucun accès réseau : le service Google est remplacé par un objet qui note ce
qu'on lui demande. Les paquets `google-*` ne sont même pas installés dans le
venv de développement, et ça doit le rester.
"""

import json
import os
import stat

import pytest

from climbcontest.sheets import client as mod
from climbcontest.sheets.client import (
    ClasseurGoogle, ErreurClasseur, ecrire_jeton_json, etat_jeton, trouver_jeton,
)


# --- Le faux service Google -------------------------------------------------

class Requete:
    """Ce que rend un appel de l'API Google : un objet qu'on `execute()`."""

    def __init__(self, service, nom, kwargs, retour):
        self.service, self.nom, self.kwargs, self.retour = service, nom, kwargs, retour

    def execute(self):
        self.service.appels.append((self.nom, self.kwargs))
        if self.nom in self.service.echecs:
            raise RuntimeError(f"Google refuse : {self.nom} (simule)")
        return self.retour() if callable(self.retour) else self.retour


class Valeurs:
    def __init__(self, service):
        self.service = service

    def get(self, **kw):
        plage = kw.get("range", "")
        return Requete(self.service, "values.get", kw,
                       {"values": self.service.lectures.get(plage, [])})

    def batchUpdate(self, **kw):                                  # noqa: N802
        return Requete(self.service, "values.batchUpdate", kw, {})

    def update(self, **kw):
        # Une ecriture se RELIT : c'est ce qui permet a l'essai d'ecriture de
        # verifier ce qu'il a pose, et de detecter une ecriture acceptee mais
        # sans effet.
        def poser():
            self.service.lectures[kw["range"]] = kw["body"]["values"]
            return {}
        return Requete(self.service, "values.update", kw, poser)

    def clear(self, **kw):
        def effacer():
            self.service.lectures.pop(kw["range"], None)
            return {}
        return Requete(self.service, "values.clear", kw, effacer)


class FeuillesFictives:
    """Un classeur en mémoire : un onglet `Import` et sa grille."""

    def __init__(self, lignes=50, colonnes=26, onglets=("Import", "Listes", "Plan"),
                 lectures=None, echecs=(), protections=None):
        self.grilles = {nom: {"lignes": lignes, "colonnes": colonnes}
                        for nom in onglets}
        self.lectures = dict(lectures or {})
        self.echecs = set(echecs)
        self.protections = protections or {}
        self.appels = []

    # -- l'API telle que le client l'appelle
    def get(self, **kw):
        return Requete(self, "get", kw, self._meta)

    def batchUpdate(self, **kw):                                  # noqa: N802
        for requete in kw.get("body", {}).get("requests", []):
            proprietes = requete["updateSheetProperties"]["properties"]
            nom = self._nom_par_id(proprietes["sheetId"])
            grille = proprietes.get("gridProperties", {})
            if "rowCount" in grille:
                self.grilles[nom]["lignes"] = grille["rowCount"]
            if "columnCount" in grille:
                self.grilles[nom]["colonnes"] = grille["columnCount"]
        return Requete(self, "batchUpdate", kw, {})

    def values(self):
        return Valeurs(self)

    # -- interne
    def _nom_par_id(self, identifiant):
        return list(self.grilles)[identifiant]

    def _meta(self):
        return {
            "properties": {"title": "Classeur de test"},
            "sheets": [
                {"properties": {"sheetId": i, "title": nom,
                                "gridProperties": {"rowCount": g["lignes"],
                                                   "columnCount": g["colonnes"]}},
                 "protectedRanges": [
                     {"protectedRangeId": 100 + j, "description": texte}
                     for j, texte in enumerate(self.protections.get(nom, []))]}
                for i, (nom, g) in enumerate(self.grilles.items())
            ],
        }

    def combien(self, nom):
        return sum(1 for appel, _ in self.appels if appel == nom)

    def dernier(self, nom):
        for appel, kw in reversed(self.appels):
            if appel == nom:
                return kw
        raise AssertionError(f"aucun appel « {nom} » dans {self.appels}")


def classeur(**kw):
    feuilles = FeuillesFictives(**kw)
    return ClasseurGoogle("classeur-de-test", feuilles=feuilles), feuilles


# --- A1, A2, A3 : la grille s'agrandit quand il le faut, jamais sinon -------

class TestAgrandissement:

    def test_un_dossard_hors_largeur_agrandit_puis_ecrit(self):
        """Le cas réel : dossard 130 → colonne DA, sur une grille de 26.

        Sans agrandissement, Google répond « exceeds grid limits » et cette
        réussite bloque son lot à chaque cycle, indéfiniment.
        """
        cl, feuilles = classeur(colonnes=26)
        cl.marquer_reussites([(130, 3)])

        agrandissement = feuilles.dernier("batchUpdate")
        proprietes = agrandissement["body"]["requests"][0]["updateSheetProperties"]
        assert proprietes["properties"]["gridProperties"]["columnCount"] >= 133
        assert "gridProperties.columnCount" in proprietes["fields"]
        # et l'écriture a bien eu lieu APRÈS
        assert [nom for nom, _ in feuilles.appels][-1] == "values.batchUpdate"

    def test_la_cellule_visee_reste_la_meme(self):
        cl, feuilles = classeur(colonnes=26)
        cl.marquer_reussites([(130, 3)])
        donnees = feuilles.dernier("values.batchUpdate")["body"]["data"]
        assert donnees[0]["range"] == "Import!EC4"      # 130 + 3 = 133 -> EC

    def test_un_numero_de_bloc_hors_hauteur_agrandit_les_lignes(self):
        cl, feuilles = classeur(lignes=50, colonnes=200)
        cl.marquer_reussites([(12, 80)])
        proprietes = feuilles.dernier("batchUpdate")["body"]["requests"][0]
        grille = proprietes["updateSheetProperties"]["properties"]["gridProperties"]
        assert grille["rowCount"] >= 81
        assert "columnCount" not in grille        # la largeur suffisait

    def test_une_grille_suffisante_ne_declenche_aucun_agrandissement(self):
        cl, feuilles = classeur(lignes=60, colonnes=123)
        cl.marquer_reussites([(5, 2), (12, 40)])
        assert feuilles.combien("batchUpdate") == 0
        assert feuilles.combien("values.batchUpdate") == 1

    def test_la_grille_n_est_lue_qu_une_fois_pour_plusieurs_lots(self):
        """Le miroir tourne toutes les 40 secondes : une lecture par lot serait
        un appel Google de plus toutes les 40 secondes, pour rien."""
        cl, feuilles = classeur(lignes=60, colonnes=123)
        cl.marquer_reussites([(5, 2)])
        cl.marquer_reussites([(6, 2)])
        assert feuilles.combien("get") == 1

    def test_apres_agrandissement_le_lot_suivant_relit_la_grille(self):
        cl, feuilles = classeur(colonnes=26)
        cl.marquer_reussites([(130, 3)])          # agrandit -> cache invalide
        cl.marquer_reussites([(131, 3)])          # tient dans la nouvelle grille
        assert feuilles.combien("get") == 2
        assert feuilles.combien("batchUpdate") == 1

    def test_un_agrandissement_refuse_n_ecrit_rien(self):
        """C'est la propriété qui protège les réussites : si l'agrandissement
        échoue, on lève, et le miroir ne marque rien comme synchronisé."""
        cl, feuilles = classeur(colonnes=26, echecs=("batchUpdate",))
        with pytest.raises(ErreurClasseur):
            cl.marquer_reussites([(130, 3)])
        assert feuilles.combien("values.batchUpdate") == 0

    def test_un_onglet_import_absent_le_dit(self):
        cl, _ = classeur(onglets=("Listes", "Plan"))
        with pytest.raises(ErreurClasseur, match="Import"):
            cl.marquer_reussites([(1, 1)])

    def test_un_lot_vide_ne_touche_a_rien(self):
        cl, feuilles = classeur()
        assert cl.marquer_reussites([]) == 0
        assert feuilles.appels == []


# --- A9 : vider la matrice sans toucher aux en-têtes ------------------------

class TestVidage:

    def test_la_plage_effacee_commence_en_D2(self):
        """Ligne 1 = les dossards, colonnes A à C = numéro et tag du bloc.
        Les effacer rendrait le classeur inutilisable."""
        cl, feuilles = classeur(lectures={
            "Import!1:1": [["N°", "Tag", "", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]],
            "Import!A2:A": [[1], [2], [3]],
        })
        rapport = cl.vider_matrice()
        assert feuilles.dernier("values.clear")["range"] == "Import!D2:O4"
        assert rapport == {"plage": "D2:O4", "lignes": 3, "colonnes": 12}

    def test_une_matrice_vide_n_appelle_pas_google(self):
        cl, feuilles = classeur(lectures={"Import!1:1": [], "Import!A2:A": []})
        assert cl.vider_matrice()["plage"] is None
        assert feuilles.combien("values.clear") == 0

    def test_un_classeur_sans_dossard_n_est_pas_vide(self):
        """Trois colonnes d'en-tête et rien d'autre : il n'y a rien à effacer,
        et surtout pas les en-têtes."""
        cl, feuilles = classeur(lectures={
            "Import!1:1": [["N°", "Tag", ""]], "Import!A2:A": [[1], [2]]})
        assert cl.vider_matrice()["plage"] is None
        assert feuilles.combien("values.clear") == 0


class TestColonne:

    @pytest.mark.parametrize("n,attendu", [(1, "A"), (26, "Z"), (27, "AA"),
                                           (52, "AZ"), (703, "AAA")])
    def test_conversion(self, n, attendu):
        assert ClasseurGoogle.colonne(n) == attendu


# --- A12, A14 : le jeton ----------------------------------------------------

@pytest.fixture()
def secrets(tmp_path, monkeypatch):
    """Un dossier de secrets isolé — et le SEUL endroit où le jeton est cherché.

    Sans ce verrouillage, le test verrait le `token.pickle` du répertoire
    courant sur la machine d'Adrien, et passerait ou échouerait selon d'où on
    lance pytest.
    """
    monkeypatch.setattr(ClasseurGoogle, "_dossiers_de_jeton",
                        staticmethod(lambda: [tmp_path]))
    return tmp_path


JETON = {"token": "ya29.court", "refresh_token": "1//refresh",
         "client_id": "id.apps.googleusercontent.com", "client_secret": "secret",
         "scopes": ["https://www.googleapis.com/auth/spreadsheets"],
         "expiry": "2026-11-15T09:00:00Z"}


class TestJeton:

    def test_sans_jeton_l_etat_le_dit_sans_lever(self, secrets):
        etat = etat_jeton()
        assert etat["present"] is False
        assert "token.json" in etat["message"]

    def test_le_json_passe_devant_le_pickle(self, secrets):
        (secrets / "token.pickle").write_bytes(b"peu importe")
        (secrets / "token.json").write_text(json.dumps(JETON))
        chemin, forme = trouver_jeton()
        assert forme == "json" and chemin.name == "token.json"

    def test_l_etat_lit_expiration_et_scopes_sans_paquet_google(self, secrets):
        (secrets / "token.json").write_text(json.dumps(JETON))
        etat = etat_jeton()
        assert etat["valide"] is True
        assert etat["expire_le"] == "2026-11-15T09:00:00Z"
        assert etat["scopes"] == JETON["scopes"]

    def test_un_json_sans_refresh_token_est_signale(self, secrets):
        sans = dict(JETON)
        sans.pop("refresh_token")
        (secrets / "token.json").write_text(json.dumps(sans))
        etat = etat_jeton()
        assert etat["valide"] is False
        assert "refresh_token" in etat["message"]

    @pytest.mark.parametrize("contenu", ['["une", "liste"]', "42", "pas du json"])
    def test_un_fichier_douteux_ne_fait_pas_tomber_la_vue(self, secrets, contenu):
        (secrets / "token.json").write_text(contenu)
        etat = etat_jeton()
        assert etat["present"] is True and etat["valide"] is False
        assert etat["message"]

    def test_un_pickle_seul_est_reconnu_sans_etre_ouvert(self, secrets):
        (secrets / "token.pickle").write_bytes(b"binaire non deserialise")
        etat = etat_jeton()
        assert etat["present"] is True and etat["source"] == "pickle"
        assert etat["valide"] is None            # on ne l'ouvre pas pour le dire

    def test_ecriture_en_0600_et_precedent_conserve(self, secrets):
        ecrire_jeton_json(json.dumps(JETON))
        cible = secrets / "token.json"
        assert stat.S_IMODE(os.stat(cible).st_mode) == 0o600

        autre = dict(JETON, refresh_token="1//nouveau")
        ecrire_jeton_json(json.dumps(autre))
        assert json.loads(cible.read_text())["refresh_token"] == "1//nouveau"
        garde = secrets / "token.json.precedent"
        assert json.loads(garde.read_text())["refresh_token"] == "1//refresh"

    def test_le_dossier_d_ecriture_est_le_premier_de_la_liste(self, secrets):
        assert mod.chemin_jeton_json() == secrets / "token.json"


# --- A1→A5 : l'essai d'écriture (spec 018) ----------------------------------
#
# La panne qu'il attrape n'est pas « la feuille est introuvable » : c'est « la
# feuille est partagée en LECTURE SEULE avec le compte du jeton ». Ce cas-là
# passe tous les contrôles de lecture sans broncher — titre lu, onglets listés,
# grille mesurée, tout est vert — et ne se révèle que quarante secondes après
# le premier scan, quand les réussites commencent à s'empiler « en attente ».

class TestEssaiEcriture:

    def test_ecrit_relit_puis_efface_le_coin_de_la_grille(self):
        """A1. Et surtout : dans CET ordre, sur la MÊME cellule."""
        cl, feuilles = classeur(lignes=60, colonnes=123)
        rapport = cl.essai_ecriture("Import")

        assert rapport["cellule"] == "Import!DS60"
        assert (rapport["tentee"], rapport["ecriture"], rapport["restauree"]) \
            == (True, True, True)

        noms = [nom for nom, _ in feuilles.appels]
        assert noms.count("values.update") == 1
        assert noms.index("values.update") < noms.index("values.clear")

        for appel in ("values.update", "values.clear"):
            assert feuilles.dernier(appel)["range"] == "Import!DS60"

        # La cellule est bien rendue à son état d'origine.
        assert "Import!DS60" not in feuilles.lectures

    def test_le_coin_n_est_jamais_dans_la_matrice(self):
        """La ligne 1 porte les dossards, A à C les blocs, D2:… les « A ».

        Tester là où le miroir écrit vraiment détruirait une réussite réelle si
        l'effacement final échouait. Le coin, lui, est vide par construction.
        """
        cl, _ = classeur(lignes=60, colonnes=123)
        cellule = cl.essai_ecriture("Import")["cellule"]
        colonne, ligne = cellule.split("!")[1][:2], int(cellule.split("!")[1][2:])
        assert ligne > 1                      # jamais la ligne des dossards
        assert colonne > "C"                  # jamais les colonnes des blocs

    def test_une_feuille_en_lecture_seule_est_detectee(self):
        """A2. LE cas qui justifie tout ce test."""
        cl, feuilles = classeur(echecs=("values.update",))
        rapport = cl.essai_ecriture("Import")

        assert rapport["tentee"] is True
        assert rapport["ecriture"] is False
        assert rapport["restauree"] is None
        assert "MODIFICATION" in rapport["message"]
        # Rien à effacer : on n'a rien posé.
        assert feuilles.combien("values.clear") == 0

    def test_une_cellule_temoin_non_vide_interrompt_avant_d_ecrire(self):
        """A3. Mieux vaut un test qui renonce qu'un test qui écrase."""
        cl, feuilles = classeur(lignes=60, colonnes=123,
                                lectures={"Import!DS60": [["déjà quelque chose"]]})
        rapport = cl.essai_ecriture("Import")

        assert rapport["tentee"] is False
        assert rapport["ecriture"] is None
        assert "n'est pas vide" in rapport["message"]
        assert feuilles.combien("values.update") == 0
        # Et la valeur qui était là n'a pas bougé.
        assert feuilles.lectures["Import!DS60"] == [["déjà quelque chose"]]

    def test_un_effacement_rate_nomme_la_cellule(self):
        """A4. Une trace oubliée dans un coin ne gêne rien — encore faut-il
        savoir qu'elle est là plutôt que la découvrir six mois plus tard."""
        cl, _ = classeur(lignes=60, colonnes=123, echecs=("values.clear",))
        rapport = cl.essai_ecriture("Import")

        assert rapport["ecriture"] is True
        assert rapport["restauree"] is False
        assert "Import!DS60" in rapport["message"]
        assert "climbcontest-test" in rapport["message"]

    def test_une_ecriture_sans_effet_est_vue(self):
        """Acceptée par Google, mais la relecture ne rend pas ce qu'on a écrit."""
        cl, feuilles = classeur(lignes=60, colonnes=123)

        # Le faux service accepte l'écriture mais ne la conserve pas.
        vraie = feuilles.values

        class SansEffet(Valeurs):
            def update(self, **kw):
                return Requete(self.service, "values.update", kw, {})

        feuilles.values = lambda: SansEffet(feuilles)
        rapport = cl.essai_ecriture("Import")
        feuilles.values = vraie

        assert rapport["ecriture"] is False
        assert "protégée" in rapport["message"] or "protegee" in rapport["message"]

    def test_les_plages_protegees_sont_signalees(self):
        """A5. L'angle mort de l'essai : une protection posée sur `D2:DP103`
        laisse le coin parfaitement écrivable et bloque pourtant le miroir."""
        cl, _ = classeur(lignes=60, colonnes=123,
                         protections={"Import": ["Matrice verrouillée"]})
        rapport = cl.essai_ecriture("Import")
        assert rapport["plages_protegees"] == ["Matrice verrouillée"]

    def test_aucune_protection_ne_coute_aucun_appel_de_plus(self):
        """A5. `protectedRanges` s'ajoute au `fields` d'une requête déjà faite."""
        cl, feuilles = classeur(lignes=60, colonnes=123)
        cl.metadonnees()
        avant = feuilles.combien("get")
        assert cl.plages_protegees("Import") == []
        assert feuilles.combien("get") == avant

    def test_le_champ_protectedranges_est_demande_a_google(self):
        """Sans ça, l'API ne le renvoie pas et la détection serait toujours
        vide — un test vert qui ne prouve rien."""
        cl, feuilles = classeur()
        cl.metadonnees()
        assert "protectedRanges" in feuilles.dernier("get")["fields"]

    def test_une_grille_trop_petite_renonce_proprement(self):
        """Pas de cellule témoin possible hors des données : on le dit."""
        cl, feuilles = classeur(lignes=1, colonnes=3)
        rapport = cl.essai_ecriture("Import")
        assert rapport["tentee"] is False
        assert feuilles.combien("values.update") == 0

    def test_un_onglet_absent_ne_leve_pas(self):
        """A2. C'est un DIAGNOSTIC : son échec est une réponse, pas une panne.

        Une exception ici ferait remonter un 500 à la console, là où l'on
        attend « voilà ce que Google a dit ».
        """
        cl, _ = classeur(onglets=("Listes",))
        rapport = cl.essai_ecriture("Import")
        assert rapport["tentee"] is False
        assert "Import" in rapport["message"]
