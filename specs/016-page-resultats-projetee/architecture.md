# Architecture — spec 016

## 1. Ce qui change, en une image

```
AVANT                                  APRÈS
/  et  /resultats  → même vue          /  → la vue (unique)
                                       /resultats → 404
liste détruite et reconstruite         lignes PERSISTANTES, identifiées par
à chaque rafraîchissement              participant, déplacées (FLIP)
fond #0E1116                           fond clair ; ?sombre pour l'inverse
rotation muette de 20 s                rotation proportionnelle, barre de
                                       progression, « ensuite : … »
6 grimpeurs visibles sur 24            la catégorie entière, en colonnes
```

Une seule page, deux mises en page (`body.mur`), comme avant. C'est ce qui
empêche les deux modes de diverger.

## 2. Le serveur

| Fichier | Changement |
| --- | --- |
| `routes/pages.py` | `/resultats` supprimée ; la racine reste seule |
| `routes/public.py` | `reussites` ajouté à la charge utile — le compteur du jour |
| `static/logo-club.png` | **nouveau** — 240 px, 54 ko, servi par nous |

`reussites` est un `COUNT` sur les réussites de la compétition active. Il coûte
une requête indexée, et la réponse est de toute façon mise en cache 5 s par
Caddy : au plus 12 calculs par minute quel que soit le nombre de spectateurs.

**Le logo est servi depuis `/static`, pas en base64.** Inline, il ajouterait
~70 ko à *chaque* chargement de page ; en fichier, il est mis en cache par le
navigateur et ne coûte qu'une fois. Ce n'est pas une ressource externe — même
origine, donc la règle « aucune requête sortante » tient.

## 3. La page

### 3.1 Les lignes ne sont plus détruites

C'est le changement structurant. `etat.noeuds` associe **un participant à un
élément du DOM**, réutilisé d'un rendu à l'autre ; `peindre()` réordonne par
`insertBefore`, ce qui *déplace* les nœuds au lieu de les recréer.

```
positions()   →  on note où était chaque ligne
peindre()     →  on réordonne (le navigateur saute à la nouvelle position)
glisser()     →  on rejoue le trajet à l'envers, en 650 ms (FLIP)
```

Sans nœuds persistants, aucune animation n'est possible : c'est pour ça que
l'ancienne page n'en avait pas.

### 3.2 Ce qui se voit quand un rang change

| Signal | Détail |
| --- | --- |
| Glissement | 650 ms, `cubic-bezier(.22,.75,.2,1)` |
| Flèche | `▲n` / `▼n`, affichée jusqu'au rafraîchissement suivant |
| Pulsation | seulement pour qui **monte**, 1,6 s, couleur de la catégorie |

Les deltas sont calculés par groupe (`etat.rangs[groupe]`), sinon un changement
de catégorie se lirait comme un mouvement général.

### 3.3 Tout tient à l'écran, sinon ça défile

```
capacité = colonnes × hauteur_disponible / hauteur_de_ligne
--h  =  (hauteur_disponible − gouttières) / lignes,  borné à [44, 124] px
```

Deux ou trois colonnes selon l'effectif. Quand même la hauteur minimale ne
suffit pas, le bloc **défile doucement** — aller-retour à ~110 px/s avec une
pause de 3 s à chaque extrémité, en boucle (`Element.animate`). Choix d'Adrien
du 31/08 : « le reste du plateau qui défile doucement », plutôt qu'une
pagination qui fait clignoter l'écran.

⚠️ Le défilement ne se déclenche **que** s'il y a débordement. Un plateau qui
tient est immobile : du mouvement gratuit sur un écran qu'on regarde toute la
journée fatigue plus qu'il n'impressionne.

### 3.4 La rotation

```
durée = 8 s + 0,55 s × nombre de grimpeurs,  borné à [12 s, 35 s]
```

Réglable par l'adresse (`?mur&rotation=25`). Elle parcourt les **catégories** et
les **circuits** ; le classement club en est exclu (décision du 31/08) mais
reste accessible au doigt sur téléphone. La barre de progression est une
transition CSS relancée à chaque écran — aucun minuteur d'animation à tenir.

### 3.5 Les couleurs

Le fond clair par défaut, `body.sombre` pour l'inverse. Toutes les couleurs sont
des variables CSS ; le mode sombre n'en redéfinit **que** les valeurs, jamais
une règle de mise en page. Une seule mise en page, deux palettes.

La couleur de circuit (`--groupe`) est posée sur `documentElement` à chaque
rendu : le titre, la pastille, la barre de progression et la pulsation la
suivent sans une ligne de plus.

## 4. Ce que le HTML ne contient toujours pas

Aucune donnée. La page va chercher le classement elle-même, ce qui lui permet de
**garder le dernier classement connu** quand le serveur tombe — une page de
résultats qui se vide sur une erreur réseau fait croire que la compétition s'est
arrêtée.

Et **aucun `innerHTML` autre que pour vider** : les squelettes de lignes sont
construits élément par élément (`div()`), les valeurs posées par `textContent`.
Le test qui vérifie cette règle a fait tomber une première version où les
squelettes venaient d'un littéral HTML — sans donnée, donc sans risque, mais une
règle qu'on ne peut pas vérifier mécaniquement finit contournée.

## 5. Hors de l'application

| Où | Quoi |
| --- | --- |
| `edge` (LXC 101) | `@public path / /resultats /api/public/*` → `/resultats` retiré |
| `intra` (LXC 109) | bloc `@climbcontest_resultats` retiré du Caddyfile |
| `intra`, portail | tuile « ClimbContest — résultats » retirée ; la tuile ClimbContest dit maintenant qu'elle mène au classement |

Sauvegardes laissées sur place : `Caddyfile.bak-avant-suppression-resultats-20260831`
sur les deux hôtes, `index.html.bak-avant-suppression-resultats-20260831` sur
`intra`.

## 6. Fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/templates/resultats.html` | réécrit |
| `climbcontest/routes/pages.py` | route supprimée |
| `climbcontest/routes/public.py` | compteur du jour |
| `climbcontest/static/logo-club.png` | **nouveau** |
| `tests/test_page_resultats.py` | 404, contrat, mécanismes |
| `docs/technical/…`, `CHANGELOG.md`, `docs/runbook-competition.md` | tenue à jour |
