# Spec 042 — les Réglages au pouce

## 1. D'où vient cette spec

Adrien, le 03/09/2026, à propos de l'écran **Réglages** de la PWA juge :

> « Si le juge set manuellement le nom de son téléphone il faut retirer la
> demande de scan du qrcode de paramétrage. Ensuite toutes les coches pour le
> paramétrage que tu trouves tu les remplaces par un interrupteur comme dans
> toutes les applications mobiles. »

Deux demandes indépendantes, sur le même écran. Elles voyagent ensemble parce
qu'elles touchent le même bloc de gabarit, pas parce qu'elles se tiennent.

### « La demande de scan » désignait deux objets

La phrase pouvait viser deux endroits, et ils ne se comportent pas pareil :

| Où | Ce qui se passe aujourd'hui |
| --- | --- |
| Le bloc `#poste` de l'**écran d'accueil** (spec 034) | Il disparaît **déjà** dès que le téléphone porte un nom, tapé ou scanné — `proposerDeNommerLePoste()` |
| Le bouton `#btnScannerPoste` des **Réglages** (spec 034) | Il reste affiché quoi qu'il arrive, bouton bleu pleine largeur et son explication |

Les deux ont été capturés côte à côte sur l'application réelle et montrés à
Adrien avant toute ligne de code : `maquettes/index.html`, section 1. **Il a
confirmé qu'il visait celui des Réglages.**

## 2. Ce qu'on cherche

Un écran de réglages qui ne demande rien quand il n'y a plus rien à demander,
et dont les commandes ressemblent à celles que le bénévole a déjà sous le pouce
dans son propre téléphone.

## 3. Ce qui est décidé

### D1 — La demande de scan devient un geste (variante B)

Trois variantes ont été capturées sur l'application réelle et montrées
(`maquettes/index.html`, section 2). **Adrien a retenu la B**, le 03/09 :

| | Ce que ça fait | Verdict |
| --- | --- | --- |
| Aujourd'hui | Bouton bleu pleine largeur + explication, sur un téléphone déjà nommé | Ce qu'on enlève |
| A | Bouton **et** explication disparaissent. Vider le champ est alors le seul chemin pour rescanner | Écartée |
| **B** | La **demande** s'en va, le **geste** reste : le bouton devient un lien discret, à la place et dans le style de « Voir mes scans » | **Retenue** |

Ce que B préserve, et que A perdait : un téléphone qui change de table en
cours de journée se rescanne **sans avoir à vider le champ d'abord**. Le geste
n'a jamais été le problème — c'est l'insistance qui n'avait plus lieu d'être.

⚠️ **Le déclencheur est le NOM, pas la façon dont il est arrivé.** Un nom posé
par scan éteint la demande exactement comme un nom tapé : c'est le même état,
et deux règles pour deux chemins finiraient par diverger. C'est déjà la règle
de l'écran d'accueil ; les deux surfaces sont désormais décidées par **une
seule fonction**.

### D2 — La case à cocher devient un interrupteur

`#garderGrimpeur` (« Garder le grimpeur entre deux blocs ») est la **seule**
case à cocher de toute l'application juge — inventaire fait sur `juge.html` et
les seize modules de `static/juge/`. Elle prend la forme de l'interrupteur
d'iOS et d'Android : 51 × 31, pastille de 27, le bleu `--action` quand c'est
allumé.

Le motif n'est pas inventé ici : c'est celui de `label.bascule` + `.glissiere`
écrit pour la console à la spec 021, repris **mot pour mot** dans son principe.
La case à cocher **native** est conservée, juste rendue invisible — elle garde
le clavier, le focus, l'état et le lecteur d'écran, que `role="switch"` fait
annoncer « interrupteur, activé » plutôt que « case à cocher, cochée ».

## 4. Périmètre

**Touché :** `climbcontest/templates/juge.html`,
`climbcontest/static/juge/juge.js`, `climbcontest/static/juge/sw.js` (le nom du
cache, sans quoi les téléphones déjà installés garderaient l'ancienne page).

**Pas touché :** le serveur, la base, l'API, la console, l'application Android,
et le format du QR de poste. Aucun réglage ne change de valeur ni de clé de
rangement : `garder-grimpeur` reste `garder-grimpeur`.

## 5. Critères d'acceptation

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| C1 | Téléphone **sans nom** : les Réglages montrent le bouton bleu pleine largeur **et** son explication | Test navigateur, `display` et largeur calculés |
| C2 | Téléphone **nommé** : plus de bouton bleu ni d'explication ; un lien discret porte le même geste, au même endroit | Test navigateur, fond transparent et largeur de trait |
| C3 | Le lien **fonctionne** : il ouvre le viseur, comme le bouton | Le gestionnaire est posé sur le même nœud — test de gabarit + test navigateur |
| C4 | Taper un nom éteint la demande **sans recharger l'écran** ; vider le champ la rallume | Test navigateur, frappe simulée dans `#nomTelephone` |
| C5 | Un nom posé par **scan** éteint la demande comme un nom tapé | Une seule fonction décide — test de source |
| C6 | `#garderGrimpeur` est calculé en interrupteur : case native invisible, glissière visible, pastille à droite quand c'est allumé | Test navigateur, styles calculés + position de la pastille |
| C7 | L'interrupteur reste **utilisable au clavier et au lecteur d'écran** | `role="switch"`, `:focus-visible` porté par la glissière — test navigateur |
| C8 | Le réglage continue de se ranger et de se relire | Test navigateur : cliquer, rouvrir, retrouver l'état |
| C9 | Les deux thèmes tiennent | Captures clair **et** sombre, `maquettes/` |
| C10 | Un téléphone déjà installé reçoit la nouvelle page | Le nom du cache du service worker change — test de source |

## 6. Cas limites

| Situation | Ce qui doit se passer |
| --- | --- |
| Le juge tape **une seule lettre** puis efface | La demande s'éteint à la première lettre et se rallume à l'effacement. C'est déjà le comportement de l'écran d'accueil : les deux surfaces bougent ensemble, et jamais l'une sans l'autre |
| Le champ ne contient que des espaces | `nettoyerLeNom` rend `null` : le téléphone n'a **pas** de nom, la demande reste. Aucune règle nouvelle — c'est la fonction qui décide déjà partout |
| Stockage indisponible (mode privé, quota) | `renommer` lève ; l'écran garde la demande, ce qui est vrai : le nom n'a pas été rangé |
| Un téléphone sur une version antérieure du cache | Il reçoit `/juge` frais au lancement **suivant** (stale-while-revalidate assumé, spec 014). Le nom du cache change, donc l'ancienne coquille est jetée |
| `prefers-reduced-motion` | La glissière ne s'anime pas |

## 7. Hors périmètre

- Les sections « Thème » (spec 040) et « Catalogue »/« Application »
  (spec 030), mergées sur `master` pendant l'écriture de ce lot. Aucune ne
  porte de case à cocher, aucune ne touche le bouton de scan — mais toutes
  atterrissent dans le même écran. Ce que la fusion donne est capturé dans
  `maquettes/`, section 4.
- Les cases à cocher de la **console** (`admin.html`, `plan.html`) : la demande
  vise l'application juge. `admin.html` a déjà ses interrupteurs.
