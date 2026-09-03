# Spec 033 — La revue du 03/09

> Spec écrite **avant** le code, cette fois. Les specs 027 et 032 portent toutes
> deux un encadré expliquant que le code était parti en premier ; c'était la
> deuxième fois de suite, et la correction était notée en tête du plan de la
> 032. Ce dossier est écrit d'abord, la branche part ensuite.
>
> Le numéro **033** a été pris après vérification des branches locales *et*
> distantes : 030 est à `feat/030-versions-visibles` (session parallèle, non
> poussée), 031 et 032 sont mergées. 034, 035 et 036 sont pris par les trois
> lots que la même revue envoie en PR séparées (voir §5).

## 1. D'où vient ce lot

Deuxième campagne de tests E2E manuels d'Adrien, le 03/09/2026, console et
application juge en main, page de résultats ouverte à côté. Douze remarques,
dictées d'affilée, sans ordre de priorité. Quatre d'entre elles partent dans
leurs propres specs parce qu'elles sont des **évolutions** et non des défauts —
elles sont listées au §5 et ne sont pas traitées ici.

La consigne de méthode est la même que le 02/09, et elle est reprise mot pour
mot : **« tu ajoutes/ajustes les tests pour ne plus avoir ces problèmes »**.
Chaque point de ce lot a donc son test, et le tableau du §4 de
[plan.md](plan.md) est le contrat.

