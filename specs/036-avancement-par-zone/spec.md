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
  rétrécit avec elle, **et sa pastille aussi**. Un libellé plus long —
  « 12/15 » — rétrécit **dans** une pastille qui, elle, ne bouge pas. Ce qu'il suppose, en revanche, ce sont des pans d'au moins ~14,6
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
| `COMPTE_DESCENTE` | 0,60 | la descente de la pastille sous l'axe de la lettre |
| `PASTILLE_HAUTEUR` | 1,12 | la hauteur du socle, **× le corps nominal** |
| `PASTILLE_LARGEUR` | 1,0 | la largeur du socle, **× la taille de la lettre** |

- haut = 0,60 − 0,224 = **0,376 ≥ 0,36** — la pastille ne mord pas la lettre ;
- bas = 0,60 + 0,224 = **0,824 ≤ 0,833** — elle ne sort pas du pan.

Le chiffre perd 13 % de corps par rapport à l'essai A (0,40 au lieu de 0,46) ;
c'est le prix de la pastille, et il est chiffré. En échange il gagne un **fond**
au lieu d'un **halo** — un halo est un contour découpé sur la forme des glyphes,
qui se battait avec les six aplats de profil. La hauteur du socle se calcule sur
le corps **nominal** et jamais sur le corps réduit d'un libellé long :
dix-sept pastilles identiques, pas dix-sept tailles.

## 2 ter. Décision ouverte — le cadre de la zone devient-il une jauge ?

> « Je ne mettrais pas un anneau, je mettrais le rectangle que tu mets en
> surbrillance vert pour dire que la zone est terminée. Et bien celui-là, je le
> remplirais en fonction de l'avancement. » (Adrien, 03/09)

> ## ✅ TRANCHÉE LE 03/09 : **le cadre se remplit**, en quatre paramètres.
>
> ⚠️ **Adrien a d'abord répondu « on ne remplit pas le cadre », puis est revenu
> sur sa réponse après avoir regardé la comparaison d'épaisseurs.** Les deux
> réponses sont vraies dans l'ordre où elles ont été données ; c'est la seconde
> qui vaut. On le note parce que l'historique du dépôt garde la première, et
> qu'un lecteur pressé pourrait s'y arrêter.
>
> | | Retenu |
> | --- | --- |
> | **E1a — la pose** | **C — rognée dans le pan** : posée sur l'arête, mais **découpée par la forme du pan**, donc seule sa moitié intérieure est peinte |
> | **E1b — l'épaisseur** | **×2**, soit **3,2 unités** |
> | **E1c — l'ordre de peinture** | **La pastille passe devant** : le compteur devient un **cartouche serti** dans le cadre |
> | **E2 — le coin de départ** | **Le serveur le garantit**, et **un test le vérifie** |
>
> ### Pourquoi ces quatre-là et pas d'autres — les mesures qui les imposent
>
> 1. **La pose C est la seule qui survive à l'épaississement.** Posée sur
>    l'arête (A), la jauge mord **1,6 unité** chez la voisine à ×2 — et les pans
>    d'Annonay se touchent bord à bord. Rentrée de 10 % (B), elle ne tient que
>    tant que le trait reste sous **1,5 unité** : au-delà, sa moitié extérieure
>    ressort. Découpée par la forme du pan, elle est à distance constante du
>    bord **quelle que soit l'épaisseur**, et ne peut structurellement pas
>    déborder.
> 2. **`scale()` ne convient pas pour rentrer un cadre.** Il est uniforme, les
>    pans ne le sont pas : sur D (15×30) et L (15×25), un rentrait par mise à
>    l'échelle rentre deux fois plus en haut qu'à gauche. Le découpage, lui, suit
>    la forme.
> 3. **La pastille devant, parce que l'inverse ampute le compteur.** L'ordre de
>    peinture actuel met les cadres après les pastilles : à ×2, l'arête basse
>    recouvre **77 %** de la hauteur de la pastille — et au pire moment, cette
>    arête étant le troisième quart du contour, donc peinte dès 2/4 et
>    **toujours** à 4/4. Vérifié à l'écran sur la page réelle : à ×1 le
>    « 12/12 » est net, à ×2 il est rogné. Le prix de l'inversion est chiffré et
>    accepté : la pastille masque **60 %** de l'arête basse, soit **15 %** du
>    périmètre — une encoche **constante**, présente sur toutes les zones et à
>    toutes les valeurs, donc un décor et non un signal. Le levier pour la
>    réduire est `PASTILLE_LARGEUR`, jamais l'ordre de peinture.
> 4. **Le coin de départ est une garantie du serveur.** Une jauge de contour
>    part d'un coin, et `plan.js` est écrit pour **ne rien savoir de la
>    géométrie** — c'est ce qui lui permet de survivre à un changement de plan.
>    Le premier point de chaque polygone est donc le coin haut-gauche, et un
>    test l'exige. Le piège devient **détectable** au lieu d'être documenté.
>
> ### Ce que ça change pour l'invariant A12
>
> « Le compteur et l'anneau vert ne se contredisent jamais » devient une
> **tautologie** : les deux dérivent du même compte. Le test reste, mais il ne
> protège plus une cohérence — il protège la dérivation unique.

