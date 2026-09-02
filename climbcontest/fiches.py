"""Ce qu'on imprime : la fiche du grimpeur (spec 023), l'étiquette du bloc (024).

La bande de trois centimètres qu'on imprimait jusqu'ici portait un QR, un
numéro et un nom. Le classeur, lui, imprime une **fiche** (onglet `Fiches`), et
cette fiche porte ce qui manquait : **quels blocs comptent pour ce grimpeur**,
et **où ils sont dans la salle**. Sans ça, le seul papier qu'il a en main de la
journée ne lui dit rien de ce qu'il doit grimper.

**Aucun Flask ici**, comme dans `cycle.py` et `circuits.py` : ce module ne parle
qu'à la base, et tout se teste sans client HTTP.
"""

from collections import defaultdict

from . import qr
from .classement import COULEURS
from .extensions import db
from .models import Bloc, BlocCircuit, Circuit

# La taille du QR d'une ÉTIQUETTE, zone de silence comprise. Deux fois celui
# d'une fiche : il est collé au mur, souvent en hauteur, et scanné d'un bras
# tendu — pas tenu à trente centimètres comme une fiche.
COTE_QR_ETIQUETTE_MM = 45.0

# La taille du QR sur le papier, zone de silence comprise. 24 mm donnent
# 0,83 mm par module sur un dossard à quatre chiffres — plus du double du
# plancher de `qr.MODULE_MINI_MM`, et de quoi scanner à bout de bras.
COTE_QR_MM = 24.0


# Les six profils de mur, ORDONNÉS du moins au plus déversant. L'ordre EST
# l'information : la trame se densifie et le gris fonce à mesure qu'on descend
# la liste, ce qui donne une seule règle à apprendre — plus ça déverse, plus ça
# tranche sur le papier.
#
# ⚠️ La place d'`incline` a été tranchée par Adrien lui-même, en assignant les
# profils à ses murs : il l'a mis APRÈS `vertical`, donc du côté qui déverse.
# La question était réelle — « incliné » ne dit pas dans quel sens — et une
# session parallèle avait fait l'hypothèse inverse.
#
# ⚠️ Aucune COULEUR ici. Le dossard s'imprime à l'encre noire ; une teinte y
# serait perdue. Les gris et les trames, eux, survivent. Le rendu du même plan
# à l'écran est ailleurs (spec 026) et n'a pas cette contrainte.
PROFILS = (
    {"cle": "dalle",    "trame": "pois",   "pas": 4.6, "epaisseur": 0.45, "gris": "#EFECE6"},
    {"cle": "vertical", "trame": None,     "pas": 0.0, "epaisseur": 0.00, "gris": "#E2DED5"},
    {"cle": "incline",  "trame": "penche", "pas": 5.0, "epaisseur": 0.50, "gris": "#D4CEC2"},
    {"cle": "devers",   "trame": "penche", "pas": 3.2, "epaisseur": 0.55, "gris": "#C1BAAB"},
    {"cle": "surplomb", "trame": "penche", "pas": 2.1, "epaisseur": 0.60, "gris": "#A79E8C"},
    {"cle": "toit",     "trame": "croise", "pas": 2.6, "epaisseur": 0.60, "gris": "#8D8473"},
)
PAR_PROFIL = {p["cle"]: p for p in PROFILS}
PROFIL_PAR_DEFAUT = "vertical"

# La marge autour du dessin, en unités de vue.
#
# ⚠️ Sept des murs d'Annonay touchent le bord — L, M, N à gauche, X et Y en
# haut, E à droite. Sans marge, la moitié de leur trait sort du cadre. Elle se
# prend sur le `viewBox` et JAMAIS sur les coordonnées : décaler les points
# pour faire de la place, ce serait maquiller le relevé pour arranger un
# problème d'affichage.
MARGE_PLAN = 1.0

# La lettre d'une zone, en unités de vue.
#
# ⚠️ Mesuré dans le navigateur, halo compris — `getBBox()` ignore le contour,
# et mesurer sans lui donne « ça tient largement » là où la marge réelle est de
# 0,25 unité. À 9 unités fixes, aucune des 17 zones d'Annonay ne débordait :
# ça tenait par chance, pas par construction, et une zone à deux caractères
# crevait le plafond. D'où un calcul depuis la boîte du mur.
LETTRE_MAXI = 9.0
LETTRE_MINI = 3.5        # 1,06 mm sur la colonne de 37 mm : le plancher lisible

