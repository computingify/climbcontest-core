"""Extrait d'un dump de classeur un jeu de test compact :
entrées (grimpeurs, blocs, tops) + sorties attendues (scores et rangs).

Sert de référence d'acceptation pour le futur moteur de classement :
le backend devra reproduire exactement ces scores.
"""
import json
import sys

SRC = sys.argv[1]
OUT = sys.argv[2]

d = json.load(open(SRC))
D = d["data"]


def grid(tab, render="FORMATTED_VALUE"):
    return D[tab][render]


def at(g, row, col):
    try:
        v = g[row - 1][col]
    except IndexError:
        return ""
    return str(v).strip()


imp = grid("Import")
res = grid("Résultats")
scr = grid("Scratchs")
lst = grid("Listes")
plan = grid("Plan")

# ---- grimpeurs : Listes F2:K121 (0=F nom, 1=G bib, 4=J club, 5=K cat)
climbers = []
for r in range(2, 200):
    name = at(lst, r, 5)
    bib = at(lst, r, 6)
    if not name or not bib:
        continue
    climbers.append(
        {
            "bib": int(bib),
            "name": name,
            "club": at(lst, r, 9),
            "category": at(lst, r, 10),
        }
    )

# ---- blocs : Import col A = numéro, col B = tag ; Résultats L1 = couleur, L18 = n° import
blocs = {}
for r in range(2, 120):
    num = at(imp, r, 0)
    tag = at(imp, r, 1)
    if num and tag:
        blocs[int(num)] = {"number": int(num), "tag": tag, "color": None, "circuits": []}

# couleur : Résultats ligne 1 (colonnes H..DC = index 7..106), ligne 18 = n° du bloc
for c in range(7, 107):
    num = at(res, 18, c)
    color = at(res, 1, c)
    if num and num.isdigit() and int(num) in blocs:
        blocs[int(num)]["color"] = color

# circuits : Plan D29:.. -> zone(0) num(16) id(-1), colonnes J/L/N (6/8/10) = circuits
circuit_names = [at(plan, 28, 3 + i) for i in range(0, 14)]
for r in range(29, 200):
    row = plan[r - 1] if r - 1 < len(plan) else []
    line = [str(x).strip() for x in row[3:25]]
    if len(line) < 17:
        continue
    num = line[-1]
    if not num.isdigit() or int(num) not in blocs:
        continue
    for idx in range(5, 14):
        if idx < len(line) and line[idx]:
            cname = circuit_names[idx] if idx < len(circuit_names) else ""
            if cname:
                blocs[int(num)]["circuits"].append(cname)

# ---- tops : Import, colonne = bib+3, ligne = numéro de bloc +1
tops = []
for num in blocs:
    r = num + 1
    for cl in climbers:
        c = cl["bib"] + 3 - 1  # index 0-based
        if at(imp, r, c).upper() == "A":
            tops.append({"bib": cl["bib"], "bloc": num})

# ---- résultats attendus : blocs de 6 colonnes à partir de DE (108)
def read_ranking(g, first_col, label_row):
    out = {}
    col = first_col
    while col + 2 < 200:
        label = at(g, label_row, col)
        if not label:
            break
        rows = []
        for r in range(19, 160):
            if at(g, r, col) != "1":
                continue
            bib = at(g, r, 6)
            score = at(g, r, col + 1)
            rank = at(g, r, col + 2)
            if bib and score:
                rows.append(
                    {"bib": int(bib), "score": int(float(score.replace(",", "."))), "rank": int(rank)}
                )
        if rows:
            out[label] = sorted(rows, key=lambda x: (x["rank"], x["bib"]))
        col += 6
    return out


fixture = {
    "source": d["title"],
    "spreadsheetId": d["spreadsheetId"],
    "climbers": climbers,
    "blocs": sorted(blocs.values(), key=lambda b: b["number"]),
    "tops": sorted(tops, key=lambda t: (t["bib"], t["bloc"])),
    "expected": {
        "by_category": read_ranking(res, 108, 18),
        "by_circuit": read_ranking(scr, 108, 18),
    },
}

json.dump(fixture, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{d['title']}")
print(f"  grimpeurs : {len(climbers)}")
print(f"  blocs     : {len(blocs)}")
print(f"  tops      : {len(tops)}")
print(f"  classements par catégorie : {list(fixture['expected']['by_category'])}")
print(f"  classements par circuit   : {list(fixture['expected']['by_circuit'])}")
print(f"  -> {OUT}")
