# Spec 044 — La préparation des ouvreurs

> **Statut : soumise à la porte 2.** Écrite avant le code, maquette produite
> avant la spec.
>
> Demande d'Adrien du 04/09/2026 : « Je veux qu'il soit possible d'avoir une
> belle interface pour préparer une compétition pour les ouvreurs, le but c'est
> qu'ils puissent utiliser le plan de la salle pour définir dans chaque zone le
> nom et le niveau des voies qui sont présentes et à quelle catégorie. Sachant
> que toutes les informations ne vont pas être remplies en une fois. Il faut que
> ce soit une interface dans la console mais avec un rôle ouvreur où il n'y aura
> accès qu'à ça. »
>
> Quatre arbitrages ont été rendus le même jour, avant rédaction. Ils sont
> repris en tête de chaque section qu'ils gouvernent.

---

## 1. Ce qui manque

**Les blocs d'une compétition n'existent que par l'import du classeur.** Il n'y
a, aujourd'hui, aucune route qui crée un bloc : `sheets/importer.py` lit
l'onglet `Plan` (colonne D pour la zone, F pour la couleur de difficulté, H pour
la couleur des prises, J/L/N/P/R pour les circuits, T pour le numéro sur le mur)
et c'est tout. La console sait tout modifier d'une compétition — participants,
dossards, circuits, cascade, classeur — **sauf ses voies**.

Conséquence pour les gens qui les posent :

1. **Les ouvreurs n'ont pas d'écran.** Ce qu'ils savent — quelle voie ils
   viennent de poser, dans quelle couleur, pour quelles catégories — transite
   par un papier, puis par une feuille de calcul remplie plus tard, par
   quelqu'un d'autre. Chaque recopie est une occasion de se tromper, et le
   classeur ne dit jamais qu'il s'est trompé.
2. **L'ouverture s'étale sur plusieurs séances**, et rien ne tient l'état
   intermédiaire. « Il reste la zone F et la moitié de la I » ne se lit nulle
   part ; il faut aller voir le mur.
3. **Le plan de la salle existe déjà et ne sert qu'à imprimer.** Il est dessiné
   depuis la console (spec 029), rendu sur les dossards (spec 023), sur la fiche
   du grimpeur (spec 026) et sur la page de résultats (spec 036). Personne ne
   s'en sert pour **saisir**, alors que c'est exactement l'objet que les
   ouvreurs ont en tête quand ils travaillent.

`docs/contraintes-metier.md` §2 annonçait déjà la reprise : « Plan des blocs,
zones, couleurs » et « Affectation bloc ↔ circuit » devaient passer du classeur
à la console. C'est ce lot qui la fait, en la donnant d'abord à ceux qui
détiennent l'information.

---

## 2. Ce qu'on fait

### F1 — La saisie s'ouvre avec le mode sans classeur (spec 045)

> **Arbitrage du 05/09**, après un premier tour : le choix n'est pas « d'où
> viennent les blocs », c'est **si le classeur existe encore**. « Si les blocs
> sont rentrés via la console, le fichier Google n'a plus lieu d'être, dans ce
> cas on va le supprimer. »

Cet écran a **deux régimes**, et c'est le réglage global de la
[spec 045](../045-mode-sans-classeur/) qui décide lequel :

| Le mode sans classeur est… | Ce qui fait foi pour les blocs | L'écran d'ouverture |
| --- | --- | --- |
| **éteint** (défaut) | l'onglet `Plan` du classeur Google | **lecture seule** — il montre ce que l'import a posé |
| **allumé** | la base, remplie par les ouvreurs | en écriture |

⚠️ **Il n'y a pas d'interrupteur propre à ce lot.** Une première version en
posait un, par compétition (`options.source_blocs`) — écarté : deux réglages
cousins qui disent la même chose finissent par se contredire, et celui-là aurait
laissé la vue « Classeur » dans les paramètres alors que la demande est
précisément de ne plus l'y voir.

**Conséquence directe : le miroir vers le classeur n'est plus un sujet ici.**
Une première rédaction consacrait toute une section au fait que les réussites
des voies créées en console tomberaient sur les mauvaises lignes de l'onglet
`Import`. Le cas ne peut plus se produire : soit le mode est éteint et aucune
voie n'est créée en console, soit il est allumé et il n'y a plus d'onglet
`Import`. Le problème n'a pas été résolu, **il a été supprimé**.

⚠️ **Ce lot est donc livrable seul, mais il n'est pleinement utile qu'avec la
045.** Livré sans elle, il apporte le rôle `ouvreur` et un écran de
consultation. C'est un ordre de merge à décider, pas une impasse.

