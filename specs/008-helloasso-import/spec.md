# Spec 008 — Les inscriptions en ligne arrivent toutes seules

> **Statut : rédigée le 03/09/2026. Les sept décisions D1→D7 sont tranchées
> (§7) ; deux nouvelles, D8 et D9, naissent de D1. Porte 2 non franchie.**
> Aucune ligne de code n'est écrite. La maquette de tous les écrans est dans
> [`maquettes/inscriptions.html`](maquettes/inscriptions.html) — c'est elle qui
> se valide en premier.
>
> ⚠️ **D1 a été tranché à l'inverse de ma proposition** : la catégorie vient de
> la **date de naissance**, pas du tarif. Ce document a été repris en
> conséquence — §4 F2 est entièrement réécrit, et §7 porte les deux questions
> que ce choix fait apparaître.
>
> Numéro **008** : réservé depuis le 28/08 dans
> [`docs/specs-index.md`](../../docs/specs-index.md) sous le nom
> `helloasso-import`. Il n'a jamais été pris.

## 1. Le besoin, tel que le terrain le pose

[`docs/contraintes-metier.md` §3](../../docs/contraintes-metier.md) le dit en
quatre points, recueillis auprès d'Adrien le 28/08 :

1. **HelloAsso est la plateforme d'inscription** à la compétition.
2. **Des inscriptions se font sur place**, le jour même, sans passer par elle.
   L'import est donc un **flux d'alimentation, jamais la source unique**.
3. **Il faut un rapprochement** : quelqu'un peut s'inscrire en ligne *et* se
   présenter au guichet. Doublon à détecter sur nom + date de naissance, avec
   **validation humaine**.
4. **Ça doit être temps réel, et visible** : « il faut pouvoir avoir un dashboard
   dans la page admin et le voir sur cet écran ». Derrière chaque inscription il
   y a un geste physique — **imprimer un dossard et l'apporter à la personne**.
   Une ligne de journal ne suffit pas.

Aujourd'hui, rien de tout ça n'existe. La seule trace de HelloAsso dans
`climbcontest-core` est une constante jamais écrite :

```python
SOURCE_CLASSEUR, SOURCE_MANUEL, SOURCE_HELLOASSO = "classeur", "manuel", "helloasso"
```

Le geste réel, en novembre 2025, était : exporter un tableur depuis HelloAsso,
le recoller à la main dans l'onglet `Listes` du classeur Google, et importer.
Une fois. Ce qui arrive après l'export n'arrive jamais.

## 2. Ce que l'API HelloAsso donne — vérifié dans la documentation

Relevé le 03/09/2026 sur <https://dev.helloasso.com>. Ces faits commandent
l'architecture, ils sont donc ici et pas seulement dans `architecture.md`.

| Fait | Conséquence pour nous |
| --- | --- |
| **Clé d'API depuis le back-office du club** (*Mon Compte → Intégrations et API*) : `clientId` + `clientSecret`. Rôle `OrganizationAdmin`, privilèges `AccessPublicData`, `AccessTransactions` | Suffisant pour lire les inscriptions. **Aucun partenariat à demander** |
| `POST /oauth2/token`, `grant_type=client_credentials` → `access_token` **30 min**, `refresh_token` **30 jours** | Le jeton se garde et se rafraîchit ; il ne se redemande pas à chaque appel |
| « Il n'est **pas permis** de générer un nouvel `access_token` à partir du client_id à chaque appel » + quotas d'authentification **10/10 s, 20/10 min, 50/h** | Un jeton en mémoire vive par worker gunicorn ferait 4× les appels. Le jeton vit en **base**, un seul worker le rafraîchit |
| Le `refresh_token` **tourne** : utiliser A rend B ; réutiliser A crée C **et révoque B** | Deux rafraîchissements simultanés se **révoquent l'un l'autre**. Il faut un verrou — celui de la table `verrou` existe déjà |
| `GET /v5/organizations/{org}/forms/{type}/{slug}/items` — un **article = un inscrit**, avec `user.firstName/lastName`, `state`, `id`, `tierDescription` | C'est la route de l'import. Un `item.id` est **stable et unique** : c'est notre clé d'idempotence |
| `withDetails=true` ajoute `customFields[]` (`name`, `type`, `answer`) et `options[]` | C'est **là** que vivent le club, la date de naissance, le sexe — dans des champs que le club définit lui-même chaque année |
| `sortField=UpdateDate` + `from=<date>` + `sortOrder=Asc` | Relevé **incrémental** : on ne redemande que ce qui a bougé depuis la dernière fois |
| Pagination par `continuationToken`. `totalCount` vaut `-1`. **Le signal de fin est le tableau vide**, pas l'absence de jeton | Boucle de pagination écrite d'après leur propre algorithme, pas d'après l'intuition |
| `item.state` ∈ `Waiting`, `Processed`, `Registered`, `Deleted`, `Unknown`, `Canceled`, `Refused`, `Abandoned` | Seuls `Processed` (payé) et `Registered` (saisi par le club) valent inscription. Une annulation **après coup** doit se voir |
| `payer` ≠ `user` : le payeur est le parent, l'`user` de l'article est l'enfant | On inscrit `user`. Confondre les deux inscrirait les parents |
| **Webhook** : URL déclarée dans le back-office. Authenticité, pour une association, **par adresse IP seulement** (`51.138.206.200`) — la signature HMAC `x-ha-signature` est **réservée aux partenaires** | Le webhook ne peut pas être une source de données de confiance. Il peut être un **réveil** |
| Le corps du webhook `Order` **ne contient pas** les `customFields` | Même s'il était signé, il faudrait rappeler l'API. Ça tranche la question |
| Bac à sable complet sur `api.helloasso-sandbox.com` | Tout se développe et se recette **sans toucher au compte du club** |

