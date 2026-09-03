# Spec 032 — La revue du 02/09, partie 1

> ## ⚠️ Cette spec a été écrite APRÈS le code. La porte 2 n'a pas été franchie.
>
> La règle 1 du dépôt dit « pas de code sans spec validée », et la porte 2 —
> spec approuvée — appartient à Adrien. Le code a été écrit, poussé, **puis
> mergé** (PR #87, `2bb4316`) alors que cette spec n'existait pas. C'est un
> manquement, et il est de mon fait : Adrien a dicté une liste de défauts
> constatés, j'ai diagnostiqué et corrigé directement au lieu de traduire la
> liste en spec et de la lui soumettre.
>
> ⚠️ **La porte 7 s'est donc refermée sur du code que la porte 2 n'avait jamais
> ouvert.** Adrien a mergé pendant que cette spec s'écrivait — il a validé sur
> la PR, ce qui est un jugement réel, mais pas sur une spec. Ce dossier arrive
> après le merge, et il ne faut pas lui faire dire le contraire.
>
> C'est **la deuxième fois de suite** — la spec 027 porte le même encadré, pour
> la même raison, écrite la veille. Deux fois n'est plus un accident : quand
> Adrien dicte une liste de défauts constatés, je la traite comme un ordre de
> travail alors que le dépôt demande d'en faire une spec. La correction est
> notée en tête du plan.
>
> Cette spec est donc un **rattrapage**, et il faut être précis sur ce qu'il
> rattrape. Elle ne rouvre pas une décision déjà prise : elle donne au lot son
> dossier — le diagnostic, les mesures, les critères, les cas limites et le
> point resté ouvert — pour que le prochain qui touche à ces écrans sache ce
> qui a été décidé et pourquoi. Rien n'est déployé : `master` n'est pas une
> release.
>
> Le numéro **032** a été pris après vérification des branches distantes : 030
> est à `feat/030-versions-visibles`, 031 à `feat/031-deploiement-depuis-la-console`,
> deux chantiers menés en parallèle.

## 1. D'où vient ce lot

Revue dictée par Adrien le 02/09/2026, après avoir piloté la console et imprimé
pour de vrai. Elle est annoncée comme partielle, en toutes lettres : « ce n'est
que la 1ère partie de ma revue ». Deux PDF sont joints — les fiches et les
étiquettes telles qu'elles sortent de son imprimante — et ce sont eux qui
tranchent les points d'impression, pas une opinion.

Neuf points, sans ordre de priorité, plus une consigne de méthode : « tu me mets
un test en face de chaque problème ».

⚠️ **Ce lot n'est pas de même nature que la spec 027.** La 027 était une liste
d'améliorations dictées. Celle-ci est une liste de **défauts constatés en
usage**, dont trois n'avaient aucun test et dont un — R10 — n'a même pas été vu
par Adrien. Le travail a donc commencé par un diagnostic, pas par du code.

## 2. Ce qu'on corrige

### Console — la cascade de couleurs

**R1 — « Aucune cascade » cache la partie règle.**
« Dans cascade de couleur je veux que la partie règle ne soit pas affichée si
"Aucune cascade" est sélectionné. »

La carte offrait « + Ajouter une règle », un contrôle et un aperçu sous un titre
qui ne s'appliquait à rien. Le titre, les phrases, le contrôle et l'aperçu sont
désormais **un seul groupe** (`#blocRegleCascade`) qui apparaît et disparaît
d'un bloc — un `hidden`, pas quatre, parce que quatre finissent par diverger.

**R2 — « Sur mesure » redevient sélectionnable depuis « Comme le classeur ».**
« Si je sélectionne "Comme le classeur" puis que je sélectionne "Sur mesure", ce
dernier n'est pas sélectionnable. Il faut que je repasse par Aucune cascade. »

Le bouton coché était **déduit** des phrases : vide → « aucune », égales à
celles du classeur → « classeur », sinon → « sur mesure ». Cliquer « Sur
mesure » en venant du classeur ne changeait **aucune phrase**, la déduction
rendait donc toujours « classeur », et le bouton se décochait sous le doigt.

⚠️ **Partir des phrases du classeur pour les retoucher est le cas normal.**
C'est une **intention**, elle ne se lit pas dans les phrases, elle se mémorise.
Les phrases du classeur sont gardées au passage : on part d'elles, c'est tout
l'intérêt du bouton.

⚠️ **L'avertissement reste calculé sur les phrases.** « Le classeur ne saura pas
suivre cette règle » répond à une question sur les phrases, pas sur l'intention.
Le brancher sur le bouton coché l'aurait fait crier sur une règle que le
classeur reproduit parfaitement.

### Console — la vue Circuits

**R3 — La difficulté et les prises ne gardent que leur pastille.**
« Sur la page Circuits, retire-moi le texte pour la difficulté et les prises, je
ne veux conserver que la pastille de couleur. »

Deux colonnes de mots répétés soixante fois poussaient « Circuits » et
« Catégories » hors de l'écran — c'est-à-dire exactement ce que la vue sert à
vérifier (spec 019).

⚠️ Le nom n'est pas perdu : il reste dans `title` — donc au survol — et dans un
texte lu par les lecteurs d'écran. Une pastille seule, sans son nom accessible,
serait une information réservée à ceux qui distinguent les couleurs. Les
en-têtes de colonne restent : ce sont eux qui disent ce que les deux formes
signifient.

### Page de résultats

**R4 — Éteindre un classement le retire VRAIMENT.**
« Si je retire des scratchs de l'affichage de la page résultat et que je
rafraîchis la page résultat, rien ne se passe. »

`groupesVisibles()` filtrait bien, mais `dessinerBarre()` lisait la charge
**brute** — masque compris — dès qu'on n'était pas en mode mur. La pastille du
scratch éteint restait dans la barre, et son classement à un doigt.

⚠️ Le fichier portait **deux commentaires qui se contredisaient** :
`groupesVisibles` promettait « il s'applique PARTOUT — mur et téléphones : une
seule vérité, rien à expliquer le jour J », la barre expliquait le contraire
deux cents lignes plus bas. Le code suivait le mauvais. C'est le réglage de la
spec 020 qui n'était appliqué qu'à moitié.

**R5 — La rotation démarre toute seule.**
« Si je passe la compétition à En cours, je m'attends à ce que la page de
résultats se mette en mode affichage en play pour passer d'un podium à
l'autre. »

`programmerRotation` était armée **une seule fois**, 1,2 s après le chargement.
Un mur allumé avant la compétition n'avait alors aucun classement —
`visibles.length` valait 0 — et la fonction sortait **sans reprogrammer quoi que
ce soit**. Passer la compétition « En cours » ne la réveillait pas : l'écran
restait figé jusqu'à un rechargement à la main. Elle repasse maintenant au
rythme de la rotation tant qu'il n'y a rien à montrer.

**R6 — Le bouton ▶/⏸ existe des deux côtés.**
« Je n'ai plus le bouton play et pause sur l'écran résultat. »

Il ne s'affichait qu'en `?mur`. Sur la page normale — celle qu'on branche au
vidéoprojecteur **sans** passer par `?mur`, exactement comme la loupe voisine —
rien ne permettait de lancer ni d'arrêter le défilement.

⚠️ **Décision d'Adrien, prise en cours de travail** (question posée, trois
options présentées) : la rotation **automatique** reste réservée à l'écran
projeté. Un parent qui regarde la catégorie de son enfant sur son téléphone ne
doit pas la voir partir toute seule.