### F2 — Un rôle `ouvreur`, qui ne voit que ça

> **Arbitrage du 04/09** : « Les voies, et rien d'autre ».

Un troisième rôle rejoint `admin` et `organisateur` dans `comptes.ROLES_CONNUS`.
Ce à quoi il donne droit, et rien d'autre :

| Il peut | Il ne peut pas |
| --- | --- |
| ouvrir l'écran **Ouverture** et y saisir | voir les participants, les dossards, les réussites |
| lire le plan de la salle | **redessiner** le plan (il part sur 120 dossards imprimés) |
| changer **son** mot de passe | gérer les comptes, le classeur, les réglages, les archives |

Trois points de vigilance, tous vérifiés dans le code existant :

1. `exige_role(ADMIN)` et `exige_role(ORGANISATEUR)` refusent déjà tout rôle
   qu'ils ne nomment pas : un ouvreur reçoit **403** sur les quarante-six routes
   existantes, sans qu'aucune ait à être modifiée.
2. **Les deux routes décorées `exige_role()` sans argument** — `GET /admin/moi`
   et `POST /admin/mon-mot-de-passe` — s'ouvrent donc à l'ouvreur. C'est voulu
   pour les deux, et c'est le seul endroit du lot où il faut le vérifier plutôt
   que le supposer.
3. Les routes de ce lot sont décorées `exige_role(OUVREUR, ORGANISATEUR)` :
   **un organisateur doit pouvoir préparer aussi.** `exige_role` n'accorde pas
   un rôle par ancienneté — sans le nommer, un organisateur serait refusé sur
   l'écran qu'il a lui-même à contrôler.

⚠️ Le contrôle d'accès **visuel** de la console (masquer les entrées du tiroir)
est un confort, pas une barrière. La barrière est serveur, et elle l'est déjà.

### F3 — L'écran « Ouverture » : le plan, la zone par-dessus

> **Arbitrage du 04/09** : « Plan plein écran, la zone s'ouvre par-dessus ».

Le rendu validé est dans [`maquettes/index.html`](maquettes/index.html) — six
états, en clair et en sombre, sur la vraie géométrie du mur d'Annonay.

**Le plan occupe l'écran.** Chaque zone porte, sous sa lettre, la pastille de la
spec 036 — même socle, mêmes cinq ratios — mais elle y porte **un compte**, pas
un avancement.

> ⚠️ **Correction du 05/09, et elle est structurelle.** La première version
> écrivait « 3/5 » et remplissait la pastille de vert à proportion : la jauge de
> la spec 036. Adrien : « je ne comprends pas ta barre de progression sur
> l'avancement de l'ouverture, elle ne devrait pas exister car les ouvreurs ne
> savent pas à l'avance ce qu'ils vont ouvrir et où. »
>
> Il a raison, et la raison n'est pas une question de goût : **une jauge suppose
> un total connu d'avance**. Sur la fiche du grimpeur, le dénominateur est le
> nombre de blocs de son circuit — un fait, arrêté avant qu'il grimpe. Ici, le
> dénominateur est *ce qui a été tapé jusqu'à maintenant*, et il grandit à
> chaque voie ajoutée. « 3/5 » se lisait « tu es à 60 % de la zone J » alors que
> personne ne sait ce que vaudra la zone J — pas même l'ouvreur qui la pose.
>
> Le **cadre vert « terminée »** tombe avec, et pour la même raison : « terminée »
> est une promesse sur ce même total inconnu.

Ce qui reste, parce que c'est un fait et non une prédiction :

| Sur la zone | Ce que ça dit |
| --- | --- |
| un **chiffre** — « 5 » | cette zone porte cinq voies déclarées |
| un **liseré ambre** | au moins une de ces voies attend encore une couleur ou une catégorie |
| **rien, zone effacée** | personne n'y a encore rien déclaré |

Le liseré n'est pas un avancement : il porte sur des voies **qui existent
déjà**. C'est du travail identifié, pas une part d'un tout qu'on ignore.

**Une zone touchée ouvre un tiroir par-dessus le plan**, avec ses voies. ⚠️ **Le
plan se replie au-dessus du tiroir plutôt que de disparaître dessous** : sans
ça, le tiroir recouvre précisément le pan qu'on vient d'ouvrir, et on perd de
vue où l'on est au moment même où l'on saisit. Sur un grand écran, le tiroir
s'ancre à droite, le plan reste entier, clair et cliquable.

**Ce que le plan ne peut pas occuper sert à dire ce qui reste.** Le mur
d'Annonay est plus large que haut : sur un téléphone il laisse un tiers de
l'écran libre, quel que soit le cadrage. Cette place porte deux choses, et pas
un vide :

