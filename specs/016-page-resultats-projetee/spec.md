# Spec 016 — La page de résultats, faite pour être projetée

> **Statut : codée, en attente de relecture (31/08/2026).** Maquettes montrées,
> direction **A** retenue par Adrien, avec défilement doux du reste du plateau.
> Demandée par Adrien le 31/08/2026 : « elle est trop moche et pas assez
> wahou », « quand des participants changent de place il faut une animation »,
> « ça va être projeté via un vidéoprojecteur, il faut que ce soit bien
> visible », « le fond noir je ne suis pas certain que ce soit une bonne idée »,
> « un mode où on tourne sur toutes les catégories ».

## 1. Le constat, mesuré

La page de la spec 006 fonctionne : elle se rafraîchit, elle survit à une panne
réseau, elle est lisible sur un téléphone. Projetée, elle rate sa cible.

**Capture faite le 31/08 à 1920×1080, mode `?mur`, sur 24 grimpeurs en
« U11 F » :**

| Ce qu'on voit | Ce qu'il faudrait |
| --- | --- |
| **6 grimpeurs et demi** — les 17 autres sont sous la ligne de flottaison, et personne ne va faire défiler un écran accroché en hauteur | La catégorie entière, d'un coup d'œil |
| Un fond quasi noir (`#0E1116`) | Un vidéoprojecteur **émet** la lumière : le noir, c'est l'absence d'image. Dans une salle éclairée, un fond sombre donne un gris sale et un contraste effondré |
| Aucun mouvement quand un rang change : la liste est **détruite et reconstruite** à chaque rafraîchissement (`el.liste.innerHTML = ""`) | Un grimpeur qui double quelqu'un doit **se voir** bouger |
| La rotation des catégories existe (20 s en mode `?mur`) mais rien ne l'annonce ni ne l'indique | Une rotation visible, avec ce qui vient ensuite |
| ~40 % de la largeur est du vide entre le nom et le score | De la place pour le reste du plateau |

Le mode `?mur` **existe déjà** et fait déjà tourner les catégories — c'est écrit
dans la spec 006. Qu'il faille le redemander est en soi le constat : rien à
l'écran ne dit qu'il existe, et le résultat projeté ne donne pas envie de le
laisser affiché.

## 2. Les deux usages, inchangés

| Mode | Pour qui | Contrainte dominante |
| --- | --- | --- |
| **Mur** (`/?mur`) | l'écran projeté dans la salle | lu **à 8 mètres**, aucune interaction, tourne seul toute la journée |
| **Spectateur** (`/`) | les téléphones des parents | tenu à bout de bras, recherche par nom ou dossard |

Ce sont deux mises en page, pas deux pages : mêmes données, même code, un
`body.mur` qui bascule. C'est ce qui fait qu'elles ne divergent pas.

## 3. Ce qu'on fait

### 3.1 Tout le plateau tient à l'écran

Une catégorie de 25 grimpeurs doit être **entièrement visible**. À 1080p, une
liste d'une colonne donne 36 px par ligne : illisible à 8 m. La mise en page
passe donc en **colonnes**, et la taille du texte s'adapte au nombre de
grimpeurs — jamais l'inverse.

Au-delà de ce qui tient (catégories exceptionnellement grandes), la page
**pagine** au lieu de rogner : « 1/2 », puis « 2/2 », dans le rythme de la
rotation. On ne coupe jamais un classement en silence.

### 3.2 Un changement de place se voit

Quand un rang change entre deux rafraîchissements :

- la ligne **glisse** de son ancienne position à la nouvelle (FLIP, ~600 ms) ;
- elle porte une **flèche ▲ / ▼ avec le nombre de places** gagnées ou perdues,
  affichée quelques secondes puis effacée ;
- celui qui **monte** reçoit une pulsation courte de la couleur de sa
  catégorie ; celui qui prend la **première place** en reçoit une plus marquée.

Techniquement, ça impose une seule chose, mais elle est structurante : les
lignes deviennent **persistantes et identifiées par participant** (`data-id`),
réutilisées d'un rendu à l'autre. On ne peut pas animer ce qu'on détruit.

⚠️ **Un mouvement doit rester lisible, pas spectaculaire.** Une réussite
enregistrée en retard peut faire *baisser* le score d'un grimpeur qui n'a rien
fait (la valeur d'un bloc dépend du nombre de grimpeurs qui l'ont réussi) :
c'est normal, et c'est déjà écrit dans la spec 006. Une animation brutale ferait
lire ce cas comme un bug.