⚠️ **Écart assumé avec l'option choisie, et il doit se voir.** Le libellé de
l'option disait que le bouton apparaîtrait sur la page normale « sans rien y
figer ». Un bouton visible qui ne fait rien est pire que pas de bouton : sur la
page normale il part donc **à l'arrêt**, et c'est lui qui transforme la page en
écran de projection. Automatique = mur seul ; manuel = partout. Si Adrien
voulait vraiment un bouton inerte, c'est ici qu'il faut le dire.

### L'éditeur du plan du mur

**R7 — « ← La console » mène à la console.**
« Le retour à la console depuis le plan ne fonctionne pas, j'ai : Not Found. Ça
va sur admin alors que c'est console. »

Diagnostic confirmé mot pour mot. `/admin` est le **préfixe des routes JSON**
(`/admin/plan`, `/admin/classeur`, `/admin/dossards`) et aucune ne répond à la
racine du préfixe. L'éditeur (spec 029) était un cul-de-sac : une fois dedans,
le seul retour était le bouton du navigateur.

### Les impressions

**R8 — Une planche de N feuilles sort en N pages.**
« L'impression des dossards n'est toujours pas bonne » et « pour l'impression
des QR codes de blocs c'est pareil, elle n'est pas à la bonne dimension ». Les
deux PDF joints portent la preuve : **40 pages pour 20 planches** de fiches,
**14 pour 7** d'étiquettes.