## 3. Le périmètre

### On fait

| # | Quoi |
| --- | --- |
| **F1** | Relier le compte HelloAsso du club depuis la console, et choisir le formulaire de la compétition |
| **F2** | Dire, une fois par édition, **ce que veulent dire les champs du formulaire** : quelles années de naissance font quel circuit, où se lit le genre, où se lisent la date de naissance et le club |
| **F3** | Relever les inscriptions **en continu** pendant la compétition, et à la demande |
| **F4** | Détecter les doublons — avec la liste, et entre inscriptions — et les faire **trancher par un humain** |
| **F5** | Une vue **Inscriptions** dans la console : ce qui est arrivé, ce qui reste à faire, et rien d'autre |
| **F6** | Une **pastille dans le bandeau**, visible depuis n'importe quel écran, avec le nombre d'inscriptions en attente |
| **F7** | **Imprimer le dossard** depuis la vue, en un clic, et la ligne quitte la pile |
| **F8** | Une annulation côté HelloAsso **se voit** |
| **F9** | `tools/dump_helloasso.py` — lecture seule, depuis le Mac, pour regarder un formulaire avant de le relier |

### On ne fait pas

| Quoi | Pourquoi |
| --- | --- |
| Encaisser un paiement (Checkout) | Le club encaisse déjà sur HelloAsso. Rien à ajouter |
| Écrire chez HelloAsso — rembourser, annuler, créer un formulaire | Lecture seule, sans exception. Le back-office du club reste le seul endroit qui modifie |
| Recopier les inscriptions dans le classeur Google | Le classeur reçoit les **réussites**, pas les inscrits. Le miroir n'est pas touché |
| Deviner la catégorie sans qu'on l'ait dite | Un grimpeur rangé dans la mauvaise catégorie fausse un classement entier. On refuse et on demande |
| Un écran de projection des inscriptions | La console suffit, et elle est déjà regardable en continu |

## 4. Ce qu'on construit

### F1 — Relier le compte, choisir le formulaire

Une page **HelloAsso** dans la section *Administration* de la console, à côté de
*Classeur*. Réservée aux **administrateurs**, comme *Classeur* : elle manipule
un secret.

Trois champs, un bouton :

- l'**identifiant** et le **secret** de la clé d'API du club ;
- l'**environnement** : *production* ou *bac à sable* ;
- « Tester » → un jeton est demandé, la liste des formulaires du club s'affiche,
  on en choisit **un**. C'est celui de la compétition active.

Le secret n'est jamais réaffiché : une fois posé, l'écran dit `Clé posée
(…a9e5b)` et propose de la remplacer.

### F2 — La correspondance, une fois par édition

C'est la pièce que rien ne peut deviner. Le formulaire HelloAsso du club change
chaque année : les tarifs changent de nom, les champs personnalisés aussi.

> **Décision D1 du 03/09 : la catégorie vient de la date de naissance**, pas du
> tarif. C'est le barème qui fait autorité, et non le nom commercial que le club
> a donné à sa billetterie.

