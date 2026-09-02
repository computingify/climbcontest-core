# Plan — 025 cascade-de-couleurs

## Étapes

### Lot A — le moteur

1. [x] **`Phrase` et `Cascade`** dans `classement.py` : deux dataclasses gelées,
   `Cascade.pour(categorie)` qui rend une cascade vide si la catégorie est
   éteinte.
2. [x] **`_valider_par_couleur` réécrite** : `pleines` (inchangé, `total > 0`
   garde D3), puis évaluation des phrases en **une passe** (D2). L'ancien calcul
   « les N couleurs pleines les plus dures » disparaît.
3. [x] **Les quatre signatures** : `_classer`, `calculer_groupe`,
   `calculer_scratch`, `calculer_tout`. Dans `_classer`, la cascade se résout
   **par membre** — c'est ce qui fait que les scratchs héritent de la règle de
   chacun sans une ligne de plus.
4. [x] **`climbcontest/cascade.py`** (nouveau) : lecture de `options.cascade`,
   **repli** sur `validation_couleur` avec la conversion exacte, écriture, et
   les quatre contrôles dont `implique()`.
5. [x] **`classement_service`** : `couleurs_requises()` remplacée par
   `cascade(comp)` ; `blocs_du_grimpeur()` ; purge du cache à l'écriture.
6. [x] **`tools/verify_ranking.py`** : appel adapté (cascade vide).

### Lot B — la console

7. [x] **Les deux routes** `GET`/`POST /admin/competition/cascade`, rôle
   `ADMIN`, sur le modèle de `competition_affichage`.
8. [x] **La carte** dans la vue **Général**, entre « L'édition » et « Ce
   qu'affiche la page de résultats » : préréglages, phrases, contrôle, aperçu,
   interrupteurs de catégorie, avertissement, bouton.
9. [x] **Le contrôle côté navigateur** — copie de la logique serveur pour
   l'affichage immédiat. Le serveur reste l'autorité : la console assiste, elle
   ne valide pas.
10. [x] **L'aperçu** : circuit, couleurs pleines cochables, jauge
    grimpé / crédité / à faire, et le compte de blocs par couleur (D3).

### Lot C — la traçabilité

11. [x] **« N grimpés · N crédités »** dans la console, partout où les blocs
    d'un grimpeur sont montrés, avec les hachures à 45° (D5).
12. [x] **L'astérisque** sur le compteur de blocs de la page de résultats,
    uniquement quand la cascade a crédité quelque chose.

### Fin

13. [x] **Tests** : le tableau ci-dessous.
14. [x] **Vérification au navigateur** (02/09, 1280 px, thèmes clair **et**
    sombre) : les préréglages écrivent et effacent les phrases, le contrôle
    signale la règle morte en direct et marque la phrase, l'avertissement du
    classeur apparaît et disparaît, l'aperçu donne 35/35 sur U11 avec Mauve et
    Rouge pleins (8 grimpés, 27 crédités), et la page de résultats affiche
    « 24* » avec l'infobulle « 9 grimpés · 15 crédités ».
    ⚠️ Reste à voir sur un vrai téléphone.
