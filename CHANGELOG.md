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

## [0.2.0] — 2026-08-28

La base devient la source de vérité, le classeur en devient un miroir. C'est le
préalable de tout le reste : ni classement live, ni page résultats, ni saisie
manuelle tant que les données ne sont pas fiables. Spec 002.

**L'application juge `v3.1.4` du Play Store continue de fonctionner sans mise à
jour** : ses trois routes gardent leur contrat au caractère près, et une suite de
tests dédiée le vérifie à chaque build.

### Ajouté

- Modèle multi-compétition. L'identité d'un participant est son identifiant, pas
  son dossard : un dossard est un attribut, nullable, unique par compétition, qui
  peut changer de main tant qu'aucune réussite n'y est attachée.
- Table `Success` avec contrainte d'unicité `(participant, bloc)` : un double
  appui sur « Envoyer » renvoie `201` et ne crée qu'une seule réussite.
- Colonne `sheet_synced_at` : ce qui reste à écrire dans le classeur est
  désormais une requête SQL, pas une file en mémoire vive.
- `GET /api/v2/catalog` versionné, avec `304` quand rien n'a changé — de quoi
  faire valider les scans hors ligne par la future application juge.
- Clé d'API en **mode toléré** : absente elle est acceptée mais comptée, fausse
  elle est refusée. Le compteur, exposé par `/health`, dira quand on pourra la
  rendre obligatoire sans casser l'application déployée.
- `/health` expose le nombre de réussites en attente de synchronisation.
- Comptes et rôles, posés vides pour éviter une migration en spec 005.

### Corrigé

- **R1** — La base n'est plus effacée au démarrage. `drop_all()` s'exécutait au
  niveau module, donc dans chacun des quatre workers gunicorn. Vérifié : quatre
  processus démarrés simultanément laissent la base intacte.
- **R2** — Les réussites survivent à un redémarrage.
- **R3** — Un échec d'écriture Google ne détruit plus rien : rien n'est marqué
  comme synchronisé, et le cycle suivant réessaie.
- **R4** — Toute réussite est tracée, horodatée, rejouable.
- **R5** — Un grimpeur sans club ni catégorie est importé et signalé, au lieu
  d'être ignoré en silence.
- **R6** — Le numéro de bloc est lu à une position explicite. Il était deviné par
  `line[-1]`, ce qui donnait le numéro de zone sur une ligne tronquée, et
  envoyait les réussites sur la mauvaise ligne du classeur.
- **R7** — Un dossard inconnu ne déclenche plus de lecture du classeur.
- **R12** — Les doublons ne sont plus possibles.

### Modifié

- Point d'entrée : `wsgi:app` via une fabrique d'application. `main.py`,
  `models.py` et `google_sheets*.py` sont remplacés.
- L'identifiant du classeur vit en base, par compétition — plus jamais en dur
  dans le code. C'était le geste le plus souvent oublié d'une édition à l'autre.

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

[Non publié]: https://github.com/computingify/climbcontest-core/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.2.0
[0.1.2]: https://github.com/computingify/climbcontest-core/releases/tag/v0.1.2
[0.1.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.1.0
