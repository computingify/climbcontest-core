# 001 — VM ClimbContest : hébergement, livraison et exploitation

## Résumé

Créer la VM `climbcontest` sur `pve01`, avec une chaîne de livraison par tirage
(release signée + changelog), une exposition HTTPS par `edge`, et un régime
d'exploitation **différent des autres VM** : elle ne tourne que pendant les
compétitions et les sessions de développement.

C'est le socle des specs suivantes : rien de ce qui concerne le backend, le
classement ou la page résultats n'est traité ici. Cette spec livre **une machine
vide, prête à recevoir des releases**.

## Pourquoi

Aujourd'hui le backend est sur Render (plan gratuit, instance qui s'endort,
aucune réponse obtenue lors de l'audit du 28/08). Le rapatrier à la maison donne
la maîtrise du déploiement, supprime la dépendance à un tiers gratuit, et
mutualise l'exposition HTTPS déjà en place sur `edge`.

## Ce qui rend cette VM différente des huit autres

| Sujet | Les autres VM | `climbcontest` |
| --- | --- | --- |
| Disponibilité | 24/7, `onboot: 1` | **éteinte par défaut**, `onboot: 0` |
| Charge | quelques requêtes/min | **25 juges + 100 spectateurs**, 250-350 req/min, et c'est normal |
| Maintenance | fenêtre 05 h 00 automatique | **préparée avant compétition**, jamais le jour J |
| Supervision | `MachineInjoignable` après 10 min | ne doit **pas** alerter quand elle est éteinte |
| CrowdSec | bannit les IP suspectes | **ne doit jamais bannir l'IP de la salle** |
| Sauvegarde | vzdump toutes les nuits | **la donnée seule**, et seulement quand il y en a |

Ces six écarts sont le cœur de la spec. Chacun, s'il est oublié, casse quelque
chose : une alerte qui hurle 350 jours par an, une fenêtre de maintenance qui
rallume la VM à 5 h du matin, ou — le pire — CrowdSec qui bannit la salle en
pleine compétition.

## Périmètre

### Inclus

1. **La VM** : VMID 110, `climbcontest`, adressage, ressources, pare-feu
   Proxmox, `onboot: 0`.
2. **Le socle applicatif** : Python, gunicorn derrière systemd, arborescence
   `releases/` + lien `current`, utilisateur de service dédié.
3. **La chaîne de livraison** : `CHANGELOG.md`, versionnage sémantique, workflow
   GitHub de release (build → test → archive `.tar.gz` + `.sha256` → publication),
   agent de tirage sur la VM (vérification d'empreinte, bascule, sonde, retour
   arrière).
4. **L'exposition** : entrée Caddy sur `edge` pour **`climbcontest.adn-dev.fr`**,
   certificat DNS-01, en-têtes de sécurité, et une **structure d'URL qui prévoit
   dès maintenant toutes les surfaces à venir** (résultats spectateurs, API
   mobile, saisie manuelle, paramétrage) — voir
   [architecture.md §5](architecture.md#5-exposition--une-porte-plusieurs-surfaces).
5. **Le nom interne** : `climbcontest.maison.adn-dev.fr` et ses alias sur le
   portail de la LXC 109, en **redirection** vers l'adresse publique — comme
   `carte.` et `guestflow.`.
6. **Les contrôles adaptés** : exclusion de `MachineInjoignable`, nouvelle alerte
   « injoignable **alors qu'elle tourne** », exemptions CrowdSec pour l'API des
   juges, absence de limite de débit sur l'API.
7. **Le cycle marche/arrêt** : commandes d'allumage et d'extinction, préparation
   avant compétition, ce que ça libère réellement.
8. **La stratégie de sauvegarde**, y compris la réponse argumentée à « est-ce
   vraiment judicieux ».

### Impacts des décisions du 28/08 sur cette spec

Trois de tes précisions changent des choix faits ici :

1. **Les participants bougent pendant la compétition** (ajouts, réaffectations de
   dossard). Cette spec ne traite pas la fonctionnalité, mais elle doit **prévoir
   la surface** : `/admin/participants` s'ajoute au plan d'URL.
2. **Republier sur le Play Store n'est pas un problème.** Mon argument « une
   seule URL de base parce qu'en changer coûte une republication » ne tient plus.
   Le choix du nom unique reste bon pour d'autres raisons (un certificat, un bloc
   Caddy, un filtrage CrowdSec par chemin), mais il n'est plus contraint.