15. [x] **Docs** : `classeur-google.md` §5 (la règle n'est plus « en réserve »),
    `specs-index.md`, `CHANGELOG.md`.

## Plan de test

### Le moteur — `tests/test_classement.py`

| Scénario | Attendu |
| --- | --- |
| Cascade vide | rien n'est crédité ; identique à l'existant |
| Une phrase « toutes les Rouge → Jaune », Rouge pleine | les Jaune du circuit sont crédités, rien d'autre |
| La même, Rouge **incomplète** | rien n'est crédité |
| « au moins 2 parmi {Vert…Noir} → Jaune », **une seule** pleine | rien (c'est K2) |
| Deux phrases sur la même cible, une seule tenue | la cible est créditée — l'union, pas l'intersection |
| Enchaînement : « Noir → Rouge » puis « Rouge → Jaune », seul Noir plein | Rouge crédité, **Jaune non** (D2, une passe) |
| Couleur à zéro bloc dans le circuit | jamais pleine ; une phrase qui n'exige qu'elle ne tient jamais (D3) |
| Bloc sans couleur | ignoré de la cascade, compté s'il est grimpé |
| Blocs crédités et dénominateur | la valeur des blocs baisse pour **tout le monde** (D4) |
| Catégorie éteinte | ses membres ne créditent rien ; les autres catégories, si |
| **Scratch** mélangeant une catégorie allumée et une éteinte | chaque membre suit **sa** règle dans le même classement |

### L'équivalence et la non-régression — `tests/test_classement.py`

| Scénario | Attendu |
| --- | --- |
| **A1** — `verify_ranking.py` sur `fixtures/contest-nov2025.json`, cascade éteinte | **196 conformes, 0 écart** |
| **A2** — préréglage « comme le classeur », circuit à six couleurs | K1 Rouge+Noir → 36 · K2 Noir seul → 1 · K3 Noir+Bleu → 27 · K4 Mauve+Rouge+Noir → 36 |
| **A3** — `options.validation_couleur = N` sans clé `cascade`, N ∈ {1,2,3} | classement **identique** à l'ancien moteur, sur la fixture réelle |
| Conversion du repli | les phrases produites égalent, couleur par couleur, « au moins N parmi les plus dures » |

### Le contrôle — `tests/test_cascade.py` (nouveau)

| Scénario | Attendu |
| --- | --- |
| Phrase sans déclencheur, ou sans cible | **400**, message nommant la phrase |
| « toutes les Jaune → valider les Rouge » | **400**, « la cascade descend, elle ne remonte pas » |
| Préréglage classeur + « toutes les Rouge et Noir → Jaune » | enregistré, **avertissement** « règle 5 sans effet » |
| Deux phrases équivalentes | **une seule** signalée, la seconde |
| « Rouge → Jaune » et « Noir → Jaune » | information « elles s'additionnent », pas d'avertissement de mort |
| Préréglage classeur seul | **aucun** signalement |
| `implique()` | vérification par force brute sur les 64 combinaisons, sur un échantillon de paires |

### Les routes — `tests/test_admin_cascade.py` (nouveau)

| Scénario | Attendu |
| --- | --- |
| `GET` sans session | 401 |
| `GET` en `ORGANISATEUR` | 403 — la carte est `ADMIN` (A9) |
| `POST` d'une règle valide | 200, `options.cascade` écrite, **les autres options intactes** |
| `POST` puis `GET` classement | le nouveau classement, **sans attendre les 5 s** du cache |
| `POST` d'une règle qui remonte | 400, `options` **inchangées** |
| `POST` avec une catégorie inconnue | acceptée et rangée — elle peut réapparaître à l'import |
| Corps illisible | 400, message clair |

### L'accesseur — `tests/test_classement_api.py`

| Scénario | Attendu |
| --- | --- |
| `blocs_du_grimpeur` sans cascade | `credites` vide, `grimpes` = ses réussites du circuit |
| Avec cascade | `grimpes` et `credites` **disjoints**, union = ce que compte le classement |
| Réussite hors circuit | dans **aucun** des deux — elle ne compte pas au classement |
| Catégorie éteinte | ne crédite rien |

### La console — `tests/test_pages.py`

| Scénario | Attendu |
| --- | --- |
| La carte est servie | `id="presetsB"`, `id="editB"`, `id="controle"` présents |
| Aucune dépendance extérieure | aucun `src=`/`href=` vers un domaine tiers — non-régression 005/016/021 |

### Ce qu'un test Python ne peut pas vérifier — à faire au navigateur

| Point | Comment |
| --- | --- |
| Le contrôle s'affiche en direct | ajouter la phrase morte, la voir signalée sans recharger |
| Les préréglages | « Comme le classeur » écrit quatre phrases ; « Aucune » les efface |
| L'avertissement de D7 | apparaît en modifiant une phrase, disparaît en revenant au préréglage |
| L'aperçu | cocher Rouge + Noir sur le circuit à six couleurs donne 36 / 36 |
| Les hachures | lisibles en clair **et** en sombre |
| Les interrupteurs | les quatre raccourcis, et le rendu sur téléphone |
