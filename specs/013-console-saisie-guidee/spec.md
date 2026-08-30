# Spec 013 — Saisie guidée et navigation de la console

> **Statut : rédigée, en attente de validation (porte 2).**
> Demandée par Adrien le 30/08/2026, en quatre messages successifs.

## 1. Le besoin

La console d'administration livrée par la [spec 005](../005-admin-console/)
fonctionne, mais elle fait **saisir à la main ce qui devrait être choisi**. Le
formulaire d'ajout d'un participant présente quatre champs de texte libre — nom,
prénom, club, catégorie — plus un dossard à taper. Trois conséquences, toutes
constatées ou mesurables aujourd'hui :

**La base contient déjà une catégorie fantôme.** Relevé sur la production le
30/08 :

| Catégorie | Participants |
| --- | --- |
| `U13 H` | 26 |
| `U13 M` | **1** |

`U13 M` n'existe pas. Quelqu'un a écrit « M » pour masculin là où le classeur
écrit « H » pour homme. Ce grimpeur est **seul dans sa catégorie** : il est
premier d'un classement d'une personne, et absent du vrai `U13 H`. Un champ
libre produit ce genre d'erreur ; une liste déroulante ne le peut pas.

**Le jour J, on tape au lieu de choisir.** Une inscription de dernière minute se
fait debout, avec la file d'attente devant soi. « Annonay Escalade » fait dix-sept
caractères ; il y a cinq clubs. Les choisir prend un geste, les taper en prend
dix-sept — et chaque frappe est une occasion de créer un sixième club qui n'existe
pas.

**Le dossard est demandé alors qu'il est déductible.** L'organisateur doit
savoir quel numéro est libre. Il ne le sait pas : il faut chercher dans la liste
au moment où on a le moins de temps.

S'ajoute un défaut d'ergonomie signalé directement : la navigation par **onglets
horizontaux** (huit pastilles dans une barre qui défile latéralement) n'est pas
le geste attendu. Les autres applications d'Adrien — guestFlow en particulier —
utilisent toutes le motif standard : **barre latérale, ouverte par un bouton
burger à gauche**.

## 2. Ce qu'on fait

Cinq changements, tous dans la console. **Aucun ne touche au moteur de
classement, à l'API des juges, ni au miroir vers le classeur.**

### 2.1 La catégorie devient une liste déroulante

À l'ajout d'un participant, `catégorie` n'est plus un champ libre mais une liste
déroulante. Elle est remplie avec **les catégories déjà connues de la
compétition en cours**, et se termine par une entrée « Autre… » qui révèle un
champ texte pour en saisir une nouvelle.

La liste est **dérivée, pas stockée** : c'est l'ensemble des valeurs distinctes
portées par les participants. Ajouter une catégorie, c'est donc simplement
l'écrire une fois dans « Autre… » — elle rejoint la liste dès que le participant
est enregistré. Aucune table, aucun écran de gestion, rien à tenir à jour.

> **Décision D2, tranchée par Adrien le 30/08.** La source est la base, pas
> l'onglet `Listes!A5:B14` du classeur (qui porte pourtant la liste officielle
> catégorie → circuit). Raison décisive : le jeton Google **n'est pas sur la
> VM** — un import est aujourd'hui impossible, une liste qui en dépendrait
> serait vide. Les catégories en base viennent de toute façon du classeur, par
> le dernier import.

### 2.2 Le club aussi

Même mécanique, même « Autre… ». Cinq clubs sont connus aujourd'hui : Annonay
Escalade, La Grimpe, Les Lezards Vagabonds, Roc N'Potes, Vertic'Ardeche.

### 2.3 Tout ce qui est tapé à la main est formaté avant d'être enregistré

Le formatage a lieu **côté serveur**, dans la couche métier — pas dans le
navigateur. Une règle appliquée seulement à l'interface serait contournée par le
premier appel direct à l'API.

**Nom et prénom — casse stricte.** Une majuscule au début de chaque mot, le
reste en minuscules, **sans exception** : « MARTIN » donne « Martin ». Taper son
nom en capitales est un réflexe courant sur un formulaire, et un nom de famille
n'est jamais un sigle.

**Club — les sigles sont préservés.** Même règle, mais un mot déjà entièrement
en majuscules et long de **2 à 5 caractères** est laissé tel quel : « CAF
Annonay » ne devient pas « Caf Annonay ». Les clubs portent des sigles, les
personnes non.

