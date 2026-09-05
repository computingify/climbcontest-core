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
#: Une voie saisie par un ouvreur dans la console (spec 044).
SOURCE_CONSOLE = "console"
SOURCE_SCAN = "scan"


def prochaine_version_catalogue() -> int:
    """Un numero de version de catalogue qui n'a jamais servi.

    Un `max(...) + 1` sur TOUTES les competitions, et non un compteur remis a 1
    a chaque edition. Voir le commentaire de `Competition.catalogue_version`
    pour ce que la remise a 1 cassait.

    Tolerant a une base pas encore creee : la valeur de repli est 1, ce qui est
    le cas de la toute premiere competition.
    """
    from sqlalchemy import func
    try:
        maximum = db.session.query(func.max(Competition.catalogue_version)).scalar()
    except Exception:                       # table absente : premier demarrage
        return 1
    return (maximum or 0) + 1


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
    # ⚠️ Globalement croissante, JAMAIS repartie a 1 (correctif du 30/08).
    #
    # Les telephones valident leur catalogue avec un simple entier
    # (`If-None-Match: "3"`). Tant que chaque competition repartait a 1, deux
    # competitions differentes portaient le meme numero : un telephone ayant
    # servi a une competition de test recevait un 304 sur la competition
    # suivante, et gardait la liste de la premiere. Il affichait alors le nom
    # d'un grimpeur de test pour un dossard bien reel -- et le nom affiche est
    # le SEUL controle humain qu'a le juge avant de valider.
    #
    # Le defaut est calcule par `prochaine_version_catalogue()` a la creation :
    # un numero jamais encore servi, donc jamais confondu.
    catalogue_version = Column(Integer, nullable=False,
                               default=lambda: prochaine_version_catalogue())

    # Options propres à l'édition : validation par couleur et sa variante.
    # JSON en texte : SQLite comme PostgreSQL, sans extension.
    options = Column(Text, nullable=False, default="{}")

    creee_le = Column(DateTime, nullable=False, default=func.now())

    participants = relationship("Participant", back_populates="competition",
                                cascade="all, delete-orphan")
    inscriptions = relationship("Inscription", back_populates="competition",
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

    # Spec 043 — le droit d'opposition (art. 21 RGPD). Vrai quand ce grimpeur,
    # ou son representant legal, refuse que son nom paraisse sur la page
    # publique. La ligne reste au classement, avec son rang et son score : elle
    # s'y affiche « Dossard N ».
    #
    # ⚠️ « refusee » et non « autorisee ». L'article 21 est un droit
    # d'OPPOSITION, pas un consentement : on publie sauf refus. Nomme dans
    # l'autre sens, le champ ferait taire tous ceux qui n'ont rien exprime --
    # c'est-a-dire presque tous.
    publication_refusee = Column(Boolean, nullable=False, default=False)

    # L'ANNÉE de naissance, et rien de plus — décision D9 du 03/09.
    #
    # C'est tout ce que la règle FFME demande (`categories.py`) : la catégorie
    # se calcule sur l'année, jamais sur la date, et personne ne change de
    # catégorie le jour de son anniversaire. Garder le jour et le mois serait
    # donc conserver la date de naissance d'un mineur sans qu'aucun calcul ne
    # s'en serve — exactement ce que la règle 7 du CLAUDE.md demande d'éviter.
    #
    # Nullable, et le restera : les participants venus du classeur n'en ont pas,
    # et un import de classeur ne doit pas se mettre à échouer pour ça.
    annee_naissance = Column(Integer)

    # Quelqu'un a rangé cette personne à la main, contre ce que le barème
    # calcule. C'est la trace d'un GESTE, pas un état du monde — même raison
    # d'être que `Success.hors_circuit_force`.
    #
    # Sans elle, « Appliquer le barème à tous les inscrits » défait
    # silencieusement le travail de quelqu'un qui connaissait le cas
    # particulier. Avec elle, l'aperçu les compte à part et il faut forcer
    # explicitement.
    categorie_forcee = Column(Boolean)

    # Les champs que quelqu'un a corriges DANS LA CONSOLE, separes par des
    # virgules : « nom,club ». Decision d'Adrien du 05/09 -- « la console gagne,
    # definitivement ».
    #
    # Sans cette trace, l'import du classeur refait sa ligne a l'identique au
    # tour suivant et la correction disparait sans un mot : le club retape
    # revient a son ancienne orthographe, la categorie remise a la main
    # redevient fausse. Personne ne le voit, et personne ne peut le voir --
    # c'est le pire des defauts silencieux.
    #
    # C'est la trace d'un GESTE, comme `categorie_forcee` et
    # `Success.hors_circuit_force`. Une colonne texte plutot que quatre
    # booleens : les champs editables changeront encore, la forme non.
    champs_forces = Column(String(120))

    cree_le = Column(DateTime, nullable=False, default=func.now())

    competition = relationship("Competition", back_populates="participants")
    reussites = relationship("Success", back_populates="participant",
                             cascade="all, delete-orphan")
    # ⚠️ SANS cascade, volontairement. Une inscription est la trace de ce que
    # HelloAsso a dit ; supprimer le participant qu'elle a créé ne doit pas
    # l'effacer, sinon le relevé suivant le recréerait aussitôt — l'article
    # serait redevenu inconnu. Elle se détache (`participant_id = NULL`) et
    # retourne dans la pile « à trancher ».
    inscriptions = relationship("Inscription", back_populates="participant")

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
        """Ce que voient les téléphones des juges.

        ⚠️ **Ne rien ajouter ici sans y penser à deux fois.** Cette méthode
        alimente `/api/v2/contest/catalogue`, donc les vingt-cinq téléphones de
        la salle. Deux raisons de la garder maigre :

        1. **La taille.** 98 participants font 6 à 8 ko compressés ; le
           catalogue est retéléchargé à chaque changement de version.
        2. **Les données personnelles.** `annee_naissance` est délibérément
           ABSENTE : l'année de naissance d'un mineur n'a aucune raison de
           voyager sur vingt-cinq téléphones que le club ne contrôle pas. Le
           juge a besoin d'un nom pour vérifier son scan, pas d'un état civil.

        La console, elle, lit `pour_la_console()`.
        """
        return {
            "id": self.id,
            "dossard": self.dossard,
            "nom": self.nom_complet,
            "club": self.club,
            "categorie": self.categorie,
        }

    # --- Ce que la console a corrige a la main ------------------------------
    #
    # `categorie` a sa propre colonne (`categorie_forcee`) depuis le 04/09, et
    # elle reste : c'est elle que lit « Appliquer le bareme a tous ». Les deux
    # se consultent par la MEME methode -- deux facons de poser la question
    # finiraient par ne plus donner la meme reponse.

    #: Les seuls champs qu'un humain peut corriger dans la liste (spec 008).
    CHAMPS_EDITABLES = ("nom", "prenom", "club", "categorie")

    def est_force(self, champ: str) -> bool:
        """Ce champ a-t-il ete corrige a la main dans la console ?"""
        if champ == "categorie":
            return bool(self.categorie_forcee)
        return champ in (self.champs_forces or "").split(",")

    def forcer(self, champ: str) -> None:
        """Note que ce champ vient de la console. Idempotent."""
        if champ == "categorie":
            self.categorie_forcee = True
            return
        deja = [c for c in (self.champs_forces or "").split(",") if c]
        if champ not in deja:
            deja.append(champ)
        self.champs_forces = ",".join(deja)

    @property
    def sources(self) -> list[str]:
        """D'où vient ce participant — parfois de deux endroits (spec 008).

        `source` dit l'ORIGINE : qui l'a créé. Une inscription HelloAsso
        rattachée après coup à quelqu'un qui venait du classeur ne change pas
        cette origine — mais elle ajoute une provenance, et c'est précisément
        ce qu'on veut montrer : le rapprochement a fait son travail, cette
        personne n'a pas été dupliquée.

        Aucune colonne nouvelle : c'est `source`, plus l'existence d'une
        inscription liée.
        """
        vues = [self.source]
        if any(i.participant_id == self.id for i in (self.inscriptions or [])):
            if SOURCE_HELLOASSO not in vues:
                vues.append(SOURCE_HELLOASSO)
        return vues

    def pour_la_console(self) -> dict:
        """Ce que voit la console d'administration. Jamais servi aux juges."""
        return {
            **self.to_dict(),
            "prenom": self.prenom,
            "present": self.present,
            "annee_naissance": self.annee_naissance,
            "categorie_forcee": bool(self.categorie_forcee),
            "champs_forces": [c for c in self.CHAMPS_EDITABLES if self.est_force(c)],
            "sources": self.sources,
            # Spec 043. Ici et NON dans `to_dict()` : celle-la alimente le
            # catalogue des vingt-cinq telephones des juges et reste maigre --
            # un test echoue si on l'elargit. Une serialisation par audience,
            # jamais une seule qu'on etend.
            "publication_refusee": bool(self.publication_refusee),
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

    # ⚠️ DEUX couleurs, et elles ne servent pas à la même chose.
    #
    # `couleur` est la couleur de DIFFICULTÉ (colonne F du `Plan`) : elle est
    # ordonnée — Jaune < Vert < Bleu < Mauve < Rouge < Noir — et c'est elle que
    # lit la validation par couleur du classement.
    #
    # `couleur_prises` est la couleur des PRISES sur le mur (colonne H). Elle
    # n'est ordonnée par rien et n'entre dans aucun calcul : c'est ce qu'on
    # cherche des yeux quand deux blocs de même difficulté sont dans la même
    # zone. Elle n'était simplement jamais lue avant la spec 019.
    couleur = Column(String(20))                      # « Jaune » … « Noir »
    couleur_prises = Column(String(20))               # « Bleu », « Fluo »…

    # Le rang de la voie DANS SA COULEUR : « V7 » a `numero_couleur = 7`
    # (spec 044). Le nom d'une voie, c'est l'initiale de sa couleur suivie de
    # ce rang, et `tag` vaut zone + nom -- « J » + « V7 » = « JV7 ».
    #
    # NULL tant qu'aucune couleur n'est choisie : une voie sans couleur n'a pas
    # encore de place dans la salle. Elle porte alors un tag de reserve
    # (« J?12 ») qui ne sert qu'a satisfaire `uq_bloc_tag`.
    #
    # ⚠️ A ne pas confondre avec `numero`, juste au-dessus : celui-la est la
    # ligne du bloc dans l'onglet `Import` du classeur, et il ne bouge JAMAIS.
    # La renumerotation ne touche que celui-ci.
    numero_couleur = Column(Integer)

    # D'ou vient cette voie. Meme role que `Participant.source` : savoir ce
    # qu'un import a le droit d'ecraser, et pouvoir dire dans deux ans d'ou
    # venait une ligne.
    #
    # ⚠️ Nullable en base bien que le modele porte un defaut : SQLite refuse
    # `ADD COLUMN ... NOT NULL` sans valeur par defaut sur une table qui a deja
    # des lignes. Celles d'avant la spec 044 valent donc NULL, et c'est la
    # verite -- elles viennent toutes du classeur. Le code lit
    # `bloc.source or SOURCE_CLASSEUR`.
    source = Column(String(20), default=SOURCE_CLASSEUR)

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
            "couleur_prises": self.couleur_prises,
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

    # Le juge a vu « ce bloc n'est pas dans son circuit » et a envoyé quand même
    # (spec 019). C'est une trace du GESTE, pas un état du monde.
    #
    # ⚠️ Nullable et sans défaut, et les trois valeurs disent trois choses
    # différentes :
    #   NULL  — on ne sait pas : une réussite d'avant la spec 019, une saisie
    #           manuelle, un import, un téléphone qui n'envoie pas le champ ;
    #   False — le téléphone a vérifié, et c'était bon ;
    #   True  — le téléphone a vérifié, ce n'était pas bon, et on a forcé.
    # Confondre le premier avec le deuxième ferait dire à la console que tout a
    # été vérifié alors que rien ne l'a été.
    #
    # Le statut COURANT — ce bloc est-il aujourd'hui dans le circuit ? — n'est
    # pas ici : il se calcule à la lecture. Corriger le classeur doit faire
    # disparaître l'anomalie, pas la figer.
    hors_circuit_force = Column(Boolean)

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


# --- Inscriptions en ligne (spec 008) ---------------------------------------

#: Les quatre états d'une inscription. Ils décrivent un **geste physique**, pas
#: un état informatique : derrière chaque ligne il y a un dossard à imprimer et
#: à porter à quelqu'un.
A_TRANCHER, A_IMPRIMER, FAITE, IGNOREE = (
    "a_trancher", "a_imprimer", "faite", "ignoree")
ETATS_INSCRIPTION = (A_TRANCHER, A_IMPRIMER, FAITE, IGNOREE)

#: Pourquoi une inscription attend. C'est ce que la carte affiche.
MOTIF_CLUB_DIFFERENT = "club_different"
MOTIF_ANNEE_ABSENTE = "annee_absente"
#: Le champ portait une reponse, mais on n'en a pas tire d'annee.
#: Distinct de l'absence : dire « annee absente » a quelqu'un qui a
#: tape « 2916 » lui ferait chercher au mauvais endroit.
MOTIF_ANNEE_ILLISIBLE = "annee_illisible"
MOTIF_ANNEE_HORS_BAREME = "annee_hors_bareme"
MOTIF_GENRE_INDETERMINE = "genre_indetermine"
MOTIF_SANS_NOM = "sans_nom"
MOTIF_ANNULEE = "annulee_apres_coup"


class Inscription(db.Model):
    """Une ligne venue de HelloAsso, et ce qu'on en a fait — spec 008.

    **La salle d'attente.** Rien de ce qui vient du réseau n'écrit directement
    dans `participant` : c'est cette table qui décide si un participant est
    créé. Même séparation que la spec 002 entre la base et le classeur — une
    source extérieure est une *entrée*, jamais une autorité.

    Elle survit au participant qu'elle a créé : c'est la trace de ce que la
    plateforme a dit, et la seule chose qui rende le relevé idempotent.

    ⚠️ **Ce qui n'est PAS ici, et c'est délibéré** (décision D5 du 03/09, « le
    strict minimum ») :

    - rien du payeur — ni nom, ni courriel, ni adresse, ni téléphone. Le payeur
      est un parent, et on n'a aucun usage de ses coordonnées ;
    - aucun montant, aucun moyen de paiement, aucun reçu ;
    - **aucune copie du JSON reçu.** Les colonnes ci-dessous *sont*
      l'enregistrement. Pour relire une inscription après correction du barème,
      on redemande l'article à HelloAsso — l'idempotence rend l'opération
      gratuite, et c'est moins de code qu'un rejeu depuis une copie ;
    - le nom du tarif : « pour la compétition tout le monde paye le même »
      (Adrien, 04/09). Il ne discrimine rien.

    `commande_id` reste, parce qu'un entier ne décrit personne. Il sert à deux
    choses réelles : retrouver la fratrie — une commande porte souvent deux
    enfants — et retrouver la commande dans le back-office HelloAsso quand il
    faut joindre quelqu'un, puisqu'on ne garde pas le courriel.
    """

    __tablename__ = "inscription"
    __table_args__ = (
        # ⚠️ L'ANTI-RÉIMPORT TIENT ICI, pas dans le code du relevé.
        #
        # Le fil repasse sur les mêmes articles toutes les soixante secondes —
        # c'est même volontaire, la fenêtre `from=` a un recouvrement de cinq
        # minutes. Sans cette contrainte, chaque tour créerait des doublons.
        # La porter en base plutôt qu'en Python, c'est la même décision que
        # `uq_reussite` : un contrôle applicatif se contourne par un chemin
        # qu'on n'avait pas prévu, une contrainte non.
        #
        # La clé est l'ARTICLE (`item.id`), jamais la commande : une commande
        # peut porter plusieurs inscrits, et s'en servir perdrait le second
        # enfant sans que rien ne le dise.
        UniqueConstraint("competition_id", "article_id", name="uq_inscription_article"),
    )

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competition.id"), nullable=False)

    article_id = Column(Integer, nullable=False)      # item.id chez HelloAsso
    commande_id = Column(Integer)                     # order.id

    etat = Column(String(20), nullable=False, default=A_TRANCHER)
    motif = Column(String(30))
    participant_id = Column(Integer, ForeignKey("participant.id"))

    nom = Column(String(80))
    prenom = Column(String(80))
    annee_naissance = Column(Integer)
    club = Column(String(80))
    categorie = Column(String(20))

    etat_helloasso = Column(String(20))               # Processed, Canceled…
    # L'heure de dernière modification CHEZ EUX. C'est elle qui fait avancer le
    # curseur du relevé — surtout pas notre propre horloge.
    maj_le = Column(DateTime)
    recue_le = Column(DateTime, nullable=False, default=func.now())
    traitee_le = Column(DateTime)
    traitee_par = Column(String(80))

    competition = relationship("Competition", back_populates="inscriptions")
    participant = relationship("Participant", back_populates="inscriptions")

    @property
    def nom_complet(self) -> str:
        return f"{self.nom} {self.prenom}".strip() if self.prenom else (self.nom or "")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "commande_id": self.commande_id,
            "etat": self.etat,
            "motif": self.motif,
            "participant_id": self.participant_id,
            "nom": self.nom_complet,
            "annee_naissance": self.annee_naissance,
            "club": self.club,
            "categorie": self.categorie,
            "etat_helloasso": self.etat_helloasso,
            "recue_le": self.recue_le.isoformat() if self.recue_le else None,
        }

    def __repr__(self) -> str:
        return (f"<Inscription article={self.article_id} "
                f"{self.nom_complet!r} {self.etat}>")


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


# --- Archives (spec 018) ----------------------------------------------------

# Le numéro de format du contenu archivé. Il monte quand la STRUCTURE du JSON
# change, jamais quand les données changent. Sa raison d'être : qu'une archive
# écrite aujourd'hui puisse être reconnue et refusée proprement dans trois ans,
# plutôt que de faire tomber la page de résultats sur une clé manquante.
FORMAT_ARCHIVE = 1


class Reglage(db.Model):
    """Un réglage GLOBAL du serveur, en clé-valeur. Une seule clé pour l'instant :
    `plan_du_mur`, le plan de la salle dessiné depuis la console (spec 029).

    **Global et non par compétition.** Le club a un mur ; le ranger dans
    `competition.options` obligerait à le redessiner à chaque édition, ou à
    inventer une reprise automatique — deux mauvaises réponses à une question
    qui ne se pose pas.

    **En base et non dans un fichier**, pour la raison exacte que donne
    `Archive` juste en dessous : `climbcontest-sauvegarde` recopie la base
    SQLite et rien d'autre. Un JSON posé dans le dossier de données serait le
    seul fichier sans sauvegarde, et une restauration ramènerait
    silencieusement l'ancien plan.
    """

    __tablename__ = "reglage"

    cle = Column(String(60), primary_key=True)
    valeur = Column(Text, nullable=False)
    modifie_le = Column(DateTime, nullable=False, default=func.now(),
                        onupdate=func.now())
    modifie_par = Column(String(80))


class Archive(db.Model):
    """Une édition figée : son classement, ses données brutes, sa date.

    **Volontairement sans clé étrangère vers `competition`.** Une archive doit
    survivre à l'effacement de ce qu'elle décrit — c'est sa seule raison d'être.
    Avec `PRAGMA foreign_keys=ON` (que la base active), une `ForeignKey` ferait
    exactement l'inverse : elle empêcherait la suppression de la compétition, ou
    emporterait l'archive en cascade. `competition_id` reste ici un entier de
    traçabilité, jamais une contrainte.

    Elle vit EN BASE et non dans un fichier à côté parce que
    `climbcontest-sauvegarde` recopie la base SQLite et **rien d'autre** : un
    JSON posé dans `shared/archives/` serait le seul fichier de la VM sans
    sauvegarde, et précisément celui qu'on ne peut pas reconstruire.
    """

    __tablename__ = "archive"

    id = Column(Integer, primary_key=True)
    competition_id = Column(Integer, nullable=False)
    nom = Column(String(120), nullable=False)
    date = Column(Date, nullable=False)
    format = Column(Integer, nullable=False, default=FORMAT_ARCHIVE)

    cree_le = Column(DateTime, nullable=False, default=func.now())
    cree_par = Column(String(80))

    # Recopiés à l'archivage pour que la LISTE n'ait jamais à désérialiser
    # `contenu` : trois cents kilo-octets de JSON par ligne, lus pour afficher
    # un nombre, c'est le genre de détail qui rend une page lente sans raison.
    participants = Column(Integer, nullable=False, default=0)
    blocs = Column(Integer, nullable=False, default=0)
    reussites = Column(Integer, nullable=False, default=0)

    contenu = Column(Text, nullable=False)            # le JSON complet

    def resume(self) -> dict:
        """Ce que la liste affiche. Ne touche jamais `contenu`."""
        return {
            "id": self.id,
            "competition_id": self.competition_id,
            "nom": self.nom,
            "date": self.date.isoformat() if self.date else None,
            "format": self.format,
            "cree_le": self.cree_le.isoformat() if self.cree_le else None,
            "cree_par": self.cree_par,
            "participants": self.participants,
            "blocs": self.blocs,
            "reussites": self.reussites,
            # Le client n'a pas à connaître la liste des formats lisibles : le
            # serveur tranche, et dit simplement si « Revoir » est possible.
            "lisible": self.format == FORMAT_ARCHIVE,
        }

    def __repr__(self) -> str:
        return f"<Archive {self.id} {self.nom!r} du {self.date}>"


class Appareil(db.Model):
    """Un telephone de juge, vu par le serveur (spec 030).

    ⚠️ **Cette table n'est PAS la source de verite des reussites.** Une reussite
    porte deja, denormalises, l'identifiant et le nom de l'appareil qui l'a
    envoyee : c'est ce qui permet de retrouver un scan des mois plus tard, meme
    si le telephone a disparu. Cette table-ci ne sert qu'a repondre a une
    question du present : « ce telephone-la tourne-t-il sur la meme version et
    le meme catalogue que le serveur ? »

    **Globale, pas par competition.** Un telephone traverse les editions ; le
    rattachement a une edition se fait par les reussites qu'il a envoyees.

    ⚠️ **Deux horodatages, et il ne faut surtout pas les fusionner.** `vu_le`
    avance a n'importe quel contact -- telechargement du catalogue ou envoi d'un
    lot. `catalogue_vu_le` n'avance QUE sur un echange de catalogue. C'est leur
    ECART qui trahit un cache pose devant `/api/v2/catalog` : le telephone
    envoie ses lots (POST, jamais mis en cache) mais ne s'annonce plus (GET,
    absorbe par le cache). Avec un seul horodatage, cette panne serait
    invisible -- et elle rendrait faux tout le tableau des appareils sans que
    rien ne bronche. Voir specs/030-versions-visibles/spec.md, F8.
    """

    __tablename__ = "appareil"

    # L'identifiant tire par le telephone lui-meme (`identite.js`, `crypto
    # .randomUUID`). C'est le meme que celui recopie sur chaque reussite.
    id = Column(String(40), primary_key=True)
    nom = Column(String(60))

    # Ce que la coquille dit executer. `None` pour un client qui ne s'annonce
    # pas -- l'application Android du Play Store, aujourd'hui.
    version_app = Column(String(20))

    # ⚠️ Le numero que le telephone DETIENT a la fin de l'echange, c'est-a-dire
    # le numero courant du serveur au moment du contact -- et non celui qu'il a
    # annonce. Un `304` signifie qu'ils sont egaux ; un `200` que le telephone
    # vient de recevoir le courant. Enregistrer le numero ANNONCE ferait
    # clignoter en ambre, apres chaque import, des telephones qui viennent
    # precisement de se mettre a jour.
    catalogue_version = Column(Integer)
    catalogue_vu_le = Column(DateTime)

    premiere_vue_le = Column(DateTime, nullable=False, default=func.now())
    vu_le = Column(DateTime, nullable=False, default=func.now(), index=True)

    def __repr__(self) -> str:
        return f"<Appareil {self.id!r} {self.nom!r} {self.version_app}>"
