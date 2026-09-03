# Architecture — spec 033

Douze corrections, cinq surfaces. Une seule ajoute un contrat d'API ; une seule
change une forme de données stockée. Les dix autres sont du gabarit, du style et
du JavaScript de page.

## 1. Le seul nouveau contrat d'API — R3

```
GET /api/public/reglages          (aucune authentification, comme ses voisines)
```

```json
{
  "competition": {
    "id": 3,
    "nom": "Contest de novembre",
    "statut": "en_cours",
    "groupes_masques": ["U11", "Scratch H"]
  }
}
```

409 avec `{"success": false, "message": "..."}` quand aucune compétition n'est
active — **exactement** la forme des autres routes de `public.py`, pour que la
page n'ait pas à connaître deux façons d'échouer.

### Pourquoi une route de plus plutôt qu'un rythme plus rapide

`GET /api/public/classement` porte tous les classements et toutes les lignes :
plusieurs dizaines de kilo-octets, relus par une soixantaine de téléphones. Le
**calcul** est déjà plafonné — `classements()` garde son résultat en cache et
Caddy met la réponse en cache 5 s —, mais la **bande passante** ne l'est pas.
Passer `PERIODE_MS` de 15 s à 3 s multiplierait par cinq le trafic du wifi de la
salle pour un réglage que seul l'organisateur touche.

Cette route-ci ne fait **aucun calcul de classement** : une lecture de la ligne
`Competition` et un `json.loads` de sa colonne `options`. La réponse tient dans
deux cents octets. Elle est donc relisible souvent.

| | `/classement` | `/reglages` |
| --- | --- | --- |
| Contenu | tous les classements, toutes les lignes | nom, statut, classements masqués |
| Taille | dizaines de ko | ~200 o |
| Coût serveur | classement (en cache 5 s) | une ligne de base |
| Rythme de la page | 15 s | **3 s** |

⚠️ **Elle ne remplace rien.** `groupes_masques` reste dans la charge de
`/classement` : c'est cette charge que `cycle.archiver` fige, et une archive
amputée serait irréparable. La page prend le réglage des deux endroits, le plus
frais gagne — et comme les deux viennent de la même source, ils ne peuvent pas
se contredire durablement.

### Ce que fait la page quand le réglage change

`appliquerReglages(competition)` est appelée par les **deux** chemins — la
charge complète et la route légère — et fait une seule chose :

1. range `groupes_masques` dans `etat.groupesMasques` et le nom dans
   `etat.competition.nom` ;
2. si rien n'a changé, **s'arrête là** : pas de redessin, donc pas d'animation
   parasite trois fois par seconde ;
3. si le classement affiché vient de disparaître, choisit le premier visible ;
4. redessine.

Le cas « tout est masqué » reste traité par `groupesVisibles()`, qui ignore le
réglage plutôt que de rendre une page vide. Il n'est pas dupliqué ici.

**Rejeu d'archive** : `ARCHIVE` non nul → aucune interrogation des réglages. Une
archive fige ce qu'elle fige.

**Testabilité** : le gabarit gagne `data-reglages`, à côté de `data-source`, et
la page lit `document.body.dataset.reglages || "/api/public/reglages"`. Le
harnais de test peut donc pointer une source qui change entre deux appels, comme
il le fait déjà pour la charge.

## 2. La seule forme de données qui change — R10

`static/juge/catalogue.js`, `FORMAT` **3 → 4**.

```js
// forme 3
participants : { "42": { n: "Dupont Lea", c: "U13" } }      // c = CIRCUIT
// forme 4
participants : { "42": { n: "Dupont Lea", c: "U13 F" } }    // c = CATEGORIE
```

Une clé, pas deux : le **circuit se déduit** de la catégorie par `circuitDe()`,
la règle qui existe déjà et qui est la même que `Participant.circuit` côté
serveur. La quantité de données stockées ne croît donc pas.