Une catégorie de ce projet — `U13 F` — est faite de **deux morceaux** : un
**circuit** (`U13`) et un **genre** (`F`). Le modèle le sait déjà :
`Participant.circuit` retire le dernier mot. La correspondance suit cette
découpe, parce que les deux morceaux ne viennent pas du même endroit.

#### Le circuit vient de l'année de naissance

La console **propose** un barème, calculé depuis la date de la compétition :
pour une saison 2026-2027, `U11` prend 2016 et 2017, `U13` prend 2014 et 2015,
et ainsi de suite. Une ligne par circuit de la compétition, deux années
modifiables.

**Proposé, jamais imposé.** Les catégories changent d'une édition à l'autre
(`U10` → `U17` selon les années, dit `contraintes-metier.md` §4) et rien ne
garantit des tranches de deux ans. Le barème se corrige à la main.

Et il se **contrôle**, comme la cascade de couleurs contrôle ses phrases mortes :

| Ce que la console attrape | Ce qu'elle dit |
| --- | --- |
| Une année couverte par **deux** circuits | *2015 est dans U13 et dans U15* |
| Un **trou** entre deux circuits | *2018 et avant : aucun circuit* |
| Un circuit **sans année** | *U17 ne prendra jamais personne* |
| Une catégorie composée qui **n'existe pas** dans la compétition | *« U9 F » n'est pas une catégorie de cette édition* |

Un barème peut être cohérent et faux ; il ne peut pas être incohérent sans que
ça se voie.

#### Le genre vient d'un endroit qu'on désigne

Une source, et une seule, choisie parmi deux :

- un **champ du formulaire** (`Sexe`, `Genre`…) ;
- ou le **nom du tarif**, quand le club vend « U11 filles » et « U11 garçons ».

La console montre les **réponses réellement vues** et on les range en `F` ou
`H`. « Fille », « F », « Féminin » sont trois écritures de la même chose, et
aucune règle générale ne les couvrira toutes.

Un circuit peut être marqué **mixte** — `Adulte`, `Loisir` : il ne reçoit alors
pas de suffixe, et sa catégorie est son seul nom.

#### Les deux champs qui restent

| Champ | Rôle |
| --- | --- |
| **Date de naissance** | **Obligatoire.** Sans lui, aucune catégorie ne se calcule |
| **Club** | Facultatif. Absent, le club reste vide et se saisit au guichet |

C'est le point à vérifier **avant** d'écrire une ligne de code, et c'est la
raison d'être de `tools/dump_helloasso.py` (F9) : si le formulaire du club ne
demande pas la date de naissance, D1 ne peut pas s'appliquer et il faut le
savoir tout de suite.

Rien de tout ça n'empêche le relevé. Une année hors barème, un genre
indéterminé, une date absente : l'inscription arrive en **« à trancher »**,
catégorie vide. On signale, on ne perd pas.

La correspondance est enregistrée **par compétition**, comme la cascade de
couleurs et les options d'affichage.

### F3 — Le relevé

Un fil de fond, sur le modèle exact du miroir vers le classeur : un verrou en
base, un seul worker travaille, il ne meurt jamais.

| Situation | Cadence |
| --- | --- |
| Compétition `en_cours` | **toutes les 60 s** |
| Compétition `preparation` datée d'aujourd'hui ou de demain | toutes les 5 min |
| Le reste du temps | toutes les 30 min |
| Bouton « Relever maintenant » | tout de suite |

Le relevé est **incrémental** : `from=` la date du dernier article vu.

### F4 — Le rapprochement

Chaque article relevé est comparé à ce qui est déjà là — participants **et**
inscriptions, toutes origines confondues.

La comparaison se fait sur le nom et le prénom **normalisés** (minuscules, sans
accent, espaces réduits, tirets et apostrophes traités comme des séparateurs —
`formatage.py` sait déjà faire), et sur la date de naissance quand les deux
côtés en ont une.

| Cas | Verdict |
| --- | --- |
| Aucun homonyme | **Nouvelle inscription.** Le participant est créé, un dossard lui est attribué |
| Homonyme, **dates de naissance identiques** | **La même personne.** L'inscription se rattache au participant existant, sans le dupliquer. Les champs vides du participant sont complétés, les autres jamais écrasés |
| Homonyme, **dates de naissance différentes** | **Deux personnes.** Créé, et signalé une fois — deux Martin Dupont, ça existe |
| Homonyme, **une date manque** | **À trancher.** Un humain voit les deux fiches côte à côte et dit |
| Date de naissance absente, ou **hors barème** | **À trancher**, catégorie vide |
| Genre indéterminé sur un circuit non mixte | **À trancher** |
| Article `Canceled` / `Refused` / `Abandoned` / `Deleted` | Pas d'inscription. Si elle existait déjà : **annulée**, et ça se voit |

