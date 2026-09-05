"""Import du classeur vers la base — tolérant, idempotent, et qui rend compte.

Trois défauts de la version précédente sont corrigés ici, tous constatés dans
l'[état des lieux](../../docs/etat-des-lieux.md) :

**R5 — le grimpeur qui disparaît.** L'ancien code n'acceptait une ligne que si
elle faisait exactement six colonnes. Or Google Sheets **tronque les cellules
vides de fin** : un grimpeur sans club ou sans catégorie renvoie une ligne de
quatre éléments et était **ignoré sans message**. Ici, nom et dossard suffisent ;
le reste est facultatif et signalé dans le rapport.

**R6 — le numéro de bloc faux.** L'ancien code prenait `line[-1]` comme numéro
de bloc. Sur une ligne complète (22 colonnes) c'est bien la colonne Y ; sur une
ligne tronquée à 17, `line[-1]` vaut la colonne T — le numéro **de zone**. Les
réussites atterrissaient alors sur la mauvaise ligne du classeur. Ici la
position est **explicite** (index 21), et une ligne trop courte est rejetée et
signalée, jamais devinée.

**R7 — l'import déclenché par un scan.** Il ne l'est plus : c'est une action
explicite de la console d'administration.

**Le doublon fabriqué par le dossard — 05/09.** Jusqu'ici, une ligne du classeur
était rapprochée **par son seul dossard**. Deux conséquences, toutes deux
prouvées par un test avant d'être corrigées :

- un participant dont le dossard avait changé de main n'était plus retrouvé, et
  l'import **recréait sa fiche** — deux « Dupont Lea » dans la liste, chacune
  avec une partie des réussites ;
- pire, si son ancien numéro était désormais porté par quelqu'un d'autre,
  l'import **écrasait le nom de ce quelqu'un d'autre** avec celui de la ligne du
  classeur, alors que des réussites y étaient déjà attachées.

Le dossard reste la **première** clé — c'est le cas courant, et c'est le plus
rapide. Mais il ne conclut plus seul : l'**identité** (nom + prénom + club) le
confirme, et prend le relais quand il ne dit rien. La comparaison est celle de
`helloasso/rapprochement.py`, pas une seconde écrite ici : deux règles de
rapprochement finiraient par ne plus rapprocher la même chose.

Structure du classeur : docs/technical/classeur-google.md.
"""

import logging
from dataclasses import dataclass, field

from .. import formatage
from ..contest import club_canonique
from ..cycle import source_active
from ..extensions import db
from ..helloasso import rapprochement
from ..models import (
    Bloc, BlocCircuit, Circuit, Competition, Participant, SOURCE_CLASSEUR,
    SOURCE_MANUEL,
)
from .client import ClasseurGoogle, ErreurClasseur

logger = logging.getLogger(__name__)

# --- Onglet « Plan », plage D29:Y — un bloc par ligne -----------------------
PLAN_ONGLET = "Plan"
PLAN_LIGNE_ENTETE = 28          # porte les noms de circuits
PLAN_PLAGE = "D28:Y"
I_ZONE = 0                      # colonne D — lettre de zone
I_COULEUR = 2                   # colonne F — couleur de difficulte
I_COULEUR_PRISES = 4            # colonne H — couleur des prises sur le mur

# Les colonnes où un circuit PEUT vivre : J, L, N, P, R — une sur deux, cinq au
# plus. Le classeur se décrit lui-même comme prévu pour « 5 circuits »
# (`Listes!A1`), et la ligne d'en-tête dit lesquelles servent vraiment.
#
# ⚠️ Elles sont DÉCOUVERTES, plus jamais figées. Jusqu'au 01/09, ce tuple valait
# `(6, 8, 10)` : trois circuits, parce que la structure avait été relevée sur le
# classeur de mars 2026 qui n'en a que trois. Celui de novembre 2025 en a
# **quatre** (U11, U13, U15, U17) — le quatrième n'était jamais créé, ses 37
# blocs n'étaient rattachés à aucun circuit, son classement sortait vide, et
# tout grimpeur de ce circuit aurait vu chacune de ses réussites comptée pour
# zéro. Rien, nulle part, ne le disait.
I_CIRCUITS_POSSIBLES = (6, 8, 10, 12, 14)

I_NUMERO_ZONE = 16              # colonne T — numero dans la zone
I_NUMERO_IMPORT = 21            # colonne Y — ligne dans l'onglet Import
PLAN_COLONNES_MINI = 22         # il FAUT aller jusqu'a Y

