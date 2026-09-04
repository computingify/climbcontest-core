# Plan — spec 040, le thème au choix

## Ce qui a été fait, dans l'ordre

| # | Geste | Fichier |
| --- | --- | --- |
| 1 | La requête media passe sous `:root:not([data-theme="clair"])` | `climbcontest/templates/juge.html` |
| 2 | Le sombre **imposé** : `:root[data-theme="sombre"]`, copie exacte | `climbcontest/templates/juge.html` |
| 3 | Le script **en ligne** du `<head>` qui pose le thème avant la peinture | `climbcontest/templates/juge.html` |
| 4 | Les trois pastilles dans l'écran Réglages, et leur style | `climbcontest/templates/juge.html` |
| 5 | Le module qui lit, range et applique | `climbcontest/static/juge/theme.js` |
| 6 | Le branchement des pastilles, et le redessin de la teinte | `climbcontest/static/juge/juge.js` |
| 7 | `enSombre()` lit le thème **imposé** avant celui du téléphone | `climbcontest/static/juge/couleurs.js` |
| 8 | La coquille hors-ligne passe en `v7` et emporte `theme.js` | `climbcontest/static/juge/sw.js` |
| 9 | Les captures et la planche des trois variantes | `specs/040-theme-au-choix/maquettes/` |
| 10 | Les quatre fichiers de tests | `tests/` |

## La décision technique qui portait tout le reste

**Comment un thème imposé cohabite avec `prefers-color-scheme`.** Trois routes,
et le choix n'est pas neutre.

| Route | Ce que ça donne | Verdict |
| --- | --- | --- |
| `light-dark()` sur chaque rôle, et on bascule `color-scheme` | Une seule écriture des deux valeurs | ❌ Safari < 17.5 rend la déclaration **invalide** : la couleur tombe à `unset`. Ce sont exactement les téléphones des bénévoles |
| Tout résoudre en JavaScript avant la peinture, une seule palette sous `[data-theme]` | Aucune duplication | ❌ Le défaut du **système** dépendrait alors d'un script. C'est un recul sur la 039, qui l'obtient sans JavaScript |
| **Deux écritures du sombre, et un test qui interdit qu'elles divergent** | Le défaut reste en CSS pur ; l'imposé s'ajoute | ✅ **Retenue** |

CSS ne sait pas partager un jeu de valeurs entre une requête media et un
sélecteur d'attribut : il n'y a pas de quatrième route. La duplication est donc
assumée, et rendue **détectable** plutôt que documentée —
`test_theme_au_choix.py` compare les deux blocs propriété par propriété, et
nomme celles qui diffèrent.

Le rangement est `localStorage` et **non** IndexedDB, contrairement aux autres
réglages : il doit être lu **avant la première peinture**, et IndexedDB est
asynchrone — il répondrait toujours trop tard, c'est-à-dire après un
clignotement. Même choix, pour la même raison, que le jeton.

## Les tests, et ce que chacun attrape

| Fichier | Ce qu'il protège | Ce qu'il ne peut pas voir |
| --- | --- | --- |
| `tests/test_theme_au_choix.py` | Les **deux sombres identiques** ; la requête media laisse la main au clair imposé ; le script est **en ligne, dans le `<head>`, avant tout module**, sans `src`, et protégé par un `try` ; la clé est la même des deux côtés ; les trois pastilles, une seule allumée ; la coquille emporte le module et a changé de nom | Ce que la cascade calcule vraiment |
| `tests/test_navigateur_theme_au_choix.py` | Dans un **vrai navigateur** : le départ est clair sans attribut, « Sombre » bat le navigateur qui demande le clair, le choix **survit au relancement** avec sa pastille et sa barre, « Système » rend la main et efface la clé | Le **clignotement** : après un rechargement, le module repose le thème de toute façon. C'est le test statique qui garde l'ordre |
| `tests/js/theme.test.mjs` | La lecture, l'écriture, l'effacement sur « Système », le rangement **refusé** (navigation privée), et la barre du navigateur qui **retrouve ses deux couleurs** après deux bascules | — |
| `tests/js/couleurs.test.mjs` | Le circuit « Noir » suit le thème **imposé**, dans les deux sens ; les cinq autres n'en dépendent pas | — |

Les tests ont été vérifiés **par mutation**, pas seulement écrits :

| Mutation | Ce qui tombe |
| --- | --- |
| Le sélecteur du sombre imposé change de nom | 2 tests navigateur, 3 statiques |
| La requête media reprend `:root` tout court | Le test du clair imposé |
| **Une seule couleur** retouchée dans la copie du sombre | Le test de divergence, qui nomme la propriété |
| Le script en ligne ne pose plus l'attribut | Le test d'ordre — **et pas** le test navigateur, ce qui est écrit noir sur blanc dans son en-tête |

## Ce qui reste à la main d'Adrien

1. **Sur un vrai iPhone**, forcer le sombre en plein jour : la barre d'état
   restera claire (§ 6 de la spec). C'est la limite à regarder pour décider si
   elle est tenable.
2. **L'application installée** sur l'écran d'accueil, pas seulement l'onglet.
3. **Après déploiement, fermer et rouvrir** sur un téléphone déjà installé : la
   coquille **`v8`** n'est prise qu'au lancement suivant (spec 007).

   ⚠️ Cette spec avait livré la coquille en `v7`. La [030](../030-versions-visibles/),
   fusionnée juste après, y ajoute `versions.js` et la fait passer en **`v8`** —
   c'est ce numéro-là qu'un téléphone doit prendre. Le détail de la bévue que
   cette fusion a failli produire est dans le commentaire de `sw.js` : la liste
   des fichiers fusionne ligne à ligne, le nom du cache est une seule ligne.

## Ce qui reste ouvert

- **La spec 035** garde ses questions de **structure** : cette spec ne touche
  ni aux cartes, ni aux tailles, ni à l'ordre de l'écran.
- **L'app juge Android** n'a toujours ni thème clair ni réglage.
