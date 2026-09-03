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


# --- Le QR de poste, pose sur la table du juge (spec 034) --------------------

# ⚠️ CE PREFIXE EST ECRIT DEUX FOIS : ici, et dans
# `climbcontest/static/juge/poste.js` qui le lit. Le jour ou les deux divergent,
# TOUS les QR de poste imprimes cessent d'etre lus, sans qu'une seule ligne ait
# l'air fausse -- et ca se decouvre le samedi matin, avec les cartons deja poses
# sur les tables. `tests/test_postes.py::TestLePrefixePartage` lit le fichier JS
# et compare : le piege n'est pas documente, il est DETECTABLE.
#
# Pourquoi un prefixe : trois familles de QR circulent le jour J et le meme
# viseur les voit toutes -- le dossard (`42`), le bloc (`ZJ6`), le lien de
# l'organisateur. Sans prefixe, un juge qui scanne un bloc par erreur depuis
# cet ecran renommerait son poste « ZJ6 » sans s'en apercevoir.
PREFIXE_QR_POSTE = "CCPOSTE:"

# Le QR d'une affiche de poste. Nettement plus gros que celui d'une etiquette
# de bloc (42 mm) : ce n'est pas un autocollant colle au mur, c'est un carton
# pose sur une table, et le telephone le vise de biais, souvent d'une seule
# main. A 70 mm, un « CCPOSTE:A » donne 2,4 mm par module -- pres de cinq fois
# le plancher de `qr.MODULE_MINI_MM`.
COTE_QR_POSTE_MM = 70.0


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
# ⚠️ REMESURE le 02/09, quand la fiche est passee de 66 a 62 mm de haut pour
# que la feuille cesse de deborder de la page (voir l'entete de
# `dossards.html`). Quatre millimetres de fiche en moins, quatre millimetres de
# budget de blocs en moins.
# Mesure du 02/09 sur le gabarit a 62 mm : `.blocs` fait 56,62 mm de haut,
# dont 3,65 pour le titre et sa marge. Reste 52,98, arrondis a 52,9.
HAUTEUR_UTILE_MM = 52.9          # ce qui reste sous le titre « TES N BLOCS »
MARGE_GROUPE_MM = 1.2            # entre deux groupes de couleur

# --- Et sa LARGEUR, qui manquait ---------------------------------------------
#
# ⚠️ Le calcul ne regardait que la hauteur. La largeur n'etait bornee par rien
# du tout : `repeat(var(--cols), 1fr)` vaut `minmax(auto, 1fr)`, et une piste
# de grille ne descend jamais sous la largeur du texte qu'elle contient. Neuf
# colonnes de « M52 » dans soixante millimetres faisaient donc SOIXANTE-DIX
# millimetres de grille, et les dernieres cases se peignaient PAR-DESSUS le
# plan du mur. Mesure du 02/09 : les 120 fiches de la planche debordaient,
# toutes, de 5,75 mm -- avant meme le changement de format.
#
# Le nombre de colonnes et la TAILLE DU TEXTE se choisissent donc ensemble :
# moins de colonnes, c'est des cases plus larges et un texte plus gros, mais
# plus de lignes ; et chaque ligne coute moins cher quand le texte est plus
# petit. On garde le premier couple qui tient -- donc le plus gros texte.
LARGEUR_BLOCS_MM = 59.8          # mesure : 59,8 mm dans une fiche de 138
GOUTTIERE_CASE_MM = 0.5          # `gap` entre deux cases
HABILLAGE_CASE_MM = 0.8          # remplissage + filets, de part et d'autre
CHASSE_CASE = 0.82               # largeur d'un caractere du numero, en em

TAILLE_CASE_MAXI_MM = 3.0        # la taille de reference, celle du gabarit
TAILLE_CASE_MINI_MM = 2.0        # sous laquelle on ne descend pas : on prefere
                                 # une fiche pleine a un numero illisible

