# Spec 018 — Le cycle de vie d'une compétition, piloté depuis la console

> **Statut : validée (porte 2) et codée — 01/09/2026.** Adrien a validé les
> quatre écarts soumis, puis tranché le cinquième point (le statut) en cours de
> relecture. La porte 7 (merge) reste la sienne.
> Demandée par Adrien le 01/09/2026 : « je voudrais pouvoir contrôler
> l'importation des données de compétition depuis la feuille Google Sheet […]
> il me faut une page de contrôle dans la console […] je veux quelque chose de
> simple ».
> Quatre points ont été tranchés par Adrien avant rédaction, un cinquième
> pendant la relecture de la porte 2 — ils sont repris tels quels au § 3.

## 1. Ce qui manque

La spec 015 a posé la vue « Classeur » : relier une feuille, la tester en
lecture, poser le jeton, lancer l'import. Elle couvre le **branchement**. Elle
ne couvre pas le **cycle de vie** d'une édition — et c'est ce qui reste à faire
à la main, ou pas du tout.

### M1 — On ne sait pas si on a le droit d'écrire

« Tester l'accès » ne fait que lire. Or la panne qu'on veut voir venir n'est
pas « la feuille est introuvable » : c'est **« la feuille est partagée en
lecture seule avec le compte du jeton »**. Ce cas-là passe le test actuel sans
broncher — titre lu, onglets listés, grille mesurée, tout est vert — et se
révèle quarante secondes après le premier scan, quand le miroir échoue en
silence et que les réussites commencent à s'empiler « en attente ».

Le seul moyen de savoir si on peut écrire, c'est d'écrire.

### M2 — Effacer les données demande de changer de classeur

Le mode « nouvelle compétition » de la spec 015 efface bien la base — mais
seulement **en même temps qu'on relie une autre feuille**. Repartir de zéro sur
la **même** feuille est un geste courant en préparation (on sème des données de
test, on veut les enlever) et il n'existe pas. Aujourd'hui il se fait en SQL sur
la base de production.

Constat au 01/09 : la base porte **715 réussites de développement** sur la
compétition active. Il n'y a aucun bouton pour les enlever.

### M3 — Une édition terminée n'est archivée nulle part

La base est multi-compétition depuis la spec 002 : « on consulte les archives
des éditions passées », dit `models.py`. Sauf que **rien ne les consulte**. La
page de résultats ne connaît que la compétition **active**, et la console
n'affiche que la compétition active. Une édition terminée existe en base sans
qu'aucun écran ne sache la montrer — et le jour où on efface pour repartir,
elle disparaît sans laisser de trace.

C'est le manque le plus coûteux des quatre : il est irréversible.

### M4 — L'import n'a qu'un seul comportement, jamais annoncé

`POST /admin/import/sheet` fait une mise à jour (ajout des lignes absentes,
correction des lignes présentes). C'est le bon comportement — mais c'est le
**seul**, et le bouton ne dit pas lequel c'est. Quand on branche le classeur
d'une nouvelle édition sur une base qui porte encore l'ancienne, « Importer »
empile la nouvelle liste sur l'ancienne : les grimpeurs de l'édition passée
restent, avec leurs dossards, et le juge qui scanne le dossard 12 voit
peut-être le nom de l'an dernier.

### M5 — Le statut d'une compétition est écrit une fois, puis ment

Question d'Adrien à la porte 2 : « comment tu fais pour savoir qu'une
compétition est démarrée ? » Réponse : **on ne le sait pas.**

`Competition.statut` est écrit **à la création, et plus jamais** — par le défaut
du modèle (`preparation`) ou en dur par les deux outils de peuplement
(`semer_competition_test.py:40`, `load/charge_novembre.py:107`, tous deux
`en_cours`). Aucune route, aucun écran, aucune commande CLI ne le change ensuite.
`contest.py` importe même `EN_COURS` sans jamais s'en servir.

Un seul endroit en décide quelque chose : la garde de la spec 015
(`parametrage.py:254`), qui refuse le mode « nouvelle compétition » sur une
compétition `en_cours`. Son effet est **exactement inversé** :

| Compétition créée par… | Statut, pour toujours | Ce que fait la garde |
| --- | --- | --- |
| La voie normale (défaut du modèle) | `preparation` | Ne se déclenche **jamais**, même en pleine compétition |
| Les outils de peuplement | `en_cours` | Bloque **en permanence**, y compris sur des données jetables |

