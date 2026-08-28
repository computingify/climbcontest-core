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
"""

import logging
import os
from pathlib import Path
import pickle
from io import BytesIO

logger = logging.getLogger(__name__)


class ErreurClasseur(Exception):
    """Le classeur est injoignable ou refuse l'opération.

    Volontairement distincte des erreurs métier : elle ne doit jamais faire
    échouer une requête de juge, seulement retarder la synchronisation.
    """


class ClasseurGoogle:
    """Client minimal de l'API Sheets.

    L'authentification reprend celle qui fonctionne depuis 2024 : `token.pickle`,
    ou `token.base64` en repli pour un hébergement sans navigateur.
    """

    ONGLET_IMPORT = "Import"

    def __init__(self, spreadsheet_id: str):
        if not spreadsheet_id:
            raise ErreurClasseur("Aucun identifiant de classeur pour cette competition")
        self.spreadsheet_id = spreadsheet_id
        self._feuilles = None

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
        cherches = []
        for dossier in ClasseurGoogle._dossiers_de_jeton():
            pickle_ = dossier / "token.pickle"
            base64_ = dossier / "token.base64"
            cherches += [str(pickle_), str(base64_)]
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
            else:
                raise ErreurClasseur(
                    "Jeton Google invalide et non rafraichissable : refaire le "
                    "consentement depuis une machine avec navigateur."
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

    # --- écriture -----------------------------------------------------------

    def marquer_reussites(self, couples: list[tuple[int, int]]) -> int:
        """Écrit « A » pour chaque couple (dossard, numéro de bloc).

        Adressage repris tel quel du classeur, il ne change pas :
        colonne = dossard + 3, ligne = numéro de bloc + 1.

        Lève `ErreurClasseur` en cas d'échec — **c'est le point important**.
        L'appelant ne marquera alors rien comme synchronisé, et réessaiera.
        """
        if not couples:
            return 0

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

    @staticmethod
    def colonne(n: int) -> str:
        """1 → A, 27 → AA."""
        nom = ""
        while n > 0:
            n, reste = divmod(n - 1, 26)
            nom = chr(65 + reste) + nom
        return nom
