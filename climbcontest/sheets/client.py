"""Accès au classeur Google — lecture et écriture, avec des erreurs typées.

Deux différences avec la version précédente, et ce sont elles qui font toute la
spec 002 :

1. **Les erreurs remontent.** L'ancien `update_google_sheet()` attrapait ses
   propres exceptions, imprimait un message et renvoyait `False` — que le
   travailleur ignorait, vidant son lot quand même. Cinquante réussites
   pouvaient disparaître sans que personne ne le sache (risque R3). Ici une
   erreur lève une exception : l'appelant décide, et il décide de ne rien
   marquer comme synchronisé.

2. **Rien n'est en dur.** L'identifiant du classeur est passé en argument ; il
   vit en base, par compétition.

Spec 015 y ajoute deux choses, et les deux existent pour la même raison — le
jour de la compétition, personne n'a de terminal SSH sous la main :

3. **La grille s'agrandit toute seule.** Un dossard attribué à chaud sort de la
   largeur préparée dans l'onglet `Import` ; Google refuse alors l'écriture
   (« exceeds grid limits ») et le miroir la retente en boucle, pour toujours.
   `marquer_reussites()` élargit la feuille avant d'écrire.

4. **Le jeton peut être du JSON.** `token.json` est lu avant `token.pickle` :
   c'est un format qu'on peut accepter depuis la console sans jamais
   désérialiser du contenu venu du réseau.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
import pickle
import tempfile

logger = logging.getLogger(__name__)

# Les trois formes du jeton, dans l'ordre où on les cherche. Le JSON d'abord :
# c'est le seul que la console sait écrire, donc le seul qui peut être plus
# récent que les autres.
FICHIER_JSON = "token.json"
FICHIER_CREDENTIALS = "credentials.json"
FICHIER_PICKLE = "token.pickle"
FICHIER_BASE64 = "token.base64"

# La marge d'agrandissement. Sans elle, dix inscriptions à chaud d'affilée
# donneraient dix appels d'agrandissement — un par dossard. Avec, le cas normal
# n'en fait qu'un. Cinq colonnes vides ne coûtent rien à un classeur.
MARGE_GRILLE = 5


class ErreurClasseur(Exception):
    """Le classeur est injoignable ou refuse l'opération.

    Volontairement distincte des erreurs métier : elle ne doit jamais faire
    échouer une requête de juge, seulement retarder la synchronisation.
    """


class ClasseurGoogle:
    """Client minimal de l'API Sheets.

    L'authentification reprend celle qui fonctionne depuis 2024 : `token.pickle`,
    ou `token.base64` en repli pour un hébergement sans navigateur — et
    désormais `token.json`, qui passe devant.
    """

    ONGLET_IMPORT = "Import"

    def __init__(self, spreadsheet_id: str, feuilles=None):
        if not spreadsheet_id:
            raise ErreurClasseur("Aucun identifiant de classeur pour cette competition")
        self.spreadsheet_id = spreadsheet_id
        # `feuilles` injectable : c'est la couture qui permet de tester
        # l'agrandissement de la grille sans reseau ni paquet Google.
        self._feuilles = feuilles
        self._meta = None

    # --- authentification ---------------------------------------------------

    @staticmethod
    def _dossiers_de_jeton():
        """Ou chercher le jeton, dans l'ordre.

        Le dossier configure d'abord -- c'est celui de la VM. Le repertoire
        courant ensuite, parce que c'est la que le jeton se trouve quand on
        lance un outil a la main depuis la racine du depot.
        """
        from flask import current_app

        dossiers = []
        try:
            configure = current_app.config.get("DOSSIER_SECRETS")
            if configure:
                dossiers.append(Path(configure))
        except RuntimeError:
            pass                       # hors contexte Flask : outils en ligne de commande
        if env := os.environ.get("CLIMBCONTEST_SECRETS_DIR"):
            dossiers.append(Path(env))
        dossiers.append(Path.cwd())
        # dedoublonne en gardant l'ordre
        vus, ordonnes = set(), []
        for d in dossiers:
            if d not in vus:
                vus.add(d)
                ordonnes.append(d)
        return ordonnes

    @staticmethod
    def _identifiants():
        from google.auth.transport.requests import Request

        creds = None
        source_json = None                 # le fichier a reecrire apres un rafraichissement
        cherches = []
        for dossier in ClasseurGoogle._dossiers_de_jeton():
            fichier_json = dossier / FICHIER_JSON
            pickle_ = dossier / FICHIER_PICKLE
            base64_ = dossier / FICHIER_BASE64
            cherches += [str(fichier_json), str(pickle_), str(base64_)]
            if fichier_json.exists():
                from google.oauth2.credentials import Credentials
                # Sans `scopes=` : on garde ceux du jeton. Les imposer ici
                # ferait echouer un jeton parfaitement valide au premier
                # changement de perimetre.
                creds = Credentials.from_authorized_user_file(str(fichier_json))
                source_json = fichier_json
                break
            if pickle_.exists():
                creds = pickle.loads(pickle_.read_bytes())
                break
            if base64_.exists():
                import base64 as b64
                creds = pickle.loads(b64.b64decode(base64_.read_text()))
                break

        if creds is None:
            # On DIT ou on a cherche. Le message precedent renvoyait a
            # « token.pickle » sans chemin, ce qui a masque le vrai probleme :
            # le fichier existait, mais ailleurs.
            raise ErreurClasseur(
                "Aucun jeton Google. Cherche dans : " + ", ".join(cherches)
                + " — voir docs/plan-de-repli.md."
            )
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                if source_json is not None:
                    # Le jeton rafraichi est REECRIT : sans ca, chaque
                    # redemarrage du service repart d'un jeton perime et
                    # redemande un rafraichissement a Google, pour rien.
                    _reecrire_jeton(source_json, creds)
            else:
                raise ErreurClasseur(
                    "Jeton Google invalide et non rafraichissable : refaire le "
                    "consentement depuis la console -- Classeur, « Connecter le "
                    "compte Google »."
                )
        return creds

    @property
    def feuilles(self):
        if self._feuilles is None:
            try:
                from googleapiclient.discovery import build
                service = build("sheets", "v4", credentials=self._identifiants(),
                                cache_discovery=False)
                self._feuilles = service.spreadsheets()
            except ErreurClasseur:
                raise
            except Exception as e:
                raise ErreurClasseur(f"Connexion au classeur impossible : {e}") from e
        return self._feuilles

    # --- lecture ------------------------------------------------------------

    def lire(self, onglet: str, plage: str) -> list[list]:
        try:
            r = self.feuilles.values().get(
                spreadsheetId=self.spreadsheet_id, range=f"{onglet}!{plage}"
            ).execute()
        except ErreurClasseur:
            raise
        except Exception as e:
            raise ErreurClasseur(f"Lecture de {onglet}!{plage} : {e}") from e
        return r.get("values", [])

    def metadonnees(self, recharger: bool = False) -> dict:
        """Titre du classeur et description de ses onglets — sans les donnees.

        Mise en cache : `marquer_reussites()` s'en sert a chaque lot pour savoir
        si la grille suffit, et la grille ne change que quand c'est nous qui la
        changeons.
        """
        if self._meta is None or recharger:
            try:
                self._meta = self.feuilles.get(
                    spreadsheetId=self.spreadsheet_id,
                    fields="properties.title,"
                           "sheets.properties(sheetId,title,gridProperties),"
                           "sheets.protectedRanges(protectedRangeId,description,range)",
                ).execute()
            except ErreurClasseur:
                raise
            except Exception as e:
                raise ErreurClasseur(f"Lecture du classeur : {e}") from e
        return self._meta

    def titre(self) -> str:
        return self.metadonnees().get("properties", {}).get("title", "")

    def onglets(self) -> list[str]:
        return [f.get("properties", {}).get("title", "")
                for f in self.metadonnees().get("sheets", [])]

    def grille(self, onglet: str) -> dict:
        """`{"id", "lignes", "colonnes"}` de l'onglet, tel que Google le voit."""
        for feuille in self.metadonnees().get("sheets", []):
            proprietes = feuille.get("properties", {})
            if proprietes.get("title") == onglet:
                grille = proprietes.get("gridProperties", {})
                return {
                    "id": proprietes.get("sheetId"),
                    "lignes": grille.get("rowCount", 0),
                    "colonnes": grille.get("columnCount", 0),
                }
        raise ErreurClasseur(
            f"Onglet « {onglet} » absent du classeur : "
            f"onglets presents = {', '.join(self.onglets()) or 'aucun'}")

    # --- écriture -----------------------------------------------------------

    def agrandir_si_besoin(self, onglet: str, lignes: int, colonnes: int) -> dict:
        """Elargit l'onglet pour qu'il contienne au moins ces lignes/colonnes.

        C'est le correctif de la spec 015. Google REFUSE une ecriture hors de la
        grille existante :

            Range ('Import'!DZ12) exceeds grid limits. Max columns: 120

        Le miroir ne marquant rien comme synchronise en cas d'echec (spec 002),
        une seule reussite de ce genre bloque son lot et tous les suivants, sans
        fin — la grille ne s'agrandit jamais toute seule.

        N'appelle Google QUE si la grille est trop petite.
        """
        actuelle = self.grille(onglet)
        demande = {}
        if lignes > actuelle["lignes"]:
            demande["rowCount"] = lignes + MARGE_GRILLE
        if colonnes > actuelle["colonnes"]:
            demande["columnCount"] = colonnes + MARGE_GRILLE
        if not demande:
            return {"lignes_ajoutees": 0, "colonnes_ajoutees": 0}

        requete = {
            "updateSheetProperties": {
                "properties": {"sheetId": actuelle["id"], "gridProperties": demande},
                "fields": ",".join(f"gridProperties.{champ}" for champ in demande),
            }
        }
        try:
            self.feuilles.batchUpdate(
                spreadsheetId=self.spreadsheet_id, body={"requests": [requete]}
            ).execute()
        except ErreurClasseur:
            raise
        except Exception as e:
            raise ErreurClasseur(
                f"Agrandissement de l'onglet {onglet} "
                f"({demande}) : {e}") from e

        ajoutees = {
            "lignes_ajoutees": max(0, demande.get("rowCount", 0) - actuelle["lignes"]),
            "colonnes_ajoutees": max(0, demande.get("columnCount", 0) - actuelle["colonnes"]),
        }
        logger.info("classeur : onglet %s agrandi (+%d ligne(s), +%d colonne(s))",
                    onglet, ajoutees["lignes_ajoutees"], ajoutees["colonnes_ajoutees"])
        self._meta = None                  # le cache decrit une grille qui n'existe plus
        return ajoutees

    def marquer_reussites(self, couples: list[tuple[int, int]]) -> int:
        """Écrit « A » pour chaque couple (dossard, numéro de bloc).

        Adressage repris tel quel du classeur, il ne change pas :
        colonne = dossard + 3, ligne = numéro de bloc + 1.

        Lève `ErreurClasseur` en cas d'échec — **c'est le point important**.
        L'appelant ne marquera alors rien comme synchronisé, et réessaiera.
        """
        if not couples:
            return 0

        # La grille d'abord : ecrire hors grille est un echec pur, et un echec
        # qui se repete indefiniment (spec 015).
        self.agrandir_si_besoin(
            self.ONGLET_IMPORT,
            lignes=max(numero for _, numero in couples) + 1,
            colonnes=max(dossard for dossard, _ in couples) + 3,
        )

        donnees = [
            {"range": f"{self.ONGLET_IMPORT}!{self.colonne(dossard + 3)}{numero + 1}",
             "values": [["A"]]}
            for dossard, numero in couples
        ]

        try:
            self.feuilles.values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"data": donnees, "valueInputOption": "RAW"},
            ).execute()
        except ErreurClasseur:
            raise
        except Exception as e:
            raise ErreurClasseur(f"Ecriture de {len(couples)} reussite(s) : {e}") from e

        logger.info("classeur : %d reussite(s) ecrite(s)", len(couples))
        return len(couples)

    def plages_protegees(self, onglet: str) -> list[str]:
        """Les protections posees sur cet onglet, decrites en clair.

        Lues des metadonnees deja chargees : aucune requete de plus. C'est
        l'angle mort de l'essai d'ecriture — une protection sur `D2:DP103`
        laisse le coin de la grille parfaitement ecrivable, et bloque pourtant
        exactement la ou le miroir ecrit.
        """
        protections = []
        for feuille in self.metadonnees().get("sheets", []):
            proprietes = feuille.get("properties", {})
            if proprietes.get("title") != onglet:
                continue
            for protection in feuille.get("protectedRanges", []) or []:
                description = (protection.get("description") or "").strip()
                protections.append(description or f"protection sans description "
                                                  f"(id {protection.get('protectedRangeId')})")
        return protections

    def essai_ecriture(self, onglet: str = ONGLET_IMPORT) -> dict:
        """Ecrit puis efface la derniere cellule de la grille. Diagnostic pur.

        **Ne leve jamais.** Un test dont l'echec EST la reponse attendue ne doit
        pas s'exprimer par une exception : « la feuille est partagee en lecture
        seule » est un resultat, pas une panne. Tout part dans le dictionnaire.

        La cellule temoin est le dernier coin de la grille, JAMAIS une cellule
        de la matrice. La ligne 1 porte les dossards, les colonnes A a C portent
        les blocs, `D2:...` porte les « A » et `D103` un horodatage : tester la
        ou le miroir ecrit vraiment detruirait une reussite reelle si
        l'effacement final echouait. Le coin, lui, est vide par construction.
        """
        rapport = {"tentee": False, "onglet": onglet, "cellule": None,
                   "ecriture": None, "restauree": None, "message": None,
                   "plages_protegees": []}

        try:
            grille = self.grille(onglet)
            rapport["plages_protegees"] = self.plages_protegees(onglet)
        except ErreurClasseur as e:
            rapport["message"] = str(e)
            return rapport

        lignes, colonnes = grille["lignes"], grille["colonnes"]
        if lignes < 2 or colonnes < 4:
            rapport["message"] = (
                f"La grille de « {onglet} » fait {lignes} x {colonnes} : trop "
                "petite pour porter une cellule temoin hors des donnees.")
            return rapport

        cellule = f"{self.colonne(colonnes)}{lignes}"
        rapport["cellule"] = f"{onglet}!{cellule}"

        # 1. Le coin doit etre vide. Sinon on renonce : mieux vaut un test qui
        #    s'arrete qu'un test qui ecrase une donnee qu'on n'avait pas prevue.
        try:
            avant = self.lire(onglet, cellule)
        except ErreurClasseur as e:
            rapport["message"] = f"Lecture de la cellule temoin impossible : {e}"
            return rapport

        if avant and any(str(c).strip() for ligne in avant for c in ligne):
            rapport["message"] = (
                f"La cellule temoin {onglet}!{cellule} n'est pas vide : rien "
                "n'a ete ecrit. Vide-la, ou teste sur un classeur ou le coin "
                "de la grille est libre.")
            return rapport

        # 2. Ecrire.
        marque = f"climbcontest-test {datetime.now().isoformat(timespec='seconds')}"
        rapport["tentee"] = True
        try:
            self.feuilles.values().update(
                spreadsheetId=self.spreadsheet_id, range=f"{onglet}!{cellule}",
                valueInputOption="RAW", body={"values": [[marque]]},
            ).execute()
        except Exception as e:
            rapport["ecriture"] = False
            rapport["message"] = (
                f"Google a refuse l'ecriture : {e}. La feuille est-elle bien "
                "partagee EN MODIFICATION avec le compte du jeton ? Un partage "
                "en lecture seule passe tous les autres controles.")
            return rapport

        # 3. Relire : une ecriture acceptee mais sans effet se verrait ici.
        try:
            relu = self.lire(onglet, cellule)
            ecrit = relu and relu[0] and str(relu[0][0]).strip() == marque
        except ErreurClasseur as e:
            relu, ecrit = None, False
            rapport["message"] = f"Relecture impossible : {e}"

        rapport["ecriture"] = bool(ecrit)
        if not ecrit and rapport["message"] is None:
            rapport["message"] = (
                "L'ecriture a ete acceptee mais la relecture ne rend pas ce "
                "qui a ete ecrit. La cellule est peut-etre protegee.")

        # 4. Remettre comme c'etait. Tente MEME quand la relecture a echoue :
        #    si quelque chose a ete pose, il faut l'enlever.
        try:
            self.feuilles.values().clear(
                spreadsheetId=self.spreadsheet_id, range=f"{onglet}!{cellule}",
                body={},
            ).execute()
            rapport["restauree"] = True
        except Exception as e:
            rapport["restauree"] = False
            rapport["message"] = (
                f"Ecriture reussie, mais la cellule {onglet}!{cellule} n'a PAS "
                f"pu etre effacee ({e}). Elle porte « {marque} » : va la vider "
                "a la main. Elle ne gene rien, mais autant le savoir.")

        if rapport["ecriture"] and rapport["restauree"] and not rapport["message"]:
            rapport["message"] = (
                f"Ecriture confirmee sur {onglet}!{cellule}, puis effacee.")

        logger.info("essai d'ecriture sur %s!%s : ecriture=%s restauree=%s",
                    onglet, cellule, rapport["ecriture"], rapport["restauree"])
        return rapport

    def vider_matrice(self, onglet: str = ONGLET_IMPORT) -> dict:
        """Efface les « A » de la matrice, et RIEN d'autre.

        Sert au mode « nouvelle competition » de la spec 015 : on repart d'un
        classeur propre sans perdre ce qui le decrit.

        La plage est bornee sur le contenu reel — les lignes qui portent un
        numero de bloc en colonne A, les colonnes qui portent un dossard en
        ligne 1 — et commence en `D2`. La ligne 1 (les dossards), les colonnes
        A a C (numero et tag du bloc) et l'horodatage en `D103` ne sont jamais
        touches.
        """
        entete = self.lire(onglet, "1:1")
        numeros = self.lire(onglet, "A2:A")

        derniere_colonne = len(entete[0]) if entete else 0
        derniere_ligne = 1 + len(numeros)
        if derniere_colonne < 4 or derniere_ligne < 2:
            return {"plage": None, "lignes": 0, "colonnes": 0}

        plage = f"D2:{self.colonne(derniere_colonne)}{derniere_ligne}"
        try:
            self.feuilles.values().clear(
                spreadsheetId=self.spreadsheet_id, range=f"{onglet}!{plage}", body={}
            ).execute()
        except ErreurClasseur:
            raise
        except Exception as e:
            raise ErreurClasseur(f"Vidage de {onglet}!{plage} : {e}") from e

        logger.info("classeur : matrice %s!%s videe", onglet, plage)
        return {"plage": plage,
                "lignes": derniere_ligne - 1,
                "colonnes": derniere_colonne - 3}

    @staticmethod
    def colonne(n: int) -> str:
        """1 → A, 27 → AA."""
        nom = ""
        while n > 0:
            n, reste = divmod(n - 1, 26)
            nom = chr(65 + reste) + nom
        return nom