Ce n'est pas théorique : la base de développement du 01/09 porte
`1 | Developpement | en_cours | active`. Le mode « nouvelle compétition » y est
donc **déjà refusé**, sur les 715 réussites de dev qu'on veut justement pouvoir
enlever.

Personne d'autre ne lit ce champ — ni la page de résultats, ni la PWA, ni l'app
Android. Il n'est affiché qu'à une ligne de la console (`admin.html:1361`), où
il affiche donc une valeur fausse.

## 2. Ce qu'on fait

Trois vues dans la console, dans l'ordre où on s'en sert :

| Vue | Ce qu'elle porte | Rôle exigé |
| --- | --- | --- |
| **Classeur** (existante, complétée) | relier, **tester en lecture ET en écriture**, jeton | `ADMIN` |
| **Compétition** (nouvelle) | **régler l'état de l'édition**, importer (deux modes), archiver, effacer | voir ci-dessous |
| **Archives** (nouvelle) | la liste des éditions archivées, revoir, télécharger, supprimer | voir ci-dessous |

Et le partage des rôles suit la règle déjà posée par la spec 015 — *décider où
vont les données est plus grave que les relire* :

| Geste | Rôle | Pourquoi |
| --- | --- | --- |
| Importer (mise à jour) | `ORGANISATEUR` | Ne fait que relire ce qui est déjà relié |
| Consulter et télécharger une archive | `ORGANISATEUR` | Consultation |
| Régler l'état de l'édition | `ORGANISATEUR` | Ne détruit rien, et c'est le geste de celui qui ouvre la journée |
| Importer (remplacement), archiver, effacer, supprimer une archive | `ADMIN` | Destructeur, ou irréversible |

### 2.1 Régler l'état de l'édition

Trois boutons — **Préparation**, **En cours**, **Terminée** — en tête de la vue
« Compétition ». C'est tout, et c'est ce qui manquait pour que le champ existant
veuille dire quelque chose (M5).

Deux gestes le changent aussi tout seuls, et c'est voulu :

| Geste | Effet sur le statut |
| --- | --- |
| **Archiver** | passe à `terminée` — archiver, c'est clore |
| Les trois boutons | ce qu'on a cliqué |

Rien d'autre. En particulier, **un scan de juge ne fait pas passer une
compétition en `en_cours`** : une réussite qui arrive parce qu'un bénévole teste
son téléphone le jeudi soir ne doit pas armer un garde-fou. C'est un geste
humain, ou rien.

Le statut ne commande **aucun** comportement du produit : ni les scans, ni le
classement, ni la page de résultats, ni les téléphones. Il ne sert qu'à deux
choses — se dire où on en est, et armer l'avertissement du § 2.5. Une étiquette,
pas un interrupteur. C'est ce qui permet de le corriger à tout moment sans rien
casser.

### 2.2 Tester l'accès en écriture

Le test actuel garde ce qu'il fait, et gagne un aller-retour :

```
1.  lire   Import!<dernière cellule de la grille>     ← doit être vide
2.  écrire la même cellule = « climbcontest-test <horodatage> »
3.  relire la même cellule                            ← doit valoir ce qu'on a écrit
4.  effacer la même cellule                           ← on remet comme c'était
```

**La cellule témoin est le dernier coin de la grille** (`DP1000` sur une grille
de 120 × 1000), pas une cellule de la matrice : la ligne 1 porte les dossards,
les colonnes A à C portent les blocs, `D2:…` porte les « A », et `D103` porte un
horodatage. Le coin, lui, est vide par construction.

**Si elle n'est pas vide, on n'écrit pas.** Le test le dit, et s'arrête là :
mieux vaut un test qui renonce qu'un test qui écrase une donnée qu'on n'avait
pas prévue.

**Si l'effacement final échoue**, le rapport nomme la cellule en toutes lettres.
Une trace `climbcontest-test 2026-09-01T14:02` dans le coin d'un onglet ne gêne
rien ni personne, mais il faut savoir qu'elle est là plutôt que la découvrir.

En prime, et parce que ça ne coûte qu'un champ sur une requête déjà faite : le
test signale les **plages protégées** de l'onglet `Import`. C'est l'autre façon
de perdre le droit d'écrire au milieu de la feuille alors qu'on l'a sur le
reste — et le test du coin, par construction, ne la verrait pas.

