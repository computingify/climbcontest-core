# Spec 035 — Refondre le design de l'application juge

> **Cette spec ne livre pas de code.** Elle livre des **maquettes** et une
> **question**. Rien de `climbcontest/templates/juge.html` ni de
> `climbcontest/static/juge/*` n'est modifié par cette PR. La porte 2 porte ici
> sur un choix de direction, pas sur une implémentation : Adrien tranche, et
> l'implémentation fait l'objet d'une spec et d'une PR distinctes.

## 1. Le fait générateur

Demande d'Adrien, 3 septembre 2026, mot pour mot :

> « Le design de cette application mobile, de cette PWA, ne me convainc toujours
> pas. Je la trouve vraiment trop sobre, trop moche et tout en noir ce n'est
> vraiment pas terrible. On n'a pas de design, c'est vraiment trop moche. Il
> faut faire quelque chose de beau et qui fasse waouh. »

Et la méthode, imposée dans la même phrase : un HTML interactif à cliquer
**avant toute implémentation**, dans une **PR à part**.

Trois mots portent le diagnostic, et ils ne disent pas la même chose :

- **« trop sobre »** — l'écran ne montre aucune intention. Il a été construit
  par corrections successives (specs 007, 019, 027) : chaque geste était juste,
  aucun n'a jamais posé de parti pris.
- **« tout en noir »** — le fond a été réchauffé le 02/09 (spec 027), mais le
  réchauffement s'est arrêté à une lueur ocre à 11 % sur un gris à `#15161B`.
  De loin, c'est toujours noir.
- **« qui fasse waouh »** — c'est le seul critère qui ne se vérifie pas en
  relisant du code. Il se vérifie à l'écran, sur un vrai téléphone, et c'est la
  raison d'être des maquettes.

## 2. Ce que l'écran doit continuer à faire

Une refonte qui casserait un de ces points serait un recul, quel que soit son
aspect. Ils viennent de l'inventaire de l'app juge et des specs 007, 019 et 027.

| # | Contrainte | D'où elle vient |
| --- | --- | --- |
| C1 | **La couleur porte de l'information.** La teinte du circuit (jaune, vert, bleu, mauve, rouge, noir) prend l'écran dès que le bloc est scanné. Un design qui mange cette couleur avec de la décoration est disqualifié. | Spec 019, et `couleurs.js` partagé avec l'Android |
| C2 | **Aucune dépendance extérieure.** Pas de CDN, pas de framework, pas de police distante. `Archivo` est servie localement et mise en cache par le service worker : la PWA doit s'habiller hors ligne. | Spec 007 |
| C3 | **Tenu à une main, toute la journée.** Cibles ≥ 44 px, action principale dans le rayon du pouce, `viewport-fit=cover` et marges `env(safe-area-inset-*)`. | Le terrain |
| C4 | **Lisible dans une salle** — et dehors. Contraste élevé, gros chiffres, jamais de gris clair sur gris. | D2, D4, D7 de l'inventaire |
| C5 | **« Effacer » ne pèse jamais autant qu'« Envoyer »**, et n'est jamais collé dessous. | F5 de l'inventaire : un pouce qui glisse perdait le scan |
| C6 | **Le voyant de connexion reste barré** quand le serveur est injoignable. La forme dit la panne, la couleur la confirme — ~8 % des hommes ne distinguent pas le vert du rouge. | Spec 007 |
| C7 | **On n'empêche jamais l'envoi.** Le hors-circuit avertit en jaune d'attention et se laisse forcer ; il ne bloque pas et n'affiche pas de rouge d'erreur. | Spec 019 |
| C8 | **L'identité est celle du club** : Annonay Escalade, son logo, son ocre `#E0A94A` / `#B5761C`. | Spec 027, écran d'accueil |

## 3. Ce que la PR livre

**Une page de maquettes autonome**, `specs/035-refonte-pwa-juge/maquettes/index.html`,
qui s'ouvre en `file://`, sans serveur ni réseau. Elle contient :

- **quatre directions** franchement différentes, nommées, chacune avec son parti
  pris en une phrase (§ 4) ;
- un **cadre de téléphone de 390 × 844**, la taille réelle de l'écran, pour
  juger ce qu'on verra vraiment et pas une vignette flatteuse ;
- la **bascule d'une direction à l'autre en un clic**, sans rechargement ;
- la navigation entre les **cinq écrans** — principal, scanner, réglages, mes
  scans, accueil — et les **cinq états** de l'écran principal — rien de scanné,
  grimpeur scanné, les deux scannés, hors-circuit, envoi en cours ;
