# Spec 024 — Les étiquettes de blocs à coller au mur

> **Statut : rédigée, en attente de la porte 2.**
> Demande d'Adrien du 01/09/2026, à la validation des specs 021-023 : « il me
> faudra aussi les étiquettes de blocs ». C'est le papier que la spec 023 avait
> explicitement laissé de côté — la zone gauche de l'onglet `Fiches`.

## 1. Ce qui manque

Le juge scanne **deux** QR : celui du grimpeur, puis celui du bloc réussi. Le
second est collé au mur, à côté du départ du bloc. Rien, dans ClimbContest, ne
sait l'imprimer : la spec 005 n'a repris que le QR des dossards, et l'étiquette
de bloc est restée dans le classeur.

Conséquence concrète : préparer une compétition demande encore d'ouvrir le
classeur et d'imprimer son onglet `Fiches`, colonnes `A` à `M`. Et ces QR-là
sont produits par `api.qrserver.com` — un appel réseau vers un tiers, qui ne
marche pas si la connexion tombe la veille au soir, quand on colle les
étiquettes.

## 2. Ce que porte l'étiquette du classeur

Relevé cellule par cellule (`Fiches!A3:M13`, bande de zone `Z`). Le classeur en
propose **deux variantes** côte à côte :

| | Variante A (`A:F`) | Variante B (`H:M`) |
| --- | --- | --- |
| Zone | `A4` seule, en tête de bande | `H4`, en tête de bande |
| Numéro du bloc | `B3` **et** `B7` — au-dessus **et** au-dessous du QR | `I3`, une fois |
| Zone, répétée sur l'étiquette | `B4` « Zone Z » | — |
| Couleur des prises | `B5` « Couleur prises : Blanc » | `I4`, idem |
| QR | `B9` → `Plan!D` & `Plan!T` = **`ZJ6`** | idem |
| **Les circuits du bloc** | — | `I9:I13` → « U11 Fiche Bleu » |

La variante B porte l'information que A n'a pas : **pour qui ce bloc compte**.
Elle la formule en couleur de fiche — `Listes!D17:E19` donne U11 → Bleu,
U13 → Vert, U15 → Rose, et `Listes!C29:C34` compte les feuilles à imprimer par
catégorie (« 5 Bleu Clair », « 6 Bleu Foncé »…). Les fiches des grimpeurs sont
imprimées **sur papier de couleur**, et l'étiquette dit quelles couleurs de
papier sont concernées.

C'est la variante B qu'on reprend, avec **les noms de circuits** plutôt que les
couleurs de papier — voir F3.

## 3. Ce qu'on fait

### F1 — Une planche d'étiquettes, six par A4

Nouvelle page `GET /admin/etiquettes`, réservée à un organisateur, sur le modèle
exact de `/admin/dossards` :

| Paramètre | Effet |
| --- | --- |
| *(aucun)* | Tous les blocs de la compétition active |
| `?zone=Z` | Les blocs d'une zone — celle qu'on va coller maintenant |
| `?bloc=ZJ6` | Une seule étiquette : celle qu'on a décollée ou perdue |

Six étiquettes par A4 (2 colonnes × 3 lignes, 99 × 105 mm chacune) :

```
┌───────────────────────────┐
│        ZONE  Z            │
│                           │
│         J 6               │   ← le numéro, en très gros
│                           │
│      ┌───────────┐        │
│      │           │        │
│      │    QR     │  45mm  │   ← contenu : « ZJ6 »
│      │           │        │
│      └───────────┘        │
│  Prises : Blanc           │
│  Compte pour : U11 · U13  │
└───────────────────────────┘
```

Le numéro est le plus gros élément : c'est ce qu'on lit à deux mètres pour
savoir si on est devant le bon bloc. Le QR, lui, se scanne à trente centimètres,
45 mm suffisent largement — c'est deux fois la taille d'un QR de dossard.

### F2 — Une zone par page

Les étiquettes sortent dans l'ordre de `Bloc.numero`, qui est **l'ordre du
`Plan`** — donc zone par zone, bloc par bloc, exactement comme le classeur les
range. Un **saut de page à chaque changement de zone** : on prend la page de la
zone `Z`, on va coller les cinq étiquettes de la zone `Z`, on ne trie rien à la
main.

Les cinq blocs par zone du classeur tiennent donc sur une page, avec une place
en rab. Une zone de plus de six blocs continue sur la page suivante, sans rien
casser.