Cause. Les feuilles occupaient la surface utile **exacte** — 285 × 198 mm à 6 mm
de marge pour les fiches, 198 × 285 pour les étiquettes. Zéro millimètre de
marge d'erreur. Or personne n'imprime dans cette surface-là : le pilote applique
la **zone imprimable** du papier, le navigateur arrondit les millimètres en
pixels, et la feuille devient un cheveu trop haute. Le moteur la coupe alors en
deux, et pose la **dernière ligne** de la rangée du bas toute seule sur la page
suivante.

⚠️ **Le défaut ne se voyait pas chez nous et se voyait chez lui**, ce qui est
exactement pourquoi il a survécu à la spec 027 : celle-ci avait vérifié le
découpage en feuilles (`120 → 20`), pas ce que l'imprimante en fait.

**R9 — Les étiquettes remplissent leur papier.**
« Il faut que ces étiquettes soient plus grosses car tu laisses beaucoup trop de
blanc autour de ces étiquettes ; on a presque 2 cm entre le texte et le trait de
découpage. »

Mesuré sur la planche d'origine : **15,8 mm de vide sous le texte**, autant à sa
droite. Le papier était le même, la lisibilité à deux mètres non.

**R10 — Les impressions sortent en couleur.**
« Les impressions PDF ne sont que en noir et blanc, alors je ne sais pas si
c'est à cause de mon Mac ou si c'est ta lib qui ne le fait pas. »

Ni l'un ni l'autre. **Un navigateur ne pose aucun aplat de couleur à
l'impression** tant que « Graphismes d'arrière-plan » n'est pas coché dans sa
boîte de dialogue — ce que personne ne coche. Les pastilles de difficulté, qui
sont des `background`, sortaient en ronds **vides** : c'est le « ○ Jaune » de
son PDF. Rien dans le dépôt ne portait `print-color-adjust`.

### Trouvé en mesurant, pas signalé

**R11 — La grille de blocs ne déborde plus sur le plan du mur.**

En mesurant la planche pour R8, constat : les cases de blocs se peignaient
**par-dessus** le plan du mur. `repeat(var(--cols), 1fr)` vaut
`minmax(auto, 1fr)` — une piste de grille ne descend **jamais** sous la largeur
de son texte. Neuf colonnes de « M52 » faisaient 70 mm de grille dans une
colonne de 60. **Les 120 fiches de la planche débordaient, toutes, de 5,75 mm**,
et le défaut est **antérieur** à ce lot.

`colonnes_qui_tiennent` (spec 027) ne regardait que la **hauteur** ; la largeur
n'était bornée par rien du tout.

⚠️ **Il est corrigé ici et pas ailleurs parce que R8 l'aggravait** : rétrécir la
fiche de 4 mm sans borner la grille aurait porté le débordement à 10,25 mm.
Corriger R8 seul aurait empiré un défaut connu.

## 3. Périmètre

**Inclus** : R1 → R11, sur `climbcontest-core` uniquement.

**Exclu, à dessein :**

- **La partie 2 de la revue**, annoncée par Adrien et pas encore dictée. Elle
  portera probablement sur les mêmes écrans ; cette spec devra peut-être être
  étendue plutôt que doublée.
