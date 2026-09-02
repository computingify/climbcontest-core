# Architecture — spec 026

## 1. Ce qu'on n'écrit pas

La moitié du travail existait déjà, et le premier réflexe — la recopier — était
le mauvais.

| Ce dont la fiche a besoin | Qui le sait déjà |
| --- | --- |
| Les blocs d'un circuit, triés comme le classeur | `fiches._blocs_par_circuit()` + `_rang()` |
| Le numéro écrit sur le mur (« ZJ6 » → « J6 ») | `fiches.numero()` |
| Le plan, son cadrage, la place et la taille des lettres | `fiches.plan_pour()` (spec 028) |
| Les réussites, filtrées par circuit | `classement_service.charger()` + `classement._classer()` |
| L'extension par couleur | `classement._valider_par_couleur()` |

Le module `suivi.py` **assemble** et ne calcule rien. C'est ce qui garantit que
la fiche et le classement ne pourront pas dire deux choses différentes : il n'y
a qu'un chemin.

## 2. Le serveur

```
climbcontest/
  classement_service.py   + blocs_du_grimpeur(comp, participant)
  suivi.py                (neuf) plan_public(), fiche(comp, participant)
  routes/public.py        + GET /api/public/grimpeur/<id>
  routes/pages.py         + le plan embarqué dans la page
```

### `blocs_du_grimpeur` — le seul accesseur, et il vient de la spec 025

Rend **trois ensembles disjoints par construction** :

```
grimpes      = brutes & blocs_du_circuit
credites     = valider_par_couleur(grimpes) - grimpes
hors_circuit = brutes - blocs_du_circuit
```

La disjonction n'est pas une observation, c'est une **garantie de contrat** :
la page peint `grimpes ∪ credites`, et un identifiant présent dans deux
ensembles s'y afficherait deux fois, dans deux états contraires. Elle est
vérifiée sur tous les participants, cascade allumée
(`TestLesTroisEnsembles.test_les_trois_ensembles_sont_disjoints`).

⚠️ **Cette fonction ne doit pas être recopiée**, et cette spec a failli le
faire. Les deux branches en ont écrit une, au même fichier, à deux endroits
différents : **git les fusionne sans conflit**, le module la définit deux fois,
et c'est l'ordre dans le fichier qui choisit laquelle survit — donc laquelle des
deux résolutions de la cascade s'applique à la fiche. La version retenue est
celle de la spec 025 : elle résout la cascade **par catégorie**, lit les
réussites via `charger()` comme le classement, et garde `hors_circuit`.

`TestUnSeulAccesseur` compte les définitions dans le fichier et échoue s'il y en
a deux. C'est le seul garde possible contre une fusion qui ne conflicte pas.

### Pourquoi une route à part

`/api/public/classement` est relue toutes les 15 s par ~60 téléphones. Y mettre
les blocs de chaque grimpeur ferait payer à tout le monde ce qu'une personne
consulte : ~200 × 12 identifiants plus un catalogue, pour une fiche que
personne n'ouvre la plupart du temps. Une requête au clic, mise en cache 5 s
par Caddy comme le reste.

La route **404 si le grimpeur n'est pas de la compétition active** : sans cette
garde, l'identifiant lirait les éditions passées, qui vivent dans la même base.

### Le plan part avec la page, pas par la route

`plan_public()` appelle `fiches.plan_pour(set())` — le plan **nu**, sans
grimpeur — et l'embarque dans un `<script type="application/json">`.

Le plan est le **même pour tout le monde** : le servir par grimpeur
transformerait une donnée commune en charge par requête, et multiplierait les
entrées de cache pour un dessin rigoureusement identique. C'est la page qui
allume les zones, à partir des blocs qu'elle a déjà. `sienne` est retiré du
contrat : le laisser à `False` inviterait quelqu'un à s'en servir, et il serait
faux.

⚠️ **Il n'est plus figé.** La spec 029 le rend enregistrable depuis la console,
et `plan_pour()` lit le plan actif. Conséquence assumée : une page **déjà
ouverte** garde le plan qu'elle a reçu jusqu'à son prochain chargement. On ne
redessine pas la salle pendant une compétition, et la page de résultats se
recharge toute seule chez les spectateurs.

Le catalogue (`/api/v2/catalog`) porte désormais le plan, versionné par
`catalogue_version`. C'est la bonne porte le jour où la fraîcheur **sans
rechargement** comptera : la page pourrait revalider comme le fait
l'application juge. Ce n'est pas fait ici — ça ajouterait un chemin de
rafraîchissement et ses tests pour un besoin qui ne s'est pas présenté.

## 3. La page

```
climbcontest/static/resultats/
  suivi.js   (neuf) états de zone, comptes, lecture/écriture du dièse
  plan.js    (neuf) garde-fou de format, description du dessin, décoration
  podium.js  (existant, spec 027)
templates/resultats.html   + styles `sf-`, balisage, branchement
```