⚠️ **Trois des douze points ne sont pas des bugs.** R3 (le réglage d'affichage
qui « n'arrive pas ») et R6 (la recherche visible) décrivent un comportement qui
marche exactement comme il a été écrit. Ce sont des demandes de **changement de
comportement**, et il faut les traiter comme telles — sinon on « corrige » un
code qui n'a rien de cassé et on perd la raison qui l'avait fait écrire ainsi.
Le §2 le dit à chaque fois.

## 2. Ce qu'on corrige

### Console — la cascade de couleurs

**R1 — « Aucune cascade » doit aussi cacher « Où elle s'applique ».**

> « Dans la console sur Général, donc cascade de couleurs, si on sélectionne
> aucune cascade, je ne veux même pas voir la partie où on sélectionne sur
> quelle catégorie ça s'applique, cette cascade. »

La spec 032 (R1) avait déjà enveloppé le titre, les phrases, le contrôle et
l'aperçu dans un seul `#blocRegleCascade` qui disparaît sans cascade. Le
regroupement s'était arrêté trop tôt : l'interrupteur **par catégorie** — les
quatre raccourcis et la grille des six catégories — restait affiché sous un
titre qui promet d'appliquer une règle qui n'existe pas. C'est le même défaut
que la 032 avait nommé, une carte plus bas.

Attendu : les deux groupes apparaissent et disparaissent **ensemble**, sur la
même condition, avec **un seul** endroit qui décide. Deux `hidden` pilotés par
la même ligne, pas deux conditions qui finiront par diverger.

**R2 — le bouton coché doit se voir.**

> « On voit qu'on a des petites pastilles pour sélectionner l'option aucune
> cascade, comme le classeur ou sur mesure. En revanche, lorsqu'elle est
> sélectionnée, le petit rond n'est pas visible une fois sélectionné. Il faut
> que ce soit plus clair pour l'utilisateur. »

Mesuré, capture à l'appui : les trois boutons sont des `<input type="radio">`
**natifs**, sans `accent-color`. En thème clair, le point coché est un petit
disque bleu système — visible, mais étranger à la palette ocre de la console.
En thème **sombre**, `color-scheme: light dark` rend un cercle pâle dont le
point coché a presque le même clair que les cercles vides : à cinquante
centimètres d'écran, les trois pastilles se ressemblent. Le seul autre indice
est la bordure ocre de la carte, discrète et facile à manquer.

Attendu : lequel des trois est choisi doit se lire **d'un coup d'œil, dans les
deux thèmes**, sans avoir à comparer trois pastilles entre elles.

### La page de résultats

**R3 — le réglage d'affichage doit arriver à la volée.**

> « Je suis en train de jouer avec la partie "ce qu'affichent la page de
> résultats". En parallèle, j'ai ma page de résultat qui est ouverte. J'active
> un interrupteur, par exemple scratch femme qui était désactivé, et je regarde
> si à côté mon scratch femme apparaît dans ma page résultat. Du coup, non, il
> n'apparaît pas. Je suis obligé de faire F5. […] Je veux aussi que si on active
> le scratch femme à la volée on rafraîchisse la page et on soit capable
> d'afficher la sélection qu'on vient d'enregistrer côté console. »

⚠️ **Ce n'est pas un bug.** La spec 032 a corrigé le vrai défaut — la barre
lisait la charge brute au lieu de `groupesVisibles()` — et il est tenu par
`test_navigateur_reglages_resultats.py`. Le réglage **arrive**, mais au rythme
de la relecture générale : `PERIODE_MS = 15000`. Quinze secondes, quand on vient
d'appuyer sur « Enregistrer » et qu'on regarde l'écran d'à côté, se lisent comme
« rien ne se passe » — et le message de la console, qui promet « au prochain
rafraîchissement », ne dit pas quand.

Ce qu'on **ne fait pas** : baisser `PERIODE_MS`. La charge de classement fait
plusieurs dizaines de kilo-octets et une soixantaine de téléphones la relisent ;
la passer à cinq secondes triplerait le trafic du wifi de la salle pour un
réglage que seul l'organisateur touche. Le calcul serveur, lui, ne bougerait pas
(Caddy met la réponse en cache 5 s), mais la bande passante, si.

Attendu : les réglages d'affichage — nom de l'édition, statut, classements
masqués — voyagent par une réponse **séparée et minuscule**, relue toutes les
**trois secondes**, et s'appliquent **immédiatement** : un classement rallumé
réapparaît dans la barre, un classement éteint disparaît, et s'il était celui
qu'on regardait, la page bascule sur un autre au lieu de rester sur une
catégorie qui n'existe plus.

**R4 — l'état lecture/pause doit survivre au rechargement.**

> « Le problème, c'est que quand je recharge la page résultat, le bouton play
> qui permet de faire avancer et afficher tous les podiums, le bouton play se
> désactive ou passe en pause. Moi, je veux qu'on reste en play si on est en
> play. »

Vrai défaut. `enPause: !MUR` est calculé **au chargement**, à partir de la seule
adresse : la page normale repart donc toujours à l'arrêt, quoi qu'on ait cliqué
avant. Sur l'ordinateur branché au vidéoprojecteur — celui qui n'est pas en mode
`?mur` — chaque rechargement arrête le défilement, et il faut retourner cliquer.

Attendu : le choix lecture/pause est **mémorisé sur l'appareil**, à côté du
choix « masquer la recherche » et pour la même raison (il ne regarde que cet
écran, il n'a rien à faire sur le réseau). Il repart de ce qu'on a laissé. Sans
rien de mémorisé, le défaut historique s'applique : en lecture sur `?mur`, à
l'arrêt ailleurs.

**R5 — les deux glyphes doivent être du même dessin.**

> « Le logo de pause n'est pas assorti au play, il faut qu'ils aient le même
> style. »

Le bouton porte `▶` (U+25B6, forme géométrique) en lecture et `⏸` (U+23F8,
caractère à présentation **emoji** par défaut) en pause. Deux familles de
glyphes différentes, deux graisses, et sur certaines plateformes une pastille
colorée pour le second : le bouton change d'allure quand il change d'état, et
l'œil lit un changement de composant, pas un changement d'état.

Attendu : deux icônes **dessinées**, du même trait, à la même taille optique,
qui prennent la couleur du bouton. Le glyphe cesse d'être du texte.

**R6 — la recherche est masquée par défaut.**

> « Par défaut sur la page résultat, je veux que la recherche soit cachée. »

⚠️ **Ce n'est pas un bug non plus.** La spec 020 a ajouté le bouton `⌕` pour
masquer le champ, et l'a laissé **affiché** par défaut : le champ est la seule
façon, pour un parent, de retrouver son enfant sans connaître sa catégorie. Le
défaut retenu servait ce parent, et le bouton servait le vidéoprojecteur.

Adrien inverse le défaut. Le prix est réel et il est écrit ici : sur le
téléphone d'un parent, la recherche n'est plus visible au premier coup d'œil et
s'ouvre par le bouton `⌕` de l'en-tête, à droite. Le bouton reste, la mémoire du
choix reste : celui qui l'ouvre une fois ne le rouvre plus.

Attendu : sans rien de mémorisé, la page démarre **sans** le champ. Le bouton
`⌕` le montre, et le choix est retenu pour cet appareil.

**R11 — la légende des profils revient sur le mur.**

> « Sur l'application, je vois que dans la partie plan, on a bien la légende
> avec marqué zone terminée. En revanche, on a perdu la légende des couleurs qui
> donnent l'inclinaison du mur et tout ce bazar-là. J'aimerais que tu me le
> remettes. »

Le plan à l'écran (spec 026) peint chaque pan selon son **profil** — dalle,
vertical, incliné, dévers, surplomb, toit — sur une échelle ordonnée qui passe
du froid au chaud au moment où le mur passe la verticale. Six couleurs qui
portent une information, et rien à l'écran ne dit laquelle. La légende ne
compte qu'une entrée, « zone terminée ».

Attendu : la légende dit **aussi** les profils, dans l'ordre du moins au plus
déversant — l'ordre EST l'information —, et ne montre que les profils que le
plan courant utilise réellement. Un plan qui n'a que des verticaux n'affiche pas
six pastilles dont cinq ne servent à rien.

### Les impressions

**R7 — la taille du numéro d'une étiquette de bloc est fixe.**

> « Bravo pour les impressions des dossards et blocs. On est très bien là
> maintenant. Juste une remarque sur l'impression des blocs : le numéro J6 ou
> J24 change de taille en fonction du nombre de caractères. Moi, je veux que la
> taille de la police soit fixe. »

C'est le comportement voulu par la spec 024 : `fiches.taille_numero_mm` calcule
la plus grande taille à laquelle le numéro tient dans ses 42 mm de colonne, donc
26 mm pour « J6 » et 19,5 mm pour « J24 ». Vu de près c'est logique ; vu sur une
planche de huit, la page a l'air bancale — ce qu'Adrien vient de constater sur
du vrai papier.

Attendu : **une seule taille**, la même sur toute étiquette, choisie pour que le
numéro le plus long y tienne. Une constante, pas un calcul par étiquette.

**R8 — les étiquettes sortent dans l'ordre alphabétique des zones.**

> « Je veux qu'ils soient classés dans l'ordre alphabétique des zones,
> c'est-à-dire la zone A d'abord et tu finis par la Z. »

Les étiquettes sortent aujourd'hui dans l'ordre de `Bloc.numero`, c'est-à-dire
l'ordre des lignes de l'onglet `Import`, c'est-à-dire l'ordre du `Plan`. Ce
n'est pas l'alphabet : le plan d'Annonay commence par X et Y et finit par E.
Pour coller au mur, on prend les feuilles dans l'ordre, et on veut aller de A à
Z.

Attendu : **zone par ordre alphabétique**, puis, à l'intérieur d'une zone,
l'ordre du classeur (difficulté puis numéro) — celui qui existe déjà. Les blocs
**sans zone** sortent en dernier : ils n'ont pas de mur où aller, et les faire
passer en premier, ce que fait SQLite avec les `NULL`, mettrait l'anomalie en
tête de la planche.

### L'application juge (PWA)

⚠️ Ces deux points ne concernent **que la PWA** : « on parle uniquement de la
PWA, car l'app Android va être supprimée » (Adrien, 03/09). Le dépôt
`climbcontest-android` n'est pas touché par ce lot.

**R9 — une icône de réglages sobre, et tout à droite.**

> « Dans cette application mobile […] la roue de configuration, son logo ne va
> pas avec le reste, trouve une roue plus sobre et simple. En plus je veux que
> ce logo soit celui de tout à droite. »

Deux défauts en un. Le glyphe est `⚙` (U+2699), un caractère à présentation
emoji sur iOS et Android : il sort en couleur, dessiné dans un autre style que
le voyant de connexion juste à côté, qui est un SVG au trait. Et il est placé
**avant** le voyant, donc ce n'est pas lui qui termine la barre.

Attendu : un engrenage **SVG au trait**, du même trait que le voyant (même
`stroke-width`, `currentColor`), et **le dernier élément** de l'en-tête.

**R10 — la catégorie du grimpeur, en gros, à droite de sa carte.**

> « Sur l'application, je voudrais que quand on scanne le grimpeur, on voit non
> seulement son nom prénom — tu as mis aussi son dossard — mais un peu plus
> gros, il faudrait aussi que tu mettes sa catégorie. En plus gros, je veux dire
> la taille du nom prénom. Et cette information, tu me la places… je la verrais
> bien plutôt sur la partie droite de la case grimpeur. »

La carte affiche aujourd'hui le nom en grand et `n°41` en petit dessous. La
catégorie n'y est pas — et ne peut pas y être : le catalogue rangé sur le
téléphone garde le **circuit** (« U13 ») et pas la catégorie complète
(« U13 F »).

⚠️ **C'est une décision de données, pas de mise en page.** Le commentaire de
`catalogue.js` explique le choix : « le genre n'apprend rien au test
d'appartenance », et il s'agit de données de mineurs entreposées sur vingt-cinq
téléphones de bénévoles. La catégorie complète voyage **déjà** sur le réseau —
`/api/v2/catalog` sert `participant.to_dict()` en entier — mais elle n'était pas
**conservée**. La demande la rend nécessaire à l'affichage : on la conserve
donc, et le circuit se **déduit** d'elle au lieu d'être rangé à côté. La quantité
de données stockées ne croît pas ; ce qu'elle contient, si, et c'est écrit noir
sur blanc dans `architecture.md`.

Attendu : la carte du grimpeur montre son **nom** à gauche, son **dossard** en
dessous, et sa **catégorie à droite**, à la taille du nom. La catégorie manque
(participant sans catégorie, catalogue d'une version antérieure) → rien ne
s'affiche à droite, et la carte reste exactement comme aujourd'hui.

### La console — les réussites

**R12 — la liste des dernières réussites.**

> « Je viens de faire un scan manuel avec mon téléphone et je suis revenu sur la
> partie réussite. Je m'attendais à avoir une entrée ou un tableau avec la liste
> des réussites, par exemple, qui ont été scannées par ce téléphone. »

La vue « Réussites » sait faire deux choses : en saisir une à la main, et en
**retrouver une** dont on connaît la référence à six caractères. Elle ne sait
pas répondre à « qu'est-ce qui vient d'arriver ? », qui est pourtant la question
qu'on se pose en sortant du scan qu'on vient de faire — et le sous-titre du menu
promet « saisir, retrouver un scan », pas « voir ».

Le serveur, lui, sait déjà : `GET /admin/reussites-tracees` accepte `?appareil=`
et rend les cent dernières réussites, les plus récentes d'abord, quand aucune
référence n'est donnée. Rien n'appelle ce cas.

Attendu : une carte **« Les dernières réussites »** dans la vue Réussites, qui
montre ce qui vient d'arriver — grimpeur, bloc, heure, téléphone, référence —,
se rafraîchit toute seule tant qu'on la regarde, et se **filtre par téléphone**
pour répondre exactement à la phrase d'Adrien. Une réussite hors du circuit du
grimpeur s'y signale, comme dans la recherche par référence.

## 3. Périmètre

### Inclus

| # | Ce qui change | Où |
| --- | --- | --- |
| R1 | « Où elle s'applique » disparaît sans cascade | console |
| R2 | Les trois boutons de la cascade se lisent | console |
| R3 | Les réglages d'affichage arrivent en ~3 s | API publique + page de résultats |
| R4 | Lecture/pause survit au rechargement | page de résultats |
| R5 | Play et pause dessinés du même trait | page de résultats |
| R6 | La recherche est masquée par défaut | page de résultats |
| R7 | Taille de numéro fixe sur les étiquettes | impression |
| R8 | Étiquettes triées par zone, de A à Z | impression |
| R9 | Engrenage SVG sobre, tout à droite | PWA juge |
| R10 | La catégorie sur la carte du grimpeur | PWA juge + catalogue |
| R11 | La légende des profils sur le mur | page de résultats |
| R12 | La liste des dernières réussites | console |

### Exclu

- **L'application Android.** Elle va être supprimée ; R9 et R10 ne la touchent
  pas.
- **Le format du plan**, la géométrie du mur, la façon dont les zones sont
  dessinées : R11 n'ajoute qu'une légende.
- **Le calcul du classement.** Aucun point de ce lot ne touche à un score.
- **Le classeur Google.** Aucune écriture, aucun changement de lecture.
- Toute refonte visuelle de la PWA : c'est la spec 035, et elle ne code rien.

## 4. Critères d'acceptation

- [ ] R1 — « Aucune cascade » coché : ni les phrases, ni le contrôle, ni
      l'aperçu, ni les raccourcis, ni la grille des catégories ne sont visibles.
      Cocher « Comme le classeur » ou « Sur mesure » ramène les deux groupes.
- [ ] R2 — dans les deux thèmes, le bouton coché se distingue des deux autres
      par autre chose qu'un point pâle : pastille pleine à l'accent de la
      console, et fond de carte teinté.
- [ ] R3 — un classement rallumé dans la console apparaît sur la page de
      résultats **sans rechargement** ; un classement éteint disparaît, et s'il
      était affiché la page bascule sur un autre. Le délai est de **3 s** en
      local, et jusqu'à **8 s** derrière le proxy, qui garde les réponses de
      `/api/public/*` cinq secondes — contre quinze auparavant, et un
      rechargement à la main.
- [ ] R4 — page mise en lecture, rechargement : elle repart **en lecture**.
      Mise en pause, rechargement : elle repart en pause. Rien de mémorisé :
      lecture sur `?mur`, pause ailleurs.
- [ ] R5 — les deux états du bouton sont deux icônes dessinées, de même taille
      optique et de même couleur ; aucun caractère emoji dans le bouton.
- [ ] R6 — première visite : le champ de recherche n'est pas affiché. Un clic
      sur `⌕` le montre, et il est encore là au rechargement suivant.
- [ ] R7 — sur une planche mêlant « J6 » et « J24 », les deux numéros ont
      **exactement** la même taille, et le plus long ne déborde pas de sa
      colonne.
- [ ] R8 — les étiquettes sortent zone A, puis B, … puis Z ; à l'intérieur
      d'une zone, l'ordre du classeur est conservé ; les blocs sans zone sont en
      dernier.
- [ ] R9 — l'engrenage est un SVG au trait, dernier élément de l'en-tête, à la
      droite du voyant de connexion.
- [ ] R10 — après le scan d'un grimpeur, sa catégorie s'affiche à droite de sa
      carte, à la taille du nom. Sans catégorie connue, la carte est celle
      d'avant.
- [ ] R11 — la légende du mur nomme les profils utilisés par le plan courant,
      avec leur couleur, du moins au plus déversant, en thème clair et sombre.
- [ ] R12 — après un scan, la vue Réussites le montre sans qu'on ait à taper
      sa référence, et le filtre par téléphone ne montre que ce que ce
      téléphone a envoyé.

## 5. Ce qui part ailleurs

Quatre remarques de la même revue sont des **évolutions**, pas des défauts.
Elles ont leur spec et leur PR, menées en parallèle :

| Spec | Ce que c'est | Branche |
| --- | --- | --- |
| [034](../034-qr-de-zone/) | Le juge scanne un QR posé sur sa table pour nommer son poste ; la console les génère et les imprime à partir des zones du plan | `feat/034-qr-de-zone` |
| [035](../035-refonte-pwa-juge/) | Maquettes interactives pour la refonte visuelle de la PWA — **aucune implémentation**, une décision à prendre | `feat/035-refonte-pwa-maquettes` |
| [036](../036-avancement-par-zone/) | L'avancement du grimpeur par zone (« 1/4 ») sur le plan de sa fiche | `feat/036-avancement-par-zone` |

⚠️ La 036 et le point R11 de ce lot touchent le **même écran** — la vue « mur »
de la fiche du grimpeur. La frontière a été posée à l'avance : R11 ne modifie
que le bloc `.sf-legende` et ses styles, la 036 ne le touche pas. Les deux
branches devront quand même être **fusionnées à blanc et testées ensemble**
avant merge : git fusionne sans conflit deux modifications voisines qui ne
tiennent pas debout ensemble.

## 6. Cas limites

| Situation | Attendu |
| --- | --- |
| R3 — tous les classements masqués | Le réglage est ignoré, comme aujourd'hui : une page vide se lit comme une panne |
| R3 — le classement regardé vient d'être masqué | La page bascule sur le premier visible, sans erreur |
| R3 — la réponse des réglages échoue | La page garde ce qu'elle a ; elle ne se vide pas, elle ne crie pas |
| R3 — rejeu d'archive (`?archive=`) | Aucune interrogation des réglages : une archive fige ce qu'elle fige |
| R4 — stockage local indisponible (navigation privée) | Le comportement d'avant, sans erreur |
| R4 — valeur mémorisée abîmée | Traitée comme absente |
| R6 — mode `?mur` | Inchangé : le champ n'y est jamais affiché |
| R7 — numéro à quatre caractères ou plus | Il ne déborde pas de l'étiquette ; il est coupé plutôt que de manger le QR |
| R8 — zone en minuscules, ou à deux lettres | Triée sans surprise ; le tri ne suppose pas une lettre unique |
| R8 — aucun bloc, ou un seul | Planche vide ou d'une étiquette, comme aujourd'hui |
| R10 — catalogue d'une version antérieure | Marqueur de format changé, le téléphone retélécharge tout seul |
| R10 — participant sans catégorie | Rien à droite de la carte, aucun trou visible |
| R11 — plan illisible par la page | Aucun plan dessiné, donc aucune légende — inchangé |
| R11 — plan dont tous les murs sont verticaux | Une seule pastille de profil |
| R12 — aucune réussite | « Aucune réussite pour l'instant », pas un tableau vide |
| R12 — réussite saisie à la main | Apparaît, avec « saisie de <compte> » à la place du téléphone |
| R12 — compétition inexistante | Le message métier de la route, comme les autres cartes |
