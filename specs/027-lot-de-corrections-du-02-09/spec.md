# Spec 027 — Le lot de corrections du 02/09

> ## ⚠️ Cette spec a été écrite APRÈS le code. La porte 2 n'a pas été franchie.
>
> La règle 1 du dépôt dit « pas de code sans spec validée », et la porte 2 —
> spec approuvée — appartient à Adrien. Le code de ce lot est committé
> (`8334550`, branche `feat/console-et-impression-2`) alors que cette spec
> n'existait pas. C'est un manquement, et il est de mon fait : Adrien a dicté
> une liste de corrections, j'ai codé directement au lieu de la traduire en spec
> et de la lui soumettre.
>
> Cette spec est donc un **rattrapage**. Elle décrit ce qui a été fait pour
> qu'Adrien puisse exercer la porte 2 sur pièces : valider, amender, ou faire
> retirer. Rien n'est mergé, rien n'est déployé.
>
> Le numéro **027** vient de la répartition proposée entre les trois chantiers
> parallèles — 025 aux cascades de couleurs, 026 à la fiche en direct, 027 à ce
> lot — parce que c'est le seul des trois dont aucun numéro n'a été publié
> ailleurs. Elle reste soumise à Adrien.

## 1. D'où vient ce lot

Demande dictée par Adrien le 02/09/2026, après avoir piloté la v0.15.0 déployée
la veille et lu le CR de validation du classement. Treize points, sans ordre de
priorité, mais avec une consigne de calendrier explicite sur le dernier : « on
le fait à la toute fin de toutes ces remarques ».

## 2. Ce qu'on corrige

### Console

**F1 — Le bouton à maintenir dit ce qu'il attend.**
« Ce n'est pas très visible, l'histoire du maintien du bouton ; regarde comment
ils font sur d'autres sites afin que ce soit plus ergonomique. »

Le défaut n'était pas le geste mais sa **découvrabilité** : le bouton
ressemblait à un bouton ordinaire, rien sur lui n'annonçait qu'il fallait le
tenir. Trois signes le disent maintenant, comme le font les produits qui
emploient ce geste :

1. le **libellé porte l'instruction** — « Maintenir 2 s pour effacer 715
   réussites » — au lieu d'un verbe seul ;
2. un **anneau de progression** entoure le bouton pendant le maintien : c'est
   l'affordance reconnaissable de ce geste ;
3. le libellé **décompte** — « Encore 2 s… » — pour que relâcher trop tôt soit
   compris comme un abandon, pas comme une panne.

Le mot `EFFACER` frappé au clavier disparaît. Adrien : « je déteste écrire ».

**F2 — Après « tout effacer », l'import du nouveau classeur suit tout seul.**
« Actuellement je suis obligé de faire une importation de classeur. »

Le second geste n'apportait **aucun choix** : après un effacement total il ne
reste rien à préserver, donc rien à décider. Un geste sans décision est un
oubli en puissance.

**F3 — « Général » passe en tête de « La compétition ».**
Il avait été rangé en dernier ; Adrien le voulait premier.

**F4 — Les classements affichés se lisent « U11 Scratch », et suivent l'ordre
du terrain.**
Le tri du serveur, alphabétique, séparait un scratch de ses catégories alors
qu'on les regarde ensemble. Chaque circuit précède désormais ses catégories
Femme/Homme, et les scratchs généraux ouvrent la liste.

**F5 — Dans « Circuits », la difficulté et les prises sont des couleurs.**
Rond plein pour la difficulté — elle est **ordonnée** — et carré pour les
prises, qui ne le sont pas. Toutes portent un **contour** : sans lui, « Blanc »,
la couleur de prises la plus courante du classeur, disparaît sur fond clair.
C'est Adrien qui a signalé le piège.

**F6 — Dix-huit paragraphes d'aide allégés, deux supprimés.**
Les deux supprimés étaient devenus **faux** : « deux fiches par page » (il y en
a six depuis la 023) et « le mot EFFACER se frappe » (plus depuis F1). Une aide
fausse est pire qu'une aide absente.

### Impressions

**F7 — Les fiches ne se chevauchent plus.**
« Beaucoup de chevauchement dans le tableau "tes xx blocs" […] lorsque la ligne
de la liste de blocs passe sur 2 lignes. »

Cause : `auto-fit` choisissait ses colonnes d'après la **largeur** disponible,
sans rien savoir de la **hauteur** produite. Dès qu'un groupe de couleur passait
sur deux lignes, la fiche débordait sur sa voisine. Le nombre de colonnes est
désormais calculé en Python, à partir de hauteurs **mesurées dans le
navigateur** — la première estimation se trompait de 25 % sur le coût d'une
ligne (5,9 mm supposés contre 7,27 mm réels), et 43 fiches débordaient.

**F8 — Plus une seule fiche à cheval sur deux feuilles.**
« Si j'essaye d'imprimer, je me retrouve avec des dossards entre 2 feuilles. »

Cause : une grille dont les éléments portent `break-inside: avoid` est
fragmentée « au mieux » par le navigateur, qui n'a aucune obligation de
respecter un nombre d'éléments par page. Le découpage passe en Python
(`fiches.en_feuilles`) et le saut de page porte sur la **feuille**, jamais sur
un élément de grille.

**F9 — Les étiquettes ne gaspillent plus de pages.**
« Je me retrouve avec des pages vides et celles qui sont avec des QRCode ne sont
pas bien remplies […] minimum 6 QRCode dans une A4. »