# La hauteur d'une ligne de cases se DEDUIT de la taille du texte, au lieu
# d'etre une constante mesuree a 3 mm : 4,2 mm d'habillage (remplissage,
# filets, ligne de zone) plus 1,05 fois la taille du texte. A 3 mm, la formule
# rend 7,35 -- la valeur qui etait ecrite en dur.
HAUTEUR_LIGNE_FIXE_MM = 4.2
HAUTEUR_LIGNE_PAR_TAILLE = 1.05

COLONNES_MINI, COLONNES_MAXI = 6, 12


def taille_case_mm(colonnes: int, caracteres: int) -> float:
    """La plus grande taille de numero qui tient dans une case, en mm.

    `caracteres` est la longueur du PLUS LONG numero de la fiche : c'est lui
    qui fixe la largeur de toutes les pistes, une grille a colonnes egales ne
    connaissant qu'une largeur.
    """
    largeur_case = ((LARGEUR_BLOCS_MM - (colonnes - 1) * GOUTTIERE_CASE_MM)
                    / colonnes)
    utile = largeur_case - HABILLAGE_CASE_MM
    if caracteres <= 0 or utile <= 0:
        return TAILLE_CASE_MAXI_MM
    tient = utile / (caracteres * CHASSE_CASE)
    return max(TAILLE_CASE_MINI_MM,
               min(TAILLE_CASE_MAXI_MM, int(tient * 20) / 20))


def hauteur_ligne_mm(taille: float) -> float:
    """La hauteur d'une ligne de cases, pour un numero de cette taille."""
    return HAUTEUR_LIGNE_FIXE_MM + HAUTEUR_LIGNE_PAR_TAILLE * taille


# Les deux valeurs mesurees d'origine, desormais DEDUITES de la formule a la
# taille de reference : 4,2 + 1,05 x 3 = 7,35 (mesure : 7,3) et une ligne de
# plus coute en outre sa gouttiere (mesure : 8,0). Elles restent nommees, parce
# qu'elles disent le cout d'une ligne dans le cas ordinaire.
HAUTEUR_LIGNE_MM = hauteur_ligne_mm(TAILLE_CASE_MAXI_MM)
HAUTEUR_LIGNE_SUP_MM = HAUTEUR_LIGNE_MM + GOUTTIERE_CASE_MM

# Combien de fiches par feuille, et combien d'etiquettes. Les deux DECOULENT de
# la geometrie des gabarits : 2 colonnes x 3 lignes pour les fiches (A4
# paysage), 2 x 4 pour les etiquettes (A4 portrait, 285 / 71,25). Les changer
# ici sans changer la geometrie laisserait des trous ou couperait une feuille.
FICHES_PAR_FEUILLE = 6
ETIQUETTES_PAR_FEUILLE = 8
# Et TROIS affiches de poste : 3 x 90 = 270 mm, sur une page utile de 277.
#
# ⚠️ La premiere version en posait DEUX (188 x 136 mm), en colonne : QR au
# milieu, nom dessous. Constate a l'ecran, pas devine -- le contenu faisait
# 164 mm de haut dans une affiche de 136, et le mode d'emploi sortait COUPE en
# bas. La disposition passe a l'horizontale (QR a gauche, texte a droite),
# comme les etiquettes de blocs depuis la spec 024 et pour la meme raison : un
# carton pose a plat est large et bas, empiler verticalement gaspille la
# largeur et manque de hauteur.
#
# Le gain n'est pas que de place : 17 zones tenaient sur 9 feuilles a moitie
# vides, elles tiennent sur 6 pleines. « Je me retrouve avec des pages vides »
# etait le reproche du 02/09 sur les etiquettes ; il vaut ici aussi.
POSTES_PAR_FEUILLE = 3


