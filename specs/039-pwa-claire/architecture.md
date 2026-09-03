# Architecture — spec 039, l'application juge s'ouvre en clair

## 1. Le motif : deux jeux de variables, un style qui ne connaît que des rôles

Le CSS de `juge.html` n'a jamais nommé une couleur ailleurs que dans `:root` —
à dix exceptions près, qui sont justement ce que cette spec a dû corriger. Le
reste ne parle que de **rôles** : `--fond`, `--carte-active`, `--encre2`,
`--attention`. C'est ce qui permet aux deux jeux de coexister **sans qu'une
seule règle ait à savoir lequel est actif**.

Trois blocs, dans cet ordre :

```css
:root { color-scheme: light dark; /* le CLAIR, complet */ }
@media (prefers-color-scheme: dark) { :root { /* le SOMBRE, complet */ } }
:root { /* ce qui ne dépend pas du thème */ }
```

Le même motif que `admin.html` depuis la spec 021, à une chose près : le
troisième bloc. Il porte les trois valeurs qui sont **identiques** dans les deux
thèmes, et les y écrire une fois vaut mieux que les recopier deux fois — une
valeur recopiée finit par diverger.

`color-scheme: light dark` n'est pas décoratif : sans lui, les cases à cocher,
les champs de saisie et les barres de défilement **natives** resteraient sombres
sur le papier clair. C'est un `<input type=checkbox>` réel dans les Réglages,
pas un dessin.

## 2. Ce qui a dû devenir un rôle

Dix couleurs étaient écrites en dur dans les règles, toutes calées sur le fond
sombre. Elles n'auraient pas suivi le thème :

| Ce qui était écrit | Où | Rôle créé |
| --- | --- | --- |
| `#1E252F` / `#3C4652` | la puce du numéro d'étape, au repos | `--puce`, `--puce-encre` |
| `#3A4759` | la puce d'une étape faite | `--puce-faite` |
| `#12140F` | l'encre de « Envoyer quand même » | `--sur-attention` |
| `rgba(0,0,0,.45)` | l'ombre de la bulle de message | `--ombre` |
| `rgba(229,180,74,.15)` ×2 | le voile des pastilles d'attente et du filtre | `--attention-voile` |
| `rgba(224,112,95,.15)` | le voile de la pastille des refusées | `--alerte-voile` |
| `#3E8CF7` ×3, `#F7F9FC` | le bleu des actions, des liens, des cases | `--action`, `--action-texte`, `--sur-action` |
| `#000` | le viseur | **aucun** — voir § 5 |

Trois de ces rôles se sont **dédoublés**, et c'est le fond du travail :

- **`--attention` / `--attention-fond`.** Le jaune qui porte un **aplat** ne
  peut pas être celui qu'on **écrit** sur du papier. L'aplat de « Envoyer quand
  même » reste `#E5B44A` dans les deux thèmes — un jaune franc avec de l'encre
  sombre se lit partout, 9,7:1. Le **texte** d'avertissement, lui, descend à
  `#7A4F0A` en clair.
- **`--action` / `--action-texte`.** `#3E8CF7` sur blanc mesure **3,1:1** :
  au-dessus du seuil d'un gros glyphe, sous celui d'un texte. L'aplat prend
  `#1F6FD0` (4,95:1 avec du blanc dessus), le lien `#1A5FB4` (6,0:1).
- **`--attention` / `--attention-voile`.** Le voile est tiré du jaune **vif**,
  pas de `--attention` : un ocre sombre dilué à 30 % dans du papier sable ne
  donne pas un bandeau jaune, il donne un khaki terne. Constaté à l'écran, et
  c'est pour ça que le voile est un rôle et non un `color-mix` de l'autre.

## 3. C1 tenue : l'aplat garde la couleur, le texte se corrige

La contrainte qui commande tout : **la teinte du circuit porte de
l'information**. Un juge lit la couleur de l'écran pour vérifier qu'il est sur
le bon circuit.

