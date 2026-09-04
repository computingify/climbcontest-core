"""Relever les inscriptions et remplir la salle d'attente — spec 008.

Le relevé lit des **articles** (`item`), jamais des commandes. C'est le point
qui décide de tout le reste : une commande peut porter plusieurs inscrits — un
parent qui inscrit deux enfants — et importer par commande perdrait le second,
silencieusement.

## Ce qui empêche de réimporter

`UniqueConstraint(competition_id, article_id)`, en base. **Pas** un contrôle
dans ce fichier : le fil repasse sur les mêmes articles toutes les soixante
secondes — la fenêtre `from` a même un recouvrement volontaire de cinq minutes —
et un contrôle applicatif finit par se contourner par un chemin qu'on n'avait
pas prévu.

## Un article, un commit

Cent articles qui passent et un qui échoue laissent cent inscriptions écrites,
pas zéro. C'est le comportement du `Rapport` de l'import du classeur, et pour la
même raison : **un import muet qui perd un grimpeur est pire qu'un import
bruyant**.
"""

import logging
import re
from datetime import datetime

from .. import categories, formatage
from ..bareme import reference as reference_de, unders as unders_de
from ..contest import ajouter_participant_numerote, incrementer_catalogue
from ..cycle import lire_options
from ..extensions import db
from ..models import (
    A_IMPRIMER, A_TRANCHER, IGNOREE, Inscription,
    MOTIF_ANNEE_ABSENTE, MOTIF_ANNEE_HORS_BAREME, MOTIF_ANNEE_ILLISIBLE,
    MOTIF_ANNULEE,
    MOTIF_CLUB_DIFFERENT, MOTIF_GENRE_INDETERMINE, MOTIF_SANS_NOM,
    Participant, SOURCE_HELLOASSO,
)
from . import rapprochement
from .client import ClientHelloAsso, ErreurHelloAsso

logger = logging.getLogger(__name__)

#: Les états d'article qui valent inscription. Tous les autres — `Canceled`,
#: `Refused`, `Abandoned`, `Deleted`, `Waiting` — n'en produisent pas.
ETATS_VALIDES = ("Processed", "Registered")


class Rapport:
    """Ce qu'un relevé a fait. Un import muet est un import dangereux."""

    def __init__(self):
        self.vus = 0
        self.nouvelles = 0
        self.deja_connues = 0
        self.rattachees = 0
        self.en_attente = 0
        self.annulees = 0
        self.erreurs = []

    def to_dict(self) -> dict:
        return {
            "vus": self.vus, "nouvelles": self.nouvelles,
            "deja_connues": self.deja_connues, "rattachees": self.rattachees,
            "en_attente": self.en_attente, "annulees": self.annulees,
            "erreurs": self.erreurs,
        }

    def resume(self) -> str:
        return (f"{self.vus} article(s), {self.nouvelles} nouvelle(s), "
                f"{self.deja_connues} deja connue(s), {self.en_attente} en attente")


# --- Lire un article ---------------------------------------------------------

def reglages(comp) -> dict:
    return lire_options(comp).get("helloasso") or {}


def _champ(article: dict, nom_du_champ: str | None):
    """La réponse à un champ personnalisé, par son nom.

    Les `customFields` n'arrivent que si l'appel portait `withDetails=true` —
    sans quoi il n'y a ni année, ni genre, ni club. La fonction rend None au
    lieu de lever : l'inscription part alors en attente, ce qui se voit, plutôt
    que le relevé entier ne tombe.
    """
    if not nom_du_champ:
        return None
    for champ in article.get("customFields") or []:
        if (champ.get("name") or "").strip().lower() == nom_du_champ.strip().lower():
            return champ.get("answer")
    for option in article.get("options") or []:
        for champ in option.get("customFields") or []:
            if (champ.get("name") or "").strip().lower() == nom_du_champ.strip().lower():
                return champ.get("answer")
    return None


def annee_de(reponse) -> int | None:
    """L'ANNÉE, extraite de ce qu'un parent a tapé — décision D9.

    HelloAsso rend ce champ en texte, et le format dépend du formulaire :
    « 2015 », « 12/04/2015 », « 2015-04-12T00:00:00+02:00 ». On ne garde que
    l'année, et pour deux raisons : c'est tout ce que la règle FFME demande, et
    c'est la donnée la plus réduite qui la satisfasse — il s'agit de mineurs.
    """
    if reponse is None:
        return None
    texte = str(reponse).strip()
    if not texte:
        return None
    # Une suite de quatre chiffres qui ressemble a une annee : on prend la
    # PREMIERE qui tient dans une fourchette plausible. « 12/04/2015 » donne
    # 2015, « 2015-04-12 » aussi.
    for trouve in re.findall(r"\d{4}", texte):
        annee = int(trouve)
        if 1900 <= annee <= 2100:
            return annee
    return None


