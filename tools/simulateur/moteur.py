"""Le moteur du simulateur : des juges, une cadence, une file par téléphone.

Ce module ne sait rien de l'interface. Il est piloté par `serveur.py`, qui lui
passe des réglages et lui demande son état — le même découpage que côté PWA,
où `politique.js` et `expediteur.js` ne touchent ni au DOM ni au réseau.

## Ce qui est copié du vrai client, et pourquoi

La politique d'envoi (lot de 5, délai de 10 s, retrait doublé) est **recopiée à
l'identique** de `climbcontest/static/juge/politique.js`, elle-même recopiée de
`PolitiqueEnvoi.kt` côté Android. Un simulateur qui enverrait à son propre
rythme produirait une charge qui ne ressemble à rien de ce qui arrivera le jour
J — et les chiffres qu'on en tirerait ne vaudraient rien.

L'invariant de la file est le même aussi : **une réussite ne quitte la file que
si le serveur a explicitement statué sur elle.** C'est ce qui rend visibles, au
tableau, les files qui gonflent quand le réseau lâche.

## Ce qui est simulé et ne l'est pas

Simulé : le geste du juge (deux scans + « Envoyer »), la file du téléphone,
les lots, le retrait après échec, les coupures réseau, les doublons entre deux
juges, les QR étrangers, les blocs hors circuit.

Pas simulé : la caméra, le décodage du QR, le service worker. Ce qui part sur
le réseau est en revanche **exactement** ce qu'un téléphone envoie.
"""

import json
import math
import random
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter, deque
from dataclasses import dataclass, asdict
from datetime import datetime

# ────────────────────────────────────────────────────────────────────────────
# La politique d'envoi. Copie de `static/juge/politique.js`.
# ────────────────────────────────────────────────────────────────────────────

LOT_PLEIN = 5          # au-delà, on part sans attendre
DELAI = 10.0           # et si le lot ne se remplit pas, on part quand même
LOT_MAX = 50           # le serveur refuse au-delà de 200 ; on reste loin dessous
RETRAIT_INITIAL = 2.0  # premier délai après un échec, puis doublé
RETRAIT_MAX = 60.0


def attente_apres_echec(echecs: int) -> float:
    if echecs <= 0:
        return 0.0
    attente = RETRAIT_INITIAL
    for _ in range(1, echecs):
        attente = min(attente * 2, RETRAIT_MAX)
    return min(attente, RETRAIT_MAX)


def doit_envoyer(en_attente, depuis_dernier_envoi, echecs,
                 forcer=False, lot_plein=LOT_PLEIN, delai=DELAI) -> bool:
    if en_attente <= 0:
        return False
    if depuis_dernier_envoi < attente_apres_echec(echecs):
        return False
    if forcer:
        return True
    return en_attente >= lot_plein or depuis_dernier_envoi >= delai


# ────────────────────────────────────────────────────────────────────────────
# Le dialogue HTTP. Copie de `static/juge/api.js`, en `urllib`.
# ────────────────────────────────────────────────────────────────────────────

ENTETE_CLE = "X-Api-Key"


