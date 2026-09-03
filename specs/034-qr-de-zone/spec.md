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

### F2 — Le format du QR : `CCPOSTE:` + le nom de la zone

```
CCPOSTE:Zone C
```

Le préfixe n'est pas décoratif. Trois familles de QR circulent le jour J, et le
même viseur les voit toutes :

| QR | Contenu | Ce qu'il ne doit **jamais** faire |
| --- | --- | --- |
| Dossard | `42` | renommer le téléphone « 42 » |
| Bloc | `ZJ6` | renommer le téléphone « ZJ6 » |
| Lien de l'organisateur | `https://…/juge?j=…` | renommer le téléphone avec une URL |
| **Poste** | `CCPOSTE:Zone C` | — |

Sans préfixe, un juge qui scanne un bloc par erreur depuis cet écran renommerait
son poste « ZJ6 » **sans s'en apercevoir**, et la console afficherait « ZJ6 »
pour tous ses envois de la journée. Le préfixe rend la confusion **impossible**,
pas improbable.

Choix du texte brut plutôt que d'une URL (`…/juge?poste=Zone+C`) :

- une URL scannée par **l'appareil photo natif** du téléphone ouvre un
  navigateur. Le juge se retrouverait dans Safari au lieu de son application,
  avec une deuxième instance sans file d'attente. `CCPOSTE:Zone C` scanné par
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

**Deux par A4**, chacune 188 × 136 mm :

```
┌────────────────────────────────────────────┐
│                                            │
│              ┌──────────────┐              │
│              │              │              │
│              │      QR      │              │
│              │    80 mm     │              │
│              │ CCPOSTE:C    │              │
│              └──────────────┘              │
│                                            │
│                   ZONE                     │
│                    C          ← 40 mm      │
│                                            │
│   Réglages → Scanner le QR de mon poste    │
└────────────────────────────────────────────┘
                188 × 136 mm
```

Grande, parce que ce n'est pas une étiquette qu'on colle : c'est un carton posé
sur une table, que le juge doit repérer en arrivant et qui doit rester lisible
quand quelqu'un pose un stylo dessus. Le nom de la zone est le plus gros élément
— c'est ce qu'on vérifie avant de scanner.

La marche à suivre est **écrite sur l'affiche** : un bénévole qui n'a pas écouté
le briefing trouve le geste sans demander.

### F5 — Le QR, généré localement

`qr.svg("CCPOSTE:" + zone, cote_mm=80)`. Aucun appel réseau, comme les dossards
depuis la spec 005 et les étiquettes depuis la 024 : on imprime parfois la
veille au soir, parfois sans connexion.

À 80 mm, un `CCPOSTE:Zone C` tient en version 1 ou 2 : plus de 2 mm par module,
soit quatre fois le plancher de `qr.MODULE_MINI_MM`. La marge est là pour les
noms de zone longs, que le plan autorise.

### F6 — Un préfixe, deux langages, un test qui les tient

Le préfixe est écrit **deux fois** : dans `fiches.py` (qui l'imprime) et dans
`poste.js` (qui le lit). Deux constantes dans deux langages qui doivent rester
égales : c'est exactement le motif qui dérive en silence, et le jour où il
dérive, **tous les QR imprimés cessent d'être lus** sans qu'une seule ligne de
code ait l'air fausse.

Un test Python lit `poste.js`, en extrait le préfixe, et le compare à celui de
`fiches.py`. Le piège n'est pas documenté : il est **détectable**.

## 3. Périmètre

**Inclus** : un module `poste.js` testable sur Node, un geste dans les réglages
de la PWA, une route `/admin/postes`, un gabarit `postes.html`, une carte dans
la vue **Téléphones** de la console, les tests.

**Exclu, à dessein** :

- **l'affichage du nom du poste en haut de l'application.** Adrien l'a demandé
  dans le même message, et c'est traité **ailleurs** : l'en-tête de `juge.html`
  est refondu en parallèle dans `fix/revue-du-03-09`, qui y pose l'emplacement
  `#nomPoste`. Deux branches qui réécrivent le même `<header>` fusionneraient
  sans conflit et en silence — le motif est déjà arrivé une fois sur ce dépôt
  (spec 032, deux fonctions du même nom). Cette spec **ne touche pas au bloc
  `<header>`**, et se contente d'appeler `identite.renommer()` : le nom
  s'affichera tout seul quand les deux branches seront ensemble ;
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

- [ ] **A1** — `GET /admin/postes` rend **une affiche par zone du plan
  courant**, deux par A4, sans qu'aucune liste de zones soit écrite à la main.
- [ ] **A2** — L'affiche porte le QR, le nom de la zone en gros, et la marche à
  suivre.
- [ ] **A3** — Le QR contient `CCPOSTE:` + le nom de la zone, et se relit par un
  décodeur indépendant à 80 mm.
- [ ] **A4** — `?zone=C` ne rend que cette zone.
- [ ] **A5** — La pagination est faite en Python (`fiches.en_feuilles`) ; une
  affiche n'est jamais coupée entre deux pages.
- [ ] **A6** — Un plan **sans aucune zone** rend une page qui le dit et renvoie
  vers `/admin/plan`, 200 — pas une page blanche, pas une 500.
- [ ] **A7** — `poste.js` décode `CCPOSTE:Zone C` en `"Zone C"`.
- [ ] **A8** — `poste.js` refuse un QR de bloc, un dossard, un lien
  d'organisateur et un préfixe sans nom — chacun avec **son** message.
- [ ] **A9** — Le geste « Scanner le QR de mon poste » existe dans les réglages
  de la PWA et appelle `identite.renommer()`.
- [ ] **A10** — Le préfixe de `poste.js` et celui de `fiches.py` sont égaux, et
  un test le vérifie.
- [ ] **A11** — Aucune ressource extérieure dans la page imprimée.
- [ ] **A12** — Anonyme → 401, rôle insuffisant → 403, comme `/admin/dossards`.
- [ ] **A13** — Le bloc `<header>` de `juge.html` est **inchangé** par cette
  branche.

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| Plan vide (aucun mur, ou aucun mur nommé) | Page qui le dit, lien vers « Dessiner le plan du mur », 200 |
| `?zone=Q` absente du plan | Page vide qui **nomme la zone demandée**, 200 — pas une 404 |
| Zone au nom long (30 caractères) | Le QR reste lisible ; le nom rétrécit pour tenir sur une ligne |
| Zone au nom contenant un espace ou un accent | Encodé tel quel dans le QR, relu tel quel |
| Deux murs portant la même zone | **Une seule** affiche : les zones sont un ensemble |
| QR de bloc scanné depuis l'écran de poste | Message clair, **aucun renommage** |
| QR de poste scanné depuis l'écran « grimpeur » | Comportement inchangé : dossard inconnu (non-régression) |
| Caméra refusée | Le message de `scan.js`, celui qui explique iOS → Réglages → Safari |
| Scan annulé | Rien ne change, aucun message |
| Aucune compétition active | La page **marche quand même** : le plan ne dépend pas d'une compétition |
| Stockage local indisponible (mode privé) | Le renommage échoue proprement, l'application continue |