- le choix de la **couleur du circuit** parmi les six, pour voir C1 à l'œuvre ;
- les **pastilles de file** et le **voyant réseau** en interrupteurs ;
- une **simulation de scan** : appuyer sur une carte ouvre le viseur, qui rend
  un résultat au bout d'une seconde. On essaie le geste, pas seulement l'image ;
- un **mode plein écran** qui retire le cadre, pour essayer au doigt sur le vrai
  téléphone ;
- une **adresse rejouable** : chaque état s'écrit dans l'URL
  (`?d=B&e=principal&s=hors&c=mauve`), ce qui permet de renvoyer un écran précis
  et de le capturer sans clic.

## 4. Les quatre directions, et ce qui les sépare

Elles ne sont pas quatre nuances d'une même idée. Elles se distinguent sur
**deux axes** : le fond est-il clair ou sombre, et jusqu'où va la couleur du
circuit.

| | Fond | La couleur du circuit… | Le circuit « Noir » devient |
| --- | --- | --- | --- |
| **A — Plein Jour** | sable clair `#F3EEE3` | remplit la carte du bloc et le bouton, en aplat imprimé | **du vrai noir** `#16130E` |
| **B — Bascule** | neutre froid `#0E1015` au repos | **inonde tout l'écran**, fond compris, et le bouton s'inverse | un fond quasi noir `#0B0D12` |
| **C — Ocre & Ardoise** | sombre chaud `#14120E` | remplit la carte du bloc d'un aplat plein | de la **craie** `#E8EBF0`, comme aujourd'hui |
| **D — Grand Pouce** | clair en haut, socle sombre en bas | teinte la ligne du bloc et le **disque** d'envoi | `#15161A`, sur le haut clair |

### A — Plein Jour

Du papier sable, de l'encre presque noire, et la couleur du circuit posée en
aplat cerclé d'un liseré d'encre — la matière des étiquettes de blocs collées
au mur (spec 024). Le bouton a une ombre franche de 5 px : il a l'air d'être
posé sur la page.

C'est la réponse directe à « tout en noir ce n'est pas terrible ». Et elle
apporte un bénéfice qu'aucune direction sombre ne peut donner : **le circuit
Noir redevient noir**. La craie de `couleurs.js` n'est pas un choix graphique,
c'est une rustine imposée par le fond sombre — « un aplat noir sur un fond
presque noir ne se verrait pas ». Sur du sable, la rustine disparaît.

Le risque est connu et documenté : D2 de l'inventaire dit qu'un écran clair
éblouit quand on lève les yeux vers le mur. Il n'a jamais été mesuré sur le
terrain, et la salle d'Annonay a une baie vitrée.

### B — Bascule

Au repos, l'écran est neutre et froid. Dès que le bloc est scanné, **tout passe
à la teinte du circuit** — fond compris — et le bouton s'inverse : noir sur
jaune, blanc sur rouge. Un organisateur qui traverse la salle lit le circuit du
poste à deux mètres, sans lire un mot.

Techniquement, toutes les surfaces sont exprimées en **part d'encre**
(`color-mix(in srgb, var(--encre-circuit) 11%, transparent)`) : elles restent
lisibles que le circuit soit jaune (encre sombre) ou bleu (encre claire), sans
une seule règle par couleur.

Deux objections, visibles dans les maquettes et à trancher :

1. **Un circuit rouge inonde l'écran de rouge.** Rien n'est cassé, mais tout le
   monde lit un écran rouge comme une erreur.
2. **Les couleurs d'état perdent leur place.** Sur un fond jaune, un vert vif ne
   se lit plus. Les maquettes les mélangent à l'encre pour garder du contraste,
   et posent l'avertissement hors-circuit sur une plaque d'encre pleine — mais
   c'est une compensation, pas une solution franche.

### C — Ocre & Ardoise

Le sombre, mais chaud et signé. L'ocre du club tient la **structure** — les
numéros d'étape, le filet sous l'en-tête, la bordure de l'étape active — et la
carte du bloc devient un **aplat plein** de son circuit, avec une lueur portée.

C'est la direction la plus proche de l'existant, et la seule qui ne remet en
cause aucune décision passée : sombre par choix mesuré, craie pour le noir,
identité ocre. Elle répond à « trop sobre » mais pas à « tout en noir ».

### D — Grand Pouce