Rien n'est fusionné dans le dos de personne : un rattachement automatique
n'arrive **que** sur une date de naissance identique, qui est la seule preuve
dont on dispose.

> ⚠️ **Conséquence de D1 qu'il faut regarder en face.** Le formulaire d'ajout
> manuel de la console ne demande **pas** la date de naissance aujourd'hui
> (spec 013 : nom, prénom, club, catégorie). Un participant saisi au guichet
> n'en a donc jamais, et toute rencontre entre une inscription en ligne et une
> saisie au guichet tombera **systématiquement** en « à trancher » — le cas
> exact que la contrainte métier §3 demande de traiter. C'est la décision
> **D8** ci-dessous.

### F5 — La vue *Inscriptions*

Une entrée dans le tiroir, groupe *La compétition*, sous *Participants*. Trois
piles, dans l'ordre où on les traite :

| Pile | Ce qu'elle contient | Le geste |
| --- | --- | --- |
| **À trancher** | Doublon possible, catégorie inconnue, annulation | Choisir, en une phrase |
| **À imprimer** | Le participant existe, son dossard n'est pas sorti | « Imprimer le dossard » |
| **Faites** | Repliée. On l'ouvre pour retrouver quelqu'un | — |

La vue se rafraîchit toute seule toutes les 30 s tant qu'elle est ouverte.
C'est l'écran que l'organisateur laisse affiché — c'est le « dashboard » demandé
le 28/08.

### F6 — La pastille

Même pastille que celle de la spec 031, même forme, même ocre : une pilule dans
le bandeau, `3 inscriptions`, visible depuis n'importe quel écran. Elle mène à la
vue *Inscriptions* et ne fait que ça.

Elle compte **à trancher + à imprimer**. Elle disparaît quand la pile est vide.

### F7 — Imprimer

Le bouton ouvre la **fiche du grimpeur** de la spec 023, pour ce seul dossard —
la route existe (`/admin/dossards?dossard=…`). L'inscription passe en *faite*.

Un « déjà remis » sans impression est là pour le cas où la personne est déjà
partie avec son dossard.

### F8 — Une annulation se voit

Un article qui repasse en `Canceled` alors qu'il avait produit un participant ne
supprime **rien**. La ligne remonte dans *À trancher* avec la mention
« annulée chez HelloAsso », et un humain décide de retirer le participant ou non.

Supprimer tout seul un participant qui porte peut-être déjà des réussites est
exactement le genre de geste qu'on ne fait pas.

### F9 — Regarder avant de relier

`tools/dump_helloasso.py`, sur le modèle de `tools/dump_sheet.py` : **lecture
seule**, lancé depuis le Mac, il affiche les formulaires du club, les tarifs et
les champs personnalisés d'un formulaire donné. C'est ce qui permet de préparer
la correspondance F2 sans rien brancher.

Comme `tools/load/`, il refuse de démarrer sans une variable d'environnement
explicite, et il **n'écrit jamais**.

## 5. Données personnelles — ce qu'on garde, ce qu'on jette

Les articles HelloAsso portent des **noms de mineurs**, leur date de naissance,
et l'adresse postale, le téléphone et le courriel du **payeur** — c'est-à-dire
d'un parent. La règle 7 du `CLAUDE.md` est explicite.

> **Décision D5 du 03/09 : le strict minimum.** Rien du payeur, pas même son
> courriel.

| Donnée | Gardée ? |
| --- | --- |
| Nom, prénom de l'inscrit | **oui** — c'est l'inscription |
| Date de naissance | **oui** — elle fait la catégorie **et** le rapprochement |
| Club, catégorie, nom du tarif | **oui** |
| Numéro de commande HelloAsso | **oui** — un entier. Il ne dit rien de personne, et c'est lui qui permet de retrouver la commande dans le back-office quand il faut joindre quelqu'un |
| Courriel du payeur | **non** (D5) |
| Nom, adresse, ville, code postal, pays, société, téléphone du payeur | **non.** Jamais écrits en base |
| Montant, moyen de paiement, reçu, échéances | **non.** Ce n'est pas notre affaire |
| Le JSON brut, ou une copie élaguée | **non.** Les colonnes de la table **sont** l'enregistrement |

