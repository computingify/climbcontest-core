"""La cohérence des specs 025, 026 et 028/029 — là où elles se touchent.

Chacune des trois a ses propres tests, et ils passaient tous **branche par
branche** avant le merge. Ce fichier ne les rejoue pas : il tient les
**coutures**, c'est-à-dire ce qu'aucune des trois ne possède seule.

| Couture | Qui écrit | Qui lit |
| --- | --- | --- |
| la cascade réglée dans la console | spec 025 | la fiche du parent (026) |
| le compte de blocs | spec 025 | la ligne du classement **et** la fiche (026) |
| le plan du mur | la console (029) | le juge, le parent (026), le dossard (028) |

Elles ont été écrites en parallèle, dans trois sessions, et se sont rencontrées
pour la première fois au merge du 02/09/2026. Trois défauts y vivaient, dont
aucun n'était visible depuis une seule branche : deux fonctions du même nom
fusionnées sans conflit, une zone d'adresse jamais confrontée au plan, et une
branche empilée sur une version périmée d'une autre. Ce fichier existe pour que
la quatrième fois soit rouge tout de suite.

⚠️ **Le scénario est celui du samedi matin**, pas une liste de cas : un
organisateur règle la cascade et redessine le mur depuis la console, un parent
ouvre la page sur son téléphone. Ce que le parent voit doit être ce que
l'organisateur a réglé — c'est la seule question que ce fichier pose.

⚠️ **Aucune assertion ne fige un score.** La cascade rend le dénominateur
`1000/n` solidaire entre catégories : en éteindre une déplace le score de
grimpeurs qui n'en font pas partie. Un test qui comparerait des classements
avant et après un réglage échouerait sur ce déplacement, qui n'est pas un
défaut. Les assertions ici sont des **invariants** — deux chemins vers la même
vérité doivent s'accorder — et ils tiennent quel que soit le dénominateur.
"""

from datetime import date
from pathlib import Path

import os
import shutil
import tempfile

import pytest

from climbcontest import comptes
from climbcontest.extensions import db
from climbcontest.models import (
    Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant, Success)

RACINE = Path(__file__).resolve().parent.parent
MDP = "un-mot-de-passe-assez-long"

# Le circuit : les six couleurs, réparties sur quatre zones du VRAI plan. Les
# zones comptent — la fiche affiche « Z » puis « J1 », et deux blocs de même
# numéro dans deux zones ne se distinguent que par elle (spec 026 F2).
CIRCUIT = [
    ("ZJ1", "Z", "Jaune"), ("ZJ2", "Z", "Jaune"),
    ("DV3", "D", "Vert"), ("DV4", "D", "Vert"),
    ("DB5", "D", "Bleu"), ("DB6", "D", "Bleu"),
    ("MM7", "M", "Mauve"), ("MM8", "M", "Mauve"),
    ("MR9", "M", "Rouge"), ("MR10", "M", "Rouge"),
    ("AN11", "A", "Noir"), ("AN12", "A", "Noir"),
]
# Les deux couleurs les plus dures, ENTIÈREMENT réussies. C'est exactement la
# condition de la règle du classeur (deux couleurs pleines plus dures), et donc
# la seule façon de voir la cascade faire quelque chose.
REUSSIS = {"MR9", "MR10", "AN11", "AN12"}


@pytest.fixture()
def salle(app):
    """Deux grimpeurs RIGOUREUSEMENT identiques, dans deux catégories.

    Même circuit, mêmes réussites, même tout — sauf la catégorie. C'est un
    montage d'expérience : toute différence entre leurs deux fiches ne peut
    venir que de l'interrupteur par catégorie de la spec 025. Sans ce
    jumelage, un écart se confondrait avec un écart de données.
    """
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comp = Competition(nom="Coherence 2026", date=date(2026, 11, 15),
                       statut=EN_COURS, active=True, spreadsheet_id="fictif")
    db.session.add(comp)
    db.session.flush()

    circuit = Circuit(competition_id=comp.id, nom="U13")
    db.session.add(circuit)
    db.session.flush()

    blocs = {}
    for i, (tag, zone, couleur) in enumerate(CIRCUIT, 1):
        b = Bloc(competition_id=comp.id, tag=tag, numero=i, zone=zone,
                 couleur=couleur)
        db.session.add(b)
        db.session.flush()
        db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=circuit.id))
        blocs[tag] = b

    grimpeurs = {}
    for nom, categorie in [("Lea", "U13 F"), ("Tom", "U13 H")]:
        p = Participant(competition_id=comp.id, nom=nom, prenom="X",
                        club="Les Lezards", categorie=categorie,
                        dossard=len(grimpeurs) + 1, present=True)
        db.session.add(p)
        db.session.flush()
        for tag in REUSSIS:
            db.session.add(Success(participant_id=p.id, bloc_id=blocs[tag].id))
        grimpeurs[categorie] = p

    db.session.commit()
    return {"competition": comp, "blocs": blocs, "grimpeurs": grimpeurs}


