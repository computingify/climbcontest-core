# Spec 037 — la recherche qui se déploie

> **Adrien a tranché le 03/09, sur la maquette.** Les trois questions du §5 ont
> leur réponse, l'implémentation suit dans la même branche, et la maquette reste
> dans `maquettes/index.html` — c'est elle qui porte le raisonnement.
>
> | | Retenu |
> | --- | --- |
> | **La variante** | **V3** — le champ recouvre la rangée, pleine largeur |
> | **Le sens de l'échange** | La **loupe termine** la rangée ; le champ se déploie vers la gauche |
> | **Le grand écran** | **Le même déploiement**, « quitte à avoir un champ court » |

## 1. D'où vient cette spec

Relecture d'Adrien du 03/09/2026, après avoir tranché les huit décisions de la
revue du même jour :

> « Pour l'écran résultat, je voudrais que tu échanges le logo recherche et play
> sur téléphone afin de modifier le fonctionnement du bouton recherche. Je veux
> que ce soit comme sur certaines applications ou pages web : au clic sur le
> bouton recherche, c'est le bouton qui s'anime et qui déploie horizontalement
> une zone de texte. C'est joli et design. »

Elle **s'appuie sur** la spec 033 (R6), qui a rendu la recherche masquée par
défaut et a remplacé les glyphes de l'en-tête par des icônes dessinées. Sans
elle, il n'y aurait pas de bouton loupe à animer.

## 2. Ce qu'on cherche

Aujourd'hui, la loupe est une **bascule** : elle fait apparaître un champ sur sa
propre ligne, sous la barre des catégories. Ça marche, et ça ne ressemble à
rien — le champ surgit, la page se décale d'un cran.

Ce qu'Adrien décrit est le motif que tout le monde connaît : **le bouton devient
le champ**. C'est une question de mouvement, donc de mise au point ; d'où la
maquette.

### Ce qui est déjà décidé, et ne se rediscute pas ici

| | |
| --- | --- |
| La recherche part **masquée** | Décision D1 du 03/09 |
| La loupe et la lecture sont **échangées** sur téléphone | Demande explicite ci-dessus |
| Fermer la recherche **vide le champ** | Sinon on laisse une liste filtrée sans rien pour l'expliquer — la règle existe déjà dans `resultats.html` |
| L'ouverture **n'est pas mémorisée** | C'est un geste, pas un réglage. Le réglage mémorisé, c'est « la recherche est-elle disponible », et il ne change pas |

### La contrainte qui décide

⚠️ **Sur un téléphone, l'en-tête se replie.** Sous le point de rupture de
680 px, `.droite` prend toute la largeur et les deux commandes tombent sur
**leur propre rangée**, à gauche. Ce n'est pas un détail : c'est ce qui donne au
champ la place de se déployer sur toute la largeur, et c'est pour ça que la
demande ne vaut que « sur téléphone ». Sur un grand écran, les deux boutons sont
au bout d'une ligne déjà pleine — le déploiement y a beaucoup moins de place.

**Le comportement sur grand écran est une question ouverte** (voir §5).

## 3. Les quatre variantes proposées

Toutes sont dans la maquette, toutes se déclenchent au doigt, et un bouton
« au ralenti » les montre à un quart de vitesse — c'est la seule façon de juger
une courbe de 300 ms.

| | Ce que ça fait | Ce que ça coûte |
| --- | --- | --- |
| **V1** — la loupe s'étire sur place | Le bouton **devient** le champ ; l'icône reste dedans en préfixe | Le champ reste étroit tant que le bouton de lecture occupe sa place |
| **V2** — le champ pousse, la lecture reste | Le champ s'ouvre **entre** les deux boutons | Deux éléments à tenir d'accord, champ un peu court |
| **V3** — le champ recouvre la rangée | Il glisse **par-dessus** les commandes et prend toute la largeur | La lecture disparaît pendant la recherche |
| **V4** — le champ se déplie dessous | *Témoin* : ce que fait la page aujourd'hui, en moins brutal | Aucun déploiement horizontal — c'est ce qu'on remplace |

V4 n'est pas là pour être choisie : elle est là pour qu'on compare à quelque
chose.

## 4. Critères d'acceptation

Ils valent quelle que soit la variante retenue.

- [x] Sur téléphone, la lecture et la loupe sont **échangées** : la loupe termine
      la rangée.
- [x] Un appui sur la loupe **déploie** le champ par une transition, et lui donne
      le focus.
- [x] Un second appui, la croix, ou **Échap** referme et **vide** le champ ; la
      liste redevient complète.
- [x] Le champ fermé n'est **pas** dans l'ordre de tabulation, et la loupe porte
      un `aria-expanded` qui dit l'état.
- [x] `prefers-reduced-motion` : le champ apparaît, sans transition.
- [x] Le mode `?mur` est **inchangé** : aucune recherche, aucun bouton.
- [x] Le comportement sur grand écran est celui tranché en §5, et il est testé.
- [x] Un test au navigateur pilote le geste complet : ouvrir, taper, filtrer,
      fermer, vérifier que la liste est revenue.

## 5. Ce qu'Adrien a tranché, et ce que ça a entraîné

**V3**, la **loupe au bout**, et **le même déploiement partout**.

### La conséquence qu'on n'avait pas vue en posant la question

⚠️ **Le réglage mémorisé de la spec 033 (R6) disparaît.** Il gardait « la
recherche est-elle offerte », posée à « masquée » par défaut. Depuis que le
champ se déploie, ce réglage n'a plus d'objet : le champ est **replié** tant
qu'on ne le demande pas, ce qui *est* « masquée par défaut » — sans avoir à se
souvenir de quoi que ce soit.

Ouvrir la recherche est un **geste**, pas un réglage : le mémoriser rouvrirait,
au chargement suivant, un champ que personne n'a demandé. Le stockage local ne
garde donc plus que l'état **lecture/pause**.

C'est une simplification, pas une perte : le besoin de la spec 020 — « masquer
la recherche au vidéoprojecteur » — est toujours servi, et mieux.

### Le défaut trouvé à l'écran, sur grand écran

Le champ s'ouvre par-dessus le bandeau de droite (nom de l'édition, heure,
compteur) et le **coupait en plein milieu** : ça se lit comme un défaut
d'affichage, pas comme un panneau qui s'ouvre. Le bandeau **s'efface** donc le
temps de la recherche et revient à la fermeture. C'est ce que « recouvrir »
veut dire, et ça n'a été vu qu'en regardant.

## 6. Cas limites

| Situation | Attendu |
| --- | --- |
| On ferme avec du texte dedans | Le champ est vidé et la liste redevient complète |
| La fiche d'un grimpeur est ouverte par-dessus | La recherche ne s'ouvre pas derrière ; la fiche garde le focus |
| Écran très étroit (320 px) | Le champ se déploie encore ; le placeholder est tronqué, pas le champ |
| `prefers-reduced-motion` | Pas de transition, le champ est simplement là |
| Clavier seul | Tab atteint la loupe, Entrée ouvre, Échap ferme, le focus revient sur la loupe |
| Mode `?mur` | Rien ne change |
