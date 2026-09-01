# Spec 023 — La fiche du grimpeur remplace la bande à découper

> **Statut : rédigée, en attente de la porte 2.**
> Demande d'Adrien du 01/09/2026 : « regarde ce qui est fait sur le classeur,
> onglet Fiches […] je veux que tu me remettes toutes ces informations, pas
> forcément de la même façon, tu peux faire quelque chose de plus joli. »
>
> Tranché par Adrien avant rédaction : la fiche **remplace** la bande,
> **deux fiches par A4**.

## 1. Ce qui manque

`/admin/dossards` imprime aujourd'hui des bandes de 30 mm : un QR, un gros
numéro, le nom, la catégorie et le club. C'est le contenu de l'onglet
`QR Code` du classeur, pas celui de l'onglet `Fiches`.

Le classeur, lui, imprime **une fiche par grimpeur**, et cette fiche porte cinq
choses de plus — vérifiées cellule par cellule dans les trois classeurs de
`archive/gel-2026-08/`, qui sont identiques sur ce point :

| Ce que porte la fiche du classeur | Où, dans l'onglet `Fiches` |
| --- | --- |
| Nom + club, sur deux lignes | `O4` = `Listes!F` & `"\n\n"` & `Listes!J` |
| **La liste de tous les blocs de son circuit** | `P4:T13` — 5 par ligne, jusqu'à 50 |
| **Le plan de la salle**, lettres de zone en position | `V4:X11`, texte figé, avec « Escalier » et « Haut » |
| La catégorie | `Z3` = `Z$1` |
| Le QR du dossard | `Z7` = `IMAGE(api.qrserver.com…&data=` `Q3` `)` |

L'ordre des blocs n'est pas alphabétique : `Plan!AM` les trie par
`Listes!B41:B46` — **la difficulté d'abord** (Jaune < Vert < Bleu < Mauve <
Rouge < Noir), le numéro ensuite. C'est visible dans le dump : `J1 J10 J11 …
J9 V1 V11 … V7 B15 B8`.

Sans cette feuille, un grimpeur ne sait pas **quels blocs comptent pour lui** ni
**où ils sont**. La bande ne le lui dit pas. C'est le seul papier qu'il a en
main de la journée.

## 2. Ce qu'on fait

### F1 — Une fiche, quatre par A4

> ⚠️ **Corrigé après coup.** Cette section disait « deux par A4 » — le choix
> qu'Adrien avait fait à la porte 2, sur description. En voyant la planche
> imprimée : « bien trop gros ». La taille du classeur se déduit de
> `Listes!C29:C34`, qui compte les feuilles à imprimer par catégorie : « 5 »
> pour 17 grimpeurs, « 6 » pour 21, « 7 » pour 28, « 3 » pour 11 — soit
> `ceil(n / 4)` à chaque fois. **Quatre fiches par feuille**, donc, et c'est ce
> qui est livré.


`/admin/dossards` rend des fiches de **99 × 142,5 mm** — le quart exact de la
surface utile d'un A4 portrait à 6 mm de marge. On coupe en croix, on obtient
quatre fiches. Les paramètres `?dossard=` et `?categorie=` ne changent pas.

```
┌──────────────────────────────────────────────────────────────────────┐
│  ┌────┐                                                    ┌───────┐ │
│  │ 42 │  Lecomte Camille                      U11 F        │  QR   │ │
│  └────┘  Les Lézards Vagabonds                circuit U11  │  28mm │ │
│                                                            └───────┘ │
│ ─────────────────────────────────────────────┬──────────────────────  │
│  TES 36 BLOCS                                │  LE MUR              │
│  ┌────┬────┬────┬────┬────┬────┐             │       X  Y           │
│  │ Z  │ D  │ A  │ M  │ I  │ J  │             │    D  Z   ⌐Escalier  │
│  │ J6 │J10 │ J1 │J14 │ J7 │J15 │             │    C  B  A           │
│  ├────┼────┼────┼────┼────┼────┤             │                      │
│  │ …  │    │    │    │    │    │             │ L                    │
│  └────┴────┴────┴────┴────┴────┘             │ M  K  J  I   H  G  F │
│  J Jaune · V Vert · B Bleu · M Mauve         │ N            E       │
│  · R Rouge · N Noir                          │    Haut              │
└──────────────────────────────────────────────────────────────────────┘
```

### F2 — Les blocs, dans l'ordre du classeur

Une case par bloc : la **zone** en petit au-dessus, le **numéro** en gros
dessous — `Z` / `J6`. L'ordre est celui du classeur : difficulté, puis numéro.

Deux ajouts par rapport au classeur, qui n'affiche que `J6` :

- **la zone.** Le classeur la garde pour lui ; sans elle, « J6 » ne dit pas où
  aller, et le plan de la salle ne sert à rien. Elle est déjà en base
  (`Bloc.zone`), et c'est exactement ce qui est écrit sur l'étiquette du bloc au
  mur (« Bloc J6 / Zone Z »). Le QR du bloc, lui, contient les deux collés :
  `ZJ6` ;
- **la légende des couleurs** sous le tableau — elle existe dans le classeur
  (`V13`), mais seulement sur certaines fiches. Ici, sur toutes.

Les blocs sont **regroupés par difficulté**, avec un mince liseré de la couleur
à gauche de chaque case. Sur une imprimante noir et blanc, le liseré devient un
gris et l'information reste : la première lettre du numéro **est** la couleur
(`J6` = Jaune n° 6).

### F3 — Le plan de la salle, repris tel quel

Le plan est **figé** : le même texte dans les trois classeurs, de 2024 à 2026.
C'est le mur d'Annonay, pas une donnée de compétition. Il est donc une constante
du code, avec le commentaire qui dit d'où il vient.

Sa grille est celle du classeur — la colonne `V` compte pour une case, `W` et
`X` pour trois chacune :

```
             │  ·   ·   ·  │  X   Y   ·
             │  D   ·   ·  │  Z   ·   ·
             │  C   B   A  │ «Escalier»
             │             │
       L     │             │
       M     │  K   J   I  │  H   G   F
       N     │             │  E   ·   ·
             │  «Haut»     │