@pytest.fixture()
def console(client, salle):
    """Un organisateur connecté — ADMIN, parce que la cascade l'exige."""
    comptes.creer("chef", MDP, [comptes.ADMIN])
    r = client.post("/admin/connexion",
                    json={"identifiant": "chef", "mot_de_passe": MDP})
    assert r.status_code == 200, r.get_json()
    return client


def fiche_de(client, participant):
    r = client.get(f"/api/public/grimpeur/{participant.id}")
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def etats(fiche):
    """{tag: etat} — la fiche vue à plat, comme un doigt la lit."""
    return {b["zone"] + b["numero"]: b["etat"]
            for g in fiche["groupes"] for b in g["blocs"]}


# --- La couture 1 : un seul accesseur pour deux specs -----------------------

class TestLeContratDeLAccesseurUnique:
    """`blocs_du_grimpeur` sert DEUX specs, qui en attendent des choses
    différentes. La 026 a besoin de `hors_circuit` — « le moteur continue de
    les servir » (spec 026 § 3) — et la 025 de la résolution **par catégorie**.

    Qu'il n'y en ait qu'une seule définition est vérifié par
    `tests/test_suivi.py::TestUnSeulAccesseur`, écrit après que la fusion en
    eut produit deux. Ici on vérifie l'autre moitié : que la survivante tienne
    les promesses des deux specs, et pas seulement celles de la dernière
    écrite.
    """

    def test_il_rend_bien_les_trois_ensembles(self, salle):
        from climbcontest.classement_service import blocs_du_grimpeur

        rendu = blocs_du_grimpeur(salle["competition"], salle["grimpeurs"]["U13 F"])
        assert set(rendu) == {"grimpes", "credites", "hors_circuit"}, (
            "les cles rendues sont " + repr(sorted(rendu))
            + " : une spec a perdu la sienne")


# --- La couture 2 : la cascade réglée dans la console se voit sur la fiche ---

