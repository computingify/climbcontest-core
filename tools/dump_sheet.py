"""Lecture SEULE du classeur ClimbContest.

Réutilise exactement le mécanisme d'authentification du serveur
(climbcontest-core/google_sheets.py) : token.pickle, ou token.base64 en repli.
N'appelle QUE des méthodes de lecture (spreadsheets().get, values().batchGet).
Aucune écriture possible depuis ce script.

Sortie : dump_<sheetid>.json dans le dossier courant.
"""
import base64
import json
import os
import pickle
import sys
from io import BytesIO

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SPREADSHEET_ID = sys.argv[1] if len(sys.argv) > 1 else "1h3e8QUSXnCJLSYSFyB8X92cppDubeDx0yi8mn3NSh5s"


def load_creds():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
    elif os.path.exists("token.base64"):
        with open("token.base64") as f:
            creds = pickle.load(BytesIO(base64.b64decode(f.read())))
    if creds is None:
        raise SystemExit("Aucun jeton trouvé (token.pickle / token.base64)")
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print("Jeton expiré -> rafraîchissement…")
            creds.refresh(Request())
        else:
            raise SystemExit(
                "Jeton invalide et non rafraîchissable : il faut refaire le "
                "consentement OAuth depuis une machine avec navigateur."
            )
    return creds


def main():
    api = build("sheets", "v4", credentials=load_creds()).spreadsheets()

    meta = api.get(spreadsheetId=SPREADSHEET_ID, includeGridData=False).execute()
    title = meta.get("properties", {}).get("title")
    tabs = []
    for s in meta.get("sheets", []):
        p = s["properties"]
        g = p.get("gridProperties", {})
        tabs.append(
            {
                "title": p["title"],
                "index": p.get("index"),
                "rows": g.get("rowCount"),
                "cols": g.get("columnCount"),
                "hidden": p.get("hidden", False),
            }
        )

    print(f"Classeur : {title}")
    print(f"{len(tabs)} onglet(s) :")
    for t in tabs:
        flag = " [masqué]" if t["hidden"] else ""
        print(f"  - {t['title']:<28} {t['rows']}x{t['cols']}{flag}")

    ranges = [f"'{t['title']}'" for t in tabs]
    out = {"spreadsheetId": SPREADSHEET_ID, "title": title, "tabs": tabs, "data": {}}

    for render in ("FORMATTED_VALUE", "FORMULA"):
        res = api.values().batchGet(
            spreadsheetId=SPREADSHEET_ID,
            ranges=ranges,
            valueRenderOption=render,
        ).execute()
        for t, vr in zip(tabs, res.get("valueRanges", [])):
            out["data"].setdefault(t["title"], {})[render] = vr.get("values", [])

    path = f"dump_{SPREADSHEET_ID[:12]}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    size = os.path.getsize(path)
    print(f"\nEcrit : {path} ({size/1024:.0f} ko)")


if __name__ == "__main__":
    main()
