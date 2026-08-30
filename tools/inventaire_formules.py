"""Inventaire EXHAUSTIF des formules d'un classeur — LECTURE SEULE.

Usage : python3 tools/inventaire_formules.py <spreadsheet_id> <sortie.json>
Puis : python3 tools/inventaire_formules.py --condenser <sortie.json>


Pour chaque onglet : toutes les cellules portant une formule, dédupliquées par
MOTIF (les références déplacées d'une recopie sont normalisées), avec le nombre
d'occurrences et une cellule d'exemple. C'est ce qui permet de comparer un
classeur de 200 000 cellules à un backend en une lecture humaine.
"""
import json
import pickle
import re
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

RACINE = Path(__file__).resolve().parent.parent

creds = pickle.loads((RACINE / "token.pickle").read_bytes())
if not creds.valid:
    creds.refresh(Request())
api = build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()

if sys.argv[1] == "--condenser":
    from collections import defaultdict
    def structure(f):
        # 'Feuille'!A1:B2, Feuille!A1, $A$1, A1, A:A, 1:1
        f = re.sub(r"('[^']+'|[A-Za-zÀ-ÿ_ ]+)?!\$?[A-Z]{1,3}\$?\d*(:\$?[A-Z]{1,3}\$?\d*)?", "•", f)
        f = re.sub(r"\$?[A-Z]{1,3}\$?\d+(:\$?[A-Z]{1,3}\$?\d+)?", "•", f)
        f = re.sub(r"\$?[A-Z]{1,3}:\$?[A-Z]{1,3}", "•", f)
        f = re.sub(r"\s+", "", f)
        return f

    donnees = json.load(open(sys.argv[2]))
    for onglet, d in donnees.items():
        groupes = defaultdict(lambda: {"n": 0, "exemples": []})
        for motif, info in d["motifs"].items():
            s = structure(info["exemple"])
            g = groupes[s]
            g["n"] += info["n"]
            if len(g["exemples"]) < 1:
                g["exemples"].append(f"{onglet}!{info['exemple_cellule']} = {info['exemple']}")
        print(f"\n======== {onglet} — {d['formules']} formules, {len(groupes)} structures ========")
        for s, g in sorted(groupes.items(), key=lambda kv: -kv[1]["n"]):
            ex = g["exemples"][0]
            if len(ex) > 240: ex = ex[:240] + "…"
            print(f"[x{g['n']:5d}] {ex}")
    sys.exit(0)

SID = sys.argv[1]
SORTIE = Path(sys.argv[2])

# Une requete par onglet (fields cible les formules seulement).
meta = api.get(spreadsheetId=SID, includeGridData=False).execute()
titres = [s["properties"]["title"] for s in meta["sheets"]]
print(f"{meta['properties']['title']} : {len(titres)} onglets")

def colonne_nom(n):
    nom = ""
    n += 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        nom = chr(65 + r) + nom
    return nom

def normaliser(f):
    """Remplace les numeros de ligne et colonnes par des jokers pour que les
    recopies d'une meme formule se regroupent."""
    # references de cellule : $A$1, A1, AB123, Feuille!A1
    f = re.sub(r"(\$?[A-Z]{1,3}\$?)\d{1,4}", r"\1#", f)
    return f

inventaire = {}
for titre in titres:
    r = api.get(
        spreadsheetId=SID,
        ranges=[f"'{titre}'"],
        fields="sheets(data(startRow,startColumn,rowData(values(userEnteredValue))))",
    ).execute()
    motifs = {}
    total = 0
    for data in r.get("sheets", [{}])[0].get("data", []):
        r0 = data.get("startRow", 0)
        c0 = data.get("startColumn", 0)
        for i, ligne in enumerate(data.get("rowData", [])):
            for j, cellule in enumerate(ligne.get("values", []) or []):
                uev = cellule.get("userEnteredValue") or {}
                formule = uev.get("formulaValue")
                if not formule:
                    continue
                total += 1
                motif = normaliser(formule)
                if motif not in motifs:
                    motifs[motif] = {
                        "exemple_cellule": f"{colonne_nom(c0 + j)}{r0 + i + 1}",
                        "exemple": formule if len(formule) < 700 else formule[:700] + "…",
                        "n": 0,
                    }
                motifs[motif]["n"] += 1
    inventaire[titre] = {"formules": total, "motifs": motifs}
    print(f"  {titre:24s} {total:6d} formules, {len(motifs):4d} motifs")

SORTIE.write_text(json.dumps(inventaire, ensure_ascii=False, indent=1))
print("->", SORTIE)