class TestLaCascadeDeLaConsoleArriveSurLeTelephone:
    """Spec 025 (le réglage) × spec 026 (ce que le parent voit).

    La 025 range la règle dans `competition.options` et la résout **par
    catégorie**. La 026 peint les blocs crédités en hachures. Entre les deux,
    personne ne vérifie que le réglage traverse.
    """

    def test_sans_cascade_aucun_bloc_n_est_credite(self, client, salle):
        """Le défaut, et le réglage réel de novembre 2025."""
        fiche = fiche_de(client, salle["grimpeurs"]["U13 F"])
        assert fiche["credites"] == 0
        assert "credite" not in set(etats(fiche).values()), (
            "un bloc est hachure alors qu'aucune cascade n'est reglee")

    def test_la_cascade_reglee_credite_les_couleurs_plus_faciles(
            self, console, salle):
        """« Comme le classeur » : deux couleurs pleines plus dures valident.

        Rouge et Noir sont pleines. Jaune, Vert, Bleu et Mauve ont chacune au
        moins deux couleurs plus dures entièrement réussies : leurs huit blocs
        sont crédités. Rouge ne l'est pas — une seule couleur est plus dure
        qu'elle — et c'est conforme au classeur, pas un oubli.
        """
        from climbcontest.cascade import regle_du_classeur

        regles = [{"parmi": sorted(p.parmi), "seuil": p.seuil,
                   "cibles": sorted(p.cibles)} for p in regle_du_classeur()]
        r = console.post("/admin/competition/cascade",
                         json={"actif": True, "regles": regles,
                               "categories_eteintes": []})
        assert r.status_code == 200, r.get_json()

        fiche = fiche_de(console, salle["grimpeurs"]["U13 F"])
        vus = etats(fiche)
        assert fiche["grimpes"] == 4
        assert fiche["credites"] == 8, (
            "la cascade reglee dans la console ne se voit pas sur la fiche")
        assert vus["ZJ1"] == "credite"
        assert vus["MR9"] == "grimpe"
        assert vus["MR10"] == "grimpe"
        # Rouge non validable, Noir non plus : ils sont grimpes, pas credites.
        assert sum(1 for e in vus.values() if e == "credite") == 8

    def test_l_interrupteur_par_categorie_separe_deux_grimpeurs_jumeaux(
            self, console, salle):
        """⚠️ **La couture la plus fine des trois specs.**

        La 025 M3 dit que l'interrupteur du classeur est **par catégorie**.
        La 026 sert la fiche **par grimpeur**. Si la résolution par catégorie
        se perdait entre les deux, la cascade s'appliquerait aux huit
        catégories — exactement le défaut que la spec 025 existe pour corriger,
        et il serait invisible tant qu'on ne regarde qu'un grimpeur.

        Les deux grimpeurs ici ont les mêmes réussites au bloc près. Seule la
        catégorie les distingue.
        """
        from climbcontest.cascade import regle_du_classeur

        regles = [{"parmi": sorted(p.parmi), "seuil": p.seuil,
                   "cibles": sorted(p.cibles)} for p in regle_du_classeur()]
        r = console.post("/admin/competition/cascade",
                         json={"actif": True, "regles": regles,
                               "categories_eteintes": ["U13 H"]})
        assert r.status_code == 200, r.get_json()

        allumee = fiche_de(console, salle["grimpeurs"]["U13 F"])
        eteinte = fiche_de(console, salle["grimpeurs"]["U13 H"])

        assert allumee["credites"] == 8
        assert eteinte["credites"] == 0, (
            "la categorie eteinte recoit quand meme la cascade : la resolution "
            "par categorie ne traverse pas jusqu'a la fiche")
        # Et le reste de la fiche est bien identique : c'est ce qui prouve que
        # l'ecart vient de l'interrupteur et de rien d'autre.
        assert allumee["total"] == eteinte["total"] == len(CIRCUIT)
        assert allumee["grimpes"] == eteinte["grimpes"] == 4


class TestLeClassementEtLaFicheDisentLeMemeNombre:
    """Spec 025 M4 × spec 026 A17.

    La page de résultats affiche « 12 blocs » à côté du score ; la fiche montre
    douze cases. Ce sont deux chemins différents vers le même nombre — le
    classement passe par `classements()`, la fiche par `blocs_du_grimpeur()`.
    Deux chemins vers une même vérité finissent toujours par diverger, et ici
    le parent voit les deux **sur le même écran**.
    """

    @pytest.mark.parametrize("eteintes", [[], ["U13 H"]])
    def test_le_compte_de_la_ligne_est_celui_de_la_fiche(
            self, console, salle, eteintes):
        from climbcontest.cascade import regle_du_classeur

        regles = [{"parmi": sorted(p.parmi), "seuil": p.seuil,
                   "cibles": sorted(p.cibles)} for p in regle_du_classeur()]
        console.post("/admin/competition/cascade",
                     json={"actif": True, "regles": regles,
                           "categories_eteintes": eteintes})

        charge = console.get("/api/public/classement").get_json()
        lignes = {l["participant_id"]: l
                  for c in charge["classements"] for l in c["lignes"]
                  if l.get("participant_id")}

        for participant in salle["grimpeurs"].values():
            fiche = fiche_de(console, participant)
            ligne = lignes[participant.id]
            assert ligne["blocs"] == fiche["grimpes"] + fiche["credites"], (
                "la ligne du classement dit " + str(ligne["blocs"])
                + " blocs et la fiche en peint "
                + str(fiche["grimpes"] + fiche["credites"])
                + " pour " + participant.nom)


# --- La couture 3 : le plan dessiné dans la console -------------------------

