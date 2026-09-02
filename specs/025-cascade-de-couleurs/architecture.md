# Architecture — 025 cascade-de-couleurs

## 1. Le déplacement principal

La règle **cesse d'être un paramètre de la compétition** pour devenir un
paramètre **du grimpeur**, résolu par sa catégorie. C'est ce qu'exige la portée
par catégorie (F4), et c'est déjà ce que fait le classeur : `Inter!DJ19` se
calcule ligne par ligne, donc grimpeur par grimpeur.

Conséquence gratuite et importante : les **scratchs**, qui mélangent les
catégories, héritent naturellement de la règle de chacun. Aucun traitement
spécial à écrire — c'est la même boucle `for m in membres` qui résout la règle.

## 2. Le rangement

`Competition.options`, texte JSON déjà en place, gagne une clé `cascade` :

```json
"cascade": {
  "actif": true,
  "regles": [
    { "parmi": ["Vert","Bleu","Mauve","Rouge","Noir"], "seuil": 2, "cibles": ["Jaune"] },
    { "parmi": ["Bleu","Mauve","Rouge","Noir"],        "seuil": 2, "cibles": ["Vert"]  },
    { "parmi": ["Mauve","Rouge","Noir"],               "seuil": 2, "cibles": ["Bleu"]  },
    { "parmi": ["Rouge","Noir"],                       "seuil": 2, "cibles": ["Mauve"] }
  ],
  "categories_eteintes": []
}
```

