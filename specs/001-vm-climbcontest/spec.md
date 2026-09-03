# 001 — VM ClimbContest : hébergement, livraison et exploitation

## Résumé

Créer la VM `climbcontest` sur `pve01`, avec une chaîne de livraison par tirage
(release signée + changelog), une exposition HTTPS par `edge`, et les contrôles qu'exige une machine qui
prend 25 juges et 100 spectateurs en rafale une journée par an.

C'est le socle des specs suivantes : rien de ce qui concerne le backend, le
classement ou la page résultats n'est traité ici. Cette spec livre **une machine
vide, prête à recevoir des releases**.

## Pourquoi

Aujourd'hui le backend est sur Render (plan gratuit, instance qui s'endort,
aucune réponse obtenue lors de l'audit du 28/08). Le rapatrier à la maison donne
la maîtrise du déploiement, supprime la dépendance à un tiers gratuit, et
mutualise l'exposition HTTPS déjà en place sur `edge`.

## Ce qui rend cette VM différente des neuf autres

| Sujet | Les autres VM | `climbcontest` |
| --- | --- | --- |
| Charge | quelques requêtes/min | **25 juges + 100 spectateurs**, 250-350 req/min, et c'est normal |
| Maintenance | fenêtre 05 h 00 automatique | la même — mais **jamais la veille ni le matin** d'une compétition |
| CrowdSec | bannit les IP suspectes | **ne doit jamais bannir l'IP de la salle** |
| Sauvegarde | vzdump toutes les nuits | la même, **plus** un instantané avant la compétition et une archive après |

Le plus coûteux de ces écarts, s'il est oublié, c'est CrowdSec : 25 juges et
100 spectateurs derrière un seul NAT ressemblent à une attaque, et un
bannissement coupe la salle entière en pleine compétition.

Tout le reste est celui du parc. **Ça n'a pas toujours été le cas** : cette VM a
été conçue intermittente, allumée pour les compétitions seulement. Ce régime a
été abandonné le 03/09/2026 — voir « Historique » en fin de document.

## Périmètre

### Inclus

1. **La VM** : VMID 110, `climbcontest`, adressage, ressources, pare-feu
   Proxmox, `onboot: 1`.
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
6. **Les contrôles adaptés** : exemptions CrowdSec pour l'API des juges et
   absence de limite de débit sur l'API. La supervision, elle, est celle du
   parc : `MachineInjoignable` s'applique sans exception.
7. **La préparation d'une compétition** : mise à jour quelques jours avant,
   instantané `avant-compet`, pense-bête du jour J, clôture.
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

- [x] VM 110 `climbcontest` démarre, `onboot: 1` vérifié par un redémarrage de
      `pve01` — la VM revient seule, comme les neuf autres invités.
- [ ] Pare-feu par-VM posé sur le modèle de la 105, vérifié règle par règle
      (`grep '^|' /etc/pve/firewall/110.fw` ne renvoie rien).
- [ ] `qemu-guest-agent` installé et répondant à `qm agent 110 ping` — le piège
      de la 107 ne se reproduit pas.
- [ ] `node_exporter` répond sur `:9100` depuis `192.168.0.28` uniquement.

### La livraison

- [x] `git tag v0.1.0 && git push origin v0.1.0` produit une release GitHub avec
      une archive et son `.sha256`.
- [ ] Le workflow **échoue** si `CHANGELOG.md` ne contient pas de section pour la
      version taguée.
- [x] La VM installe la release seule, en moins de 3 minutes, sans intervention.
      → **13 secondes** pour la `v0.2.0` (17:24:55 → 17:25:08), le déclencheur
      passant toutes les 2 minutes. Vérifié deux fois le 28/08
- [ ] Une archive dont l'empreinte ne correspond pas est **refusée**, et rien
      n'est installé.
- [ ] Une release qui ne répond pas à la sonde déclenche un **retour arrière
      automatique** vers la précédente, vérifié en conditions réelles.
- [x] Les trois dernières releases restent disponibles pour un retour arrière
      → `v0.1.2`, `v0.2.0`, `v0.2.1` présentes après trois déploiements
      manuel instantané.

### L'exposition

- [x] `https://climbcontest.adn-dev.fr/` répond en 200 avec un certificat valide.
      → vérifié le 28/08, `ssl_verify_result=0`
- [ ] `https://climbcontest.maison.adn-dev.fr` redirige vers l'adresse publique,
      et les alias (`escalade.`, `resultats.`, `saisie.`, `parametres.`) mènent
      chacun au bon chemin.
- [ ] Les cinq surfaces prévues répondent à leur chemin, chacune avec son régime
      de protection — même si leur contenu est encore vide.
- [x] Les en-têtes de sécurité communs sont présents (`import commun`).
      → `strict-transport-security`, `x-content-type-options`, `x-frame-options`,
      `referrer-policy` vérifiés en réponse réelle
- [x] `/.git/config` et `/.env` répondent **404** (`import sondes`). → vérifié
- [x] L'API des juges refuse une requête sans clé (401), l'accepte avec.
      **Satisfait le 29/08 par la spec 012.**

      Le critère est resté ouvert un jour, et à dessein : l'application
      `v3.1.4` du Play Store n'envoie aucune clé, et la casser aurait été pire
      que le risque couvert. Le régime était donc *toléré*.

      La spec 012 a fait les deux moitiés en même temps : l'application envoie
      désormais sa clé, et le régime **strict est le défaut**. Le mode toléré
      reste atteignable par `CLIMBCONTEST_API_KEY_STRICTE=0` — c'est ce que le
      plan de repli exige en premier, puisque le gel `V3.1.4` n'envoie toujours
      rien.
