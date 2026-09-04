"""Regarder un formulaire HelloAsso — **lecture seule** — spec 008.

## À quoi ça sert, et pourquoi c'est le premier geste du chantier

La spec 008 fait reposer toute la catégorie sur **l'année de naissance** lue
dans un champ personnalisé du formulaire. Si le formulaire du club ne demande
pas cette information, la décision D1 tombe entièrement — et le symptôme, si on
s'en aperçoit trop tard, sera « les cent inscriptions sont en attente » un matin
de compétition, avec pour seul message « année hors barème », qui n'accuse
personne.

Cet outil répond à la question **avant** qu'une ligne de relevé soit écrite :

    python3 tools/dump_helloasso.py --formulaires
    python3 tools/dump_helloasso.py --champs Event bloc-party-2026

## Ce qu'il ne fait pas

Il n'écrit **rien**, ni chez HelloAsso ni en base : il n'appelle que des `GET`.
Et comme `tools/load/`, il refuse de démarrer sans que l'environnement soit
nommé explicitement — on ne veut pas découvrir après coup qu'on interrogeait la
production en croyant tester.

    CLIMBCONTEST_HELLOASSO_ENV=sandbox python3 tools/dump_helloasso.py --formulaires

⚠️ Il n'affiche **jamais** de réponse individuelle : ni nom, ni date de
naissance. Les inscrits d'une compétition d'escalade sont des mineurs. Ce qu'on
montre ici, ce sont les **noms des champs** et les **valeurs distinctes** vues
dans les listes de choix — de quoi remplir la correspondance de la console, et
rien de plus.
"""

import json
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from climbcontest.helloasso import client as ha           # noqa: E402


def usage(message: str = "") -> None:
    if message:
        print(f"\n⚠️  {message}\n", file=sys.stderr)
    print(__doc__)
    raise SystemExit(2 if message else 0)


def _client():
    environnement = os.environ.get("CLIMBCONTEST_HELLOASSO_ENV")
    if environnement not in ha.HOTES:
        usage("Definir CLIMBCONTEST_HELLOASSO_ENV a « production » ou « sandbox ». "
              "Ce script ne devine pas sur quel compte il travaille.")

    secret = ha.lire_secret()
    if secret is None:
        usage("Aucune cle trouvee. Poser helloasso.json dans le dossier des "
              "secrets, ou definir CLIMBCONTEST_SECRETS_DIR.")
    return ha.ClientHelloAsso({**secret, "environnement": environnement})


def formulaires(slug: str) -> None:
    for f in _client().formulaires(slug):
        print(f"{f.get('formType'):<14} {f.get('formSlug'):<34} {f.get('title')}")


def champs(slug: str, type_de_formulaire: str, slug_formulaire: str) -> None:
    """Les champs du formulaire, et les valeurs distinctes de chacun.

    C'est de cette sortie qu'on remplit la correspondance de la console : quel
    champ porte l'annee de naissance, lequel le genre, lequel le club.
    """
    client = _client()
    vus: dict[str, set] = {}
    combien = 0
    for article in client.articles(slug, type_de_formulaire, slug_formulaire):
        combien += 1
        for champ in (article.get("customFields") or []):
            nom = (champ.get("name") or "").strip()
            if not nom:
                continue
            reponse = (champ.get("answer") or "").strip()
            valeurs = vus.setdefault(nom, set())
            # ⚠️ On ne garde que les valeurs qui se REPETENT, c'est-a-dire les
            # listes de choix : « Fille », « Garcon », un nom de club. Une
            # reponse unique est une donnee personnelle -- une date de
            # naissance, un numero de licence -- et n'a rien a faire ici.
            valeurs.add(reponse)

    print(f"\n{combien} article(s) lus.\n")
    for nom in sorted(vus):
        valeurs = {v for v in vus[nom] if v}
        distinctes = len(valeurs)
        if distinctes <= 8:
            apercu = ", ".join(sorted(valeurs)[:8])
        else:
            # Trop de valeurs distinctes : c'est un champ libre, donc une
            # donnee personnelle. On dit sa forme, jamais son contenu.
            apercu = f"{distinctes} valeurs differentes (champ libre)"
        print(f"  {nom:<34} {apercu}")
    print()


def main() -> None:
    arguments = sys.argv[1:]
    if not arguments or arguments[0] in ("-h", "--help"):
        usage()

    if arguments[0] == "--formulaires":
        slug = arguments[1] if len(arguments) > 1 else os.environ.get(
            "CLIMBCONTEST_HELLOASSO_ORG")
        if not slug:
            usage("Le nom court de l'association est attendu : "
                  "--formulaires annonay-escalade")
        formulaires(slug)
    elif arguments[0] == "--champs":
        if len(arguments) < 3:
            usage("Usage : --champs <type> <formulaire> [association]")
        slug = arguments[3] if len(arguments) > 3 else os.environ.get(
            "CLIMBCONTEST_HELLOASSO_ORG")
        if not slug:
            usage("Le nom court de l'association est attendu.")
        champs(slug, arguments[1], arguments[2])
    else:
        usage(f"Option inconnue : {arguments[0]}")


if __name__ == "__main__":
    try:
        main()
    except ha.ErreurHelloAsso as e:
        raise SystemExit(f"\n⚠️  {e.message}\n")