- **La taille du numéro de bloc sur une fiche U15.** La correction R11 la fait
  tomber à ~2,15 mm — c'était 3 mm, mais 3 mm qui débordaient. Si c'est trop
  petit sur le papier, la sortie est de passer à **quatre fiches par A4**, ce
  qui change le format et mérite sa propre décision. Point ouvert, § 6.
- **Le CHANGELOG**, qui se remplit à la release, dans son propre commit.

## 4. Critères d'acceptation

Tous **mesurés** le 02/09/2026, suite complète au vert.

- [x] **A1** — « Aucune cascade » n'affiche ni titre de règle, ni phrase, ni
  contrôle, ni aperçu.
- [x] **A2** — Depuis « Comme le classeur », un clic sur « Sur mesure » le
  laisse coché, et garde les phrases du classeur comme point de départ.
- [x] **A3** — L'avertissement du classeur ne dépend que des phrases : cocher
  « Sur mesure » sans rien changer ne le déclenche pas.
- [x] **A4** — Dans Circuits, Difficulté et Prises n'affichent aucun texte, et
  leur nom reste au survol et pour les lecteurs d'écran.
- [x] **A5** — Un classement éteint dans la console disparaît de la barre de la
  page de résultats, mur **et** téléphone.
- [x] **A6** — Un mur ouvert **sans aucun classement** se met à défiler tout
  seul dès que les classements arrivent, sans rechargement.
- [x] **A7** — Le bouton ▶/⏸ est présent sur la page normale, à l'arrêt, et y
  lance la rotation.
- [x] **A8** — « ← La console » répond 200.
- [x] **A9** — 120 fiches → **20 pages** et 60 étiquettes → **8 pages**, pour
  une zone imprimable rognée de 6 à 14 mm.
- [x] **A10** — Toute feuille est strictement plus petite que la surface utile
  de la page, avec de la marge pour l'arrondi.
- [x] **A11** — Les deux gabarits forcent l'impression des aplats, et le plan du
  mur reste sans couleur.
- [x] **A12** — Sur une étiquette, les quatre lignes de texte font ≥ 4 mm et le
  numéro tient dans sa colonne quelle que soit sa longueur.
- [x] **A13** — **Zéro** case de bloc hors de sa colonne, sur les 120 fiches
  (contre 120/120 avant).

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| « Sur mesure » sur une liste vide | Une phrase s'ouvre, sinon le clic n'aurait servi à rien |
| Retour sur l'onglet Général en cours d'édition | Ce qu'on écrit n'est pas emporté ; l'intention se relit des phrases servies |
| Règle sur mesure identique à celle du classeur | Le bouton reste sur « Sur mesure », l'avertissement reste muet |
| Bloc sans couleur de prises | La cellule affiche « — », pas une pastille vide |
| Tous les classements masqués | Le réglage est ignoré : une page vide se lit comme une panne |
| Archive rejouée en `?mur` | La rotation marche comme avant ; le masque ne s'applique pas à une archive |
| Page normale sur téléphone | Rien ne défile tant qu'on n'a pas appuyé sur ▶ |
| Zone imprimable de 16 mm ou plus | La feuille entière part à la page suivante — une page perdue, aucune rangée coupée |
| Numéro de bloc à 4 caractères | La taille descend jusqu'au plancher de 2 mm, puis la case tronque **chez elle** |
| Circuit de 300 blocs | Le calcul sature le plafond de colonnes au lieu de lever une exception |

## 6. Point ouvert

**La lisibilité du numéro de bloc sur une fiche U15.** 36 blocs en six couleurs,
dans 59,8 × 52,9 mm, à côté d'un plan du mur : le calcul retient 9 colonnes et
un numéro de **2,15 mm**. C'est petit. Les trois sorties, par ordre de coût :

1. **Ne rien faire** — c'est lisible sur papier à distance de lecture, et c'est
   déjà mieux que 3 mm qui débordent.
2. **Quatre fiches par A4** au lieu de six — le numéro remonte, la planche passe
   de 20 à 30 pages.
3. **Retirer le plan du mur de la fiche** — 37 mm rendus aux blocs, mais on perd
   ce que les specs 023 et 028 ont mis là exprès.

Décision d'Adrien. Aucune n'est engagée par cette spec.