- [x] La console d'administration exige une authentification.
      → **Était faux jusqu'au 28/08.** `GET /admin/import/rapport` répondait `200`
      depuis Internet : les routes portaient le garde-fou de clé en mode *toléré*,
      qui accepte une requête sans clé. Corrigé aux deux niveaux — clé stricte
      côté application (`v0.2.1`), et `/admin/*` hors du LAN côté Caddy.
      Vérifié : `401` sans clé, `200` avec
- [ ] `/health` n'est **pas** joignable depuis Internet.
      Règle vérifiée dans la configuration **chargée** par Caddy (filtre
      `remote_ip` sur `192.168.0.0/24` et l'IP publique, `404` sinon). La
      vérification de bout en bout demande une IP **non listée** — c'est le test
      en 5G qu'Adrien veut faire. Non cochée tant qu'il n'a pas eu lieu.

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

- [x] VM rendue muette (arrêt de gunicorn) : `MachineInjoignable` en moins de
      10 minutes, comme pour n'importe quel invité du parc.
- [x] La fenêtre de maintenance de 05 h 00 la met à jour **en tête de séquence**
      — elle est le canari du parc — sans annuler la séquence des neuf autres.
- [x] Le chien de garde de 08 h 00 réclame sa sauvegarde PBS du jour, et la
      trouve : elle est dans `backup-nightly`.

### L'exploitation

- [x] `qm start 110` puis service opérationnel en moins de 90 secondes —
      vérifié au redémarrage de `pve01` du 03/09.
- [x] Une procédure écrite « préparer la VM avant une compétition » existe et a
      été jouée une fois de bout en bout — voir
      [runbook-competition.md](../../docs/runbook-competition.md).

## Cas limites

| Situation | Comportement attendu |
| --- | --- |
| `pve01` redémarre, un jour quelconque ou en pleine compétition | La VM revient seule (`onboot: 1`) |
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
| Q1 | Rallumage automatique pendant une compétition | **Oui** — à l'époque par une bascule d'`onboot` le jour J. **Sans objet depuis le 03/09/2026** : `onboot` vaut `1` en permanence |
| Q2 | Gel des déploiements pendant une compétition | **Non** — Adrien doit pouvoir corriger le jour J. Le pipeline reste actif, avec retour arrière automatique et une commande de déploiement immédiat |
| Q3 | Nom de domaine | **`climbcontest.adn-dev.fr`**, une seule entrée, les surfaces se distinguent par le chemin |
| Q4 | Adresse `192.168.0.32` | **Validée** — la plage DHCP de la Freebox va de `.40` à `.200`, le statique est libre en dessous |
| Q5 | Sauvegarde | **Pas de copie périodique pendant la compétition** — jugée inutile. Réduite à un instantané avant, une archive après. Voir [architecture.md §8](architecture.md#8-sauvegarde--la-version-revue) |
| Q6 | Base mono ou multi-compétition | **Multi-compétition** — archives consultables depuis `/admin/archives`. Toute donnée porte une référence d'édition ; un dossard n'est unique qu'au sein d'une compétition |
| Q7 | Écriture miroir vers le classeur | **Conservée pour le moment** — la redondance gratuite des données du jour J reste en place |

### Encore ouvertes

*Aucune.* Toutes les questions de cette spec sont tranchées.

## Historique — ce que cette spec ne dit plus

**Le régime intermittent a été abandonné le 03/09/2026.** La VM avait été
conçue pour ne tourner que pendant les compétitions : `onboot: 0`, hors
d'`ADN_GUESTS`, hors du job de sauvegarde, exclue de `MachineInjoignable` par
une étiquette `intermittent: 'oui'`, et couverte par une alerte dédiée qui ne se
déclenchait que si l'hyperviseur la disait démarrée.

Déclencheur : la mise à jour du noyau de `pve01` a redémarré l'hyperviseur le
03/09 à 05 h 04. Les neuf autres invités sont revenus seuls, pas elle — et rien
ne l'a signalé, puisque c'est ce que la conception demandait.

Le raisonnement en faveur de l'intermittence **a été retiré de cette spec, pas
seulement signalé caduc** : laissé en place, il se relit comme un argumentaire
complet, et se ré-applique. Il reste dans l'historique git de ce dossier. L'état
en service est décrit dans `homelab/vm110-climbcontest/README.md`, qui porte
aussi les **cinq réglages qui ne se déplacent jamais séparément** (`onboot`,
`ADN_GUESTS`, le job `backup-nightly`, l'étiquette Prometheus, la sonde).

Deux autres décisions de cette spec ont été défaites depuis :

- **Q5** — « pas de copie périodique pendant la compétition ». La base est
  aujourd'hui recopiée toutes les dix minutes dans
  `/opt/climbcontest/shared/sauvegardes/`, les 24 dernières conservées.
- **L'agent de tirage toutes les 2 minutes** — retiré le 03/09/2026 par la
  [spec 031](../031-deploiement-depuis-la-console/) : une release ne s'installe
  plus qu'en cliquant dans la console, ou par
  `sudo systemctl start climbcontest-deploy.service`.
