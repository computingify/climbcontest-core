# Spec 042 — architecture

## 1. Un seul nœud pour le geste, pas deux

Le bouton **ne se dédouble pas**. `#btnScannerPoste` reste le seul nœud qui
porte le geste ; ce qui change, c'est son habit.

```html
<button class="action pleine" id="btnScannerPoste" type="button">Scanner le QR de mon poste</button>
<p class="explication" id="expliquerScanPoste">Le carton posé sur ta table…</p>
```

| Le téléphone | `#btnScannerPoste` | `#expliquerScanPoste` |
| --- | --- | --- |
| n'a pas de nom | `class="action pleine"` — aplat bleu, pleine largeur | visible |
| porte un nom | `class="lien"` — texte bleu, aligné à gauche | `hidden` |

Deux nœuds — un bouton et un lien, l'un caché, l'autre montré — auraient
demandé **deux** gestionnaires de clic, **deux** libellés à garder identiques,
et auraient cassé les tests existants qui cherchent `id="btnScannerPoste"` dans
l'écran des Réglages (`tests/test_postes.py::TestLaCoutureAvecLApplicationJuge`).
Un seul nœud n'a aucune de ces façons de se contredire.

⚠️ L'ancien `style="width:100%;margin-top:12px"` **en ligne** disparaît au
profit de `.action.pleine`. En ligne, il aurait survécu au changement de classe
et donné un lien de 100 % de large avec 12 px de marge.

## 2. Une seule fonction décide, comme pour l'écran d'accueil

`proposerDeNommerLePoste()` existe déjà et porte exactement cette
responsabilité : *le téléphone a-t-il un nom, et que montre-t-on en
conséquence ?* Elle gagne la seconde surface, et **ne change pas de nom** — un
test de `test_postes.py` vérifie qu'elle est bien rappelée après un scan
réussi, et le renommer ferait passer ce test au vert pour de mauvaises raisons.

```js
function proposerDeNommerLePoste() {
  const nomme = Boolean(identite && identite.nom);
  $("poste").hidden = nomme;                       // l'écran d'accueil
  $("btnScannerPoste").className = nomme ? "lien" : "action pleine";
  $("expliquerScanPoste").hidden = nomme;          // les Réglages
}
```

Les trois appels existants suffisent, et c'est le point : ce sont exactement
les trois moments où le nom peut changer.

| Appel | Quand |
| --- | --- |
| `ouvrirLesReglages()` | on ouvre l'écran — l'état de départ |
| l'écouteur `input` de `#nomTelephone` | à chaque frappe, y compris l'effacement |
| `scannerMonPoste()` | après un scan de poste réussi |

`ouvrirLesReglages()` ne l'appelait pas encore : c'est le seul ajout d'appel.
Sans lui, un téléphone nommé au démarrage ouvrirait ses Réglages avec la
demande encore allumée.

## 3. L'interrupteur

```html
<label class="bascule">
  <span class="quoi">Garder le grimpeur entre deux blocs</span>
  <input type="checkbox" id="garderGrimpeur" role="switch">
  <span class="glissiere" aria-hidden="true"></span>
</label>
```

L'ordre des trois enfants **est** le mécanisme : `input:checked + .glissiere`
est un sélecteur de frère adjacent. Un `<span>` glissé entre les deux éteindrait
la glissière sans qu'aucune ligne n'ait l'air fausse.

La glissière est un **frère**, jamais un `::after` posé sur l'`<input>` : un
pseudo-élément sur un élément remplacé tient de la tolérance des navigateurs, et
cette application tourne sur les téléphones que les bénévoles apportent.

`#garderGrimpeur` garde son `id`, son type, sa clé de rangement et son écouteur
`change` : côté JavaScript, **rien ne change**.

### Le piège de cascade, et pourquoi il ne se referme pas tout seul

