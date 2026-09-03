# Spec 036 — L'avancement par zone, sur le plan du mur

> **Statut : rédigée AVANT le code, le 03/09/2026.** Porte 2 non franchie au
> moment de la rédaction ; Adrien a demandé le lot en disant « tu fais ou mets
> à jour les specs si nécessaire, tu corriges et surtout tu ajoutes/ajustes les
> tests ». La spec est donc écrite d'abord, la maquette ensuite, le code après.
> C'est la correction de ce qui a été reproché aux specs 027 et 032.
>
> Demande d'Adrien du 03/09 : « Je suis revenu sur la partie affichage
> résultats. Et quand je clique sur un grimpeur, je peux voir effectivement son
> pseudo, son dossard, et après quand je bascule sur le mur, j'aimerais bien
> que par zone où il est censé grimper, où il a des blocs à faire, je veux voir
> son avancement par zone. Je voudrais que tu m'affiches un petit chiffre avec
> le nombre de blocs qu'il a réussi sur le nombre de blocs qui lui reste dans
> cette zone. Tu vois par exemple, s'il a réussi un bloc sur quatre dans cette
> zone, tu marques un sur quatre, à côté de la zone. Il faut que ce soit
> visuel. »

## 1. Ce qui manque

La spec 026 a donné au mur trois états, et trois seulement :

| Ce que la zone montre | Ce qu'elle dit |
| --- | --- |
| effacée | il n'a rien à y faire |
| pleine | il lui reste au moins un bloc |
| contour vert | il les a tous faits |

Entre « il m'en reste » et « j'ai fini », il n'y a **aucune mesure**. Un
grimpeur dont le circuit s'étale sur cinq zones voit cinq pans allumés à
l'identique : celui où il lui reste un bloc et celui où il lui en reste sept se
peignent pareil. Pour savoir lequel vaut le déplacement, il faut toucher les
zones **une par une** et lire le compteur du panneau du bas — cinq gestes pour
une information qui tient en cinq chiffres.

Le compteur existe donc déjà, mais il n'est lisible **que zone par zone**, et
seulement après l'avoir choisie. Ce lot ne l'invente pas : il le **sort du
panneau et le pose sur le plan**, pour que les cinq zones se comparent d'un coup
d'œil.

## 2. Ce qu'on fait

### F1 — Chaque zone du circuit porte son compteur

Sur le plan du mur de la fiche, une zone où le grimpeur a des blocs porte
**« faits / total »** — « 1/4 » : un bloc validé sur les quatre blocs de son
circuit qui se trouvent dans cette zone.

La notation `N/M` n'est pas choisie ici : **la fiche l'écrit déjà**, en tête de
chaque groupe de couleur (`.sf-couleur-tete em` — « 3/6 » sous « Vert »). Le
plan reprend la notation de l'écran qui l'ouvre, pas une deuxième.

Le total, c'est **les blocs de son circuit dans cette zone**, pas les blocs de
la zone. Une zone de vingt blocs dont trois sont dans son circuit affiche « 1/3 »
et jamais « 1/20 » : la fiche ne parle que de ce qui compte pour lui.

### F2 — Une zone sans bloc du circuit ne porte pas de compteur

Elle est déjà effacée (spec 026 F3). Un « 0/0 » posé dessus rendrait la moitié
du plan bavarde pour ne rien dire, et surtout : il ferait chercher des blocs là
où le grimpeur n'en a pas. **L'absence de compteur est l'information.**

Une zone où il n'a rien fait porte, elle, **« 0/4 »** — le zéro est une
information, l'absence en est une autre.

### F3 — Le compteur compte ce que le classement compte

Un bloc **crédité par la cascade de couleurs** (spec 025) compte comme fait.
C'est le point délicat du lot ; il a sa section, la § 6.

### F4 — Il reste lisible partout où la page se lit

