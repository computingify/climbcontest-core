# Spec 034 — Le QR de poste, posé sur la table du juge

> **Statut : spec écrite AVANT le code** — 03/09/2026. C'est le point de la
> demande : les specs 027 et 032 portent un encadré de honte pour l'avoir fait
> dans l'autre sens.
>
> Demande d'Adrien du 03/09/2026 : « Je voudrais que le juge lorsqu'il arrive à
> sa table, il puisse utiliser l'application pour scanner un QR code qui serait
> posé sur sa table et qui permettrait de configurer son application avec le bon
> nom de téléphone […] Dans ce cas, il faut que tu me fasses un endroit dans la
> console où je peux générer ces QR codes et les imprimer un petit peu comme tu
> l'as fait pour les grimpeurs et les blocs. De plus, tu connais parfaitement
> grâce au plan le nombre des zones, donc tu peux tout à fait le générer
> automatiquement. »

> ### Retouches du 03/09, après relecture d'Adrien
>
> La spec ci-dessous a été écrite avant le code, le code a été écrit, et Adrien
> l'a relu à l'écran. Cinq décisions en sont sorties. Elles sont **intégrées
> dans le texte** — pas ajoutées en annexe — et chacune porte sa raison.
>
> 1. **Huit affiches par A4** au lieu de trois (§ F4). « Lors de l'impression tu
>    m'en rentres beaucoup plus sur une feuille — à quatre, j'en voudrais au
>    moins six, voire huit. » On prend le haut de la fourchette.
> 2. **Plus de mode d'emploi sur le carton** (§ F4). « Sur ces planches qui sont
>    imprimées, tu n'as pas besoin de mettre le texte qui permet de comprendre
>    comment est-ce qu'il faut le scanner. »
> 3. **Le geste passe sur l'écran d'accueil de la PWA** (§ F7) — c'est là que
>    part le mode d'emploi retiré du carton.
> 4. **Le nom envoyé à la console devient « Zone A »** (§ F2), composé par
>    l'application ; le QR, lui, ne porte toujours que la lettre.
> 5. **Plusieurs téléphones par zone** (§ F8) : ils portent le même nom, et la
>    console doit pouvoir les distinguer.

## 1. Ce qui manque

Le nom du téléphone existe depuis la spec 011. Il désigne **un poste, pas une
personne** — « Mur jaune », « Zone C » — et c'est lui qui s'affiche dans la
console à côté de chaque réussite envoyée. Sans lui, la vue « Qui envoie quoi »
ne montre qu'une suite d'identifiants tronqués, et un téléphone muet depuis dix
minutes ne dit pas *où* aller voir.

Aujourd'hui, ce nom se tape à la main. Il faut : ouvrir les réglages, trouver le
champ, écrire quelque chose. Trois problèmes, tous constatés :

1. **personne ne le fait.** C'est un réglage optionnel, invisible depuis
   l'écran principal, dans une application qu'on ouvre pour scanner ;
2. **quand c'est fait, c'est fait n'importe comment.** « Zone C », « zone c »,
   « C », « mur de Julien » : la console affiche ce qu'on lui donne, et deux
   téléphones du même mur portent deux noms différents ;
3. **ça se refait à chaque compétition**, et les téléphones sont ceux des
   bénévoles : rien ne persiste d'une édition à l'autre.

Le geste que le juge sait déjà faire, lui, c'est **scanner**. Il le fait cent
fois dans la journée.

## 2. Ce qu'on fait

### F1 — Un QR posé sur la table, scanné depuis l'application

Un geste dans les **réglages** de la PWA juge : *« Scanner le QR de mon
poste »*. Il ouvre **le même viseur** que « Scanner le QR de l'organisateur »
(spec 014) — même caméra, même jsQR versé dans le dépôt, aucun réseau — lit un
QR, et **renomme le téléphone**.

Le juge arrive à sa table, ouvre l'application, scanne le carton posé devant
lui. Son téléphone s'appelle « Zone C ». Il n'a rien tapé.

### F2 — Le format du QR : `CCPOSTE:` + la lettre de la zone

```
CCPOSTE:C          →  le téléphone s'appelle « Zone C »
```

