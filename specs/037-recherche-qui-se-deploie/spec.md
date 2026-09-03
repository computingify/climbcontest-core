# Spec 037 — la recherche qui se déploie

> **Cette spec ne contient aucune implémentation, et c'est volontaire.** Son
> livrable est une **décision** d'Adrien, prise sur une maquette qu'on touche :
> `maquettes/index.html`. Une animation ne se juge pas sur une capture.
>
> Le code viendra une fois la variante choisie, dans une PR qui suivra celle-ci.
> C'est le même déroulé que la spec 035, et c'est ce qu'Adrien a demandé
> explicitement le 03/09 : « pour toutes tes questions il me faut un visuel si
> c'est de l'UX, donc un HTML que je peux regarder ».

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

- [ ] Sur téléphone, la lecture et la loupe sont **échangées** : la loupe termine
      la rangée.
- [ ] Un appui sur la loupe **déploie** le champ par une transition, et lui donne
      le focus.
- [ ] Un second appui, la croix, ou **Échap** referme et **vide** le champ ; la
      liste redevient complète.
- [ ] Le champ fermé n'est **pas** dans l'ordre de tabulation, et la loupe porte
      un `aria-expanded` qui dit l'état.
- [ ] `prefers-reduced-motion` : le champ apparaît, sans transition.
- [ ] Le mode `?mur` est **inchangé** : aucune recherche, aucun bouton.
- [ ] Le comportement sur grand écran est celui tranché en §5, et il est testé.
- [ ] Un test au navigateur pilote le geste complet : ouvrir, taper, filtrer,
      fermer, vérifier que la liste est revenue.

## 5. Ce qu'Adrien doit trancher

1. **La variante** — V1, V2 ou V3 (ou un croisement).
2. **Le sens de l'échange.** La maquette a un bouton « la loupe à droite » qui
   inverse l'ordre : la loupe au bout de la rangée, ou en tête. J'ai posé la
   loupe **au bout** par défaut, parce que c'est de là que le champ se déploie
   naturellement vers la gauche — mais c'est à voir au doigt.
3. **Le grand écran.** Trois sorties : le même déploiement (le champ y sera
   court), le comportement actuel (le champ sous la barre), ou rien du tout —
   sur un vidéoprojecteur, la recherche ne sert pas.

## 6. Cas limites

| Situation | Attendu |
| --- | --- |
| On ferme avec du texte dedans | Le champ est vidé et la liste redevient complète |
| La fiche d'un grimpeur est ouverte par-dessus | La recherche ne s'ouvre pas derrière ; la fiche garde le focus |
| Écran très étroit (320 px) | Le champ se déploie encore ; le placeholder est tronqué, pas le champ |
| `prefers-reduced-motion` | Pas de transition, le champ est simplement là |
| Clavier seul | Tab atteint la loupe, Entrée ouvre, Échap ferme, le focus revient sur la loupe |
| Mode `?mur` | Rien ne change |