### 3.3 La rotation devient un vrai mode

- Toutes les catégories **et** les circuits (« scratch ») défilent en boucle.
- Une **barre de progression** montre le temps restant sur la catégorie
  affichée, et le nom de **la suivante** est annoncé.
- La transition entre deux catégories est une **traversée**, pas un clignement :
  la couleur de la catégorie change, le titre glisse.
- Le classement **club** entre dans la rotation, en dernier.
- Durée par écran : **20 s** par défaut, réglable par l'adresse
  (`?mur&rotation=30`).

### 3.4 Le fond n'est plus noir

Le défaut devient **clair**. La raison est physique, pas esthétique : un
vidéoprojecteur ajoute de la lumière sur un mur, il n'en retire pas. Un fond
sombre n'est pas « sombre », c'est **du mur non éclairé** — et dans une salle
d'escalade où l'on ne peut pas éteindre les lumières, le contraste s'effondre.

Le mode sombre reste atteignable (`?mur&sombre`) pour une salle réellement dans
le noir, ou un écran LED plutôt qu'un projecteur.

### 3.5 Ce qui fait le « wahou », sans nuire à la lecture

- Un **podium** traité comme un podium : or, argent, bronze, plus grands que le
  reste, avec le nombre de blocs en évidence.
- La **couleur de circuit** portée franchement, pas en filet de 4 px.
- Le **logo du club** dans le bandeau, et le nom de la compétition en grand.
- Un **compteur discret** de ce qui se passe : nombre de réussites enregistrées
  depuis le début, qui monte dans la journée.
- Des chiffres **tabulaires** qui ne dansent pas quand ils changent.

Ce qu'on ne fait **pas** : pas de dégradé animé permanent, pas de confettis, pas
de police téléchargée (la page doit survivre à une box qui tombe), pas de
dépendance externe — la règle de la spec 006 tient : **zéro requête sortante**.

### 3.6 `/resultats` disparaît au profit de `/`

Les deux adressent aujourd'hui la même vue. `climbcontest.adn-dev.fr` sert déjà
la page à la racine : `/resultats` est un doublon.

**Ce qu'on fait** : `/resultats` devient une **redirection permanente** vers `/`
plutôt qu'une 404. Le coût est d'une ligne, et ça protège les liens déjà
partagés — un QR affiché dans la salle, un message envoyé aux parents l'an
dernier. Le doublon disparaît quand même : il n'existe plus qu'une seule page.

À mettre à jour dans la foulée : le lien de la console (`admin.html`), la
`@public path` du Caddyfile de `edge`, et les mentions dans les specs 001 et
006.

## 3.7 Reprise du 31/08 (après la mise en service)

Trois retours d'Adrien, tous vérifiés à l'écran :

**« Ce n'est pas logique : on voit les 3 premiers en ligne puis le reste en
colonne. »** Il a raison — le podium est une rangée qui se lit de gauche à
droite, et le classement enchaînait sur des colonnes qui se lisent de haut en
bas. L'œil changeait de sens au milieu de l'écran. Le classement se remplit
maintenant **par lignes** : 4, 5, 6, puis 7, 8, 9. Un seul sens de lecture.

**« La liste des catégories en haut, avec un truc pour voir le défilement. »**
La barre de catégories, qui n'existait que sur téléphone, est désormais **la
même dans les deux modes** — et la jauge de rotation vit **dans la pastille de
la catégorie affichée** plutôt que dans un filet en haut de l'écran que
personne ne reliait à rien. Sur le mur, elle dit où on en est dans le cycle ;
sur un téléphone, c'est le sélecteur. Toucher une catégorie l'affiche, et
relance le cycle à partir d'elle.

**« Responsive, et sur téléphone un seul tableau. »** Le nombre de colonnes
suit la **largeur** autant que l'effectif (une colonne par tranche de 340 px,
trois au plus), le podium en bandeau disparaît sous 900 px — trois cartes côte
à côte s'y écrasent —, et toutes les tailles du bandeau sont fluides
(`clamp()`) au lieu d'être figées. Sur téléphone, une seule colonne, un seul
tableau : celui qu'on a choisi.

## 3.8 Reprise du 31/08 (soir) — le podium, et un vrai tableau

**Le podium prend la forme qu'on lui connaît** : le premier au centre et plus
haut, le deuxième à gauche un peu en dessous, le troisième à droite plus bas
encore, chacun sur son socle à la couleur de sa médaille. C'est la forme qu'on
lit sans la lire.

