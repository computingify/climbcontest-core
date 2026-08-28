# 006 — Architecture

## Une page, servie telle quelle

```
  GET /resultats            ->  climbcontest/templates/resultats.html
  GET /resultats?mur        ->  la meme page, mode mur
        |
        |  toutes les ~15 s
        v
  GET /api/public/classement   (spec 004, deja livree)
        |
        v
  Caddy : Cache-Control 5 s   -> ~12 calculs/min quel que soit le nombre d'ecrans
```

Aucune route nouvelle côté API. La page est un client de plus de ce qui existe
déjà — et c'est ce qui la rend remplaçable : le jour où on en veut une autre, on
l'écrit sans toucher au backend.

## Pourquoi un seul fichier, sans rien

| Choix | Raison |
| --- | --- |
| Aucune bibliothèque | Un classement est une liste ordonnée. Un framework ajouterait un build, des dépendances à tenir à jour et un mode de panne de plus — pour afficher un tableau |
| Polices système | Une page projetée pendant une compétition ne peut pas attendre un service de polices. Si la box tombe à 10 h, l'écran doit continuer |
| Pas de build | Le fichier est servi tel qu'il est écrit. Une correction le jour J se fait en éditant un fichier, pas en relançant une chaîne de compilation |

Ce n'est pas de l'ascétisme : c'est le calcul de ce qui peut tomber un dimanche
matin dans une salle de sport.

## L'identité visuelle

Elle est tirée du sujet, pas d'un thème : **les six couleurs de circuit du
club**, dans leur ordre de difficulté.

```
  Jaune  <  Vert  <  Bleu  <  Mauve  <  Rouge  <  Noir
```

Chaque catégorie reçoit sa couleur. À cinq mètres, on sait ce qui est affiché
avant d'avoir lu le titre — et quand la rotation change de catégorie, le
changement se voit à la couleur avant de se lire.

Le podium reçoit un traitement distinct — c'est ce que les gens cherchent — mais
**sans or, argent ni bronze** : le classement bouge toute la journée, et une page
qui célèbre un podium provisoire vieillit mal.

## Le mode mur

| | Mode mur | Mode spectateur |
| --- | --- | --- |
| Taille du nom | ~34 px sur 1080p | ~17 px |
| Lignes visibles | 10, le reste attend le tour suivant | toutes |
| Navigation | rotation auto toutes les 20 s | sélecteur + recherche |
| Chrome | aucun | barre de catégories, champ de recherche |

La rotation ne s'arrête jamais et n'attend aucune interaction : l'écran est
accroché en hauteur, personne ne le touchera de la journée.

## Le rafraîchissement

```
  toutes les 15 s : GET /api/public/classement
      succes  -> on remplace les donnees, on note l'heure
      echec   -> on GARDE ce qu'on a, et l'age passe en rouge
```

Le point important est la seconde ligne. Une page de résultats qui se vide parce
qu'une requête a échoué est **pire** qu'une page en retard : elle fait croire que
la compétition s'est arrêtée. On garde toujours le dernier classement connu, et
on affiche son âge.

`calcule_le` vient du serveur (spec 004) : la page affiche « il y a 8 s » plutôt
que de laisser croire à du temps réel.

## Fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/templates/resultats.html` | **nouveau** — la page entière |
| `climbcontest/routes/public.py` | les routes qui la servent |
| `tests/test_page_resultats.py` | **nouveau** |

## Ce qui pourrait mal tourner

| Risque | Parade |
| --- | --- |
| Le backend tombe pendant la compétition | dernier classement conservé, âge affiché en rouge |
| 60 téléphones rafraîchissent en même temps | cache Caddy 5 s + cache moteur 5 s : ~12 calculs/min quel que soit le nombre |
| Un nom très long casse la mise en page | troncature, jamais de débordement |
| L'écran de la salle est en 4:3 ou en portrait | mise en page fluide, aucune dimension en dur |
| Quelqu'un ouvre la page avant le premier scan | message d'attente, pas un tableau vide |