> **Décision du 03/09.** Adrien : « dans le nom qu'on envoie à la console, je
> veux que ce soit "zone" et la lettre de la zone ». Le libellé est composé
> **par l'application** (`poste.js`, `MOT_ZONE` + la lettre) ; le QR, lui,
> continue de ne porter que la lettre.
>
> Deux raisons de ne pas imprimer `CCPOSTE:Zone C` :
>
> - **un QR minimal se lit mieux.** Cinq caractères de moins, c'est une version
>   de symbole gagnée sur les noms de zone longs, donc des modules plus gros à
>   taille de papier égale — et c'est la lisibilité du QR qui décide si le
>   carton sert à quelque chose ;
> - **le libellé peut changer sans réimprimer dix-sept affiches.** Le jour où
>   « Zone A » devient « Poste A », on change un mot et on livre une version de
>   l'application. Les cartons posés sur les tables restent valables.
>
> Contrepartie assumée : le mot est écrit **deux fois**, dans `poste.js` et
> dans `fiches.MOT_ZONE` — le carton imprime « ZONE » au-dessus de la lettre. Un
> test les compare, comme pour le préfixe (§ F6).
>
> Une zone qui s'appelle déjà « Zone Nord » n'est **pas** préfixée deux fois :
> rien dans le plan n'interdit ce nom, et « Zone Zone Nord » aurait l'air cassé.

Le préfixe n'est pas décoratif. Trois familles de QR circulent le jour J, et le
même viseur les voit toutes :

| QR | Contenu | Ce qu'il ne doit **jamais** faire |
| --- | --- | --- |
| Dossard | `42` | renommer le téléphone « 42 » |
| Bloc | `ZJ6` | renommer le téléphone « ZJ6 » |
| Lien de l'organisateur | `https://…/juge?j=…` | renommer le téléphone avec une URL |
| **Poste** | `CCPOSTE:C` | — |

Sans préfixe, un juge qui scanne un bloc par erreur depuis cet écran renommerait
son poste « ZJ6 » **sans s'en apercevoir**, et la console afficherait « ZJ6 »
pour tous ses envois de la journée. Le préfixe rend la confusion **impossible**,
pas improbable.

Choix du texte brut plutôt que d'une URL (`…/juge?poste=Zone+C`) :

- une URL scannée par **l'appareil photo natif** du téléphone ouvre un
  navigateur. Le juge se retrouverait dans Safari au lieu de son application,
  avec une deuxième instance sans file d'attente. `CCPOSTE:C` scanné par
  l'appareil photo natif **ne fait rien** : c'est un échec propre et sans
  conséquence, exactement ce qu'on veut d'un geste fait au mauvais endroit ;
- une URL entraînerait une route serveur, donc une dépendance réseau sur un
  réglage purement local ;
- le préfixe se lit à l'œil nu sur le carton imprimé si un jour on doit
  débugger.

Le préfixe est **insensible à la casse** en lecture (`ccposte:` passe), toujours
écrit en majuscules en génération. Un QR refait à la main ne doit pas devenir un
QR mort.

### F3 — Ce que l'application refuse, et ce qu'elle en dit

Un renommage silencieux vaut moins que pas de renommage. Chaque refus porte un
message qui dit **quel QR a été vu** et **quoi faire** :

| Ce qui est scanné | Message |
| --- | --- |
| `ZJ6`, `42`, n'importe quoi | « Ce QR n'est pas un QR de poste. Le QR de poste est celui posé sur ta table. » |
| `https://…/juge?j=…` | « Ce QR est le lien de l'organisateur, pas un QR de poste. Il sert à installer l'application. » |
| `CCPOSTE:` sans nom | « Ce QR de poste ne porte aucun nom de zone. Va voir un organisateur. » |
| *(annulé)* | Rien. Le juge a appuyé sur « Annuler ». |

En cas de succès : *« Ce téléphone s'appelle maintenant « Zone C ». »*

Le nom passe par `identite.nettoyerLeNom()` — le même nettoyage que la saisie au
clavier : coupé à 60 caractères, espaces de bord retirés. Une seule règle, pas
deux.

### F4 — La planche de QR de poste, dans la console

Nouvelle page `GET /admin/postes`, réservée à un organisateur, sur le modèle
exact de `/admin/dossards` et `/admin/etiquettes`.

**Les zones se déduisent du plan courant** (`fiches.plan_courant()` puis
`fiches.zones_du_plan()`), jamais d'une liste tapée à la main : Adrien l'a dit,
« tu connais parfaitement grâce au plan le nombre des zones ». Un mur ajouté
dans `/admin/plan` produit son QR à l'impression suivante, sans qu'on touche à
quoi que ce soit.