def plan_a_trois_zones():
    """Un relevé volontairement PAUVRE : trois zones, la quatrième retirée.

    La zone « A » disparaît alors que deux blocs du circuit y vivent. C'est le
    cas A14 de la spec 026 — un bloc dont la zone est absente du plan doit
    rester inerte, pas faire tomber l'écran — et il ne peut se produire QUE si
    la console peut redessiner le plan, donc que depuis la spec 029.
    """
    return {
        "vue": [100, 100],
        "murs": [
            {"zone": "Z", "profil": "dalle",
             "points": [[0, 0], [40, 0], [40, 40], [0, 40]]},
            {"zone": "D", "profil": "devers",
             "points": [[50, 0], [100, 0], [100, 40]]},
            {"zone": "M", "profil": "toit",
             "points": [[0, 50], [40, 50], [40, 100], [0, 100]]},
        ],
        "reperes": [{"texte": "Escalier", "point": [70, 90]}],
        "contour": None,
    }


def zones_du_plan_servi(client):
    """Les zones que la PAGE reçoit — celles que le doigt du parent touchera."""
    from climbcontest.suivi import plan_public
    return {m["zone"] for m in plan_public()["murs"]}


class TestLePlanDessineDansLaConsoleArriveSurLeTelephone:
    """Spec 029 (dessiner) × spec 028 (le plan) × spec 026 (l'écran du parent).

    C'est la chaîne complète : la console écrit en base, `plan_courant()` la
    lit, `plan_pour()` la met en forme, `plan_public()` l'estampille, la page
    la dessine. Cinq maillons, trois specs, aucun test de bout en bout.
    """

    def test_avant_tout_dessin_c_est_le_plan_d_usine(self, client, salle):
        from climbcontest.fiches import PLAN
        attendu = {m["zone"] for m in PLAN["murs"] if m["zone"]}
        assert zones_du_plan_servi(client) == attendu

    def test_le_plan_enregistre_remplace_le_plan_d_usine(self, console, salle):
        r = console.post("/admin/plan", json=plan_a_trois_zones())
        assert r.status_code == 200, r.get_json()
        assert r.get_json()["zones"] == 3

        assert zones_du_plan_servi(console) == {"Z", "D", "M"}, (
            "le plan dessine dans la console n'atteint pas la page publique")

    def test_la_page_publique_porte_le_nouveau_plan(self, console, salle):
        """Le plan voyage dans le HTML de « / », pas dans une requête à part.

        C'est ce qui permet à la page de dessiner le mur sans aller-retour —
        et c'est aussi ce qui fait qu'un parent déjà sur la page garde
        l'ancien plan jusqu'à ce qu'il recharge. Ce test vérifie le
        chargement, qui est le seul moment où le plan entre.
        """
        console.post("/admin/plan", json=plan_a_trois_zones())
        page = console.get("/").get_data(as_text=True)
        assert '"Z"' in page and '"D"' in page and '"M"' in page
        assert '"format": "polygones/1"' in page or '"format":"polygones/1"' in page

    def test_l_estampille_ne_bouge_pas_quand_le_plan_change(self, console, salle):
        """Spec 026 F6 : la page refuse un format qu'elle ne connaît pas.

        Un plan **dessiné** n'est pas un plan d'un autre **format** : si
        l'enregistrement changeait l'estampille, la page cesserait de dessiner
        le mur, et le parent ne verrait plus rien sans qu'aucune erreur ne le
        dise.
        """
        from climbcontest.suivi import FORMAT_PLAN, plan_public

        avant = plan_public()["format"]
        console.post("/admin/plan", json=plan_a_trois_zones())
        assert plan_public()["format"] == avant == FORMAT_PLAN

    def test_un_bloc_dont_la_zone_a_disparu_reste_dans_la_fiche(
            self, console, salle):
        """Spec 026 A14. La fiche liste le circuit ENTIER — c'est ce que le
        grimpeur doit grimper, le plan n'a pas à en retirer. C'est la page qui
        rendra la case inerte, faute de `data-zone` correspondante."""
        console.post("/admin/plan", json=plan_a_trois_zones())

        fiche = fiche_de(console, salle["grimpeurs"]["U13 F"])
        assert fiche["total"] == len(CIRCUIT)
        vus = etats(fiche)
        assert "AN11" in vus and "AN12" in vus, (
            "les blocs de la zone retiree ont disparu de la fiche : le plan "
            "commande l'affichage du circuit, ce qu'il ne doit jamais faire")
        assert "A" not in zones_du_plan_servi(console)

    def test_effacer_ramene_le_plan_d_usine(self, console, salle):
        """La sortie de secours de la spec 029 F4, vue du téléphone."""
        from climbcontest.fiches import PLAN

        console.post("/admin/plan", json=plan_a_trois_zones())
        assert zones_du_plan_servi(console) == {"Z", "D", "M"}

        r = console.delete("/admin/plan")
        assert r.status_code == 200, r.get_json()
        attendu = {m["zone"] for m in PLAN["murs"] if m["zone"]}
        assert zones_du_plan_servi(console) == attendu


