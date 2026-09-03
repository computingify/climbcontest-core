"""Le simulateur de juges (`tools/simulateur_juges.py`).

Ce qu'on vérifie ici tient en une phrase : **le simulateur envoie ce qu'un
téléphone enverrait**. Un simulateur qui dérive du vrai client ne mesure plus
rien, et il dérive en silence — personne ne s'en aperçoit avant le jour où on
tire une conclusion fausse d'un test qui semblait vert.

D'où le premier test, qui relit les constantes DANS `politique.js` au lieu de
les recopier : une valeur changée d'un côté et pas de l'autre casse la suite.
"""
import re
from pathlib import Path

import pytest

from tools.simulateur import moteur

RACINE = Path(__file__).resolve().parent.parent
POLITIQUE_JS = RACINE / "climbcontest" / "static" / "juge" / "politique.js"


def _constante_js(nom: str) -> float:
    """La valeur d'une constante exportée par `politique.js`."""
    trouve = re.search(rf"export const {nom} = ([\d_]+)", POLITIQUE_JS.read_text())
    assert trouve, f"{nom} introuvable dans politique.js"
    return float(trouve.group(1).replace("_", ""))


# ── La politique d'envoi est celle du client, pas une approximation ─────────

def test_les_constantes_sont_celles_de_la_pwa():
    assert moteur.LOT_PLEIN == _constante_js("LOT_PLEIN")
    assert moteur.DELAI * 1000 == _constante_js("DELAI_MS")
    assert moteur.LOT_MAX == _constante_js("LOT_MAX")
    assert moteur.RETRAIT_INITIAL * 1000 == _constante_js("RETRAIT_INITIAL_MS")
    assert moteur.RETRAIT_MAX * 1000 == _constante_js("RETRAIT_MAX_MS")


@pytest.mark.parametrize("echecs, attendu", [
    (0, 0), (1, 2), (2, 4), (3, 8), (4, 16), (5, 32), (6, 60), (20, 60)])
def test_le_retrait_double_puis_plafonne(echecs, attendu):
    assert moteur.attente_apres_echec(echecs) == attendu


def test_rien_ne_part_quand_la_file_est_vide():
    assert not moteur.doit_envoyer(0, 999, 0, forcer=True)


def test_le_lot_plein_part_sans_attendre_le_delai():
    assert moteur.doit_envoyer(5, 0.1, 0)
    assert not moteur.doit_envoyer(4, 0.1, 0)


def test_le_delai_fait_partir_un_lot_incomplet():
    assert moteur.doit_envoyer(1, 10, 0)
    assert not moteur.doit_envoyer(1, 9.9, 0)


def test_forcer_ignore_le_lot_mais_pas_le_retrait():
    """« Tout envoyer maintenant » sur un serveur éteint ne doit pas le noyer."""
    assert moteur.doit_envoyer(1, 0.1, 0, forcer=True)
    assert not moteur.doit_envoyer(1, 0.1, 3, forcer=True)


# ── Le circuit se déduit comme côté serveur et côté PWA ────────────────────

@pytest.mark.parametrize("categorie, attendu", [
    ("U13 F", "U13"), ("U11 H", "U11"), ("Senior", "Senior"),
    ("", None), (None, None), ("  U15 F  ", "U15")])
def test_circuit_de(categorie, attendu):
    assert moteur.circuit_de(categorie) == attendu


# ── Le tirage ne sort jamais du catalogue ──────────────────────────────────

CATALOGUE = {
    "competition": {"id": 1, "nom": "Test", "statut": "en_cours"},
    "version": 7,
    "participants": [
        {"id": 1, "dossard": 1, "nom": "A", "categorie": "U11 F"},
        {"id": 2, "dossard": 2, "nom": "B", "categorie": "U13 H"},
        {"id": 3, "dossard": 3, "nom": "C", "categorie": "U13 F"},
    ],
    "blocs": [
        {"id": 1, "tag": "ZJ1", "numero": 1, "circuits": ["U11"]},
        {"id": 2, "tag": "ZJ2", "numero": 2, "circuits": ["U13"]},
        {"id": 3, "tag": "DV1", "numero": 3, "circuits": ["U13"]},
    ],
    "circuits": ["U11", "U13"],
    "plan": {"murs": [{"zone": "Z", "profil": "vertical"},
                      {"zone": "D", "profil": "toit"}]},
}


@pytest.fixture()
def simulation():
    sim = moteur.Simulation()
    sim.catalogue = moteur.Catalogue(CATALOGUE)
    sim.reglages = moteur.Reglages(p_doublon=0, p_inconnu=0, p_hors_circuit=0,
                                   p_coupure=0)
    return sim


def test_les_zones_viennent_de_la_premiere_lettre_du_tag(simulation):
    assert simulation.catalogue.zones == {"Z": ["ZJ1", "ZJ2"], "D": ["DV1"]}
    assert simulation.catalogue.profil_de_zone["D"] == "toit"