# --- Onglet « Listes », plage F2:K — un participant par ligne ---------------
LISTES_ONGLET = "Listes"
LISTES_PLAGE = "F2:K"
I_NOM_COMPLET = 0               # colonne F
I_DOSSARD = 1                   # colonne G
I_NOM = 2                       # colonne H
I_PRENOM = 3                    # colonne I
I_CLUB = 4                      # colonne J
I_CATEGORIE = 5                 # colonne K


@dataclass
class Rapport:
    """Ce que l'import a fait, et ce qu'il n'a pas pu faire.

    Le rapport est la moitié du travail : un import muet qui perd un grimpeur
    est exactement ce qui s'est passé jusqu'ici.
    """

    participants_crees: int = 0
    participants_mis_a_jour: int = 0
    # Les champs que l'import n'a PAS reecrits parce que quelqu'un les avait
    # corriges dans la console. Compte a part, et affiche : un import qui
    # conserve en silence ne se distingue pas d'un import qui n'a rien vu.
    corrections_conservees: int = 0
    blocs_crees: int = 0
    blocs_mis_a_jour: int = 0
    circuits_crees: int = 0
    # Les circuits lus dans l'en-tête, avec leur colonne : « U17 (colonne P) ».
    # Affiché systématiquement, même quand tout va bien — c'est la seule ligne
    # qui aurait montré, en novembre 2025, qu'un circuit sur quatre manquait.
    circuits: list[str] = field(default_factory=list)
    ignores: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "participants": {"crees": self.participants_crees,
                             "mis_a_jour": self.participants_mis_a_jour,
                             "corrections_conservees": self.corrections_conservees},
            "blocs": {"crees": self.blocs_crees, "mis_a_jour": self.blocs_mis_a_jour},
            "circuits_crees": self.circuits_crees,
            "circuits": self.circuits,
            "ignores": self.ignores,
            "avertissements": self.avertissements,
        }

    def resume(self) -> str:
        return (f"{self.participants_crees} participant(s) cree(s), "
                f"{self.participants_mis_a_jour} mis a jour, "
                f"{self.corrections_conservees} correction(s) conservee(s) ; "
                f"{self.blocs_crees} bloc(s) cree(s), {self.blocs_mis_a_jour} mis a jour ; "
                # Le nombre de circuits LUS, pas seulement les nouveaux : c'est
                # ce chiffre-la qu'on compare de tete a ce qu'on attend.
                f"{len(self.circuits)} circuit(s) : {', '.join(self.circuits) or 'aucun'} ; "
                f"{len(self.ignores)} ligne(s) ignoree(s)")


def _lettre(index: int) -> str:
    """L'index dans `D28:Y` → la lettre de colonne du classeur. 6 → « J ».

    Sert aux messages, et uniquement à eux : c'est en lettres qu'on lit une
    feuille de calcul, et « colonne 12 » n'aide personne à retrouver la case.
    """
    return chr(ord("D") + index)


def _colonnes_possibles() -> str:
    return ", ".join(_lettre(i) for i in I_CIRCUITS_POSSIBLES)


def _texte(ligne: list, index: int) -> str | None:
    """Lecture tolérante : une colonne absente vaut None, pas une exception."""
    if index >= len(ligne):
        return None
    valeur = str(ligne[index]).strip()
    return valeur or None