class TestLePapierEtLEcranMontrentLeMemeMur:
    """Spec 028 (le dossard, en noir et blanc) × spec 026 (l'écran, en couleur).

    Le grimpeur a la fiche papier dans la poche et son parent a le téléphone
    dans la main. S'ils ne montraient pas la même salle, le second enverrait
    le premier au mauvais mur — et c'est précisément ce qui arriverait si l'un
    des deux lisait la constante pendant que l'autre lit la base.
    """

    def test_les_memes_zones_des_deux_cotes(self, console, salle):
        import re

        console.post("/admin/plan", json=plan_a_trois_zones())

        planche = console.get("/admin/dossards?dossard=1").get_data(as_text=True)
        assert planche, "la planche a imprimer est vide"
        # Le SVG du dossard porte ses zones en `data-zone`, comme l'ecran.
        papier = set(re.findall(r'data-zone="([^"]+)"', planche))
        ecran = zones_du_plan_servi(console)
        assert papier == ecran, (
            "le dossard imprime montre " + repr(sorted(papier))
            + " et le telephone " + repr(sorted(ecran)))

    def test_le_dossard_n_utilise_aucune_couleur(self, console, salle):
        """Spec 028 A9. La 026 a ajouté une palette froid → chaud pour
        l'écran ; elle ne doit pas avoir fui vers le papier, qui s'imprime à
        l'encre noire."""
        import re

        planche = console.get("/admin/dossards?dossard=1").get_data(as_text=True)
        # On ne regarde que le SVG du plan : le reste de la fiche a le droit
        # d'avoir des couleurs de couleur de bloc (« Jaune », « Vert »...).
        svgs = re.findall(r"<svg[^>]*class=\"[^\"]*plan[^\"]*\".*?</svg>",
                          planche, re.S)
        assert svgs, "aucun SVG de plan dans la planche"
        for svg in svgs:
            teintes = re.findall(r"#[0-9a-fA-F]{3,6}|rgb\(|hsl\(", svg)
            vives = [t for t in teintes
                     if t.startswith("rgb") or t.startswith("hsl")
                     or not _est_gris(t)]
            assert not vives, "le plan du dossard porte des couleurs : " + repr(vives)


def _est_gris(hexa: str) -> bool:
    """`#333`, `#f0f0f0`, `#000` — un gris a ses trois composantes égales."""
    v = hexa.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        return False
    return v[0:2].lower() == v[2:4].lower() == v[4:6].lower()