Une zone **sans bloc** ne produit aucune page — c'est ce que fait le classeur
avec son filtre `Plan!AY` (« la zone a-t-elle au moins un bloc de circuit ? »),
et sept des vingt zones étaient dans ce cas en mars 2026.

### F3 — « Compte pour », en noms de circuits

L'étiquette dit **U11 · U13**, pas « Fiche Bleu ». Deux raisons :

1. le backend connaît déjà les circuits d'un bloc (`BlocCircuit`), et
   **ne connaît pas** la correspondance circuit → couleur de papier
   (`Listes!D17:E19` n'est pas importée) ;
2. un nom de circuit se lit sans rien savoir : « U11 » est écrit sur la fiche du
   grimpeur, sur son dossard et dans la console. Une couleur de papier demande
   de connaître une convention.

Un bloc **rattaché à aucun circuit** l'écrit en toutes lettres : *« Aucun
circuit — ce bloc ne compte pour personne. »* C'est exactement l'anomalie que la
spec 019 traque dans la console, et elle doit se voir aussi sur le papier qu'on
va coller : c'est le dernier moment où on peut la rattraper.

### F4 — Le QR, généré localement

`qr.svg(bloc.tag, cote_mm=45)`. Contenu : `ZJ6` — zone + numéro, collés, ce que
l'application juge attend et ce que `bloc_par_tag()` sait relire. Pas un
caractère de plus.

Aucun appel réseau, comme pour les dossards depuis la spec 005.

## 4. Périmètre

**Inclus** : une route, un gabarit `etiquettes.html`, une carte dans la vue
**Circuits** de la console (c'est là que vivent les blocs), les tests.

**Exclu, à dessein** :

- **la couleur de papier des fiches** (`Listes!D17:E19`). L'importer serait une
  bonne idée — elle ferait apparaître « Fiche Bleu Clair » sur la fiche du
  grimpeur *et* sur l'étiquette. C'est une évolution de l'import, pas de
  l'impression : une autre spec ;
- **la variante A** du classeur (numéro répété au-dessus et au-dessous). Elle
  n'apporte rien qu'une seule impression bien cadrée ne donne ;
- **le format autocollant planche A4 du commerce** (Avery et consorts). Six
  étiquettes régulières se découpent aux ciseaux ; caler des marges au dixième
  de millimètre pour une planche précise se fera si le besoin apparaît.

## 5. Critères d'acceptation

- [ ] **A1** — `GET /admin/etiquettes` rend une étiquette par bloc de la
  compétition active, six par A4.
- [ ] **A2** — L'étiquette porte : zone, numéro, QR, couleur des prises,
  circuits.
- [ ] **A3** — Le QR contient `zone + numéro` (`ZJ6`) et se relit par un
  décodeur indépendant à 45 mm.
- [ ] **A4** — `?zone=Z` ne rend que cette zone ; `?bloc=ZJ6` une seule
  étiquette.
- [ ] **A5** — Saut de page à chaque changement de zone ; une étiquette n'est
  jamais coupée.
- [ ] **A6** — Les blocs sortent dans l'ordre de `Bloc.numero`.
- [ ] **A7** — Un bloc sans circuit le dit sur son étiquette.
- [ ] **A8** — Une zone sans bloc ne produit aucune page.
- [ ] **A9** — Aucune ressource extérieure dans la page.
- [ ] **A10** — Anonyme → 401, rôle insuffisant → 403, comme `/admin/dossards`.
- [ ] **A11** — Le nombre de requêtes SQL ne dépend pas du nombre de blocs.

## 6. Cas limites

| Situation | Attendu |
| --- | --- |
| Aucun bloc en base | La page le dit et renvoie vers Compétition → Importer |
| `?zone=Q` inconnue | Page vide qui nomme la zone demandée, 200 — pas une 404 |
| `?bloc=ZJ9` inconnu | Idem |
| Bloc sans couleur de prises | La ligne « Prises » disparaît, l'étiquette garde sa mise en page |
| Bloc sans zone | L'étiquette n'affiche que le numéro ; le QR reste le `tag` complet |
| Bloc rattaché à 5 circuits | Les cinq tiennent sur une ligne, à l'ellipse si besoin |
| Zone de plus de six blocs | Continue à la page suivante, la zone suivante repart d'une page neuve |
| Aucune compétition active | 409, comme `/admin/dossards` |
| Tag contenant un caractère exotique | Le QR l'encode tel quel ; `bloc_par_tag()` le relit — non-régression |
