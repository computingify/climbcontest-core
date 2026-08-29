# 010 — Architecture

## Dérivé, pas recalculé

```
  calculer_tout()  ->  classements par categorie et par circuit
                            |
                            v
                   calculer_clubs()  ->  un classement de plus
```

Le classement club **ne recalcule rien**. Il additionne des scores déjà
calculés, en ne prenant que les classements de type `categorie`.

C'est ce qui garantit qu'il ne pourra jamais diverger : si le moteur change, le
classement club suit sans qu'on y touche. Recalculer à partir des réussites
aurait créé un second chemin, et donc la possibilité qu'ils ne disent pas la
même chose.

## Pourquoi la catégorie et pas le scratch

Un grimpeur figure dans deux classements. Les additionner le compterait deux
fois ; il faut donc choisir.

La **catégorie** est son résultat officiel — celui qu'on annonce, celui du
podium. Le scratch est une lecture transversale du même travail, pas un second
résultat.

## Ce qui apparaît dans l'API

Le classement club est un `Classement` comme les autres, de type `club`. Il
arrive donc dans `/api/public/classement` et dans `/api/public/groupes` sans
qu'aucune route ne change, et la page de résultats l'affiche sans modification —
elle boucle déjà sur les groupes.

La seule différence est le contenu d'une ligne : un club n'a pas de dossard, et
son nombre de grimpeurs compte. `Ligne` porte déjà `blocs_reussis` ; on y met le
total des blocs du club, et le nombre de grimpeurs va dans `dossard`… non : ce
serait un détournement qui se paierait plus tard.

**Un champ dédié.** `Ligne` gagne `membres`, `null` partout ailleurs.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `climbcontest/classement.py` | `calculer_clubs()`, et `club` sur `ParticipantCalcul` |
| `climbcontest/classement_service.py` | charge le club, ajoute le classement |
| `tests/test_classement_club.py` | **nouveau** |