def importer_participants(comp: Competition, classeur, rapport: Rapport,
                          lignes: list[list] | None = None) -> None:
    """⚠️ Ne fait rien si le classeur n'est pas une source d'inscrits.

    Le reglage du 04/09 porte sur les PARTICIPANTS, et sur eux seuls : une
    edition peut tres bien prendre ses inscrits sur HelloAsso tout en
    continuant a lire les BLOCS et les CIRCUITS dans le classeur, qui reste la
    carte du mur. C'est pourquoi la garde est ici, sur cette fonction, et non
    sur `importer()`.
    """
    if not source_active(comp, SOURCE_CLASSEUR):
        rapport.avertissements.append(
            "Le classeur n'est pas une source d'inscrits pour cette edition : "
            "les blocs sont importes, les participants non.")
        return

    if lignes is None:
        lignes = classeur.lire(LISTES_ONGLET, LISTES_PLAGE)

    # Toute la liste, lue UNE fois. Le rapprochement par identite compare
    # chaque ligne a tout le monde ; une requete par ligne ferait cent
    # requetes, et surtout ne verrait pas les participants crees par les
    # lignes precedentes du meme import -- deux lignes jumelles du classeur
    # produiraient alors deux fiches, ce qu'on est justement en train
    # d'empecher.
    existants = Participant.query.filter_by(competition_id=comp.id).all()

    for n, ligne in enumerate(lignes, start=2):
        nom_complet = _texte(ligne, I_NOM_COMPLET)
        dossard_brut = _texte(ligne, I_DOSSARD)
        if not nom_complet:
            continue                                # ligne vide : normal

        if not dossard_brut:
            rapport.ignores.append(f"Listes L{n} : « {nom_complet} » sans dossard")
            continue
        try:
            dossard = int(dossard_brut)
        except ValueError:
            rapport.ignores.append(
                f"Listes L{n} : dossard « {dossard_brut} » illisible pour « {nom_complet} »")
            continue

        # ⚠️ Le formatage s'applique ICI DEPUIS LE 04/09, et c'est un
        # changement de doctrine assume -- voir l'en-tete de `formatage.py`.
        #
        # Sans lui, « ANNONAY ESCALADE » venu du classeur et « Annonay
        # Escalade » tape au guichet sont deux clubs : deux entrees dans la
        # liste deroulante, et un rapprochement qui echoue. C'est-a-dire un
        # doublon, fabrique par une difference de casse.
        #
        # Il ne corrige que la FORME : un nom mal orthographie ou une categorie
        # inexistante restent signales par le rapport, plus bas.
        nom = formatage.nom(_texte(ligne, I_NOM) or nom_complet)
        prenom = formatage.nom(_texte(ligne, I_PRENOM))
        club = club_canonique(comp, _texte(ligne, I_CLUB))
        categorie = formatage.categorie(_texte(ligne, I_CATEGORIE))

        # Facultatif, mais on le dit — c'est ce qui manquait avant.
        if not categorie:
            rapport.avertissements.append(
                f"Listes L{n} : « {nom_complet} » sans categorie (importe quand meme)")
        if not club:
            rapport.avertissements.append(
                f"Listes L{n} : « {nom_complet} » sans club (importe quand meme)")

        p = _retrouver(comp, existants, dossard, nom, prenom, club, categorie,
                       n, nom_complet, rapport)
        if p is _IGNORER:
            continue

        if p is None:
            p = Participant(
                competition_id=comp.id, nom=nom, prenom=prenom, club=club,
                categorie=categorie, dossard=dossard, source=SOURCE_CLASSEUR)
            db.session.add(p)
            db.session.flush()
            existants.append(p)
            rapport.participants_crees += 1
            continue

        # Retrouve. Le classeur complete, il n'ecrase plus ce que la console a
        # corrige -- decision d'Adrien du 05/09 : « la console gagne,
        # definitivement ».
        conserves, avant = [], (p.nom, p.prenom, p.club, p.categorie)
        for champ, valeur in (("nom", nom), ("prenom", prenom),
                              ("club", club), ("categorie", categorie)):
            if p.est_force(champ):
                if getattr(p, champ) != valeur:
                    conserves.append(champ)
                continue
            setattr(p, champ, valeur)

        if (p.nom, p.prenom, p.club, p.categorie) != avant:
            rapport.participants_mis_a_jour += 1
        if conserves:
            rapport.corrections_conservees += len(conserves)
            rapport.avertissements.append(
                f"Listes L{n} : « {p.nom_complet} » — {', '.join(conserves)} "
                f"corrige(s) dans la console, la ligne du classeur n'ecrase pas.")

        # ⚠️ Le dossard n'est JAMAIS reecrit ici. Il est unique dans la
        # competition : le reprendre au classeur pendant qu'un autre le porte
        # ferait echouer tout l'import sur une contrainte, une ligne sur cent.
        if p.dossard is None and _dossard_libre(existants, dossard):
            # Il n'a plus de numero et le sien est libre : on le lui rend.
            # C'est le retour a la normale apres une fusion de doublons.
            p.dossard = dossard
            rapport.avertissements.append(
                f"Listes L{n} : dossard {dossard} rendu a « {p.nom_complet} ».")
        elif p.dossard != dossard:
            # Nommer QUI porte le numero : sans ce nom, l'organisateur doit
            # chercher dans la liste ce que l'import savait deja.
            porteur = next((x for x in existants
                            if x.dossard == dossard and x.id != p.id), None)
            occupe = f", porte par « {porteur.nom_complet} »" if porteur else ""
            rapport.avertissements.append(
                f"Listes L{n} : « {p.nom_complet} » porte le dossard "
                f"{p.dossard if p.dossard is not None else 'aucun'} en console, "
                f"le classeur dit {dossard}{occupe}. La console fait foi, aucune "
                f"fiche n'a ete creee — corriger le classeur si l'ecart n'est "
                f"pas voulu.")

        db.session.add(p)

    db.session.commit()


#: Ce que `_retrouver` rend quand la ligne ne doit rien produire du tout.
_IGNORER = object()


