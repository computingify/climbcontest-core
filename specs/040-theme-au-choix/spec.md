# Spec 040 — le thème au choix, dans les Réglages

## 1. Le fait générateur

Adrien, 3 septembre 2026, quelques heures après le merge de la spec 039 :

> « je voudrais un bouton dans les paramètres de l'application PWA pour changer
> le mode sombre vers claire et inversement »

Puis, sur la planche de comparaison des trois formes possibles :
**« B — trois pastilles »**, c'est-à-dire *Système / Clair / Sombre*.

## 2. Ce que cette spec change à la 039, et il faut le dire

La spec 039 écrit, section 6 :

> **Un réglage de thème dans l'application** : explicitement écarté.

Cette spec **revient sur cette décision**. Ce n'est pas une contradiction qu'on
laisse cohabiter : c'est un changement d'avis, daté du même jour, et la
justification de la 039 tenait en une phrase — « un juge n'a pas à trouver un
interrupteur de thème le matin d'une compétition ». Elle reste vraie, et c'est
exactement ce que la forme retenue préserve : le réglage **existe** mais ne se
présente à personne. L'application s'ouvre toujours sur « Système », donc sur le
comportement de la 039, à l'octet près.

Ce que la 039 ne pouvait pas donner, en revanche, et qui est la raison d'être de
celle-ci : **le juge dont le téléphone dit le contraire de ce que la salle
demande**. Un bénévole avec un iPhone en sombre automatique, sous les baies
vitrées à quatorze heures ; un autre en clair permanent, dans un coin de salle
mal éclairé le soir. La 039 leur répond « change le réglage de ton téléphone »,
ce qui est une réponse pour quelqu'un qui sait où il est.

## 3. Ce que la spec livre

- **Trois positions** dans les Réglages : *Système*, *Clair*, *Sombre*.
- **« Système » est la position de départ**, et elle reste **atteignable**.
  C'est ce qui a fait écarter l'interrupteur à deux positions : une fois
  touché, il ne sait plus rendre la main au téléphone.
- Le choix **survit au relancement**, et il est appliqué **avant la première
  peinture** — pas de clignotement clair→sombre à chaque ouverture.
- La **barre du navigateur** suit le thème imposé.
- Le circuit **« Noir » suit le thème réellement peint**, pas celui du
  téléphone (voir § 5).

## 4. La forme, et pourquoi celle-là

Trois variantes ont été capturées dans l'application réelle, en clair et en
sombre, avant d'écrire une ligne de code définitif —
[`maquettes/index.html`](maquettes/index.html).

| | Ce que c'est | Pourquoi pas |
| --- | --- | --- |
| **A** | Un interrupteur « Thème sombre », la même case que « Garder le grimpeur » | Deux positions : plus de retour au réglage du téléphone |
| **B** | **Trois pastilles : Système / Clair / Sombre** | **Retenue** |
| **C** | Deux pastilles ☀ Clair / ☾ Sombre | Même défaut que A, en plus visible |

La pastille n'est pas un dessin neuf : c'est **exactement** celle du filtre
« Pas arrivés » de l'écran « Mes scans ». Un choix parmi peu, tous visibles,
aucun menu à ouvrir.

Le réglage est dans l'écran **Réglages**, sous « Saisie » — pas dans l'en-tête.
Ce n'est pas un geste de compétition : on le pose une fois, le matin.

## 5. Le piège que cette spec a trouvé, et fermé

Le circuit **« Noir »** prend l'encre du thème depuis la 039 : presque noir
(`#22201B`) sur le papier, craie (`#E8EBF0`) sur l'ardoise. Le module lisait le
thème avec `matchMedia("(prefers-color-scheme: dark)")` — c'est-à-dire **le
téléphone**.

Dans le cas exact que cette spec sert — un juge qui force le sombre sur un
téléphone en clair — l'aplat du circuit « Noir » serait sorti en `#22201B` sur
un fond `#15161B`. **Invisible.** Le juge n'aurait pas su s'il avait scanné,
c'est-à-dire l'inverse de ce à quoi la couleur du circuit sert.

`enSombre()` lit désormais l'attribut posé par le réglage, et ne retombe sur
`matchMedia` que si personne n'a rien imposé. Le test qui le prouve nomme le
scénario, pas la fonction.

## 6. Ce que ça ne fait pas

- **La barre d'état d'un iPhone installé sur l'écran d'accueil** ne suit pas le
  réglage : elle est gouvernée par `apple-mobile-web-app-status-bar-style`,
  figé au lancement, qui vaut `default` et suit donc le **système**. Un juge qui
  force le sombre sur un iPhone en clair aura une barre d'état claire au-dessus
  d'une application sombre. Aucune API ne permet d'y toucher depuis la page ;
  c'est assumé et écrit ici pour ne pas être redécouvert.
- **L'écran de démarrage de l'application installée** vient du manifeste, qui
  n'a pas de requête media et porte le fond **clair**. Il ne peut pas suivre le
  réglage — même limite qu'en 039, inchangée.
- **L'app juge Android** reste en `darkColorScheme`, sans réglage. La parité
  était déjà rompue par la 039 ; elle ne l'est pas davantage.
- **La console** (`admin.html`) garde le motif de la spec 021 : le système
  décide, sans réglage. Personne ne l'a demandé, et la console se regarde sur
  un ordinateur, pas dans une salle.
- **Le partage entre téléphones.** Le choix est local au navigateur : il ne suit
  ni le juge ni son jeton. C'est voulu — c'est un réglage d'écran, pas de
  compte.

## 7. Ce qui se vérifie, et où

| Quoi | Comment |
| --- | --- |
| Les deux écritures du thème sombre ne peuvent pas diverger | `tests/test_theme_au_choix.py` — comparées propriété par propriété |
| Le thème est posé **avant la première peinture**, en ligne, avant tout module | `tests/test_theme_au_choix.py` |
| La clé de rangement est la même dans le gabarit et dans `theme.js` | `tests/test_theme_au_choix.py` |
| Le juge impose le sombre à un navigateur qui demande le clair | `tests/test_navigateur_theme_au_choix.py` — un vrai navigateur, cascade appliquée |
| Le choix **survit au relancement**, pastille comprise | `tests/test_navigateur_theme_au_choix.py` |
| « Système » efface la clé et rend la main | `tests/test_navigateur_theme_au_choix.py`, `tests/js/theme.test.mjs` |
| Un rangement refusé (navigation privée) ne casse pas le démarrage | `tests/js/theme.test.mjs` |
| Le circuit « Noir » suit le thème **imposé** | `tests/js/couleurs.test.mjs` |
| Le défaut de la 039 est intact tant qu'on ne touche à rien | `tests/test_pwa_claire.py`, `tests/test_navigateur_theme_au_choix.py` |
| Ce que ça donne vraiment | `specs/040-theme-au-choix/maquettes/index.html` — huit captures, trois variantes, les deux thèmes |
| Sur un vrai iPhone, barre d'état comprise | **Adrien.** Aucun test ne remplace ça |
