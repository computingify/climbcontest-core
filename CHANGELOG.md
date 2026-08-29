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

## [0.4.1] — 2026-08-29

### Ajouté

- **La console d'administration elle-même**, sur `/console`. La `0.4.0` livrait
  ses routes JSON — et la spec la déclarait livrée — mais pas la page. Un
  organisateur ne peut pas utiliser `curl` un dimanche matin.

  Quatre écrans : connexion, participants, saisie manuelle, impression. En
  mauve là où la page publique est en bleu, pour qu'on sache d'un coup d'œil si
  on regarde ce que voient les spectateurs ou ce qu'on peut modifier.

  Pensée pour le jour J : une session qui expire ramène à la connexion **en le
  disant** plutôt que de ressembler à une panne ; une saisie en double
  s'affiche en jaune et non en rouge — ce n'est pas une faute, c'est une
  précaution qui a fonctionné ; après une saisie le curseur revient sur le
  champ « bloc », pour enchaîner plusieurs blocs du même grimpeur.

## [0.4.0] — 2026-08-29

**La console d'administration.** Spec 005 — les quatre briques retenues pour
novembre.

### Ajouté

- **Comptes et rôles.** Deux rôles : `admin` et `organisateur`. Mot de passe
  haché, session signée de 12 heures, et un contrôle d'accès **fail closed** —
  session absente, illisible, expirée, cookie forgé, utilisateur désactivé
  entre-temps, rôle inconnu : tout donne `401`.
  Le premier compte se crée par `flask creer-admin`, jamais par une route.
- **Participants à chaud** : ajouter quelqu'un pendant la compétition, et
  réaffecter un dossard. Le catalogue est incrémenté, donc les téléphones
  voient le nouveau venu en moins de vingt secondes.
- **Saisie manuelle** d'une réussite, et sa suppression. Elle compte au
  classement exactement comme un scan, porte `source = manuel` et
  **l'identifiant de qui l'a saisie**.
- **Impression des dossards** : format repris du classeur, en bandes à
  découper, dimensionné en millimètres. Un lot, une catégorie, ou un seul.
  Le QR est généré **localement** — le classeur, lui, appelle
  `api.qrserver.com`, ce qui envoie les dossards à un tiers et ne fonctionne
  pas si la connexion tombe.

### Sécurité

- La clé d'API ne donne **plus** accès à l'administration. Elle est partagée
  entre 25 téléphones ; en faire un droit d'administration reviendrait à donner
  les clés de la base à tout le monde. C'était une mesure d'attente, posée en
  urgence la veille.
- Le temps de réponse à la connexion est le même que l'identifiant existe ou
  non. Répondre plus vite pour un compte inconnu révélerait quels identifiants
  sont valides.

### ⚠️ À faire au déploiement

`CLIMBCONTEST_SECRET_KEY` doit être définie sur la VM. Sans elle, la console
répond **503** et refuse de servir — avec la clé de développement, un cookie de
session se forge en trois lignes. Mieux vaut une console indisponible qu'une
console ouverte. Le reste du service n'est pas affecté.

## [0.3.4] — 2026-08-28

### Corrigé

- **Le miroir répétait la même plainte toutes les 40 secondes.** Le garde-fou de
  la `0.3.3` évitait bien l'appel Google inutile, mais l'avertissement partait
  encore à chaque cycle et sur chacun des quatre workers. Sur une journée, des
  milliers de lignes identiques — et c'est ainsi qu'on rate la vraie panne
  quand elle arrive.

  Une cause n'est journalisée **qu'une fois**. Le retour à la normale, lui, est
  annoncé : le silence qui suit une plainte serait autrement ambigu — on ne
  saurait pas si le miroir est reparti ou s'il est mort.
- Le garde-fou annonçait « 0 en attente ». C'est le chiffre qui compte : il dit
  combien de réussites seront reportées le jour où un classeur sera relié.

## [0.3.3] — 2026-08-28

### Corrigé