Le saut de page par zone laissait des feuilles à moitié vides : une zone d'un
seul bloc en gaspillait sept places. Les blocs sortent déjà dans l'ordre du
`Plan`, donc zone par zone, et chaque étiquette porte sa zone en tête : le
regroupement physique est conservé sans payer une feuille par zone. **Huit par
A4**, au-dessus des six demandés.

### Page de résultats

**F10 — Le podium s'affiche toujours, avec ses trois marches.**
« Même si le podium n'est pas encore établi, il faut l'afficher même s'il doit
être vide. As-tu pris en compte le cas d'une catégorie avec une seule personne,
ou 2 ? »

Deux conditions le faisaient disparaître : moins de quatre grimpeurs, et « tout
le monde est sur le podium ». C'est **exactement** le cas des catégories à une
ou deux personnes qu'Adrien vise. Les places sans gagnant montrent une marche en
pointillé — un podium en attente, pas un podium absent.

Et un grimpeur n'y monte que s'il a **marqué**. Sans ce filtre, une catégorie
qui n'a pas commencé couronnait dix-sept personnes à zéro point.

### Application juge

**F11 — Un écran d'accueil au logo du club.**
Effacé dès que l'application est prête, avec un **plancher de 750 ms** : sans
lui, sur un téléphone rapide, il clignotait sans être vu — pire que pas d'écran
du tout.

**F12 — Le fond réchauffé vers l'ocre du logo.**
« Change-moi le fond pour qu'elle soit plus accueillante, regarde le design
d'autres applications du même style. »

⚠️ **La contrainte qui borne cette demande** : dans cette application, la
couleur **porte de l'information** — la teinte du circuit prend l'écran dès
qu'un bloc est scanné, c'est le retour visuel du juge. Une teinte franche au
repos entrerait en concurrence avec elle. D'où une **lueur** en haut d'écran et
un fond réchauffé, jamais un aplat coloré.

**F13 — Cache du service worker en v3.**
Sans ce changement de version, les téléphones déjà équipés garderaient
l'ancienne coquille, sans le logo. C'est le genre d'oubli qui ne se voit qu'en
compétition.

## 3. Périmètre

**Exclu, à dessein — et c'est le point à ne pas perdre :**

- **La refonte du plan du mur.** Adrien : « je voudrais qu'on retravaille le
  plan qui est sur les dossards, car il n'est pas très beau et ne représente pas
  vraiment la forme du mur, on le fait à la toute fin de toutes ces remarques ».
  Elle fera sa propre spec, parce qu'elle change la **structure** de `PLAN` —
  d'une grille 8×7 à des polygones libres avec un profil de mur — et pas
  seulement le relevé. Elle est **bloquée sur Adrien** : il doit dessiner sa
  salle dans la planche qui lui a été livrée. Deux autres sessions travaillent
  sur des chantiers qui lisent `PLAN` ; le contrat de la nouvelle structure leur
  a été transmis.
- **Les couleurs de papier des fiches** (`Listes!D17:E19`), toujours pas
  importées — voir spec 024 § 4.

## 4. Critères d'acceptation

Tous **mesurés** le 02/09/2026, suite complète au vert (Python + `node --test`).

- [x] **A1** — Le bouton destructif annonce la durée du maintien et ce qu'il
  détruit, montre sa progression, et décompte.
- [x] **A2** — Changer de classeur en mode « tout effacer » importe le nouveau
  classeur sans second geste.
- [x] **A3** — « Général » est le premier élément de « La compétition ».
- [x] **A4** — Un circuit s'affiche « U11 Scratch » et précède ses catégories ;
  les scratchs généraux sont en tête.
- [x] **A5** — Difficulté et prises sont des pastilles colorées avec contour ;
  « Blanc » reste visible sur fond clair.
- [x] **A6** — Aucune aide ne décrit un comportement disparu.
- [x] **A7** — **Zéro chevauchement** et **zéro débordement** sur les 120 fiches
  de la compétition de test.
- [x] **A8** — 120 fiches → **20 feuilles**, six par feuille, aucune à cheval.
- [x] **A9** — 53 étiquettes → **7 feuilles**, huit par A4, aucune page vide.
- [x] **A10** — Le podium s'affiche à 0, 1, 2 et 3+ grimpeurs classés.
- [x] **A11** — Un grimpeur à zéro point ne monte sur aucune marche.
- [x] **A12** — L'écran d'accueil reste visible au moins 750 ms puis s'efface.
- [x] **A13** — Le cache du service worker a changé de version et sert le logo.

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| Maintien relâché à 1,5 s | Rien n'est détruit ; l'anneau revient à zéro |
| Maintien sur un appareil tactile | Même geste ; `pointerdown` couvre les deux |
| « Tout effacer » sur un classeur injoignable | L'effacement a lieu, l'import échoue et le dit — l'un ne masque pas l'autre |
| Bloc sans couleur de prises | La pastille disparaît, la ligne garde sa mise en page |
| Grimpeur à 43 blocs | La fiche calcule ses colonnes et ne déborde pas |
| Zone d'un seul bloc | Ses étiquettes complètent la feuille de la zone précédente |
| Catégorie à 1 grimpeur | Une marche occupée, deux en pointillé |
| Catégorie où personne n'a marqué | Trois marches en pointillé, aucun nom |
| Téléphone déjà équipé de la v2 | La v3 se substitue au premier chargement en ligne |