def genre_de(reponse, table: dict) -> str | None:
    """« Fille » → « F ». Une réponse inconnue rend None, **jamais « H »**.

    « Fille », « F », « Féminin » sont trois écritures de la même chose, et
    aucune règle générale ne les couvre toutes : c'est l'organisateur qui les
    range, une fois, depuis la console. Prendre une valeur par défaut ferait
    entrer des grimpeuses dans un classement masculin sans que rien ne le dise.
    """
    if reponse is None:
        return None
    brut = str(reponse).strip()
    for vue, range_en in (table or {}).items():
        if vue.strip().lower() == brut.lower():
            return (range_en or "").strip() or None
    return None


def lire_article(article: dict, commande: dict, config: dict,
                 ref: int, liste_unders) -> dict:
    """Un article HelloAsso → ce qu'on en garde. Rien de plus.

    ⚠️ Le payeur ne passe pas. Ni son nom, ni son courriel, ni son adresse, ni
    son téléphone — décision D5. Seul le nom de l'inscrit sert de repli quand
    l'article n'a pas d'`user`, et l'inscription est alors mise en attente
    plutôt que d'inventer un participant.
    """
    champs = config.get("champs") or {}
    utilisateur = article.get("user") or {}

    nom = formatage.nom(utilisateur.get("lastName"))
    prenom = formatage.nom(utilisateur.get("firstName"))
    sans_nom = False
    if not nom:
        payeur = commande.get("payer") or {}
        nom = formatage.nom(payeur.get("lastName"))
        prenom = formatage.nom(payeur.get("firstName"))
        sans_nom = True

    reponse_annee = _champ(article, champs.get("naissance"))
    annee = annee_de(reponse_annee)
    genre = genre_de(_champ(article, champs.get("genre")),
                     config.get("genre_valeurs") or {})
    club = formatage.club(_champ(article, champs.get("club")))

    circuit = (categories.circuit(annee, ref, liste_unders)
               if annee is not None else None)
    # La categorie est faite de DEUX morceaux : le circuit vient de l'annee, le
    # genre d'un champ du formulaire. Il en manque un, il n'y a pas de
    # categorie -- « U13 » tout seul, a cote de « U13 F » et « U13 H »,
    # fabriquerait un classement d'une personne.
    categorie = (formatage.categorie(f"{circuit} {genre}")
                 if circuit and genre else None)

    motif = None
    if sans_nom or not nom:
        motif = MOTIF_SANS_NOM
    elif annee is None:
        # « Absente » et « illisible » ne se disent pas pareil : envoyer
        # chercher un champ vide quelqu'un qui a tape « 2916 » lui ferait
        # perdre le seul moment ou il peut corriger.
        motif = (MOTIF_ANNEE_ILLISIBLE if str(reponse_annee or "").strip()
                 else MOTIF_ANNEE_ABSENTE)
    elif circuit is None:
        motif = MOTIF_ANNEE_HORS_BAREME
    elif genre is None:
        motif = MOTIF_GENRE_INDETERMINE

    horodatage = (article.get("meta") or {}).get("updatedAt") \
        or (commande.get("meta") or {}).get("updatedAt")

    return {
        "article_id": article.get("id"),
        "commande_id": commande.get("id"),
        "nom": nom, "prenom": prenom,
        "annee_naissance": annee,
        "club": club,
        "categorie": categorie if not motif else None,
        "etat_helloasso": article.get("state"),
        "maj_le": _horodatage(horodatage),
        "motif": motif,
    }


def _horodatage(valeur) -> datetime | None:
    if not valeur:
        return None
    try:
        # HelloAsso rend un ISO 8601 avec fuseau. On le range en heure naive :
        # cette colonne ne sert qu'a faire avancer un curseur, jamais a
        # comparer deux dates de provenances differentes.
        return datetime.fromisoformat(str(valeur)).replace(tzinfo=None)
    except ValueError:
        return None


# --- Poser une inscription ---------------------------------------------------

def _existants(comp) -> list:
    """Participants **et** inscriptions : les deux origines se rencontrent ici.

    Sans les inscriptions, deux articles pour la même personne — celui du matin
    mis en attente, celui de midi — créeraient deux participants dès que le
    premier serait tranché.
    """
    gens = [rapprochement.Personne(p.id, p.nom, p.prenom, p.club, p.categorie)
            for p in Participant.query.filter_by(competition_id=comp.id)]
    return gens