### 2.3 Importer, avec le mode annoncé

Deux modes, choisis à l'écran, jamais devinés :

| Mode | Ce qu'il fait | Quand |
| --- | --- | --- |
| **Mise à jour** (défaut) | Ajoute les grimpeurs et les blocs absents, corrige ceux dont la ligne a changé dans le classeur. N'efface jamais rien. | Le cas courant : on a corrigé une catégorie, ajouté trois inscrits de dernière minute |
| **Remplacement complet** | Efface participants, blocs, circuits et **réussites** de la compétition active, puis importe. | On branche le classeur d'une nouvelle édition sur une base qui porte encore l'ancienne |

Le remplacement exige la même confirmation que l'effacement (§ 2.5). Il ne
touche **pas** au classeur Google : il n'efface que le serveur.

**Le classeur est lu AVANT que quoi que ce soit soit effacé.** Si Google refuse
ou ne répond pas, rien n'a bougé — on ne veut pas d'une base vide et d'un import
qui n'a jamais eu lieu. C'est le même ordre que celui retenu à la spec 015 pour
le mode « nouvelle compétition », et pour la même raison.

Ce que l'import ne changera pas : un participant ajouté **à la main** pendant la
compétition n'est jamais écrasé par une ligne du classeur qui porterait le même
dossard. La règle vient de la spec 013, elle est déjà codée, elle reste — et en
mode remplacement elle ne s'applique plus, puisqu'il n'y a plus personne à
écraser.

### 2.4 Archiver une édition terminée

Archiver, c'est **figer** puis **clôturer** :

1. Le serveur calcule le classement complet et le range, avec les données
   brutes qui l'ont produit, dans une ligne de la table `archive`.
2. La compétition passe en statut `terminée`.
3. **Rien n'est effacé.** L'archive et les données coexistent — effacer est un
   geste séparé, qu'on fait quand on veut, ou jamais.

L'archive vit **dans la base**, pas dans un fichier à côté. La raison est
mesurable : `climbcontest-sauvegarde` recopie la base SQLite toutes les nuits et
relit sa copie ; il ne recopie **rien d'autre**. Une archive posée dans
`shared/archives/` serait le seul fichier de la VM sans sauvegarde — et ce
serait précisément le fichier qu'on ne peut pas reconstruire.

Elle reste **téléchargeable** depuis la console : un JSON daté, pour en avoir
une copie hors de la VM.

### 2.5 Effacer les données du serveur

Un bouton, une **fenêtre de confirmation**, et un périmètre écrit noir sur
blanc :

| Effacé | Conservé |
| --- | --- |
| Participants, blocs, circuits de la compétition active | Les autres compétitions |
| Réussites et réaffectations de dossard | Les comptes de la console |
| — | **Les archives** |
| — | **Le classeur Google** — pas une cellule n'est touchée |

La fenêtre affiche les **compteurs réels** avant d'effacer (« 196 participants,
50 blocs, 3 120 réussites »), et le bouton ne s'arme que si l'on a frappé
`EFFACER`. Les chiffres ne sont pas décoratifs : c'est le seul contrôle qui
attrape le cas « je croyais être sur la base de test ».

**Refusé sur une compétition `en_cours` — sauf forçage explicite** (Adrien,
01/09 : « oui je veux pouvoir le forcer »). La fenêtre affiche alors une case
supplémentaire, décochée :

```
⚠ Cette compétition est marquée EN COURS.
[ ] Effacer quand même
[ EFFACER                    ]
```

**Le forçage ne remplace pas la confirmation, il s'y ajoute.** Cocher la case
sans frapper `EFFACER` ne fait rien ; frapper `EFFACER` sans cocher la case sur
une compétition `en_cours` donne le 409. Deux gestes, deux intentions.

Le même forçage arrive sur le mode « nouvelle compétition » de la spec 015, qui
porte exactement la même garde : une seule règle, deux points d'entrée, pas deux
comportements à retenir.

Maintenant que le statut se règle à la main (§ 2.1), cette garde veut enfin dire
quelque chose — et le forçage est là pour le cas où elle se trompe quand même.