# --- Le jeton, vu de la console ---------------------------------------------
#
# Ces fonctions vivent ici parce que c'est ici qu'on sait ou le jeton est
# cherche, et dans quel ordre. Aucune n'importe de paquet Google : la console
# doit pouvoir dire « aucun jeton » sur une installation qui n'en a pas encore.


def chemin_jeton_json() -> Path:
    """Ou la console ECRIT le jeton : le premier dossier de la liste."""
    return ClasseurGoogle._dossiers_de_jeton()[0] / FICHIER_JSON


def chemin_credentials() -> Path | None:
    """Le `credentials.json` de l'application OAuth, ou None.

    C'est l'identite de l'APPLICATION (client_id, client_secret), pas celle du
    compte : il ne change jamais d'une competition a l'autre. Cherche dans les
    memes dossiers que le jeton, et dans le meme ordre.
    """
    for dossier in ClasseurGoogle._dossiers_de_jeton():
        chemin = dossier / FICHIER_CREDENTIALS
        if chemin.exists():
            return chemin
    return None


def etat_credentials() -> dict:
    """`{"pret", "chemin", "message"}`. Ne leve jamais.

    Un `credentials.json` absent est un etat NORMAL d'une installation neuve,
    pas une panne : la console doit l'AFFICHER et desactiver le bouton, pas
    rendre une 500 ni offrir un bouton qui ne marchera pas.
    """
    chemin = chemin_credentials()
    if chemin is None:
        cherches = [str(d / FICHIER_CREDENTIALS)
                    for d in ClasseurGoogle._dossiers_de_jeton()]
        return {"pret": False, "chemin": None,
                "message": "Aucun " + FICHIER_CREDENTIALS + ". Attendu dans "
                           + cherches[0] + "."}

    try:
        contenu = json.loads(chemin.read_text())
    except (OSError, ValueError) as e:
        return {"pret": False, "chemin": str(chemin),
                "message": f"{chemin.name} illisible : {e}"}

    # Google produit soit `{"web": {...}}`, soit `{"installed": {...}}`. Le
    # notre est de type « web », le seul qui accepte une URI de retour HTTPS.
    if not isinstance(contenu, dict) or not (
            contenu.get("web") or contenu.get("installed")):
        return {"pret": False, "chemin": str(chemin),
                "message": f"{chemin.name} ne porte ni « web » ni « installed » : "
                           "ce n'est pas un identifiant client OAuth."}

    return {"pret": True, "chemin": str(chemin), "message": None}