class Api:
    """Les mêmes requêtes que la PWA et l'application Android, au corps près.

    ⚠️ Aucune route n'existe pour le simulateur. Il parle le contrat public, et
    c'est ce qui fait que le tester revient à tester ce que fera un téléphone.
    """

    def __init__(self, base: str, cle: str | None = None, timeout: float = 12.0):
        self.base = base.rstrip("/")
        self.cle = (cle or "").strip() or None
        self.timeout = timeout

    def _entetes(self, json_corps=True) -> dict:
        entetes = {"Accept": "application/json"}
        if json_corps:
            entetes["Content-Type"] = "application/json"
        # Pas d'en-tête plutôt qu'un en-tête vide : une clé vide est une clé
        # FAUSSE pour le serveur (401), là où l'absence reste acceptée en mode
        # toléré. Les deux ne sont pas interchangeables.
        if self.cle:
            entetes[ENTETE_CLE] = self.cle
        return entetes

    def _appel(self, chemin, corps=None, methode="POST", entetes_sup=None):
        """Rend (code, json, latence_s). `code` vaut 0 si la requête n'est pas partie."""
        url = f"{self.base}{chemin}"
        donnees = json.dumps(corps).encode() if corps is not None else None
        entetes = self._entetes(json_corps=corps is not None)
        entetes.update(entetes_sup or {})
        requete = urllib.request.Request(url, data=donnees, headers=entetes,
                                         method=methode)
        debut = time.monotonic()
        try:
            with urllib.request.urlopen(requete, timeout=self.timeout) as r:
                brut = r.read()
                latence = time.monotonic() - debut
                try:
                    return r.status, json.loads(brut) if brut else None, latence
                except ValueError:
                    return r.status, None, latence
        except urllib.error.HTTPError as e:
            latence = time.monotonic() - debut
            try:
                return e.code, json.loads(e.read()), latence
            except Exception:
                return e.code, None, latence
        except Exception:
            # Réseau coupé, serveur injoignable, TLS. Jamais un 4xx.
            return 0, None, time.monotonic() - debut

    def catalogue(self, version_connue=None):
        entetes = {"If-None-Match": f'"{version_connue}"'} if version_connue else None
        code, corps, latence = self._appel("/api/v2/catalog", None, "GET", entetes)
        if code == 304:
            return {"etat": "deja-a-jour", "latence": latence}
        if code == 200 and isinstance(corps, dict):
            return {"etat": "recu", "catalogue": corps, "latence": latence}
        message = (corps or {}).get("message") if isinstance(corps, dict) else None
        return {"etat": "echec", "code": code, "latence": latence,
                "message": message or _message_reseau(code)}

    def envoyer_lot(self, reussites, appareil=None):
        """POST /api/v3/successes — un verdict par élément, ou rien du tout.

        Rend les `ref` **acquittées** et les refus. Une `ref` absente des deux
        n'a pas été traitée : l'appelant la garde. Le défaut est de garder,
        parce que perdre une réussite est le seul résultat inacceptable.
        """
        corps = {"items": reussites}
        if appareil and appareil.get("id"):
            corps["appareil"] = appareil
        code, reponse, latence = self._appel("/api/v3/successes", corps)
        if code != 200 or not isinstance(reponse, dict):
            message = (reponse or {}).get("message") if isinstance(reponse, dict) else None
            return {"ok": False, "code": code, "latence": latence,
                    "acquittees": set(), "refusees": [],
                    "message": message or _message_reseau(code)}

        acquittees, refusees, deja = set(), [], 0
        for item in reponse.get("resultats") or []:
            ref = item.get("ref")
            if not ref:
                continue
            etat = item.get("etat")
            # Les trois états sont DÉFINITIFS : la réussite quitte la file dans
            # les trois cas. Tout autre état : on ne sait pas, donc on garde.
            if etat in ("enregistree", "deja_connue"):
                acquittees.add(ref)
                deja += etat == "deja_connue"
            elif etat == "refusee":
                acquittees.add(ref)
                refusees.append({"ref": ref, "message": item.get("message") or ""})
        return {"ok": True, "code": code, "latence": latence,
                "acquittees": acquittees, "refusees": refusees,
                "deja_connues": deja,
                "catalogue_version": reponse.get("catalogue_version")}

    def envoyer_une_v2(self, reussite):
        """Le geste de l'application GELÉE `v3.1.4` : trois allers-retours.

        Dossard, bloc, envoi — et le juge attend à chacun des trois. C'est le
        plan de repli de novembre : il doit pouvoir être mis à la même charge
        que le reste, sinon on ne l'aura mesuré qu'en théorie.

        Rend `appels`, la liste des (code, latence) de chacun des trois : c'est
        le nombre de requêtes qui fait tout l'intérêt de la comparaison avec les
        lots (10 800 contre 817 sur une compétition, spec 003). Le compter pour
        un seul appel effacerait précisément ce qu'on cherche à voir.

        ⚠️ La route `v2` répond 201 même sur un doublon — elle est idempotente
        et ne dit pas laquelle des deux choses s'est produite. En `v2`, le
        compteur « déjà connues » reste donc à zéro : c'est une limite du
        protocole, pas du simulateur.
        """
        appels = []

        def verdict(code, reponse, definitif=None):
            message = (reponse or {}).get("message") if isinstance(reponse, dict) else None
            return {"code": code, "appels": appels,
                    "definitif": 400 <= code < 500 if definitif is None else definitif,
                    "message": message or _message_reseau(code)}

        for chemin, corps in (("climber/name", {"id": reussite["bib"]}),
                              ("bloc/name", {"id": reussite["bloc"]})):
            code, reponse, latence = self._appel(f"/api/v2/contest/{chemin}", corps)
            appels.append((code, latence))
            if code != 201:
                # Un refus métier (400) est définitif ; une panne (0, 5xx) ne
                # l'est pas et la réussite doit rester en file.
                return verdict(code, reponse)

        code, reponse, latence = self._appel(
            "/api/v2/contest/success",
            {"bib": reussite["bib"], "bloc": reussite["bloc"]})
        appels.append((code, latence))
        return verdict(code, reponse, definitif=code == 201 or 400 <= code < 500)


def _message_reseau(code) -> str:
    if code == 0:
        return "serveur injoignable"
    if code == 401:
        return "clé d'API refusée (401)"
    if code == 409:
        return "aucune compétition active (409)"
    return f"refusé ({code})"


# ────────────────────────────────────────────────────────────────────────────
# Le catalogue, lu comme le lit `static/juge/catalogue.js`.
# ────────────────────────────────────────────────────────────────────────────

def circuit_de(categorie) -> str | None:
    """« U13 F » → « U13 ». La même règle que `Participant.circuit`, côté serveur."""
    if not isinstance(categorie, str) or not categorie.strip():
        return None
    valeur = categorie.strip()
    espace = valeur.rfind(" ")
    return valeur if espace == -1 else valeur[:espace]