- la **répartition des couleurs** — six barres, « ai-je assez de bleues ? » est
  la deuxième question d'un ouvreur ;
- les **zones à compléter**, en pastilles touchables — la première.

⚠️ **Aucun bouton d'accent sur cet écran.** L'action principale, c'est de
toucher une zone. « Renuméroter » peint en ocre sur toute la largeur en faisait
le geste que l'œil propose en premier, alors que c'est le seul de l'écran qui ne
se rattrape pas.

### F4 — Une voie se remplit en plusieurs fois

> Contrainte énoncée le 04/09 : « toutes les informations ne vont pas être
> remplies en une fois ».

Une voie porte quatre choses, et **aucune n'est obligatoire pour l'enregistrer** :

| Champ | D'où il vient | Obligatoire ? |
| --- | --- | --- |
| la **zone** | le pan qu'on a touché | oui, par construction |
| la **couleur de difficulté** | six jetons — Jaune, Vert, Bleu, Mauve, Rouge, Noir | non |
| la **couleur des prises** | sept jetons courants, et un **nuancier** derrière « Personnaliser… » | non |
| les **catégories** | les circuits de l'édition, en jetons | non |

> **Le nuancier des prises, demandé le 05/09** : « il faut qu'on laisse à
> l'ouvreur le choix de la couleur […] un bouton pour personnaliser [qui] ouvre
> une palette de couleur plus large, une espèce de nuancier chromatique.
> Attention il ne faut pas qu'il y ait trop de choix, ce ne sont que des prises
> d'escalade ; donc proposer 10 nuances de rouge n'est pas nécessaire, mais du
> rouge et du rose oui. »
>
> Quinze teintes, **distinctes et nommables** — pas un dégradé : Blanc, Gris,
> Noir, Beige, Marron, Jaune, Fluo, Orange, Rouge, Rose, Fuchsia, Violet, Bleu,
> Turquoise, Vert. Sept sont visibles d'emblée (celles d'avant le nuancier) ;
> les huit autres attendent derrière le bouton. L'écran de tous les jours ne
> grandit pas parce qu'un choix rare est devenu possible.
>
> ⚠️ **Une couleur déjà posée est toujours montrée**, même hors des sept
> courantes et même absente du nuancier — le classeur a pu y écrire un mot que
> le nuancier ne connaît pas. La masquer la laisserait en base et sur
> l'étiquette imprimée, sans qu'on puisse la retrouver dans la console.

Une voie est **complète** quand elle porte une couleur de difficulté *et* au
moins une catégorie. C'est ce que compte la pastille de sa zone, et c'est le
seul jugement que l'écran porte sur une voie.

⚠️ **Aucun champ libre, aucun clavier.** Tout est un jeton qu'on touche. Un
clavier qui s'ouvre devant un mur, téléphone tenu d'une main, c'est trois fautes
de frappe sur dix voies — et une couleur mal orthographiée sort du classement
sans le dire (`fiches._rang` range un bloc de couleur inconnue **après** tous les
autres, silencieusement).

⚠️ **Pas de nom libre, pas de cotation.** Le modèle ne porte que ce que le
classement lit. Arbitrage du 04/09 : « il faut seulement la couleur de
difficulté et la couleur de prise ». Le « nom » de la demande initiale, c'est le
numéro écrit sur le mur — voir F5.

### F5 — Le numéro s'attribue au fil de l'ouverture

> **Arbitrage du 04/09** : « la numérotation doit se faire au fur et à mesure de
> l'ouverture ».

Le nom d'une voie, c'est **l'initiale de sa couleur suivie de son rang dans
cette couleur** : `V7` est la septième verte de la salle. C'est déjà la
convention du club — le relevé de novembre 2025 porte `z J4`, `a B10`, `b R8`,
c'est-à-dire zone + couleur + rang. Les six initiales sont distinctes :

| Jaune | Vert | Bleu | Mauve | Rouge | Noir |
| --- | --- | --- | --- | --- | --- |
| `J` | `V` | `B` | `M` | `R` | `N` |

**Le QR code de la voie, lui, porte zone + nom** — `J` + `V7` = `JV7`. C'est le
`tag` que le juge scanne, et c'est ce que l'écran affiche en chasse fixe sous
chaque ligne : c'est là qu'une faute de zone se voit.

Le numéro s'attribue **dès que la couleur est choisie**, et pas avant : le
premier rang libre de cette couleur dans l'édition. Une voie sans couleur n'a
pas de nom, et c'est cohérent — elle n'a pas encore de place dans la salle.