L'**aplat** — le bouton « Envoyer », la pastille du tag — garde donc la couleur
exacte du circuit, au point près, dans les deux thèmes. C'est lui qu'on lit à
deux mètres, et il n'est pas négociable.

Mais la même teinte sert aussi de **texte** : le libellé « BLOC » et le détail
« U13 · U15 — Jaune ». Un jaune pur sur du papier mesure **1,9:1** — on ne le
lit pas. D'où `--circuit-texte`, qui tire la teinte **de moitié vers l'encre**
en clair et la laisse intacte en sombre :

```css
/* clair  */ --circuit-texte: color-mix(in srgb, var(--circuit) 50%, var(--encre));
/* sombre */ --circuit-texte: var(--circuit);
```

Le jaune écrit passe ainsi à **5,1:1**, le vert à 6,1:1, et la hue reste
reconnaissable. Même raison pour `--trait-circuit`, le liseré de la carte du
bloc : un jaune à 50 % de transparence sur du blanc disparaît, il est mélangé au
trait neutre plutôt que dilué dans le fond.

`color-mix()` était déjà une dépendance du fichier avant cette spec (le liseré
de la carte, le voile du hors-circuit, la pulsation du bouton) : Safari 16.4+,
Chrome 111+. Aucun téléphone qui faisait tourner l'application ne la perd.

## 4. Le circuit « Noir » : le seul qui dépend du thème

`couleurs.js` est **partagé de fait** avec l'Android (`ui/theme/Color.kt`) :
c'est la même famille de six couleurs, et elle ne bouge pas. Une exception, une
seule, et elle est écrite dans le fichier :

```js
export const NOIR = { clair: "#22201B", sombre: "#E8EBF0" };
export function couleurDeCircuit(nom, sombre = enSombre()) { … }
```

- `enSombre()` lit `matchMedia`. **Hors navigateur** — les tests de `tests/js/`
  tournent sous Node — il n'y en a pas, et la réponse est *clair* : le défaut de
  l'application, pas une valeur de repli arbitraire.
- Le paramètre `sombre` est **explicite et surchargeable** : c'est ce qui rend
  les deux branches testables sans simuler un navigateur.
- `CIRCUITS.noir` vaut `NOIR.clair` — une seule source pour la valeur par
  défaut, plutôt que la même chaîne écrite à deux endroits.

Et parce que la teinte est posée **en variable en ligne** par `redessiner()`, un
téléphone qui bascule clair/sombre en cours de journée — le réglage automatique
d'iOS le fait au coucher du soleil, et une compétition finit le soir — gardait
la craie sur le papier. `juge.js` écoute donc `matchMedia(...).change` et
redessine. Le CSS suivait tout seul ; c'est la seule valeur qui ne le faisait
pas.

## 5. Le viseur reste noir, et c'est un choix mesurable

Le seul `#000` qui survit. Ce n'est pas du décor : c'est l'image de la caméra.
Un cadre clair autour d'un flux vidéo éblouit dans la pénombre et fait fermer
l'iris du capteur — le QR met alors plus longtemps à être reconnu. Même raison
que le mur toujours clair de `resultats.html` : **la couleur suit l'usage, pas
le thème.** Le commentaire est dans le code, à côté de la règle.

## 6. Ce qui n'a pas de requête media : le manifeste, et la barre d'état

Deux endroits échappent au CSS, et ils demandent une décision plutôt qu'une
technique.

**Le manifeste.** `background_color` et `theme_color` sont l'écran de démarrage
et la barre de l'application **installée**. Un manifeste n'a pas de requête
media : ils portent donc le thème par **défaut**, le clair. Un téléphone réglé
en sombre verra un démarrage clair puis une application sombre ; l'inverse — un
démarrage noir sur les téléphones du plus grand nombre — serait le mauvais
compromis. `#F3EEE3` y est **la même valeur** que `--fond` : deux valeurs qui
dérivent font un liseré au démarrage, et un test les compare.