class TestUnSeulMurPourTroisConsommateurs:
    """Le plan est GLOBAL, et il part vers trois écrans par trois chemins.

    | Qui | Par où | Fraîcheur |
    | --- | --- | --- |
    | le juge, sur son téléphone | `GET /catalog`, champ `plan` | versionnée (`catalogue_version` + ETag) |
    | le parent, sur son téléphone | le HTML de `/`, en ligne | au rechargement |
    | le grimpeur, sur son dossard | `GET /admin/dossards` | à l'impression |

    Trois mécanismes de fraîcheur différents pour **une seule** donnée. Chacun
    se tient — ce qui ne se tient pas tout seul, c'est qu'ils montrent le même
    mur au même instant, et personne ne le vérifie : la spec 029 sert le
    catalogue, la 028 le dossard, la 026 l'écran du parent.
    """

    def zones(self, texte_ou_murs):
        import re
        if isinstance(texte_ou_murs, str):
            return set(re.findall(r'data-zone="([^"]+)"', texte_ou_murs))
        return {m["zone"] for m in texte_ou_murs if m.get("zone")}

    def test_les_trois_montrent_le_meme_mur_apres_un_dessin(self, console, salle):
        from climbcontest.suivi import plan_public

        r = console.post("/admin/plan", json=plan_a_trois_zones())
        assert r.status_code == 200, r.get_json()

        juge = self.zones(console.get("/api/v2/catalog").get_json()["plan"]["murs"])
        parent = self.zones(plan_public()["murs"])
        dossard = self.zones(
            console.get("/admin/dossards?dossard=1").get_data(as_text=True))

        assert juge == parent == dossard == {"Z", "D", "M"}, (
            "les trois consommateurs du plan divergent -- juge " + repr(sorted(juge))
            + ", parent " + repr(sorted(parent))
            + ", dossard " + repr(sorted(dossard)))

    def test_le_juge_apprend_que_le_mur_a_change(self, console, salle):
        """La version du catalogue est ce qui EMPÊCHE un juge de garder un mur
        périmé. Si elle ne bougeait pas, son `304` lui servirait l'ancien plan
        sans qu'aucun des deux ne puisse le savoir."""
        avant = console.get("/api/v2/catalog").get_json()["version"]
        console.post("/admin/plan", json=plan_a_trois_zones())
        apres = console.get("/api/v2/catalog").get_json()["version"]

        assert apres != avant, (
            "enregistrer un plan ne change pas catalogue_version : le telephone "
            "du juge gardera l'ancien mur sur un 304, sans moyen de le savoir")

    def test_effacer_le_plan_previent_aussi_le_juge(self, console, salle):
        """La sortie de secours de la spec 029 F4 doit être aussi visible que
        l'enregistrement : c'est le geste qu'on fait quand un dessin part de
        travers EN COMPÉTITION, donc celui où la fraîcheur compte le plus."""
        console.post("/admin/plan", json=plan_a_trois_zones())
        avant = console.get("/api/v2/catalog").get_json()["version"]

        console.delete("/admin/plan")
        catalogue = console.get("/api/v2/catalog").get_json()

        assert catalogue["version"] != avant, (
            "revenir au plan d'usine ne previent pas le telephone du juge")
        from climbcontest.fiches import PLAN
        assert self.zones(catalogue["plan"]["murs"]) == self.zones(PLAN["murs"])


# --- La couture 4 : une zone que le plan ne connaît plus ---------------------
#
# ⚠️ Ce cas n'existe QUE depuis la spec 029. Tant que `PLAN` était une
# constante, une zone nommée dans une adresse était forcément dessinable ; la
# console peut maintenant la faire disparaître entre le moment où le lien est
# partagé et celui où il est ouvert.

from tests.navigateur import (                                     # noqa: E402
    CHROME, page_harnais, piloter, servir)

SONDE_ZONE = """
    await attendre("mur", () => $(".sf-feuille"));
    // ⚠️ `svg.plan >` : ON COMPTE LES PANS. Depuis la spec 036, chaque zone a
    // deux groupes -- son pan, et le compteur, qui vit une couche plus haut
    // pour passer devant le cadre. Sans le `>`, ce test compterait deux fois
    // chaque zone et dirait « six » pour un plan qui en porte trois.
    note("zonesDessinees", $$(".sf-feuille svg.plan > g[data-zone]").length);
    note("visee", $$(".sf-feuille g[data-zone].visee").length);
    const titre = $(".sf-mur-tete b");
    note("titre", titre ? titre.textContent.trim() : "(aucun)");
    note("diese", vue().location.hash || "(vide)");
"""


@pytest.mark.skipif(CHROME is None,
                    reason="aucun navigateur : ce test se saute, il n'echoue pas")