**Une liste, pas une table par couleur.** Une table `{cible: {parmi, seuil}}`
serait plus compacte, mais elle ne sait pas porter **deux conditions
différentes** sur la même couleur — ce que la liste permet, et ce que l'écran
autorise (le contrôle le signale sans l'interdire).

**Pas de champ « mode ».** Les trois préréglages écrivent les phrases ; le
bouton actif et l'avertissement de F7 se **calculent** en comparant la liste à
la règle du classeur. Un état écrit en double finit toujours par mentir sur ce
que la liste dit vraiment.

**On range les catégories ÉTEINTES, jamais les allumées** — exactement le
principe de `groupes_masques` (spec 020), et pour la même raison. Une catégorie
créée en cours de journée, à l'inscription à chaud, est absente de toute liste
écrite le matin. Rangée en « allumées », elle sortirait **éteinte** : ses
grimpeuses seraient classées sous une autre règle que leurs camarades, sans que
rien ne le dise. Rangée en « éteintes », elle sort **allumée**, ce qu'exige F4.

La liste vide — le cas courant — signifie donc « la règle s'applique partout »,
et `actif: false` reste le vrai interrupteur général.

### Compatibilité avec l'existant, démontrée

`options.validation_couleur = N` reste lu **en repli** quand `cascade` est
absente, et se convertit exactement :

> pour chaque couleur X ayant au moins N couleurs plus dures :
> `Phrase(parmi = les couleurs plus dures que X, seuil = N, cibles = {X})`

Ce n'est pas une approximation. La règle actuelle valide tout ce qui est plus
facile que la **N-ième couleur pleine la plus dure**, ce qui équivaut à « X est
validé s'il existe au moins N couleurs pleines strictement plus dures que X ».
**9 000 comparaisons** entre `_valider_par_couleur()` tel quel et sa réécriture
en phrases, sur des tirages aléatoires et N ∈ {1, 2, 3} : **0 écart**.

C'est ce qui rend le critère A3 vérifiable par un test, pas par une relecture.

## 3. Le modèle de calcul

Dans `climbcontest/classement.py`, deux dataclasses gelées — le module reste
**pur**, sans Flask ni SQL :

```python
@dataclass(frozen=True)
class Phrase:
    parmi: frozenset[str]     # les couleurs qui comptent
    seuil: int                # combien il en faut
    cibles: frozenset[str]    # ce que ça valide

@dataclass(frozen=True)
class Cascade:
    phrases: tuple[Phrase, ...] = ()
    categories: frozenset[str] | None = None   # None = toutes

    def pour(self, categorie: str | None) -> "Cascade":
        """La cascade telle qu'elle s'applique à CE grimpeur. Vide si sa
        catégorie est éteinte."""
```

### Signatures modifiées

| Fonction | Avant | Après |
| --- | --- | --- |
| `_valider_par_couleur` | `(reussites, blocs, blocs_du_circuit, couleurs_requises: int)` | `(reussites, blocs, blocs_du_circuit, cascade: Cascade)` |
| `_classer` | `(…, couleurs_requises: int)` | `(…, cascade: Cascade)` — résolue **par membre** |
| `calculer_groupe`, `calculer_scratch`, `calculer_tout` | `couleurs_requises: int = 0` | `cascade: Cascade = Cascade()` |
| `classement_service.couleurs_requises(comp)` | rend un `int` | **remplacée** par `cascade(comp) -> Cascade` |

Le corps de `_valider_par_couleur` change entièrement : il ne cherche plus « les
N couleurs pleines les plus dures » mais évalue les phrases.

```python
pleines = {c for c in COULEURS
           if total_par_couleur.get(c, 0) > 0
           and reussis_par_couleur.get(c, 0) == total_par_couleur[c]}
valides = set()
for p in cascade.phrases:
    if len(p.parmi & pleines) >= p.seuil:
        valides |= p.cibles
```

Une couleur à **zéro bloc** n'entre jamais dans `pleines` — c'est déjà le
comportement actuel (`total > 0`), et c'est la décision D3. Une seule passe : ce
qui est dans `valides` n'alimente jamais `pleines` (D2).

⚠️ `pleines` se calcule sur les blocs **du circuit**, donc une même règle produit
naturellement des effets différents d'un circuit à l'autre — un circuit sans
Noir ne peut pas satisfaire une phrase qui n'exige que du Noir.

## 4. Le contrôle (F3)

Écrit **une fois**, en Python, dans un module pur `climbcontest/cascade.py`, et
appelé par la route ; le JavaScript de la console en fait sa propre copie pour
l'affichage immédiat, mais **le serveur reste l'autorité** — une console ne
valide rien, elle assiste.

```python
def implique(b: Phrase, a: Phrase) -> bool:
    """La condition de `b` entraîne-t-elle celle de `a` ?

    Exact : dans le pire des cas, satisfaire `b` laisse à `a`
    `seuil(b) - |parmi(b) \\ parmi(a)|` couleurs pleines.
    """
    hors = len(b.parmi - a.parmi)
    return (b.seuil - hors) >= a.seuil
```

| Contrôle | Règle | Effet |
| --- | --- | --- |
| Phrase incomplète | `parmi` ou `cibles` vide | **400**, refus d'enregistrer |
| Cascade qui remonte | une cible n'est pas plus facile que `min(parmi)` | **400**, refus |
| Phrase morte | `implique(b, a)` et `b.cibles ⊆ a.cibles` pour un `a ≠ b` | avertissement dans la réponse, enregistre |
| Deux phrases, même cible | intersection non vide, hors phrases mortes | information, enregistre |

Deux phrases équivalentes s'impliquent mutuellement : on ne signale que la
**seconde**, sinon chacune accuse l'autre et on ne sait pas laquelle retirer.

**Le test d'implication a été validé par force brute** : 3 890 paires tirées au
hasard, confrontées à l'énumération des 64 combinaisons de couleurs pleines,
0 désaccord.

## 5. L'accès aux blocs d'un grimpeur (F6, et contrat avec la spec 026)

Aujourd'hui l'extension par couleur se calcule **à l'intérieur** de `_classer`,
groupe par groupe, et ne se lit nulle part. La fiche du grimpeur à l'écran
(spec 026) en a besoin. D'où **un seul accesseur**, dans `classement_service` :

```python
def blocs_du_grimpeur(comp, participant) -> dict:
    """{ "grimpes": set[int], "credites": set[int] }"""
```

- Les **deux ensembles sont disjoints par construction** — et c'est une garantie
  de contrat, pas une observation : `credites` est l'étendu **moins** le brut,
  `grimpes` le brut **inter** le circuit. La spec 026 peint `grimpes | credites`
  et dépend de cette disjonction pour ne pas afficher deux fois le même bloc.
- La règle appliquée est celle **de la catégorie du grimpeur** : c'est le même
  `cascade.pour(categorie)` que le classement, donc l'écran ne peut pas montrer
  autre chose que ce qui est compté.

⚠️ **Ce que l'accesseur ne rend pas, et pourquoi.** Il a porté deux champs de
plus le 02/09 — `hors_circuit` (les réussites forcées hors du circuit, spec 019)
et `reussites` (l'heure et la source de chacune, inséparables parce qu'une
saisie manuelle porte l'heure de la saisie et non de la grimpe). Adrien a fait
retirer cet affichage de la fiche le jour même : **plus aucun consommateur**. Ils
sont retirés — un champ que personne ne lit finit par mentir, et le remettre
coûte vingt lignes.

**Le besoin, lui, reste entier** : une réussite hors circuit n'est visible
**nulle part** pour la personne concernée. La console est le bon endroit, parce
que c'est là qu'un organisateur peut **agir** ; sur un écran public, un parent ne
peut que s'inquiéter. Hors périmètre de cette spec, à loger dans une prochaine.

## 6. Les routes

| Méthode | Chemin | Rôle | Corps / réponse |
| --- | --- | --- | --- |
| `GET` | `/admin/competition/cascade` | `ADMIN` | la règle, les catégories de l'édition avec leur état, et — pour l'aperçu — le nombre de blocs par couleur et par circuit |
| `POST` | `/admin/competition/cascade` | `ADMIN` | `{actif, regles, categories}`. **400** si le contrôle bloque, sinon `{success, avertissements: [...]}` |

Même forme que `competition_affichage` (spec 020) : `_corps_objet()`,
`exige_role(ADMIN)`, `ErreurMetier` remontée en JSON.

⚠️ Écrire la cascade doit **vider le cache** de `classement_service` pour cette
compétition (`_cache.pop(comp.id, None)`), sans quoi le réglage ne se voit
qu'après cinq secondes — assez pour qu'on le croie sans effet et qu'on
recommence.

## 7. Les fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/classement.py` | `Phrase`, `Cascade`, `_valider_par_couleur` réécrite, quatre signatures |
| `climbcontest/cascade.py` | **nouveau** — lecture/écriture du JSON, conversion du repli, les quatre contrôles |
| `climbcontest/classement_service.py` | `couleurs_requises` → `cascade(comp)`, `blocs_du_grimpeur()`, purge du cache |
| `climbcontest/cycle.py` | rien — `ecrire_options()` fusionne déjà sans écraser |
| `climbcontest/routes/admin.py` | les deux routes |
| `climbcontest/templates/admin.html` | la carte dans la vue **Général**, entre « L'édition » et « Ce qu'affiche la page de résultats » |
| `tools/verify_ranking.py` | appel adapté à la nouvelle signature (cascade vide) |
| `tests/` | voir `plan.md` |
| `docs/technical/classeur-google.md` | §5 : la règle n'est plus « en réserve », elle est réglable |
| `docs/specs-index.md` | la ligne 025 |

## 8. Ce que ça ne touche pas

- **Le classeur Google.** Aucune écriture, aucun changement de miroir. Son
  interrupteur `Listes!D29:D38` reste vide.
- **L'application juge.** Elle envoie des réussites ; la cascade est un calcul
  d'affichage du classement, elle n'a rien à connaître.
- **Le cache de classement** dans son principe : cinq secondes, par processus.
  Seule la purge à l'écriture s'ajoute.
- **`Bloc.couleur`** et son ordre `COULEURS` : inchangés.
