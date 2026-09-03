# Architecture — 036, l'avancement par zone

## 1. Où ça se pose, et pourquoi là

Le mur de la fiche se rend en deux temps, et la spec 026 y tient beaucoup :

```
decrire(plan)   -> une description pure { tag, attrs, enfants }   (plan.js)
monter(desc)    -> le SVG, une fois par grimpeur                  (plan.js)
decorer(racine) -> les classes d'etat, a chaque repeinture        (plan.js)
```

Le compteur dépend **du grimpeur**, et `decrire()` ne connaît que le plan — il
est appelé une fois, avec une donnée commune à tout le monde. Il change **en
direct**, et `monter()` n'est rejoué que lorsqu'on change de grimpeur.

Le compteur est donc **décrit vide et rempli par `decorer()`** :

| Étape | Ce qu'elle fait du compteur |
| --- | --- |
| `decrire` | ajoute un `<text class="compte-zone">` **sans texte** dans le groupe de chaque zone, à une place et une taille déduites de `mur.etiquette` et `mur.taille` |
| `monter` | le monte comme le reste, sans rien décider |
| `decorer` | écrit son `textContent`, pose `a-compte` sur **toutes** les formes de la zone, et donne au vert de la pastille sa largeur |

C'est ce qui rend F5 vrai gratuitement : un rafraîchissement de la fiche
n'appelle que `decorer`, et le chiffre suit.

**Ce que ça ne casse pas.** Les trois règles de l'en-tête de `plan.js` tiennent :
le format est toujours vérifié avant de dessiner (le compteur est à l'intérieur
de `decrire`, qui rend `null` sur un format inconnu) ; tout ce qui décide reste
descriptible et testable sans navigateur ; et le lien avec les blocs passe
toujours **par `data-zone` seul** — `decorer` cherche `[data-zone]`, comme avant,
et le compteur est un enfant du groupe qu'il a déjà trouvé.

## 2. Le compte, calculé une seule fois

`suivi.js` porte déjà deux lectures du même compte, écrites deux fois :

```js
etatsDesZones(groupes)        // boucle 1 : total/faits par zone -> "finie"/"reste"
compteDeZone(groupes, zone)   // boucle 2 : total/faits d'UNE zone
```

Le lot en ajouterait une troisième. Trois additions du même nombre dans le même
fichier, c'est la divergence garantie — et c'est exactement ce que la § 6 de la
spec promet d'empêcher. On extrait donc **une** fonction, et les trois autres en
dérivent :

```js
comptesDesZones(groupes) -> { M: { total, faits, grimpes, credites }, ... }
etatsDesZones(groupes)   -> deduit de comptesDesZones (faits === total ? finie : reste)
compteDeZone(g, zone)    -> une entree de comptesDesZones (signature inchangee)
libelleCompte(compte)    -> "1/4", ou "" quand il n'y a rien a dire
```

`grimpes` et `credites` sont portés par le compte sans être affichés : ils ne
coûtent rien à compter, et c'est ce qui permettra au **panneau** de faire une
phrase le jour où la cascade servira (spec 036 § 6, dernier paragraphe) sans
rouvrir la mécanique.

`libelleCompte` rend `""` — et non `"0/0"` — pour une zone sans bloc du circuit :
c'est ce qui tient F2, et ça tient au même endroit que le reste.

Au passage, `peindreFiche` comptait ses blocs faits avec `b.etat !== "reste"`,
en clair et à la main, à côté d'un `estFait()` qui dit exactement ça. La ligne
passe par `estFait` : c'est le quatrième exemplaire de la même règle, et le
seul qui ne s'exprimait pas dans le vocabulaire du module.

## 3. La géométrie du compteur

Le serveur calcule déjà, par zone, **où poser la lettre** (`etiquette`, le
centroïde de surface) et **quelle taille elle peut faire** (`taille`, bornée par
la boîte du pan — `fiches.taille_lettre`). Le compteur se raccroche à ces deux
nombres, et à rien d'autre : il n'y a **aucune lecture de géométrie côté page**.

Le compteur est posé sur une **pastille** — la pose B, tranchée par Adrien le
03/09. Cinq ratios, et une règle qui les gouverne tous : **la pastille se
dimensionne sur la LETTRE, jamais sur son texte.**