- **Thème clair et thème sombre** (`body.sombre`), sur les six remplissages de
  profil (dalle → toit) qui sont tous des aplats moyennement clairs : le
  compteur est posé sur une **pastille** de la couleur du halo de la lettre —
  sans fond, un chiffre posé sur un aplat de profil devient illisible. La
  pastille remplace le halo, et le fait mieux : un halo est un contour découpé
  sur la forme des glyphes, une pastille est un fond.
- **Sur un téléphone de 390 px de large comme sur un écran de portable.** Le
  compteur est dimensionné **en proportion de la lettre de la zone**
  (`mur.taille`, calculée par le serveur pour tenir dans le pan) : il grandit et
  rétrécit avec elle, **et sa pastille aussi**. Un libellé trop long rétrécit
  **dans** une pastille qui, elle, ne bouge pas — depuis qu'elle fait 1,6 fois
  la lettre (§ 2 ter), « 12/15 » tient à sa taille pleine et le rétrécissement
  ne sert plus qu'aux cas extrêmes. Ce qu'il suppose, en revanche, ce sont des pans d'au moins ~14,6
  unités de haut ; c'est une limite réelle, chiffrée et surveillée par un test,
  et elle est expliquée dans `architecture.md` § 3.
- La **fiche n'existe pas en mode mur** (`?mur`) — spec 026 F1, garde
  `if (!MUR && !ARCHIVE)`. Le compteur n'est donc jamais projeté dans la salle.
  Ce qui doit rester vrai, c'est qu'il tienne sur un grand écran de bureau,
  où la feuille est large.

### F5 — Il suit les réussites en direct

La fiche ouverte se rafraîchit au battement du classement (spec 026 § 6.5). Le
mur ne se **redessine** pas à chaque rafraîchissement — il est monté une fois
par grimpeur — il se **décore**. Le compteur est donc posé par la décoration,
comme les états de zone, et pas par le dessin : un bloc validé pendant qu'on
regarde le plan doit faire passer « 1/4 » à « 2/4 » sans reconstruire dix-sept
polygones.

## 2 bis. Ce que les maquettes ont tranché

`maquettes/compteurs.html` — le vrai relevé d'Annonay, la vraie géométrie
(polygones, place et taille des lettres sortis de `fiches.plan_pour(set())`), un
circuit simulé de 27 blocs sur six zones : une zone intacte (0/2), une entamée
(1/4), une terminée (3/3), une à bloc unique (1/1) et une à deux chiffres de
chaque côté (10/12) — celle qui dit si le compteur rétrécit ou s'il déborde.
Onze zones sans bloc du circuit, qui ne doivent rien porter.

| Essai | Verdict |
| --- | --- |
| A — le chiffre nu sous la lettre | Proposé, **non retenu** |
| A2 — la lettre rend un cran au chiffre | Écarté. 13 % de corps gagnés, mais la lettre d'un pan changerait de taille **selon le circuit du grimpeur** : deux téléphones côte à côte ne montreraient plus la même salle. Et il faudrait poser une transformation sur la lettre, que la fiche **papier** dessine aussi |
| **B — la pastille (socle arrondi)** | **RETENU par Adrien le 03/09** : « j'aime beaucoup la pastille que tu mets là dans l'écran B » |
| C — l'anneau de progression | Écarté. L'anneau se confond avec le contour vert de « zone terminée » et avec l'anneau ocre de la zone visée : trois cercles pour trois choses différentes |

**Ce qui avait fait écarter B, et pourquoi ça ne tient plus.** La maquette
dimensionnait le socle sur son **texte** : il avait donc une largeur que rien ne
bornait, et sur le relevé réel il mordait la lettre au-dessus et sortait du pan
en dessous. Le socle se dimensionne maintenant sur la **lettre** — largeur
`1,0 × taille`, hauteur `1,12 × le corps nominal du chiffre` — et il hérite
donc des bornes que `fiches.taille_lettre` a déjà posées sur la lettre par la
boîte du pan. **Aucune géométrie n'est relue côté page**, ce qui était
l'objection de fond.