def hauteur_mm(tailles: list[int], colonnes: int,
               taille_texte: float = TAILLE_CASE_MAXI_MM) -> float:
    """La hauteur qu'occuperaient ces groupes de blocs sur `colonnes` colonnes.

    Le nombre de LIGNES ne depend pas du nombre de blocs mais du nombre de
    COULEURS et du remplissage de chacune : une couleur de 22 blocs sur 8
    colonnes prend trois lignes a elle seule, et chaque groupe paie en plus sa
    marge.

    `taille_texte` par defaut vaut la taille de reference du gabarit : appelee
    sans elle, la fonction rend ce qu'elle rendait avant que la taille devienne
    variable.
    """
    ligne = hauteur_ligne_mm(taille_texte)
    total = 0.0
    for n in tailles:
        lignes = -(-n // colonnes)                            # ceil
        total += ligne + (lignes - 1) * (ligne + GOUTTIERE_CASE_MM)
    return total + MARGE_GROUPE_MM * max(0, len(tailles) - 1)


def mise_en_page_blocs(groupes) -> tuple[int, float]:
    """Le couple (colonnes, taille du numero en mm) qui fait tenir la fiche.

    ⚠️ C'est calcule ici et pas laisse au CSS, POUR LES DEUX AXES.

    En hauteur : `auto-fit` choisit ses colonnes d'apres la largeur disponible,
    sans rien savoir du nombre de lignes que ca produira -- quand un groupe
    passait sur deux lignes, la fiche debordait sur sa voisine (Adrien, 02/09).

    En largeur : une piste `1fr` ne descend jamais sous la largeur de son
    texte. Neuf colonnes de « M52 » faisaient soixante-dix millimetres de
    grille dans une colonne de soixante, et les dernieres cases se peignaient
    par-dessus le plan du mur -- sur les 120 fiches de la planche, mesure du
    02/09. Le CSS seul ne peut pas arbitrer : lui n'a pas le droit de changer
    la taille du texte, nous si.

    On parcourt les colonnes du plus PETIT nombre au plus grand. Peu de
    colonnes donne des cases larges et un gros texte, mais beaucoup de lignes ;
    et une ligne coute moins cher quand le texte est plus petit. Le premier
    couple qui tient en hauteur est donc celui qui garde le plus gros texte.
    """
    tailles = [len(g["blocs"]) for g in groupes if g["blocs"]]
    if not tailles:
        return COLONNES_MINI, TAILLE_CASE_MAXI_MM
    plus_long = max((len(b["numero"]) for g in groupes for b in g["blocs"]),
                    default=1)
    dernier = (COLONNES_MAXI, taille_case_mm(COLONNES_MAXI, plus_long))
    for colonnes in range(COLONNES_MINI, COLONNES_MAXI + 1):
        taille = taille_case_mm(colonnes, plus_long)
        if hauteur_mm(tailles, colonnes, taille) <= HAUTEUR_UTILE_MM:
            return colonnes, taille
    return dernier


def colonnes_qui_tiennent(groupes) -> int:
    """Le nombre de colonnes seul — voir `mise_en_page_blocs`."""
    return mise_en_page_blocs(groupes)[0]


# --- La taille du numero d'une etiquette, en millimetres ----------------------
#
# ⚠️ MESUREES DANS LE NAVIGATEUR, comme le budget de hauteur d'une fiche, et
# pas estimees : la premiere version tablait sur 0,58 em par caractere, la
# mesure en a donne 0,705, et « M40 » debordait de neuf millimetres.
#
# La colonne de texte fait 94 mm (l'etiquette) moins 6 (le remplissage) moins
# 42 (le QR) moins 3 (la gouttiere) = 43 mm ; on en garde 42 pour l'arrondi.
LARGEUR_NUMERO_MM = 42.0
CHASSE_NUMERO = 0.72              # largeur d'un caractere, en em (mesure : 0,705)

# ⚠️ UNE SEULE TAILLE, la meme sur toute etiquette (spec 033, R7).
#
# Elle etait calculee par etiquette : « J6 » sortait a 26 mm et « J24 » a
# 19,5 mm, parce qu'on prenait la plus grande taille a laquelle chaque numero
# tenait. C'est logique vu de pres, et bancal vu sur une planche de huit --
# « le numero J6 ou J24 change de taille en fonction du nombre de caracteres,
# je veux que la taille de la police soit fixe » (Adrien, 03/09, apres avoir
# imprime pour de vrai).
#
# 42 / (3 x 0,72) = 19,4, arrondi au demi-millimetre inferieur. TROIS
# caracteres, parce qu'un numero d'etiquette est la lettre de couleur suivie
# du numero dans la couleur : « J6 », « J24 », « M40 ». Un quatrieme
# caractere ne mange pas le QR -- `overflow: hidden` et `white-space: nowrap`
# tiennent la colonne -- il est coupe, ce qui se voit et se corrige.
#
# ⚠️ Une constante, et PAS « la plus grande taille qui tient sur cette
# planche ». Cette seconde option donnerait des numeros plus gros quand la
# planche n'a que des numeros courts, mais imprimer toute la salle puis la
# seule zone A rendrait DEUX tailles differentes pour les memes etiquettes :
# le filtre change le plus long numero de la planche. On recollerait au mur
# des etiquettes qui ne se ressemblent pas.
TAILLE_NUMERO_MM = 19.0

# --- Et la taille du nom de zone d'une affiche de poste (spec 034) -----------
#
# ⚠️ Le nom de zone, LUI, reste dimensionne par son texte -- et ce n'est pas un
# oubli de la R7 juste au-dessus. Les deux raisons qui ont fige le numero
# d'etiquette ne mordent pas ici :
#
#  - une planche d'etiquettes en aligne huit cote a cote, et deux voisines de
#    tailles differentes se voient. Une affiche de poste est un objet SEUL,
#    scotche sur sa table ; les trois d'un meme A4 sont decoupees avant d'etre
#    posees, et ne se revoient jamais.
#  - la seconde raison -- imprimer toute la salle puis une seule zone donnerait
#    deux tailles pour la MEME etiquette -- ne s'applique pas non plus : la
#    taille ne depend que du texte, donc « TOIT » sort identique qu'on imprime
#    une affiche ou vingt.
#
# Si un jour les affiches doivent se ressembler entre elles, c'est la meme
# correction qu'en R7 : une constante, pas « la plus grande qui tient sur cette
# planche » (le filtre changerait la taille).
#
# La colonne de texte fait 188 mm (l'affiche) moins 10 (le rembourrage) moins
# 70 (le QR) moins 6 (la gouttiere) = 102 mm ; on en garde 100 pour l'arrondi.
LARGEUR_NOM_POSTE_MM = 100.0
CHASSE_NOM_POSTE = 0.72           # meme graisse (800) que le numero d'etiquette
TAILLE_NOM_POSTE_MAXI_MM = 30.0   # au-dela, le nom mange le mode d'emploi


def taille_nom_poste_mm(texte: str) -> float:
    """La plus grande taille a laquelle ce nom de zone tient sur une ligne.

    Arrondie au demi-millimetre inferieur, et sans plancher a dessein : un nom
    tres long doit RETRECIR, pas deborder. Le gabarit pose `white-space:
    nowrap`, donc ce qui ne tient pas serait coupe -- et un nom de zone coupe
    ne sert plus a rien. Un texte vide rend le maximum.

    ⚠️ Ce calcul etait partage avec celui du numero d'etiquette, par un
    `_taille_qui_tient_mm` commun. La R7 a fige le numero : le partage n'a plus
    d'objet, et un helper generique « la plus grande taille qui tient » serait
    surtout une invitation a refaire ce qu'Adrien vient de defaire.
    """
    n = len(texte or "")
    if n <= 0:
        return TAILLE_NOM_POSTE_MAXI_MM
    tient = LARGEUR_NOM_POSTE_MM / (n * CHASSE_NOM_POSTE)
    return min(TAILLE_NOM_POSTE_MAXI_MM, int(tient * 2) / 2)



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

        colonnes, taille_case = mise_en_page_blocs(groupes)
        planche.append({
            "dossard": p.dossard,
            "nom": p.nom_complet,
            "club": p.club,
            "categorie": p.categorie,
            "circuit": circuit,
            "qr": qr.svg(p.dossard, cote_mm=COTE_QR_MM),
            "total": len(blocs),
            "groupes": groupes,
            "colonnes": colonnes,
            # La taille du numero d'un bloc suit le nombre de colonnes : voir
            # `mise_en_page_blocs`. Elle part au gabarit comme `--case`.
            "taille_case": taille_case,
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
    """Les blocs à coller au mur, **zone par zone, de A à Z**.

    ⚠️ L'ordre était celui de `Bloc.numero` — le numéro de ligne de l'onglet
    `Import`, qui suit le `Plan`. Les blocs sortaient bien zone par zone, mais
    dans l'ordre du plan, qui n'est pas l'alphabet : celui d'Annonay commence
    par X et Y et finit par E. « Je veux qu'ils soient classés dans l'ordre
    alphabétique des zones, c'est-à-dire la zone A d'abord et tu finis par la
    Z » (Adrien, 03/09, spec 033 R8).

    Le tri est donc `(zone absente, zone, numéro)` :

    - **`zone IS NULL` en premier critère**, parce que SQLite range les `NULL`
      AVANT tout le reste. Sans lui, une planche s'ouvrirait sur les blocs qui
      n'ont aucun mur où aller — l'anomalie en tête de la première feuille.
    - la zone, sur sa VALEUR : depuis la spec 029 le nom de zone est saisi dans
      la console, et rien ne garantit qu'il tient sur une lettre.
    - `Bloc.numero`, qui reste l'ordre du classeur À L'INTÉRIEUR d'une zone :
      difficulté puis numéro. C'est celui qui existait, et on n'y touche pas.

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
    blocs = requete.order_by(
        Bloc.zone.is_(None), Bloc.zone, Bloc.numero).all()

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


# --- Les affiches de poste, posées sur la table du juge (spec 034) -----------


def texte_qr_poste(zone: str) -> str:
    """Ce qu'on encode dans le QR d'une zone. Le pendant de `poste.nomDePoste`."""
    return PREFIXE_QR_POSTE + str(zone or "").strip()


def postes(zone: str | None = None, plan: dict | None = None) -> list[dict]:
    """Une affiche par zone du plan, triée par nom de zone.

    ⚠️ **Les zones se déduisent du plan, jamais d'une liste tenue à la main.**
    Adrien, le 03/09 : « tu connais parfaitement grâce au plan le nombre des
    zones, donc tu peux tout à fait le générer automatiquement ». Un mur ajouté
    dans `/admin/plan` sort son QR à l'impression suivante, sans qu'on touche à
    quoi que ce soit — et une liste qui divergerait du plan ferait imprimer un
    carton pour une zone qui n'existe plus.

    ⚠️ **Aucune requête sur `Bloc`, `Participant` ou `Competition`.** Une
    planche de QR de poste ne dépend d'aucune compétition : c'est ce qui permet
    de l'imprimer la veille au soir, avant même d'avoir importé le classeur.

    L'ordre est **alphabétique**, pas celui du plan. Le plan range les murs dans
    l'ordre où on les a dessinés — arbitraire pour qui cherche la zone « M »
    dans une pile de neuf feuilles. Les étiquettes de blocs, elles, suivent le
    `Plan` parce qu'on les colle mur par mur : ce n'est pas le même geste.

    Deux murs portant la même zone ne donnent **qu'une** affiche :
    `zones_du_plan` rend un ensemble.
    """
    zones = sorted(zones_du_plan(plan if plan is not None else plan_courant()))
    if zone:
        # Une zone absente du plan rend une liste VIDE, pas une exception : la
        # page doit pouvoir la nommer et dire qu'elle n'existe pas.
        zones = [z for z in zones if z == zone]

    planche = []
    for z in zones:
        texte = texte_qr_poste(z)
        planche.append({
            "zone": z,
            "texte": texte,
            # La taille du nom suit sa LONGUEUR : voir `taille_nom_poste_mm`.
            "taille_nom": taille_nom_poste_mm(z),
            "qr": qr.svg(texte, cote_mm=COTE_QR_POSTE_MM),
        })
    return planche