def _dossard_libre(existants: list, dossard: int) -> bool:
    return not any(x.dossard == dossard for x in existants)


def _retrouver(comp, existants, dossard, nom, prenom, club, categorie,
               n, nom_complet, rapport):
    """Qui est cette ligne du classeur ? Deux cles, dans cet ordre.

    Rend le participant, `None` s'il faut le creer, ou `_IGNORER` si la ligne
    ne doit rien produire -- et dans ce cas le rapport porte deja le pourquoi.
    """
    par_dossard = next((x for x in existants if x.dossard == dossard), None)
    meme = (par_dossard is not None
            and formatage.identite(par_dossard.nom, par_dossard.prenom)
            == formatage.identite(nom, prenom))

    if meme:
        return par_dossard                          # le cas courant, et le plus rapide

    # Le numero ne dit pas la meme personne. On demande a l'identite -- la
    # MEME fonction que le rapprochement HelloAsso, pour que « le doublon entre
    # deux origines » ait une seule definition dans tout le projet.
    verdict = rapprochement.confronter(
        rapprochement.Personne(None, nom, prenom, club, categorie),
        [rapprochement.Personne(x.id, x.nom, x.prenom, x.club, x.categorie)
         for x in existants])

    if verdict.quoi == rapprochement.MEME_PERSONNE:
        return db.session.get(Participant, verdict.identifiant)

    if par_dossard is None:
        return None                                 # personne, nulle part : c'est un nouveau

    # Le classeur peut reecrire les fiches QU'IL POSSEDE, et celles-la seules.
    #
    # C'est le cas banal du nom mal orthographie corrige dans le classeur :
    # « Dupond » devient « Dupont » sur la ligne du dossard 5, et l'identite ne
    # reconnait evidemment plus personne. Le refuser obligerait a trancher a la
    # main une coquille que le classeur vient justement de corriger.
    #
    # Trois conditions, et il les faut toutes : la fiche vient du classeur (une
    # inscription HelloAsso ou un ajout au guichet ne lui appartiennent pas),
    # elle ne porte aucune reussite, et aucune inscription en ligne n'y est
    # rattachee. Sans elles, « corriger un nom » deviendrait « donner les
    # reussites de quelqu'un a quelqu'un d'autre ».
    if (par_dossard.source == SOURCE_CLASSEUR
            and not par_dossard.reussites
            and not par_dossard.inscriptions):
        return par_dossard

    # Quelqu'un d'autre porte ce numero, et l'identite ne le reconnait pas.
    #
    # ⚠️ C'est ici que se jouait le defaut le plus grave : l'ancienne version
    # ecrivait le nom de la ligne du classeur SUR CE QUELQU'UN D'AUTRE, dont
    # les reussites etaient deja enregistrees. Elles changeaient de
    # proprietaire sans un mot. On ne touche a rien, et on le dit.
    #
    # On ne cree pas non plus la fiche manquante : elle partirait sans dossard
    # -- invisible pour les juges, qui scannent un numero -- et l'organisateur
    # croirait la ligne importee.
    a_la_main = " (ajoute a la main)" if par_dossard.source == SOURCE_MANUEL else ""
    rapport.ignores.append(
        f"Listes L{n} : le dossard {dossard} est porte par "
        f"« {par_dossard.nom_complet} »{a_la_main}, pas par « {nom_complet} ». "
        f"Ligne ignoree, rien n'a ete modifie -- verifier lequel des deux garde "
        f"ce numero.")
    return _IGNORER


