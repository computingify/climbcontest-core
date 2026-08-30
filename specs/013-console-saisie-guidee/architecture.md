# Architecture — Spec 013

## 1. Où va quoi

| Couche | Fichier | Rôle dans cette spec |
| --- | --- | --- |
| Formatage | `climbcontest/formatage.py` | **nouveau** — fonctions pures, aucune dépendance |
| Métier | `climbcontest/contest.py` | `prochain_dossard`, `ajouter_participant_numerote`, formatage appliqué |
| API | `climbcontest/routes/admin.py` | `GET /admin/referentiels`, la route d'ajout n'exige plus de dossard |
| Interface | `climbcontest/templates/admin.html` | barre latérale, listes déroulantes, champ dossard retiré |
| Tests | `tests/test_formatage.py` | **nouveau** — la table de vérité du formatage |
| Tests | `tests/test_admin_participants.py` | attribution du dossard, référentiels, non-régression |

## 2. Le formatage — `formatage.py`

Un module **sans import applicatif** : ni base, ni Flask. C'est ce qui permet de
le tester par une table de cas, sans monter d'application.

```python
SEPARATEURS = " -'’"          # espace, trait d'union, apostrophes droite et typographique
SIGLE_MAXI = 5                # « CAF », « ASPTT » : oui. « MARTIN » : non.

def mots(texte: str | None) -> str | None:
    """Une majuscule au début de chaque mot. Les sigles survivent."""

def categorie(texte: str | None) -> str | None:
    """Tout en majuscules, espaces réduits. « u13  f » -> « U13 F »."""
```

**Pourquoi découper sur trois séparateurs et pas seulement l'espace.** Sans le
trait d'union, « jean-luc » donne « Jean-luc ». Sans l'apostrophe, « roc
n'potes » donne « Roc N'potes » — et le club s'appelle « Roc N'Potes » dans le
classeur. Les deux formes cohabiteraient alors dans la liste déroulante, ce que
cette spec cherche précisément à empêcher. Les séparateurs sont **conservés** à
leur place : on découpe, on capitalise, on recolle à l'identique.

**Pourquoi un plafond de longueur sur les sigles.** La règle « un mot déjà tout
en majuscules est laissé tel quel » protège « CAF », mais garderait aussi
« MARTIN » — or taper son nom en capitales est un réflexe courant sur un
formulaire. Le plafond tranche par la seule information disponible : un sigle
est court. À 5 caractères, « ASPTT » passe et « MARTIN » non.

> Ce plafond est le point de la **question ouverte Q3** de la spec. S'il est
> décidé que nom et prénom ne doivent jamais préserver de capitales, la
> signature devient `mots(texte, sigles=True|False)` et l'appelant choisit —
> une ligne de plus, pas une refonte.

**Ce que le formatage ne touche pas : l'import du classeur.** `sheets/importer.py`
construit ses `Participant` directement et **reste inchangé**. Le classeur fait
autorité sur ses propres lignes ; les reformater ici masquerait ses erreurs au
lieu de les signaler, et ferait diverger la base de la source qu'elle recopie.
Le formatage s'applique à ce qui est **saisi**, pas à ce qui est **importé**.

## 3. L'attribution du dossard — `contest.py`

### 3.1 Le numéro

```python
def prochain_dossard(comp: Competition) -> int:
    """Le plus petit numéro libre. Un trou d'abord, sinon la suite."""
```

Les dossards pris sont lus triés, et on avance jusqu'au premier trou :
`1, 2, 3, 7, 8` → `4`. Sans trou, `1..109` → `110`. Sur cent vingt participants,
c'est une lecture d'une colonne indexée et une boucle — le coût est nul et
l'algorithme se lit d'un coup d'œil, ce qui compte davantage ici.

### 3.2 La course entre deux organisateurs

Deux personnes qui inscrivent en même temps calculent le même « plus petit
numéro libre ». La contrainte `uq_dossard_competition` rejette le second — c'est
elle qui protège, pas le calcul.

```python
def ajouter_participant_numerote(nom, prenom=None, club=None, categorie=None,
                                 essais=5) -> Participant:
    """Ajoute avec un dossard attribué. Retente si la course est perdue."""
```

Le motif est **celui qui existe déjà** dans `enregistrer_reussite` : tenter,
attraper la collision, refaire. Ici on retente avec le numéro suivant, jusqu'à
cinq fois — au-delà, il ne s'agit plus d'une course mais d'un défaut, et il doit
remonter plutôt qu'être avalé.

