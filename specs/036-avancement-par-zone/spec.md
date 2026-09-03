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
  compteur porte le même halo que la lettre de la zone, pour la même raison —
  sans lui, un chiffre posé sur une trame devient illisible.
- **Sur un téléphone de 390 px de large comme sur un écran de portable.** Le
  compteur est dimensionné **en proportion de la lettre de la zone**
  (`mur.taille`, calculée par le serveur pour tenir dans le pan) : il grandit et
  rétrécit avec elle. Un libellé plus long — « 12/15 » — rétrécit au lieu de
  déborder. Ce qu'il suppose, en revanche, ce sont des pans d'au moins ~14,6
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

## 2 bis. Ce que la maquette a tranché

`maquettes/compteurs.html` — le vrai relevé d'Annonay, la vraie géométrie
(polygones, place et taille des lettres sortis de `fiches.plan_pour(set())`), un
circuit simulé de 27 blocs sur six zones : une zone intacte (0/2), une entamée
(1/4), une terminée (3/3), une à bloc unique (1/1) et une à deux chiffres de
chaque côté (10/12) — celle qui dit si le compteur rétrécit ou s'il déborde.
Onze zones sans bloc du circuit, qui ne doivent rien porter.

| Essai | Verdict |
| --- | --- |
| **A — le chiffre sous la lettre** | **Retenu.** Un nœud de plus, et rien d'autre ne bouge |
| A2 — la lettre rend un cran au chiffre | Écarté. 13 % de corps gagnés, mais la lettre d'un pan changerait de taille **selon le circuit du grimpeur** : deux téléphones côte à côte ne montreraient plus la même salle. Et il faudrait poser une transformation sur la lettre, que la fiche **papier** dessine aussi |
| B — la pastille (socle arrondi) | Écarté. Le socle a une largeur à lui, que rien ne borne : sur le relevé réel il mord la lettre au-dessus et sort du pan en dessous. Le dimensionner demanderait la boîte du pan, donc de recopier côté page une géométrie qui vit côté serveur |
| C — l'anneau de progression | Écarté. L'anneau se confond avec le contour vert de « zone terminée » et avec l'anneau ocre de la zone visée : trois cercles pour trois choses différentes |

Le chiffre retenu fait `0,46 × taille` de la lettre, posé à `0,59 × taille` sous
elle, avec le halo de la lettre. Ce sont les deux plus grandes valeurs qui
tiennent à la fois sous la lettre et dans le pan — le calcul est dans
`architecture.md` § 3.

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