class Catalogue:
    """Ce que le serveur dit de la compétition : qui peut scanner quoi.

    Les dossards et les tags viennent d'ici et **jamais d'une liste inventée** :
    c'est ce qui fait la différence entre un test de charge et une répétition.
    """

    def __init__(self, brut: dict):
        self.brut = brut
        comp = brut.get("competition") or {}
        self.nom = comp.get("nom") or "sans nom"
        self.statut = comp.get("statut") or "?"
        self.version = brut.get("version")
        self.participants = [p for p in (brut.get("participants") or [])
                             if p.get("dossard") is not None]
        self.blocs = list(brut.get("blocs") or [])
        self.circuits = list(brut.get("circuits") or [])

        self.circuit_du_dossard = {
            p["dossard"]: circuit_de(p.get("categorie")) for p in self.participants}
        self.nom_du_dossard = {p["dossard"]: p.get("nom") or "" for p in self.participants}
        self.circuits_du_bloc = {
            b["tag"]: [c for c in (b.get("circuits") or []) if c] for b in self.blocs}

        # La zone d'un bloc est la PREMIÈRE LETTRE de son tag (« ZJ6 » = zone Z).
        # C'est la convention du classeur et celle du plan de la salle.
        self.zones: dict[str, list[str]] = {}
        for b in self.blocs:
            tag = str(b.get("tag") or "").strip()
            if not tag:
                continue
            self.zones.setdefault(tag[0].upper(), []).append(tag)

        self.profil_de_zone = {}
        for mur in ((brut.get("plan") or {}).get("murs") or []):
            if mur.get("zone"):
                self.profil_de_zone[str(mur["zone"]).upper()] = mur.get("profil") or ""

        self.dossard_max = max((p["dossard"] for p in self.participants), default=0)

    def utilisable(self) -> str | None:
        """Le motif pour lequel on ne peut pas simuler, ou `None` si tout va bien."""
        if not self.participants:
            return "la compétition active n'a aucun dossard"
        if not self.blocs:
            return "la compétition active n'a aucun bloc"
        return None

    def dans_le_circuit(self, dossard, tag) -> bool | None:
        """Le même test que `Catalogue.horsCircuit` côté PWA. `None` = indécidable."""
        circuit = self.circuit_du_dossard.get(dossard)
        if not circuit:
            return None
        circuits = self.circuits_du_bloc.get(tag)
        if not circuits:
            return None
        return circuit in circuits


# ────────────────────────────────────────────────────────────────────────────
# Les réglages
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class Reglages:
    juges: int = 12
    cadence: float = 2.5            # validations par juge et par minute
    irregularite: int = 70          # 0 = métronome, 100 = rafales et creux
    duree_min: float = 20.0         # 0 = sans fin
    montee: str = "progressive"     # immediate | progressive | vagues
    p_doublon: float = 4.0
    p_inconnu: float = 2.0
    p_hors_circuit: float = 6.0
    p_coupure: float = 5.0      # part du temps passee hors reseau, en %
    protocole: str = "v3"           # v3 (lots) | v2 (trois appels)
    lot_plein: int = 5
    delai: float = 10.0
    a_blanc: bool = False

    @classmethod
    def depuis(cls, brut: dict) -> "Reglages":
        r = cls()
        for champ, valeur in (brut or {}).items():
            if not hasattr(r, champ):
                continue
            attendu = type(getattr(r, champ))
            try:
                setattr(r, champ, attendu(valeur) if attendu is not bool else bool(valeur))
            except (TypeError, ValueError):
                pass
        r.juges = max(1, min(60, r.juges))
        r.cadence = max(0.1, min(120.0, r.cadence))
        r.irregularite = max(0, min(100, r.irregularite))
        r.lot_plein = max(1, min(LOT_MAX, r.lot_plein))
        r.delai = max(1.0, min(300.0, r.delai))
        if r.protocole not in ("v2", "v3"):
            r.protocole = "v3"
        if r.montee not in ("immediate", "progressive", "vagues"):
            r.montee = "progressive"
        return r


# ────────────────────────────────────────────────────────────────────────────
# Un juge
# ────────────────────────────────────────────────────────────────────────────

MONTEE_PROGRESSIVE = 120.0   # secondes pour atteindre la cadence de croisière
PERIODE_VAGUE = 300.0        # un tour de rotation dure cinq minutes
DUREE_COUPURE = 25.0         # durée moyenne d'un décrochage wifi, en secondes