def test_un_juge_ne_scanne_que_les_blocs_de_sa_zone(simulation):
    juge = moteur.Juge(1, "D", simulation.catalogue.zones["D"], simulation)
    for _ in range(30):
        item = simulation.tirer_une_reussite(juge)
        assert item["bloc"] == "DV1"


def test_sans_aleas_le_dossard_est_toujours_dans_le_circuit_du_bloc(simulation):
    juge = moteur.Juge(1, "Z", simulation.catalogue.zones["Z"], simulation)
    for _ in range(40):
        item = simulation.tirer_une_reussite(juge)
        assert "hors_circuit" not in item
        assert simulation.catalogue.dans_le_circuit(
            int(item["bib"]), item["bloc"]) is not False


def test_un_dossard_inconnu_sort_du_catalogue(simulation):
    simulation.reglages = moteur.Reglages(p_inconnu=100, p_doublon=0,
                                          p_hors_circuit=0, p_coupure=0)
    juge = moteur.Juge(1, "Z", simulation.catalogue.zones["Z"], simulation)
    connus = set(simulation.catalogue.nom_du_dossard)
    for _ in range(20):
        assert int(simulation.tirer_une_reussite(juge)["bib"]) not in connus


def test_hors_circuit_n_est_posé_que_s_il_l_est_vraiment(simulation):
    simulation.reglages = moteur.Reglages(p_hors_circuit=100, p_inconnu=0,
                                          p_doublon=0, p_coupure=0)
    juge = moteur.Juge(1, "Z", simulation.catalogue.zones["Z"], simulation)
    for _ in range(20):
        item = simulation.tirer_une_reussite(juge)
        if item.get("hors_circuit"):
            assert simulation.catalogue.dans_le_circuit(
                int(item["bib"]), item["bloc"]) is False


def test_ce_qui_part_sur_le_reseau_n_a_que_les_champs_du_contrat(simulation):
    juge = moteur.Juge(1, "Z", simulation.catalogue.zones["Z"], simulation)
    item = simulation.tirer_une_reussite(juge)
    item["interne"] = "ne doit pas partir"
    assert set(moteur._sans_extra(item)) <= {"ref", "bib", "bloc", "at", "hors_circuit"}
    assert {"ref", "bib", "bloc", "at"} <= set(moteur._sans_extra(item))


# ── L'invariant de la file ─────────────────────────────────────────────────

class ApiMuette:
    """Une API qui ne statue que sur ce qu'on lui dit de statuer."""

    def __init__(self, resultats=None, ok=True):
        self.resultats = resultats
        self.ok = ok
        self.envois = []

    def envoyer_lot(self, reussites, appareil=None):
        self.envois.append((reussites, appareil))
        if not self.ok:
            return {"ok": False, "code": 0, "latence": 0.01, "acquittees": set(),
                    "refusees": [], "message": "serveur injoignable"}
        acquittees, refusees, deja = set(), [], 0
        for r in reussites:
            etat = (self.resultats or {}).get(r["ref"], "enregistree")
            if etat in ("enregistree", "deja_connue"):
                acquittees.add(r["ref"])
                deja += etat == "deja_connue"
            elif etat == "refusee":
                acquittees.add(r["ref"])
                refusees.append({"ref": r["ref"], "message": "Dossard inconnu"})
        return {"ok": True, "code": 200, "latence": 0.01, "acquittees": acquittees,
                "refusees": refusees, "deja_connues": deja, "catalogue_version": 7}


def _juge_charge(simulation, combien=3):
    juge = moteur.Juge(1, "Z", simulation.catalogue.zones["Z"], simulation)
    for _ in range(combien):
        juge.file.append(simulation.tirer_une_reussite(juge))
    return juge


def test_un_envoi_qui_echoue_ne_vide_rien(simulation):
    simulation.api = ApiMuette(ok=False)
    juge = _juge_charge(simulation)
    juge.tenter()
    assert len(juge.file) == 3
    assert juge.echecs == 1


def test_une_reponse_partielle_garde_ce_sur_quoi_le_serveur_n_a_rien_dit(simulation):
    juge = _juge_charge(simulation)
    refs = [e["ref"] for e in juge.file]
    # Le serveur ne statue que sur la première : les deux autres restent.
    simulation.api = ApiMuette({refs[0]: "enregistree",
                                refs[1]: "inconnu", refs[2]: "inconnu"})
    juge.tenter()
    assert [e["ref"] for e in juge.file] == refs[1:]


def test_une_refusee_est_mise_de_cote_et_quitte_la_file(simulation):
    juge = _juge_charge(simulation)
    refs = [e["ref"] for e in juge.file]
    simulation.api = ApiMuette({refs[0]: "refusee"})
    juge.tenter()
    assert juge.file == []
    assert [r["ref"] for r in juge.refusees] == [refs[0]]
    assert juge.refusees[0]["motif"] == "Dossard inconnu"
    assert juge.nb_refusees == 1


def test_a_blanc_ne_touche_pas_au_reseau(simulation):
    simulation.api = ApiMuette()
    simulation.reglages.a_blanc = True
    juge = _juge_charge(simulation)
    juge.tenter()
    assert simulation.api.envois == []
    assert juge.file == []