def trouver_jeton():
    """`(chemin, forme)` du jeton qui sera effectivement utilise, ou `None`."""
    for dossier in ClasseurGoogle._dossiers_de_jeton():
        for nom, forme in ((FICHIER_JSON, "json"),
                           (FICHIER_PICKLE, "pickle"),
                           (FICHIER_BASE64, "base64")):
            chemin = dossier / nom
            if chemin.exists():
                return chemin, forme
    return None


def etat_jeton() -> dict:
    """Ce que la console affiche du jeton. Ne leve jamais.

    Un jeton absent est un etat NORMAL d'une installation neuve, pas une panne :
    la vue doit l'afficher, pas rendre une erreur 500.
    """
    trouve = trouver_jeton()
    if trouve is None:
        cherches = [str(d / FICHIER_JSON) for d in ClasseurGoogle._dossiers_de_jeton()]
        return {"present": False, "source": None, "chemin": None, "valide": None,
                "expire_le": None, "scopes": [],
                "message": "Aucun jeton Google. Il sera ecrit dans "
                           + cherches[0] + "."}

    chemin, forme = trouve
    etat = {"present": True, "source": forme, "chemin": str(chemin),
            "valide": None, "expire_le": None, "scopes": [], "message": None}

    if forme == "json":
        # Lisible sans aucun paquet Google — c'est tout l'interet du format.
        try:
            contenu = json.loads(chemin.read_text())
        except (OSError, ValueError) as e:
            etat["valide"] = False
            etat["message"] = f"Fichier illisible : {e}"
            return etat
        if not isinstance(contenu, dict):
            # Du JSON valide qui n'est pas un objet : une liste, un nombre. La
            # vue doit le DIRE, pas tomber en 500 sur un `.get` impossible.
            etat["valide"] = False
            etat["message"] = "Fichier de jeton illisible : un objet JSON etait attendu."
            return etat
        etat["expire_le"] = contenu.get("expiry")
        etat["scopes"] = contenu.get("scopes") or []
        etat["valide"] = bool(contenu.get("refresh_token"))
        if not etat["valide"]:
            etat["message"] = ("Jeton sans refresh_token : il cessera de "
                               "fonctionner a la premiere expiration.")
        return etat

    etat["message"] = ("Jeton binaire pose sur le serveur (« " + chemin.name
                       + " »). Il fonctionne ; la console ne peut pas en lire "
                         "la date d'expiration.")
    return etat