**Le classement en dessous devient un tableau**, et pas une pile de cartes.
Adrien : « la présentation des résultats en dessous n'est vraiment pas
terrible ». En regardant comment les services de résultats sportifs s'y prennent
(IFSC, chronométrage de course, tables de classement), trois choses reviennent
partout et manquaient toutes :

| Ce qu'ils font | Pourquoi | Chez nous |
| --- | --- | --- |
| **Position + écart au leader** | « 1287 » ne dit rien seul ; « 1287, à −368 » dit la course. C'est la deuxième colonne de tout classement chronométré | colonne **Écart** |
| **Un en-tête de colonnes** | sans lui, « 16 » et « −368 » sont deux nombres qu'il faut deviner | Rang · Grimpeur · Blocs · Écart · Score |
| **Chiffres tabulaires, alignés à droite ; texte à gauche** | c'est ce qui permet de comparer deux nombres sans les lire | `font-variant-numeric: tabular-nums` partout |

Et des **zébrures très peu saturées** plutôt que des cartes détachées : la
littérature sur les tableaux est nuancée — le gain de vitesse est faible — mais
la précision de lecture progresse, et sur un mur c'est la précision qui compte.
Des colonnes alignées se parcourent à la verticale ; des cartes obligent à
relire chaque ligne en entier.

**Sur téléphone, le tableau se replie en deux lignes** : nom et score en grand,
et « club · 13 blocs · −285 » en petit dessous. Les cinq colonnes coûtent près
de 300 px de gabarit fixe — en dessous, il ne reste plus de place pour le nom,
et c'est le nom qu'on vient lire. Aucune information n'est perdue, elle change
de place.

## 3.9 Le téléphone du spectateur (31/08, soir)

Trois demandes d'Adrien, toutes pour le mode spectateur — le mur ne change pas,
personne ne le touche.

**Le balayage.** Un glissement franc vers la gauche ou la droite passe à la
catégorie suivante ou précédente. Viser une pastille demande de regarder ce
qu'on touche ; un balayage, non. Il est ignoré s'il part de la barre (qui défile
déjà horizontalement) ou s'il est trop vertical — le geste le plus fréquent sur
un classement reste le défilement.

**Les favoris.** Chaque ligne porte une **étoile**. Ce qu'elle change :

| Où | Ce qu'on voit |
| --- | --- |
| Dans un classement | la ligne du favori est **surlignée** et bordée |
| Dans la barre | la catégorie qui contient un favori porte une **étoile** |
| En tête de barre | une entrée **« ★ Mes favoris »** : la liste, avec le rang de chacun dans sa catégorie, et l'étoile pour le retirer |

La recherche par nom ou dossard existait déjà (spec 006) et traverse toutes les
catégories ; c'est d'elle qu'on part pour suivre quelqu'un.

**Où ça se range.** Dans le **stockage local du téléphone**, pas dans un cookie.
Un cookie repart dans *chaque* requête — vers une page que soixante personnes
rafraîchissent toutes les quinze secondes — alors que ces noms n'ont rien à
faire sur le réseau. Là, ils ne quittent jamais l'appareil : rien n'est envoyé,
rien n'est stocké côté serveur, et le classeur ne sait pas qui suit qui.

⚠️ **La liste est liée à une compétition.** Les identifiants de participant sont
réattribués d'une édition à l'autre : suivre « le n°12 » de l'an dernier
désignerait quelqu'un d'autre. Changement de compétition, liste vidée.

Un favori disparu du classement (retiré de la compétition) reste affiché dans la
liste, avec la mention « plus au classement » — sinon on ne pourrait plus
l'enlever.