```
lettre   = etiquette[1] - taille * 0.267     LETTRE_MONTEE  (elle MONTE)
cy       = etiquette[1] + taille * 0.523     COMPTE_DESCENTE
x        = etiquette[0]                      (meme axe que la lettre)
socle    = taille * 1.60  de large           PASTILLE_LARGEUR
           taille * 0.40 * 1.12 de haut      COMPTE_ECHELLE * PASTILLE_HAUTEUR
           rx = la demi-hauteur              (un stade, pas un rectangle)
jauge    = un rect de socle.largeur * part, decoupe DANS le socle
fontSize = taille * min(0.40, 1.6 * 0.86 / (0.58 * n))     n = longueur du libelle
```

**Pourquoi la largeur est le point.** C'est ce qui avait fait écarter la pose B
à la première maquette : le socle y était calibré sur son **texte**, donc rien
ne le bornait, et il sortait du pan. Calibré sur `taille`, il hérite de la borne
que `fiches.taille_lettre` a déjà posée par la boîte du pan
(`taille ≤ 0,94 × largeur`). **Aucune géométrie n'est relue côté page** — c'était
l'objection de fond, et elle tombe.

**D'où sortent 0,267 et 0,523 : les trois airs égaux.** Ce qu'on répartit,
c'est la hauteur du pan. Avec `dominant-baseline: central`, une capitale grasse
occupe ±0,36 × son corps, et son **halo** déborde de la moitié de son épaisseur
(0,24), donc la lettre occupe **±0,48**. Le bas du pan est à `0,833 × taille`
(la demi-hauteur d'un pan de 15 unités rapportée à une lettre plafonnée à 9).

```
le pan          2 x 0.833  =  1.666
la lettre       2 x 0.48   =  0.960   (halo compris)
la pastille                =  0.448   (0.40 x 1.12)
                              -----
il reste                      0.258   ->  TROIS AIRS DE 0.086
```

Les trois airs — au-dessus de la lettre, **entre la lettre et la pastille**,
sous la pastille — sont donc égaux. C'est la position **E**, choisie par Adrien
le 03/09 parmi six, sur `maquettes/pastille.html`. Les deux ratios de place en
découlent :

```
LETTRE_MONTEE   = 0.833 - 0.086 - 0.48   = 0.267
COMPTE_DESCENTE = 0.833 - 0.086 - 0.224  = 0.523
```

**⚠️ Ce qu'on a réglé là est un chevauchement, pas un espacement.** Avant, la
lettre restait sur son centroïde et la pastille descendait à 0,60 : le glyphe ne
la touchait pas (0,376 ≥ 0,36) mais **son halo la recouvrait de 0,104 × taille**
— près d'une unité de plan. « Là c'est trop proche » ne demandait donc pas de la
place en plus, mais de séparer deux objets qui se touchaient. Et la place n'était
pas où on l'aurait cherchée : **il ne restait que 0,009 × taille sous la
pastille** — un cinquième de pixel sur un téléphone — contre **0,353 au-dessus
de la lettre**. C'est pour ça que c'est la lettre qui monte.

Les trois marges valent maintenant 0,086 × taille chacune, soit **0,77 unité de
plan** pour une lettre de 9. C'est mince, et il faut le dire : **ce n'est pas une
place qu'on peut reprendre pour grossir le chiffre.**

**Ce que la pastille coûte, et ce qu'elle rapporte.** Le chiffre passe de 0,46 à
`0,40 × taille` : **13 % de corps en moins**. En échange il gagne un **fond** au
lieu d'un **halo**. Ce n'est pas un troc neutre : un halo est un contour découpé
sur la forme des glyphes, qui laisse passer l'aplat de profil entre les jambages
et se battait avec les six teintes ; une pastille est une surface pleine, et
c'est ce qu'il faut sous trois chiffres de trois pixels. Le compteur **n'a plus
de halo du tout** — garder les deux ferait un liseré clair autour de chaque
chiffre, sur un socle déjà clair.

**Pourquoi sous la lettre et pas ailleurs.** Le centroïde est le seul point que
le serveur garantit à l'intérieur du pan ; s'en éloigner en diagonale (un coin,
un socle sur un bord) demanderait la boîte englobante, donc de recopier côté
page une géométrie qui vit côté serveur — et de la voir diverger le jour où un
pan cesse d'être un rectangle. Sous la lettre, la seule chose qu'on consomme,
c'est la place que `taille` a **déjà** réservée.

**Le rétrécissement, et ce qui ne rétrécit pas.** La borne est la largeur de la
**pastille**, dont le libellé n'occupe que 86 % : « 1/4 » sort à sa taille
pleine, et depuis que le socle fait 1,6 fois la lettre, « 12/15 » aussi — c'est
le bénéfice direct de l'élargissement, et il était demandé (« repasse sa taille
à celle d'origine »). Le rétrécissement reste pour les libellés qu'aucun
élargissement raisonnable ne ferait tenir. Le 0,58
est la largeur d'un chiffre tabulaire en fraction de sa taille — la même famille
de constante que `LARGEUR_CAPITALE` côté Python, et prise comme elle sur le pire
glyphe. ⚠️ **La pastille, elle, se calcule sur le corps NOMINAL** et jamais sur
le corps réduit : c'est le chiffre qui rentre dans le socle, pas le socle qui
s'étire pour le chiffre. Sans ça, deux zones voisines porteraient deux pastilles
de tailles différentes pour dire la même chose.

**La limite connue, et ce qui la surveille.** La pastille descend jusqu'à
`0,824 × taille` sous le centroïde — soit 7,42 unités quand la lettre est à son
plafond de 9. Il faut donc un pan d'au moins **14,8 unités de haut**. Les
dix-sept zones d'Annonay en font 15 au minimum : la marge est de 0,08 unité, un
cinquième de pixel sur un téléphone.

Ce n'est pas laissé à un commentaire : `tests/test_suivi.py` **relit les quatre
constantes dans `plan.js`** et vérifie, pan par pan, que la boîte de la
**pastille** tient dans le plan servi — c'est elle le plus gros objet, mesurer
le seul chiffre ne suffit plus. Si quelqu'un change un ratio ou touche à
`taille_lettre`, le test rougit et nomme la zone. C'est le même dispositif que
`test_la_page_sait_dessiner_ce_que_le_serveur_envoie` : un accord entre deux
langages que rien d'autre ne confronterait.

**Ce que ce test ne couvre pas, et le vrai remède.** Il vérifie le plan **servi
par le test**, donc le plan d'usine. Depuis la spec 029, Adrien peut en
enregistrer un autre depuis la console ; s'il y dessine des pans de douze
unités, la pastille sortira sous son pan et aucun test ne le dira. Le remède
propre n'est pas une constante mieux choisie — il n'en existe aucune qui tienne
dans un pan arbitrairement bas — c'est de faire calculer la place du compteur
**par le serveur**, là où la boîte du pan est connue, exactement comme
`taille_lettre` calcule celle de la lettre. Ça change la forme de
`plan_public()`, donc ça demande d'incrémenter `FORMAT_PLAN` : c'est un lot à
part, pas une ligne à glisser dans celui-ci. En attendant, ce qui protège, c'est
que le seul plan qui existe fait des pans de 15.

## 3 bis. La pastille qui se remplit

Le compteur dit **combien** ; la pastille dit **quelle part**. Les deux dérivent
du même `comptesDesZones`, donc ils ne peuvent pas se contredire — c'est la
même règle que la § 2, appliquée à un troisième affichage.

### Trois couches, et pourquoi le compteur est monté d'un cran

```
<defs>                une decoupe par pastille (clipPath)
g[data-zone] x17      le pan : forme, trame, lettre
g.cadres-zone         le cadre d'etat de chaque zone
g.compteurs-zone      la pastille, son vert et son chiffre
```

En SVG l'ordre de peinture est l'ordre du document — il n'y a pas de `z-index`.
Les cadres passaient déjà **après tous les murs** : un cadre dessiné dans le
groupe de sa zone se fait rogner sur les arêtes qu'elle partage avec sa voisine,
et le relevé d'Annonay n'est presque que ça.

**Le compteur, lui, a dû monter.** Il vivait dans le groupe de sa zone, donc
*sous* les cadres. Tant que la pastille faisait une fois la lettre, elle ne les
croisait pas ; à **1,6 fois**, elle fait 14,4 unités dans un pan de 15 quand
l'intérieur du cadre en fait 13,4. Peinte dessous, elle se ferait couper **à ses
deux extrémités** — justement là où le vert dit où il s'arrête. Elle passe donc
devant, et c'est le cadre qui porte l'encoche : un décor constant, présent sur
toutes les zones comptées, plutôt qu'une jauge tronquée.

Le groupe du compteur reprend le `data-zone` **et le centre de rotation** de son
pan : il reçoit les mêmes classes d'état, et **rebondit avec lui**. Trois
conséquences à ne pas perdre :

- `decorer` pose `a-compte` sur **toutes** les formes de la zone, et plus
  seulement sur celle qui porte le chiffre : c'est cette classe qui allume la
  pastille et son vert **ensemble** ;
- la couche des compteurs est `pointer-events: none`, et les clics ne sont
  câblés que sur les enfants directs du SVG (`:scope > g[data-zone]`) — sans ça,
  dix-sept écouteurs morts se poseraient sur les compteurs ;
- le redémarrage d'animation de `resultats.html` passe **au pluriel** : la zone
  visée, c'est maintenant deux nœuds, et redémarrer le premier seul les
  désynchronise dès la deuxième visite d'une même zone.

### Le vert : un rectangle franc, découpé dans le socle

```
<rect class="socle-compte"   x y w h rx>          le fond
<rect class="remplit-compte" x y (w * part) h     la jauge
      clip-path="url(#plan-socle-Z)" data-plein=w>
<text class="compte-zone">                        le chiffre
```

**Pourquoi une découpe et pas un `rx`.** Un rectangle arrondi de son côté ferait
une petite pastille **dans** la grande : on lirait deux objets. Découpé dans la
forme du socle, le vert en épouse le bord arrondi à gauche et **se coupe net à
droite** — c'est un niveau, et ça se lit comme une proportion. Choisi sur pièce
le 03/09 (`maquettes/pastille.html`, § 4).

**Pourquoi la largeur est posée par `decorer` et pas par `decrire`.** Comme le
chiffre : la part dépend **du grimpeur**, et le dessin est le même pour tout le
monde. C'est ce qui rend la jauge « en direct » sans rien reconstruire — une
réussite qui arrive pendant qu'on regarde le plan ne repasse que par la
décoration. `data-plein` porte la largeur du socle : c'est la seule chose dont
`decorer` a besoin pour en peindre une fraction, et **elle ne relit aucune
géométrie**.

**La remise à zéro n'est pas optionnelle.** Le dessin persiste d'une repeinture
à l'autre ; sans elle, la pastille d'un grimpeur resterait à moitié pleine sur
la fiche du suivant. `decorer` réécrit donc la largeur **à chaque passage**, y
compris à zéro.

### Ce que la couleur coûte

Le vert est **franc** (62 % de `--ok`), et le chiffre est posé dessus. C'est le
seul arbitrage du lot, et il se voit : plus le vert est fort, moins le chiffre
se détache. Trois forces ont été rendues côte à côte, sur le vrai plan, et c'est
celle-là qui a été choisie.

⚠️ **Le chiffre d'une zone terminée ne vire plus au vert.** Il le faisait quand
la pastille était un fond neutre. Sur une pastille **pleine** de vert, vert sur
vert ne se lit pas : deux signaux se disputeraient le même pixel. C'est le
remplissage qui dit « terminée », et le chiffre reste à l'encre — la classe
`compte-finie` disparaît avec sa règle, plutôt que de rester sans effet.

## 4. Le style

Tout dans `resultats.html`, sous les règles `.plan` existantes, avec les
variables déjà posées pour le thème clair et `body.sombre` :

```css
.plan .socle-compte { fill: var(--pl-halo); stroke: none; pointer-events: none; }
.plan g[data-zone]:not(.a-compte) .socle-compte { display: none; }
.plan .compte-zone { ... font-variant-numeric: tabular-nums; }
.plan g[data-zone]:not(.a-compte) .remplit-compte { display: none; }
.plan .remplit-compte { fill: color-mix(in srgb, var(--ok) 62%, transparent); }
.plan .compteurs-zone { pointer-events: none; }
```

- La **pastille** prend `var(--pl-halo)`, la couleur qui servait au halo de la
  lettre. Elle existe déjà dans les deux thèmes ; **aucune nouvelle variable de
  couleur n'est créée**.
- `font-variant-numeric: tabular-nums`, comme partout où la page aligne des
  chiffres.
- La zone porte `a-compte` quand elle a un compteur. Le **texte** vide ne peint
  déjà rien ; c'est la **pastille** qu'il faut retirer, sans quoi dix-sept
  socles clairs se poseraient sur des zones où le grimpeur n'a rien à faire.
  Retrait **en CSS et sans toucher au DOM**, donc sans que `decorer` ait à créer
  ou supprimer des nœuds.

**Ce qu'on ne touche pas.** `.sf-legende` et ses règles sont **hors limites** :
une PR parallèle (`fix/revue-du-03-09`) y remet la légende des couleurs de
profil. Aucune règle, aucune ligne de `peindreMur` concernant la légende n'est
modifiée par ce lot, et aucun bloc n'est inséré à côté d'elle.

## 5. Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/static/resultats/suivi.js` | `comptesDesZones`, `libelleCompte` ; `etatsDesZones` et `compteDeZone` en dérivent |
| `climbcontest/static/resultats/plan.js` | `COMPTE_ECHELLE`, `COMPTE_DESCENTE`, `PASTILLE_HAUTEUR`, `PASTILLE_LARGEUR`, `tailleDuCompte` ; les nœuds `socle-compte` et `compte-zone` dans `decrire` ; le 4ᵉ argument de `decorer` |
| `climbcontest/templates/resultats.html` | les règles `.plan .socle-compte` et `.plan .compte-zone` ; l'appel `decorer(..., comptes)` ; `estFait` dans `peindreFiche` |
| `tests/js/suivi.test.mjs` | les comptes, le libellé, l'invariant état ↔ compte |
| `tests/js/plan.test.mjs` | le nœud décrit, la décoration, la zone sans compteur, le rétrécissement |
| `tests/test_suivi.py` | la **pastille** tient dans chaque pan du plan servi, et le chiffre tient dans la pastille |
| `tests/test_navigateur_fiche.py` | les compteurs lus dans un vrai navigateur, et leur mise à jour en direct |

Et pour la pastille qui se remplit (§ 3 bis) :

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/static/resultats/plan.js` | `LETTRE_MONTEE`, `partFaite` ; `PASTILLE_LARGEUR` à 1,6 et `COMPTE_DESCENTE` à 0,523 ; la lettre monte, les découpes dans `<defs>`, la couche `compteurs-zone` et le `remplit-compte` ; `decorer` pose la largeur du vert |
| `climbcontest/templates/resultats.html` | `.remplit-compte`, la couche des compteurs et son rebond sans lueur, le retrait de `.compte-finie`, le clic câblé sur les seuls pans, le redémarrage d'animation au pluriel |
| `tests/js/plan.test.mjs` | la part faite, la jauge décrite vide et découpée, l'ordre des couches, la remise à zéro, la lettre montée et les trois airs égaux |
| `tests/test_suivi.py` | le halo qui ne sort pas par le haut, la pastille qui ne sort ni par le bas ni sur les côtés, et les deux qui ne se touchent pas |
| `tests/test_navigateur_fiche.py` | le vert mesuré dans un vrai navigateur : sa part, sa découpe, sa boîte, l'ordre de peinture, et le cadre resté au tout-ou-rien |
| `tests/test_coherence_console_ecran.py` | la sonde qui comptait les `g[data-zone]` compte les **pans** |
| `specs/036-avancement-par-zone/maquettes/pastille.html` | le rendu réel des deux lectures, les trois réglages et les six positions |

**Aucun fichier Python de `climbcontest/` n'est modifié.** La charge servie
contient déjà `zone` et `etat` sur chaque bloc.
