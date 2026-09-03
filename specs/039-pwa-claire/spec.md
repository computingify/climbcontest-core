# Spec 039 — L'application juge s'ouvre en clair

## 1. Le fait générateur

Adrien, 3 septembre 2026, mot pour mot :

> « pour l'application PWA je voudrais que par défaut elle s'ouvre en claire »

Et, sur la question posée en retour — clair *toujours*, clair *avec une bascule*,
ou clair *sauf si le téléphone demande le sombre* :

> **« clair sauf téléphone en sombre »**, et **la PWA seule pour l'instant**
> (l'app juge Android reste sombre).

Puis, après l'aperçu : « oui très bien le thème claire et sombre, implémente ».

C'est **la moitié de la question laissée ouverte par la spec 035** — « la
direction, clair ou sombre, jusqu'où va la couleur, et ce qu'on fait du circuit
*Noir* ». Cette spec répond à *clair ou sombre* et à *le circuit Noir*. Elle ne
répond pas au reste : la structure de l'écran ne bouge pas, aucune des quatre
directions n'est adoptée. La 035 reste ouverte sur la mise en page.

## 2. Le défaut, tel qu'il était

Le fond de la PWA était sombre **en dur** : les couleurs étaient figées dans
`:root` et rien ne regardait `prefers-color-scheme`. Un bénévole qui ouvrait
l'application en plein jour, dans une salle à baie vitrée, lisait un écran noir
sans l'avoir demandé — avec la luminosité poussée à fond, c'est-à-dire au prix
de sa batterie, sur un téléphone qui doit tenir la journée.

C'est **exactement** le défaut que la spec 021 a corrigé sur `admin.html`, et
son constat s'appliquait déjà mot pour mot à la PWA. Il n'y avait pas de raison
de le laisser vivre plus longtemps d'un côté que de l'autre.

## 3. Ce que la spec livre

- Le **clair est le défaut** — pas un cas particulier. Le sombre est une
  redéfinition sous `@media (prefers-color-scheme: dark)`.
- **Aucun réglage dans l'application** : le système décide. Choix d'Adrien, et
  le même que sur la console. Un juge n'a pas à trouver un interrupteur de
  thème le matin d'une compétition.
- Le **thème sombre est inchangé**, au point près : les valeurs de la requête
  media sont celles du 02/09, lueur ocre comprise. Ce qui change, c'est
  *laquelle des deux* s'applique quand le téléphone ne demande rien.
- Le papier sable vient de la direction **« Plein Jour »** des maquettes de la
  spec 035 : `#F3EEE3`. Rien n'est inventé ici qui n'ait déjà été regardé dans
  un cadre de téléphone.

## 4. Ce que l'écran doit continuer à faire

Reprises de la spec 035, § 2. Une seule a demandé un vrai travail — la première.

| # | Contrainte | Ce que le clair en fait |
| --- | --- | --- |
| C1 | **La couleur porte de l'information** : la teinte du circuit prend l'écran dès que le bloc est scanné | L'**aplat** garde la couleur exacte du circuit, au point près, dans les deux thèmes. Seule la teinte **écrite** est tirée vers l'encre en clair : un jaune pur sur du papier mesure 1,9:1 |
| C2 | **Aucune dépendance extérieure** | Inchangé : deux jeux de variables dans le même `<style>` en ligne |
| C3 | **Tenu à une main, toute la journée** | Aucune géométrie ne change |
| C4 | **Lisible dans une salle, et dehors** | C'est le but même de la spec. Les mesures sont dans l'architecture |
| C5 | **« Effacer » ne pèse jamais autant qu'« Envoyer »** | Inchangé |
| C6 | **Le voyant reste barré** quand le serveur est injoignable | Inchangé : la forme dit la panne, la couleur la confirme |
| C7 | **On n'empêche jamais l'envoi** | Inchangé. L'aplat jaune de « Envoyer quand même » est le **même** dans les deux thèmes |
| C8 | **L'identité est celle du club** | Le papier sable et la lueur ocre viennent du logo, comme la console |

## 5. Le circuit « Noir » — la question tranchée

Il était rendu en **craie** (`#E8EBF0`), et ce n'était pas un choix de couleur :
un aplat noir sur un fond presque noir ne se voit pas, et le juge ne saurait pas
s'il a scanné. Mais la craie était une **rustine du fond sombre** — sur du
papier sable, elle ne se voit pas davantage.

« Noir » prend donc **l'encre du thème** : `#22201B` sur le papier, `#E8EBF0`
sur l'ardoise. Dans les deux cas c'est la couleur la plus contrastée de l'écran,
ce que « Noir » veut dire dans une salle. C'est le **seul** circuit dont le
rendu dépend du fond ; les cinq autres sont identiques au pixel, et le restent.

## 6. Ce qui n'est pas dans le périmètre

- **L'app juge Android** reste en `darkColorScheme`. Les deux clients ne se
  ressembleront plus tant qu'elle n'a pas suivi. C'est assumé, écrit dans le
  code là où la parité était promise, et ce sera une autre spec — avec sa
  release Android, qu'on ne publie pas à la légère à deux mois d'une
  compétition.
- **La structure de l'écran** : aucune des quatre directions de la spec 035
  n'est adoptée. Cartes, tailles, gestes, ordre : rien ne bouge.
- **Un réglage de thème dans l'application** : explicitement écarté.

## 7. Ce qui se vérifie, et où

| Quoi | Comment |
| --- | --- |
| L'application s'ouvre en clair quand le téléphone ne demande rien | `tests/test_navigateur_juge_claire.py` — un vrai navigateur, cascade appliquée, luminance mesurée |
| Le sombre existe toujours et redéfinit **tous** les rôles | `tests/test_pwa_claire.py` — aucune couleur ne peut n'être définie que dans un seul des deux blocs |
| Le circuit « Noir » suit le thème, les cinq autres non | `tests/js/couleurs.test.mjs` |
| L'écran de démarrage de l'application installée ne dérive pas du fond clair | `tests/test_pwa_claire.py` — le manifeste et `--fond` sont comparés |
| Ce que ça donne vraiment | `specs/039-pwa-claire/maquettes/index.html` — l'application réelle, seize captures, les deux thèmes côte à côte |
| Sur un vrai iPhone, en plein soleil, barre d'état comprise | **Adrien.** Aucun test ne remplace ça |