class TestUneZoneQueLePlanNeConnaitPlus:
    """Spec 029 (le plan bouge) × spec 026 F6 (la page refuse ce qu'elle ne sait
    pas dessiner).

    La 026 valide la zone d'un **bloc** contre le plan — `ZONES_DU_PLAN.has()`
    rend la case inerte, c'est son critère A14. La zone qui vient de
    **l'adresse** demande le même contrôle, et pour une raison plus forte : un
    lien se partage le matin et s'ouvre l'après-midi, sur un mur que la console
    a redessiné entre-temps.
    """

    def test_le_mur_ne_titre_pas_une_zone_qu_il_ne_dessine_pas(self):
        """La zone A a disparu du plan. Le mur doit se dessiner quand même, ne
        viser personne, et ne pas annoncer un mur qu'il ne montre pas."""
        from flask import request

        from climbcontest import creer_app, plan_du_mur
        from climbcontest.config import Config

        dossier = tempfile.mkdtemp(prefix="climbcontest-zone-")
        os.environ["CLIMBCONTEST_TEST"] = "1"

        class ConfigZone(Config):
            SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(dossier, "z.db")
            SHEETS_ACTIF = False
            API_KEY_STRICTE = False
            SESSION_COOKIE_SECURE = False

        app = creer_app(ConfigZone)
        verdict = {"texte": None}
        with app.app_context():
            db.create_all()
            cible = _semer_une_salle()
            plan_du_mur.ecrire(plan_a_trois_zones(), par="chef")

        @app.post("/__verdict")
        def poser():
            verdict["texte"] = request.get_data(as_text=True)
            return "", 204

        @app.get("/__harnais")
        def harnais():
            from flask import Response
            # `periode=0.3` : la page de resultats relit ses donnees toutes
            # les quinze secondes, et la fiche que cette sonde attend ne se
            # construit qu'une fois le classement arrive. Quand le premier
            # chargement perd la course -- ce qui n'arrive jamais sur le Mac et
            # tout le temps sur un runner charge -- il faut attendre le
            # battement suivant, parfois deux. Ce test coutait 29 s en CI pour
            # une seconde de travail, et c'est lui qui expirait a 120 s le
            # 02/09.
            return Response(
                page_harnais(f"/?periode=0.3#g={cible}&z=A", SONDE_ZONE),
                mimetype="text/html")

        url, arreter = servir(app)
        try:
            rendu = piloter(url + "/__harnais", verdict)
        finally:
            arreter()
            shutil.rmtree(dossier, ignore_errors=True)

        assert rendu.startswith("OK "), rendu
        mesures = dict(m.split("=", 1) for m in rendu[3:].split(" ") if "=" in m)

        # Le plan redessine est bien celui qu'on voit : trois zones, pas dix-sept.
        assert mesures["zonesDessinees"] == "3"
        # Aucune zone visee, et c'est normal : il n'y a pas de A a viser.
        assert mesures["visee"] == "0"
        # Le panneau ne nomme pas un mur que le dessin ne porte pas, et
        # l'adresse est nettoyee de sa zone -- comme elle l'est deja d'un
        # grimpeur inconnu (A11).
        assert mesures["titre"] != "Zone_A", (
            "le panneau titre « Zone A » alors qu'aucune zone A n'est dessinee")
        assert "z=A" not in mesures["diese"], (
            "l'adresse garde une zone que le plan ne connait pas : " + mesures["diese"])


def _semer_une_salle() -> int:
    """La même salle que la fixture `salle`, hors contexte de test Flask.

    Le serveur du navigateur tourne dans un autre fil : il lui faut une base
    sur FICHIER, donc une application a part, donc son propre semis.
    """
    comp = Competition(nom="Coherence", date=date(2026, 11, 15),
                       statut=EN_COURS, active=True, spreadsheet_id="fictif")
    db.session.add(comp)
    db.session.flush()
    circuit = Circuit(competition_id=comp.id, nom="U13")
    db.session.add(circuit)
    db.session.flush()

    blocs = {}
    for i, (tag, zone, couleur) in enumerate(CIRCUIT, 1):
        b = Bloc(competition_id=comp.id, tag=tag, numero=i, zone=zone,
                 couleur=couleur)
        db.session.add(b)
        db.session.flush()
        db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=circuit.id))
        blocs[tag] = b

    p = Participant(competition_id=comp.id, nom="Lea", prenom="X",
                    club="Les Lezards", categorie="U13 F", dossard=1,
                    present=True)
    db.session.add(p)
    db.session.flush()
    for tag in REUSSIS:
        db.session.add(Success(participant_id=p.id, bloc_id=blocs[tag].id))
    db.session.commit()
    return p.id