Les quatre ratios retenus, et le calcul qui les fixe (détail dans
`plan.js`) : le budget vertical est ce qui reste entre le bas du glyphe de la
lettre (`0,36 × taille`) et le bas du pan (`0,833 × taille` pour un pan de 15
unités portant une lettre de 9), soit **0,473 × taille**. La pastille en occupe
`1,12 × 0,40 = 0,448`, centrée à `0,60` :

| Ratio | Valeur | Ce qu'il borne |
| --- | --- | --- |
| `COMPTE_ECHELLE` | 0,40 | le corps du chiffre |
| `COMPTE_DESCENTE` | 0,523 | la descente de la pastille sous le centroïde |
| `PASTILLE_HAUTEUR` | 1,12 | la hauteur du socle, **× le corps nominal** |
| `PASTILLE_LARGEUR` | 1,6 | la largeur du socle, **× la taille de la lettre** |
| `LETTRE_MONTEE` | 0,267 | de combien **la lettre monte** au-dessus du centroïde |

⚠️ **Ces valeurs ont bougé le 03/09, deux fois.** Le tableau ci-dessus est celui
qui vaut ; le paragraphe qui suit dit d'où venaient les précédentes, parce que
l'arithmétique est la même et que seule la répartition a changé. La pastille est
passée de 1,0 à 1,6 pour porter la jauge (§ 2 ter), et la lettre s'est mise à
monter pour lui faire de la place. Le détail du calcul des trois airs égaux est
dans `architecture.md` § 3.

Avec la première répartition — lettre au centroïde, pastille à 0,60 :

- haut = 0,60 − 0,224 = **0,376 ≥ 0,36** — la pastille ne mordait pas le
  **glyphe** de la lettre…
- …mais **son halo, si** : il descend à 0,48, donc il la recouvrait de
  **0,104 × taille**. C'est ce chevauchement qu'Adrien a vu (« là c'est trop
  proche »), et c'est la position **E** qui l'a réglé ;
- bas = 0,60 + 0,224 = **0,824 ≤ 0,833** — elle ne sortait pas du pan, mais il
  ne restait que 0,009 dessous : la descendre n'était pas une option.

Le chiffre perd 13 % de corps par rapport à l'essai A (0,40 au lieu de 0,46) ;
c'est le prix de la pastille, et il est chiffré. En échange il gagne un **fond**
au lieu d'un **halo** — un halo est un contour découpé sur la forme des glyphes,
qui se battait avec les six aplats de profil. La hauteur du socle se calcule sur
le corps **nominal** et jamais sur le corps réduit d'un libellé long :
dix-sept pastilles identiques, pas dix-sept tailles.

## 2 ter. Ce qui se remplit — la pastille, et pas le cadre

> « Je ne mettrais pas un anneau, je mettrais le rectangle que tu mets en
> surbrillance vert pour dire que la zone est terminée. Et bien celui-là, je le
> remplirais en fonction de l'avancement. » (Adrien, 03/09)

> ## ✅ TRANCHÉE LE 03/09, **sur le rendu réel** : c'est **la pastille du
> compteur** qui se remplit de vert. Le cadre de la zone garde son
> tout-ou-rien.
>
> ⚠️ **Cette phrase a deux lectures, et la première implémentation a pris la
> mauvaise.** « Le rectangle en surbrillance verte » a d'abord été compris comme
> le **cadre** de la zone : il a été épaissi (×2), rogné dans le pan pour ne pas
> déborder chez la voisine, et rempli sur la longueur de son contour — quatre
> paramètres, tous mesurés, tous cohérents entre eux. Mis sous les yeux
> d'Adrien : **« ah non ce n'est pas ce que je voulais »**. Ce qu'il appelait
> « le truc avec le nombre de blocs restant », c'était **la pastille**.
>
> On garde la trace des deux, parce que l'historique du dépôt garde la première
> et qu'un lecteur pressé pourrait s'y arrêter — et parce que la leçon vaut
> plus que le code jeté : **une phrase qui décrit un objet à l'écran se vérifie
> en montrant l'objet, pas en raisonnant dessus.** La maquette
> `maquettes/pastille.html` montre les deux rendus réels côte à côte.