⚠️ **Ce qui change, c'est ce qu'elles contiennent.** Le commentaire de
`catalogue.js` justifiait la forme 3 par la minimisation : des données de
mineurs vivent sur vingt-cinq téléphones de bénévoles, et le genre n'apprenait
rien au test d'appartenance au circuit. Il apprend maintenant quelque chose : la
catégorie est ce qu'Adrien demande d'**afficher** au juge, pour qu'il vérifie
d'un coup d'œil qu'il scanne le bon grimpeur. Le commentaire est **réécrit**, pas
supprimé : il dira la nouvelle raison et la date, sinon quelqu'un rétablira la
forme 3 en croyant corriger une régression.

La catégorie complète **voyageait déjà** : `/api/v2/catalog` sert
`participant.to_dict()` en entier. Aucune route ne change.

Le **marqueur de format** fait le reste : un téléphone qui a la forme 3 la
trouve périmée au démarrage et retélécharge tout. C'est le mécanisme prévu, et
c'est précisément le cas pour lequel il a été ajouté.

## 3. Ce que chaque point touche

| # | Fichiers |
| --- | --- |
| R1 | `templates/admin.html` — un `<div id="blocPorteeCascade">` autour du titre, des raccourcis et de la grille ; `majPresetsCascade()` pose le même `hidden` sur les deux groupes |
| R2 | `templates/admin.html` — `fieldset.choix input[type=radio]` en `appearance: none`, pastille à `--accent`, fond de carte teinté sur `:has(input:checked)` |
| R3 | `routes/public.py` (route), `suivi.py` **non touché**, `templates/resultats.html` (poll + `appliquerReglages`), `templates/admin.html` (le message de confirmation cesse de promettre « au prochain rafraîchissement ») |
| R4 | `templates/resultats.html` — `lireAffichage()` / `ecrireAffichage()` remplacent la lecture/écriture ponctuelle de `CLE_AFFICHAGE` |
| R5 | `templates/resultats.html` — deux `<svg>` dans le bouton, `majBoutonPause()` bascule un `hidden` au lieu d'écrire du texte |
| R6 | `templates/resultats.html` — le défaut de `sansRecherche` passe à `true` |
| R7 | `fiches.py` — `TAILLE_NUMERO_MM` remplace `taille_numero_mm()` ; `templates/etiquettes.html` — plus de `--taille` par étiquette |
| R8 | `fiches.py::etiquettes` — `order_by` par zone |
| R9 | `templates/juge.html` — l'engrenage devient un SVG, et passe après le voyant |
| R10 | `static/juge/catalogue.js` (forme 4 + `categorie()`), `static/juge/juge.js` (rendu), `templates/juge.html` (mise en page de la carte) |
| R11 | `templates/resultats.html` — la légende liste les profils du plan courant |
| R12 | `templates/admin.html` — une carte, une requête sur une route qui existe déjà |

Aucune migration de base. Aucun modèle touché. Aucune écriture Google.

## 4. Les décisions qui ne se déduisent pas du code

### R7 — pourquoi une constante et pas « la plus grande taille qui tient partout »

Deux façons de rendre la taille « fixe » :

1. **une constante** — toute étiquette, toute planche, la même taille ;
2. **uniforme par planche** — on calcule la taille du numéro le plus long de la
   planche et on l'applique à tous.

La seconde donne des numéros plus gros quand la planche n'a que des numéros
courts. Elle a un défaut qui la disqualifie : imprimer *toute la salle* puis
*seulement la zone A* donnerait **deux tailles différentes** pour les mêmes
étiquettes, parce que le filtre change le plus long numéro de la planche. On
recollerait au mur des étiquettes qui ne se ressemblent pas.

