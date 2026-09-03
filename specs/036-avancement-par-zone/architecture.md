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

```
x        = etiquette[0]                      (meme axe que la lettre)
y        = etiquette[1] + taille * 0.58      COMPTE_DESCENTE
fontSize = taille * min(0.42, 1/(0.58 * n))  COMPTE_ECHELLE, n = longueur du libelle
```

**Pourquoi sous la lettre et pas ailleurs.** Le centroïde est le seul point que
le serveur garantit à l'intérieur du pan ; s'en éloigner en diagonale (un coin,
une pastille sur un bord) demanderait la boîte englobante, donc de recopier côté
page une géométrie qui vit côté serveur — et de la voir diverger le jour où un
pan cesse d'être un rectangle. Sous la lettre, la seule chose qu'on consomme,
c'est la place que `taille` a **déjà** réservée.

**Le rétrécissement.** `min(0.42, 1/(0.58·n))` borne la largeur du libellé à une
fois `taille`, quel que soit le nombre de chiffres : « 1/4 » sort à sa taille
pleine, « 12/15 » rétrécit au lieu de déborder. Le 0,58 est la largeur d'un
chiffre tabulaire en fraction de sa taille — la même famille de constante que
`LARGEUR_CAPITALE` côté Python, et prise comme elle sur le pire glyphe.

**La limite connue, et ce qui la surveille.** Le compteur descend jusqu'à
`0,79 × taille` sous le centroïde. Comme `taille ≤ 0,97 × hauteur` du pan et
qu'elle est plafonnée à 9, tout pan d'au moins ~9,3 unités de haut le contient :
les dix-sept zones d'Annonay font 15 unités au minimum, la marge est de 0,4
unité. Un plan futur dessiné avec des pans plus petits ferait déborder le
chiffre sous son pan.

Ce n'est pas laissé à un commentaire : `tests/test_suivi.py` **relit les deux
constantes dans `plan.js`** et vérifie, pan par pan, que la boîte du compteur
tient dans le plan servi. Si quelqu'un change un ratio, redessine la salle avec
des pans minuscules ou touche à `taille_lettre`, le test rougit et nomme la
zone. C'est le même dispositif que `test_la_page_sait_dessiner_ce_que_le_serveur_envoie` :
un accord entre deux langages que rien d'autre ne confronterait.

## 4. Le style

Tout dans `resultats.html`, sous les règles `.plan` existantes, avec les
variables déjà posées pour le thème clair et `body.sombre` :

```css
.plan .compte-zone { ... paint-order: stroke fill; stroke: var(--pl-halo); }
.plan .compte-zone.compte-finie { fill: var(--ok); }
.plan g[data-zone]:not(.a-compte) .compte-zone { display: none; }
```

- Le **halo** (`paint-order: stroke fill`, `stroke: var(--pl-halo)`) est repris
  de la lettre, pour la raison qui l'y a mis : un chiffre posé sur un aplat de
  profil devient illisible sans lui. Les deux variables de halo existent déjà
  dans les deux thèmes ; **aucune nouvelle variable de couleur n'est créée**.
- `font-variant-numeric: tabular-nums`, comme partout où la page aligne des
  chiffres.
- La zone porte `a-compte` quand elle a un compteur : c'est ce qui cache le
  nœud vide sur les zones effacées, **en CSS et sans toucher au DOM**, donc sans
  que `decorer` ait à créer ou supprimer des nœuds.

**Ce qu'on ne touche pas.** `.sf-legende` et ses règles sont **hors limites** :
une PR parallèle (`fix/revue-du-03-09`) y remet la légende des couleurs de
profil. Aucune règle, aucune ligne de `peindreMur` concernant la légende n'est
modifiée par ce lot, et aucun bloc n'est inséré à côté d'elle.

## 5. Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/static/resultats/suivi.js` | `comptesDesZones`, `libelleCompte` ; `etatsDesZones` et `compteDeZone` en dérivent |
| `climbcontest/static/resultats/plan.js` | `COMPTE_ECHELLE`, `COMPTE_DESCENTE`, `tailleDuCompte` ; le nœud `compte-zone` dans `decrire` ; le 4ᵉ argument de `decorer` |
| `climbcontest/templates/resultats.html` | les règles `.plan .compte-zone` ; l'appel `decorer(..., comptes)` ; `estFait` dans `peindreFiche` |
| `tests/js/suivi.test.mjs` | les comptes, le libellé, l'invariant état ↔ compte |
| `tests/js/plan.test.mjs` | le nœud décrit, la décoration, la zone sans compteur, le rétrécissement |
| `tests/test_suivi.py` | le compteur tient dans chaque pan du plan servi |
| `tests/test_navigateur_fiche.py` | les compteurs lus dans un vrai navigateur, et leur mise à jour en direct |

**Aucun fichier Python de `climbcontest/` n'est modifié.** La charge servie
contient déjà `zone` et `etat` sur chaque bloc.
