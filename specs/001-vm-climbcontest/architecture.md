# Architecture : 001 — VM ClimbContest

Références : `~/.claude/notes/migration-proxmox/` et le dépôt `homelab`.
Tout ce qui suit s'aligne sur les conventions déjà en place — pare-feu par-VM,
Caddy sur `edge`, supervision sur la 108, sauvegarde PBS sur la 107.

---

## 1. La machine

| Paramètre | Valeur | Pourquoi |
| --- | --- | --- |
| VMID | **110** | premier libre après la 109 |
| Nom | `climbcontest` | |
| IP | **192.168.0.32/24** | premier libre après `.31` ; la plage DHCP Freebox va de `.40` à `.200` — **validé le 28/08** |
| vCPU | **4** | l'hôte a 20 threads ; la pointe d'une compétition dure quelques heures, le reste du temps ce CPU ne coûte rien |
| RAM | **4 Go** | |
| Disque | **24 Go** sur `local-lvm` (thin, `discard=on`) | ~4 Go réellement occupés |
| `onboot` | **1** | comme les neuf autres invités : elle revient seule après une coupure |
| `agent` | `enabled=1` **et paquet installé** | le piège de la 107 (gel du 2026-08-26) |
| OS | Debian 13, cloud-init, compte `adrien` | comme la 105 |
| `tags` | `climbcontest` | |

La config en service est `homelab/pve01/vm-configs/110.conf`.

## 2. Pare-feu (`110.fw`)

Calqué sur la 105, avec une entrée de plus pour le service.

```
[OPTIONS]
enable: 1
policy_in: DROP
policy_out: DROP
ndp: 1
dhcp: 0

[RULES]
IN ACCEPT -source 192.168.0.28 -p tcp -dport 9100  # supervision
IN ACCEPT -source 192.168.0.22 -p tcp -dport 5007  # Caddy (edge) uniquement
IN ACCEPT -source 192.168.0.0/24 -p tcp -dport 22  # SSH admin LAN
IN ACCEPT -source 192.168.0.0/24 -p icmp
OUT ACCEPT -dest 192.168.0.254 -p udp -dport 53
OUT ACCEPT -dest 192.168.0.254 -p tcp -dport 53
OUT ACCEPT -p udp -dport 123                       # NTP
OUT DROP -dest 192.168.0.0/24                      # pve01 / NAS / MQTT / autres VM
OUT DROP -dest 10.0.0.0/8
OUT DROP -dest 172.16.0.0/12
OUT ACCEPT                                          # Internet : GitHub + API Google Sheets
```

Différence avec la 105 : le port applicatif n'est ouvert que depuis **`edge`**,
pas depuis tout le LAN. Rien n'a besoin d'attaquer le backend en direct.

> ⚠ Piège connu : `pvesh create …/firewall/rules` crée la règle **désactivée**.
> Passer `--enable 1` et contrôler avec `grep '^|' /etc/pve/firewall/110.fw`.

## 3. Le socle applicatif

```
/opt/climbcontest/
├── releases/
│   ├── v1.0.0/          ← archive extraite
│   ├── v1.0.1/
│   └── v1.1.0/          ← 3 conservées
├── current -> releases/v1.1.0      (lien symbolique — la bascule)
├── shared/
│   ├── data/            ← base SQLite, JAMAIS dans une release
│   ├── secrets/         ← token Google, clé d'API juges, secret de session (0600)
│   └── venv/            ← environnement Python
└── .deployed-tag
```

- Utilisateur de service **`climbcontest`**, sans shell de connexion.
- `climbcontest.service` (systemd) : gunicorn, `WorkingDirectory=/opt/climbcontest/current`,
  `Restart=on-failure`, journalisation `journald`.
- Écoute sur **127.0.0.1:5007** ? Non — sur `0.0.0.0:5007`, filtré par le
  pare-feu Proxmox. Cohérent avec la 105 (solio-map écoute sur 4010).

**Pas de pm2.** `guestflow` et `soliomap` sont en node/pm2 ; ici c'est du Python,
et systemd fait le travail sans pièce mobile supplémentaire.

### Dimensionnement gunicorn

Cible : plusieurs dizaines de connexions simultanées, chacune très courte.