C'est donc **19 mm**, constante, calculée pour que trois caractères tiennent
dans les 42 mm de colonne : `42 / (3 × 0,72) = 19,4`, arrondi au demi-millimètre
inférieur. Trois caractères, parce qu'un numéro d'étiquette est la couleur
suivie du numéro dans la couleur (`J6`, `J24`, `M40`) : deux ou trois. Un
quatrième caractère ne déborde pas sur le QR — `overflow: hidden` et
`white-space: nowrap` étaient déjà là — il est coupé, ce qui se voit et se
corrige, au lieu de manger le code à scanner.

`taille_numero_mm()` **disparaît** avec son test : garder une fonction sans
appelant, c'est exactement ce que la spec 024 s'était reproché avec `par_zone()`.

### R8 — pourquoi le tri est en SQL et pas en Python

`Bloc.zone` est une colonne ; trier en base évite de charger puis de retrier, et
surtout garde le tri **au même endroit que le filtre**. Le tri est
`(zone IS NULL, zone, numero)` :

- `zone IS NULL` d'abord, parce que SQLite range les `NULL` **avant** tout le
  reste : sans ce premier critère, une planche s'ouvrirait sur les blocs qui
  n'ont pas de mur ;
- puis la zone, alphabétiquement ;
- puis `Bloc.numero`, qui est l'ordre du classeur à l'intérieur de la zone —
  celui qui existe déjà, et qu'on ne change pas.

Le tri est sur la **valeur** de la zone, sans supposer qu'elle tient sur une
lettre : depuis la spec 029 le nom de zone est saisi dans la console.

### R11 — la légende ne montre que ce que le plan utilise

Les profils affichés sont ceux que porte le **plan courant**, pas les six de
`fiches.PROFILS`. Le plan est de la donnée saisie (spec 029) : une salle qui n'a
que des verticaux n'a pas à lire cinq pastilles qui ne désignent rien.

L'ordre reste celui de `PROFILS` — du moins au plus déversant. C'est écrit dans
`fiches.py` : « l'ordre EST l'information ». Une légende triée autrement (par
fréquence, alphabétiquement) détruirait la seule règle que le lecteur a à
apprendre.

Les libellés vivent **dans la page**, à côté des couleurs qu'ils nomment : la
page connaît déjà les six teintes en CSS (`--pf-*`), et le plan qu'elle reçoit
porte les clés (`dalle`, `vertical`, …). Faire voyager les libellés depuis le
serveur ajouterait un contrat pour six mots qui ne changent pas.

### R12 — pourquoi aucune route nouvelle

`GET /admin/reussites-tracees?appareil=<id>&limite=<n>` existe depuis la spec
011, gère déjà le cas « aucune référence » — les N dernières, les plus récentes
d'abord — et rend tout ce qu'il faut : grimpeur, dossard, bloc, horodatage,
téléphone, référence, `hors_circuit`. Elle n'avait **aucun appelant** pour ce
cas. Le lot ajoute l'écran, pas le serveur.

Le rafraîchissement est **piloté par la vue** : le minuteur ne tourne que
lorsque la vue « Réussites » est affichée, et il est coupé en la quittant. Une
console laissée ouverte sur « Réglages » toute la journée ne doit pas interroger
la base toutes les dix secondes pour un tableau que personne ne regarde.

## 5. Ce qui pourrait casser le jour J

| Ce qui peut arriver | Conséquence | Ce qui l'amortit |
| --- | --- | --- |
| `/api/public/reglages` tombe | Les réglages arrivent encore, à 15 s, par la charge complète | Les deux chemins portent la même information |
| Le poll de 3 s charge le serveur | Une lecture de ligne par appel, réponse mise en cache par Caddy | Aucun calcul de classement |
| Un téléphone garde la forme 3 du catalogue | Il retélécharge au démarrage | `FORMAT`, prévu pour ça |
| Le plan devient illisible | Aucun mur dessiné, donc aucune légende | Le garde de `peutDessiner()` est déjà là |
| Une planche a des numéros à 4 caractères | Le numéro est coupé, le QR reste entier | `overflow: hidden`, `nowrap` |
