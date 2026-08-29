# 012 — Fermer le lien entre l'application juge et le backend

## Résumé

Le backend est joignable depuis Internet. Les routes que l'application juge
appelle — vérifier un dossard, vérifier un bloc, envoyer un lot de réussites,
télécharger le catalogue — portent déjà un garde-fou de clé d'API, mais **en mode
toléré** : une requête sans clé est acceptée.

Autrement dit, n'importe qui connaissant l'adresse peut aujourd'hui écrire dans
la base d'une compétition en cours.

Cette spec ferme le lien : l'application envoie une clé, le serveur l'exige.

## Ce qui existe déjà

`climbcontest/auth.py` porte le mécanisme depuis la spec 001, avec trois régimes :

| Requête | Mode toléré (défaut actuel) | Mode strict |
| --- | --- | --- |
| clé absente | **acceptée**, comptée | refusée `401` |
| clé correcte | acceptée | acceptée |
| clé incorrecte | refusée `401` | refusée `401` |

La tolérance existait pour une raison précise, écrite dans la spec 001 :
l'application `v3.1.4` du Play Store n'envoie aucune clé, et la casser le jour
d'une compétition aurait été pire que le risque couvert.

Il manque donc **une seule chose côté serveur** — basculer le régime — et **tout
côté application**.

## Ce qu'une clé dans un APK protège, et ce qu'elle ne protège pas

Il faut le dire avant d'écrire une ligne, parce que ça décide de ce qu'on peut
attendre de cette spec.

La clé est compilée dans l'application, qui est distribuée publiquement. **Elle
s'extrait de l'APK en quelques minutes** avec des outils courants. Ce n'est donc
pas un secret au sens cryptographique.

Ce que ça arrête, et qui est le risque réel ici :

- un robot qui balaie Internet et trouve `/api/v3/successes` ;
- quelqu'un qui découvre l'adresse dans l'historique d'un navigateur ou sur un
  écran, et qui essaie ;
- un envoi accidentel depuis un outil de test pointé sur la mauvaise adresse.

Ce que ça n'arrête pas : quelqu'un qui a l'application, veut fausser la
compétition, et sait démonter un APK. Pour celui-là, il faudrait une clé par
appareil remise à la main — un choix qu'Adrien a écarté le 29/08, et à raison :
vingt-cinq manipulations un dimanche matin coûtent plus cher que le risque.

**La clé relève le mur ; elle ne le rend pas infranchissable.** Elle vient en
plus de ce qui existe déjà : CrowdSec sur `edge`, HTTPS, et une VM allumée
seulement les jours de compétition.

## Décisions prises (29/08)

| Question | Décision d'Adrien |
| --- | --- |
| Où l'application prend la clé | **Compilée dans l'APK**, depuis une propriété Gradle jamais commitée |
| Quand le serveur l'exige | **Tout de suite** — mode strict activé |
| Deux clés acceptées | **Oui**, pour pouvoir changer la clé sans jour de bascule |

## La conséquence sur le plan de repli, assumée

Le repli garanti pour novembre est le gel `V3.1.4`, qui **n'envoie aucune clé**.
En mode strict, y revenir ne suffirait donc plus : il faudrait aussi reposer
`CLIMBCONTEST_API_KEY_STRICTE=0` sur la VM.

C'est une commande de plus à exécuter dans l'urgence, et c'est exactement le
genre d'étape qu'on oublie. Elle est donc **écrite dans le plan de repli**, en
premier, avant le retour de version — pas en note de bas de page.

## Périmètre

### Inclus

**Serveur**

- Le mode strict devient le **défaut**. Une installation qui oublie la variable
  est fermée, pas ouverte.
- Plusieurs clés acceptées en parallèle, pour changer de clé sans coupure.
- Une configuration incohérente — mode strict et aucune clé définie — répond
  **503 avec un message clair**, pas `401`. Un `401` ferait chercher une erreur
  de clé là où le problème est une variable absente.