**Statut : ACCEPTÉE (03/09), en implémentation.** C'est une **unification** : le
cadre vert « zone terminée » (`.cadre-zone.z-finie`) et le compteur cessent
d'être deux signaux pour devenir deux lectures de la même donnée — « terminée »
n'est plus un état à part, c'est le cadre plein. L'invariant A12 (« le compteur
et l'anneau vert jamais contradictoires ») devient alors une tautologie plutôt
qu'un test.

La maquette qui l'instruit est `maquettes/remplissage.html` : sept variantes,
sur le vrai relevé, en clair et en sombre. Les cinq cas — 0/4, 1/4, 3/4, 4/4 et
une zone sans bloc — sont posés sur **cinq pans qui se touchent bord à bord**
(J, I, H, G, F) et sur cinq profils différents, plus la zone visée (D) et une
colonne empilée (L sur M).

| Variante | Verdict de la maquette |
| --- | --- |
| **R1b — le contour qui se remplit, rentré de 10 %** | Recommandé **avant** la demande d'épaississement ; ne tient plus au-delà de 1,5 unité de trait |
| R2 — le contour gradué, un segment par bloc | La version riche de R1b, si on veut **compter** sur le plan |
| R1 — le même contour, posé sur l'arête | Écarté : il déborde chez la voisine et les jauges se soudent |
| R3 — le remplissage par le bas | Écarté : il fabrique une arête horizontale au milieu du pan |
| R4 — le remplissage horizontal | Écarté : même chose, en vertical, sur une bande qui n'est faite que d'arêtes verticales |
| R5 — c'est la pastille qui se remplit | Écarté : elle ne répond pas à la demande, et vert sur vert ne se lit pas |

### Les cinq pièges, et ce que la maquette en dit

1. **Les pans se touchent bord à bord.** Un cadre posé sur une arête déborde de
   la moitié de son épaisseur chez la voisine : les jauges de deux zones
   voisines se **soudent** en un seul trait qui n'appartient à personne. Le
   remède est de **rentrer** le cadre dans le pan (`transform: scale(.90)` sur
   la boîte de la forme — c'est le navigateur qui la calcule, la page ne lit
   toujours aucune géométrie).
2. **Le remplissage entre en concurrence avec la couleur de profil.** C'est ce
   qui tue R3 et R4 : la teinte obtenue **dépend du profil** — vert sur *dalle*
   (bleu froid) donne un vert-de-gris qui n'existe dans aucune des six teintes,
   vert sur *incliné* (ocre) donne un olive et vert sur *toit* (rouge) un brun,
   deux couleurs qui ressemblent à des profils. Une jauge de **contour** ne
   touche jamais la surface du pan : elle est hors du conflit.