### Ce qui est retenu, et qui l'a choisi sur pièce

| | Retenu | Ce que ça règle |
| --- | --- | --- |
| **Ce qui se remplit** | **la pastille du compteur** | elle porte déjà le nombre de blocs ; le vert en dit la part sans ajouter d'objet au plan |
| **La forme du vert** | **bout droit** — un rectangle franc découpé dans le socle | il épouse le bord arrondi à gauche et se coupe net à droite : on lit un **niveau**. Arrondi, il ferait une petite pastille dans la grande, donc **deux objets** |
| **La force du vert** | **franc**, 62 % | le chiffre est posé dessus : c'est le seul arbitrage du lot, et il a été fait à l'œil sur les trois forces |
| **La largeur du socle** | **×1,6** la lettre (au lieu de ×1,0) | un vert qui remplit un rond ne dit pas une proportion. **La hauteur ne bouge pas**, ni le corps du chiffre : « seulement l'ovale de fond, et uniquement horizontalement » |
| **Le cadre de la zone** | **inchangé** — tout-ou-rien, 1,6 unité, sur l'arête | « repasse la taille du cadre vert de réussite totale à sa taille d'avant » |
| **La place** | position **E, l'équilibre** : la lettre monte de 0,267, la pastille se pose à 0,523 | les **trois airs deviennent égaux** — au-dessus de la lettre, entre la lettre et la pastille, sous la pastille |

### « Là c'est trop proche » — ce que la mesure a dit

La demande était : « descends un peu la jauge de la lettre, ou monte la lettre,
ou un mélange des deux ». La mesure ne répond qu'à moitié, et c'est le résultat
utile du lot :

- **sous la pastille il ne restait que 0,009 × taille** — un cinquième de pixel
  sur un téléphone. La descendre seule ne pouvait rien donner ;
- **ce qui la collait à la lettre n'était pas la place, c'était un
  chevauchement** : le **halo** de la lettre recouvrait la pastille de
  **0,104 × taille**, près d'une unité de plan. Les deux objets se touchaient ;
- **toute la place libre était au-dessus** de la lettre : 3,18 unités entre son
  halo et le haut du pan.

D'où six positions, posées sur le vrai dessin et chiffrées
(`maquettes/pastille.html`), et le choix de **E** : les trois airs égaux, à
0,086 × taille chacun. Les deux ratios en découlent, ils ne sont pas réglés à
l'œil :

```
LETTRE_MONTEE   = 0,833 − 0,086 − 0,48  = 0,267
COMPTE_DESCENTE = 0,833 − 0,086 − 0,224 = 0,523
```

### Ce que ça coûte, chiffré et accepté

- **La pastille croise le cadre « terminée »** : 14,4 unités de large dans un
  pan de 15, contre 13,4 pour l'intérieur du cadre. Elle **passe devant** —
  peinte dessous, elle se ferait couper à ses deux extrémités, là où le vert dit
  justement où il s'arrête. C'est donc **le cadre qui porte l'encoche**, une
  encoche constante, sur toutes les zones comptées.
- **Le chiffre d'une zone terminée ne vire plus au vert.** Il le faisait quand
  la pastille était un fond neutre ; sur une pastille pleine de vert, vert sur
  vert ne se lit pas. C'est le remplissage qui dit « terminée », et le chiffre
  reste à l'encre.
- **Un libellé long ne rétrécit plus aussi tôt** : le socle borne le texte, et
  il fait 1,6 fois la lettre. « 12/15 » sort maintenant à sa taille pleine.
  C'est le bénéfice direct de l'élargissement — « repasse sa taille à celle
  d'origine ».

### Ce que la première lecture a laissé derrière elle

Rien dans le code : la jauge de contour, sa piste, son découpage et
l'épaississement ont tous été retirés. Deux choses lui survivent, parce
qu'elles se justifient toutes seules :