- `/health` dit quel régime est actif et combien de clés sont acceptées.

**Application**

- La clé voyage dans l'en-tête `X-Api-Key`, sur **toutes** les requêtes API.
- Elle vient d'une propriété Gradle ou d'une variable d'environnement, jamais du
  dépôt — qui est public.
- Un build **release** sans clé **échoue**, plutôt que de produire un APK qui
  sera refusé par le serveur.

**Documentation**

- Le plan de repli gagne l'étape `CLIMBCONTEST_API_KEY_STRICTE=0`.
- Le critère resté ouvert de la spec 001 est repris.

### Exclu

- **Une clé par appareil.** Écarté par Adrien le 29/08 : vingt-cinq
  manipulations le jour J coûtent plus cher que le risque couvert.
- **Une signature des requêtes** (HMAC sur le corps). Ça résisterait au rejeu et
  à la falsification, mais suppose un secret que l'APK ne peut pas garder — donc
  le même plafond, pour beaucoup plus de code.
- **Limiter le débit par clé.** CrowdSec est déjà sur `edge` et couvre le cas.
- Toucher aux routes publiques (`/api/public/*`) ou à la console, qui a ses
  propres comptes depuis la spec 005.

## Critères d'acceptation

### Serveur

- [x] Sans variable `CLIMBCONTEST_API_KEY_STRICTE`, le régime est **strict**.
- [x] Une requête sans clé sur une route de juge reçoit `401`.
- [x] Une requête avec la bonne clé passe.
- [x] Une requête avec une clé fausse reçoit `401`, dans les deux régimes.
- [x] La comparaison des clés est à **temps constant**, et ne dit jamais
      laquelle des clés acceptées a été reconnue.
- [x] Deux clés configurées : les deux passent.
- [x] Mode strict **sans aucune clé configurée** : `503` avec un message qui
      nomme la variable manquante.
- [x] Le mode toléré reste atteignable par `CLIMBCONTEST_API_KEY_STRICTE=0` —
      c'est la porte de sortie du plan de repli.
- [x] `/health` expose le régime et le nombre de clés acceptées, **jamais** la
      clé elle-même ni un préfixe.
- [x] Les routes publiques restent accessibles sans clé.

### Application

- [x] Toutes les requêtes API portent `X-Api-Key`.
- [x] La clé n'apparaît **nulle part** dans le dépôt.
- [x] `assembleRelease` sans clé **échoue**, avec un message qui dit quoi faire.
- [x] `installDebug` sans clé **fonctionne** : la clé de développement suffit.
- [x] Une clé refusée par le serveur ne fait perdre aucune réussite : la file
      garde tout et réessaie.

### Documentation

- [x] Le plan de repli porte l'étape `CLIMBCONTEST_API_KEY_STRICTE=0`, **avant**
      le retour de version.
- [x] Le critère de la spec 001 est repris et daté.

## Cas limites

| Cas | Comportement attendu |
| --- | --- |
| Un téléphone reste sur `V3.1.4` le jour J | Ses envois sont refusés `401`. **Ses réussites ne sont pas perdues** : l'application `v3.1.4` garde sa file et réessaie. Il faut lui installer la nouvelle version, ou repasser en mode toléré. |
| La clé fuite pendant la compétition | On ne change rien pendant. Après : nouvelle clé publiée dans une nouvelle version, les deux clés acceptées le temps que tous les téléphones l'aient, puis l'ancienne retirée. |
| La variable est vide (`CLIMBCONTEST_API_KEY=`) | Traitée comme absente. Une chaîne vide n'est pas une clé. |
| Deux clés identiques | Sans effet. On ne le refuse pas : ce serait une panne au démarrage pour un doublon sans conséquence. |
| Le serveur répond `401` à un lot | La file est **intacte** — c'est déjà l'invariant de l'`Expediteur` : une réussite ne quitte la file que si le serveur a statué sur elle. |
