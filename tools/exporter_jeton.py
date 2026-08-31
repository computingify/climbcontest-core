#!/usr/bin/env python3
"""`token.pickle` → le JSON à coller dans la console (spec 015).

À lancer **sur ton Mac**, là où le jeton existe — jamais sur le serveur.

    python3 tools/exporter_jeton.py                   # cherche token.pickle ici
    python3 tools/exporter_jeton.py chemin/token.pickle
    python3 tools/exporter_jeton.py token.base64

La sortie est le contenu à coller dans **Console → Classeur → Jeton Google**.

⚠️ Ce texte contient le `refresh_token` : c'est un **secret**, au même titre
qu'un mot de passe. Il ne se commit pas, il ne se colle pas dans une
conversation, et le fichier temporaire dans lequel on le range se supprime.

Le pickle ne se déserialise QUE sur ta machine, avec un fichier que tu as
produit toi-même. C'est toute la raison d'être de ce script : le serveur, lui,
ne fera jamais `pickle.loads()` sur quelque chose venu du réseau.

Il faut un Python où `google-auth` est installé (le pickle contient un objet
`google.oauth2.credentials.Credentials`) :

    python3 -m venv /tmp/gs && /tmp/gs/bin/pip install google-auth
    /tmp/gs/bin/python tools/exporter_jeton.py
"""
import base64
import pickle
import sys
from pathlib import Path

CANDIDATS = ("token.json", "token.pickle", "token.base64")


def charger(chemin: Path):
    donnees = chemin.read_bytes()
    if chemin.name.endswith(".base64"):
        donnees = base64.b64decode(donnees)
    return pickle.loads(donnees)


def main() -> int:
    if len(sys.argv) > 1:
        chemin = Path(sys.argv[1])
    else:
        trouves = [Path(nom) for nom in CANDIDATS if Path(nom).exists()]
        if not trouves:
            print("Aucun jeton ici. Attendu : " + ", ".join(CANDIDATS)
                  + f"\nRepertoire courant : {Path.cwd()}", file=sys.stderr)
            return 1
        chemin = trouves[0]

    if not chemin.exists():
        print(f"Introuvable : {chemin}", file=sys.stderr)
        return 1

    if chemin.name.endswith(".json"):
        # Deja au bon format : on le recopie, ca evite d'expliquer deux gestes.
        sys.stdout.write(chemin.read_text())
        print(f"\n(deja au format JSON : {chemin})", file=sys.stderr)
        return 0

    try:
        creds = charger(chemin)
    except Exception as e:                                   # noqa: BLE001
        print(f"Lecture de {chemin} impossible : {e}\n"
              "Il faut un Python avec google-auth installe (voir l'en-tete).",
              file=sys.stderr)
        return 1

    if not hasattr(creds, "to_json"):
        print(f"{chemin} ne contient pas un objet Credentials Google.",
              file=sys.stderr)
        return 1

    sys.stdout.write(creds.to_json())
    print("", file=sys.stderr)
    if not getattr(creds, "refresh_token", None):
        print("⚠️  Ce jeton n'a PAS de refresh_token : la console le refusera, "
              "et elle a raison — il mourrait a la premiere expiration.",
              file=sys.stderr)
    else:
        print("✓ A coller dans Console → Classeur → « Jeton Google ». "
              "C'est un SECRET : ne le laisse pas trainer.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
