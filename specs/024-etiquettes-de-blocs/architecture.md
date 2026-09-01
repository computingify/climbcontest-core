# Architecture — 024 étiquettes-de-blocs

## Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/fiches.py` | `etiquettes()` s'ajoute à `construire()` — même module, même sujet : ce qu'on imprime |
| `climbcontest/templates/etiquettes.html` | **Nouveau** |
| `climbcontest/routes/admin.py` | `GET /admin/etiquettes` |
| `climbcontest/templates/admin.html` | Une carte « Imprimer les étiquettes » dans la vue **Circuits** |
| `tests/test_etiquettes.py` | **Nouveau** |

Aucun modèle, aucune migration, aucun contrat JSON.

## `fiches.etiquettes()`

```python
def etiquettes(comp, zone=None, tag=None) -> list[dict]:
    """Les blocs a coller au mur, dans l'ordre du Plan (= Bloc.numero).

    Deux requetes, quel que soit le nombre de blocs : les blocs, puis les
    liens bloc<->circuit joints aux circuits. Le meme budget que
    `circuits.inventaire()`.
    """
```

Rend, par bloc :

```python
{"tag": "ZJ6", "zone": "Z", "numero": "J6", "couleur_prises": "Blanc",
 "circuits": ["U11", "U13"], "qr": "<svg …>", "coupure": False}
```

- `numero` = `tag.removeprefix(zone)` — la même règle que la fiche du grimpeur
  (spec 023), écrite une fois, dans le même module.
- `coupure` vaut `True` sur le **premier** bloc d'une zone, sauf le tout
  premier : c'est ce que le gabarit traduit en saut de page. Le calcul est fait
  ici, pas en Jinja — une boucle de gabarit qui compare avec l'élément
  précédent est exactement le genre de chose qu'on relit trois fois.

## La route

```python
@bp.get("/etiquettes")
@exige_role(ORGANISATEUR)
def page_etiquettes():
    """La planche a coller au mur. `?zone=Z`, `?bloc=ZJ6`."""
```

Copie conforme de `page_dossards()` : compétition active, filtres, tri, journal
(« impression de N etiquette(s) par <identifiant> »), `render_template`.

## Le gabarit

```css
@page { size: A4 portrait; margin: 5mm; }
.planche   { display: grid; grid-template-columns: 1fr 1fr; }
.etiquette { height: 92.3mm;            /* (297 - 10) / 3 */
             break-inside: avoid; page-break-inside: avoid; }
.etiquette.coupure { break-before: page; page-break-before: always; }
```

⚠️ `break-before: page` sur un enfant de grille est mal supporté. La grille est
donc **refermée et rouverte** à chaque zone : le gabarit boucle sur des
**groupes de zone**, un `<div class="planche">` par zone, et c'est le `div` qui
porte `break-before`. Une seule grille par zone, aucun élément de grille
n'ayant à sauter de page.

C'est aussi pour ça que `etiquettes()` peut rendre une liste plate avec un
drapeau : le gabarit regroupe avec `groupby`, Jinja sait le faire, et la logique
de découpe reste en Python.