C'est la seule direction qui change **l'architecture de l'écran**, pas
seulement sa peau. L'écran se coupe en deux : en haut, sur clair, **ce qu'on
lit** — deux lignes compactes, libellé à gauche, valeur en gros à droite ; en
bas, un **socle sombre arrondi** où tombe le pouce, et **rien d'autre** que
l'action : un disque de 210 px, « Effacer » sous lui en discret.

C'est la lecture la plus littérale de « tenu à une main toute la journée ». La
question qu'elle pose : est-ce que deux cartes réduites à des lignes disent
encore assez, quand le geste est répété deux cents fois ?

## 5. Critères d'acceptation

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A1 | La page s'ouvre en `file://`, sans serveur, sans réseau, sans CDN | Ouvrir le fichier depuis le Finder, couper le wifi |
| A2 | Les quatre directions se comparent sans rechargement | Cliquer les quatre cartes |
| A3 | Les cinq écrans et les cinq états sont atteignables dans chaque direction | Parcourir les 4 × 5 combinaisons |
| A4 | Les six couleurs de circuit sont exactement celles de `couleurs.js` | Comparer les valeurs, y compris le repli du « Noir » |
| A5 | Le cadre affiche 390 × 844 réels, et le mode plein écran retire le cadre | Capture mesurée à 390 × 844 |
| A6 | La page se manipule au doigt sur le téléphone d'Adrien comme à la souris | Essai sur les deux |
| A7 | Aucune donnée personnelle, aucun nom réel, aucun secret | Relecture ; les noms des maquettes sont inventés |
| A8 | La spec dit **ce qui reste à trancher**, et la PR pose la question | § 7 |

## 6. Cas limites traités par les maquettes

| Cas | Ce que les maquettes montrent |
| --- | --- |
| **Le circuit « Noir »** | Chaque direction déclare son rendu. C'est le seul circuit dont la couleur dépend du fond, donc le seul argument technique dans le débat clair / sombre. |
| **Un circuit rouge** | En direction B, l'écran entier devient rouge alors que rien n'est en erreur. Montré tel quel, sans le corriger : c'est une décision, pas un bug. |
| **Hors-circuit** | Le bandeau jaune d'attention et le bouton « Envoyer quand même » dans les quatre directions. En B, sur fond inondé, l'avertissement devient une plaque d'encre pleine, sinon il disparaît. |
| **Serveur injoignable** | Voyant rouge **barré**, dans les quatre directions. |
| **File d'attente et refus** | Pastilles dans l'en-tête, jamais en bandeau qui pousse la mise en page vers le bas (leçon D9 de l'inventaire). |
| **La bande des six circuits à l'accueil** | Elle dit en une ligne ce que l'application fait de la couleur — et le ruban « Noir » a besoin d'un contour pour exister sur les fonds sombres, ce qui rejoue le même problème. |

## 7. Ce qui reste à trancher — **c'est le but de cette PR**

| # | Question | Ce qui en dépend |
| --- | --- | --- |
| **D1** | **Quelle direction ?** A, B, C ou D — ou un croisement explicite, par exemple la bascule de B posée sur le papier de A. | Tout le reste |
| **D2** | **Clair ou sombre ?** L'app est sombre depuis la refonte Android, sur un argument (« un écran clair éblouit quand on lève les yeux vers le mur ») **jamais mesuré en salle**. A et D remettent la décision sur la table. | D1, et la cohérence avec l'app Android, qui devra suivre ou diverger |
| **D3** | **Jusqu'où va la couleur du circuit ?** Bordure et bouton (A, C, D) ou écran entier (B) ? Et si c'est l'écran entier : que fait-on du rouge, qui se lit comme une erreur ? | La lisibilité des couleurs d'état |
| **D4** | **Le circuit « Noir » reste-t-il en craie ?** La craie est une rustine du fond sombre. Un fond clair la supprime. | D2 |
| **D5** | **L'app Android suit-elle ?** Deux clients, une seule identité, dit `couleurs.js`. Une refonte du seul web crée un écart entre deux téléphones de bénévoles le même jour. | Le périmètre de la spec d'implémentation |

## 8. Hors périmètre

- **Toute implémentation.** `juge.html` et `static/juge/*` ne sont pas touchés.
- **L'app Android.** Elle sera traitée quand D5 sera tranchée.
- **La console** (`admin.html`) et la **page de résultats**, refaites par les
  specs 021 et 016.
- **Les fonctionnalités.** Aucune n'est ajoutée, retirée ni renommée : c'est une
  refonte visuelle, et le vocabulaire de l'écran reste celui d'aujourd'hui.
