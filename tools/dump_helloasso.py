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
    python3 tools/dump_helloasso.py --champs Event bloc-party

Le nom court de l'association n'est pas demande : la cle le connait.

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
    # `sans_base` : ce script n'a ni contexte Flask ni base de donnees.
    return ha.ClientHelloAsso({**secret, "environnement": environnement},
                              sans_base=True)


def _association(client, propose: str | None = None) -> str:
    """Le nom court de l'association. La cle le connait, on ne le demande pas.

    Vaut pour la console comme pour ce script : un nom tape a la main a sa
    faute de frappe, et le symptome est « aucun formulaire trouve » -- qui
    n'accuse personne.
    """
    if propose:
        return propose
    trouvees = client.organisations()
    if not trouvees:
        usage("Cette cle ne donne acces a aucune association.")
    if len(trouvees) > 1:
        print("Plusieurs associations : " +
              ", ".join(o["slug"] for o in trouvees), file=sys.stderr)
    return trouvees[0]["slug"]


def formulaires(slug: str | None) -> None:
    client = _client()
    slug = _association(client, slug)
    print(f"association : {slug}\n")
    for f in client.formulaires(slug):
        print(f"{f.get('formType'):<14} {f.get('formSlug'):<34} {f.get('title')}")


def champs(slug: str, type_de_formulaire: str, slug_formulaire: str) -> None:
    """Les champs du formulaire, et les valeurs distinctes de chacun.

    C'est de cette sortie qu'on remplit la correspondance de la console : quel
    champ porte l'annee de naissance, lequel le genre, lequel le club.
    """
    client = _client()
    slug = _association(client, slug)
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
        # L'association est FACULTATIVE : la cle la connait.
        formulaires(arguments[1] if len(arguments) > 1 else None)
    elif arguments[0] == "--champs":
        if len(arguments) < 3:
            usage("Usage : --champs <type> <formulaire> [association]")
        champs(arguments[3] if len(arguments) > 3 else None,
               arguments[1], arguments[2])
    else:
        usage(f"Option inconnue : {arguments[0]}")


if __name__ == "__main__":
    try:
        main()
    except ha.ErreurHelloAsso as e:
        raise SystemExit(f"\n⚠️  {e.message}\n")