def _ecrire_atomique(chemin: Path, contenu: str) -> None:
    """Ecrit en 0600, sans jamais laisser un fichier a moitie ecrit.

    Un jeton tronque par une coupure au mauvais moment serait un jeton perdu,
    et la panne se verrait au pire endroit : le samedi matin, sur la VM.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fd, provisoire = tempfile.mkstemp(dir=str(chemin.parent), prefix=".jeton-")
    try:
        with os.fdopen(fd, "w") as sortie:
            sortie.write(contenu)
        os.chmod(provisoire, 0o600)
        os.replace(provisoire, chemin)
    except BaseException:
        try:
            os.unlink(provisoire)
        except OSError:
            pass
        raise


def _reecrire_jeton(chemin: Path, creds) -> None:
    """Persiste un jeton rafraichi. Best effort : jamais fatal.

    Le jeton en memoire est valide — la synchronisation doit continuer meme si
    le disque refuse l'ecriture.
    """
    try:
        _ecrire_atomique(chemin, creds.to_json())
        logger.info("jeton Google rafraichi et reecrit dans %s", chemin)
    except Exception as e:                                  # noqa: BLE001
        logger.warning("jeton rafraichi mais non reecrit dans %s : %s", chemin, e)


def ecrire_jeton_json(contenu: str, chemin: Path | None = None) -> Path:
    """Pose le jeton venu de la console, en gardant le precedent sous la main.

    `token.json.precedent` : un jeton ecrase par erreur se rattrape depuis la
    console suivante, sans SSH ni scp.
    """
    cible = chemin or chemin_jeton_json()
    if cible.exists():
        try:
            _ecrire_atomique(cible.with_suffix(cible.suffix + ".precedent"),
                             cible.read_text())
        except OSError as e:
            logger.warning("jeton precedent non conserve : %s", e)
    _ecrire_atomique(cible, contenu)
    logger.info("jeton Google pose dans %s", cible)
    return cible