- **Une compétition sans classeur relié remplissait le journal.** Entre la
  création d'une compétition et son paramétrage, il n'y a pas encore de
  `spreadsheet_id` — c'est normal. Le miroir tentait pourtant l'écriture toutes
  les 40 secondes et journalisait une erreur Google à chaque fois, sur chacun
  des quatre workers : **six erreurs par minute** pour une situation
  parfaitement normale.

  C'est ainsi qu'un journal devient illisible, et qu'on rate la vraie panne
  quand elle arrive. Le miroir passe désormais son tour, et le dit une fois.

## [0.3.2] — 2026-08-28

### Corrigé

- **Le miroir ne trouvait jamais le jeton Google en production.** Le client le
  cherchait en chemin *relatif* — donc dans le répertoire de travail du service,
  où il n'a jamais été. Il vit dans `shared/secrets/`, hors des releases, comme
  les données ; l'unité systemd définissait déjà `CLIMBCONTEST_SECRETS_DIR`, que
  le code n'avait jamais lu.

  Constaté sur la VM : « Aucun jeton Google » toutes les 40 secondes. **Aucune
  réussite n'aurait atteint le classeur le jour de la compétition.** Les données
  n'étaient pas perdues pour autant — elles restent en base, marquées non
  synchronisées, et sont retentées : c'est exactement ce que la spec 002 avait
  prévu. Mais le classeur serait resté vide.

  Le message d'erreur cite désormais **les chemins essayés**. Le précédent
  disait « le déposer dans token.pickle », sans chemin — c'est ce qui a masqué
  le vrai problème : le fichier existait, mais ailleurs.

## [0.3.1] — 2026-08-28

### Corrigé

- **Avant le premier scan, l'écran de la salle affichait tout le monde à zéro,
  sans rien dire.** Le classement était juste — tous ex æquo — mais projeté sur
  un mur pendant la première demi-heure de chaque compétition, il se lisait
  comme un écran figé. La page l'annonce désormais, tout en gardant la liste :
  voir les inscrits affichés rassure sur le fait que le système tourne.

## [0.3.0] — 2026-08-28

La page de résultats. Spec 006.

C'est la première version que les **spectateurs** voient : jusqu'ici, tout ce qui
avait été livré s'adressait aux juges ou aux organisateurs.

### Ajouté

- **La page de résultats**, en deux modes servis par un seul fichier :
  - `/resultats?mur` — l'écran de la salle. Rotation automatique des catégories
    toutes les 20 s, nom à **42 px** sur un écran 1080p (lisible à cinq mètres),
    aucun bouton. Elle ne s'arrête jamais et n'attend aucune interaction.
  - `/resultats` — les téléphones. Recherche par nom ou par dossard, et choix de
    la catégorie.
- La recherche traverse **tous** les classements, pas seulement celui affiché :
  un parent qui cherche son enfant ne connaît pas forcément sa catégorie.
- `age_s` dans `/api/public/classement` : l'âge réel du calcul, vu par le
  serveur. La page ne peut pas le déduire — son horloge n'est pas celle du
  serveur — et affichait donc « calculé il y a 1 s » pour un classement que le
  cache gardait depuis 5 s.
- `tools/mesurer_volume.py` — le critère A12 de la spec 003.

### Modifié

- La racine `/` sert la page de résultats, et non plus un JSON de service.
- **Aucune dépendance extérieure** dans la page : polices système, aucune
  bibliothèque, un seul fichier servi tel quel. Une page projetée pendant une
  compétition ne peut pas dépendre d'un CDN — si la box tombe à 10 h, l'écran de
  la salle doit continuer. Vérifié dans un navigateur : **2 requêtes en tout**.
- Quand le backend devient injoignable, la page **garde** le dernier classement
  connu et affiche son âge en rouge. Une page de résultats qui se vide sur une
  erreur réseau fait croire que la compétition s'est arrêtée.

### Mesuré

Le volume échangé par l'application juge, contre la VM, sur 200 validations
réelles extrapolées à 3 600 :

| | v2 | v3 |
| --- | --- | --- |
| Requêtes HTTP | 10 800 | **817** |
| Octets sur le fil | 4,53 Mo | **696 ko** |
| Allers-retours **bloquants** | 10 800 | **0** |

L'estimation de la spec 003 (~360 requêtes, ~110 ko) était trop optimiste ; la
spec a été corrigée avec les chiffres mesurés, pas l'inverse.