def test_l_appareil_identifie_un_poste(simulation):
    simulation.api = ApiMuette()
    juge = _juge_charge(simulation, 1)
    juge.tenter()
    _, appareil = simulation.api.envois[0]
    assert appareil["nom"] == "Poste Z1"
    assert appareil["id"].startswith("sim-")


# ── Le lien juge remplace l'adresse et la clé ──────────────────────────────

@pytest.mark.parametrize("serveur, cle, attendu", [
    ("https://exemple.fr", "abc", ("https://exemple.fr", "abc")),
    ("exemple.fr", "abc", ("https://exemple.fr", "abc")),
    ("https://exemple.fr/", "abc", ("https://exemple.fr", "abc")),
    ("", "https://exemple.fr/juge?j=secret", ("https://exemple.fr", "secret")),
    ("https://exemple.fr/juge?j=secret", "", ("https://exemple.fr", "secret")),
])
def test_demeler(serveur, cle, attendu):
    assert moteur._demeler(serveur, cle) == attendu


# ── Ce qui est retenu d'une session à l'autre ──────────────────────────────

@pytest.fixture()
def memoire_isolee(tmp_path, monkeypatch):
    """La mémoire dans un dossier jetable : jamais celle de la machine."""
    from tools.simulateur import memoire
    monkeypatch.setattr(memoire, "DOSSIER", tmp_path / "config")
    monkeypatch.setattr(memoire, "CHEMIN", tmp_path / "config" / "sim.json")
    return memoire


def test_rien_de_retenu_au_depart(memoire_isolee):
    assert memoire_isolee.lire() == {}


def test_ce_qui_est_ecrit_se_relit(memoire_isolee):
    memoire_isolee.ecrire(serveur="https://exemple.fr", cle="secrete")
    assert memoire_isolee.lire() == {"serveur": "https://exemple.fr", "cle": "secrete"}


def test_ecrire_ne_touche_pas_aux_autres_champs(memoire_isolee):
    memoire_isolee.ecrire(serveur="https://exemple.fr", cle="secrete")
    memoire_isolee.ecrire(reglages={"juges": 7})
    retenu = memoire_isolee.lire()
    assert retenu["cle"] == "secrete"
    assert retenu["reglages"] == {"juges": 7}


def test_un_champ_absent_n_efface_rien(memoire_isolee):
    memoire_isolee.ecrire(cle="secrete")
    memoire_isolee.ecrire(cle=None, serveur="https://exemple.fr")
    assert memoire_isolee.lire()["cle"] == "secrete"


def test_le_fichier_n_est_lisible_que_par_son_proprietaire(memoire_isolee):
    """Il contient une clé d'API : sur un Mac partagé, ça compte."""
    memoire_isolee.ecrire(cle="secrete")
    assert oct(memoire_isolee.CHEMIN.stat().st_mode)[-3:] == "600"
    assert oct(memoire_isolee.DOSSIER.stat().st_mode)[-3:] == "700"


def test_un_fichier_abime_coute_une_ressaisie_pas_un_plantage(memoire_isolee):
    memoire_isolee.DOSSIER.mkdir(parents=True)
    memoire_isolee.CHEMIN.write_text("{ ceci n'est pas du JSON")
    assert memoire_isolee.lire() == {}


def test_la_memoire_vit_hors_du_depot():
    """La seule garantie qui tienne : git ne peut pas atteindre le fichier.

    Une ligne de `.gitignore` se supprime, se contourne par `git add -f`, et les
    deux dépôts sont PUBLICS. Hors du dépôt, il n'y a plus de geste à ne pas
    faire.
    """
    from tools.simulateur import memoire as vraie
    assert RACINE not in vraie.CHEMIN.parents
    assert vraie.CHEMIN.is_relative_to(Path.home())


def test_oublier_supprime_tout(memoire_isolee):
    memoire_isolee.ecrire(cle="secrete")
    memoire_isolee.oublier()
    assert not memoire_isolee.CHEMIN.exists()
    memoire_isolee.oublier()          # deux fois de suite ne lève pas


# ── La version du serveur ──────────────────────────────────────────────────

class ApiSonde(moteur.Api):
    def __init__(self, reponse, code=200):
        super().__init__("http://exemple", "cle")
        self._reponse, self._code = reponse, code

    def _appel(self, chemin, corps=None, methode="POST", entetes_sup=None):
        return self._code, self._reponse, 0.01


def test_la_version_du_serveur_est_lue_sur_la_sonde():
    api = ApiSonde({"status": "ok", "version": "0.17.0"})
    assert api.sante() == {"version": "0.17.0", "statut": "ok", "code": 200}


def test_une_sonde_degradee_donne_quand_meme_la_version():
    """503 est justement le cas où on veut voir la version."""
    api = ApiSonde({"status": "degraded", "version": "0.17.0"}, code=503)
    assert api.sante()["version"] == "0.17.0"
    assert api.sante()["statut"] == "degraded"


def test_une_sonde_illisible_ne_leve_pas():
    assert moteur.Api("http://exemple").sante() == {}
