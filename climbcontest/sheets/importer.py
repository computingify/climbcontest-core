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

Structure du classeur : docs/technical/classeur-google.md.
"""

import logging
from dataclasses import dataclass, field

from ..extensions import db
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
I_CIRCUITS = (6, 8, 10)         # colonnes J, L, N
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
    blocs_crees: int = 0
    blocs_mis_a_jour: int = 0
    circuits_crees: int = 0
    ignores: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "participants": {"crees": self.participants_crees,
                             "mis_a_jour": self.participants_mis_a_jour},
            "blocs": {"crees": self.blocs_crees, "mis_a_jour": self.blocs_mis_a_jour},
            "circuits_crees": self.circuits_crees,
            "ignores": self.ignores,
            "avertissements": self.avertissements,
        }

    def resume(self) -> str:
        return (f"{self.participants_crees} participant(s) cree(s), "
                f"{self.participants_mis_a_jour} mis a jour ; "
                f"{self.blocs_crees} bloc(s) cree(s), {self.blocs_mis_a_jour} mis a jour ; "
                f"{len(self.ignores)} ligne(s) ignoree(s)")


def _texte(ligne: list, index: int) -> str | None:
    """Lecture tolérante : une colonne absente vaut None, pas une exception."""
    if index >= len(ligne):
        return None
    valeur = str(ligne[index]).strip()
    return valeur or None


def importer_participants(comp: Competition, classeur, rapport: Rapport) -> None:
    lignes = classeur.lire(LISTES_ONGLET, LISTES_PLAGE)

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

        nom = _texte(ligne, I_NOM) or nom_complet
        prenom = _texte(ligne, I_PRENOM)
        club = _texte(ligne, I_CLUB)
        categorie = _texte(ligne, I_CATEGORIE)

        # Facultatif, mais on le dit — c'est ce qui manquait avant.
        if not categorie:
            rapport.avertissements.append(
                f"Listes L{n} : « {nom_complet} » sans categorie (importe quand meme)")
        if not club:
            rapport.avertissements.append(
                f"Listes L{n} : « {nom_complet} » sans club (importe quand meme)")

        p = Participant.query.filter_by(competition_id=comp.id, dossard=dossard).first()
        if p and p.source == SOURCE_MANUEL:
            # ⚠️ Spec 013. Un participant ajoute A LA MAIN pendant la competition
            # porte un dossard attribue par le serveur. Si le classeur apporte
            # plus tard le MEME numero, l'ecraser remplacerait son nom, son club
            # et sa categorie -- et ses reussites, attachees a la ligne,
            # changeraient de proprietaire SANS QUE RIEN NE LE DISE.
            #
            # On refuse, et on le signale. Le rapport d'import existe pour ca :
            # l'organisateur tranche, en connaissance de cause.
            rapport.ignores.append(
                f"Listes L{n} : le dossard {dossard} est deja porte par "
                f"« {p.nom_complet} », ajoute a la main. Ligne du classeur "
                f"ignoree -- verifier lequel des deux garde ce numero.")
            continue
        if p:
            avant = (p.nom, p.prenom, p.club, p.categorie)
            p.nom, p.prenom, p.club, p.categorie = nom, prenom, club, categorie
            if (p.nom, p.prenom, p.club, p.categorie) != avant:
                rapport.participants_mis_a_jour += 1
            db.session.add(p)
        else:
            db.session.add(Participant(
                competition_id=comp.id, nom=nom, prenom=prenom, club=club,
                categorie=categorie, dossard=dossard, source=SOURCE_CLASSEUR))
            rapport.participants_crees += 1

    db.session.commit()


def importer_blocs(comp: Competition, classeur, rapport: Rapport) -> None:
    lignes = classeur.lire(PLAN_ONGLET, PLAN_PLAGE)
    if not lignes:
        rapport.ignores.append("Plan : aucune ligne lue")
        return

    entete, lignes = lignes[0], lignes[1:]
    noms_circuits = {i: _texte(entete, i) for i in I_CIRCUITS}
    if not any(noms_circuits.values()):
        raise ErreurClasseur(
            f"Plan L{PLAN_LIGNE_ENTETE} : aucun nom de circuit dans les colonnes "
            f"J, L, N. La structure du classeur a change — import interrompu, "
            f"rien n'a ete modifie.")

    circuits: dict[str, Circuit] = {}
    for nom in filter(None, noms_circuits.values()):
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

        bloc = Bloc.query.filter_by(competition_id=comp.id, tag=tag).first()
        if bloc:
            if (bloc.numero, bloc.couleur) != (numero, couleur):
                bloc.numero, bloc.couleur = numero, couleur
                rapport.blocs_mis_a_jour += 1
            db.session.add(bloc)
        else:
            bloc = Bloc(competition_id=comp.id, tag=tag, numero=numero,
                        zone=zone, couleur=couleur)
            db.session.add(bloc)
            rapport.blocs_crees += 1
        db.session.flush()

        # Rattachement aux circuits : une croix dans la colonne du circuit.
        for i in I_CIRCUITS:
            nom_circuit = noms_circuits.get(i)
            if not nom_circuit or not _texte(ligne, i):
                continue
            c = circuits[nom_circuit]
            lien = BlocCircuit.query.filter_by(bloc_id=bloc.id, circuit_id=c.id).first()
            if not lien:
                db.session.add(BlocCircuit(bloc_id=bloc.id, circuit_id=c.id))

    db.session.commit()


def importer(comp: Competition, classeur=None) -> Rapport:
    """Importe participants et blocs. Idempotent : rejouable sans rien dupliquer.

    Le rejeu est ce qui permet de reprendre une correction faite dans le
    classeur — un dossard changé, une catégorie corrigée — ce que l'ancienne
    version ne faisait jamais (elle n'ajoutait que les noms absents).
    """
    cl = classeur or ClasseurGoogle(comp.spreadsheet_id)
    rapport = Rapport()

    importer_blocs(comp, cl, rapport)
    importer_participants(comp, cl, rapport)

    comp.catalogue_version = (comp.catalogue_version or 0) + 1
    db.session.add(comp)
    db.session.commit()

    logger.info("import du classeur : %s", rapport.resume())
    return rapport