## [0.2.1] — 2026-08-28

### Sécurité

- **La console d'administration n'exigeait aucune authentification.** Ses deux
  routes (`/admin/import/sheet`, `/admin/import/rapport`) étaient protégées par
  le garde-fou de clé d'API **en mode toléré** — lequel accepte, par
  construction, une requête sans clé. Cette tolérance existe pour que
  l'application `v3.1.4` du Play Store continue de fonctionner ; elle n'avait
  rien à faire ici.

  Constaté en production, exposé sur Internet :
  `GET https://climbcontest.adn-dev.fr/admin/import/rapport` répondait `200`, et
  un `POST` sur `/admin/import/sheet` aurait déclenché un **réimport complet du
  classeur** — réécriture de la base et rafale d'appels Google — à la demande de
  n'importe qui.

  Ces routes exigent désormais une clé **valide**, sans tolérance, et chaque
  refus est journalisé. Les trois routes du juge restent tolérantes ; un test le
  verrouille explicitement pour qu'on ne durcisse pas la `v3.1.4` par accident.

  Corrigé en parallèle côté `edge` : `/admin/*` ne sort plus du LAN, sur le même
  motif que `/health`. Les deux couches sont voulues — la spec 005 ouvrira cette
  console à de vrais comptes, et il vaut mieux que le filtre réseau soit déjà là
  le jour où l'authentification applicative change.

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

- **Moteur de classement** (spec 004), pur et sans dépendance à Flask ou SQL.
  Reproduit **196 scores et rangs sur 196** du classeur de novembre 2025, sur
  1003 réussites et 12 groupes. Validation par couleur en option par
  compétition, désactivée par défaut ; variante retenue quand elle sera activée :
  **deux couleurs pleines** (décision du 28/08).
- `GET /api/public/classement` et `/api/public/groupes` — sans authentification,
  avec cache de 5 s. Ce sont les routes de la future page spectateurs.
- **Envoi par lots** : `POST /api/v3/successes` (spec 003, IT1). Un lot n'échoue
  jamais en bloc — un dossard inconnu sur cinq n'empêche pas les quatre autres
  d'être enregistrés. Verdict par élément, et la version du catalogue voyage
  dans la réponse. Les trois routes `v2` restent en service, **inchangées**.
- `ETag` / `If-None-Match` sur le catalogue : quand rien n'a bougé, la réponse
  fait ~150 octets au lieu de 6–8 ko.
- Traçabilité des réaffectations de dossard. Avec la file d'attente à venir, une
  réussite peut arriver après que son dossard ait changé de main ; la décision du
  28/08 est de **l'accepter** — elle suit le nouveau porteur. `reussites_suspectes()`
  permet de retrouver ces cas au lieu de les laisser passer en silence.

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

- **La sonde `/health` interroge la base.** Elle répondait `"ok"` sans jamais
  l'ouvrir : quatre workers démarrés sur une base sans tables passaient pour un
  déploiement réussi, alors que chaque scan renvoyait 500. Elle répond
  désormais **503 `degraded`**, ce qui déclenche le retour arrière.
- **Verrou de schéma : un orphelin ne bloque plus les démarrages.** Un processus
  tué entre la prise et la libération laissait la ligne en base. Le délai
  d'expiration de 60 s ne suffisait pas — `RestartSec=5s` fait toujours
  redémarrer le service à l'intérieur de ce délai. La question posée n'est plus
  « le verrou est-il vieux » mais « le schéma est-il prêt ».
- `_rendre_verrou()` supprimait le verrou de n'importe qui, y compris celui,
  tout frais, du processus qui venait de le lui voler.
- **L'archive de release ne contenait pas l'application.** Le script copiait
  `climb_contest` — un nom qui n'a jamais existé — et un `|| true` avalait
  l'échec. Le premier tag portant le vrai backend aurait produit une archive
  sans une ligne de code, et gunicorn serait mort au démarrage. Une vérification
  refuse désormais de publier une archive sans application.
- Un corps JSON qui n'est pas un objet (`[1,2]`, `"x"`, `42`) donnait **500** sur
  les routes de juge. Il donne 400.