Même découpe que `podium.js`, et pour la même raison : **la logique est
extraite pour être testable sans navigateur**. Le gabarit ne garde que du
branchement au DOM.

### Le contrat avec le plan, et sa version

```
suivi.FORMAT_PLAN = "polygones/1"        (serveur : ce que j'envoie)
plan.FORMATS_RENDUS = ["polygones/1"]    (page : ce que je sais dessiner)
```

- On **incrémente** le numéro dès que la forme de `plan_public()` change — un
  champ retiré, renommé, une géométrie exprimée autrement. **Pas** quand les
  coordonnées changent : redessiner la salle ne casse rien.
- `FORMATS_RENDUS` est un **tableau** : le jour du changement, la page peut
  accepter les deux le temps d'un déploiement, où la page servie et l'API ne
  sont jamais mises à jour à la même seconde.
- Deux tests empêchent le contrat de pourrir :
  `test_la_forme_du_plan_est_celle_de_son_numero` (la liste des clés est
  épinglée) et `test_la_page_sait_dessiner_ce_que_le_serveur_envoie` (le test
  Python lit `plan.js` et confronte les deux listes). Sans le second, une
  divergence ferait disparaître le mur en silence.

### `decrire` / `monter` / `decorer`

`decrire(plan)` rend un arbre d'objets, `monter()` le traduit en SVG en dix
lignes sans aucune décision, `decorer()` pose les classes d'état. Tout ce qui
décide est donc testable en Node, y compris le comportement sur un plan abîmé.

`data-zone` est posé sur le **groupe** et non sur le polygone : l'état efface la
zone entière — forme, trame et lettre — et une opacité posée sur le seul
polygone laisserait sa lettre en pleine lumière au-dessus d'un mur éteint.

Les **cadres d'état sont une couche à part**, peinte après tous les murs. En
SVG l'ordre de peinture est l'ordre du document et il n'y a pas de `z-index` :
un cadre dessiné dans le groupe de sa zone se fait rogner sur les arêtes
qu'elle partage avec sa voisine — et les murs d'Annonay se touchent bord à
bord.

### L'historique

Un seul chemin : `versDiese()` écrit, `hashchange` appelle `appliquer()`,
`appliquer()` peint. `quitter()` appelle `history.back()` et rien d'autre.

`replaceState` sert dans deux cas, et seulement deux : changer de zone (un
retour doit ramener à la fiche, pas défaire les zones une par une) et nettoyer
l'adresse après un grimpeur inconnu (le retour ne doit pas ramener à un état
mort). `replaceState` ne déclenche pas `hashchange` : `versDiese` appelle donc
`appliquer()` lui-même dans ce cas.

⚠️ **Aucun état de navigation n'est gardé à côté de l'adresse.** « Suis-je au
mur » l'a été, et créait une course — voir spec § 6.3.

## 4. Les tests

| Fichier | Ce qu'il couvre |
| --- | --- |
| `tests/test_suivi.py` | les trois ensembles et leur disjonction, la fiche, ce qui manque, le plan servi, la route, l'anti-pourrissement du contrat |
| `tests/js/suivi.test.mjs` | états de zone, comptes, dièse — y compris les adresses abîmées |
| `tests/js/plan.test.mjs` | le garde-fou de format, les plans abîmés, la description, la décoration |
| `tests/test_navigateur_fiche.py` | le parcours entier dans un vrai navigateur |

Le dernier **se saute proprement s'il n'y a pas de navigateur**, parce qu'un
test qui échoue faute d'outil apprend à ignorer les échecs. Mais il ne se saute
pas sur la CI : `ubuntu-latest` fournit `/usr/bin/chromium`, et le parcours y est
donc rejoué à chaque poussée. `CLIMBCONTEST_CHROME` force un binaire.

⚠️ Le chemin des binaires Playwright se cherche par `glob`, jamais par numéro de
build. Figé sur `chromium_headless_shell-1234`, il aurait cessé de correspondre
à la première mise à jour et le test se serait sauté **en silence** — plus rien
n'aurait protégé le branchement, et rien ne l'aurait dit.

Il vérifie une chose qu'aucun autre ne peut : que **le clic atteint vraiment la
case**. `.click()` appelle le gestionnaire sans faire de test de pointage —
c'est exactement ce qu'une règle `pointer-events` mal placée casse, sans rien
casser d'autre.

## 5. Ce qui reste ouvert

- La fiche en **rejeu d'archive** (route publique côté compétition active).
- Le **mur seul**, sans fiche derrière.
- La **couleur des prises** dans le détail d'un bloc.
- Le **hors-circuit dans la console**, sorti du périmètre de cette spec et de
  la 025 : il n'appartient à personne aujourd'hui.