def importer_blocs(comp: Competition, classeur, rapport: Rapport,
                   lignes: list[list] | None = None) -> None:
    if lignes is None:
        lignes = classeur.lire(PLAN_ONGLET, PLAN_PLAGE)
    if not lignes:
        rapport.ignores.append("Plan : aucune ligne lue")
        return

    entete, lignes = lignes[0], lignes[1:]
    # Seules les colonnes qui portent un nom sont des circuits. Un classeur à
    # trois circuits et un classeur à cinq passent ici sans qu'on ait à savoir
    # lequel on lit.
    noms_circuits = {i: _texte(entete, i) for i in I_CIRCUITS_POSSIBLES}
    noms_circuits = {i: nom for i, nom in noms_circuits.items() if nom}
    if not noms_circuits:
        raise ErreurClasseur(
            f"Plan L{PLAN_LIGNE_ENTETE} : aucun nom de circuit dans les colonnes "
            f"{_colonnes_possibles()}. La structure du classeur a change — import "
            f"interrompu, rien n'a ete modifie.")

    rapport.circuits = [f"{nom} (colonne {_lettre(i)})"
                        for i, nom in sorted(noms_circuits.items())]

    circuits: dict[str, Circuit] = {}
    for nom in noms_circuits.values():
        c = Circuit.query.filter_by(competition_id=comp.id, nom=nom).first()
        if not c:
            c = Circuit(competition_id=comp.id, nom=nom)
            db.session.add(c)
            rapport.circuits_crees += 1
        circuits[nom] = c
    db.session.flush()

    for n, ligne in enumerate(lignes, start=PLAN_LIGNE_ENTETE + 1):
        zone = _texte(ligne, I_ZONE)
        if not zone:
            continue                                # ligne vide : normal

        # R6 : on exige d'aller jusqu'a la colonne Y. Une ligne plus courte est
        # rejetee et SIGNALEE, jamais devinee.
        if len(ligne) < PLAN_COLONNES_MINI:
            rapport.ignores.append(
                f"Plan L{n} : ligne de {len(ligne)} colonnes, il en faut "
                f"{PLAN_COLONNES_MINI} pour lire le numero d'import (colonne Y)")
            continue

        numero_zone = _texte(ligne, I_NUMERO_ZONE)
        numero_brut = _texte(ligne, I_NUMERO_IMPORT)
        if not numero_zone or not numero_brut:
            rapport.ignores.append(f"Plan L{n} : numero de bloc absent")
            continue
        try:
            numero = int(numero_brut)
        except ValueError:
            rapport.ignores.append(f"Plan L{n} : numero « {numero_brut} » illisible")
            continue

        tag = f"{zone}{numero_zone}"
        couleur = _texte(ligne, I_COULEUR)
        couleur_prises = _texte(ligne, I_COULEUR_PRISES)

        bloc = Bloc.query.filter_by(competition_id=comp.id, tag=tag).first()
        if bloc:
            if ((bloc.numero, bloc.couleur, bloc.couleur_prises)
                    != (numero, couleur, couleur_prises)):
                bloc.numero, bloc.couleur = numero, couleur
                bloc.couleur_prises = couleur_prises
                rapport.blocs_mis_a_jour += 1
            db.session.add(bloc)
        else:
            bloc = Bloc(competition_id=comp.id, tag=tag, numero=numero,
                        zone=zone, couleur=couleur, couleur_prises=couleur_prises)
            db.session.add(bloc)
            rapport.blocs_crees += 1
        db.session.flush()

        # Rattachement aux circuits : une croix dans la colonne du circuit.
        for i, nom_circuit in noms_circuits.items():
            if not _texte(ligne, i):
                continue
            c = circuits[nom_circuit]
            lien = BlocCircuit.query.filter_by(bloc_id=bloc.id, circuit_id=c.id).first()
            if not lien:
                db.session.add(BlocCircuit(bloc_id=bloc.id, circuit_id=c.id))

    db.session.commit()


@dataclass
class Lecture:
    """Ce que le classeur a répondu, avant qu'on touche à quoi que ce soit.

    C'est toute la raison d'être de cette classe : en mode « remplacement
    complet » (spec 018), la base est effacée puis repeuplée. Si la lecture
    échouait APRÈS l'effacement, on se retrouverait avec une base vide et un
    import qui n'a jamais eu lieu — le pire des deux mondes, et sans retour
    possible. Lire d'abord, détruire ensuite.
    """

    plan: list[list]
    listes: list[list]


def lire_tout(classeur) -> Lecture:
    """Les deux plages du classeur, et RIEN d'autre. Que du réseau."""
    return Lecture(plan=classeur.lire(PLAN_ONGLET, PLAN_PLAGE),
                   listes=classeur.lire(LISTES_ONGLET, LISTES_PLAGE))


def importer(comp: Competition, classeur=None, lecture: Lecture | None = None) -> Rapport:
    """Importe participants et blocs. Idempotent : rejouable sans rien dupliquer.

    Le rejeu est ce qui permet de reprendre une correction faite dans le
    classeur — un dossard changé, une catégorie corrigée — ce que l'ancienne
    version ne faisait jamais (elle n'ajoutait que les noms absents).

    Sans `lecture`, il lit lui-même : c'est le comportement d'origine, et tous
    les appels existants le gardent.
    """
    cl = classeur or ClasseurGoogle(comp.spreadsheet_id)
    rapport = Rapport()

    importer_blocs(comp, cl, rapport, lecture.plan if lecture else None)
    importer_participants(comp, cl, rapport, lecture.listes if lecture else None)

    comp.catalogue_version = (comp.catalogue_version or 0) + 1
    db.session.add(comp)
    db.session.commit()

    logger.info("import du classeur : %s", rapport.resume())
    return rapport