| Paramètre | Effet |
| --- | --- |
| *(aucun)* | Une affiche par zone du plan courant |
| `?zone=C` | Une seule affiche : celle qu'on a perdue ou déchirée |

> ⚠️ **Deux corrections successives, toutes deux constatées à l'écran.**
>
> **La première.** Cette section disait « deux par A4 », en disposition
> **verticale** (188 × 136 mm) : QR de 80 mm, puis le nom, puis le mode
> d'emploi. Le contenu faisait **164 mm de haut dans une affiche de 136** — le
> mode d'emploi sortait **coupé** en bas de chaque affiche, et aucun test ne le
> voyait. La disposition est passée à l'**horizontale**, QR à gauche et texte à
> droite, comme les étiquettes de blocs depuis la spec 024 : un carton posé à
> plat est large et bas. Trois par page.
>
> **La seconde, le 03/09 après relecture.** Adrien : « lors de l'impression tu
> m'en rentres beaucoup plus sur une feuille — à quatre, j'en voudrais au moins
> six, voire huit », et « sur ces planches qui sont imprimées, tu n'as pas
> besoin de mettre le texte qui permet de comprendre comment est-ce qu'il faut
> le scanner ».
>
> Les deux vont ensemble : **le mode d'emploi parti, une affiche n'a plus besoin
> de la pleine largeur.** Deux colonnes de quatre deviennent possibles, et les
> 17 zones passent de 6 feuilles à **3**.

**Huit par A4**, en **deux colonnes de quatre**, chacune 94 × 67,5 mm :

```
┌────────────────────────┬────────────────────────┐
│ ┌──────────┐  ZONE     │ ┌──────────┐  ZONE     │
│ │    QR    │  ┌─┐      │ │    QR    │  ┌─┐      │
│ │  48 mm   │  │A│      │ │  48 mm   │  │B│      │
│ │«CCPOSTE:A»│  └─┘      │ │«CCPOSTE:B»│  └─┘      │
│ └──────────┘           │ └──────────┘           │
├────────────────────────┼────────────────────────┤
│           C            │           D            │
├────────────────────────┼────────────────────────┤
│           E            │           F            │
├────────────────────────┼────────────────────────┤
│           G            │           H            │
└────────────────────────┴────────────────────────┘
                 188 × 270 mm
```

Il ne reste sur le carton que **ce qui sert à la table** :

1. le **nom de la zone**, l'élément le plus gros — c'est ce qu'on lit en
   arrivant, à un mètre, pour savoir qu'on est à la bonne table ;
2. le **QR**, qu'on vise d'une seule main, l'autre étant occupée.

**Le QR fait 48 mm, et 42 est le plancher.** Ce n'est pas un chiffre choisi au
jugé : 42 mm est la taille des étiquettes de blocs depuis la spec 024, et elles
se scannent à bout de bras. Six millimètres de marge au-dessus, pour un carton
posé à plat et visé de biais. Densifier davantage passerait sous cette barre —
et un QR qu'on ne lit pas se découvre le samedi matin, cartons déjà posés.

**La densité est UNE constante nommée**, `fiches.POSTES_PAR_FEUILLE`. Le nombre
de colonnes, la hauteur d'une affiche et la place laissée au nom en descendent
par `fiches.geometrie_postes()` ; le gabarit ne fait que poser les millimètres
qu'on lui donne, en variables CSS. Repasser à **six** — l'autre borne de la
fourchette d'Adrien — est **une valeur à changer**, pas une refonte du CSS.
C'est précisément ce qui manquait à la version à trois : la densité vivait dans
une constante Python *et* dans une demi-douzaine de millimètres écrits en dur
dans le gabarit.

**Où est passé le mode d'emploi.** Dans l'application, § F7 — et il y arrive au
bon moment. Un mode d'emploi imprimé se lit une fois, quand on n'en a pas
besoin ; un message dans l'application se lit quand on en a besoin, et disparaît
ensuite.

### F5 — Le QR, généré localement

`qr.svg("CCPOSTE:" + zone, cote_mm=48)`. Aucun appel réseau, comme les dossards
depuis la spec 005 et les étiquettes depuis la 024 : on imprime parfois la
veille au soir, parfois sans connexion.

À 48 mm, un `CCPOSTE:A` tient en version 1 — 21 modules plus huit de zone de
silence : **1,6 mm par module**, soit plus de trois fois le plancher de
`qr.MODULE_MINI_MM`. La marge est là pour les noms de zone longs, que le plan
d'usine autorise.