> **Décision D1, tranchée par Adrien le 30/08 : les deux cas sont traités
> séparément.** C'est la recommandation de la question ouverte Q3, désormais
> close.

Les séparateurs reconnus sont l'espace, le trait d'union et l'apostrophe
(droite `'` et typographique `’`) — sans quoi « jean-luc » donnerait
« Jean-luc » et « roc n'potes » donnerait « Roc N'potes », alors que le club
s'appelle « Roc N'Potes ».

**Catégorie — tout en majuscules, et l'espace avant le genre est garanti.**
Espaces multiples réduits à un seul, et **une catégorie qui se termine par `H`
ou `F` collé à un chiffre reçoit l'espace qui manque** :

| Saisi | Enregistré |
| --- | --- |
| `u13 f` | `U13 F` |
| `U13F` | `U13 F` |
| `u13f` | `U13 F` |
| `U13  H` | `U13 H` |

> **Décision D4, ajoutée par Adrien le 30/08.** Sans cette règle, « U13F » et
> « U13 F » seraient deux catégories distinctes dans la liste déroulante, et
> deux classements séparés. C'est le même défaut que le `U13 M` existant, sous
> une autre forme.

L'insertion de l'espace ne se déclenche **que** si le caractère précédent est un
chiffre. Une catégorie qui finirait par `F` sans être un genre n'est donc jamais
coupée.

### 2.4 Le dossard n'est plus saisi : il est attribué

Le champ « dossard » disparaît du formulaire d'ajout. À la création, le serveur
attribue **le plus petit numéro libre** de la compétition — un trou dans la
suite s'il y en a un, sinon le suivant du plus grand (décision D3).

Ce qui **ne change pas** : le bouton « Changer le dossard » de la liste des
participants, et la règle métier de la [spec 002](../002-reliable-success-storage/)
qu'il applique — *un dossard portant des réussites ne peut pas changer de main*.
Attribuer et réaffecter restent deux gestes distincts.

### 2.5 La navigation passe en barre latérale

Les huit pastilles horizontales sont remplacées par le motif standard, celui de
guestFlow :

- un **bouton burger à gauche** dans l'en-tête ;
- une **barre latérale de 240 px** listant les sections, celle en cours mise en évidence ;
- **au-delà de 900 px de large** : barre toujours visible, burger masqué ;
- **en dessous** : barre masquée, ouverte par le burger, par-dessus le contenu avec un voile ; se referme au choix d'une section, au clic sur le voile, ou par `Échap`.

### 2.6 La page « Dossards » suit

Le champ « catégorie » de l'onglet d'impression devient lui aussi une liste
déroulante, alimentée par la même source. Il garde une entrée vide qui signifie
« toutes les catégories ». Le champ « un seul dossard » ne change pas.

## 3. Ce qu'on ne fait pas

- Pas d'écran de gestion des catégories et des clubs (renommer, fusionner,
  supprimer). La liste est dérivée de l'usage.
- Pas de correction rétroactive du `U13 M` existant. C'est une modification de
  donnée de compétition, elle se fera à la main et en connaissance de cause —
  voir la question ouverte Q1.
- Pas de lecture de `Listes!A5:B14`. Reportée, faute de jeton Google sur la VM.
- Pas de renumérotation des dossards existants.

## 4. Critères d'acceptation