3. **Trois emphases sur la zone visée.** Réglé en **teignant la jauge** au lieu
   de lui en ajouter une : la zone visée porte sa jauge en ocre (`--pl-anneau`)
   et plus épaisse, avec la lueur et le rebond déjà en place. Il n'y a jamais
   deux cerclages sur le même pan.
4. **0/4 et « pas de bloc ici » ne doivent pas se ressembler.** Une jauge à zéro
   ne peint rien — donc rien ne la distingue d'une zone effacée, au niveau du
   cadre. Le remède est une **piste** : un cadre faible, tracé sur les seules
   zones qui portent un compteur. 0/4 = piste complète, rien de peint ;
   pas de bloc = **aucun cadre du tout**.
5. **340 px de large.** Mesuré : le plan rend **2,39 px par unité**, le trait du
   cadre fait donc **3,8 px** d'épaisseur. C'est peu — et c'est pour ça que la
   jauge doit varier en **longueur** et pas en épaisseur : un quart de périmètre
   d'un pan de 15 unités fait **35,9 px** de long, et 36 px se voient à 3,8 px
   d'épaisseur. Le chiffre de la pastille, lui, fait **8,6 px** de corps dans un
   socle de **21,5 × 9,7 px** : lisible sur un écran à deux pixels par point,
   juste à la limite sur un écran à un.

### Ce qui reste à trancher

- **R1b ou R2** — le contour continu, ou le contour gradué en un segment par
  bloc. Le relevé d'Annonay rend la question moins vive qu'elle n'en a l'air :
  ses pans sont **carrés**, donc un quart de périmètre tombe pile sur une arête
  et une zone à quatre blocs dessine déjà *une arête par bloc*. R2 ne devient
  indispensable que sur les pans qui ne sont pas carrés (D fait 15 × 30, L
  15 × 25), où R1b coupe au milieu d'une arête.
- **Par quel coin la jauge commence.** La page **ne peut pas choisir** : choisir
  demanderait de savoir quel point est en haut à gauche, donc de lire la
  géométrie, ce que `plan.js` s'interdit (sa règle 3). La jauge part donc du
  **premier point du polygone, dans le sens du polygone** — et le coin de départ
  devient une **garantie du serveur** à écrire dans la spec plutôt qu'une
  coïncidence à espérer. Aujourd'hui `fiches.PLAN` énumère tous ses pans depuis
  le coin haut-gauche dans le sens horaire et `plan_public()` les recopie tels
  quels ; il n'y a **aucun test** qui l'exige, et c'est ce test-là qu'il faudra
  écrire avant de coder la jauge.
- **La piste** est un élément neuf sur le plan. Elle règle le piège 4, mais elle
  ajoute un huitième objet à un dessin qui en porte déjà sept. À valider à
  l'œil, sur le mur, pas sur une planche.

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
| A3 | Zone entièrement faite | « 4/4 », dans le vert de la réussite |
| A3b | Zone sans bloc de son circuit | **aucune pastille** non plus — un socle vide serait un fond posé pour ne rien porter |
| A4 | Zone sans bloc de son circuit | **aucun compteur** |
| A5 | Bloc crédité par la cascade | compté comme fait (§ 6) |
| A6 | Zone du circuit absente du plan | rien à dessiner, aucune erreur |
| A7 | Réussite enregistrée, mur ouvert | le compteur passe de « 1/2 » à « 2/2 » sans redessiner |
| A8 | Zone visée (on arrive depuis un bloc) | le compteur reste lisible pendant le rebond |
| A9 | Thème sombre | contraste tenu sur les six profils |
| A10 | Plan de format inconnu | pas de mur, donc pas de compteur — inchangé |
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