Et surtout : un **décodeur indépendant** (OpenCV) relit ce qu'on produit, dans
`tests/test_postes.py::TestVraimentLisible`. C'est le seul test qui prouve
quelque chose — un QR d'allure correcte que personne ne lit passerait toutes
les autres vérifications, et se découvrirait le samedi matin.

### F6 — Un préfixe, deux langages, un test qui les tient

Le préfixe est écrit **deux fois** : dans `fiches.py` (qui l'imprime) et dans
`poste.js` (qui le lit). Deux constantes dans deux langages qui doivent rester
égales : c'est exactement le motif qui dérive en silence, et le jour où il
dérive, **tous les QR imprimés cessent d'être lus** sans qu'une seule ligne de
code ait l'air fausse.

Un test Python lit `poste.js`, en extrait le préfixe, et le compare à celui de
`fiches.py`. Le piège n'est pas documenté : il est **détectable**.

### F7 — Le geste sur l'écran d'accueil de la PWA

> **Décision du 03/09.** Adrien : « Lorsque le juge arrive à sa table, il va
> ouvrir l'application et dans l'application, on va lui afficher un petit texte
> en haut comme quand la première fois qu'il l'a ouverte pour scanner le QR code
> qui permet d'avoir le secret d'API. Là ici, on aura encore un petit bouton au
> milieu sur la page d'accueil qui permet de scanner ce QR code qui permet de
> setter la zone. »

C'est la **contrepartie** du mode d'emploi retiré du carton (§ F4) : il fallait
qu'il réapparaisse quelque part, et au bon moment.

Le motif existe déjà et n'est **pas réinventé** : c'est celui de `#relier` /
`#btnRelier` (spec 014), le bloc caché sous l'en-tête que le démarrage révèle
quand il manque quelque chose. Un bloc `#poste` / `#btnPoste` s'y ajoute, avec
son petit texte au-dessus du bouton.

| Quand | Ce qu'on voit |
| --- | --- |
| Le téléphone n'a **pas** de nom | « Ce téléphone n'a pas encore de poste. Le carton posé sur ta table porte le QR qui le nomme. » + le bouton |
| Le téléphone a un nom | **Rien.** Le bloc disparaît |

**Il doit disparaître, et c'est le point.** Le juge scanne son carton **une fois
le matin**, pas cent fois par jour. Un bandeau qui resterait toute la journée
au-dessus des cartes de scan volerait de la place à ce qu'on touche cent fois.
Le geste reste ensuite **dans les Réglages**, où il était déjà (§ F1) — pour le
carton changé de table, ou le nom effacé par erreur.

Trois moments décident de cette visibilité : le démarrage, un scan de poste
réussi, et la frappe dans le champ du nom. **Une seule fonction** en décide,
`proposerDeNommerLePoste()` — trois endroits qui poseraient `hidden` eux-mêmes
finiraient par laisser le bloc affiché sur un téléphone déjà nommé.

> **Choix fait seul, à signaler.** Le petit texte est **dans le bloc**, au-dessus
> du bouton, et non passé à `dire()` comme le fait `#relier`. Un message de genre
> « attention » ne s'efface jamais tout seul, s'affiche **en bas** de l'écran, et
> serait balayé par le premier message de scan. Le texte inline est au-dessus du
> bouton — « en haut », comme demandé — et disparaît avec lui.

Depuis l'accueil, un scan réussi **n'ouvre pas les Réglages** : ce serait
déposer le juge sur un écran qu'il n'a pas demandé, juste avant son premier
scan. Depuis les Réglages, il les rouvre — c'est le rafraîchissement existant
qui repose la valeur du champ.

### F8 — Plusieurs téléphones sur la même zone

> **Décision du 03/09.** Adrien : « il faut aussi que tu prennes en compte qu'il
> peut y avoir plusieurs téléphones par zone. Dans ce cas-là, les juges vont
> tous les deux scanner le même QR code, ce qui fait que les téléphones vont
> porter le même nom. Moi, ce que je veux, c'est que tu sois capable de les
> distinguer côté console. »

Le nom d'un poste **n'est plus unique, et c'est voulu**. Deux juges affectés à
la zone A scannent le même carton : leurs deux téléphones s'appellent « Zone A ».

**La donnée existait déjà.** Chaque téléphone porte un `appareil_id` — un UUID
posé par `static/juge/identite.js` depuis la spec 011 — et la vue « Téléphones »
en affiche déjà les huit premiers caractères dans une colonne « Identifiant ».
Il n'y avait **rien à inventer**.

Ce qui manquait est la **lisibilité** : deux lignes « Zone A » côte à côte ne
disent pas laquelle est laquelle, et la colonne d'identifiants est à l'autre
bout de la ligne. Le nom est donc **suivi du code court** :

```
Zone A (3f9a1c2b)
Zone A (7e40aa91)
```

Huit caractères : c'est ce que l'application affiche dans ses réglages, donc ce
que le juge peut **lire sur son écran et dicter par radio**.

> ⚠️ **Une seule fonction compose ce libellé**, `contest.libelle_poste(nom,
> appareil_id)`, côté serveur. Toutes les vues de la console l'appellent — « Qui
> envoie quoi », la colonne « Téléphone » de la recherche de scans, et ce qui
> viendra. La **forme** exacte (parenthèses, tiret, code devant ou derrière) est
> en cours d'arbitrage : en changer doit rester une modification d'un seul
> endroit. Deux vues qui nommeraient un poste différemment obligeraient à faire
> la correspondance de tête, au pire moment.

Une **saisie manuelle** n'a pas d'appareil : le libellé est `null`, et la console
dit « saisie de adrien ». Lui inventer un appareil serait faux.

La colonne « Identifiant » **reste** : elle porte le code seul, sélectionnable,
et c'est la seule façon de le copier. Le libellé le répète pour qu'on n'ait pas
à traverser la ligne des yeux.

## 3. Périmètre

**Inclus** : un module `poste.js` testable sur Node, un geste dans les réglages
de la PWA **et sur son écran d'accueil**, une route `/admin/postes`, un gabarit
`postes.html`, une carte dans la vue **Téléphones** de la console, **le libellé
d'un poste dans la console** (`contest.libelle_poste`), les tests.

**Exclu, à dessein** :

- **l'affichage du nom du poste en haut de l'application.** Adrien l'a demandé
  dans le même message, et c'est traité **ailleurs** : l'en-tête de `juge.html`
  est refondu en parallèle dans `fix/revue-du-03-09`, qui y pose l'emplacement
  `#nomPoste`. Deux branches qui réécrivent le même `<header>` fusionneraient
  sans conflit et en silence — le motif est déjà arrivé une fois sur ce dépôt
  (spec 032, deux fonctions du même nom). Cette spec **ne touche pas au bloc
  `<header>`**, et se contente d'appeler `identite.renommer()`.

  > ⚠️ **Et le piège a bien failli se refermer.** `fix/revue-du-03-09` est
  > mergée ; au rebase, les deux branches ont fusionné **sans un seul conflit**
  > sur ce point — et pour cause, elles ne se touchent pas. Sauf que
  > `afficherLeNomDuPoste()` n'est appelée qu'au démarrage et à la frappe dans
  > le champ du nom : le **scan** ne la déclenchait pas. Un juge qui scanne son
  > carton aurait vu le bloc de l'accueil disparaître et l'en-tête rester vide
  > jusqu'au prochain démarrage. Corrigé, et **A17** le tient ;
- **un QR de poste par téléphone** (un identifiant plutôt qu'une zone). Ça
  reviendrait à attribuer les téléphones depuis la console, ce qui suppose de
  savoir combien il y en a — on ne le sait pas, ce sont ceux des bénévoles ;
- **la validation de la zone contre le plan, côté téléphone.** Le catalogue
  local peut avoir du retard sur un plan redessiné le matin même. Refuser un nom
  parce qu'une copie périmée ne le connaît pas bloquerait un juge pour un
  réglage qui n'a aucune conséquence sur les données. Le nom du poste est une
  **étiquette**, pas une clé : il ne référence rien ;
- **la synchronisation du nom vers le serveur.** Il y part déjà, dans chaque
  envoi de réussite (`expediteur.js` → `identite`). Rien à ajouter.

## 4. Critères d'acceptation

- [x] **A1** — `GET /admin/postes` rend **une affiche par zone du plan
  courant**, **huit par A4**, sans qu'aucune liste de zones soit écrite à la
  main. La densité est **une constante nommée** (`POSTES_PAR_FEUILLE`) dont
  descend toute la géométrie : passer à six est une valeur à changer.
- [x] **A2** — L'affiche porte le QR et le nom de la zone en gros, et **rien
  d'autre** — pas de mode d'emploi.
- [x] **A3** — Le QR contient `CCPOSTE:` + la **lettre** de la zone, fait au
  moins 42 mm (le plancher mesuré des étiquettes de blocs), et se relit par un
  **décodeur indépendant** (OpenCV).
- [x] **A4** — `?zone=C` ne rend que cette zone.
- [x] **A5** — La pagination est faite en Python (`fiches.en_feuilles`) ; une
  affiche n'est jamais coupée entre deux pages.
- [x] **A6** — Un plan **sans aucune zone** rend une page qui le dit et renvoie
  vers `/admin/plan`, 200 — pas une page blanche, pas une 500.
- [x] **A7** — `poste.js` décode `CCPOSTE:C` en `"Zone C"` — le libellé est
  **composé par l'application**, et `MOT_ZONE` vaut celui de `fiches.MOT_ZONE`.
- [x] **A8** — `poste.js` refuse un QR de bloc, un dossard, un lien
  d'organisateur et un préfixe sans nom — chacun avec **son** message.
- [x] **A9** — Le geste « Scanner le QR de mon poste » existe dans les réglages
  de la PWA et appelle `identite.renommer()`.
- [x] **A10** — Le préfixe de `poste.js` et celui de `fiches.py` sont égaux, et
  un test le vérifie.
- [x] **A11** — Aucune ressource extérieure dans la page imprimée.
- [x] **A12** — Anonyme → 401, rôle insuffisant → 403, comme `/admin/dossards`.
- [x] **A13** — Le bloc `<header>` de `juge.html` est **inchangé** par cette
  branche.
- [x] **A14** — L'écran d'accueil de la PWA porte le bouton « Scanner le QR de
  mon poste » et son petit texte **tant que le téléphone n'a pas de nom**, et
  **rien** dès qu'il en a un. Une seule fonction décide de cette visibilité.
- [x] **A15** — Deux téléphones portant le **même nom** rendent deux libellés
  **différents** dans la console, et le libellé est composé par **une seule
  fonction** serveur (`contest.libelle_poste`).
- [x] **A16** — Toutes les vues de la console qui nomment un poste affichent le
  **même** libellé — « Qui envoie quoi », la colonne « Téléphone » des
  dernières réussites, la recherche par référence, et le menu de filtrage par
  téléphone.
- [x] **A17** — Un scan de poste réussi **rafraîchit `#nomPoste`** dans
  l'en-tête. C'est la couture avec `fix/revue-du-03-09` : les deux branches ne
  se touchent pas, donc elles ont fusionné sans conflit, et le scan est le seul
  chemin qui renomme le téléphone hors du champ de saisie.

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| Plan vide (aucun mur, ou aucun mur nommé) | Page qui le dit, lien vers « Dessiner le plan du mur », 200 |
| `?zone=Q` absente du plan | Page vide qui **nomme la zone demandée**, 200 — pas une 404 |
| Zone au nom long | `plan_du_mur.ZONE_MAXI` plafonne à **3 caractères** ce qui se dessine dans la console. Le nom rétrécit quand même pour tenir sur une ligne — le plan d'usine est du code, et rien n'y impose ce plafond |
| Zone au nom contenant un espace ou un accent | Encodé tel quel dans le QR, relu tel quel (`valider()` met en majuscules ce qui vient de la console) |
| Deux murs portant la même zone | **Une seule** affiche : les zones sont un ensemble |
| QR de bloc scanné depuis l'écran de poste | Message clair, **aucun renommage** |
| QR de poste scanné depuis l'écran « grimpeur » | Comportement inchangé : dossard inconnu (non-régression) |
| Caméra refusée | Le message de `scan.js`, celui qui explique iOS → Réglages → Safari |
| Scan annulé | Rien ne change, aucun message |
| Aucune compétition active | La page **marche quand même** : le plan ne dépend pas d'une compétition |
| Stockage local indisponible (mode privé) | Le renommage échoue proprement, l'application continue |
| Zone dont le nom commence déjà par « Zone » | **Pas** de double préfixe : `CCPOSTE:Zone Nord` → « Zone Nord » |
| Deux téléphones sur la même zone | Même nom, **libellés distincts** dans la console (le code court) |
| Téléphone qui envoie sans s'être nommé | « Sans nom (3f9a1c2b) » — désignable quand même |
| Saisie manuelle (aucun appareil) | Libellé `null` ; la console dit « saisie de … » |
| Le juge vide le champ du nom à la main | Le bloc de l'écran d'accueil **revient** |
| Scan de poste depuis l'écran d'accueil | Le poste est nommé, et on **reste** sur l'accueil |
