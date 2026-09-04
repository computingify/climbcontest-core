"""Deviner ce que veulent dire les champs du formulaire — spec 008.

Demande d'Adrien le 04/09 : « lors des imports je veux un maximum
d'automatisation ». Ce module est cette automatisation.

## Ce qu'on devine, et ce qu'on ne devine pas

Trois choses se devinent bien parce que les formulaires du monde réel les
nomment presque toujours pareil :

| Ce qu'on cherche | Ce qu'on reconnaît |
| --- | --- |
| L'année de naissance | *date de naissance*, *né(e) le*, *birth date*, *anniversaire* |
| Le genre | *sexe*, *genre*, *fille ou garçon*, *catégorie F/H* |
| Le club | *club*, *association*, *structure*, *licence FFME* |

Et une quatrième se devine **par ses réponses** plutôt que par son nom : un
champ dont toutes les réponses sont dans *{fille, garçon, f, h, m, féminin,
masculin…}* est un champ de genre, quel que soit son intitulé — « Votre enfant
est », « Il/Elle »… C'est le filet qui rattrape les formulaires écrits à la
main, et c'est celui qui sert le plus.

## Ce qu'on ne devine jamais

**Rien n'est deviné en silence.** La console montre ce qui a été trouvé, avec
les réponses vues, et l'organisateur corrige d'un clic. Deviner sans le dire
transformerait une erreur de reconnaissance en cent inscriptions mal rangées,
et personne ne saurait où regarder.

## Pourquoi le genre a une table intégrée

« Fille », « F », « Féminin », « Girl » sont quatre écritures de la même chose.
Faire saisir cette table à la main à chaque édition, c'est quatre lignes de
paramétrage pour une information que tout le monde écrit de la même façon. La
table intégrée les couvre ; la table de l'édition, elle, ne sert plus qu'aux
cas vraiment particuliers — et elle **gagne** toujours, parce que c'est un
humain qui l'a écrite.
"""

import re
import unicodedata

#: Ce que « F » veut dire, et ce que « H » veut dire, dans les écritures qu'on
#: rencontre vraiment. Comparé sans accent et en minuscules.
GENRES_CONNUS = {
    "f": "F", "fille": "F", "filles": "F", "feminin": "F", "feminine": "F",
    "femme": "F", "girl": "F", "female": "F", "mademoiselle": "F", "mme": "F",
    "h": "H", "m": "H", "garcon": "H", "garcons": "H", "masculin": "H",
    "homme": "H", "boy": "H", "male": "H", "monsieur": "H", "mr": "H",
}

#: Les intitulés qui désignent chaque rôle. Cherchés en sous-chaîne, sans
#: accent : « Date de naissance » comme « DATE DE NAISSANCE de l'enfant ».
INDICES = {
    "naissance": ("date de naissance", "annee de naissance", "naissance",
                  "ne le", "nee le", "birth", "anniversaire", "age"),
    "genre": ("sexe", "genre", "fille ou garcon", "garcon ou fille",
              "categorie f", "gender", "civilite"),
    "club": ("club", "association", "structure", "licence ffme", "comite"),
}

#: Une année plausible dans une réponse : quatre chiffres.
_QUATRE_CHIFFRES = re.compile(r"\d{4}")


def _sans_accent(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", str(texte or ""))
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


def genre_connu(reponse) -> str | None:
    """« Fille » → « F ». None si ce n'est pas une écriture reconnue.

    ⚠️ Ne devine JAMAIS par défaut. Une réponse inconnue rend None, et
    l'inscription part en attente — faire entrer une grimpeuse dans un
    classement masculin parce qu'on a choisi une valeur par défaut serait le
    genre d'erreur que personne ne remarque avant le podium.
    """
    if reponse is None:
        return None
    return GENRES_CONNUS.get(_sans_accent(reponse).strip())


def champs_du_formulaire(articles) -> dict[str, list[str]]:
    """Les champs vus, et les réponses **distinctes** de chacun.

    On ne garde que les réponses, pas qui a répondu quoi : ce module ne sert
    qu'à reconnaître des colonnes.
    """
    vus: dict[str, set] = {}
    for article in articles:
        sources = [article.get("customFields") or []]
        for option in article.get("options") or []:
            sources.append(option.get("customFields") or [])
        for champs in sources:
            if not isinstance(champs, list):
                continue
            for champ in champs:
                nom = (champ.get("name") or "").strip()
                if nom:
                    vus.setdefault(nom, set()).add(
                        (champ.get("answer") or "").strip())
    return {nom: sorted(v for v in valeurs if v) for nom, valeurs in vus.items()}


def _ressemble_a_des_genres(reponses) -> bool:
    """Toutes les réponses sont-elles des écritures de genre connues ?

    C'est le filet qui rattrape « Votre enfant est » et les autres intitulés
    qu'aucune liste de mots-clés ne prévoira. On exige que **tout** soit
    reconnu : un seul intrus, et ce n'est pas un champ de genre.
    """
    utiles = [r for r in reponses if r]
    if not (1 <= len(utiles) <= 6):
        return False
    return all(genre_connu(r) for r in utiles)


def _ressemble_a_des_annees(reponses) -> bool:
    utiles = [r for r in reponses if r]
    if not utiles:
        return False
    return all(_QUATRE_CHIFFRES.search(str(r)) for r in utiles)


def deviner(champs: dict[str, list[str]]) -> dict:
    """Propose un rôle pour chaque champ. **Une proposition, pas une décision.**

    Rend `{"champs": {...}, "genre_valeurs": {...}, "trouves": [...]}` :
    `trouves` liste les rôles reconnus, pour que la console dise ce qu'elle a
    trouvé toute seule au lieu de le faire passer pour une saisie.

    L'ordre compte : le nom d'abord, les réponses ensuite. Un champ nommé
    « Sexe » est un champ de genre même si personne n'y a encore répondu.
    """
    proposition = {"naissance": None, "genre": None, "club": None}

    for role, indices in INDICES.items():
        for nom in sorted(champs):
            sans = _sans_accent(nom)
            if any(indice in sans for indice in indices):
                proposition[role] = nom
                break

    # Le filet : reconnaitre par les REPONSES ce que le nom n'a pas dit.
    if proposition["genre"] is None:
        for nom in sorted(champs):
            if _ressemble_a_des_genres(champs[nom]):
                proposition["genre"] = nom
                break
    if proposition["naissance"] is None:
        for nom in sorted(champs):
            if _ressemble_a_des_annees(champs[nom]):
                proposition["naissance"] = nom
                break

    valeurs = {}
    if proposition["genre"]:
        for reponse in champs.get(proposition["genre"], []):
            reconnu = genre_connu(reponse)
            if reconnu:
                valeurs[reponse] = reconnu

    return {
        "champs": proposition,
        "genre_valeurs": valeurs,
        "trouves": [role for role, nom in proposition.items() if nom],
        # Les reponses de genre qu'on n'a PAS su ranger. La console les montre :
        # ce sont les seules lignes qui demandent encore un geste.
        "genres_inconnus": sorted(
            r for r in champs.get(proposition["genre"] or "", [])
            if r and not genre_connu(r)),
    }
