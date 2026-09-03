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
| `decorer` | écrit son `textContent`, pose `a-compte` sur le groupe, `compte-finie` sur le texte |

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
03/09. Quatre ratios, et une règle qui les gouverne tous : **la pastille se
dimensionne sur la LETTRE, jamais sur son texte.**

```
cy       = etiquette[1] + taille * 0.60      COMPTE_DESCENTE
x        = etiquette[0]                      (meme axe que la lettre)
socle    = taille * 1.00  de large           PASTILLE_LARGEUR
           taille * 0.40 * 1.12 de haut      COMPTE_ECHELLE * PASTILLE_HAUTEUR
           rx = la demi-hauteur              (un stade, pas un rectangle)
fontSize = taille * min(0.40, 1/(0.58 * n))  COMPTE_ECHELLE, n = longueur du libelle
```

**Pourquoi la largeur est le point.** C'est ce qui avait fait écarter la pose B
à la première maquette : le socle y était calibré sur son **texte**, donc rien
ne le bornait, et il sortait du pan. Calibré sur `taille`, il hérite de la borne
que `fiches.taille_lettre` a déjà posée par la boîte du pan
(`taille ≤ 0,94 × largeur`). **Aucune géométrie n'est relue côté page** — c'était
l'objection de fond, et elle tombe.

**D'où sortent 0,60, 0,40 et 1,12.** Le budget vertical est ce qui reste **entre
le bas du glyphe de la lettre** et **le bas du pan**. Avec
`dominant-baseline: central`, une capitale grasse occupe ±0,36 × son corps ; le
bas du pan est à `0,833 × taille` (la demi-hauteur d'un pan de 15 unités
rapportée à une lettre plafonnée à 9). Le budget vaut donc
`0,833 − 0,36 = 0,473 × taille`, et **pas un centième de plus**. La pastille en
occupe `1,12 × 0,40 = 0,448`, centrée à 0,60 :

```
haut = 0.60 - 0.224 = 0.376  >=  0.36    elle ne mord pas la lettre
bas  = 0.60 + 0.224 = 0.824  <=  0.833   elle ne sort pas du pan
```

Les deux marges valent 0,145 et 0,084 × taille — soit 1,3 et 0,8 dixièmes
d'unité pour une lettre de 9. C'est mince, et il faut le dire : **ce n'est pas
une place qu'on peut reprendre pour grossir le chiffre.**

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

**Le rétrécissement, et ce qui ne rétrécit pas.** `min(0.40, 1/(0.58·n))` borne
la largeur du libellé à une fois `taille`, quel que soit le nombre de chiffres :
« 1/4 » sort à sa taille pleine, « 12/15 » rétrécit au lieu de déborder. Le 0,58
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

## 4. Le style

Tout dans `resultats.html`, sous les règles `.plan` existantes, avec les
variables déjà posées pour le thème clair et `body.sombre` :

```css
.plan .socle-compte { fill: var(--pl-halo); stroke: none; pointer-events: none; }
.plan g[data-zone]:not(.a-compte) .socle-compte { display: none; }
.plan .compte-zone { ... font-variant-numeric: tabular-nums; }
.plan .compte-zone.compte-finie { fill: var(--ok); }
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

**Aucun fichier Python de `climbcontest/` n'est modifié.** La charge servie
contient déjà `zone` et `etat` sur chaque bloc.