Changer la couleur d'une voie lui donne un nouveau nom dans la nouvelle couleur
et libère l'ancien. **Ça change son QR** : voir les garde-fous en F7.

### F6 — Le bouton « Renuméroter »

> **Arbitrage du 04/09** : « un bouton qui permet de tout renuméroter
> automatiquement en suivant une certaine logique : la numérotation pour une
> couleur de difficulté commence en zone A et termine en Z ».

Pour **chaque couleur**, on parcourt les zones **dans l'ordre alphabétique** et
on numérote `1, 2, 3…` sans trou. À l'intérieur d'une zone, l'ordre de saisie
est conservé.

Cette dernière phrase n'est pas un détail : c'est ce qui rend l'opération
**stable**. Relancée deux fois, la seconde ne change rien — et une action qui
donne un résultat différent à chaque appel n'est pas une action qu'on ose
lancer la veille d'une compétition.

L'écran de confirmation **nomme ce qui change** (« 17 voies changent de
numéro »), en montrant les premières lignes avant/après. Il dit aussi la
conséquence, parce qu'elle n'est pas devinable :

> Leur QR change avec — les étiquettes déjà collées sur le mur ne seront plus
> valables et sont à réimprimer.

Et **il se confirme par un geste, pas par un clic** — celui de la maison :

| Surface | Geste | D'où il vient |
| --- | --- | --- |
| Souris / trackpad | **maintenir 2 s**, avec anneau, jauge et décompte | `admin.html`, `button.detruire` (spec 032, 02/09) |
| Doigt | **glisser** le curseur jusqu'au bout | Sowel, `SlideToConfirm.tsx` (spec 146) |

⚠️ **C'est le pointeur qui décide, pas la largeur de l'écran** :
`(hover: hover) and (pointer: fine)` → le maintien, sinon le glissement. Un
portable tactile et un téléphone en paysage se rangeraient du mauvais côté d'une
simple largeur.

⚠️ **Relâcher trop tôt annule, dans les deux cas.** C'est tout l'objet du
geste : une pression accidentelle ne déclenche rien.

⚠️ **Le geste est réservé à ce qui ne se rattrape pas.** La règle existe déjà
dans le code — « le maintien de deux secondes est réservé à ce qui efface »
(`admin.html`, à propos de `dlgMaj`). Renuméroter change dix-sept QR collés sur
un mur : c'est de cette famille. **Supprimer une voie ne l'est pas** — elle est
déjà refusée dès qu'une réussite existe, et une voie vide se recrée en trois
touches. Bouton ordinaire.

### F7 — Les garde-fous : ce qui devient impossible

Trois interdits, et chacun ferme un chemin par lequel une compétition se
casserait en silence :

1. **Rien ne se saisit hors d'une compétition en `preparation`.** Dès qu'elle
   passe `en_cours`, l'écran devient une consultation. Un tag qui change pendant
   la compétition, c'est un QR collé sur le mur qui ne désigne plus rien : le
   juge scanne, l'application répond « bloc inconnu », et le grimpeur perd sa
   réussite.
2. **Une voie qui porte au moins une réussite ne change ni de couleur, ni de
   zone, et ne se supprime pas.** Le refus nomme le nombre de réussites — c'est
   la même règle, et la même formulation, que la réaffectation de dossard
   (`docs/contraintes-metier.md` §1).
3. **« Renuméroter » est refusé dès qu'une réussite existe dans l'édition.**
   Pas seulement sur les voies concernées : le geste est global, il doit être
   jugé globalement.

⚠️ Ces trois règles sont **serveur**. L'écran les affiche, mais ce n'est pas
l'écran qui les tient.

### F8 — Les catégories se créent depuis l'écran

Sans circuit, un ouvreur ne peut cocher aucune catégorie — et aujourd'hui les
circuits ne naissent **que** de l'en-tête de l'onglet `Plan` du classeur. En
mode sans classeur, ce chemin n'existe plus.

L'écran permet donc, quand la saisie est ouverte, de **créer un circuit** (un
nom, vingt caractères) et d'en **supprimer un qui ne porte aucune voie**. Rien
de plus : renommer un circuit déplacerait des blocs d'une catégorie à l'autre
sans le dire.

### F9 — Rien à faire du côté du classeur

Section conservée volontairement, et vide, pour dire **pourquoi** elle l'est.

Voir F1 : les deux régimes de cet écran s'excluent, et aucun des deux ne produit
de réussite sans adresse dans le classeur. Toute la mécanique du débranchement —
le réglage, l'extinction de l'import, du miroir et de la vue « Classeur », et le
contrôle avant bascule — vit dans la [spec 045](../045-mode-sans-classeur/).