Ce que D5 coûte, et il faut le dire : quand quelqu'un s'est trompé de prénom, on
ne peut plus le joindre **depuis la console**. On lit le numéro de commande à
l'écran et on le retrouve dans le back-office HelloAsso, où le courriel est déjà,
et où il a sa place.

Ce que D5 simplifie : la relecture d'une inscription avec une correspondance
corrigée ne se fait plus depuis une copie locale — elle **redemande** l'article à
HelloAsso. C'est moins de données gardées *et* moins de code, parce que
l'idempotence rend le re-relevé gratuit.

Les inscriptions suivent leur compétition : effacées par « Effacer les données du
serveur », emportées par la suppression de l'édition. Elles ne partent **pas**
dans l'archive (spec 018) : une archive sert à rejouer un classement, pas à
conserver l'état civil d'un enfant pendant dix ans.

## 6. Sécurité — le risque R13, à solder d'abord

Le `README.md` du dépôt **public** `climbBackEnd` contient en clair
`clientId`, `clientSecret` et deux jetons HelloAsso de bac à sable. C'est le
risque R13 de l'état des lieux, ouvert depuis le 28/08.

**Rien de cette spec ne commence avant que ce soit fait** :

1. révoquer la clé de bac à sable depuis le compte HelloAsso ;
2. retirer les lignes du `README.md` et pousser ;
3. considérer les jetons publiés comme perdus — ils sont dans l'historique git
   d'un dépôt public, et le réécrire ne les rattrape pas.

Et ici, jamais deux fois la même erreur :

- le `clientSecret` va dans `shared/secrets/`, **hors du dépôt et hors des
  releases**, comme le jeton Google ;
- il n'est **jamais** renvoyé par une route, jamais journalisé, jamais réaffiché ;
- `.gitleaks.toml` reçoit un motif pour les clés HelloAsso, pour que la question
  ne se repose pas.

## 7. Décisions

### Tranchées par Adrien le 03/09/2026

| # | Question | **Tranché** |
| --- | --- | --- |
| **D1** | D'où vient la **catégorie** ? | **De la date de naissance.** Un barème année → circuit, proposé puis corrigé ; le genre lu à part. Le tarif ne fait plus autorité |
| **D2** | Une inscription sans ambiguïté crée-t-elle le participant toute seule ? | **Oui** |
| **D3** | Webhook, ou sondage seul ? | **Sondage seul**, 60 s en compétition |
| **D4** | Imprimer le dossard vaut-il « remis » ? | **Oui**, avec un « déjà remis » pour le cas inverse |
| **D5** | Que garde-t-on de la commande ? | **Le strict minimum.** Rien du payeur, pas même son courriel |
| **D6** | Sur quoi développe-t-on ? | **Le bac à sable** |
| **D7** | Qui crée la clé d'API ? | **Adrien**, et R13 est soldé avant qu'on commence |

### Ce que D1 fait apparaître, et qui reste à trancher

Ces deux questions n'existaient pas tant que la catégorie venait du tarif.

| # | Question | Ce que je propose |
| --- | --- | --- |
| **D8** | Le formulaire d'ajout manuel apprend-il l'**année de naissance** ? | **Oui, un champ facultatif.** Sans elle, une saisie au guichet et une inscription en ligne pour la même personne tombent **toujours** en « à trancher » — et la catégorie continue de se choisir à la main d'un côté pendant qu'elle se calcule de l'autre. C'est une retouche à l'écran de la spec 013 : elle est à valider, pas à faire en douce |
| **D9** | Garde-t-on la **date complète**, ou l'**année seule** ? | **La date complète.** L'année suffit pour la catégorie, mais c'est la date qui autorise une fusion sans demander : avec l'année seule, deux homonymes nés la même année seraient fusionnés à tort. Si le « strict minimum » de D5 doit aller jusque-là, la règle de fusion se durcit — nom + prénom + année + **club**, et tout le reste en « à trancher » |

## 8. Critères d'acceptation