# ⚠️ La largeur d'une capitale, en fraction de sa taille. C'est la largeur du
# PIRE glyphe, pas la moyenne.
#
# La première version prenait 0,62 -- la moyenne d'une capitale condensée
# grasse. Mesuré au navigateur sur la boîte réelle d'un mur de quinze unités,
# avec la police effectivement servie et le halo compris : ONZE combinaisons de
# deux caractères sur trente-neuf débordaient, « NM » de 2,6 unités, soit
# 0,39 mm de chaque côté. « M », « N » et « W » crèvent la moyenne.
#
# Une moyenne ne borne rien. 0,85 borne. Le relevé d'Annonay n'a que des
# lettres seules et son rendu ne change pas d'un pixel -- le plafond de
# `LETTRE_MAXI` mord avant. Mais depuis la spec 029 le nom de zone est de la
# donnée saisie : « M2 » arrivera.
LARGEUR_CAPITALE = 0.85


# Le mur de bloc d'Annonay, relevé par Adrien le 02/09/2026 avec
# la planche de la console (`/admin/plan`, spec 029). C'est la salle, pas une
# donnée de compétition.
#
# ⚠️ Depuis la spec 029 ce n'est plus la SOURCE mais le DÉFAUT : voir
# `plan_courant()`. Ne plus la modifier à la main — on la dessine.
#
# Remplace la grille de 8×7 cases des specs 023-024, qui ne savait dire ni la
# forme de la salle, ni le profil d'un mur, ni les proportions.
PLAN = {
    "vue": (120, 150),
    "contour": None,
    "murs": (
        {"zone": "X", "profil": "vertical",
         "points": ((60, 0), (80, 0), (80, 15), (60, 15)), "etiquette": None},
        {"zone": "Y", "profil": "vertical",
         "points": ((80, 0), (100, 0), (100, 15), (80, 15)), "etiquette": None},
        {"zone": "D", "profil": "toit",
         "points": ((5, 15), (20, 15), (20, 45), (5, 45)), "etiquette": None},
        {"zone": "Z", "profil": "vertical",
         "points": ((100, 15), (115, 15), (115, 30), (100, 30)), "etiquette": None},
        {"zone": "C", "profil": "incline",
         "points": ((20, 45), (35, 45), (35, 60), (20, 60)), "etiquette": None},
        {"zone": "B", "profil": "devers",
         "points": ((35, 45), (50, 45), (50, 60), (35, 60)), "etiquette": None},
        {"zone": "A", "profil": "vertical",
         "points": ((50, 45), (70, 45), (70, 60), (50, 60)), "etiquette": None},
        {"zone": "L", "profil": "toit",
         "points": ((0, 75), (15, 75), (15, 100), (0, 100)), "etiquette": None},
        {"zone": "M", "profil": "dalle",
         "points": ((0, 100), (15, 100), (15, 115), (0, 115)), "etiquette": None},
        {"zone": "K", "profil": "surplomb",
         "points": ((15, 75), (30, 75), (30, 90), (15, 90)), "etiquette": None},
        {"zone": "J", "profil": "vertical",
         "points": ((30, 75), (45, 75), (45, 90), (30, 90)), "etiquette": None},
        {"zone": "I", "profil": "devers",
         "points": ((45, 75), (60, 75), (60, 90), (45, 90)), "etiquette": None},
        {"zone": "H", "profil": "incline",
         "points": ((60, 75), (75, 75), (75, 90), (60, 90)), "etiquette": None},
        {"zone": "G", "profil": "vertical",
         "points": ((75, 75), (90, 75), (90, 90), (75, 90)), "etiquette": None},
        {"zone": "F", "profil": "dalle",
         "points": ((90, 75), (105, 75), (105, 90), (90, 90)), "etiquette": None},
        {"zone": "N", "profil": "dalle",
         "points": ((0, 115), (15, 115), (15, 130), (0, 130)), "etiquette": None},
        {"zone": "E", "profil": "vertical",
         "points": ((105, 90), (120, 90), (120, 105), (105, 105)), "etiquette": None},
    ),
    "reperes": (
        {"texte": "Escalier", "point": (97, 52)},
        {"texte": "Haut", "point": (61, 111)},
        {"texte": "Bas", "point": (60, 30)},
    ),
}

# Déduit de PLAN, jamais recopié à la main : deux listes qui divergeraient
# feraient disparaître une zone du message « hors plan » sans rien casser
# visiblement.
# ⚠️ Les zones du plan D'USINE. Pour savoir ce qui est « hors plan » il faut
# celles du plan COURANT : voir `zones_du_plan()`. Cette constante reste pour
# les tests et pour le repli.
ZONES_DU_PLAN = frozenset(
    m["zone"] for m in PLAN["murs"] if m["zone"])