## 4. Critères d'acceptation

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A1 | À 1920×1080, une catégorie de **25 grimpeurs** tient entièrement, sans défilement | Capture pilotée, comptage des lignes visibles |
| A2 | À 1280×720 (vieux projecteur), elle tient encore | Idem, seconde résolution |
| A3 | Au-delà de la capacité d'un écran, la page pagine et **le dit** (« 1/2 ») | Jeu de 40 grimpeurs |
| A4 | Un rang qui change **glisse** ; la ligne n'est ni détruite ni recréée | Deux rendus successifs, l'élément DOM est le même (`data-id` stable) |
| A5 | Une montée porte ▲ et le nombre de places, une descente ▼ | Jeu de test à deux états |
| A6 | La rotation parcourt **toutes** les catégories, les circuits et le club, puis reboucle | Compte des écrans sur un cycle complet |
| A7 | La barre de progression et le nom de la catégorie suivante sont affichés | Capture |
| A8 | Le fond est clair par défaut ; `?mur&sombre` rend le fond sombre | Deux captures |
| A9 | Aucune requête sortante : ni police, ni image, ni script externe | Le test existant « aucune ressource externe » couvre déjà la règle |
| A10 | La page garde le dernier classement connu quand le serveur tombe | Test existant, conservé |
| A11 | `/resultats` répond 308 vers `/` | Test de route |
| A12 | Le mode spectateur (téléphone) reste utilisable : recherche, choix de catégorie | Capture 390 px + tests existants |
| A13 | `prefers-reduced-motion` coupe les animations | Media query, vérifiée |
| A14 | Le classement se lit dans **un seul sens** — rangées, comme le podium | Absence de `grid-auto-flow: column` ; vérifié à l'écran |
| A15 | La barre de catégories existe dans les **deux** modes, et porte la jauge de rotation | Test de gabarit + capture |
| A16 | Toucher une catégorie l'affiche seule et relance le cycle à partir d'elle | Piloté : clic sur « U13 H » → 25 lignes, une seule table |
| A17 | Le nombre de colonnes suit la largeur de la fenêtre | 1920 → 3, 1100 → 3, 900 → 2, 560 → 1 |
| A18 | Sous 900 px, le podium en bandeau s'efface au profit de la liste | Capture 760 px |
| A19 | Le podium est en **marches** : 1er au centre et plus haut, 2e à gauche, 3e à droite et plus bas | Capture 1920 |
| A20 | Le classement porte un **en-tête de colonnes** et une colonne **Écart** | Capture + test de gabarit |
| A21 | Sous 430 px de colonne, le tableau se replie en deux lignes sans rien perdre | Capture 390 px |
| A22 | Le classement se lit **en colonnes**, chaque colonne annonçant sa tranche | Capture 1920 |
| A23 | Les **ex æquo partagent leur marche** : même niveau, même socle, même médaille | Capture d'une catégorie à deux premiers |
| A24 | Or, argent et bronze se distinguent au premier coup d'œil | Capture |
| A25 | Un balayage horizontal change de catégorie sur téléphone | Piloté : `U11 F` → `U11 H` |
| A26 | L'étoile ajoute et retire un favori, et il survit au rechargement | Piloté + contenu du stockage local |
| A27 | Un favori est surligné dans son classement, sa catégorie marquée dans la barre | Capture 390 px |
| A28 | « ★ Mes favoris » liste les suivis avec leur rang, et permet de les retirer | Capture 390 px |
| A29 | Aucun favori ne part sur le réseau ni dans un cookie | Test de gabarit : `localStorage`, pas de `document.cookie` |

## 5. Ce qui reste hors périmètre

- **Les finales** (spec 009) : un affichage de finale a ses propres règles.
- **Le classement club** garde sa forme actuelle ; il entre dans la rotation,
  il n'est pas repensé.
- **Le contrat de l'API** ne change pas. Si un besoin d'affichage exige une
  donnée que `/api/public/classement` ne porte pas, il rejoint la liste des
  décisions ci-dessous plutôt que d'être ajouté en douce.

## 6. Les décisions, prises le 31/08

Trois directions visuelles ont été maquettées, mêmes données, même résolution
(`maquettes/`) :

| | Direction | Ce qu'elle privilégie |
| --- | --- | --- |
| **A** ✅ | **Podium en bandeau**, fond clair | **Retenue.** Le top 3 en grand sur toute la largeur, le reste en colonnes — et il **défile doucement** quand il déborde |
| **B** | **Grille deux colonnes**, fond clair | La densité : tout le monde à la même taille |
| **C** | **Sombre premium**, fond nuit | Le spectacle, pour un écran LED ou une salle obscure — devenu `?sombre` |

Et les quatre questions ouvertes, tranchées le même jour :

| Question | Décision |
| --- | --- |
| Durée de rotation | **Proportionnelle au plateau** : 8 s + 0,55 s par grimpeur, entre 12 et 35 s |
| Bandeau | **Logo du club**, **compteur de blocs validés du jour**, **heure et fraîcheur du calcul** |
| Classement club | **Hors rotation** — il reste consultable sur téléphone |
| `/resultats` | **Suppression franche (404)**, et retrait des doublons sur `maison.adn-dev.fr` |

Le § 3.6 ci-dessus décrivait une redirection 308 ; c'est la suppression qui a
été retenue. Les alias `resultats.maison.adn-dev.fr` et `classement.maison…`
ont été retirés du portail interne le même jour, sans quoi le doublon aurait
simplement changé d'endroit.