- La journalisation applicative n'écrivait nulle part : le logger racine est à
  `WARNING` sans destination, et le service ne passe aucun niveau. La ligne qui
  doit décider du passage en mode strict de la clé d'API était donc muette.

### Modifié

- Point d'entrée : `wsgi:app` via une fabrique d'application. `main.py`,
  `models.py` et `google_sheets*.py` sont remplacés.
- L'identifiant du classeur vit en base, par compétition — plus jamais en dur
  dans le code. C'était le geste le plus souvent oublié d'une édition à l'autre.

## [0.1.2] — 2026-08-28

Trois défauts de l'agent de déploiement, trouvés en jouant réellement les
scénarios d'échec de la spec 001 plutôt qu'en les supposant.

- **Moteur de classement** (spec 004), pur et sans dépendance à Flask ou SQL.
  Reproduit **196 scores et rangs sur 196** du classeur de novembre 2025, sur
  1003 réussites et 12 groupes. Validation par couleur en option par
  compétition, désactivée par défaut ; variante retenue quand elle sera activée :
  **deux couleurs pleines** (décision du 28/08).
- `GET /api/public/classement` et `/api/public/groupes` — sans authentification,
  avec cache de 5 s. Ce sont les routes de la future page spectateurs.
- **Envoi par lots** : `POST /api/v3/successes` (spec 003, IT1). Un lot n'échoue
  jamais en bloc — un dossard inconnu sur cinq n'empêche pas les quatre autres
  d'être enregistrés. Verdict par élément, et la version du catalogue voyage
  dans la réponse. Les trois routes `v2` restent en service, **inchangées**.
- `ETag` / `If-None-Match` sur le catalogue : quand rien n'a bougé, la réponse
  fait ~150 octets au lieu de 6–8 ko.
- Traçabilité des réaffectations de dossard. Avec la file d'attente à venir, une
  réussite peut arriver après que son dossard ait changé de main ; la décision du
  28/08 est de **l'accepter** — elle suit le nouveau porteur. `reussites_suspectes()`
  permet de retrouver ces cas au lieu de les laisser passer en silence.

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

- **La sonde `/health` interroge la base.** Elle répondait `"ok"` sans jamais
  l'ouvrir : quatre workers démarrés sur une base sans tables passaient pour un
  déploiement réussi, alors que chaque scan renvoyait 500. Elle répond
  désormais **503 `degraded`**, ce qui déclenche le retour arrière.
- **Verrou de schéma : un orphelin ne bloque plus les démarrages.** Un processus
  tué entre la prise et la libération laissait la ligne en base. Le délai
  d'expiration de 60 s ne suffisait pas — `RestartSec=5s` fait toujours
  redémarrer le service à l'intérieur de ce délai. La question posée n'est plus
  « le verrou est-il vieux » mais « le schéma est-il prêt ».
- `_rendre_verrou()` supprimait le verrou de n'importe qui, y compris celui,
  tout frais, du processus qui venait de le lui voler.
- **L'archive de release ne contenait pas l'application.** Le script copiait
  `climb_contest` — un nom qui n'a jamais existé — et un `|| true` avalait
  l'échec. Le premier tag portant le vrai backend aurait produit une archive
  sans une ligne de code, et gunicorn serait mort au démarrage. Une vérification
  refuse désormais de publier une archive sans application.
- Un corps JSON qui n'est pas un objet (`[1,2]`, `"x"`, `42`) donnait **500** sur
  les routes de juge. Il donne 400.
- La journalisation applicative n'écrivait nulle part : le logger racine est à
  `WARNING` sans destination, et le service ne passe aucun niveau. La ligne qui
  doit décider du passage en mode strict de la clé d'API était donc muette.

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

[Non publié]: https://github.com/computingify/climbcontest-core/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.4.1
[0.4.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.4.0
[0.3.4]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.4
[0.3.3]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.3
[0.3.2]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.2
[0.3.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.1
[0.3.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.0
[0.2.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.2.1
[0.2.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.2.0
[0.1.2]: https://github.com/computingify/climbcontest-core/releases/tag/v0.1.2
[0.1.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.1.0