`.bloc label { display: block; font-size: 0.8rem; color: var(--encre2) }`
s'applique à ce `<label>`. Même spécificité que `label.bascule` (0,1,1) : c'est
l'**ordre dans le fichier** qui tranche, et rien dans le CSS ne dit qu'il
compte. Le même genre de piège que `#ligneRefus` (voir l'en-tête de
`tests/test_navigateur_juge_reglages.py`), où `.ligne { display: flex }`
battait le `[hidden]` du navigateur et affichait un bouton mort.

La réponse du dépôt à cette classe de défaut est déjà écrite : **mesurer le
style calculé dans un navigateur**, pas relire le gabarit. C'est ce que fait le
test dédié (`plan.md`, T6) — il refuse `display: block` sur la bascule, une
police de 0,8 rem, et une glissière de largeur nulle.

## 4. Ce qui se croise avec les autres branches

Écrit quand les specs **040** (le thème au choix) et **030** (les versions
visibles) attendaient encore en PR. **Trois specs ont été mergées pendant
l'écriture de ce lot** — la 040, la 030, puis la 041 (la matière imprimée) —
et la fusion à blanc prévue est devenue deux rebases successifs. Voici ce
qu'ils ont donné.

| Fichier | Qui d'autre y touche | Ce qui s'est passé |
| --- | --- | --- |
| `climbcontest/templates/juge.html` | la 040 ajoute « Thème », la 030 ajoute « Catalogue » et « Application », la 041 retouche la matière (liseré, ombre) | **Fusionné sans conflit** — quatre specs dans le même écran, aucun recouvrement. C'est exactement le cas où git ne dit rien : l'écran déroulé est capturé dans `maquettes/`, section 4 |
| `climbcontest/static/juge/sw.js` | la 040 l'a passé en `v7`, la 030 en `v8`, la 041 en `v9` | **Conflit sur les commentaires — et pas sur la constante.** Au second rebase, les deux côtés avaient écrit `v9` : git a cru qu'ils étaient d'accord et a laissé `const CACHE = "…-v9"` **hors du conflit**, avec deux raisons différentes au-dessus. C'est exactement le piège que la 030 avait documenté ; le test l'attrape désormais. Résolu en **`v10`** |
| `docs/specs-index.md` | toutes les PR (spec 038) | **Conflit** sur une ligne de tableau. Résolu en reprenant l'index de `master` et en y posant la ligne 042 |
| `CHANGELOG.md` | toutes les PR (spec 038) | Fusionné sans conflit — les entrées se sont rangées sous leurs propres titres |

⚠️ **Le numéro de cache est le seul endroit où la fusion pouvait se tromper
sans bruit** — la liste `COQUILLE` fusionne ligne à ligne, le NOM du cache est
une seule ligne. Le commentaire de la spec 030 le dit déjà ; la 042 y ajoute un
test : le dernier commentaire `// vN le …` doit porter le numéro de la
constante, sans quoi l'un des deux a été oublié.

## 5. Fichiers touchés

| Fichier | Ce qui bouge |
| --- | --- |
| `climbcontest/templates/juge.html` | CSS `label.bascule`/`.glissiere` et `.action.pleine` ; la ligne « Garder le grimpeur » devient un `<label class="bascule">` ; le style en ligne du bouton de scan part dans une classe ; le `<p>` d'explication reçoit un `id` |
| `climbcontest/static/juge/juge.js` | `proposerDeNommerLePoste()` gagne les deux nœuds des Réglages ; `ouvrirLesReglages()` l'appelle |
| `climbcontest/static/juge/sw.js` | `CACHE` passe en `v10`, avec la raison écrite à la suite des précédentes |
| `tests/test_pwa_juge.py` | les assertions de gabarit (T1, T5, T7) |
| `tests/test_navigateur_juge_reglages.py` | les sondes de style calculé (T2, T3, T4, T6) |
| `specs/042-reglages-au-pouce/` | spec, architecture, plan, maquettes |
| `docs/specs-index.md`, `CHANGELOG.md` | une ligne chacun |
