#!/usr/bin/env python3
"""Extrait la section d'une version depuis CHANGELOG.md.

Sort en erreur si la section n'existe pas : c'est ce qui rend le changelog
contraignant. Utilise par le workflow de release ET par scripts/release.sh, pour
que l'echec arrive sur le poste d'Adrien plutot qu'en CI quand c'est possible.

    python3 scripts/extract_changelog.py 1.2.0
"""
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def extraire(version: str, texte: str) -> str:
    """Renvoie le corps de la section `## [version]`, sans son titre."""
    debut = re.compile(rf"^## \[{re.escape(version)}\][^\n]*$", re.M)
    m = debut.search(texte)
    if not m:
        raise SystemExit(
            f"ECHEC : aucune section '## [{version}]' dans CHANGELOG.md.\n"
            f"Ajoute-la avant de taguer — le corps de la release GitHub en est\n"
            f"tire, et sans elle personne ne sait ce que contient {version}."
        )
    reste = texte[m.end():]
    suivante = re.search(r"^## \[", reste, re.M)
    corps = (reste[:suivante.start()] if suivante else reste).strip()
    if not corps:
        raise SystemExit(f"ECHEC : la section '## [{version}]' est vide.")
    return corps


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: extract_changelog.py <version>")
    version = sys.argv[1].lstrip("v")
    texte = (RACINE / "CHANGELOG.md").read_text(encoding="utf-8")
    print(extraire(version, texte))


if __name__ == "__main__":
    main()