```
gunicorn --workers 4 --threads 4 --worker-class gthread \
         --timeout 30 --graceful-timeout 30 --keep-alive 65 \
         --bind 0.0.0.0:5007 wsgi:app
```

- **4 workers × 4 threads = 16 requêtes en parallèle**, pour une pointe estimée à
  **250-350 req/min** (~5 req/s) — voir
  [contraintes-metier.md §3 bis](../../docs/contraintes-metier.md#3-bis-combien-de-monde-vraiment).
  Le trafic est dominé par les **spectateurs**, pas par les juges.
- `--keep-alive 65` : les téléphones réutilisent leur connexion, ce qui supprime
  la poignée de main TLS à chaque scan.
- ⚠ **Plusieurs workers = plusieurs processus.** Le risque R1 de l'état des lieux
  (base effacée à l'import du module) devient mortel ici. La spec 002 devra
  poser l'initialisation dans un point d'entrée unique.

## 4. La chaîne de livraison

Modèle **par tirage**, décision 16 du dossier de migration, adaptée à Python.
Aucun code tiers ne s'exécute sur la VM : pas de runner GitHub.

```
  Poste d'Adrien              GitHub (runner jetable)            VM 110
  ──────────────              ───────────────────────            ──────
  scripts/release.sh
    ├─ bump version
    ├─ vérifie CHANGELOG
    ├─ git tag vX.Y.Z
    └─ git push --tags  ────►  release.yml
                                 ├─ tests pytest
                                 ├─ vérifie la section
                                 │   CHANGELOG (sinon ÉCHEC)
                                 ├─ construit app-vX.Y.Z.tar.gz
                                 ├─ calcule le .sha256
                                 └─ publie la Release      ◄──── timer 2 min
                                     corps = extrait du            │
                                     CHANGELOG                     ▼
                                                          climbcontest-deploy
                                                            1. dernière release ?
                                                            2. télécharge .tar.gz + .sha256
                                                            3. VÉRIFIE L'EMPREINTE
                                                            4. extrait dans releases/vX.Y.Z
                                                            5. pip install dans le venv
                                                            6. bascule le lien current
                                                            7. systemctl restart
                                                            8. sonde /health
                                                            9. KO ⇒ RETOUR ARRIÈRE
```

### Le changelog est contraignant, pas décoratif

`CHANGELOG.md` au format Keep a Changelog, en français :

```markdown
## [1.2.0] — 2026-09-15

### Ajouté
- Page de saisie manuelle des réussites (spec 005)

### Corrigé
- La base n'est plus effacée au démarrage de chaque worker (R1)
```

Le workflow `release.yml` **échoue avant de construire quoi que ce soit** si la
section `## [X.Y.Z]` n'existe pas. C'est la même contrainte que le
`verify-release-notes` de Sowel : sans elle, le changelog dérive en deux
releases.

Le corps de la Release GitHub est cet extrait. On lit donc l'historique depuis
GitHub sans ouvrir le dépôt.

### Versionnage

Sémantique. `MAJOR` sur rupture du contrat d'API avec l'app juge (elle est
déployée sur des téléphones qu'on ne met pas à jour le jour J), `MINOR` sur
fonctionnalité, `PATCH` sur correction.

### L'agent de tirage

`/usr/local/bin/climbcontest-deploy`, unité systemd déclenchée **à la demande**,
utilisateur `climbcontest`. Le minuteur (`OnBootSec=1min`,
`OnUnitActiveSec=2min`) a été **retiré le 03/09/2026** par la
[spec 031](../031-deploiement-depuis-la-console/) : il consommait 30 requêtes/h
sur un quota GitHub anonyme de 60 partagé par toute la maison, et installait
sans qu'on l'ait demandé.

Directement dérivé de `solio-map-deploy`, **avec ses deux bugs déjà corrigés** :

1. extraction des URL d'assets avec `awk '$1 ~ /\.tar\.gz$/'` (ancré sur le nom,
   pas sur la fin de ligne) ;
2. téléchargement avec **un seul** en-tête `Accept: application/octet-stream`,
   sans passer par le helper `api()`.

**Aucun jeton n'est nécessaire.** Le dépôt `computingify/climbcontest-core` est
**public** : les assets d'une release publique se téléchargent sans
authentification. C'est un écart favorable avec solio-map, dont le dépôt est privé
et qui doit donc porter un PAT sur la machine.

Conséquence : **un secret de moins sur la VM**, et une pièce de moins à faire
tourner. Si le dépôt devenait privé un jour, il faudrait poser un PAT à portée
fine en lecture seule dans `/opt/climbcontest/shared/secrets/github-token` (0600) —
le script doit donc gérer les deux cas : jeton présent, il l'utilise ; jeton
absent, il tire en anonyme.

Différences avec solio-map :
- `pip install -r requirements.txt` dans le venv partagé avant la bascule ;
- `systemctl restart climbcontest` au lieu de `pm2 reload` ;
- sonde sur `/health` (à créer dans la spec 002), pas sur `/`.

## 5. Exposition — une porte, plusieurs surfaces

**Un seul nom public : `climbcontest.adn-dev.fr`.** Un seul certificat, un seul
bloc Caddy, une seule URL de base pour l'app mobile. Les surfaces se distinguent
par le **chemin**, ce qui permet de leur appliquer des régimes différents —
authentification, cache, exemption CrowdSec — sans multiplier les sous-domaines.

### Le plan d'URL, prévu dès maintenant

| Chemin | Surface | Qui | Régime |
| --- | --- | --- | --- |
| `/` | **Page résultats** — écran de la salle et téléphones des spectateurs | tout le monde | public, cache 5 s, aucune limite de débit |
| `/api/public/*` | Données du classement en JSON (ce que consomme la page) | tout le monde | public, cache 5 s, **exempt CrowdSec** |
| `/api/v2/contest/*` | **API de l'app juge** — scans et envoi des réussites | app mobile | clé d'API, **aucune limite de débit**, **exempt CrowdSec** |
| `/api/v2/catalog` | Catalogue téléchargé au démarrage de l'app (spec 003) | app mobile | clé d'API |
| `/admin/` | **Tableau de bord** — état de la compétition, inscriptions HelloAsso en attente de traitement, regardable en continu | organisateurs | **session + rôles**, CrowdSec **actif** |
| `/admin/login` | Connexion | tout le monde | CrowdSec **actif** — c'est la seule surface qui mérite un bannissement |
| `/admin/participants` | **Ajout de participant et réaffectation de dossard, en cours de compétition** | organisateurs | authentification, journalisée |
| `/admin/saisie` | **Saisie manuelle** des réussites | organisateurs | authentification, journalisée |
| `/admin/parametres` | **Paramétrage de la compétition** — dont la validation par couleur | organisateurs | authentification, journalisée |
| `/admin/classeur` | **Connexion au classeur Google et test d'accès** | organisateurs | authentification |
| `/admin/inscriptions` | **Import HelloAsso**, file des inscriptions à traiter (spec 008) | organisateurs | authentification |
| `/admin/impression` | **Dossards à imprimer** — en lot ou à l'unité | organisateurs | authentification |
| `/admin/archives` | **Compétitions passées** et leurs résultats | organisateurs, lecture | authentification |
| `/admin/utilisateurs` | Comptes et rôles | admin | authentification, rôle `admin` |
| `/health` | Sonde | `edge` et LAN seulement | **bloqué depuis Internet** |

Les surfaces d'administration correspondent à tes décisions du 28/08 : validation
par couleur **en option par compétition**, saisie manuelle, paramétrage incluant
la connexion au classeur, **gestion des participants à chaud** et **import
HelloAsso**. Cette spec pose leur emplacement, leur protection et leur traitement
par CrowdSec — **leur contenu est le sujet des specs 005 et 008**.

L'objectif de fond, énoncé le 28/08 : **la page de paramétrage doit finir par
remplacer le classeur Google.** Le plan d'URL est donc taillé pour accueillir
tout ce que fait aujourd'hui le classeur, pas seulement ce dont le backend a
besoin.

### Pourquoi un seul nom plutôt qu'un sous-domaine par surface

- Un seul certificat à renouveler, un seul enregistrement DNS.
- L'app mobile a **une** URL de base, ce qui simplifie sa configuration. (Ce
  n'est plus un argument de rigidité : Adrien a confirmé le 28/08 que republier
  sur le Play Store ne pose pas de problème et que l'app va évoluer.)
- CrowdSec filtre déjà par chemin (§6.1) : la granularité est la même.
- Le spectateur tape ou scanne une adresse courte qui mène directement aux
  résultats.

Si un jour la console doit disparaître complètement de la surface publique, un
second nom reste possible sans rien casser — les chemins ne changeraient pas.

### Caddyfile (à ajouter sur `edge`)

```caddy
# --- ClimbContest (VM 110, 192.168.0.32)
# Une seule entree, plusieurs surfaces distinguees par le chemin.
# Le detail des regimes est dans specs/001-vm-climbcontest/architecture.md
climbcontest.adn-dev.fr {
	import commun
	import sondes

	# La sonde de sante ne sort pas du LAN.
	@sante path /health
	handle @sante {
		@interne remote_ip 192.168.0.0/24
		handle @interne {
			reverse_proxy 192.168.0.32:5007
		}
		respond 404
	}

	# Page resultats et donnees publiques : cache court.
	# ~60 spectateurs qui rafraichissent toutes les 15 s font ~240 req/min ;
	# avec ce cache, le classement est calcule au plus 12 fois par minute.
	# C'est la piece maitresse du dimensionnement, pas un confort.
	@public path / /resultats /api/public/*
	header @public Cache-Control "public, max-age=5"

	handle {
		reverse_proxy 192.168.0.32:5007
	}
}
```

Certificat Let's Encrypt en DNS-01 Cloudflare via l'`acme_dns` **global**,
exactement comme guestFlow et les quatre autres : **aucun réglage TLS propre à ce
site**. Un contournement (résolveurs IPv4 forcés) avait été posé le temps de
diagnostiquer, puis retiré une fois la vraie cause corrigée — le DNS sortant
d'`edge` était bloqué depuis le durcissement du 2026-08-24, ce qui aurait aussi
fait échouer le renouvellement des cinq certificats de production vers le
18 octobre. Un enregistrement `climbcontest` à créer dans la zone
`adn-dev.fr`, en **DNS uniquement** (non proxifié), comme les autres.

### Deux mécanismes d'authentification, pas un

Le découpage reprend celui de **guestFlow**, qui a exactement cette forme :

| Middleware guestFlow | Ici | Protège |
| --- | --- | --- |
| `requirePublicApiKey` | clé d'API en en-tête | `/api/v2/contest/*` — l'app juge |
| `requireAuth` (session) + `enforceRoleAccess` (liste blanche par rôle, fail-closed) | session + rôles | `/admin/*` — la console |

La gestion des comptes et des rôles est le sujet de la spec 005 ; cette spec pose
seulement la **séparation des deux surfaces** et leur traitement par CrowdSec.

### Pourquoi la console d'administration reste publique

Le résolveur interne de la LXC 109 sert les noms privés, et la consigne générale
est de ne pas exposer ce qui peut rester en LAN. Mais **les organisateurs sont à
la salle, pas sur ton LAN** : une console joignable seulement en interne serait
inutilisable le jour J, précisément quand on en a besoin.

Elle reste donc publique, protégée par authentification et par CrowdSec —
exactement le raisonnement déjà tenu pour la console de solio-map (note du
2026-08-25 dans `adn-rules.yml`).

## 5 bis. Le nom interne — `climbcontest.maison.adn-dev.fr`

Le service étant public, la règle du portail (note du 2026-08-27) s'applique :
**une redirection, jamais un proxy**. Le navigateur part droit vers `edge` par le
NAT retourné de la Freebox, et aucune règle de pare-feu n'est nécessaire.

À ajouter au Caddyfile de la LXC 109 :

| Nom (+ alias) | Mène à |
| --- | --- |
| `climbcontest.` · `escalade.` · `contest.` | `https://climbcontest.adn-dev.fr` |
| `resultats.` · `classement.` | `https://climbcontest.adn-dev.fr/` |
| `saisie.` | `https://climbcontest.adn-dev.fr/admin/saisie` |
| `parametres.` · `climbcontest-admin.` | `https://climbcontest.adn-dev.fr/admin` |

Même découpage que `carte.` / `carte-admin.` : le nom du service mène au service,
le nom de l'outil mène à l'outil. La page d'accueil `maison.adn-dev.fr` doit
lister ClimbContest avec les autres.

*(La réserve d'origine — « un nom interne qui pointe vers un service éteint 350
jours par an affiche une erreur de connexion la plupart du temps » — est sans
objet depuis le 03/09/2026 : la VM tourne en permanence.)*

## 6. Les contrôles adaptés

### 6.1 CrowdSec — le risque numéro un

**Le scénario à éviter absolument** : **25 juges et plus de 100 spectateurs**
derrière le **NAT de la salle** partagent une seule IP publique. Pour CrowdSec,
c'est une IP qui envoie 250 à 350 requêtes par minute pendant des heures. Un
débordement de seau, et **la salle entière est bannie au pare-feu, en pleine
compétition**.

Trois mesures, dans cet ordre :

1. **Exempter les chemins de l'API et de la page résultats.** Une whitelist
   CrowdSec par expression, sur le modèle de `crowdsec-whitelist-adn.yaml` déjà
   présent sur la 108 :

   ```yaml
   name: adn/climbcontest-api
   description: "L'API des juges et la page resultats ne declenchent aucun scenario"
   whitelist:
     reason: "trafic normal de competition : une salle entiere derriere un seul NAT"
     expression:
       - evt.Meta.http_path startsWith '/api/v2/contest/'
       - evt.Meta.http_path startsWith '/api/public/'
   ```

2. **Garder CrowdSec actif sur `/admin/*`.** C'est la seule surface qui mérite un
   bannissement, et la seule où un bruteforce a du sens.

3. **Une commande de déblocage d'urgence, écrite dans le runbook du jour J** :

   ```bash
   ssh adrien@192.168.0.22 'sudo cscli decisions list'
   ssh adrien@192.168.0.22 'sudo cscli decisions delete --ip <IP-de-la-salle>'
   ```

> ⚠ `BruteforceSurUneAuthentification` compte les 401 sur **tous** les hôtes
> derrière Caddy. L'API des juges répondant 401 sans clé, un déploiement d'app
> mal configuré pourrait la faire déborder. D'où l'exemption par chemin plutôt
> que par hôte.

### 6.2 Aucune limite de débit applicative

Pas de rate limiting dans l'application ni dans Caddy sur l'API. Le raisonnement
tenu pour solio-map (« un délai applicatif viderait le seau de CrowdSec plus vite
qu'un attaquant ne le remplit ») ne s'applique pas ici : le trafic des juges est
légitime, il faut qu'il passe. La protection de l'API est la **clé d'API**, pas
le débit.

### 6.3 Prometheus — les règles du parc, sans exception

`MachineInjoignable` se déclenche sur `up{job="nodes"} == 0` pendant 10 min, et
elle s'applique ici comme partout ailleurs. La cible est déclarée sans étiquette
particulière :

```yaml
- targets: ['192.168.0.32:9100']
  labels: {machine: 'climbcontest', role: 'app', expose: 'internet'}
```

### 6.4 `adn-maintenance` — la VM en fait partie, en tête de liste

La 110 est **le premier invité d'`ADN_GUESTS`**. Deux conséquences voulues :

1. la fenêtre de 05 h 00 la met à jour comme les autres — instantané, mise à
   jour, sonde, retour arrière si échec ;
2. elle est le **canari** de la séquence : si sa mise à jour casse quelque
   chose, ça se voit sur elle avant de se voir sur les neuf autres.

`check_backup` exige une sauvegarde PBS du jour pour **chaque** invité
d'`ADN_GUESTS` et annule toute la séquence s'il en manque une. C'est pour ça
que l'entrée dans `ADN_GUESTS` et l'entrée dans le job `backup-nightly` ne se
font jamais l'une sans l'autre.

Ce que ça ne change pas : **on ne met jamais à jour la veille ni le matin d'une
compétition.** La fenêtre nocturne tourne toute l'année ; la préparation d'une
compétition, elle, se fait à la main quelques jours avant (§7).

### 6.5 Le chien de garde

`adn-watchdog` réclame la sauvegarde PBS du jour pour chaque invité
d'`ADN_GUESTS`. La 110 y est, et elle est dans le job `backup-nightly` : il la
réclame, et il la trouve.

## 7. Préparer une compétition

La VM tourne toute l'année. Il n'y a donc plus de cycle marche/arrêt : ce qui
reste, c'est la préparation du jour J. La procédure complète, commande par
commande, est dans
[`docs/runbook-competition.md`](../../docs/runbook-competition.md) ; ce qui suit
n'en est que l'ossature.

### Quelques jours avant — jamais la veille

1. Mise à jour de l'OS, redémarrage si nécessaire.
2. Dernière release installée **depuis la console** (Réglages → Version du
   serveur → Installer). Il n'y a plus de tirage automatique depuis la
   [spec 031](../031-deploiement-depuis-la-console/).
3. Clé d'API, classeur relié, jeton Google, miroir qui écrit vraiment.
4. Un scan de bout en bout avec un vrai téléphone et un vrai QR code.
5. Instantané `prete-compet`.

### Le jour J

```bash
climbcontest competition   # instantané 'avant-compet' + pense-bête
```

Rien à basculer : `onboot` vaut déjà `1`, donc un redémarrage de l'hyperviseur
en pleine compétition ramène la VM toute seule.

### Corriger pendant la compétition (décision Q2 : pas de gel)

Adrien doit pouvoir livrer un correctif le jour même.

```bash
# Installer la release publiee : console > Reglages > Version du serveur,
# ou a la main
ssh adrien@192.168.0.32 'sudo systemctl start climbcontest-deploy.service'

# Revenir a la release precedente, instantanement
ssh adrien@192.168.0.32 'sudo climbcontest-rollback'
```

`climbcontest-rollback` refait pointer le lien `current` vers la release
précédente et redémarre le service — quelques secondes, sans réinstallation,
puisque les trois dernières releases sont sur le disque.

⚠️ Une compétition **en cours** bloque le bouton de la console : c'est voulu
(spec 031), et sans contournement dans l'interface.

### Après la compétition

1. Archiver l'édition **depuis la console** (spec 018), puis exporter la base.
2. `climbcontest cloture` — retire l'instantané `avant-compet`. La VM reste
   allumée : la sauvegarde PBS de 02 h 30 emporte la compétition dès cette nuit.

## 8. Sauvegarde — la version revue

**Position d'Adrien (28/08) : la copie périodique pendant la compétition est
inutile.** Je l'avais proposée toutes les 10 minutes ; c'est écarté.

Pour être précis sur le malentendu possible : je proposais de copier **la base
SQLite** (quelques kilo-octets), pas la VM. La décision reste la même, et elle se
défend — voici pourquoi, et ce qui la remplace.

### Ce que contient cette VM

| Contenu | Reconstructible ? | Depuis quoi |
| --- | --- | --- |
| Système Debian | oui | cloud-init, ~10 min |
| Code applicatif | oui | release GitHub signée |
| Configuration | oui | dépôt `homelab` |
| Secrets | oui | gestionnaire de mots de passe |
| **Données d'une compétition** | ❌ non | irremplaçable, **pendant une seule journée par an** |

### La sauvegarde nocturne, écartée puis reprise

Elle avait été écartée : 364 nuits sur 365, elle aurait sauvegardé une VM
éteinte sans rien de neuf. **Depuis le 03/09/2026 la VM tourne en permanence**,
elle est dans `ADN_GUESTS`, et `check_backup` exige donc une sauvegarde du jour
pour elle — les deux réglages se déplacent ensemble (§6.4). Elle est dans le job
`backup-nightly`.

### Ce qui protège réellement les données du jour J

Le risque n'est pas « le SSD meurt un dimanche matin » — c'est très rare, et un
instantané ne sauverait de toute façon pas les heures écoulées. Le risque réel,
c'est **une fausse manœuvre ou un déploiement raté**, et contre ça les bons
outils sont ailleurs :

| Menace | Ce qui protège |
| --- | --- |
| Déploiement raté le jour J | retour arrière automatique de release (§4), et retour arrière manuel instantané |
| Fausse manœuvre en base | instantané `avant-compet` pris juste avant le début |
| Perte du disque en pleine journée | l'**écriture miroir vers le classeur Google**, si on la conserve (Q7) + la file locale de chaque app juge |
| Perte après la compétition | archive `vzdump` de fin de journée |

### Le dispositif retenu

| Quand | Quoi | Où |
| --- | --- | --- |
| Juste avant le début | instantané Proxmox `avant-compet` (30 s, gratuit) | `local-lvm` |
| Pendant la journée | **recopie locale de la base, toutes les 10 min** | `shared/sauvegardes/` |
| En fin de compétition | un `vzdump` manuel + un export de la base | PBS 107 → NAS (immuable) |
| Après un changement d'infra | un `vzdump` manuel | PBS 107 |
| Le reste de l'année | `vzdump` nocturne, comme les neuf autres | PBS 107 → NAS |

La VM est dans le job `backup-nightly` depuis le 03/09/2026 : elle est
sauvegardée chaque nuit à 02 h 30, comme les autres. Les archives passent par
PBS et héritent des instantanés Btrfs immuables du NAS.

> **Q7, tranchée le 29/08 — et l'argument d'origine était faux.**
>
> La ligne « pendant la journée : rien » reposait sur une idée : le miroir vers
> le classeur Google donne une redondance gratuite des données du jour.
>
> Ce jour-là, on a découvert que ce miroir était **cassé en silence depuis des
> heures** — il cherchait le jeton Google au mauvais endroit. La redondance
> n'était donc pas une garantie, c'était une espérance. Et elle disparaîtra de
> toute façon quand la console remplacera le classeur.
>
> D'où une **recopie locale de la base toutes les dix minutes**, qui ne dépend
> de personne. Ce n'est pas la copie de VM qu'Adrien avait jugée inutile à ce
> rythme, et il avait raison de la juger inutile : une copie SQLite fait
> ~160 ko et prend moins d'une seconde, là où un instantané de VM est une
> opération lourde. Ce sont deux choses différentes.
>
> Elle protège de la fausse manœuvre, de la corruption, et du « c'était mieux
> il y a dix minutes ». Elle ne protège **pas** de la perte du disque — pour
> ça, il y a l'instantané pris avant la compétition et le `vzdump` de fin de
> journée.
>
> Et son âge est exposé par `/health` : une sauvegarde qui s'arrête doit **se
> voir**. C'est exactement la leçon du miroir.

## 9. Fichiers créés ou modifiés

### Dans le dépôt `homelab`

| Fichier | Action |
| --- | --- |
| `pve01/vm-configs/110.conf` | créé |
| `pve01/firewall/110.fw` | créé |
| `pve01/adn-guest-state/adn-guest-state` + `.service` + `.timer` | créés — collecteur d'état des invités |
| `pve01/adn-maintenance/probes/110.sh` | créé (sonde, utilisée hors fenêtre nocturne) |
| `vm101-edge/Caddyfile` | bloc `climbcontest.adn-dev.fr` ajouté |
| `vm109-intra/Caddyfile` | noms internes + alias, en redirection ; entrée sur la page d'accueil |
| `vm108-monitoring/prometheus.yml` | cible `.32`, sans étiquette particulière |
| `vm108-monitoring/rules/adn-rules.yml` | rien de spécifique : les règles génériques s'appliquent |
| `vm108-monitoring/crowdsec-whitelist-adn.yaml` | exemption des chemins d'API |
| `vm110-climbcontest/` | nouveau dossier : unités systemd, agent de tirage, README |
| `scripts/climbcontest` | état, préparation du jour J, clôture |

### Dans le dépôt du backend

| Fichier | Action |
| --- | --- |
| `CHANGELOG.md` | créé |
| `.github/workflows/release.yml` | créé |
| `scripts/release.sh` | créé |
| `deployment/climbcontest.service` | créé |
| `deployment/install.sh` | créé — pose la VM à neuf |
| `wsgi.py` | créé (point d'entrée gunicorn) |

### Hors dépôt

- Enregistrement DNS `climbcontest` dans la zone `adn-dev.fr` chez Cloudflare.
- Enregistrements internes `climbcontest`, `escalade`, `contest`, `resultats`,
  `classement`, `saisie`, `parametres`, `climbcontest-admin` sur le résolveur de
  la LXC 109.
- PAT GitHub à portée fine, lecture seule, dans le gestionnaire de mots de passe.
