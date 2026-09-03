# Spec 031 — Mettre à jour le serveur depuis la console

> **Statut : maquette validée par Adrien le 03/09/2026**, puis code écrit dans la
> foulée sur sa demande (« parfait implémente »). La porte 2 a été franchie sur
> la **maquette**, pas sur ce document : il est écrit après le code, comme la
> spec 032. Ce qu'il décrit est ce qui a été livré, pas une intention.
>
> Maquette : [`maquettes/carte-version.html`](maquettes/carte-version.html).

## 1. Le fait générateur

La VM 110 a cessé d'être intermittente le 03/09/2026 : elle tourne désormais en
permanence (`homelab/vm110-climbcontest/README.md`). Son minuteur de
déploiement, lui, n'a pas changé — il interroge `api.github.com` **toutes les
deux minutes**.

Deux conséquences, apparues le jour même :

1. **Le quota.** 30 requêtes par heure, en continu, sur un plafond **anonyme de
   60 par heure et par adresse IP publique** — celle de toute la maison. Le
   30/08, cinq déploiements d'affilée avaient déjà échoué pour dépassement, et
   l'échec ne se lisait **que dans le journal** : rien ne l'a signalé.
2. **Le déploiement non demandé.** Publier un tag mettait en production en moins
   de deux minutes. C'était acceptable quand la VM ne s'allumait que pour une
   compétition ; ça ne l'est plus quand elle est toujours là.

Décision d'Adrien : supprimer le mécanisme automatique, et le remplacer par un
bouton dans la console.

## 2. Ce qu'on fait

### F1 — Le minuteur disparaît

`climbcontest-deploy.timer` est retiré : de la VM, de `deployment/install.sh` et
du dépôt. `climbcontest-deploy.service` **reste** — c'est lui qu'on déclenche.
Le script `/usr/local/bin/climbcontest-deploy` n'est pas touché : il garde son
verrou, sa vérification d'empreinte, sa sonde `/health` et son retour arrière.

### F2 — Une vérification par jour, et déclenchée par la console

`GET /admin/maj` interroge GitHub **si la dernière vérification date de plus de
24 h**, et range le résultat dans la table `reglage`. Il n'y a aucun minuteur :
la console est le seul appelant. Personne n'ouvre la console, personne ne
consomme le quota.

Coût : **1 requête sur 60 par heure**, contre 30 auparavant.

### F3 — La carte « Version du serveur », dans Réglages

Réservée aux administrateurs, comme « Créer un compte ». Elle montre la version
en service, la date de la dernière vérification, et un verdict d'une ligne :

| Situation | Ce qui s'affiche |
| --- | --- |
| Rien de neuf | **Version à jour** |
| Version disponible | *v0.17.0 disponible* + le changelog + « Installer v0.17.0 » |
| Compétition en cours | *Compétition en cours (…) — installation bloquée*, bouton grisé |
| Installation lancée | *Installation de v0.17.0 en cours…* |
| Installation échouée | *Échec — revenu en v0.16.0* |
| GitHub muet | *GitHub injoignable — quota atteint* |

Le changelog affiché est le **corps de la release GitHub**, qui est déjà la
section du `CHANGELOG` : `scripts/extract_changelog.py` l'y place et le workflow
de release échoue s'il ne la trouve pas. Il n'y a rien à reconstituer.

### F4 — Une pastille dans le bandeau

Quand une version est disponible, une pastille ocre paraît dans la barre du
haut, visible depuis n'importe quel écran. Elle **mène aux Réglages** et ne fait
que ça : une pastille qui installerait d'un clic serait un bouton de mise en
production dans une barre de navigation.

Sa forme est celle des pastilles de Sowel — pilule, 0,75 rem semi-gras, icône de
14 px, fond au ton à 12 % — pour que les deux consoles de la maison signalent la
même chose de la même façon. Sa **teinte** est l'ocre d'ici : Sowel colore ses
mises à jour en rouge, ce qui dirait « panne » sur un écran où rien n'est cassé.

### F5 — Une compétition en cours bloque, sans exception

`Competition.statut == "en_cours"` grise le bouton et fait répondre **409** à la
route. Redémarrer coupe vingt-cinq téléphones au milieu des scans.

Le geste de secours reste la ligne de commande —
`sudo systemctl start climbcontest-deploy.service` — où l'on sait ce qu'on fait.
Il n'y a **pas** de contournement dans l'interface : c'était le choix entre
prévenir et bloquer, Adrien a tranché pour bloquer le 03/09.

## 3. Critères d'acceptation

- [x] `climbcontest-deploy.timer` n'existe plus, ni sur la VM ni dans le dépôt
- [x] Trois consultations d'affilée de la console ne produisent **qu'une**
      requête GitHub ; le lendemain, une deuxième
- [x] Le bouton « Vérifier » force l'appel sans attendre l'échéance
- [x] Une version plus récente affiche son changelog
- [x] Une compétition `en_cours` grise le bouton et fait répondre 409
- [x] Une compétition `preparation` ne bloque pas
- [x] L'installation ~~part avec `--no-block`~~ **dépose une demande** et rend
      la main immédiatement — le critère est tenu, par un autre chemin
      (2026-09-03, voir `architecture.md` § 4)
- [x] L'issue (réussie / échouée) se lit, et cesse d'être annoncée passé 10 min
- [x] Les trois routes répondent 403 à un organisateur, 401 sans session
- [x] Le quota GitHub est nommé en toutes lettres quand il est atteint

## 4. Cas limites

**Le processus qui meurt en répondant.** L'agent redémarre l'application,
c'est-à-dire le processus qui traite la requête d'installation. D'où le
non-blocage — hier `--no-block`, aujourd'hui l'écriture d'un fichier qui rend la
main aussitôt : attendre la fin du service, ce serait attendre sa propre mort.
Côté console, les requêtes échouent une quinzaine de secondes — c'est le
symptôme attendu, pas une erreur à afficher.

**Quatre workers, une vérification.** Les quatre workers gunicorn peuvent voir
« c'est dû » à la même seconde. L'horodatage est écrit **avant** l'appel réseau.
Il reste une fenêtre de quelques centaines de millisecondes où deux requêtes
partent : 2 sur 60, une fois par jour. Un verrou à deux états aurait un mode
d'échec silencieux où **plus aucune** vérification ne se ferait — bien pire.

**GitHub muet ne doit rien effacer.** Une version trouvée hier l'est toujours
aujourd'hui : l'erreur s'ajoute à ce qu'on savait, elle ne le remplace pas.

**Le changelog vient d'ailleurs.** C'est le corps d'une release, donc du contenu
qu'on ne fabrique pas. Il est posé avec `textContent`, jamais en HTML.

**La version affichée peut être périmée.** Si une release plus récente paraît
entre le chargement de la console et le clic, l'installation est refusée plutôt
que d'installer autre chose que ce qui était affiché.

## 5. Hors périmètre

- **Le jeton GitHub.** Poser un PAT en lecture dans
  `shared/secrets/github-token` ferait passer le quota à 5 000/h. Le script et
  ce module le lisent déjà s'il existe ; le créer appartient à Adrien.
- **Le rattrapage automatique.** Écarté explicitement : si personne n'ouvre la
  console, rien ne se met à jour. Conséquence assumée — une release de sécurité
  attendra un clic.
- **La version des téléphones.** C'est la spec 030 (`versions-visibles`), en
  cours ailleurs. Les deux se croisent dans `admin.html` : à fusionner à blanc
  avant merge.