class Juge:
    """Un téléphone posté devant une zone du mur.

    Un juge ne juge pas toute la salle : il est **posté**, et ne voit que les
    blocs de sa zone. C'est ce qui fait qu'un même passage est parfois validé
    deux fois par deux juges voisins, et que les doublons du jour J
    apparaissent tout seuls ici.
    """

    def __init__(self, numero: int, zone: str, blocs: list[str], sim: "Simulation"):
        profil = sim.catalogue.profil_de_zone.get(zone) if sim.catalogue else None
        self.numero = numero
        self.zone = zone
        self.nom = f"Poste {zone}{numero}"
        self.profil = profil or ""
        self.blocs = blocs
        self.sim = sim
        # L'identité d'un POSTE, pas d'une personne (spec 011) : c'est elle qui
        # apparaîtra dans « Réussites tracées » de la console.
        self.appareil = {"id": f"sim-{uuid.uuid4()}", "nom": self.nom}

        self.verrou = threading.Lock()
        self.file: list[dict] = []
        self.refusees: list[dict] = []
        self.actif = True
        self.forcer = False
        self.echecs = 0
        self.dernier_envoi = time.monotonic()
        self.hors_ligne_jusqua = 0.0
        self.dernier_test_reseau = time.monotonic()

        self.envoi_en_cours = False
        self.scannees = 0
        self.envoyees = 0
        self.deja_connues = 0
        self.nb_refusees = 0
        self.verdict = ""
        self.horodatage_dernier_envoi = None

    # — le geste du juge ————————————————————————————————————————————————

    def scanner(self):
        """Deux scans et un appui sur « Envoyer » : la réussite entre en file.

        Côté juge, c'est fini — « Validé » s'affiche parce que la réussite est
        **sur le téléphone**, pas parce qu'elle est sur le serveur.
        """
        item = self.sim.tirer_une_reussite(self)
        if item is None:
            return
        with self.verrou:
            self.file.append(item)
            self.scannees += 1
        self.sim.noter_scan()

    def intervalle(self) -> float:
        """Le temps jusqu'au prochain scan, tiré au sort autour de la cadence.

        Une compétition n'est pas un métronome : les grimpeurs arrivent par
        grappes, s'échauffent, se reposent. Un tirage **exponentiel** produit
        exactement ça — des rafales et des creux, avec la bonne moyenne.
        Le curseur « irrégularité » mélange ce tirage avec un rythme constant :
        à 0 % le juge est une horloge, à 100 % il est un vrai juge.
        """
        r = self.sim.reglages
        moyenne = 60.0 / max(0.1, r.cadence * self.sim.facteur_de_montee())
        a = r.irregularite / 100.0
        return max(0.4, moyenne * ((1 - a) + a * random.expovariate(1.0)))

    # — l'expédition ————————————————————————————————————————————————————

    def acquitter(self, refs: set):
        with self.verrou:
            self.file = [e for e in self.file if e["ref"] not in refs]

    def mettre_de_cote(self, item, motif):
        # On met de côté AVANT d'acquitter : une coupure entre les deux laisse
        # la réussite en file, elle repartira et sera refusée à nouveau. C'est
        # sans gravité. L'ordre inverse la perdrait.
        with self.verrou:
            self.refusees.append({**item, "motif": motif})

    def tenter(self):
        """Un essai d'envoi. Ne rend rien : tout passe par les compteurs."""
        with self.verrou:
            lot = self.file[:min(len(self.file), LOT_MAX)]
        if not lot:
            return

        self.dernier_envoi = time.monotonic()
        self.envoi_en_cours = True
        try:
            self._envoyer(lot)
        finally:
            self.envoi_en_cours = False

    def _envoyer(self, lot):
        if self.sim.reglages.a_blanc:
            # À blanc : la file se vide sans que rien ne parte. Utile pour
            # régler la cadence sans écrire dans une compétition.
            self.acquitter({e["ref"] for e in lot})
            self.envoyees += len(lot)
            self.echecs = 0
            self._verdict("ok", f"{len(lot)} à blanc")
            self.sim.journal("h", self.nom, f"lot de {len(lot)} → à blanc, rien envoyé")
            return

        if self._est_hors_ligne():
            self.echecs += 1
            self._verdict("ko", "réseau coupé")
            self.sim.journal(
                "ko", self.nom,
                f"lot de {len(lot)} → réseau coupé, file conservée, "
                f"nouvel essai dans {attente_apres_echec(self.echecs):.0f} s")
            return

        if self.sim.reglages.protocole == "v2":
            self._tenter_v2(lot)
        else:
            self._tenter_v3(lot)

    def _tenter_v3(self, lot):
        resultat = self.sim.api.envoyer_lot([_sans_extra(e) for e in lot], self.appareil)
        self.sim.noter_requete(resultat["code"], resultat["latence"])

        if not resultat["ok"]:
            self.echecs += 1
            self._verdict("ko", resultat["message"])
            self.sim.journal(
                "ko", self.nom,
                f"lot de {len(lot)} → {resultat['message']}, file conservée, "
                f"nouvel essai dans {attente_apres_echec(self.echecs):.0f} s")
            return

        self.echecs = 0
        par_ref = {e["ref"]: e for e in lot}
        for refus in resultat["refusees"]:
            item = par_ref.get(refus["ref"])
            if item:
                self.mettre_de_cote(item, refus["message"])
        self.acquitter(resultat["acquittees"])

        deja = resultat.get("deja_connues", 0)
        refusees = len(resultat["refusees"])
        enregistrees = len(resultat["acquittees"]) - refusees - deja
        self.envoyees += max(0, enregistrees)
        self.deja_connues += deja
        self.nb_refusees += refusees
        self.sim.noter_verdicts(enregistrees, deja, refusees)
        self.horodatage_dernier_envoi = time.time()

        detail = ", ".join(filter(None, [
            f"{enregistrees} enregistrée{'s' if enregistrees > 1 else ''}" if enregistrees else "",
            f"{deja} déjà connue{'s' if deja > 1 else ''}" if deja else "",
            f"{refusees} refusée{'s' if refusees > 1 else ''}" if refusees else ""]))
        niveau = "warn" if refusees else "h"
        motif = resultat["refusees"][0]["message"] if refusees else ""
        self._verdict("ok" if not refusees else "warn",
                      f"{resultat['code']} · lot de {len(lot)}"
                      + (f" · {motif}" if motif else ""))
        self.sim.journal(niveau, self.nom,
                         f"lot de {len(lot)} → {resultat['code']} "
                         f"{resultat['latence'] * 1000:.0f} ms  {detail}"
                         + (f" ({motif})" if motif else ""))

    def _tenter_v2(self, lot):
        """L'application gelée envoie une réussite à la fois, en trois appels."""
        traitees, refusees = set(), 0
        essai = lot[:self.sim.reglages.lot_plein]
        for item in essai:
            r = self.sim.api.envoyer_une_v2(item)
            for code, latence in r["appels"]:
                self.sim.noter_requete(code, latence)

            if r["code"] == 201:
                traitees.add(item["ref"])
                self.envoyees += 1
                continue
            if r["definitif"]:
                self.mettre_de_cote(item, r["message"])
                traitees.add(item["ref"])
                refusees += 1
                continue

            # Panne : ce qui n'a pas été traité reste en file, intact.
            self.echecs += 1
            self._verdict("ko", r["message"])
            self.sim.journal("ko", self.nom,
                             f"trois appels → {r['message']}, "
                             f"{len(essai) - len(traitees)} gardée(s) en file")
            break
        else:
            self.echecs = 0

        self.acquitter(traitees)
        self.nb_refusees += refusees
        enregistrees = len(traitees) - refusees
        self.sim.noter_verdicts(enregistrees, 0, refusees)
        if traitees:
            self.horodatage_dernier_envoi = time.time()
            self._verdict("ok" if not refusees else "warn",
                          f"201 · {enregistrees} en trois appels")
            self.sim.journal("warn" if refusees else "h", self.nom,
                             f"{enregistrees} réussite(s) en trois appels → 201"
                             + (f", {refusees} refusée(s)" if refusees else ""))

    # — le réseau qui lâche ——————————————————————————————————————————————

    def _est_hors_ligne(self) -> bool:
        """Le wifi du gymnase, avec 125 personnes dessus.

        ⚠️ Le tirage se fait **sur le temps écoulé**, pas à chaque envoi. Tiré
        par envoi, un juge rapide décrocherait dix fois plus souvent qu'un juge
        lent — alors que c'est le même wifi. Le réglage se lit donc « part du
        temps passée hors réseau », et il veut dire la même chose pour tout le
        monde.
        """
        maintenant = time.monotonic()
        if maintenant < self.hors_ligne_jusqua:
            return True

        ecoule, self.dernier_test_reseau = (
            maintenant - self.dernier_test_reseau, maintenant)
        part = min(0.9, max(0.0, self.sim.reglages.p_coupure / 100.0))
        if part <= 0:
            return False
        # Une coupure dure `DUREE_COUPURE` en moyenne. Pour passer une fraction
        # `part` du temps hors ligne, il faut décrocher au taux ci-dessous.
        taux = part / (DUREE_COUPURE * (1 - part))
        if random.random() < 1 - math.exp(-taux * ecoule):
            self.couper(random.expovariate(1 / DUREE_COUPURE))
            return True
        return False

    def couper(self, secondes: float):
        self.hors_ligne_jusqua = time.monotonic() + secondes

    def retablir(self):
        self.hors_ligne_jusqua = 0.0

    def _verdict(self, _niveau, texte):
        self.verdict = texte

    # — vue ——————————————————————————————————————————————————————————————

    def vue(self) -> dict:
        maintenant = time.monotonic()
        with self.verrou:
            en_file = len(self.file)
        if maintenant < self.hors_ligne_jusqua:
            etat = "coupe"
        elif self.envoi_en_cours:
            etat = "envoi"
        elif en_file:
            etat = "scan"
        else:
            etat = "attente"
        return {
            "nom": self.nom, "zone": self.zone, "profil": self.profil,
            "etat": etat, "file": en_file, "envoyees": self.envoyees,
            "deja": self.deja_connues, "refusees": self.nb_refusees,
            "verdict": self.verdict,
            "dernier": self.horodatage_dernier_envoi,
        }


