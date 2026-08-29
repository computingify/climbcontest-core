"""Modèle de données ClimbContest.

Trois principes, tirés de ce que le terrain impose
(docs/contraintes-metier.md) :

1. **L'identité d'un participant est son `id`, jamais son dossard.** Un dossard
   se réaffecte en cours de compétition — on récupère celui d'un inscrit qui
   n'est pas venu plutôt que d'en imprimer un nouveau.
2. **Tout porte une compétition.** La base est multi-compétition : on consulte
   les archives des éditions passées.
3. **Une réussite est une ligne en base, pas un élément volatil.** C'est ce qui
   change tout par rapport à la version précédente, où elle transitait par une
   file en RAM.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from .extensions import db

# --- Statuts ----------------------------------------------------------------
PREPARATION, EN_COURS, TERMINEE = "preparation", "en_cours", "terminee"

# --- Origine d'une donnée ---------------------------------------------------
SOURCE_CLASSEUR, SOURCE_MANUEL, SOURCE_HELLOASSO = "classeur", "manuel", "helloasso"
SOURCE_SCAN = "scan"


class Competition(db.Model):
    """Une compétition — une journée, un classeur, un jeu de participants."""

    __tablename__ = "competition"

    id = Column(Integer, primary_key=True)
    nom = Column(String(120), nullable=False)
    date = Column(Date, nullable=False, default=date.today)
    statut = Column(String(20), nullable=False, default=PREPARATION)
    active = Column(Boolean, nullable=False, default=False)

    # L'identifiant du classeur vit ICI, plus jamais en dur dans le code : c'est
    # le geste le plus souvent oublié d'une édition à l'autre.
    spreadsheet_id = Column(String(80))

    # Incrémentée à chaque changement de participant ou de bloc. C'est ce qui
    # permet à l'application juge de ne retélécharger qu'un delta (spec 003).
    catalogue_version = Column(Integer, nullable=False, default=1)

    # Options propres à l'édition : validation par couleur et sa variante.
    # JSON en texte : SQLite comme PostgreSQL, sans extension.
    options = Column(Text, nullable=False, default="{}")

    creee_le = Column(DateTime, nullable=False, default=func.now())

    participants = relationship("Participant", back_populates="competition",
                                cascade="all, delete-orphan")
    blocs = relationship("Bloc", back_populates="competition",
                         cascade="all, delete-orphan")
    circuits = relationship("Circuit", back_populates="competition",
                            cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Competition {self.id} {self.nom!r}>"


class Circuit(db.Model):
    """Un circuit = une tranche d'âge. Filles et garçons grimpent le même.

    « U13 F » et « U13 H » sont deux catégories du circuit « U13 » : mêmes blocs,
    classements séparés.
    """

    __tablename__ = "circuit"
    __table_args__ = (UniqueConstraint("competition_id", "nom", name="uq_circuit"),)

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competition.id"), nullable=False)
    nom = Column(String(20), nullable=False)          # « U13 »

    competition = relationship("Competition", back_populates="circuits")
    blocs = relationship("BlocCircuit", back_populates="circuit",
                         cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Circuit {self.nom!r}>"


class Participant(db.Model):
    """Un grimpeur inscrit.

    `id` est l'identité. `dossard` est un attribut — celui qui est imprimé sur
    le QR code — qui peut être absent, et qui peut changer de main tant qu'aucune
    réussite n'y est attachée.
    """

    __tablename__ = "participant"
    __table_args__ = (
        # Un dossard est unique DANS une compétition, pas globalement.
        UniqueConstraint("competition_id", "dossard", name="uq_dossard_competition"),
    )

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competition.id"), nullable=False)

    nom = Column(String(80), nullable=False)
    prenom = Column(String(80))
    # Nullables volontairement : une ligne de classeur sans club ni catégorie ne
    # doit pas faire disparaître le grimpeur en silence (risque R5).
    club = Column(String(80))
    categorie = Column(String(20))                    # « U13 F »

    dossard = Column(Integer)                         # nullable : inscrit absent
    present = Column(Boolean, nullable=False, default=False)
    source = Column(String(20), nullable=False, default=SOURCE_CLASSEUR)

    cree_le = Column(DateTime, nullable=False, default=func.now())

    competition = relationship("Competition", back_populates="participants")
    reussites = relationship("Success", back_populates="participant",
                             cascade="all, delete-orphan")

    @property
    def nom_complet(self) -> str:
        return f"{self.nom} {self.prenom}".strip() if self.prenom else self.nom

    @property
    def circuit(self) -> str | None:
        """« U13 F » → « U13 ». Le classement se calcule par circuit."""
        if not self.categorie:
            return None
        return self.categorie.rsplit(" ", 1)[0] if " " in self.categorie else self.categorie

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dossard": self.dossard,
            "nom": self.nom_complet,
            "club": self.club,
            "categorie": self.categorie,
        }

    def __repr__(self) -> str:
        return f"<Participant {self.id} dossard={self.dossard} {self.nom_complet!r}>"


class Bloc(db.Model):
    """Un bloc de la compétition.

    `tag` est le contenu du QR code (« ZJ6 » = zone Z + numéro J6).
    `numero` est la ligne du bloc dans l'onglet `Import` du classeur.
    """

    __tablename__ = "bloc"
    __table_args__ = (
        UniqueConstraint("competition_id", "tag", name="uq_bloc_tag"),
        UniqueConstraint("competition_id", "numero", name="uq_bloc_numero"),
    )

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competition.id"), nullable=False)

    tag = Column(String(20), nullable=False)          # « ZJ6 », le QR code
    numero = Column(Integer, nullable=False)          # ligne dans l'onglet Import
    zone = Column(String(5))                          # « Z »
    couleur = Column(String(20))                      # « Jaune » … « Noir »

    competition = relationship("Competition", back_populates="blocs")
    circuits = relationship("BlocCircuit", back_populates="bloc",
                            cascade="all, delete-orphan")
    reussites = relationship("Success", back_populates="bloc",
                             cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tag": self.tag,
            "numero": self.numero,
            "couleur": self.couleur,
            "circuits": [bc.circuit.nom for bc in self.circuits],
        }

    def __repr__(self) -> str:
        return f"<Bloc {self.tag!r} n°{self.numero}>"


class BlocCircuit(db.Model):
    """Quels blocs comptent pour quel circuit.

    Sans ce lien, une réussite sur un bloc hors du circuit du grimpeur serait
    comptée au classement — ce que le classeur ne fait pas. C'est l'écart qui
    gonflait le score de 17 grimpeurs sur 98 sur l'édition de novembre 2025.
    """

    __tablename__ = "bloc_circuit"
    __table_args__ = (UniqueConstraint("bloc_id", "circuit_id", name="uq_bloc_circuit"),)

    id = Column(Integer, primary_key=True)
    bloc_id = Column(Integer, ForeignKey("bloc.id"), nullable=False)
    circuit_id = Column(Integer, ForeignKey("circuit.id"), nullable=False)

    bloc = relationship("Bloc", back_populates="circuits")
    circuit = relationship("Circuit", back_populates="blocs")


class Success(db.Model):
    """Une réussite : ce grimpeur a réussi ce bloc.

    `sheet_synced_at` est la pièce maîtresse de la spec 002. Il remplace la file
    en mémoire vive : tant qu'il vaut NULL, la réussite reste à envoyer au
    classeur. Un redémarrage, un crash ou une panne de l'API Google ne la font
    plus disparaître — le travail à faire est une requête SQL.
    """

    __tablename__ = "success"
    __table_args__ = (
        # C'est cette contrainte qui rend l'envoi idempotent : un double appui
        # sur « Envoyer », ou deux juges qui valident le même passage, ne
        # produisent qu'une seule réussite.
        UniqueConstraint("participant_id", "bloc_id", name="uq_reussite"),
    )

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey("participant.id"), nullable=False)
    bloc_id = Column(Integer, ForeignKey("bloc.id"), nullable=False)

    horodatage = Column(DateTime, nullable=False, default=func.now())
    source = Column(String(20), nullable=False, default=SOURCE_SCAN)
    sheet_synced_at = Column(DateTime)                # NULL = pas encore au classeur

    # Le dossard tel que le juge l'a scanne, et l'heure a laquelle il l'a fait.
    # Les deux servent a une seule chose : detecter apres coup qu'une reussite
    # est arrivee APRES que son dossard ait change de main. Avec la file
    # d'attente de la spec 003, une reussite peut rester plusieurs secondes dans
    # le telephone ; si le dossard est reaffecte entre-temps, elle se colle au
    # nouveau porteur. Decision d'Adrien du 28/08 : on l'AUTORISE, on ne bloque
    # pas. Ces deux colonnes rendent le cas visible plutot que silencieux.
    #
    # `scanne_le` vient du client, donc d'une horloge qu'on ne controle pas :
    # il est INDICATIF et ne sert jamais a trier. `horodatage` fait foi.
    dossard_scanne = Column(Integer)
    scanne_le = Column(DateTime)

    # Qui a saisi, quand c'est une saisie manuelle. NULL pour un scan. Ce qu'on
    # trace ici, c'est l'INTERVENTION HUMAINE sur les donnees -- le jour ou un
    # score est conteste, savoir qu'une reussite a ete ajoutee a la main par
    # untel a 14 h 32 est la seule chose qui permette de trancher.
    #
    # Cette colonne identifie donc QUELQU'UN. Les trois suivantes, non : elles
    # identifient un TELEPHONE. Ne pas confondre les deux -- un telephone change
    # de main dans la journee, et « Mur jaune » designe un poste, pas un
    # benevole.
    saisie_par = Column(String(60))

    # De quel telephone vient cette reussite (spec 011). NULL pour une saisie
    # manuelle ou un import : ils n'ont pas d'appareil.
    #
    # `appareil_nom` est DENORMALISE exprès : c'est le nom au moment de l'envoi.
    # Renommer un telephone en pleine competition ne doit pas reecrire
    # l'histoire de ce qu'il a deja envoye.
    #
    # `ref_client` est la reference que le telephone a donnee au scan. Ce n'est
    # PAS une cle -- l'idempotence reste portee par `uq_reussite`. C'est ce qui
    # permet a un juge de lire six caracteres a voix haute et a un organisateur
    # de repondre « oui, elle est arrivee ».
    appareil_id = Column(String(40), index=True)
    appareil_nom = Column(String(60))
    ref_client = Column(String(40), index=True)

    participant = relationship("Participant", back_populates="reussites")
    bloc = relationship("Bloc", back_populates="reussites")

    def __repr__(self) -> str:
        etat = "synchronisee" if self.sheet_synced_at else "EN ATTENTE"
        return f"<Success p={self.participant_id} b={self.bloc_id} {etat}>"


class ReaffectationDossard(db.Model):
    """Journal des dossards qui ont changé de main.

    Une seule raison d'exister : rendre traçable le cas que la file d'attente
    de la spec 003 rend possible. Un juge scanne le dossard 42 à 10 h 04 ; la
    réussite reste huit secondes dans son téléphone ; entre-temps un
    organisateur donne le 42 à quelqu'un d'autre parce qu'il « n'a aucun
    résultat ». La réussite arrive et se colle au nouveau porteur.

    Adrien a tranché le 28/08 : **on autorise**. Ce journal ne l'empêche donc
    pas — il permet de le retrouver, en comparant l'heure du scan à l'heure de
    la réaffectation. Sans lui, la réussite serait simplement attribuée au
    mauvais grimpeur et personne ne s'en apercevrait jamais.
    """

    __tablename__ = "reaffectation_dossard"

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competition.id"), nullable=False)
    dossard = Column(Integer, nullable=False)
    ancien_participant_id = Column(Integer, ForeignKey("participant.id"))
    nouveau_participant_id = Column(Integer, ForeignKey("participant.id"), nullable=False)
    effectuee_le = Column(DateTime, nullable=False, default=func.now())

    def __repr__(self) -> str:
        return (f"<Reaffectation dossard={self.dossard} "
                f"{self.ancien_participant_id} -> {self.nouveau_participant_id}>")


# --- Comptes, posés dès maintenant pour éviter une migration en spec 005 -----

class Utilisateur(db.Model):
    """Compte d'accès à la console d'administration.

    Modèle repris de guestFlow : mot de passe haché, rôles en table de jointure
    (plusieurs rôles par personne), contrôle d'accès fail-closed.
    """

    __tablename__ = "utilisateur"

    id = Column(Integer, primary_key=True)
    identifiant = Column(String(60), nullable=False, unique=True)
    mot_de_passe_hache = Column(String(255), nullable=False)
    nom_affiche = Column(String(80))
    actif = Column(Boolean, nullable=False, default=True)
    cree_le = Column(DateTime, nullable=False, default=func.now())

    roles = relationship("UtilisateurRole", back_populates="utilisateur",
                         cascade="all, delete-orphan")

    def a_le_role(self, role: str) -> bool:
        return any(r.role == role for r in self.roles)


class UtilisateurRole(db.Model):
    __tablename__ = "utilisateur_role"
    __table_args__ = (UniqueConstraint("utilisateur_id", "role", name="uq_utilisateur_role"),)

    id = Column(Integer, primary_key=True)
    utilisateur_id = Column(Integer, ForeignKey("utilisateur.id"), nullable=False)
    role = Column(String(30), nullable=False)         # admin · organisateur · lecture

    utilisateur = relationship("Utilisateur", back_populates="roles")


class TentativeConnexion(db.Model):
    """Les echecs de connexion, par adresse. Le frein anti-force-brute.

    EN BASE, et non en memoire : avec quatre workers gunicorn, un compteur par
    processus diviserait la protection par quatre -- un robot n'aurait qu'a
    insister pour tomber sur un worker au compteur vierge. Il survit aussi aux
    redemarrages, ce qui compte : relancer le service ne doit pas offrir une
    ardoise propre a qui essaie des mots de passe.

    Le volume est negligeable : une ligne par adresse ayant echoue, effacee des
    qu'une connexion reussit.
    """

    __tablename__ = "tentative_connexion"

    adresse = Column(String(64), primary_key=True)
    echecs = Column(Integer, nullable=False, default=0)
    derniere = Column(DateTime, nullable=False, default=func.now())

    def __repr__(self) -> str:
        return f"<TentativeConnexion {self.adresse} x{self.echecs}>"


class Verrou(db.Model):
    """Verrou consultatif porté par la base.

    Le miroir vers le classeur et les migrations ne doivent tourner que dans UN
    processus. Avec quatre workers gunicorn (spec 001), un verrou en mémoire ne
    suffit pas : il faut qu'il soit partagé, donc en base.
    """

    __tablename__ = "verrou"

    nom = Column(String(40), primary_key=True)
    detenu_par = Column(String(80))
    pris_le = Column(DateTime)