3. **Pas de gel des déploiements le jour J** : le pipeline doit être utilisable
   sous pression. D'où une commande de déploiement immédiat et une commande de
   retour arrière manuel, en plus du retour arrière automatique.

### Explicitement exclu

- Toute évolution du code backend (specs 002 et suivantes).
- Le moteur de classement, la page résultats, la page de saisie manuelle et la
  page de paramétrage — cette spec prévoit **leur emplacement et leur
  protection**, pas leur contenu.
- La migration des données depuis Render (il n'y en a pas : rien n'y est
  persisté).
- L'arrêt du service Render, qui reste en secours jusqu'à la première
  compétition réussie sur la VM.

## Critères d'acceptation

### La machine

- [ ] VM 110 `climbcontest` démarre, `onboot: 0` vérifié par un redémarrage de
      `pve01` — la VM reste éteinte.
- [ ] Pare-feu par-VM posé sur le modèle de la 105, vérifié règle par règle
      (`grep '^|' /etc/pve/firewall/110.fw` ne renvoie rien).
- [ ] `qemu-guest-agent` installé et répondant à `qm agent 110 ping` — le piège
      de la 107 ne se reproduit pas.
- [ ] `node_exporter` répond sur `:9100` depuis `192.168.0.28` uniquement.

### La livraison

- [ ] `git tag v0.1.0 && git push origin v0.1.0` produit une release GitHub avec
      une archive et son `.sha256`.
- [ ] Le workflow **échoue** si `CHANGELOG.md` ne contient pas de section pour la
      version taguée.
- [ ] La VM installe la release seule, en moins de 3 minutes, sans intervention.
- [ ] Une archive dont l'empreinte ne correspond pas est **refusée**, et rien
      n'est installé.
- [ ] Une release qui ne répond pas à la sonde déclenche un **retour arrière
      automatique** vers la précédente, vérifié en conditions réelles.
- [ ] Les trois dernières releases restent disponibles pour un retour arrière
      manuel instantané.

### L'exposition

- [ ] `https://climbcontest.adn-dev.fr/` répond en 200 avec un certificat valide.
- [ ] `https://climbcontest.maison.adn-dev.fr` redirige vers l'adresse publique,
      et les alias (`escalade.`, `resultats.`, `saisie.`, `parametres.`) mènent
      chacun au bon chemin.
- [ ] Les cinq surfaces prévues répondent à leur chemin, chacune avec son régime
      de protection — même si leur contenu est encore vide.
- [ ] Les en-têtes de sécurité communs sont présents (`import commun`).
- [ ] `/.git/config` et `/.env` répondent **404** (`import sondes`).
- [ ] L'API des juges refuse une requête sans clé (401), l'accepte avec.
- [ ] La console d'administration exige une authentification.
- [ ] `/health` n'est **pas** joignable depuis Internet.

### La charge

Cible réelle : **~25 juges** et **plus de 100 spectateurs**, tous derrière le NAT
de la salle — donc **une seule IP publique**.

- [ ] 25 clients « juges » + 80 clients « spectateurs » en simultané pendant
      10 minutes : aucune erreur, temps de réponse médian sous 200 ms.
- [ ] Le test lancé depuis **une seule IP publique** ne déclenche **aucune**
      décision CrowdSec.
- [ ] La page résultats absorbe 300 rafraîchissements/minute sans dépasser 30 %
      de CPU — c'est le cache de 5 s qui doit faire le travail, pas la puissance.
- [ ] Le nombre de calculs de classement reste plafonné par le cache, quel que
      soit le nombre de spectateurs.

