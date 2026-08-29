# 012 — Plan

Deux itérations. L'ordre compte, et il est contre-intuitif : **l'application
d'abord**.

Basculer le serveur en premier casserait l'émulateur, la CI et tout téléphone de
test à la seconde où la variable change. En envoyant la clé d'abord, le mode
toléré continue de tout accepter, et on vérifie que la clé passe **avant** de
fermer la porte.

## IT1 — L'application envoie la clé

- [ ] `build.gradle.kts` : `API_KEY`, valeur par défaut en debug, absente en
      release.
- [ ] Garde-fou : une tâche release sans clé fait échouer le build.
- [ ] `ClimbContestApi` pose `X-Api-Key` sur les quatre requêtes.

## IT2 — Le serveur l'exige

- [ ] `API_KEYS` remplace `API_KEY`, plusieurs clés acceptées.
- [ ] Comparaison à temps constant, sans court-circuit.
- [ ] Le mode strict devient le défaut.
- [ ] Strict sans clé configurée → `503` nommant la variable.
- [ ] `/health` expose le régime et le nombre de clés.
- [ ] Plan de repli et critère de la spec 001 mis à jour.

## Plan de test

Écrit avant l'implémentation.

### Application — JVM

| Scénario | Résultat attendu |
| --- | --- |
| vérifier un dossard | l'en-tête `X-Api-Key` est présent |
| vérifier un bloc | idem |
| télécharger le catalogue | idem, sur un `GET` |
| envoyer un lot | idem |
| clé vide | **aucun** en-tête, plutôt qu'un en-tête vide qui vaudrait une clé fausse |
| le serveur répond `401` | la file garde tout, `echecsConsecutifs` augmente |

### Serveur — pytest

| Scénario | Résultat attendu |
| --- | --- |
| strict, sans clé | `401` |
| strict, bonne clé | passe |
| strict, clé fausse | `401` |
| strict, en-tête vide | `401` |
| toléré, sans clé | passe, et c'est compté |
| toléré, clé fausse | `401` |
| deux clés, la première | passe |
| deux clés, la seconde | passe |
| clé retirée de la configuration | ne passe plus |
| variable définie mais vide | traitée comme absente |
| strict, aucune clé configurée | `503`, message nommant `CLIMBCONTEST_API_KEY` |
| défaut sans variable de régime | strict |
| routes publiques | passent sans clé |
| `/health` | donne le régime et le nombre, **pas** la clé |

### Sur le terrain

| À vérifier | Comment |
| --- | --- |
| L'émulateur parle au backend local en mode strict | une réussite mise en file arrive en base |
| Une clé fausse est refusée sans perte | file intacte après plusieurs tentatives |
| `/health` ne divulgue rien | lecture de la réponse complète |
