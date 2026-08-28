"""Vérifie qu'un algorithme de classement reproduit les résultats du classeur.

    python3 tools/verify_ranking.py fixtures/contest-nov2025.json

Sert de test d'acceptation : tant que ce script ne sort pas 0 écart, le moteur
de classement du backend n'est pas conforme au classeur.
"""
import json
import sys
from collections import defaultdict

MAX_BLOC_VALUE = 1000


def circuit_of(category):
    """« U11 F » -> « U11 »"""
    return category.rsplit(" ", 1)[0]


def compute(members, tops_by_bib, circuits_by_bloc, circuit):
    """Classement d'un groupe de grimpeurs sur un circuit donné.

    Seuls comptent les blocs du circuit. La valeur d'un bloc vaut
    1000 / nombre de grimpeurs DU GROUPE qui l'ont réussi.
    """
    def counts(bloc):
        return bloc in circuits_by_bloc and circuit in circuits_by_bloc[bloc]

    tops_in_scope = {
        bib: {b for b in tops_by_bib.get(bib, ()) if counts(b)} for bib in members
    }

    toppers = defaultdict(set)
    for bib, blocs in tops_in_scope.items():
        for b in blocs:
            toppers[b].add(bib)

    value = {b: MAX_BLOC_VALUE / len(s) for b, s in toppers.items() if s}
    scores = {bib: round(sum(value.get(b, 0) for b in blocs)) for bib, blocs in tops_in_scope.items()}

    ordered = sorted(scores.items(), key=lambda kv: -kv[1])
    ranks, prev_score, prev_rank = {}, None, 0
    for i, (bib, sc) in enumerate(ordered, 1):
        rank = prev_rank if sc == prev_score else i
        ranks[bib] = rank
        prev_score, prev_rank = sc, rank
    return scores, ranks


def main(path):
    f = json.load(open(path, encoding="utf-8"))
    circuits_by_bloc = {b["number"]: set(b["circuits"]) for b in f["blocs"]}
    tops_by_bib = defaultdict(set)
    for t in f["tops"]:
        tops_by_bib[t["bib"]].add(t["bloc"])

    total_ok = total_ko = 0
    for label, groups in (("catégorie", f["expected"]["by_category"]),
                          ("circuit", f["expected"]["by_circuit"])):
        for name, rows in groups.items():
            members = {r["bib"] for r in rows}
            circuit = circuit_of(name) if label == "catégorie" else name
            scores, ranks = compute(members, tops_by_bib, circuits_by_bloc, circuit)
            ok = ko = 0
            for r in rows:
                if scores.get(r["bib"]) == r["score"] and ranks.get(r["bib"]) == r["rank"]:
                    ok += 1
                else:
                    ko += 1
                    if ko <= 3:
                        print(
                            f"    ECART {name} bib {r['bib']} : "
                            f"classeur score={r['score']} rang={r['rank']} | "
                            f"calcule score={scores.get(r['bib'])} rang={ranks.get(r['bib'])}"
                        )
            status = "OK  " if ko == 0 else "ECART"
            print(f"  [{status}] {label:<9} {name:<8} {ok} grimpeur(s) conforme(s), {ko} ecart(s)")
            total_ok += ok
            total_ko += ko

    print(f"\nTotal : {total_ok} conforme(s), {total_ko} ecart(s)")
    return 1 if total_ko else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "fixtures/contest-nov2025.json"))
