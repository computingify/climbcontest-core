# 010 — Le classement par club

## Résumé

Le classeur n'a aucun classement par club. Adrien en veut un, et a tranché la
règle le 29/08 : **somme des scores de tous les grimpeurs du club**.

## La conséquence, assumée

Un club qui vient à quinze passera presque toujours devant un club qui vient à
quatre, quel que soit le niveau. Ce n'est pas un défaut de la règle : c'est ce
qu'elle mesure — la participation autant que la performance.

C'est le choix d'Adrien, fait en connaissance de cause, après avoir vu les trois
formats côte à côte. **À redire au micro le jour J**, pour que personne ne
s'en étonne devant le podium.

### Une nuance qui tempère la règle

Elle n'apparaît pas au premier abord, et elle est rassurante : **s'agglutiner
sur les mêmes blocs ne rapporte presque rien**.

Un bloc vaut `1000 / nombre de personnes du groupe l'ayant réussi`. Trois
grimpeurs du même club qui font tous le même bloc facile gagnent 333 chacun —
soit 999 à eux trois, moins qu'un seul grimpeur ayant tenu deux blocs que
personne d'autre n'a réussis.

Autrement dit : « le gros club gagne » est vrai **à niveau égal**, pas dans
l'absolu. Le barème protège déjà en partie de l'effet redouté. Un test le
verrouille, pour que ça reste vrai.

## La question que la décision ne tranchait pas

Un grimpeur a **deux** scores : celui de sa catégorie (`U13 F`) et celui de son
circuit, le scratch (`U13`). Ils diffèrent — la valeur d'un bloc dépend du
nombre de personnes du groupe qui l'ont réussi, et le groupe n'est pas le même.

Les additionner compterait chaque grimpeur deux fois.

**Décision : c'est le score de la CATÉGORIE qui compte.** C'est le résultat
officiel du grimpeur, celui qu'on annonce et qui figure sur le podium. Le
scratch est une lecture transversale, pas un second résultat.

Un grimpeur **sans catégorie** ne compte donc pour aucun club — il n'apparaît
déjà dans aucun classement.

## Périmètre

### Inclus

- Un classement par club, dérivé des classements par catégorie.
- Exposé par l'API publique, au même titre que les autres groupes.
- Visible sur la page de résultats.

### Exclu

- Toute autre règle d'agrégation (moyenne, *n* meilleurs). Si le format change
  un jour, ce sera une décision, pas une option de plus à maintenir.
- Un classement club par catégorie. Un seul, toutes catégories confondues.

## Critères d'acceptation

- [x] Le score d'un club est la **somme** des scores de ses grimpeurs.
- [x] Chaque grimpeur ne compte **qu'une fois**, par sa catégorie.
- [x] Un grimpeur sans club ne fait pas apparaître un club « vide ».
- [x] Un grimpeur sans catégorie ne compte pour aucun club.
- [x] Les ex æquo partagent le rang, comme partout ailleurs.
- [x] Le nombre de grimpeurs du club est affiché — c'est ce qui rend le
      classement lisible, vu la règle retenue.
- [x] Aucune compétition, ou aucune réussite : pas de plantage.
- [x] Le classement club n'altère **aucun** classement existant.

## Cas limites

| Situation | Comportement |
| --- | --- |
| Grimpeur sans club | ignoré, aucun club fantôme |
| Club orthographié différemment (`La Grimpe` / `la grimpe`) | **deux clubs distincts** — on n'invente pas de rapprochement |
| Tous les scores à zéro | tous les clubs à zéro, ex æquo |
| Un seul club | un classement à une ligne, ce qui est correct |
