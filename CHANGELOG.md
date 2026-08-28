# Changelog

Toutes les évolutions notables de ClimbContest. Format
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnage
[sémantique](https://semver.org/lang/fr/).

**Ce fichier est contraignant, pas décoratif.** Le workflow de release échoue
avant même de construire l'archive s'il ne trouve pas la section de la version
taguée. Le contenu de cette section devient le corps de la release GitHub :
c'est ce qu'on lit pour savoir ce qui a changé.

Règle de version, sachant que l'application juge est déployée sur des téléphones
qu'on ne met pas à jour le matin d'une compétition :

- **MAJEUR** — rupture du contrat d'API avec l'application juge. Se prépare
  entre deux compétitions, jamais pendant.
- **MINEUR** — nouvelle fonctionnalité, compatible.
- **CORRECTIF** — correction, compatible.

## [Non publié]

## [0.1.2] — 2026-08-28

Trois défauts de l'agent de déploiement, trouvés en jouant réellement les
scénarios d'échec de la spec 001 plutôt qu'en les supposant.

### Corrigé

- **Boucle de redémarrages.** Une release défectueuse était retentée à chaque
  tick de 2 minutes, et chaque tentative redémarrait le service deux fois. Un
  tag qui a échoué est désormais mémorisé et n'est plus réessayé ; publier une
  version suivante suffit à débloquer.
- **Retour arrière non vérifié.** Le script annonçait « revenu sur vX » sans
  sonder. Si la version précédente était cassée elle aussi, le journal disait
  que tout allait bien alors que le service était à terre. Le retour arrière se
  vérifie maintenant, et dit clairement quand il échoue.
- **Exécutions concurrentes.** Le timer et un déploiement manuel pouvaient se
  croiser : constaté en recette, deux exécutions à 14 secondes d'intervalle. La
  seconde a lu le lien `current` après la bascule de la première, a pris la
  version cassée pour « la précédente », et y est « revenue ». Un verrou
  garantit une seule opération à la fois, déploiement et retour arrière
  compris — c'est indispensable puisque le déploiement manuel est la commande
  du jour J.

### Modifié

- Le journal ne double plus chaque ligne sous systemd.

## [0.1.0] — 2026-08-28

Première release. Elle ne contient **aucun backend** : son seul but est de
valider la chaîne de livraison de bout en bout avant qu'il y ait quelque chose à
livrer — spec 001, itération 3.

### Ajouté

- Point d'entrée `wsgi.py` avec une route `/health` qui renvoie la **version
  déployée**. L'agent de déploiement vérifie ainsi que le service répond *avec
  la version qu'il vient d'installer*, et pas seulement qu'il répond.
- Service systemd `climbcontest` : gunicorn, 4 workers × 4 threads, durci
  (`ProtectSystem=strict`, écriture limitée à `shared/`).
- Agent de tirage `climbcontest-deploy` : lit la dernière release GitHub,
  **vérifie l'empreinte SHA-256**, construit l'environnement Python dans la
  release, bascule un lien symbolique, sonde, et **revient en arrière tout seul**
  si la nouvelle version ne répond pas.
- `climbcontest-rollback` : retour arrière manuel instantané, pour corriger sous
  pression un jour de compétition.
- `deployment/install.sh` : pose le socle sur une VM neuve, de façon idempotente.

### Sécurité

- Le compte de service n'a le droit de redémarrer que `climbcontest`, via une
  règle `sudoers` limitée à ce seul service.
- Les données et les secrets vivent dans `shared/`, hors des releases : un
  déploiement ou un retour arrière ne peut pas les toucher.

[Non publié]: https://github.com/computingify/climbcontest-core/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/computingify/climbcontest-core/releases/tag/v0.1.2
[0.1.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.1.0
