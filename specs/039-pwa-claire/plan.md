# Plan — spec 039, l'application juge s'ouvre en clair

## Ce qui a été fait, dans l'ordre

| # | Geste | Fichier |
| --- | --- | --- |
| 1 | Le `:root` clair, la requête media sombre, le bloc partagé | `climbcontest/templates/juge.html` |
| 2 | Les dix couleurs écrites en dur passées en rôles | `climbcontest/templates/juge.html` |
| 3 | `--circuit-texte` et `--trait-circuit` : la teinte du circuit **écrite** | `climbcontest/templates/juge.html` |
| 4 | Les deux `theme-color` avec leur `media`, la barre iOS en `default` | `climbcontest/templates/juge.html` |
| 5 | Le circuit « Noir » suit le thème | `climbcontest/static/juge/couleurs.js` |
| 6 | Redessin quand le téléphone bascule en cours de journée | `climbcontest/static/juge/juge.js` |
| 7 | Le manifeste porte le fond clair | `climbcontest/templates/manifest.webmanifest` |
| 8 | La coquille hors-ligne passe en `v6` | `climbcontest/static/juge/sw.js` |
| 9 | Les captures et la planche de comparaison | `specs/039-pwa-claire/maquettes/` |
| 10 | Les trois fichiers de tests | `tests/` |

## Les tests, et ce que chacun attrape

| Fichier | Ce qu'il protège | Ce qu'il ne peut pas voir |
| --- | --- | --- |
| `tests/test_pwa_claire.py` | Le clair est déclaré **avant** la requête media ; le sombre n'existe **que** dedans ; **aucun rôle n'est défini dans un seul des deux thèmes** ; le bloc partagé ne croise jamais le sombre ; plus une seule couleur en dur dans les règles, hors le noir du viseur ; les deux `theme-color`, le clair en tête ; le manifeste égal au `--fond` clair | Ce que la cascade calcule vraiment |
| `tests/test_navigateur_juge_claire.py` | Dans un **vrai navigateur**, le fond est clair sans que rien ne l'ait demandé, et **vingt-six textes** tiennent leur seuil de contraste contre leur fond **effectif** — voiles composés, `color-mix` résolus, variables en ligne posées | Le thème sombre : le harnais lance un chromium en ligne de commande, sans réglage système à offrir |
| `tests/js/couleurs.test.mjs` | « Noir » rend l'encre du thème dans les deux sens, les cinq autres circuits n'en dépendent pas, et hors navigateur la réponse est **clair** | — |

Trois pièges ont été payés en écrivant ces tests, et chacun a laissé son
commentaire dans le code :

1. **Les transitions.** `.carte` porte `transition: background .25s`. Mesurer
   juste après avoir posé une classe rend la couleur d'**avant** : le test
   passerait au vert en mesurant l'ancien thème. La sonde gèle les transitions
   et les animations avant toute mesure.
2. **`#effacer` est un sélecteur qui ressemble à une couleur.** Ses six
   premières lettres sont toutes des chiffres hexadécimaux. Le test des
   littéraux en dur l'accusait d'être une couleur oubliée.
3. **`--fond` est déclaré deux fois.** Un dictionnaire garde le **dernier** —
   celui du thème sombre — et la comparaison avec le manifeste échouait en
   accusant une dérive qui n'existait pas.

## Ce qui reste à la main d'Adrien

Aucun test ne remplace ces quatre-là.

1. **Sur un vrai iPhone, en plein jour.** C'est la demande d'origine, et le seul
   juge du résultat. Regarder aussi la **barre d'état** : c'est elle qui
   écrivait en blanc sur du papier.
2. **L'application installée**, pas seulement l'onglet : l'écran de démarrage
   vient du manifeste, et il ne peut pas suivre le réglage du téléphone.
3. **Un téléphone réglé en sombre** : vérifier qu'il retrouve exactement
   l'application du 02/09.
4. **Après déploiement, fermer et rouvrir l'application** sur un téléphone déjà
   installé. La coquille `v6` n'est prise qu'au lancement suivant — c'est le
   comportement voulu (spec 007), pas un défaut.

## Ce qui reste ouvert, et qui n'est pas dans cette PR

- **L'app juge Android** reste en `darkColorScheme`. Elle demande sa propre
  spec, sa release et son APK — ce qui ne se fait pas à la légère à deux mois
  d'une compétition. C'est la question **D5** de la spec 035.
- **La spec 035** reste ouverte sur la **structure** de l'écran : aucune des
  quatre directions n'est adoptée. Elle a perdu deux de ses questions — « clair
  ou sombre » et « le circuit Noir » — et garde les autres.