def zones_du_plan(plan: dict | None = None) -> frozenset[str]:
    """Les zones dessinées par le plan qui s'applique.

    Déduit du plan, jamais recopié : deux listes qui divergeraient feraient
    disparaître une zone du message « hors plan » sans rien casser visiblement.

    `plan` se passe quand l'appelant l'a déjà lu — c'est le cas de `construire`,
    qui rend jusqu'à cent vingt fiches et ne doit lire la base qu'une fois.
    """
    return frozenset(m["zone"] for m in (plan or plan_courant())["murs"] if m["zone"])


def _cadre(points) -> tuple[float, float, float, float]:
    """La boîte englobante d'un polygone : (x0, y0, x1, y1)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _centroide(points) -> tuple[float, float]:
    """Le centre de SURFACE du polygone, pas la moyenne de ses sommets.

    La moyenne des sommets tire la lettre vers les côtés les plus découpés :
    sur un triangle dont un bord porte trois points, elle sort du dessin. Le
    centroïde d'aire, lui, tombe où l'œil attend le centre.

    Le repli sur la moyenne ne sert qu'aux polygones dégénérés — trois points
    alignés, aire nulle — où la formule diviserait par zéro.
    """
    aire = cx = cy = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        f = x1 * y2 - x2 * y1
        aire += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    if abs(aire) < 1e-9:
        return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)
    return (cx / (3 * aire), cy / (3 * aire))


def taille_lettre(points, texte: str) -> float:
    """La taille de la lettre, ajustée à la boîte du mur.

    On ne remplit la boîte qu'à 80 % en largeur, pour laisser respirer le halo,
    et la largeur d'une capitale est prise à `LARGEUR_CAPITALE` — celle du PIRE
    glyphe, pas la moyenne. Voir le commentaire de cette constante : une
    moyenne ne borne rien.
    """
    x0, y0, x1, y1 = _cadre(points)
    n = max(1, len(texte))
    largeur = ((x1 - x0) * 0.8 / (n * LARGEUR_CAPITALE)) if x1 > x0 else LETTRE_MAXI
    hauteur = (y1 - y0) * 0.97 if y1 > y0 else LETTRE_MAXI
    return max(LETTRE_MINI, min(LETTRE_MAXI, largeur, hauteur))


def _rang(bloc) -> tuple[int, str]:
    """L'ordre du classeur : la difficulté d'abord, le numéro ensuite.

    C'est le tri de `Plan!AM` — `sort(AA; AB)` où `AB` vaut
    `Listes!B41:B46 + COUNTIF(...)`, soit 1000 par couleur plus le rang
    alphabétique. Le tri se fait donc sur la CHAÎNE (« J10 » avant « J9 ») ;
    on le reproduit tel quel plutôt que de le corriger, sans quoi la fiche et
    le classeur ne liraient pas dans le même ordre.

    Un bloc sans couleur connue passe APRÈS tous les autres : il est douteux, il
    ne doit pas ouvrir la liste.
    """
    couleur = bloc.couleur if bloc.couleur in COULEURS else None
    return (COULEURS.index(couleur) if couleur else len(COULEURS), bloc.tag or "")


def numero(bloc) -> str:
    """« ZJ6 » → « J6 » : le numéro tel qu'il est écrit sur le mur.

    `removeprefix` et non une découpe à un caractère : rien ne garantit qu'une
    zone tiendra toujours sur une lettre. Et si le tag se réduit à sa zone, on
    rend le tag — mieux vaut un libellé redondant qu'une case vide.
    """
    if not bloc.zone:
        return bloc.tag
    return bloc.tag.removeprefix(bloc.zone) or bloc.tag


def _blocs_par_circuit(comp) -> dict[str, list]:
    """Circuit → ses blocs, triés comme le classeur les trie.

    Deux requêtes, quel que soit le nombre de grimpeurs : c'est ce qui fait que
    cent fiches ne coûtent pas cent requêtes. Même budget que
    `circuits.inventaire()`.

    Un circuit connu mais vide rend une liste vide, jamais `None` : la fiche
    doit pouvoir distinguer « circuit inconnu » de « circuit sans bloc », les
    deux ne se réparent pas au même endroit.
    """
    blocs = {b.id: b for b in Bloc.query.filter_by(competition_id=comp.id).all()}
    circuits = {c.id: c.nom
                for c in Circuit.query.filter_by(competition_id=comp.id).all()}

    par_circuit: dict[str, list] = defaultdict(list)
    for nom in circuits.values():
        par_circuit[nom] = []

    if circuits:
        liens = (db.session.query(BlocCircuit.bloc_id, BlocCircuit.circuit_id)
                 .filter(BlocCircuit.circuit_id.in_(circuits)).all())
        for bloc_id, circuit_id in liens:
            bloc = blocs.get(bloc_id)
            if bloc is not None:
                par_circuit[circuits[circuit_id]].append(bloc)

    for liste in par_circuit.values():
        liste.sort(key=_rang)
    return dict(par_circuit)


def plan_courant() -> dict:
    """Le plan qui s'applique : celui dessiné dans la console, sinon l'usine.

    ⚠️ `PLAN` cesse d'être la source pour devenir le DÉFAUT (spec 029). Il
    s'applique tant que personne n'a dessiné, et sert de repli si la ligne
    enregistrée est illisible — imprimer les dossards la veille au soir ne doit
    pas dépendre de l'intégrité d'une ligne de base.

    Import tardif : `plan_du_mur` a besoin de `PAR_PROFIL` pour valider, et le
    faire en tête créerait un cycle.
    """
    from . import plan_du_mur
    return plan_du_mur.lire() or PLAN


def plan_pour(zones: set[str], plan: dict | None = None) -> dict:
    """Le plan de la salle, chaque mur sachant s'il est « le sien ».

    Le gabarit ne fait qu'afficher : c'est ici qu'on décide ce qui s'allume,
    ici qu'on place les lettres et ici qu'on calcule le cadrage. Une boucle de
    gabarit qui calcule des coordonnées est exactement ce qu'on relit trois
    fois sans le croire.

    Les points sortent DÉJÀ formatés (`"60,0 80,0 …"`) : Jinja n'a pas à
    fabriquer de géométrie.
    """
    # ⚠️ `plan` se passe quand on rend une PLANCHE : cette fonction est appelee
    # une fois par grimpeur, et sans lui cent vingt fiches feraient cent vingt
    # lectures du meme plan en base. C'est un test de budget de requetes qui
    # l'a rattrape, pas une relecture.
    plan = plan or plan_courant()
    largeur, hauteur = plan["vue"]
    m = MARGE_PLAN

    murs = []
    for mur in plan["murs"]:
        points = mur["points"]
        zone = mur["zone"] or ""
        # Un profil inconnu ne fait pas tomber une impression : on retombe sur
        # le vertical, qui est le cas le plus courant et le plus neutre.
        profil = mur["profil"] if mur["profil"] in PAR_PROFIL else PROFIL_PAR_DEFAUT
        murs.append({
            "zone": zone,
            "profil": profil,
            "d": " ".join(f"{x},{y}" for x, y in points),
            "etiquette": mur["etiquette"] or _centroide(points),
            "sienne": bool(zone) and zone in zones,
            "taille": taille_lettre(points, zone),
            # Le gabarit en a besoin : sur une zone « sienne », l'aplat noir a
            # mangé la trame et il faut la reposer en clair par-dessus.
            "trame": bool(PAR_PROFIL[profil]["trame"]),
        })

    contour = plan["contour"]
    return {
        "vue": plan["vue"],
        # ⚠️ La marge se prend ICI, sur le cadrage, et jamais sur les
        # coordonnées : sept murs d'Annonay touchent le bord, et sans elle la
        # moitié de leur trait sort du dessin.
        "cadrage": f"{-m} {-m} {largeur + 2 * m} {hauteur + 2 * m}",
        "contour": " ".join(f"{x},{y}" for x, y in contour) if contour else None,
        "murs": murs,
        "reperes": [{"texte": r["texte"], "x": r["point"][0], "y": r["point"][1]}
                    for r in plan["reperes"]],
    }


def _groupes(blocs) -> list[dict]:
    """Les blocs coupés par couleur de difficulté, dans l'ordre déjà trié.

    Un regroupement par parcours, et non un `groupby` sur un dictionnaire :
    la liste est déjà dans le bon ordre, et l'ordre est ce qui compte.
    """
    groupes: list[dict] = []
    for bloc in blocs:
        couleur = bloc.couleur if bloc.couleur in COULEURS else None
        if not groupes or groupes[-1]["couleur"] != couleur:
            groupes.append({"couleur": couleur, "blocs": []})
        groupes[-1]["blocs"].append({
            "tag": bloc.tag, "zone": bloc.zone, "numero": numero(bloc),
            "couleur": couleur,
        })
    return groupes


# --- Le budget de hauteur d'une fiche, en millimetres --------------------------
#
# ⚠️ Ces quatre valeurs sont MESUREES dans le navigateur sur le gabarit reel,
# pas estimees. La premiere version les avait estimees a vue et se trompait de
# 25 % sur la hauteur d'une ligne : les fiches U15 debordaient de six
# millimetres. Si le gabarit change (taille de police, remplissage des cases,
# marges), il faut les REMESURER : `TestLaHauteurDUneFiche` verifie la
# coherence DU CALCUL -- monotonie, cout d'une ligne, cout d'une marge -- mais
# aucun test ne peut verifier que ces quatre nombres decrivent encore le CSS.
# Seule une mesure au navigateur le dit.
HAUTEUR_UTILE_MM = 58.3          # ce qui reste sous le titre « TES N BLOCS »
HAUTEUR_LIGNE_MM = 7.3           # une ligne de cases
HAUTEUR_LIGNE_SUP_MM = 8.0       # chaque ligne SUPPLEMENTAIRE (ligne + gouttiere)
MARGE_GROUPE_MM = 1.2            # entre deux groupes de couleur

COLONNES_MINI, COLONNES_MAXI = 6, 12

# Combien de fiches par feuille, et combien d'etiquettes. Les deux DECOULENT de
# la geometrie des gabarits : 2 colonnes x 3 lignes pour les fiches (A4
# paysage), 2 x 4 pour les etiquettes (A4 portrait, 285 / 71,25). Les changer
# ici sans changer la geometrie laisserait des trous ou couperait une feuille.
FICHES_PAR_FEUILLE = 6
ETIQUETTES_PAR_FEUILLE = 8


def hauteur_mm(tailles: list[int], colonnes: int) -> float:
    """La hauteur qu'occuperaient ces groupes de blocs sur `colonnes` colonnes.

    Le nombre de LIGNES ne depend pas du nombre de blocs mais du nombre de
    COULEURS et du remplissage de chacune : une couleur de 22 blocs sur 8
    colonnes prend trois lignes a elle seule, et chaque groupe paie en plus sa
    marge.
    """
    total = 0.0
    for n in tailles:
        lignes = -(-n // colonnes)                            # ceil
        total += HAUTEUR_LIGNE_MM + (lignes - 1) * HAUTEUR_LIGNE_SUP_MM
    return total + MARGE_GROUPE_MM * max(0, len(tailles) - 1)


def colonnes_qui_tiennent(groupes) -> int:
    """Le nombre de colonnes le plus PETIT qui fait tenir tous les blocs.

    ⚠️ C'est calcule ici et pas laisse au CSS. `auto-fit` choisit ses colonnes
    d'apres la largeur disponible, sans rien savoir de la hauteur que ca
    produira : quand un groupe passait sur deux lignes, la fiche debordait et
    ses cadres chevauchaient la fiche voisine. Signale par Adrien le 02/09.

    Le plus petit nombre de colonnes qui tient donne les cases les PLUS
    GRANDES -- donc les plus lisibles -- sans deborder.
    """
    tailles = [len(g["blocs"]) for g in groupes if g["blocs"]]
    if not tailles:
        return COLONNES_MINI
    for colonnes in range(COLONNES_MINI, COLONNES_MAXI + 1):
        if hauteur_mm(tailles, colonnes) <= HAUTEUR_UTILE_MM:
            return colonnes
    return COLONNES_MAXI


def en_feuilles(elements: list, par_feuille: int) -> list[list]:
    """Découpe une liste en feuilles de taille fixe.

    ⚠️ La pagination est faite ICI, pas par le CSS. Une grille dont les
    éléments portent `break-inside: avoid` est fragmentée par le navigateur
    « au mieux » : en pratique une fiche se retrouvait à cheval sur deux
    feuilles. Des groupes explicites, un `break-after: page` par groupe, et le
    découpage devient déterministe.
    """
    return [elements[i:i + par_feuille]
            for i in range(0, len(elements), par_feuille)]


def construire(comp, participants) -> list[dict]:
    """Une fiche par participant, dans l'ordre où on les a reçus.

    La fiche s'imprime TOUJOURS, même quand il n'y a rien à y mettre : c'est
    elle qui porte le QR, et sans QR le grimpeur ne peut pas être scanné. Ce qui
    manque se dit dans `manque`, en toutes lettres.
    """
    par_circuit = _blocs_par_circuit(comp)
    # Une seule lecture du plan pour toute la planche : `construire` sert
    # jusqu'a cent vingt fiches, et le plan ne change pas entre deux.
    plan = plan_courant()
    dessinees = zones_du_plan(plan)

    planche = []
    for p in participants:
        circuit = p.circuit
        blocs = par_circuit.get(circuit) if circuit else None

        manque = None
        if not p.categorie:
            manque = ("Aucune catégorie : ce grimpeur n'est rattaché à aucun "
                      "circuit. Corrige-la dans la console, puis réimprime.")
        elif blocs is None:
            manque = (f"Circuit « {circuit} » inconnu — le classeur n'a pas "
                      "encore été importé pour cette compétition.")
        elif not blocs:
            manque = (f"Aucun bloc dans le circuit « {circuit} ». La vue "
                      "« Circuits » de la console dit pourquoi.")

        blocs = blocs or []
        zones = {b.zone for b in blocs if b.zone}
        groupes = _groupes(blocs)

        planche.append({
            "dossard": p.dossard,
            "nom": p.nom_complet,
            "club": p.club,
            "categorie": p.categorie,
            "circuit": circuit,
            "qr": qr.svg(p.dossard, cote_mm=COTE_QR_MM),
            "total": len(blocs),
            "groupes": groupes,
            "colonnes": colonnes_qui_tiennent(groupes),
            "plan": plan_pour(zones, plan),
            # Pour l'etiquette accessible du SVG : un lecteur d'ecran ne lit
            # pas un polygone, il lit le texte qu'on lui donne.
            "zones_siennes": sorted(zones & dessinees),
            # Une zone qu'on ne peut pas situer doit SE DIRE, pas disparaître :
            # le plan ne porte que 17 des 20 zones du classeur.
            "hors_plan": sorted(zones - dessinees),
            "manque": manque,
        })
    return planche


# --- Les étiquettes de blocs, à coller au mur (spec 024) ---------------------


def etiquettes(comp, zone: str | None = None, tag: str | None = None) -> list[dict]:
    """Les blocs à coller au mur, dans l'ordre du `Plan`.

    L'ordre est celui de `Bloc.numero` — le numéro de ligne dans l'onglet
    `Import`, qui suit le `Plan` : les blocs sortent donc zone par zone, comme
    le classeur les range. On prend la page de la zone Z, on va coller les cinq
    étiquettes de la zone Z, on ne trie rien à la main.

    Deux requêtes, quel que soit le nombre de blocs.

    ⚠️ Plus de découpage par zone. Il vivait ici sous la forme d'un drapeau
    `coupure` et d'un `par_zone()`, tous deux supprimés : la pagination porte
    désormais sur la FEUILLE (`en_feuilles`), parce qu'un saut par zone
    laissait des pages à moitié vides — une zone d'un seul bloc en gaspillait
    sept places. Ils survivaient sans appelant, avec des tests qui donnaient
    une fausse impression de couverture.
    """
    requete = Bloc.query.filter_by(competition_id=comp.id)
    if tag:
        requete = requete.filter(Bloc.tag == tag)
    elif zone:
        requete = requete.filter(Bloc.zone == zone)
    blocs = requete.order_by(Bloc.numero).all()

    circuits = {c.id: c.nom
                for c in Circuit.query.filter_by(competition_id=comp.id).all()}
    par_bloc: dict[int, list[str]] = defaultdict(list)
    if circuits and blocs:
        liens = (db.session.query(BlocCircuit.bloc_id, BlocCircuit.circuit_id)
                 .filter(BlocCircuit.circuit_id.in_(circuits),
                         BlocCircuit.bloc_id.in_([b.id for b in blocs])).all())
        for bloc_id, circuit_id in liens:
            par_bloc[bloc_id].append(circuits[circuit_id])

    planche = []
    for bloc in blocs:
        planche.append({
            "tag": bloc.tag,
            "zone": bloc.zone,
            "numero": numero(bloc),
            "couleur": bloc.couleur,
            "couleur_prises": bloc.couleur_prises,
            "circuits": sorted(par_bloc.get(bloc.id, ())),
            # Le QR porte le tag COMPLET — « ZJ6 » — c'est ce que l'application
            # juge attend et ce que `bloc_par_tag()` sait relire. Pas un
            # caractère de plus.
            "qr": qr.svg(bloc.tag, cote_mm=COTE_QR_ETIQUETTE_MM),
        })
    return planche