- **la couche des compteurs**, peinte après les cadres — c'est maintenant la
  largeur de la pastille qui l'impose ;
- **le rebond du compteur avec son pan**, et son redémarrage au pluriel.

Ce qui a été retiré et mérite d'être retrouvé si la question revient : la
**garantie de coin du serveur** (chaque pan réénuméré depuis son coin
haut-gauche, dans le sens horaire). Elle ne servait qu'à une jauge de contour ;
elle est dans l'historique de la branche, avec ses deux tests.

## 3. Périmètre

**Dans** : le plan du mur de la fiche du grimpeur (`resultats.html`,
`static/resultats/plan.js`, `static/resultats/suivi.js`), et leurs tests.

**Hors** :

- **Le serveur.** `/api/public/grimpeur/<id>` envoie déjà tout ce qu'il faut :
  chaque bloc des groupes porte sa `zone` et son `etat`. Compter côté serveur
  ajouterait un champ dérivé — donc un champ qui peut mentir — pour une
  addition que la page fait déjà deux fois. **Aucune ligne de Python dans ce
  lot.**
- **Le bloc de légende `.sf-legende`.** Une PR parallèle (`fix/revue-du-03-09`)
  y remet la légende des couleurs de profil. On n'y touche pas, et on n'ajoute
  pas de légende à côté : le panneau du bas dit déjà « 1 sur 2 » en toutes
  lettres dès qu'on touche une zone, ce qui explique le compteur mieux qu'une
  ligne de légende de plus.
- **La fiche papier** (spec 023). Elle sort de l'imprimante le matin et ne sait
  rien de ce qui a été grimpé ; un compteur y serait toujours « 0/4 ».
- **Le nom accessible du SVG.** Le plan est `role="img"` avec un libellé
  unique ; ses enfants ne sont pas exposés. Le compteur y est donc **muet pour
  un lecteur d'écran** — et c'est acceptable parce que le panneau du bas porte
  la même information en texte (« Zone M — tes 2 blocs · 1 sur 2 »). Le
  formuler autrement demanderait de revoir l'accessibilité du plan entier, ce
  qui est un autre lot.

## 4. Critères d'acceptation

| # | Situation | Attendu |
| --- | --- | --- |
| A1 | Zone où le grimpeur a 4 blocs, 1 fait | la zone porte « 1/4 » |
| A2 | Zone où il n'a rien fait | « 0/4 » |
| A3 | Zone entièrement faite | « 4/4 », sur une **pastille entièrement verte** — le chiffre, lui, reste à l'encre : vert sur vert ne se lit pas |
| A3b | Zone sans bloc de son circuit | **aucune pastille** non plus — un socle vide serait un fond posé pour ne rien porter |
| A4 | Zone sans bloc de son circuit | **aucun compteur** |
| A5 | Bloc crédité par la cascade | compté comme fait (§ 6) |
| A6 | Zone du circuit absente du plan | rien à dessiner, aucune erreur |
| A7 | Réussite enregistrée, mur ouvert | le compteur passe de « 1/2 » à « 2/2 » sans redessiner |
| A8 | Zone visée (on arrive depuis un bloc) | le compteur reste lisible pendant le rebond |
| A9 | Thème sombre | contraste tenu sur les six profils |
| A10 | Plan de format inconnu | pas de mur, donc pas de compteur — inchangé |
| A9b | Zone à 1 bloc sur 4 | la pastille est **verte au quart**, depuis son bord gauche |
| A9c | Zone à 0 bloc fait | la pastille est là, **rien n'est vert** — le zéro se dit, et il se voit |
| A9d | Le vert | ne sort **jamais** du socle : il y est découpé |
| A9e | Réussite enregistrée, mur ouvert | le vert s'allonge au même battement que le chiffre |
| A9f | Le cadre de la zone | **inchangé** : tout-ou-rien, 1,6 unité, aucun remplissage |
| A11 | Le compteur du plan et celui du panneau | **le même nombre**, toujours |
| A12 | Le compteur et l'anneau vert « zone terminée » | **jamais contradictoires** |