### Les contrôles

- [ ] VM éteinte pendant 24 h : **aucun mail**, aucune alerte Prometheus.
- [ ] VM allumée puis rendue muette (arrêt de gunicorn) : alerte
      `ClimbcontestInjoignableEnService` en moins de 10 minutes.
- [ ] La fenêtre de maintenance de 05 h 00 **ne rallume pas** la VM et
      **n'annule pas** la séquence des huit autres invités.
- [ ] Le chien de garde de 08 h 00 ne signale pas la VM éteinte.

### L'exploitation

- [ ] `qm start 110` puis service opérationnel en moins de 90 secondes.
- [ ] `qm shutdown 110` : arrêt propre, RAM rendue à l'hôte (vérifié sur
      `pve01`).
- [ ] Une procédure écrite « préparer la VM avant une compétition » existe et a
      été jouée une fois de bout en bout.

## Cas limites

| Situation | Comportement attendu |
| --- | --- |
| `pve01` redémarre pendant l'année | La VM **reste éteinte** |
| `pve01` redémarre **pendant** une compétition | La VM redémarre seule : `onboot` est basculé à `1` pour la journée (Q1 tranchée) |
| GitHub est injoignable au moment du tirage | L'agent échoue silencieusement, réessaie au tick suivant, la version en service n'est pas touchée |
| Une release est publiée pendant une compétition | **Elle est installée** — c'est voulu (Q2 tranchée) : Adrien doit pouvoir corriger le jour J. D'où l'importance du retour arrière automatique et d'une commande de déploiement immédiat |
| L'archive téléchargée est corrompue | Empreinte invalide → rien n'est installé, message dans le journal |
| La nouvelle release démarre mais ne répond pas | Retour arrière automatique vers la précédente |
| Le retour arrière échoue lui aussi | Le service reste arrêté, alerte, intervention manuelle — l'ancienne release est toujours sur le disque |
| Le disque de la VM se remplit | `DisqueQuiSeRemplit` s'applique normalement (elle est dans `job nodes`) |
| Internet tombe côté maison pendant une compétition | Le backend est injoignable ; c'est le mode hors-ligne de l'app juge (spec 003) qui couvre ce cas — **pas cette spec** |
| Un juge scanne 200 fois en 2 minutes | Aucun bannissement, aucune limite de débit sur l'API |
| Quelqu'un force la console d'administration | CrowdSec bannit — c'est le seul endroit où le bannissement reste actif |

## Décisions ouvertes

### Tranchées le 28/08

| # | Question | Décision |
| --- | --- | --- |
| Q1 | Rallumage automatique pendant une compétition | **Oui** — `onboot` passe à `1` pour la journée, puis revient à `0`. C'est une étape de la procédure de préparation et de la clôture |
| Q2 | Gel des déploiements pendant une compétition | **Non** — Adrien doit pouvoir corriger le jour J. Le pipeline reste actif, avec retour arrière automatique et une commande de déploiement immédiat |
| Q3 | Nom de domaine | **`climbcontest.adn-dev.fr`**, une seule entrée, les surfaces se distinguent par le chemin |
| Q4 | Adresse `192.168.0.32` | **Validée** — la plage DHCP de la Freebox va de `.40` à `.200`, le statique est libre en dessous |
| Q5 | Sauvegarde | **Pas de copie périodique pendant la compétition** — jugée inutile. Réduite à un instantané avant, une archive après. Voir [architecture.md §8](architecture.md#8-sauvegarde--la-version-revue) |
| Q6 | Base mono ou multi-compétition | **Multi-compétition** — archives consultables depuis `/admin/archives`. Toute donnée porte une référence d'édition ; un dossard n'est unique qu'au sein d'une compétition |
| Q7 | Écriture miroir vers le classeur | **Conservée pour le moment** — la redondance gratuite des données du jour J reste en place |

### Encore ouvertes

*Aucune.* Toutes les questions de cette spec sont tranchées.