```

Deux améliorations sur le classeur, dont il dit lui-même qu'il est « pas très
joli » :

- les zones **où ce grimpeur a des blocs** sont en aplat d'encre, les autres en
  gris clair. Le plan devient un itinéraire, pas une carte générale ;
- « Escalier » et « Haut » sont écrits en italique gris : ce sont des repères de
  la salle, pas des zones. Le classeur les mélange aux lettres.

⚠️ **Une lecture à confirmer.** Le dump ne garde que le *texte* des cellules,
pas leur alignement. Les cellules à trois lettres (`c b a`, `k j i`, `h g f`)
donnent les positions sans ambiguïté ; celles à une ou deux lettres (`d`, `z`,
`e`, `x y`, `Haut`) sont **lues comme calées à gauche** de leur cellule. C'est
la lecture qui préserve les alignements verticaux visibles (`D` au-dessus de
`C`, `Z` au-dessus de « Escalier », `E` sous `H`). À vérifier d'un coup d'œil
sur le vrai classeur avant de coder : c'est une constante, elle se corrige en
une ligne.

⚠️ **Le plan ne porte que 17 des 20 zones** — `U`, `V` et `W` n'y figurent pas,
et n'ont jamais porté de bloc dans les trois classeurs. Si un bloc du circuit
tombait dans l'une d'elles, la fiche l'écrirait sous le plan : *« hors plan :
zone U »*. Un bloc qu'on ne peut pas situer doit **se dire**, pas disparaître.

### F4 — Ce qui reste vrai de l'existant

- Le QR est **généré localement** (`qr.py`, `segno`) — le classeur, lui, appelle
  `api.qrserver.com`, ce qui envoie les dossards à un tiers et ne marche pas si
  la connexion tombe le matin. C'est acquis depuis la spec 005, ça le reste.
- Le contenu du QR est **le dossard nu**, inchangé : les téléphones des juges
  lisent ça et rien d'autre.
- Une fiche n'est jamais coupée par un saut de page.
- L'en-tête d'écran (« 100 fiches à imprimer, vérifie l'échelle à 100 % »)
  reste, et reste masqué à l'impression.

## 3. Périmètre

**Inclus** : `templates/dossards.html` (réécrit), `routes/admin.py`
(`page_dossards` charge les circuits), une constante de plan, le libellé de la
carte de la console.

**Exclu, à dessein** :

- **les étiquettes de blocs à coller au mur** — la zone gauche de l'onglet
  `Fiches` (`A3:M13` : zone, numéro, couleur des prises, QR `ZJ6`). C'est un
  autre papier, pour un autre public, et il mérite sa propre spec. Adrien l'a
  décrit pour situer l'onglet, pas pour le demander ;
- **une case à cocher par bloc.** La fiche deviendrait un support de saisie
  papier concurrent de l'onglet `Saisie manuelle`, ce que la consigne
  d'exploitation interdit depuis la spec 005 (« le jour J, on ne coche plus la
  grille du classeur ») ;
- **le score ou le classement sur la fiche.** Elle s'imprime avant la
  compétition ;
- **l'URL `/admin/dossards`**, qui ne change pas. Le mot « dossard » reste juste
  côté serveur : c'est le numéro, et il est toujours là. Seul le libellé de la
  console parle de « fiches ».

## 4. Critères d'acceptation

**Tous vérifiés le 01/09/2026** — 47 tests (`tests/test_fiches.py`,
`tests/test_qr_et_dossards.py`) et un PDF mesuré : 8 fiches → 2 pages,
99 × 142,5 mm au pixel près.

- [x] **A1** — Une fiche par participant numéroté, **quatre par page A4**,
  jamais coupée par un saut de page.
- [x] **A2** — La fiche porte : dossard, nom, club, catégorie, circuit, QR.
- [x] **A3** — Le QR contient le dossard nu et se relit par un décodeur
  indépendant à sa taille d'impression — **non-régression** du test qui existe.
- [x] **A4** — Le tableau liste **tous** les blocs du circuit du grimpeur, et
  seulement eux.
- [x] **A5** — L'ordre est celui du classeur : difficulté (Jaune→Noir), puis
  numéro. Un bloc sans couleur passe en dernier, jamais en premier.
- [x] **A6** — Chaque case porte la zone et le numéro.
- [x] **A7** — Le plan de la salle reprend les positions du classeur, à la case
  près.
- [x] **A8** — Les zones du grimpeur ressortent sur le plan ; les autres sont
  en gris.
- [x] **A9** — Une zone hors plan est signalée sous le plan.
- [x] **A10** — `?dossard=42` rend une fiche, `?categorie=U11 F` rend le lot de
  la catégorie — **non-régression**.
- [x] **A11** — Aucun appel réseau dans la page : ni police, ni image, ni script
  distant — **non-régression** de la règle des specs 005/016.
- [x] **A12** — Le nombre de requêtes SQL ne dépend pas du nombre de
  participants (3 requêtes, comme `circuits.inventaire`).

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| Participant sans catégorie | Fiche imprimée quand même : identité et QR, et à la place du tableau *« Aucune catégorie : ce grimpeur n'est rattaché à aucun circuit. »* Il faut pouvoir lui donner son dossard |
| Catégorie renseignée, circuit absent en base | *« Circuit U11 inconnu — le classeur n'a pas encore été importé. »* |
| Circuit connu, aucun bloc rattaché | *« Aucun bloc dans ce circuit »* + renvoi vers Circuits, qui sait dire pourquoi (spec 019) |
| Bloc sans couleur de difficulté | Rangé après toutes les couleurs, sans liseré, sans casser le tri |
| Bloc sans zone | La case n'affiche que le numéro ; rien ne s'allume sur le plan |
| Circuit de plus de 50 blocs | Les cases rétrécissent, la fiche **reste sur une seule A5** — jamais de débordement sur la fiche voisine |
| Nom très long, club très long | Coupés à l'ellipse, jamais repoussant le QR hors de la fiche |
| Aucun participant numéroté | La page le dit, comme aujourd'hui |
| Nombre impair de fiches | La dernière demi-page reste vide |
| Impression noir et blanc | Tout reste lisible : les liserés deviennent des gris, la couleur est déjà dans la lettre du numéro |
| Un dossard réaffecté après impression | Hors sujet, et déjà couvert : on réimprime **une** fiche avec `?dossard=` |
