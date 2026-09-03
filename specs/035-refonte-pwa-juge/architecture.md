# Architecture : 035 — Refonte du design de l'application juge

Deux architectures cohabitent dans cette spec : celle de la **maquette**,
livrée ici, et celle de l'**implémentation future**, qui ne l'est pas. La
seconde n'est décrite que pour montrer que la première ne s'en éloigne pas.

## 1. La maquette : un fichier, quatre visages

`specs/035-refonte-pwa-juge/maquettes/index.html` — un seul fichier, aucune
dépendance, ouvrable en `file://`.

Le choix structurant : **une seule structure HTML pour les quatre directions.**
Le squelette de l'application est écrit une fois ; ce sont des **variables CSS**
et une poignée de règles ciblées qui font les quatre visages. Quatre copies du
même écran auraient divergé dès la première correction — et une maquette qui
ment sur un état est pire que pas de maquette.

```
body.planche            le cadre autour : titre, 4 directions, commandes
 └ .cadre               le châssis, 414 × 868, mis à l'échelle par le JS
    └ .chassis          390 × 844 — la taille réelle de l'écran
       └ .app[data-d]   l'application ; data-d vaut A, B, C ou D
          ├ .e-accueil
          ├ .e-principal
          ├ .e-scanner
          ├ .e-reglages
          └ .e-scans
```

### L'état, en attributs

Tout l'état visuel tient dans des attributs `data-*` posés sur `.app`. Aucune
classe n'est ajoutée ou retirée à la main sur un élément profond : le CSS lit
l'état à la racine et se débrouille.

| Attribut | Valeurs | Ce qu'il pilote |
| --- | --- | --- |
| `data-d` | `A` `B` `C` `D` | La direction — donc toute la palette |
| `data-ecran` | `accueil` `principal` `scanner` `reglages` `scans` | Quel écran est visible |
| `data-grimpeur` | `0` `1` | L'étape 1 est faite |
| `data-bloc` | `0` `1` | L'étape 2 est faite — **et l'entrée de la couleur** |
| `data-hors` | `0` `1` | L'avertissement hors-circuit |
| `data-envoi` | `0` `1` | La toupie et l'atténuation du bouton |
| `data-pret` | `0` `1` | La pulsation du bouton |
| `data-circuit` | `jaune` … `noir` | Documentaire ; la teinte réelle passe par les variables |
| `data-reseau` | `ok` `ko` `doute` | Le voyant, et son trait |
| `data-file` | `0` `1` | Les pastilles de file et de refus |

L'**étape active** ne se pose jamais : elle se déduit par voisinage, exactement
comme dans le gabarit de production.

```css
.app:not([data-grimpeur="1"]) .c-grimpeur,
.app[data-grimpeur="1"]:not([data-bloc="1"]) .c-bloc { … }
```

### La couleur du circuit : deux variables, jamais plus

Comme en production, deux variables suffisent, et elles sont posées par le JS
sur `.app` :

- `--circuit` : la teinte, prise dans une table **recopiée** de
  `static/juge/couleurs.js` ;
- `--encre-circuit` : de l'encre lisible dessus, calculée par la **même**
  formule de luminance que `encreSur()` — seuil 0,55.

La table est recopiée et non importée : un module ES ne se charge pas depuis
`file://`, et la maquette doit s'ouvrir d'un double-clic. La recopie est
signalée par un commentaire à l'endroit exact. Si les couleurs bougent en
production, la maquette ment — mais elle n'aura plus de raison d'exister.

Le circuit **« Noir »** n'a pas de valeur dans la table : il est rendu par une
table `NOIR` indexée **par direction**. C'est le seul point où les quatre
directions divergent sur une donnée et pas sur un style, et c'est voulu : la
question « quelle couleur pour le Noir ? » est une des décisions ouvertes.

### La bascule de la direction B

Elle tient en un seul sélecteur, et c'est ce qui la rend défendable :

```css
.app[data-d="B"][data-bloc="1"] {
  --fond: var(--circuit);
  --encre: var(--encre-circuit);
  --surface: color-mix(in srgb, var(--encre-circuit) 11%, transparent);
  --trait:   color-mix(in srgb, var(--encre-circuit) 22%, transparent);
  …
}
```

