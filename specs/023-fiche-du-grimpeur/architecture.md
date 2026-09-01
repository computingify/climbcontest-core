# Architecture — 023 fiche-du-grimpeur

## Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/fiches.py` | **Nouveau** — le plan de la salle, l'ordre des blocs, la construction des fiches. Aucun Flask |
| `climbcontest/templates/dossards.html` | Réécrit : la bande devient une fiche A5 |
| `climbcontest/routes/admin.py` | `page_dossards()` appelle `fiches.construire()` |
| `climbcontest/templates/admin.html` | La carte « Imprimer les dossards » → « Imprimer les fiches » |
| `tests/test_qr_et_dossards.py` | Les tests de planche suivent ; ceux du QR ne bougent pas |
| `docs/technical/classeur-google.md` | L'onglet `Fiches` passe de « ➖ papier » à « ✅ repris » dans le tableau du § 5 bis |

Aucun modèle, aucune migration, aucune route, aucun contrat JSON.

## `fiches.py`

Pas de Flask, comme `cycle.py`, `circuits.py` et `classement.py` : tout se teste
sans client HTTP.

```python
COULEURS = classement.COULEURS      # Jaune < Vert < Bleu < Mauve < Rouge < Noir
PLAN = ( ... )                      # le mur d'Annonay, cf. plus bas

def construire(comp, participants) -> list[dict]
def _blocs_par_circuit(comp) -> dict[str, list[Bloc]]
def _plan_pour(zones: set[str]) -> list[list[dict]]
```

### Le plan

Constante, parce que c'en est une : le même texte dans les trois classeurs de
2024, novembre 2025 et mars 2026. Sept cases par ligne — la colonne `V` du
classeur en vaut une, `W` et `X` en valent trois chacune :

```python
# Le mur de bloc d'Annonay, releve de l'onglet « Fiches » du classeur
# (V4:X11). Identique dans les trois classeurs archives : c'est la salle,
# pas une donnee de competition. Une zone absente d'ici -- U, V, W -- n'a
# jamais porte de bloc ; la fiche le DIT plutot que de la perdre.
#
# Une case vaut : None (vide), "X" (une zone), ou REPERE("Escalier") --
# un repere de la salle, pas une zone. Le classeur les melange aux lettres,
# ce qui est precisement ce qui rend son schema illisible.
def REPERE(nom): return ("repere", nom)

PLAN = (
    (None, None, None, None, "X",   "Y",  None),
    (None, "D",  None, None, "Z",   None, None),
    (None, "C",  "B",  "A",  REPERE("Escalier"), None, None),
    (None, None, None, None, None,  None, None),
    ("L",  None, None, None, None,  None, None),
    ("M",  "K",  "J",  "I",  "H",   "G",  "F"),
    ("N",  None, None, None, "E",   None, None),
    (None, REPERE("Haut"), None, None, None, None, None),
)
# Deduit de PLAN, jamais recopie a la main : deux listes qui divergeraient
# feraient disparaitre une zone du message « hors plan » sans rien casser.
ZONES_DU_PLAN = frozenset(c for ligne in PLAN for c in ligne if isinstance(c, str))
```

`_plan_pour(zones)` rend la même grille, chaque case enrichie de
`{"zone", "repere", "sienne"}` — `sienne` étant vrai quand le grimpeur a au
moins un bloc dans cette zone. Le gabarit ne fait qu'afficher.

### L'ordre des blocs

Celui de `Plan!AM` du classeur, qui trie sur
`Listes!B41:B46 + COUNTIF(...)` — difficulté d'abord, numéro ensuite :

```python
def _rang(bloc):
    """La difficulte d'abord, le numero ensuite. Un bloc sans couleur passe
    APRES tous les autres : il est douteux, il ne doit pas ouvrir la liste."""
    return (COULEURS.index(bloc.couleur) if bloc.couleur in COULEURS else len(COULEURS),
            bloc.tag)
```

`classement.COULEURS` est réutilisé, pas recopié : c'est la même échelle, et
deux listes qui divergeraient donneraient un tri différent du classement.

### Le budget de requêtes

Trois requêtes, quel que soit le nombre de participants — le même budget que
`circuits.inventaire()` et `classement_service.charger()` :

1. les blocs de la compétition,
2. les liens `bloc ↔ circuit` joints aux circuits,
3. les participants (déjà chargés par la route).

Le regroupement `circuit → blocs triés` se fait **une fois**, en mémoire, puis
chaque fiche y pointe. Cent fiches ne coûtent pas cent requêtes.

### Ce que `construire()` rend

```python
{
  "dossard": 42, "nom": "Lecomte Camille", "club": "Les Lézards Vagabonds",
  "categorie": "U11 F", "circuit": "U11",
  "qr": "<svg …>",                        # qr.svg(dossard, cote_mm=28)
  "blocs": [{"zone": "Z", "numero": "J6", "couleur": "Jaune"}, …],
  "groupes": [{"couleur": "Jaune", "blocs": [...]}, …],   # pour le liseré
  "plan": [[{…}, …], …],
  "hors_plan": ["U"],                     # zones du grimpeur absentes du plan
  "manque": None,                         # ou la phrase a afficher (cas limites)
}
```

`numero` est `tag` privé de son préfixe de zone — `ZJ6` → `J6`, ce qui est le
numéro écrit sur l'étiquette au mur. Le retrait se fait par
`tag.removeprefix(zone)` **et non** par une découpe à un caractère : rien ne
garantit qu'une zone tiendra toujours sur une lettre.

`manque` porte les quatre cas de dégradation de la spec (pas de catégorie,
circuit inconnu, circuit vide, aucun bloc). La fiche s'imprime **toujours** :
c'est le papier qui porte le QR.

## Le gabarit

Tout en millimètres, comme aujourd'hui : c'est la taille physique qui compte.

```css
@page { size: A4 portrait; margin: 6mm; }
.fiche {
  height: 142.5mm;          /* (297 - 12) / 2 : la moitie exacte de l'utile */
  break-inside: avoid; page-break-inside: avoid;
  display: grid; grid-template-rows: auto 1fr;
}
.blocs { display: grid; grid-template-columns: repeat(auto-fill, minmax(15mm, 1fr)); }
```

`auto-fill` + `minmax` porte le cas « circuit de plus de 50 blocs » sans une
ligne de JavaScript : les cases se resserrent, la fiche garde sa hauteur.

Le trait de coupe est une bordure en pointillé sur la fiche **paire** — jamais
une bordure complète : on coupe dessus, ce n'est pas un cadre à garder.

Aucune ressource externe, aucune police téléchargée : c'est le critère A11, et
c'est la règle depuis la spec 005.