Après l'effacement, `catalogue_version` prend une valeur **jamais servie**
(`prochaine_version_catalogue()`) : sans ça, les vingt-cinq téléphones gardent
la liste de l'édition précédente et affichent un nom d'an dernier sur un dossard
tout neuf. C'est le correctif du 30/08, et il s'applique ici mot pour mot.

### 2.6 Revoir une archive

La page « Archives » liste les éditions, la plus récente en tête : nom, date,
nombre de participants, de blocs, de réussites, date de l'archivage. Trois
boutons par ligne — **Revoir**, **Télécharger**, **Supprimer**.

« Revoir » ouvre **la vraie page de résultats**, celle du vidéoprojecteur, avec
son podium, ses colonnes et ses scratchs — alimentée par le classement figé au
lieu de la base. Pas une seconde page à maintenir : le même gabarit, une source
de données différente.

**C'est de la consultation, et rien d'autre** (Adrien, 01/09 : « cette visu ne
doit être que temporaire, c'est juste de la consultation »). Concrètement :

- rien n'est restauré en base, rien ne redevient actif ;
- la page publique `/` continue d'afficher la compétition **active**, pendant
  qu'on regarde une archive dans un autre onglet ;
- le rafraîchissement automatique est **coupé** — les données sont figées, les
  relire toutes les 15 s n'aurait aucun sens, et l'âge du calcul non plus. Le
  bandeau affiche « Archive du <date> » à la place ;
- fermer l'onglet suffit à en sortir.

La page d'archive est **derrière la session de la console**, contrairement à la
page publique. Le classement d'une édition passée n'a pas à être servi à qui
passe, et il porte des noms de mineurs.

## 3. Ce qui a été tranché par Adrien (01/09)

| Question | Réponse |
| --- | --- |
| Ce que veut dire « archiver » | Clôturer **et** produire un fichier — mais **archivé sur la VM**, avec une page qui liste les archives et un bouton pour revoir les résultats. Consultation temporaire uniquement |
| Comment tester l'écriture | Aller-retour sur une cellule de l'onglet `Import` |
| Jusqu'où va « effacer » | La compétition active, **serveur seul** — le classeur Google n'est pas touché. Avec une **fenêtre** de confirmation |
| Le mode « mise à jour » de l'import | Ajoute **et** corrige — le comportement actuel |
| Le statut, et la garde `en_cours` (porte 2) | Le statut devient **réglable depuis la console**, la garde est **conservée**, et l'effacement peut être **forcé** |

## 4. Critères d'acceptation

### Tester l'écriture

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A1 | Le test écrit dans le coin de la grille, relit, et efface | Faux classeur : `values.update` puis `values.get` puis `values.clear` sur la même cellule, dans cet ordre |
| A2 | Une feuille partagée en lecture seule est **détectée** | Le faux service lève sur `values.update` → rapport `ecriture: false`, message de Google repris, et une phrase qui dit de partager la feuille en modification |
| A3 | Une cellule témoin non vide interrompt le test avant d'écrire | Aucun `values.update` appelé, rapport explicite |
| A4 | L'effacement final échoué est signalé, avec le nom de la cellule | Rapport `restauree: false`, la cellule en clair |
| A5 | Une plage protégée sur `Import` est signalée | Avertissement dans le rapport |
| A6 | Le test en lecture continue de faire ce qu'il faisait | Les critères A6 et A14 de la spec 015 restent verts |

### Importer

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A7 | Mode « mise à jour » : comportement d'aujourd'hui, à l'octet près | Les tests de `test_import.py` passent inchangés |
| A8 | Mode « remplacement » sans confirmation : refusé, rien touché | 400, compteurs identiques avant/après |
| A9 | Mode « remplacement » : base vidée **puis** repeuplée depuis le classeur | Un participant absent du classeur a disparu, un participant du classeur est là, les réussites sont à zéro |
| A10 | Mode « remplacement » quand la **lecture** du classeur échoue : la base n'a pas bougé | 502, compteurs identiques |
| A11 | Le remplacement ne touche pas au classeur Google | Le faux classeur ne voit aucun appel d'écriture |
| A12 | Le rapport d'import dit le mode employé | Champ `mode` dans la réponse |

### Effacer

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A13 | Efface participants, blocs, circuits, réussites et réaffectations de la compétition active | Compteurs à zéro |
| A14 | N'efface **ni** les autres compétitions, **ni** les comptes, **ni** les archives | Compteurs de la seconde compétition et de `Utilisateur` inchangés |
| A15 | Sans le mot `EFFACER` : 400, rien touché | Compteurs inchangés |
| A16 | Sur une compétition `en_cours` sans forçage : 409, message qui renvoie vers « archiver » | Rien touché |
| A17 | `catalogue_version` prend une valeur jamais servie | Strictement supérieure au maximum de **toutes** les compétitions d'avant |
| A18 | Le classement relu juste après l'effacement est vide | Le cache est invalidé — sans ça il resterait périmé jusqu'à 5 s |
| A19 | Aucun appel au classeur Google | Le faux classeur ne voit rien |

### Archiver et consulter

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A20 | Archiver crée une ligne `archive` portant le classement complet et les données brutes | Le JSON relu contient les mêmes rangs que `/api/public/classement` |
| A21 | Archiver passe la compétition en `terminée` et **n'efface rien** | Statut changé, compteurs inchangés |
| A22 | Archiver une compétition sans aucune réussite : accepté, avec un avertissement | 200, `avertissements` non vide |
| A23 | La liste des archives est rendue **sans désérialiser** le JSON | Les compteurs viennent de colonnes dédiées |
| A24 | « Revoir » affiche le classement figé dans la page de résultats | La page reçoit le classement de l'archive, pas celui de la base |
| A25 | Consulter une archive ne touche ni la base, ni la compétition active | `/api/public/classement` renvoie toujours la compétition active |
| A26 | En mode archive, la page ne se rafraîchit pas et affiche la date de l'archive | Aucun second `fetch`, bandeau « Archive du … » |
| A27 | **Archiver puis effacer** : l'archive reste complète et consultable | Le scénario de bout en bout, en un test |
| A28 | Le téléchargement sert un JSON daté | `Content-Disposition`, nom de fichier avec la date |
| A29 | Supprimer une archive exige `ADMIN` et une confirmation | 403 en organisateur, 400 sans confirmation |

### Le statut et le forçage

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A32 | `POST /admin/competition/statut` accepte les trois valeurs et les écrit | Statut relu en base après chacune |
| A33 | Une valeur inconnue est refusée | 400, statut **inchangé** |
| A34 | Effacer une compétition `en_cours` **avec** forçage : accepté | 200, données effacées |
| A35 | Le forçage seul, sans le mot `EFFACER` : refusé | 400, rien touché |
| A36 | `relier(mode=reinitialiser)` gagne le même forçage | Accepté sur `en_cours` avec forçage, 409 sans |
| A37 | La console affiche le statut réel après changement | `GET /admin/classeur` renvoie le nouveau statut |
| A38 | Un scan de juge ne change **pas** le statut | Une réussite enregistrée sur une compétition `preparation` la laisse `preparation` |

### Les rôles

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A30 | Effacer, archiver, remplacer, supprimer une archive : `ADMIN` seul | 403 en organisateur sur les quatre routes |
| A31 | Lister, revoir, télécharger une archive, importer en mise à jour, régler le statut : `ORGANISATEUR` | 200 en organisateur, 401 sans session |

## 5. Les cas limites, et ce qu'on en fait

**Aucune compétition active.** Les vues « Compétition » et « Archives »
s'ouvrent quand même. La première le dit et n'offre rien ; la seconde continue
de lister les archives — elles n'ont pas besoin d'une compétition active pour
exister, et c'est justement dans cet état-là qu'on vient les consulter.

**Archiver deux fois la même édition.** Autorisé. On archive avant une
correction, on corrige, on ré-archive : deux lignes, deux horodatages, la plus
récente en tête. Aucune raison d'interdire ce qui ne coûte que quelques
centaines de kilo-octets.

**Une archive volumineuse.** **Mesuré** le 01/09 sur une édition à l'échelle
réelle — 196 grimpeurs, 50 blocs, 3 031 réussites : **701 Ko**, calculée en
44 ms. Dont 576 Ko de données brutes et 124 Ko de classement.

L'estimation portée ici avant l'implémentation disait « de l'ordre de 300 Ko » :
elle était basse d'un facteur 2,3. C'est la mesure qui fait foi, et c'est
pourquoi le plan la prévoyait.

Ça ne change pas la conception. SQLite range 701 Ko sans discuter, et dix
éditions font 7 Mo — la base de production en pèse aujourd'hui moins de deux.
Ce que ça confirme, en revanche, c'est que **la liste ne doit jamais charger la
colonne `contenu`** : dix archives ouvertes pour afficher dix nombres feraient
7 Mo de lecture par affichage de page. Elle ne le fait pas (`with_entities`),
et le critère A23 est là pour que ça le reste.

À noter pour plus tard : **les données brutes pèsent 80 % de l'archive** pour un
usage qui n'existe pas encore. Le jour où le volume gênerait, c'est la première
chose à comprimer ou à retirer — pas le classement, qui est ce qu'on consulte.

**Le format d'archive change un jour.** Chaque archive porte un numéro de
`format`. Une archive d'un format qu'on ne sait plus lire s'affiche dans la
liste et reste téléchargeable ; seul « Revoir » se désactive, avec la raison.
C'est ce qui évite qu'un changement de moteur de classement rende les vieilles
archives illisibles.

**Effacer sans avoir archivé.** Autorisé — on efface souvent des données de
test, qui ne méritent aucune archive. Mais si la compétition porte des réussites
et n'a **jamais** été archivée, la fenêtre de confirmation le dit avant, en une
ligne. Elle n'empêche pas ; elle prévient.

**Les compétitions déjà en base portent un statut faux.** Elles ne se réparent
pas toutes seules — rien ne devine ce qu'aurait dû être `preparation` ou
`terminee`. Les trois boutons du § 2.1 servent aussi à ça : la base de dev
passe de `en_cours` à `preparation` en un clic, et redevient effaçable. **Aucune
migration ne touchera aux statuts existants** : réécrire en masse un champ dont
on vient d'établir qu'il n'a jamais rien voulu dire, c'est remplacer une valeur
fausse par une valeur inventée.

**Le classeur reste relié après un effacement.** C'est voulu : on efface le plus
souvent pour réimporter la même feuille proprement. Changer de classeur reste le
geste de la vue « Classeur ».

## 6. Hors périmètre

- **Créer ou choisir une compétition depuis la console.** Toujours hors sujet,
  comme à la spec 015 : ces écrans travaillent sur la compétition **active**.
  Une édition suivante réutilise la même ligne, vidée puis réimportée — et
  l'archive porte la mémoire de la précédente. Gérer plusieurs compétitions de
  front est un autre écran, et une autre spec.
- **Restaurer une archive dans la base.** Adrien a été explicite : la
  consultation est temporaire. Restaurer poserait la question de ce qu'on fait
  des données en place, et n'a aujourd'hui aucun usage.
- **Copier le classeur Google dans le Drive.** Le jeton n'a que le scope
  `spreadsheets`. C'était déjà hors périmètre à la spec 015, ça le reste.
- **Purger automatiquement les vieilles archives.** Quelques mégaoctets par
  décennie. Le jour où ça compte, ce sera un bouton de plus, pas une politique.

## 7. Ce qu'on ne fera pas, et pourquoi

**Le test d'écriture n'écrira pas dans la matrice.** La tentation serait de
tester là où le miroir écrit vraiment — une cellule `D2:…` — pour prouver le
droit exactement où il sert. On ne le fera pas : cette zone porte les réussites
de la compétition, et un test qui écrit puis efface au mauvais endroit détruit
une donnée réelle sans que rien ne le dise. Le coin de la grille prouve le droit
d'écrire sur la feuille ; la détection des plages protégées couvre le reste du
risque. C'est moins précis, et infiniment moins dangereux.

**Le statut ne se déduira pas de l'activité.** Il serait tentant de faire passer
une compétition en `en_cours` à la première réussite reçue, et en `terminée`
après quelques heures de silence. On ne le fera pas : un bénévole qui essaie son
téléphone le jeudi soir armerait le garde-fou, et une pause déjeuner le
désarmerait. Un statut deviné se trompe précisément les jours où il compte. Trois
boutons et un humain valent mieux qu'une heuristique — d'autant que ce champ ne
commande rien d'autre.

**L'effacement ne touchera pas au classeur Google.** La spec 015 offre déjà ce
geste-là, lié à un changement de feuille, avec sa confirmation et son refus en
`en_cours`. En dupliquer une seconde porte d'entrée, c'est doubler les chances
de se tromper de bouton sur l'action la plus destructrice du produit. Le § 2.5
le dit à l'écran : « le classeur Google n'est pas touché ».