Deux échecs sont attrapés, pas un : `IntegrityError` (course perdue au *commit*)
et `ErreurMetier(409)` (le contrôle d'occupation de `ajouter_participant` a vu
l'autre arriver en premier).

### 3.3 Ce qui ne change pas

`ajouter_participant(dossard=None)` **garde exactement son sens actuel** : un
participant sans dossard. C'est délibéré. Le modèle de la
[spec 002](../002-reliable-success-storage/) repose sur l'existence d'inscrits
sans numéro — l'absent dont on reprend le dossard. Supprimer cette possibilité
depuis la couche métier casserait ce concept, et trois tests existants qui le
vérifient :

| Test | Ce qu'il garantit |
| --- | --- |
| `test_sans_dossard_c_est_permis` | un ajout sans numéro reste possible |
| `test_les_sans_dossard_sont_a_la_fin` | le tri de la liste les place en fin |
| `test_present_est_pose_si_un_dossard_est_donne` | `present` suit le dossard |

**La politique « toute inscription reçoit un numéro » appartient à la route**,
pas au métier. La console n'offre plus le choix ; la fonction, elle, sait encore
faire les deux.

## 4. L'API

### 4.1 `GET /admin/referentiels` — nouveau

Rôle : `organisateur`. Les valeurs distinctes de la compétition en cours.

```json
{ "success": true,
  "categories": ["U11 F", "U11 H", "U13 F", "U13 H", "U15 F", "U15 H", "U17 H"],
  "clubs": ["Annonay Escalade", "La Grimpe", "Les Lezards Vagabonds",
            "Roc N'Potes", "Vertic'Ardeche"] }
```

Deux `SELECT DISTINCT` triés, les `NULL` écartés. Sans compétition active :
deux listes vides et `success: true` — **pas une erreur**. Le formulaire doit
rester utilisable, « Autre… » suffit à créer le premier participant.

Un seul appel pour les deux listes : la console les charge ensemble, à
l'ouverture. Deux routes auraient fait deux allers-retours pour un seul geste.

### 4.2 `POST /admin/participants` — modifiée

Le corps n'a plus besoin de `dossard`. **S'il en porte un quand même, il est
honoré** : la route reste compatible avec les appels existants et avec ses
tests. Sinon, `ajouter_participant_numerote` attribue.

La réponse est inchangée (`201` + le participant), et porte donc le dossard
attribué — c'est ce que la console affiche dans son message de confirmation.

## 5. L'interface — `admin.html`

### 5.1 La barre latérale

Reprise du motif de guestFlow (`client/src/App.jsx`), transposée sans
bibliothèque — la console n'a **aucune dépendance extérieure**, et ce n'est pas
cette spec qui va en introduire une :

| Largeur | Barre | Burger | Contenu |
| --- | --- | --- | --- |
| ≥ 900 px | visible en permanence, 240 px | masqué | décalé de 240 px |
| < 900 px | hors écran, glisse par-dessus | visible à gauche | pleine largeur |

Le basculement est fait par une **media query**, pas par du JavaScript : la
barre est au bon endroit dès le premier rendu, sans attendre le script. Le
JavaScript ne gère que l'ouverture en mode étroit — une classe sur `<body>`.

Fermeture en mode étroit : choix d'une section, clic sur le voile, ou `Échap`.
Le bouton porte `aria-expanded` et `aria-controls` ; la section courante porte
`aria-current="page"`.

### 5.2 Les listes déroulantes

Un `<select>` alimenté au chargement, dont la dernière entrée est
`＋ Autre…`. La choisir révèle un `<input>` texte juste en dessous.

> **Pourquoi pas `<datalist>`.** Un `<input list=…>` fait les deux en un seul
> champ, et c'est tentant. Mais son rendu est irrégulier d'un navigateur mobile
> à l'autre, et surtout il **n'empêche rien** : on peut y taper n'importe quoi
> sans s'en rendre compte, ce qui est exactement la façon dont `U13 M` est né.
> Le `<select>` rend le choix explicite et l'écart délibéré.

Après un ajout réussi, les listes sont rechargées : une catégorie inédite
devient aussitôt disponible pour l'inscription suivante.

### 5.3 Le champ dossard disparaît

Retiré du formulaire d'ajout. Le message de confirmation annonce le numéro
attribué — c'est lui qu'il faut aller imprimer :

> « Léa Dupont ajoutée avec le **dossard 110**. Les téléphones la verront dans
> quelques secondes. »

Le bouton « Changer le dossard » de la liste et sa règle métier ne bougent pas.

### 5.4 L'onglet Dossards

`#dCategorie` passe de `<input>` à `<select>`, alimenté par la même source, avec
une première entrée vide valant « toutes les catégories ». Pas d'« Autre… » ici :
on imprime pour une catégorie **qui existe**.

## 6. Ce qui pourrait mal tourner

| Risque | Parade |
| --- | --- |
| Deux inscriptions simultanées reçoivent le même dossard | Contrainte d'unicité en base + retente (§3.2) — la parade est la contrainte, pas le calcul |
| Le classeur importe plus tard un dossard attribué à la main | **Non couvert.** Question ouverte Q2 de la spec : faire refuser l'écrasement d'un participant `source = manuel` |
| Le formatage change une valeur de catégorie et casse un classement | Impossible : les catégories en base sont déjà en majuscules, `categorie()` les laisse identiques. Le classement groupe par égalité de chaîne, sur des valeurs inchangées |
| Une nouvelle catégorie crée un classement d'une seule personne | C'est le comportement attendu du moteur — et c'est justement ce que la liste déroulante rend délibéré au lieu d'accidentel |
| La barre latérale masque le contenu sur un petit écran | Elle glisse par-dessus avec un voile, et se referme au premier choix |
| Le JavaScript de la console n'est pas testé | Vrai aujourd'hui : il est inline dans le gabarit. Les critères A12 et A13 se vérifient **dans un vrai navigateur**, à la main. Sortir ce script en module testable est une dette identifiée, hors périmètre de cette spec |