def _sans_extra(item: dict) -> dict:
    """Ce qui part réellement sur le réseau, sans les champs internes."""
    return {c: v for c, v in item.items() if c in ("ref", "bib", "bloc", "at", "hors_circuit")}


# ────────────────────────────────────────────────────────────────────────────
# La simulation
# ────────────────────────────────────────────────────────────────────────────

class Simulation:
    """Tout l'état : les juges, les compteurs, le journal. Un seul exemplaire."""

    def __init__(self):
        self.verrou = threading.Lock()
        self.reglages = Reglages()
        self.api: Api | None = None
        self.catalogue: Catalogue | None = None
        self.serveur = ""
        self.juges: list[Juge] = []
        self.fils: list[threading.Thread] = []
        self.arret = threading.Event()
        self.en_pause = False
        self.debut = None
        self.fin_prevue = None

        self.enregistrees = 0
        self.deja_connues = 0
        self.refusees = 0
        self.requetes = 0
        self.codes = Counter()
        self.latences = deque(maxlen=400)
        self.scans = deque(maxlen=6000)
        self.lignes = deque(maxlen=400)
        self.paires = set()        # (dossard, tag) déjà envoyés, tous juges confondus
        self.epuise_signale = False

    # — connexion ————————————————————————————————————————————————————————

    def connecter(self, serveur: str, cle: str) -> dict:
        """Lit le catalogue de la compétition active. N'écrit rien."""
        serveur, cle = _demeler(serveur, cle)
        if not serveur:
            return {"ok": False, "message": "adresse du serveur manquante"}
        # La clé ne redescend jamais vers le panneau : après un rechargement de
        # page, son champ est vide alors que le simulateur la connaît toujours.
        # La redemander serait une friction née d'une précaution.
        if not cle and self.api:
            cle = self.api.cle or ""
        api = Api(serveur, cle)
        reponse = api.catalogue()
        if reponse["etat"] != "recu":
            return {"ok": False, "message": reponse.get("message", "catalogue illisible")}
        catalogue = Catalogue(reponse["catalogue"])
        motif = catalogue.utilisable()
        if motif:
            return {"ok": False, "message": motif}
        with self.verrou:
            self.api, self.catalogue, self.serveur = api, catalogue, serveur
            # Relire le catalogue, c'est repartir de zéro : après un effacement
            # des données depuis la console, les couples qu'on croyait pris
            # sont redevenus libres.
            self.paires.clear()
            self.epuise_signale = False
        self.journal("oki", "catalogue",
                     f"« {catalogue.nom} » — {len(catalogue.participants)} dossards, "
                     f"{len(catalogue.blocs)} blocs, version {catalogue.version}")
        return {"ok": True, **self.cible()}

    def cible(self) -> dict:
        if not self.catalogue:
            return {"connecte": False}
        c = self.catalogue
        return {"connecte": True, "serveur": self.serveur, "competition": c.nom,
                "statut": c.statut, "version": c.version,
                "participants": len(c.participants), "blocs": len(c.blocs),
                "zones": sorted(c.zones)}

    # — cycle de vie ————————————————————————————————————————————————————

    def demarrer(self, reglages: Reglages) -> dict:
        if not self.catalogue or not self.api:
            return {"ok": False, "message": "se connecter au serveur d'abord"}
        if self.debut and not self.arret.is_set():
            return {"ok": False, "message": "déjà en cours"}

        self.arret = threading.Event()
        self.reglages = reglages
        self.en_pause = False
        self.debut = time.monotonic()
        self.fin_prevue = (self.debut + reglages.duree_min * 60
                           if reglages.duree_min > 0 else None)
        self.epuise_signale = False
        self.juges = []
        self._poster_les_juges(reglages.juges)

        self.fils = [threading.Thread(target=self._boucle_scan, daemon=True),
                     threading.Thread(target=self._boucle_envoi, daemon=True)]
        for fil in self.fils:
            fil.start()

        self.journal("oki", "simulateur",
                     f"{reglages.juges} juges · {reglages.cadence:g} validations/juge/min "
                     f"· protocole {reglages.protocole}"
                     + (" · À BLANC" if reglages.a_blanc else ""))
        if reglages.protocole == "v2":
            self.journal("warn", "simulateur",
                         "v2 répond 201 sur un doublon : « déjà connues » "
                         "restera à zéro")
        return {"ok": True}

    def _poster_les_juges(self, combien: int):
        """Répartit les juges sur les zones du mur, en tournant."""
        zones = sorted(self.catalogue.zones) or ["?"]
        compte = Counter()
        for i in range(combien):
            zone = zones[i % len(zones)]
            compte[zone] += 1
            self.juges.append(Juge(compte[zone], zone,
                                   self.catalogue.zones.get(zone, []), self))

    def appliquer(self, reglages: Reglages):
        """Change les réglages en cours de route, sans rien perdre."""
        avant = self.reglages.juges
        self.reglages = reglages
        if not self.debut or self.arret.is_set():
            return
        if reglages.juges > avant:
            self._poster_les_juges(reglages.juges - avant)
            self.journal("h", "simulateur", f"{reglages.juges - avant} juge(s) de plus")
        elif reglages.juges < avant:
            # Les juges retirés cessent de scanner mais finissent de vider leur
            # file : abandonner des réussites en cours de route mentirait sur
            # ce que fait le vrai système.
            for juge in self.juges[reglages.juges:]:
                juge.actif = False
            self.journal("h", "simulateur",
                         f"{avant - reglages.juges} juge(s) retiré(s), "
                         f"leur file part quand même")

    def pause(self, valeur: bool):
        self.en_pause = valeur
        self.journal("h", "simulateur", "en pause" if valeur else "reprise")

    def arreter(self):
        if not self.debut:
            return
        self.arret.set()
        self.journal("oki", "simulateur",
                     f"arrêté — {self.enregistrees} enregistrées, "
                     f"{self.deja_connues} déjà connues, {self.refusees} refusées")
        self.debut = None

    def action(self, quoi: str) -> dict:
        if quoi == "flush":
            for juge in self.juges:
                juge.forcer = True
            return {"ok": True}
        if quoi == "vider":
            for juge in self.juges:
                with juge.verrou:
                    juge.file.clear()
                    juge.refusees.clear()
            self.journal("warn", "simulateur", "files vidées à la main")
            return {"ok": True}
        if quoi == "couper":
            coupes = any(j.hors_ligne_jusqua > time.monotonic() for j in self.juges)
            for juge in self.juges:
                juge.retablir() if coupes else juge.couper(600)
            self.journal("warn", "simulateur",
                         "réseau rétabli" if coupes else "réseau coupé pour tous")
            return {"ok": True, "coupe": not coupes}
        return {"ok": False, "message": f"action inconnue : {quoi}"}

    # — les deux boucles ————————————————————————————————————————————————

    def _boucle_scan(self):
        """Fait scanner chaque juge à son propre rythme."""
        prochains = {}
        while not self.arret.is_set():
            maintenant = time.monotonic()
            if self.fin_prevue and maintenant >= self.fin_prevue:
                self.journal("oki", "simulateur", "durée atteinte, plus de scans")
                self.fin_prevue = None
                for juge in self.juges:
                    juge.actif = False
            if not self.en_pause:
                for juge in list(self.juges):
                    if not juge.actif:
                        continue
                    echeance = prochains.get(id(juge))
                    if echeance is None:
                        prochains[id(juge)] = maintenant + random.uniform(0, juge.intervalle())
                        continue
                    if maintenant >= echeance:
                        juge.scanner()
                        prochains[id(juge)] = maintenant + juge.intervalle()
            self.arret.wait(0.08)

    def _boucle_envoi(self):
        """Décide, pour chaque juge, s'il est l'heure d'envoyer.

        Un seul fil pour tous les envois donnerait une file d'attente qui
        n'existe pas sur le terrain : chaque téléphone envoie pour son compte.
        Les envois partent donc dans des fils courts, un par juge et par essai.
        """
        en_vol: dict[int, threading.Thread] = {}
        while not self.arret.is_set():
            maintenant = time.monotonic()
            for juge in list(self.juges):
                fil = en_vol.get(id(juge))
                if fil and fil.is_alive():
                    continue
                with juge.verrou:
                    en_attente = len(juge.file)
                if not doit_envoyer(en_attente, maintenant - juge.dernier_envoi,
                                    juge.echecs, forcer=juge.forcer,
                                    lot_plein=self.reglages.lot_plein,
                                    delai=self.reglages.delai):
                    continue
                juge.forcer = False
                fil = threading.Thread(target=juge.tenter, daemon=True)
                en_vol[id(juge)] = fil
                fil.start()
            self.arret.wait(0.15)

    # — le tirage d'une réussite ——————————————————————————————————————————

    def tirer_une_reussite(self, juge: Juge) -> dict | None:
        """Ce que le juge vient de scanner : un dossard, un bloc de SA zone.

        L'ordre des tirages n'est pas indifférent. On regarde d'abord les cas
        rares (QR étranger, bloc hors circuit, doublon volontaire), puis on
        cherche un passage qui n'a pas encore été validé — sinon le simulateur
        passerait sa vie à réenvoyer les mêmes couples et le serveur ne
        répondrait plus que « déjà connue ».
        """
        c = self.catalogue
        if not c or not juge.blocs:
            return None
        r = self.reglages
        tag = random.choice(juge.blocs)
        hors_circuit = None
        dossard = None

        tirage = random.random() * 100
        if tirage < r.p_inconnu:
            # Un QR qui n'est pas de cette compétition : dossard d'une autre
            # édition, étiquette mal imprimée. Le serveur doit répondre
            # « refusée » sans que le lot entier échoue.
            dossard = c.dossard_max + random.randint(1, 60)
        elif tirage < r.p_inconnu + r.p_hors_circuit:
            candidats = [p["dossard"] for p in c.participants
                         if c.dans_le_circuit(p["dossard"], tag) is False]
            if candidats:
                dossard = random.choice(candidats)
                hors_circuit = True
        elif tirage < r.p_inconnu + r.p_hors_circuit + r.p_doublon:
            deja = [d for (d, t) in self.paires if t == tag]
            if deja:
                dossard = random.choice(deja)

        if dossard is None:
            dossard = self._dossard_neuf(tag)
            if dossard is None:
                return None

        with self.verrou:
            self.paires.add((dossard, tag))

        item = {"ref": str(uuid.uuid4()), "bib": str(dossard), "bloc": tag,
                "at": datetime.now().astimezone().isoformat(timespec="seconds")}
        if hors_circuit:
            item["hors_circuit"] = True
        return item

    def _dossard_neuf(self, tag: str):
        """Un grimpeur du circuit du bloc qui ne l'a pas encore réussi."""
        c = self.catalogue
        candidats = [p["dossard"] for p in c.participants
                     if c.dans_le_circuit(p["dossard"], tag) is not False]
        libres = [d for d in candidats if (d, tag) not in self.paires]
        if libres:
            return random.choice(libres)
        if not self.epuise_signale:
            self.epuise_signale = True
            self.journal("warn", "simulateur",
                         "tous les passages possibles ont été validés — "
                         "la suite ne produira que des doublons")
        return random.choice(candidats) if candidats else None

    # — compteurs et journal ——————————————————————————————————————————————

    def facteur_de_montee(self) -> float:
        """De combien la cadence est multipliée à cet instant."""
        if not self.debut:
            return 1.0
        ecoule = time.monotonic() - self.debut
        if self.reglages.montee == "progressive":
            return max(0.12, min(1.0, ecoule / MONTEE_PROGRESSIVE))
        if self.reglages.montee == "vagues":
            # Les grimpeurs tournent : une zone se remplit, se vide, se remplit.
            return 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * ecoule / PERIODE_VAGUE))
        return 1.0

    def noter_scan(self):
        with self.verrou:
            self.scans.append(time.time())

    def noter_requete(self, code, latence):
        with self.verrou:
            self.requetes += 1
            self.codes[str(code) if code else "réseau"] += 1
            if code:
                self.latences.append(latence)

    def noter_verdicts(self, enregistrees, deja, refusees):
        with self.verrou:
            self.enregistrees += max(0, enregistrees)
            self.deja_connues += deja
            self.refusees += refusees

    def journal(self, niveau, qui, texte):
        with self.verrou:
            self.lignes.append({"t": datetime.now().strftime("%H:%M:%S"),
                                "n": niveau, "qui": qui, "texte": texte})

    # — l'état, tel que le panneau le lit ————————————————————————————————

    def etat(self) -> dict:
        maintenant = time.time()
        with self.verrou:
            latences = sorted(self.latences)
            scans = list(self.scans)
            lignes = list(self.lignes)[-120:]
            codes = dict(self.codes)
            enregistrees, deja = self.enregistrees, self.deja_connues
            refusees, requetes = self.refusees, self.requetes

        juges = [j.vue() for j in self.juges]
        en_file = sum(j["file"] for j in juges)

        # L'histogramme : une barre toutes les cinq secondes sur cinq minutes.
        barres = [0] * 60
        for t in scans:
            age = maintenant - t
            if 0 <= age < 300:
                barres[59 - int(age // 5)] += 1

        recents = [t for t in scans if maintenant - t <= 60]
        return {
            "cible": self.cible(),
            "en_cours": bool(self.debut) and not self.arret.is_set(),
            "en_pause": self.en_pause,
            "depuis": (time.monotonic() - self.debut) if self.debut else 0,
            "restant": max(0, self.fin_prevue - time.monotonic()) if self.fin_prevue else None,
            "compteurs": {
                "enregistrees": enregistrees, "deja": deja,
                "file": en_file, "refusees": refusees,
                "p50": _centile(latences, 50), "p95": _centile(latences, 95),
                "requetes": requetes, "par_minute": len(recents),
                "codes": codes,
            },
            "barres": barres,
            "juges": juges,
            "journal": lignes,
            "reglages": asdict(self.reglages),
        }


def _centile(tries: list, rang: int):
    if not tries:
        return None
    i = min(len(tries) - 1, int(round((rang / 100.0) * (len(tries) - 1))))
    return round(tries[i] * 1000)


def _demeler(serveur: str, cle: str) -> tuple[str, str]:
    """Accepte le LIEN JUGE de la console à la place de la clé.

    Le lien que la console donne aux bénévoles porte déjà les deux
    informations (`https://…/juge?j=…`). Le coller entier est le geste naturel ;
    exiger de le découper à la main serait une friction gratuite.
    """
    serveur = (serveur or "").strip()
    cle = (cle or "").strip()
    for valeur in (cle, serveur):
        if "://" in valeur and "j=" in valeur:
            from urllib.parse import urlparse, parse_qs
            morceaux = urlparse(valeur)
            jeton = (parse_qs(morceaux.query).get("j") or [""])[0]
            if jeton:
                return f"{morceaux.scheme}://{morceaux.netloc}", jeton
    if "://" not in serveur and serveur:
        serveur = "https://" + serveur
    return serveur.rstrip("/"), cle
