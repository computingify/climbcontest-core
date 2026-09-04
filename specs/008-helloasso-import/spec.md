# Spec 008 — Les inscriptions en ligne arrivent toutes seules

> **Statut : maquette validée par Adrien le 04/09 (« c'est nickel, implémente »),
> lots 1 à 7 livrés le jour même. Reste le lot 8 — la recette sur le bac à
> sable — qui demande une clé d'API et n'est donc pas de moi.**
>
> **D10 et D11 sont restées sans réponse** : mes propositions ont été appliquées
> — une catégorie corrigée à la main est protégée, et le vert de la maquette est
> conservé. Un mot suffit pour changer l'une ou l'autre.
>
> La maquette de tous les écrans est dans
> [`maquettes/inscriptions.html`](maquettes/inscriptions.html).
>
> Numéro **008** : réservé depuis le 28/08 dans
> [`docs/specs-index.md`](../../docs/specs-index.md) sous le nom
> `helloasso-import`.

## 1. Le besoin, tel que le terrain le pose

[`docs/contraintes-metier.md` §3](../../docs/contraintes-metier.md), recueilli
auprès d'Adrien le 28/08 :

1. **HelloAsso est la plateforme d'inscription** à la compétition.
2. **Des inscriptions se font sur place**, le jour même. L'import est un **flux
   d'alimentation, jamais la source unique**.
3. **Il faut un rapprochement** : quelqu'un peut s'inscrire en ligne *et* se
   présenter au guichet, avec **validation humaine**.
4. **Ça doit être temps réel, et visible** : « il faut pouvoir avoir un dashboard
   dans la page admin et le voir sur cet écran ». Derrière chaque inscription il
   y a un geste physique — **imprimer un dossard et l'apporter**.

Aujourd'hui, la seule trace de HelloAsso dans `climbcontest-core` est une
constante jamais écrite :

```python
SOURCE_CLASSEUR, SOURCE_MANUEL, SOURCE_HELLOASSO = "classeur", "manuel", "helloasso"
```

Le geste réel, en novembre 2025 : exporter un tableur, le recoller à la main
dans l'onglet `Listes`, importer. Une fois. Ce qui arrive après l'export
n'arrive jamais.

## 2. La règle des catégories — FFME, relevée le 04/09/2026

C'est la pièce que la décision **D1** met au centre, et elle est **calculable**.

« U » veut dire *under*. **U13 = moins de 13 ans**, et c'est le **plus petit
Under qui l'emporte**. Deux précisions font tout le reste :

- c'est l'**année de naissance** qui compte, pas la date : personne ne change de
  catégorie le jour de son anniversaire ;
- l'année de référence est celle où **finit** la saison. La saison FFME va du
  1ᵉʳ septembre au 31 août, donc une compétition de novembre 2026 est dans la
  saison 2026-2027 et sa référence est **2027**. C'est ce qui fait qu'« ils
  démarrent leur année dans une catégorie et y restent toute l'année ».

```
age       = annee_de_reference - annee_de_naissance
categorie = le plus petit U(n) tel que age < n

annee_de_reference(jour) = jour.year + 1 si jour.month >= 9 sinon jour.year
```

Vérification contre le tableau publié pour la saison 2025-2026 (référence 2026) :

| Catégorie | Années de naissance | Âge en 2026 | Contrôle |
| --- | --- | --- | --- |
| U11 | 2016 – 2017 | 9 – 10 ans | 10 < 11 ✓ |
| U13 | 2014 – 2015 | 11 – 12 ans | 12 < 13 ✓ |
| U15 | 2012 – 2013 | 13 – 14 ans | 14 < 15 ✓ |
| U17 | 2010 – 2011 | 15 – 16 ans | 16 < 17 ✓ |
| U19 | 2008 – 2009 | 17 – 18 ans | 18 < 19 ✓ |
| U21 | 2006 – 2007 | 19 – 20 ans | 20 < 21 ✓ |

> ⚠️ **La version du 03/09 de cette spec était fausse d'un an** : elle prenait
> l'année où la saison *commence*. Pour une compétition de novembre 2026, U13
> est **2015-2016**, pas 2014-2015. L'erreur est corrigée ici, et le test
> d'acceptation du barème est précisément la reproduction du tableau ci-dessus.

Conséquence : **le barème n'est plus une saisie**. Il se déduit de la date de la
compétition et des catégories de l'édition. Une correction à la main reste
possible, repliée — une fédération peut changer ses tranches, et ce jour-là on
ne veut pas attendre une release.

## 3. Ce que l'API HelloAsso donne — vérifié le 03/09/2026

| Fait | Conséquence pour nous |
| --- | --- |
| **Clé d'API depuis le back-office du club**. Rôle `OrganizationAdmin`, privilèges `AccessPublicData`, `AccessTransactions` | Suffisant. **Aucun partenariat à demander** |
| `access_token` **30 min**, `refresh_token` **30 jours**, quotas d'authentification **50/h** | Le jeton se garde et se rafraîchit ; il ne se redemande pas |
| Le `refresh_token` **tourne** : réutiliser A crée C **et révoque B** | Deux rafraîchissements simultanés se **révoquent l'un l'autre** → verrou en base |
| `GET .../items` — **un article = un inscrit**, `item.id` stable et unique | C'est la clé qui empêche de réimporter |
| **Un `order` peut contenir plusieurs `items`** — un parent, deux enfants | Le **numéro de commande n'est pas une clé de personne**. Voir §5 |
| `withDetails=true` → `customFields[]` (`name`, `type`, `answer`) | C'est là que vivent l'année de naissance, le genre et le club |
| `sortField=UpdateDate` + `from=` | Relevé incrémental, et une annulation ancienne reste visible |
| Fin de pagination = **tableau vide**, pas absence de jeton ; `totalCount = -1` | Boucle écrite d'après leur algorithme |
| `item.state` ∈ `Waiting`…`Canceled`…`Abandoned` | Seuls `Processed` et `Registered` valent inscription |
| `payer` ≠ `user` : le payeur est le parent | On inscrit `user` |
| Webhook : signature HMAC **réservée aux partenaires**, corps sans `customFields` | Il ne peut pas être une source de données → **D3** |

## 4. Le périmètre

### On fait

| # | Quoi | Dépend de HelloAsso ? |
| --- | --- | --- |
| **F1** | La règle FFME calculée, dans un module à part | **non** |
| **F2** | L'écran **Catégories** : le barème déduit, et « Appliquer à tous les inscrits » | **non** |
| **F3** | La colonne **Source** — `G` classeur, `H` HelloAsso, `M` guichet | **non** |
| **F4** | La **sélection par cases** pour l'impression, qui remplace la tuile « Imprimer les fiches » | **non** |
| **F5** | Le **crayon** : la ligne s'édite sur place, listes déroulantes avec création | **non** |
| **F6** | L'ajout manuel : **année ⇄ catégorie**, chacune propose l'autre | **non** |
| **F7** | Relier le compte HelloAsso, choisir le formulaire, désigner **trois champs** | oui |
| **F8** | Relever les inscriptions en continu, et à la demande | oui |
| **F9** | **Ne pas réimporter**, et **rapprocher** — deux mécanismes distincts | oui |
| **F10** | La vue **Inscriptions** et la **pastille** du bandeau | oui |
| **F11** | Une annulation HelloAsso **se voit** | oui |
| **F12** | `tools/dump_helloasso.py`, lecture seule | oui |

**F1 à F6 ne dépendent pas de HelloAsso** et peuvent être livrées seules. C'est
ce qui rend le plan robuste : si la clé d'API tarde, la moitié utile est déjà en
production.

### On ne fait pas

| Quoi | Pourquoi |
| --- | --- |
| Le **tarif** comme critère | *« Pour la compétition tout le monde paye le même tarif »* (04/09). Il ne discrimine rien : ni la catégorie, ni le genre |
| Écrire chez HelloAsso | Lecture seule, sans exception |
| Encaisser un paiement | Le club encaisse déjà |
| Recopier les inscriptions dans le classeur | Le classeur reçoit des réussites, pas des inscrits |
| Deviner une catégorie sans année | On refuse et on demande |

## 5. Ne pas réimporter, et rapprocher — deux mécanismes, deux clés

Les confondre est le piège de ce dossier.

| | **Ne pas réimporter** | **Rapprocher** |
| --- | --- | --- |
| La question | Ai-je déjà vu **cet article** ? | Cette personne est-elle déjà dans la liste ? |
| La clé | `item.id`, l'article HelloAsso | nom + prénom + club, la catégorie en contrôle |
| Où elle vit | Une contrainte SQL `UNIQUE(competition_id, article_id)` | Une fonction pure, testée par table de cas |
| Ce qu'elle protège | Un relevé qui repasse sur les mêmes articles toutes les 60 s | Le doublon entre deux origines |

**Pourquoi pas le numéro de commande comme clé anti-doublon** — et c'est la
réponse à la question posée le 04/09 : il est bien unique et fiable, mais **pour
une commande, pas pour une personne**. Un parent qui inscrit deux enfants
produit **une** commande et **deux** articles. S'en servir comme clé perdrait le
second enfant, silencieusement.

Il est gardé quand même, pour deux usages réels : **retrouver la fratrie**, et
**retrouver la commande dans le back-office** quand il faut joindre quelqu'un —
puisque D5 dit qu'on ne garde pas le courriel.

### La table de rapprochement

| Cas | Verdict |
| --- | --- |
| Aucun homonyme | **Nouveau.** Participant créé, dossard attribué |
| Nom + prénom + **club identiques** | **La même personne.** Rattachée, jamais dupliquée ; les champs vides sont complétés, les autres jamais écrasés |
| Nom + prénom identiques, **club différent** | **À trancher.** Les deux fiches côte à côte |
| Nom + prénom identiques, **club absent** d'un côté | **À trancher** |
| Rattachée, mais **catégorie différente** | Rattachée quand même, et **signalée** |
| **Année absente**, ou hors barème | **À trancher**, catégorie vide |
| **Genre indéterminé** | **À trancher** |
| Article `Canceled` / `Refused` / `Abandoned` / `Deleted` | Pas d'inscription. Si elle existait : **annulée**, et ça se voit |

La comparaison passe par les normalisations de `formatage.py` : minuscules,
accents retirés, tirets et apostrophes en séparateurs. « DUPONT Jean-Luc » et
« dupont jean luc » sont le même nom.


## 5 bis. Un seul formatage, et aucun doublon

> Demande d'Adrien le 04/09, après la livraison des sept lots : « débrouille-toi
> pour uniformiser le formatage, je ne veux pas de doublon ».

Un doublon naît toujours du même écart : **deux écritures d'un même nom qui ne
tombent pas sur la même clé**. Quatre chemins pouvaient le produire ; ils sont
fermés un par un.

### La clé d'identité vit avec les règles de mise en forme

`formatage.identite()` et `formatage.identite_club()` sont désormais dans
`formatage.py`, à côté des règles qui les rendent vraies — et non plus dans le
module qui rapproche les inscriptions. Si la mise en forme et la comparaison
vivent dans deux fichiers, elles dérivent : l'une gagne une règle que l'autre
n'a pas, et le doublon revient par la porte qu'on n'a pas refermée.

### Le classeur passe par le formatage

**Changement de doctrine.** La spec 013 tenait `sheets/importer.py` à l'écart,
au motif que « le classeur fait autorité sur ses propres lignes ». Ce
raisonnement se retourne : une erreur de casse dans le classeur n'est pas une
erreur qu'on veut voir, c'est une erreur qui **fabrique** un doublon.
« ANNONAY ESCALADE » importé et « annonay escalade » tapé au guichet donnaient
deux clubs, deux entrées dans la liste déroulante, et un rapprochement qui
échoue.

Ce qui reste vrai de la réserve d'origine : le formatage ne corrige que la
**forme**. Un nom mal orthographié, une catégorie inexistante, un dossard en
double restent signalés par le rapport d'import.

### La première orthographe fait référence

`formatage.club()` ne préserve un sigle que s'il est **déjà** en capitales :
« caf vivarais » devient donc « Caf Vivarais », à côté du « CAF Vivarais » du
classeur. Aucune liste de sigles connus ne réglerait ça — il faudrait la tenir à
jour pour chaque club de la région.

La règle retenue est plus simple et plus juste : **le club existe déjà sous une
forme, on reprend la sienne**. `contest.club_canonique()`, appliqué à l'import,
à la saisie et à l'édition en ligne.

### La garde à l'ajout

Créer un participant de même identité **et même club** est refusé — `409`, avec
le nom de celui qui est déjà là.

| Cas | Ce qui se passe |
| --- | --- |
| Même nom, **même club** | **Refusé.** La console montre la fiche et propose de la reprendre |
| Même nom, **club différent** | **Créé**, et signalé. Deux « Martin Lea » existent vraiment — c'est le risque R5 |
| Même nom, **club absent** d'un côté | **Créé**, et signalé. Deviner sur un champ vide ferait fusionner deux personnes |
| Refus forcé à la main | **Créé.** Deux cousins homonymes au même club, ça se voit une fois |

### Ce qui est déjà là

Une base qui a vécu avant le 04/09 porte peut-être des doublons. Une carte
**Doublons** paraît dans la vue Participants — et seulement s'il y en a. Elle
montre les fiches côte à côte et laisse choisir **laquelle garde son dossard** :
c'est celui qui est déjà imprimé et distribué, et le serveur n'a aucun moyen de
le savoir.

La fusion déplace les réussites, complète les champs vides, rattache les
inscriptions, et supprime la fiche absorbée.

## 5 ter. L'import devine

> « Lors des imports je veux un maximum d'automatisation. »

`helloasso/correspondance.py` reconnaît les champs du formulaire, de deux
façons — et la seconde est celle qui sert le plus :

1. **par le nom** : *date de naissance*, *né(e) le*, *sexe*, *genre*, *club*,
   *association*… ;
2. **par les réponses** : un champ dont **toutes** les réponses sont des
   écritures de genre connues *est* un champ de genre, quel que soit son
   intitulé. C'est le filet qui rattrape « Votre enfant est » et tous les
   libellés qu'aucune liste de mots-clés ne prévoira.

Une table intégrée reconnaît « Fille », « F », « Féminin », « Girl » — quatre
écritures de la même chose, qu'il serait absurde de faire saisir à chaque
édition. La table de l'édition, elle, **gagne toujours** : c'est un humain qui
l'a écrite.

Deux garde-fous, et ils comptent autant que l'automatisation :

- **un intrus suffit à disqualifier.** « La plupart ressemblent à des genres »
  ne vaut jamais reconnaissance : une erreur de colonne rangerait tout un
  formulaire de travers, et personne ne saurait où regarder ;
- **rien n'est deviné en silence.** Choisir le formulaire rend la liste de ce
  qui a été reconnu, et les réponses qu'on n'a **pas** su ranger. Ce sont les
  seules lignes qui demandent encore un geste.

## 5 quater. D'où viennent les inscrits — le réglage

> Demandé le 04/09 : « je voudrais pouvoir paramétrer si on récupère les
> informations des participants depuis la fiche Google Sheet ou HelloAsso ou
> les 2 [...] si HelloAsso n'est pas sélectionné je ne veux voir aucun
> paramétrage HelloAsso dans ma console. »

Un réglage par édition, dans **Général**, à trois positions :

| Position | Ce qui alimente la liste | Ce que la console montre |
| --- | --- | --- |
| **Le classeur seul** *(défaut)* | L'import du classeur | Aucun écran HelloAsso, aucune pastille |
| **HelloAsso seul** | Le relevé | Le classeur reste la carte du mur |
| **Les deux** | Les deux, et le rapprochement les fait se rencontrer | Tout |

### Ce que le réglage ne touche pas

Il porte sur les **participants**, et sur rien d'autre :

- le **miroir** continue d'écrire les réussites dans le classeur ;
- l'import du classeur continue d'apporter les **blocs et les circuits** — le
  classeur peut cesser de fournir les inscrits tout en restant la carte du mur.

Les confondre reviendrait à éteindre le miroir, ou à perdre le mur, en
décochant une case qui ne parle ni de l'un ni de l'autre.

### Désactiver n'efface rien

C'est la demande explicite, et c'est aussi la bonne façon de faire : **un
réglage qui efface en se désactivant n'est pas un interrupteur, c'est un
piège.** Décocher HelloAsso masque son paramétrage et arrête son fil ; la clé,
le formulaire et la correspondance reviennent tels quels à la réactivation.

Pour effacer vraiment, il y a **« Débrancher »** sur l'écran HelloAsso, qui dit
ce qu'il fait.

### La garde est dans le métier

`relever()` refuse si la source est éteinte — pas seulement la route et le fil.
Un relevé qui passerait par un troisième chemin ferait entrer des inscrits dans
une édition qui a déclaré ne pas s'en servir, et personne ne comprendrait d'où
ils viennent.

## 6. Les trois sources, montrées

| | Vient de | `Participant.source` |
| --- | --- | --- |
| **G** (bleu Google) | Le classeur Google | `classeur` |
| **H** (vert HelloAsso) | HelloAsso | `helloasso` |
| **M** (ocre de la console) | La saisie au guichet | `manuel` |

Les trois constantes existent depuis la spec 002 ; elles n'ont jamais été
montrées. **Deux pastilles sur une ligne** veut dire que le rapprochement a fait
son travail : la personne était dans le classeur, son inscription en ligne s'y
est rattachée. Aucune colonne nouvelle — c'est `source`, plus l'existence d'une
inscription liée.

## 7. Ce qu'on construit côté console

### F2 — L'écran Catégories

Le barème calculé (§2), la saison détectée, le nombre d'inscrits par catégorie,
un verdict d'une ligne, et deux boutons : **Appliquer à tous les inscrits**, et
*Corriger à la main…* replié.

« Appliquer » réécrit des catégories : il montre donc **l'avant / après** et le
nombre de lignes touchées, et son bouton se **maintient** (spec 027). Un inscrit
**sans année** n'est jamais touché — on ne remplace pas une catégorie saisie à
la main par un vide calculé.

### F4 — La sélection pour l'impression

Un bouton *Sélectionner pour impression* au-dessus de la liste. Il fait
apparaître une **bande ocre** — une case *Tout sélectionner*, le compte, le
bouton d'impression, *Annuler* — et une **colonne de cases**, les lignes
retenues teintées. C'est la teinte et la colonne qui disent qu'on est en train
de choisir ; aucune phrase d'explication n'est nécessaire.

La tuile **« Imprimer les fiches » disparaît**. Sa fonction « une catégorie
(vide = toutes) » survit autrement : un **filtre Catégorie** entre dans la barre
de la liste, on filtre, on *Tout sélectionne*, on imprime.

Le même mécanisme sert dans la vue *Inscriptions* : **une seule façon
d'imprimer** dans toute la console.

### F5 — Le crayon

Au bout de chaque ligne. Il ouvre **la ligne**, pas une fenêtre : les cellules
deviennent des champs, `Enregistrer` / `Annuler` au bout. Club et catégorie sont
des listes déroulantes avec **« + Créer… »**, et ce qui est créé passe par
`formatage.py` — `u13f` devient `U13 F`. C'est ce qui empêche « U13 M » de
cohabiter avec « U13 H » et de fabriquer un classement d'une personne, défaut
mesuré en production le 30/08.

Un dossard qui porte des réussites **refuse** de changer de main : règle de la
spec 002, l'édition en ligne ne l'ouvre pas.

### F6 — L'ajout manuel, dans les deux sens

Décision D8 : **l'année ou la catégorie**, jamais les deux obligatoires.

- On tape **2016** → la catégorie se propose : *U11*, il reste à choisir F ou H ;
- on choisit **U11 H** → le champ année affiche l'attendu : *2017 ou 2018*.

Une catégorie couvre deux années : la choisir ne peut pas remplir l'année,
seulement dire laquelle on attend. L'inverse, si.

### F7 — HelloAsso, trois champs à désigner

Le tarif ayant disparu, il ne reste que : **année de naissance** (obligatoire —
elle fait la catégorie), **genre** (obligatoire — le F ou le H, avec ses
réponses rangées : « Fille », « F », « Féminin » sont trois écritures de la même
chose), et **club** (facultatif).

Un seul refus d'enregistrement : **sans champ d'année, rien ne se calcule**. La
console le dit tout de suite plutôt que de laisser cent inscriptions s'empiler.

### F8 — Le relevé

Un fil de fond, sur le modèle du miroir vers le classeur : verrou en base, un
seul worker travaille, il ne meurt jamais.

| Situation | Cadence |
| --- | --- |
| Compétition `en_cours` | **60 s** |
| `preparation`, aujourd'hui ou demain | 5 min |
| Le reste du temps | 30 min |
| Pas de clé posée | **le fil ne démarre pas** |

### F10 — La vue Inscriptions, et la pastille

Trois piles — *À trancher*, *À imprimer*, *Faites* — rafraîchies toutes les
30 s. C'est le « dashboard » demandé le 28/08 : l'écran qu'on laisse ouvert.

La pastille du bandeau reprend la forme de celle de la spec 031, en ocre. Elle
compte *à trancher + à imprimer*, mène à la vue, et disparaît quand la pile est
vide.

### F11 — Une annulation se voit

Un article qui repasse en `Canceled` alors qu'il avait produit un participant ne
supprime **rien**. La ligne remonte dans *À trancher*, et un humain décide.
Supprimer tout seul un participant qui porte peut-être des réussites est
exactement le genre de geste qu'on ne fait pas.

## 8. Données personnelles

Décision D5 — le strict minimum. D9 réduit encore : **l'année**, pas la date.

| Donnée | Gardée ? |
| --- | --- |
| Nom, prénom | **oui** |
| **Année** de naissance | **oui** — un entier, et c'est tout ce que la règle FFME demande |
| Jour et mois de naissance | **non** (D9) |
| Club, catégorie | **oui** |
| Numéro de commande | **oui** — un entier qui ne décrit personne |
| Tout du payeur : nom, courriel, adresse, ville, téléphone | **non** |
| Montants, moyens de paiement, reçus, échéances | **non** |
| Nom du tarif | **non** — il ne sert plus à rien |
| Le JSON brut, ou une copie élaguée | **non** — les colonnes **sont** l'enregistrement |

Ce que D5 coûte : quand quelqu'un s'est trompé de prénom, on ne le joint plus
**depuis la console**. On lit le numéro de commande et on retrouve la commande
dans le back-office, où le courriel est déjà, et où il a sa place.

Ce que D5 simplifie : relire une inscription après correction ne rejoue pas une
copie locale, elle **redemande** l'article. L'idempotence rend l'opération
gratuite.

Les inscriptions suivent leur compétition : effacées par « Effacer les données
du serveur », emportées par la suppression de l'édition. Elles ne partent **pas**
dans l'archive (spec 018) : une archive sert à rejouer un classement, pas à
conserver l'état civil d'un enfant pendant dix ans.

## 9. Sécurité — le risque R13, à solder d'abord

Le `README.md` du dépôt **public** `climbBackEnd` contient en clair `clientId`,
`clientSecret` et deux jetons HelloAsso de bac à sable — risque R13, ouvert
depuis le 28/08. **Rien ne commence avant** : révoquer, nettoyer le fichier,
pousser, et considérer les jetons publiés comme perdus.

Et ici : le secret va dans `shared/secrets/`, hors dépôt et hors releases ; il
n'est jamais renvoyé par une route, jamais journalisé, jamais réaffiché ;
`.gitleaks.toml` reçoit un motif pour les clés HelloAsso.

## 10. Décisions

### Tranchées

| # | Question | Tranché |
| --- | --- | --- |
| **D1** | D'où vient la catégorie ? | De l'**année de naissance**, par la règle FFME (§2) |
| **D2** | Création automatique sans ambiguïté ? | **Oui** |
| **D3** | Webhook ou sondage ? | **Sondage seul**, 60 s |
| **D4** | Ce qui clôt une inscription | **Imprimer vaut « remis »**, avec un « déjà remis » |
| **D5** | Données gardées | **Le strict minimum** |
| **D6** | Environnement | **Bac à sable** |
| **D7** | Risque R13 | **Révoqué et nettoyé avant de commencer** |
| **D8** | Le formulaire manuel | **Année *ou* catégorie**, et chacune propose l'autre |
| **D9** | Finesse de la date | **L'année seule** |

### Ouvertes

| # | Question | Ce que je propose |
| --- | --- | --- |
| **D10** | « Appliquer à tous » écrase-t-il une catégorie corrigée à la main ? | **Non.** Le participant porte une trace du geste (`categorie_forcee`), comme `hors_circuit_force` le fait déjà pour les juges. L'aperçu les compte à part, avec un bouton pour forcer quand même |
| **D11** | Le vert de HelloAsso | Celui de la maquette. Leur page de charte graphique répond **403** : je n'ai pas pu relever le code exact |

## 11. Critères d'acceptation

**La règle des catégories**

- [ ] Le barème calculé **reproduit le tableau FFME publié** pour 2025-2026
- [ ] Une compétition de novembre 2026 et une de mars 2027 donnent **le même** barème
- [ ] Le plus petit Under l'emporte : 12 ans en référence → U13, jamais U15
- [ ] Une année hors de tout Under ne casse rien — la catégorie reste vide

**Le relevé**

- [ ] Une inscription en ligne apparaît **en moins de 90 s** pendant une compétition, sans que personne n'ait cliqué
- [ ] Le même article relevé dix fois ne crée **qu'un** participant
- [ ] Une commande à **deux** enfants crée **deux** participants
- [ ] Un article annulé après coup remonte, et **ne supprime rien**

**Le rapprochement**

- [ ] Nom + prénom + club identiques ne créent **pas** de doublon
- [ ] Club différent attend un humain
- [ ] Catégorie différente rattache quand même, et le dit

**La console**

- [ ] Les trois pastilles de source s'affichent, et **deux** apparaissent sur un participant rapproché
- [ ] Le mode sélection se voit sans qu'une phrase l'explique
- [ ] *Tout sélectionner* après un filtre catégorie imprime cette catégorie
- [ ] Le crayon ouvre la ligne ; `Annuler` ne laisse **aucune** trace
- [ ] `u13f` créé à la main est enregistré `U13 F`
- [ ] Un dossard portant des réussites **refuse** de changer de main à l'édition
- [ ] Année saisie → catégorie proposée ; catégorie choisie → années attendues affichées
- [ ] « Appliquer à tous » montre l'avant / après **avant** d'écrire
- [ ] Un participant sans année n'est **jamais** touché par le barème

**Le reste**

- [ ] Quatre workers gunicorn ne produisent **qu'un** rafraîchissement de jeton
- [ ] Aucune donnée du payeur, aucun montant n'entre en base
- [ ] Le secret n'apparaît ni dans une réponse, ni dans un journal
- [ ] Pas de clé posée : pas de menu, pas de fil, **aucun appel réseau**
- [ ] HelloAsso injoignable une heure : dit une fois, le reste marche

## 12. Cas limites

**Le formulaire ne demande pas l'année de naissance.** C'est le cas qui fait
tomber D1 tout entier, et il se découvre avec `tools/dump_helloasso.py`
**avant** qu'une ligne de code de relevé soit écrite. La console refuse
d'enregistrer une correspondance sans champ d'année.

**Le formulaire ne demande pas le genre.** Toutes les inscriptions passent en
*à trancher*. Vu au même moment, pas en recette.

**Une année aberrante.** Une faute de frappe sur l'année — 1015, 2916 — donne
une catégorie vide et une mise en attente avec l'année affichée : c'est
justement la faute de frappe qu'on voit tout de suite.

**Deux enfants d'une même famille dans une même commande.** Un article par
enfant, deux `user`, un seul `payer`. Cas nominal, et celui qu'un import « par
commande » raterait. On importe **des articles**.

**Un inscrit sans nom.** `user` absent sur certains types de tarifs. On retombe
sur le `payer` et on marque *à trancher* — jamais un participant « Sans nom ».

**Le `refresh_token` a plus de 30 jours.** Entre deux compétitions, personne
n'ouvre la console pendant des mois. La console dit « clé à reconnecter » et le
fil **cesse d'essayer**, plutôt que de brûler le quota d'authentification.

**La compétition est terminée.** Le fil passe en cadence lente. Les inscriptions
restent consultables et n'entrent pas dans le classement — il ne connaît que les
participants.