A11 et A12 ne sont pas des vœux : ils sont tenus **par construction**, les trois
lectures dérivant d'une seule fonction (voir `architecture.md`), et un test le
vérifie.

## 5. Cas limites

| Cas | Décision |
| --- | --- |
| Bloc sans zone (`zone` vide) | ignoré, comme dans `etatsDesZones` — il n'invente pas de zone |
| Zone nommée dans le circuit mais absente du plan | aucun nœud à décorer, la boucle ne la voit pas |
| Zone du plan absente du circuit | compteur vide, pas « 0/0 » |
| Circuit vide ou inconnu | pas de bouton « Le mur » (déjà : `PLAN_DESSINABLE && d.total`) |
| Compteur à trois chiffres par côté (« 12/15 ») | il rétrécit au lieu de déborder |
| `mur.taille` absent ou nul | repli à 6, comme la lettre |

## 6. Le cas des blocs crédités — la décision

**Le compteur compte les blocs crédités comme faits.** « 1/4 » veut dire « un
bloc de cette zone est validé », pas « un bloc de cette zone a été grimpé ».

C'est contre-intuitif au regard de la règle du projet — *l'historique est la
seule source de vérité, et un bloc crédité n'est pas un bloc grimpé* — donc
voici pourquoi, et ce qui empêche cette décision de devenir un mensonge.

**Pourquoi.**

1. **Un écran ne peut pas porter deux définitions de « fait ».** La page en tient
   déjà trois, toutes du même côté : l'anneau vert « zone terminée »
   (`etatsDesZones`), le compteur du panneau (« 1 sur 2 », `compteDeZone`) et le
   compteur par couleur de la fiche (« 3/6 ») comptent **tous** le crédité comme
   fait. Un quatrième compteur qui compterait autrement afficherait « 3/4 » sur
   une zone cerclée de vert et détaillée en « terminée » juste en dessous. Le
   lecteur n'en conclurait pas « il y a un bloc crédité » : il en conclurait que
   la page est cassée.
2. **Le plan répond à une question, une seule : où me reste-t-il du travail ?**
   Un bloc crédité est du travail que le grimpeur n'a **plus** à faire. L'y
   envoyer serait la seule erreur vraiment coûteuse de ce lot — et la spec 026
   a déjà tranché dans ce sens en rendant une case créditée **non cliquable** :
   « on n'envoie personne grimper ce qu'il n'a pas besoin de grimper ».
3. **La distinction reste, là où elle est utile.** Elle vit sur la case du bloc,
   en hachures à 45°, et à un seul geste : toucher la zone ouvre le panneau qui
   montre ses cases. Le plan est une carte, pas un relevé de validation.

**Ce qui empêche que ça devienne un mensonge.** Les trois lectures ne sont pas
trois additions écrites côte à côte : elles dérivent toutes de
`comptesDesZones()`, une fonction unique — l'état d'une zone se **déduit** de son
compte, il ne se recompte pas. Deux compteurs du même écran ne peuvent donc pas
diverger sans que la fonction soit fausse pour les deux à la fois, et un test
vérifie l'invariant A12 explicitement (« une zone `finie` a toujours
`faits === total` », sur des données qui contiennent un crédité).

**Ce qu'on n'a pas fait, et pourquoi.** Marquer le compteur quand une partie de
son compte vient de la cascade — une hachure, un signe, une teinte à part — a
été écarté : `validation_couleur` vaut 0 par défaut, la cascade n'a servi **ni
en novembre 2025 ni en mars 2026**, et la spec 026 pose déjà la règle pour ce
cas précis (« la légende ne le nomme que s'il existe »). Décorer un chiffre de
trois pixels pour un état qui n'est jamais arrivé coûterait plus de lisibilité
qu'il n'en apporterait. Le jour où la cascade est activée pour de bon, c'est le
**panneau** — qui a la place de faire une phrase — qui devra le dire, pas le
plan.