**La barre d'état iOS.** `apple-mobile-web-app-status-bar-style` passe de
`black-translucent` à `default` : sur un fond clair, l'heure et la batterie
s'écrivaient en **blanc sur du papier sable**. `default` laisse iOS écrire en
sombre sur clair et en clair sur sombre — exactement ce que les deux thèmes
demandent.

**`<meta name="theme-color">`** devient deux balises, `media` à l'appui, et le
**clair est en premier** : un navigateur qui ignore l'attribut — les iOS
antérieurs à 15.4, donc des téléphones de bénévoles — garde la première, et
c'est le défaut voulu.

## 7. La coquille du service worker

`CACHE` passe de `climbcontest-juge-v5` à **`v6`**. La coquille porte `/juge`,
donc tout le CSS : sans changement de nom, `activate` ne supprime rien et un
téléphone déjà installé **rouvrirait l'ancienne page sombre**. `couleurs.js`
change aussi, et une coquille qui mélangerait l'ancien CSS et le nouveau module
afficherait de la craie sur du papier.

Comme d'habitude (spec 007), la nouvelle version est prise **au lancement
suivant**, jamais en pleine compétition.

## 8. Les mesures, en clair

Toutes calculées sur les valeurs livrées, formule WCAG 2.1.

| Ce qu'on lit | Sur quoi | Rapport |
| --- | --- | --- |
| `--encre` — les noms, les tags, « À scanner » | la carte active (blanche) | **18,4:1** |
| `--encre` | le papier | **15,9:1** |
| `--encre2` — le détail, le n° de dossard, le nom du poste | la carte faite | **5,6:1** |
| `--encre3` — le libellé de l'étape **pas encore atteignable** | la carte en attente | **3,9:1** |
| « ENVOYER » désactivé (1,9 rem, 800) | la carte en attente | **3,9:1** (seuil du gros texte : 3:1) |
| le bleu des liens `--action-texte` | la carte faite | **6,0:1** |
| du blanc sur l'aplat bleu `--action` | — | **4,95:1** |
| `--attention` — le texte du hors-circuit | son voile | **5,3:1** |
| `--alerte` — « 1 refusée » | son voile | **5,0:1** |
| l'encre sombre sur l'aplat de « Envoyer quand même » | — | **9,7:1** |
| le tag « ZJ1 » sur l'aplat jaune | — | **10,3:1** |
| le tag sur les aplats bleu / mauve / rouge | — | **3,2:1** — gros texte, et **identique en sombre** : c'est la palette Android, inchangée |
| le circuit **écrit** (jaune, le pire cas) | la carte faite | **5,1:1** |

Deux valeurs sont sous 4,5:1 et le sont **exprès** :

- **`--encre3` à 3,9:1** est le libellé d'une étape qu'on ne peut pas encore
  remplir — « pas ton tour ». Il passe à `--encre` (18:1) dès que l'étape
  devient active. Le thème sombre le rend à **1,9:1** ; le clair fait deux fois
  mieux, et la hiérarchie des trois encres reste lisible comme hiérarchie.
- **les aplats bleu / mauve / rouge à 3,2:1** portent le tag du bloc et le mot
  « ENVOYER » — 1,85 à 1,9 rem en graisse 800, dont le seuil est 3:1 — et le
  **chiffre de la puce d'étape**, lui à 0,7 rem : le seul texte de l'écran sous
  son seuil. Il dit l'ordre des deux étapes, que leur position dit déjà, et le
  libellé « BLOC » à côté se lit, lui, à 5,1:1.
  Ces trois teintes sont les couleurs de l'Android **au point près**, et elles
  sont **identiques dans les deux thèmes** : ce n'est pas une régression du
  clair. Les corriger ici casserait C1 et la parité sur ce qui porte de
  l'information.