def poser(comp, lu: dict, rapport: Rapport) -> Inscription:
    """Écrit une inscription et, si rien n'est douteux, crée le participant."""
    inscription = Inscription.query.filter_by(
        competition_id=comp.id, article_id=lu["article_id"]).first()

    annule = (lu.get("etat_helloasso") or "") not in ETATS_VALIDES

    if inscription is None:
        if annule:
            # Un article annule qu'on n'a jamais vu ne cree rien : il n'y a
            # personne a inscrire, et rien a signaler a personne.
            return None
        inscription = Inscription(competition_id=comp.id,
                                  article_id=lu["article_id"])
        db.session.add(inscription)
        nouvelle = True
    else:
        nouvelle = False

    for champ in ("commande_id", "nom", "prenom", "annee_naissance", "club",
                  "categorie", "etat_helloasso", "maj_le"):
        setattr(inscription, champ, lu[champ])

    if annule:
        # ⚠️ On ne supprime RIEN. Le participant porte peut-etre deja des
        # reussites, et le retirer tout seul est exactement le genre de geste
        # qu'on ne fait pas. La ligne remonte, un humain decide.
        if inscription.etat != IGNOREE:
            inscription.etat = A_TRANCHER
            inscription.motif = MOTIF_ANNULEE
            rapport.annulees += 1
        db.session.commit()
        return inscription

    if not nouvelle and inscription.participant_id:
        rapport.deja_connues += 1
        db.session.commit()
        return inscription

    if lu["motif"]:
        inscription.etat = A_TRANCHER
        inscription.motif = lu["motif"]
        rapport.en_attente += 1
        db.session.commit()
        return inscription

    verdict = rapprochement.confronter(
        rapprochement.Personne(None, lu["nom"], lu["prenom"], lu["club"],
                               lu["categorie"]),
        _existants(comp))

    if verdict.quoi == rapprochement.MEME_PERSONNE:
        participant = db.session.get(Participant, verdict.identifiant)
        inscription.participant_id = participant.id
        # On COMPLETE ce qui manque, on n'ecrase jamais ce qui est la : la
        # console fait autorite sur ce que quelqu'un y a saisi.
        if participant.annee_naissance is None:
            participant.annee_naissance = lu["annee_naissance"]
        if not participant.club:
            participant.club = lu["club"]
        db.session.add(participant)
        inscription.etat = A_IMPRIMER
        inscription.motif = None
        rapport.rattachees += 1
        db.session.commit()
        return inscription

    if verdict.quoi == rapprochement.A_TRANCHER:
        inscription.etat = A_TRANCHER
        inscription.motif = verdict.motif or MOTIF_CLUB_DIFFERENT
        rapport.en_attente += 1
        db.session.commit()
        return inscription

    # Rien d'ambigu : le participant est cree par le MEME chemin que le bouton
    # « Ajouter » de la console (decision D2). Deux chemins de creation
    # divergeraient au premier correctif.
    participant = ajouter_participant_numerote(
        nom=lu["nom"], prenom=lu["prenom"], club=lu["club"],
        categorie=lu["categorie"], source=SOURCE_HELLOASSO,
        annee_naissance=lu["annee_naissance"])
    inscription.participant_id = participant.id
    inscription.etat = A_IMPRIMER
    inscription.motif = None
    rapport.nouvelles += 1
    db.session.commit()
    return inscription


# --- Le relevé ---------------------------------------------------------------

def dernier_vu(comp) -> datetime | None:
    """L'heure du dernier article relevé, qui sert de curseur."""
    ligne = (Inscription.query.filter_by(competition_id=comp.id)
             .order_by(Inscription.maj_le.desc()).first())
    return ligne.maj_le if ligne else None


def relever(comp, client=None, tout: bool = False) -> Rapport:
    """Relève les articles arrivés ou modifiés depuis le dernier passage.

    `tout=True` repart du début : c'est ce que fait le bouton « rejouer les
    inscriptions en attente » après une correction du barème. L'idempotence
    rend l'opération gratuite — d'où le fait qu'on ne garde aucune copie locale
    des articles (décision D5).
    """
    config = reglages(comp)
    if not config.get("form_slug"):
        raise ErreurHelloAsso(
            "Aucun formulaire HelloAsso choisi pour cette competition.", code=409)

    client = client or ClientHelloAsso()
    ref = reference_de(comp)
    liste_unders = unders_de(comp)
    rapport = Rapport()

    depuis = None if tout else dernier_vu(comp)
    commandes_vues = {}

    for article in client.articles(config.get("organisation") or "",
                                   config["form_type"], config["form_slug"],
                                   depuis=depuis):
        rapport.vus += 1
        try:
            # Les articles rendus par /items portent leur commande en creux :
            # `order` quand l'API la joint, sinon on ne dispose que de l'id.
            commande = article.get("order") or commandes_vues.get(
                (article.get("order") or {}).get("id")) or {}
            lu = lire_article(article, commande, config, ref, liste_unders)
            if lu["article_id"] is None:
                rapport.erreurs.append("article sans identifiant, ignore")
                continue
            poser(comp, lu, rapport)
        except Exception as e:                       # noqa: BLE001
            # Un article qui echoue ne doit pas emporter les cent autres.
            db.session.rollback()
            rapport.erreurs.append(f"article {article.get('id')} : {e}")
            logger.warning("releve HelloAsso : article %s ignore (%s)",
                           article.get("id"), e)

    if rapport.nouvelles or rapport.rattachees:
        incrementer_catalogue(comp)
        db.session.commit()

    logger.info("releve HelloAsso : %s", rapport.resume())
    return rapport