| # | Critère | Vérifié par |
| --- | --- | --- |
| A1 | La catégorie et le club sont des listes déroulantes remplies avec les valeurs connues de la compétition | test de route + essai manuel |
| A2 | « Autre… » permet d'enregistrer une valeur inédite, qui apparaît dans la liste au chargement suivant | test de route |
| A3 | `«  jean-luc  »` enregistré donne `Jean-Luc` ; `« roc n'potes »` donne `Roc N'Potes` | test unitaire |
| A4 | `« CAF annonay »` en **club** donne `CAF Annonay` — le sigle survit | test unitaire |
| A4bis | `« MARTIN »` en **nom** donne `Martin` — pas de sigle sur une personne | test unitaire |
| A5 | `« u13 f »` donne `U13 F` | test unitaire |
| A5bis | `« U13F »` donne `U13 F` — l'espace avant le genre est rétabli | test unitaire |
| A6 | Le formatage s'applique aussi à un appel direct de l'API, sans passer par la console | test de route |
| A7 | Un participant créé sans dossard en reçoit un automatiquement | test de route |
| A8 | Avec les dossards 1, 2, 3, 7, 8 en base, le suivant attribué est **4** | test unitaire |
| A9 | Avec les dossards 1..109 en base, le suivant attribué est **110** | test unitaire |
| A10 | Deux créations simultanées ne reçoivent jamais le même dossard | test de concurrence |
| A11 | La règle « un dossard portant des réussites ne se réaffecte pas » est intacte | tests existants, non modifiés |
| A12 | Au-delà de 900 px la barre latérale est visible et le burger absent ; en dessous l'inverse | essai manuel + test Playwright |
| A13 | `Échap`, le voile et le choix d'une section referment la barre en mode étroit | test Playwright |
| A14 | L'onglet Dossards propose la liste des catégories, entrée vide = toutes | test de route |
| A15 | Aucune régression : les 3 suites de tests de la console passent | `pytest` |

## 5. Cas limites

| Situation | Comportement attendu |
| --- | --- |
| Aucune compétition active | Les listes reviennent vides, le formulaire reste utilisable via « Autre… » |
| Base sans aucun participant | Listes vides, « Autre… » est le seul chemin — c'est le cas du tout premier ajout |
| Catégorie saisie identique à une existante après formatage (`« u13 h »`) | Elle rejoint l'existante, pas de doublon créé |
| Club saisi avec des espaces en trop | Réduits avant enregistrement |
| « Autre… » choisi mais champ laissé vide | Traité comme non renseigné (le champ est facultatif), pas comme une erreur |
| Tous les dossards de 1 à N pris, N très grand | Le suivant est N+1, aucune limite imposée |
| Deux organisateurs créent un participant en même temps | La contrainte d'unicité rejette le second, qui retente avec le numéro suivant |
| Le classeur importe plus tard un dossard attribué à la main | **Risque connu — voir Q2** |

## 6. Décisions et questions

**Q1 — Le `U13 M` existant.** Faut-il le corriger, et le basculer en `U13 H` ?
C'est une modification de donnée de compétition ; elle ne sera pas faite sans
accord explicite. Recommandation : oui, mais après novembre, ou avant si cette
compétition n'est que du jeu d'essai.

**Q2 — CLOSE le 30/08. L'écrasement par un import ultérieur.**

> Réponse d'Adrien : « sécurise pour faire en sorte qu'on ne prenne que des
> emplacements de dossard libre, et protège pour que 2 navigateurs ne puissent
> pas prendre le même numéro s'ils font une demande en même temps. »
>
> Les deux points sont couverts par l'architecture §3. La protection de
> l'importateur décrite ci-dessous est **retenue également**, au titre du même
> « sécurise » : elle ferme le dernier chemin par lequel un dossard déjà
> attribué peut changer de propriétaire en silence.

 L'importateur retrouve un
participant **par son dossard** (`importer.py`, `filter_by(dossard=...)`). Un
participant ajouté à la main et qui reçoit le dossard 110 sera **écrasé** —
nom, prénom, club, catégorie remplacés — si un import du classeur apporte un
jour un dossard 110. Ses réussites, elles, restent attachées à la ligne : elles
changeraient donc de propriétaire en silence.

La numérotation à partir de 900 aurait supprimé le risque ; elle n'a pas été
retenue. Cette spec propose donc, à valider : **l'importateur refuse d'écraser
un participant dont `source = manuel`** et le signale dans son rapport, au lieu
de le remplacer sans bruit. Une ligne de code, et le rapport d'import existe
déjà pour ça.

**Q3 — CLOSE le 30/08 : les cas sont traités séparément** (voir §2.3). Énoncé
d'origine, conservé pour mémoire :

**Q3 — Un nom tapé en capitales.** La règle des sigles préserve les mots de 2 à
5 caractères tout en majuscules. « MARTIN » (6 caractères) devient donc
« Martin », mais « DUPUY » (5) resterait « DUPUY ». La question posée le 30/08
présentait les deux comportements de façon contradictoire — ce point mérite
d'être tranché explicitement. Recommandation : appliquer la préservation des
sigles **au club seulement**, et un formatage strict au nom et au prénom, où la
saisie en capitales est un réflexe fréquent et jamais un sigle.