---

## 3. Critères d'acceptation

| # | Ce qu'on vérifie |
| --- | --- |
| A1 | Mode sans classeur **éteint** : l'écran s'ouvre et refuse toute écriture (409) |
| A2 | Mode **allumé** : l'écriture est permise, et l'import du classeur n'existe plus (spec 045) |
| A3 | Un compte `ouvreur` reçoit 403 sur `/admin/participants`, `/admin/classeur`, `/admin/comptes`, `/admin/plan` (POST), et 200 sur `/admin/ouverture` et `/admin/moi` |
| A4 | Un compte `organisateur` accède à l'écran d'ouverture (il n'est pas refusé faute d'être nommé) |
| A5 | Une voie s'enregistre sans couleur et sans catégorie ; sa zone la compte comme incomplète |
| A6 | Poser une couleur sur une voie qui n'en a pas lui attribue le premier rang libre de cette couleur, et son `tag` devient zone + nom |
| A7 | « Renuméroter » sur le jeu d'essai donne, pour chaque couleur, `1…n` en parcourant les zones de A à Z ; relancé, il ne change plus rien |
| A8 | « Renuméroter » est refusé (409) dès qu'une réussite existe, en nommant leur nombre |
| A9 | Changer la couleur d'une voie qui porte une réussite est refusé (409) ; la supprimer aussi |
| A10 | Toute écriture est refusée si la compétition n'est pas en `preparation` |
| A11 | Toute écriture incrémente `catalogue_version` : un téléphone déjà synchronisé revoit les voies changées |
| A12 | Créer un circuit depuis l'écran le rend cochable ; supprimer un circuit qui porte une voie est refusé |
| A13 | La pastille d'une zone affiche « complètes / déclarées » ; une zone sans voie n'en porte aucune |

---

## 4. Cas limites

| Situation | Ce qui doit se passer |
| --- | --- |
| Deux ouvreurs saisissent la même zone en même temps | La dernière écriture gagne sur la voie qu'elle touche, et **elle seule** : on écrit voie par voie, jamais la zone entière |
| Une zone du plan disparaît (le mur est redessiné) | Ses voies restent en base et remontent dans un bandeau « hors plan » — même repli que `fiches`, qui ne fait jamais disparaître un bloc silencieusement |
| Une voie importée du classeur porte une couleur hors des six | Elle s'affiche telle quelle, en lecture ; la modifier impose de choisir parmi les six |
| Le plan n'a jamais été dessiné | Le plan d'usine s'applique, comme partout ailleurs |
| Le rang d'une couleur dépasse 99 | Rien ne casse : le nom est du texte, la pastille rétrécit son libellé (`tailleDuCompte`) |
| L'ouvreur ouvre l'écran hors compétition en préparation | Un écran qui explique, pas une erreur : « aucune compétition en préparation » |

---

## 5. Ce qui n'est PAS dans ce lot

- **Écrire l'onglet `Plan` du classeur depuis la console.** C'était la troisième
  option de l'arbitrage, écartée : ce serait la première écriture de *structure*
  dans le classeur, beaucoup plus lourde et plus risquée que d'y écrire des
  réussites.
- **Une cotation d'ouvreur** (4a, 5b…). Écartée le 04/09.
- **Un nom libre de voie.** Idem.
- **L'impression des étiquettes depuis cet écran.** Elle existe déjà
  (`/admin/etiquettes`, spec 024) et n'a pas besoin d'être dupliquée ici.
- **Le rôle ouvreur sur la page de résultats.** Hors du besoin « préparer ».

---

## 6. Les décisions de la porte 2

Tranchées par Adrien les **04** et **05/09/2026**.

1. **F1 — l'interrupteur.** ✅ *Remplacé par un réglage **global**, dans la
   [spec 045](../045-mode-sans-classeur/).* Le choix n'est pas la source des
   blocs, c'est l'existence du classeur : « je ne veux plus du tout le voir dans
   les paramètres et je ne veux plus qu'on lui remonte les infos ».
2. **F9 — le miroir.** ✅ *Sans objet.* Le filtre voie par voie décidé plus tôt
   est **retiré** : le cas qu'il traitait ne peut plus se produire.
3. **F7.1 — l'écriture réservée aux compétitions en `preparation`.** ✅
   *Confirmé.* Une correction sur une compétition déjà lancée passe par un
   retour explicite en préparation.
4. **F2 — l'ouvreur ne redessine pas le plan.** ✅ *Confirmé.* « L'ouvreur ne
   peut pas redessiner le plan. » Il le lit, il ne l'écrit pas.