Toutes les surfaces sont exprimées en **part d'encre**. Il n'y a donc aucune
règle par couleur : le même bloc marche pour le jaune (encre sombre) et pour le
bleu (encre claire). C'est aussi ce qui rend l'implémentation crédible — une
douzaine de lignes, pas six palettes à maintenir.

### Les modes d'affichage

| Mode | Comment | À quoi il sert |
| --- | --- | --- |
| Planche | par défaut | Comparer, cliquer, décider sur le Mac |
| Plein écran | `body.nu`, bouton ou `?nu=1` | Essayer au doigt sur le vrai téléphone ; les marges d'encoche repassent en `env(safe-area-inset-*)` |
| Capture | `?cap=1` | Le châssis seul, centré, à l'échelle 1 : c'est ce qui produit les images de 390 × 844 exactement |

### L'adresse

Chaque état s'écrit dans la requête — `?d=B&e=principal&s=hors&c=mauve&f=1&r=ko` —
et se relit au chargement. Deux bénéfices : un écran précis se renvoie par
message, et les captures se prennent sans piloter de clic.

`history.replaceState` est enveloppé dans un `try` : certains navigateurs le
refusent sur `file://`, et un écran de maquette ne doit pas mourir pour ça.

### Les ressources

Deux, toutes deux **dans le dépôt**, référencées en relatif depuis le dossier
des maquettes :

| Ressource | Chemin | Si elle manque |
| --- | --- | --- |
| Le logo du club | `../../../climbcontest/static/juge/logo-club.png` | Le texte de remplacement s'affiche |
| La police Archivo | `../../../climbcontest/static/juge/archivo.ttf` | Repli sur `system-ui` |

Le QR du viseur est un **dessin SVG en ligne**, pas un code valide. Un vrai code
scannable dans une maquette finirait par être visé pour de bon.

## 2. L'implémentation future : ce qui bougerait, et ce qui ne bougerait pas

Rien de ceci n'est fait dans cette PR. C'est la carte du terrain, pour que la
décision de la § 7 de la spec se prenne en connaissant son coût.

| Fichier | Ce qui bougerait |
| --- | --- |
| `climbcontest/templates/juge.html` | **Le bloc `<style>` en entier**, et la structure des cartes si la direction D est retenue (les valeurs passent dans un conteneur `.textes`) |
| `climbcontest/static/juge/couleurs.js` | Rien — **sauf** si D4 conclut que le « Noir » cesse d'être de la craie |
| `climbcontest/static/juge/juge.js` | Rien, ou presque : il pose déjà `--circuit` et `--encre-circuit`, et lit l'état par classes. Une direction qui exige un attribut `data-*` supplémentaire coûterait une ligne dans `redessiner()` |
| `climbcontest/static/juge/sw.js` | Le numéro de version de la coquille, pour que les téléphones reprennent le nouveau CSS |
| `<meta name="theme-color">` | Suit le fond de la direction retenue — sinon la barre d'état iOS reste `#0B0D11` sur un écran clair |
| `climbcontest-android/` | **Hors périmètre tant que D5 n'est pas tranchée** |

Deux points d'attention repérés en maquettant, qui coûteront une ligne chacun
mais qu'on ne verrait qu'à l'écran :

1. **`theme-color`.** Il vaut `#0B0D11` aujourd'hui, une valeur qui n'existe
   même plus dans le CSS depuis le réchauffement du 02/09. Sur une direction
   claire, il ferait une barre d'état noire au-dessus d'un écran sable.
2. **L'écran d'accueil hérite du fond par `background: inherit`.** Une direction
   qui change le fond doit vérifier que le logo tient encore dessus — le PNG a
   un dessin clair cerclé de noir, il passe sur les deux, mais ça se regarde.

## 3. Ce que la maquette ne prouve pas

- **L'éblouissement.** Une direction claire se juge dans la salle, un jour de
  compétition, pas sur un Mac.
- **La lisibilité au soleil.** Le contraste calculé n'est pas le contraste
  perçu à 100 000 lux.
- **La fatigue.** Deux cents validations dans la journée ne se simulent pas en
  dix clics.
- **Le rendu réel des couleurs.** Chaque téléphone de bénévole a son écran, et
  aucun n'est calibré.