- [ ] R13 soldé : clé de bac à sable révoquée, `README.md` de `climbBackEnd` nettoyé
- [ ] Une clé d'API valide se pose depuis la console et le secret n'est jamais réaffiché
- [ ] Une clé invalide donne un message qui dit **quoi faire**, pas une trace
- [ ] La liste des formulaires du club s'affiche et l'un d'eux se choisit
- [ ] Les tarifs, les champs personnalisés et **les réponses réellement vues** sont **découverts**, pas saisis
- [ ] Le barème année → circuit est **proposé** depuis la date de la compétition, et modifiable
- [ ] Le contrôle du barème attrape un **recouvrement**, un **trou**, un circuit **sans année**, et une catégorie composée **inexistante**
- [ ] Une inscription en ligne apparaît dans la console **en moins de 90 secondes** pendant une compétition, sans que personne n'ait cliqué
- [ ] Le même article relevé dix fois ne crée **qu'un** participant
- [ ] Un homonyme de même date de naissance ne crée **pas** de second participant
- [ ] Un homonyme de date différente en crée deux, et le dit
- [ ] Un homonyme sans date attend un humain
- [ ] Une année hors barème, une date absente ou un genre indéterminé mettent l'inscription en attente, **sans bloquer les autres**
- [ ] Un circuit **mixte** ne reçoit pas de suffixe de genre
- [ ] Un article annulé après coup remonte dans *À trancher*, et **ne supprime rien**
- [ ] La pastille compte juste, et disparaît quand la pile est vide
- [ ] « Imprimer le dossard » ouvre la fiche du bon dossard et vide la ligne
- [ ] Quatre workers gunicorn ne produisent **qu'un** rafraîchissement de jeton
- [ ] Aucune adresse postale, aucun téléphone, aucun montant, **aucun courriel**, aucun nom de payeur n'entre en base
- [ ] Les routes répondent **403** à un organisateur pour le réglage de la clé, **401** sans session
- [ ] HelloAsso non configuré : aucune entrée de menu, aucun fil, **aucun appel réseau**
- [ ] HelloAsso injoignable pendant une heure : la console le dit une fois, le reste marche

## 9. Cas limites

**Le jeton expire pendant le relevé.** L'`access_token` vit 30 minutes, le
relevé dure quelques secondes : c'est le rafraîchissement qui se croise avec un
autre worker qui pose problème, pas la durée. D'où le verrou. Un `401` en cours
de relevé provoque **un** rafraîchissement et **un** seul réessai.

**Le `refresh_token` a plus de 30 jours.** Entre deux compétitions, personne
n'ouvre la console pendant des mois. Le jeton meurt. La console doit alors dire
« clé à reconnecter », pas « erreur 401 » — et le fil doit **cesser d'essayer**
plutôt que de brûler le quota d'authentification.

**Le formulaire ne demande pas la date de naissance.** C'est le cas qui fait
tomber D1 tout entier, et il se découvre avec `tools/dump_helloasso.py`
**avant** qu'une ligne de code soit écrite (lot 1). Si ça arrive : soit le club
ajoute le champ à son formulaire, soit D1 se rejoue. La console, elle, refuse
d'enregistrer une correspondance sans champ de date : elle dit *« aucun champ de
date de naissance — aucune catégorie ne pourra se calculer »* plutôt que de
laisser cent inscriptions s'empiler en attente.

**Une année hors barème.** Un adulte accompagnateur, un enfant trop jeune, une
faute de frappe sur l'année. L'inscription arrive en *À trancher* avec l'année
affichée : c'est souvent la faute de frappe qu'on voit tout de suite.

**Le barème change en cours de compétition.** On corrige une ligne, on
enregistre, et un bouton **rejoue** les inscriptions en attente. Le rejeu
**redemande** les articles à HelloAsso plutôt que de relire une copie locale
(D5) ; l'idempotence rend l'opération gratuite.

**Un circuit mixte.** `Adulte`, `Loisir` : pas de suffixe de genre, la catégorie
est le nom du circuit. Sans cette case, la console composerait « Adulte F » —
une catégorie qui n'existe nulle part, et un classement d'une personne.

**Deux enfants d'une même famille dans une même commande.** Un article par
enfant, deux `user` différents, un seul `payer`. C'est le cas nominal, pas un
cas limite — mais c'est celui qu'un import « par commande » raterait. On importe
**des articles**, jamais des commandes.

**Un inscrit sans nom.** `user` est absent sur certains types de tarifs. On
retombe sur le `payer`, et on marque l'inscription *à trancher* — jamais un
participant nommé « Sans nom ».

**Le dossard est déjà attribué.** L'attribution automatique (spec 013) prend le
premier numéro libre. Rien de neuf ici : l'inscription en ligne emprunte le même
chemin que le bouton « Ajouter ».

**La compétition est terminée.** Le fil se met en cadence lente et les
inscriptions restent consultables. Elles n'entrent plus dans le classement — le
classement ne regarde que les participants, et un humain a arrêté d'en créer.
