# Runbook — une compétition, de A à Z

À suivre tel quel. Chaque commande est faite pour être copiée-collée sans
réfléchir, parce qu'un jour de compétition on ne réfléchit pas bien.

Le script `climbcontest` vit dans le dépôt `homelab` (`scripts/climbcontest`).
Ajoute-le à ton `PATH` ou lance-le par son chemin complet.

---

## Quelques jours avant — préparer, jamais la veille

> **On ne met jamais à jour le matin d'une compétition.** C'est la règle qui
> justifie que cette VM soit exclue de la fenêtre de maintenance automatique
> de 05 h 00.

```bash
climbcontest start
```

Puis :

1. **Mise à jour du système**
   ```bash
   ssh adrien@192.168.0.32 'sudo unattended-upgrade -v; sudo reboot'
   ```
   Attendre, puis `climbcontest status`.

2. **Dernière release en place** — le timer s'en charge seul en 2 minutes.
   ```bash
   ssh adrien@192.168.0.32 'sudo climbcontest-rollback --list'
   ```

3. **La clé d'API est-elle en place ?** ⚠️ Depuis la spec 012, sans elle le
   service démarre mais **toutes les routes du juge répondent 503**.
   ```bash
   ssh adrien@192.168.0.32 \
     'curl -s localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[\"status\"], d[\"api\"][\"regime\"], d[\"api\"][\"cles_acceptees\"], \"cle(s)\")"'
   ```
   Attendu : `ok strict 1 cle(s)`. Si c'est `degraded`, voir
   [Poser la clé d'API](#poser-la-cle-dapi) plus bas.

   Et vérifier que **les téléphones ont la version qui envoie la clé** : un
   téléphone resté sur l'ancienne recevra un 401 sur chaque envoi.

4. **Le classeur est-il le bon ?** ⚠️ Point le plus souvent oublié.
   Depuis la spec 015, ça se voit et ça se change **depuis la console** :
   `/console` → menu → **Classeur**. La carte du haut dit sur quel classeur
   pointe la compétition active, et « Tester l'accès » le lit pour de vrai —
   titre, onglets, taille de la grille. Plus besoin de SSH ni de SQL.

   Trois modes au moment de relier, à choisir en connaissance de cause :
   **relier seulement** (rien d'autre ne bouge), **même compétition, autre
   feuille** (toutes les réussites déjà enregistrées repartent vers la nouvelle
   feuille), **nouvelle compétition** (efface les données du serveur *et* vide
   la matrice `Import` de la nouvelle feuille — confirmation `EFFACER` exigée,
   refusé si la compétition est `en_cours`).

5. **Le jeton Google est-il sur la VM ?** ⚠️ Constaté absent à l'audit du
   30/08 : `/opt/climbcontest/shared/secrets/` était **vide** — le miroir
   n'aurait jamais écrit une ligne dans le classeur. Voir
   [Poser le jeton Google](#poser-le-jeton-google) plus bas.

6. **Le miroir écrit-il vraiment ?** Saisir une réussite de test depuis la
   console, attendre une minute, puis :
   ```bash
   curl -s https://climbcontest.adn-dev.fr/health | \
     python3 -c "import sys,json; d=json.load(sys.stdin); \
       print('en attente :', d['reussites_en_attente'], \
             '| derniere erreur :', d['miroir_derniere_erreur'])"
   ```
   Attendu : `en attente : 0 | derniere erreur : None`. Une erreur qui reste
   affichée dit **exactement** ce qui bloque (« aucun classeur relié… »,
   « Aucun jeton Google… ») — plus besoin d'ouvrir un SSH pour le savoir.
   Supprimer ensuite la réussite de test depuis la console.

7. **Un scan de bout en bout** avec un vrai téléphone et un vrai QR code —
   et un iPhone de bénévole via l'onglet **App juge** de la console
   (le QR d'installation s'y trouve).

8. **Instantané de secours**
   ```bash
   ssh root@192.168.0.21 'qm snapshot 110 prete-compet --description "Prete pour la competition"'
   ```

9. **Éteindre**
   ```bash
   climbcontest stop
   ```

---

## L'écran de la salle

L'adresse à projeter : **`https://climbcontest.adn-dev.fr/?mur`**

Elle tourne seule toute la journée — podium, catégorie entière à l'écran,
rotation d'une catégorie à l'autre, et les changements de place qui glissent
avec leur flèche. Personne n'a besoin d'y toucher.

| Variante | Quand |
| --- | --- |
| `/?mur` | le cas normal : **fond clair**, fait pour un vidéoprojecteur |
| `/?mur&sombre` | écran LED, ou salle qu'on peut vraiment assombrir |
| `/?mur&rotation=30` | forcer la durée d'un écran, en secondes |
| `/` | ce que voient les parents sur leur téléphone : recherche par nom ou dossard |

⚠️ `/resultats` **n'existe plus** (spec 016) : c'était un doublon de la racine.

## Le matin du jour J

```bash
climbcontest competition
```

Cette seule commande fait quatre choses :

- allume la VM et **attend qu'elle réponde vraiment** (pas juste qu'elle démarre) ;
- bascule `onboot` à **1** — si l'hyperviseur redémarre en pleine compétition
  (coupure de courant), la VM revient seule ;
- prend l'instantané `avant-compet` ;
- affiche le pense-bête des trois commandes d'urgence.

Puis vérifier depuis l'extérieur, **avec un téléphone en 4G, pas sur le wifi de
la maison** :

```
https://climbcontest.adn-dev.fr/
```

---

## Pendant la compétition

### Livrer un correctif

Les déploiements **ne sont pas gelés** : c'est une décision assumée, tu dois
pouvoir corriger le jour J.

```bash
# depuis le Mac, après avoir poussé une release
ssh adrien@192.168.0.32 'sudo systemctl start climbcontest-deploy.service'
```

N'attend pas le tick de 2 minutes. Si la nouvelle version ne répond pas, l'agent
**revient tout seul** à la précédente et le vérifie.

### Revenir en arrière tout de suite

```bash
ssh adrien@192.168.0.32 'sudo climbcontest-rollback'            # version précédente
ssh adrien@192.168.0.32 'sudo climbcontest-rollback v0.1.2'     # une version précise
ssh adrien@192.168.0.32 'sudo climbcontest-rollback --list'     # ce qui est disponible
```

Quelques secondes : les trois dernières releases sont sur le disque avec leur
environnement Python. Aucune réinstallation, aucun réseau.

### 🔴 La salle entière n'a plus accès

Le symptôme : **tout le monde** perd l'accès en même temps, juges et
spectateurs. C'est presque toujours CrowdSec qui a banni l'adresse publique de
la salle — 25 juges et 100 spectateurs derrière un seul NAT ressemblent à une
attaque.

```bash
ssh root@192.168.0.21 "pct exec 101 -- cscli decisions list"
ssh root@192.168.0.21 "pct exec 101 -- cscli decisions delete --ip <adresse-de-la-salle>"
```

Une exemption est déjà posée sur `/api/v2/contest/*` et `/api/public/*`, donc ça
ne devrait pas arriver. Si ça arrive quand même, regarde **quel scénario** a
déclenché : c'est probablement un chemin qu'on n'avait pas prévu.

### 🔴 Un téléphone n'envoie plus rien, les autres si

Le symptôme, vu de la console : dans l'onglet **Appareils**, un téléphone
apparaît en rouge (« muet depuis plus de dix minutes ») pendant que les autres
avancent. Vu du juge : le voyant de connexion est rouge barré alors que son
wifi marche.

Cause la plus probable depuis la spec 012 : **ce téléphone a une ancienne
version de l'application**, sans clé d'API, et le serveur refuse tout ce qu'il
envoie.

Vérifier :

```bash
ssh adrien@192.168.0.32 'journalctl -u climbcontest --since "10 min ago" | grep "appel sans cle"'
```

- des lignes → c'est bien ça. Installer la version à jour sur ce téléphone.
  **Ses réussites ne sont pas perdues** : l'application garde sa file et
  repartira toute seule une fois la clé bonne ;
- aucune ligne → ce n'est pas la clé. Regarder le wifi du téléphone.

En dernier recours, si plusieurs téléphones sont concernés et qu'on n'a pas le
temps de les mettre à jour, on rouvre l'API : c'est le §3 du
[plan de repli](plan-de-repli.md).

### Un correctif publié ne semble pas arriver sur les téléphones

**PWA (iPhone).** Elle sert son code depuis son propre cache, pour pouvoir
s'ouvrir sans réseau. La version fraîche est téléchargée en arrière-plan et
prend effet **au lancement suivant** — c'est volontaire : recharger la page
toute seule couperait un juge en plein geste.

Concrètement : demande aux juges de **fermer complètement l'application et de la
rouvrir**. Sur iPhone, glisser vers le haut depuis la barre d'accueil puis
balayer la carte de l'application.

**Android.** Un correctif passe par le Play Store, donc par une mise à jour
d'application. On ne fait pas ça un jour de compétition — c'est le sens du gel
de repli.

### Le service ne répond plus

```bash
ssh adrien@192.168.0.32 'systemctl status climbcontest; journalctl -u climbcontest -n 50'
ssh adrien@192.168.0.32 'sudo systemctl restart climbcontest'
```

### Revenir à l'instantané du matin

Dernier recours — **on perd toutes les réussites de la journée**.

```bash
ssh root@192.168.0.21 'qm rollback 110 avant-compet'
```

---

## Pendant la compétition — les recopies locales

La base est recopiée **toutes les dix minutes** dans
`/opt/climbcontest/shared/sauvegardes/`, les 24 dernières sont conservées
(soit quatre heures de recul). Chaque copie fait ~160 ko et est relue
immédiatement après écriture.

```bash
# Est-ce que ça tourne encore ? (l'âge de la dernière copie)
curl -s https://climbcontest.adn-dev.fr/health | python3 -m json.tool | grep -A4 sauvegarde

# Les copies disponibles
ssh adrien@192.168.0.32 'sudo ls -lht /opt/climbcontest/shared/sauvegardes/ | head'

# Revenir dix minutes en arrière (APRÈS avoir arrêté le service)
ssh adrien@192.168.0.32 'sudo systemctl stop climbcontest
  sudo -u climbcontest cp /opt/climbcontest/shared/sauvegardes/climbcontest-AAAAMMJJ-HHMMSS.db \
    /opt/climbcontest/shared/data/climbcontest.db
  sudo systemctl start climbcontest'
```

> ⚠️ Ces copies sont sur le **même disque** que la base. Elles protègent d'une
> fausse manœuvre ou d'une corruption, pas de la perte du disque — pour ça, il
> y a l'instantané `avant-compet` et le `vzdump` de fin de journée.

## Après la compétition

### D'abord, depuis la console (spec 018)

Avant les sauvegardes système, **archiver dans la console** — `/console` →
« Compétition » → **Archiver l'édition**. Le classement complet et les données
brutes sont figés dans la base, la compétition passe « terminée », et **rien
n'est effacé**.

L'édition est ensuite consultable dans « Archives », avec trois boutons :

| Bouton | Ce qu'il fait |
| --- | --- |
| **Revoir** | Rouvre la vraie page de résultats sur le classement figé — podium, classements, scratchs, et `?mur` marche aussi. Consultation seule : rien n'est restauré |
| **Télécharger** | Un JSON daté, pour en avoir une copie hors de la VM (~700 Ko pour une édition complète) |
| **Supprimer** | Réservé aux administrateurs, confirmation à frapper |

Puis, pour repartir sur l'édition suivante :

1. « Compétition » → **Effacer les données** (fenêtre de confirmation, mot
   `EFFACER` à frapper). Les archives et le classeur Google ne sont pas touchés.
2. « Classeur » → **Relier** la feuille de la nouvelle édition, puis
   **Tester l'accès en écriture** — c'est le geste qui attrape une feuille
   partagée en lecture seule, avant le jour J plutôt qu'après le premier scan.
3. « Compétition » → **Importer** (mise à jour). Ou **remplacement complet** si
   la base porte encore l'édition précédente.
4. « Compétition » → l'état repasse à **En préparation**.

### Ensuite, les sauvegardes système

```bash
# 1. Archiver la base
ssh adrien@192.168.0.32 'sudo -u climbcontest sqlite3 /opt/climbcontest/shared/data/climbcontest.db ".backup /tmp/compet-$(date +%F).db"'
scp adrien@192.168.0.32:/tmp/compet-*.db ~/Documents/

# 2. Archiver la machine entière
ssh root@192.168.0.21 'vzdump 110 --storage pbs-nas --mode snapshot --compress zstd'

# 3. Clôturer : onboot remis à 0, instantané nettoyé, VM éteinte
climbcontest cloture
```

---

## Poser le jeton Google

À faire **une fois** (et à refaire si le jeton est révoqué). Sans lui, le
miroir vers le classeur tourne mais n'écrit jamais — les réussites restent en
base, `/health` montre `reussites_en_attente` qui monte et
`miroir_derniere_erreur` qui dit pourquoi.

Le jeton vit sur le Mac (`climbcontest-core/token.pickle`, hors dépôt).

### Depuis la console (spec 015) — le chemin normal

Sur le Mac, convertir le jeton en JSON :

```bash
python3 tools/exporter_jeton.py            # cherche token.pickle dans le dossier courant
```

Puis coller la sortie dans `/console` → **Classeur** → « Jeton Google ». Le
serveur l'écrit dans `/opt/climbcontest/shared/secrets/token.json`, en `0600`,
et garde le précédent en `.precedent`. La carte du haut affiche aussitôt l'état
du jeton et sa date d'expiration.

⚠️ Ce JSON est un **secret** : il ouvre le compte Google du classeur. Il ne se
commit pas, ne se colle pas dans une conversation, et le fichier temporaire qui
le porte se supprime.

**Pourquoi du JSON et pas le `token.pickle` directement** : le serveur ferait
`pickle.loads()` sur un contenu venu du réseau, et une session d'administrateur
volée deviendrait une exécution de code sur la VM. Le JSON porte la même
information et n'est que des données.

### Par `scp` — toujours valable

```bash
scp token.pickle adrien@192.168.0.32:/tmp/token.pickle
ssh adrien@192.168.0.32 'sudo install -m 600 -o climbcontest -g climbcontest \
  /tmp/token.pickle /opt/climbcontest/shared/secrets/token.pickle && rm /tmp/token.pickle'
```

Le serveur lit `token.json`, puis `token.pickle`, puis `token.base64` — dans cet
ordre. Un `token.json` posé depuis la console **passe donc devant** un
`token.pickle` existant.

Puis vérifier avec l'étape « Le miroir écrit-il vraiment ? » ci-dessus. Si le
jeton est périmé et non rafraîchissable, refaire le consentement **depuis le
Mac** (une machine avec navigateur) et re-poser le fichier.

---

## Si tout est cassé : le plan de repli

La version 2025-2026 tourne toujours sur Render et reste déployable en une
trentaine de minutes. Tout est dans [plan-de-repli.md](plan-de-repli.md) :
tags `V2.1.1` (backend) et `V3.1.4` (app), bundles hors-ligne, APK installable,
secrets Google.

---

## Poser la clé d'API

À faire **une fois**, et à refaire seulement si la clé doit changer.

⚠️ Deux choses doivent porter **la même clé** : la VM et l'application. Poser
l'une sans l'autre casse le lien — VM sans clé = `503` partout, application sans
clé = `401` partout.

### 1. Sur la VM — générer et poser

La clé est générée **sur la VM** : elle ne transite ainsi par aucune autre
machine, aucun presse-papier, aucun historique de terminal.

```bash
ssh adrien@192.168.0.32
CLE=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
echo "CLIMBCONTEST_API_KEY=$CLE" | sudo tee -a /opt/climbcontest/shared/secrets/env
sudo sed -i '/^CLIMBCONTEST_API_KEY=$/d' /opt/climbcontest/shared/secrets/env   # retire la ligne vide
sudo systemctl restart climbcontest
curl -s localhost:8000/health | python3 -m json.tool | grep -E 'status|regime|cles_acceptees'
```

Attendu : `"status": "ok"`, `"regime": "strict"`, `"cles_acceptees": 1`.

Pour les **iPhone des bénévoles** (PWA), poser aussi une clé distincte —
c'est elle qui voyage dans le lien d'installation, la séparer permet de la
révoquer sans toucher aux téléphones Android :

```bash
CLE_PWA=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
echo "CLIMBCONTEST_API_KEY_PWA=$CLE_PWA" | sudo tee -a /opt/climbcontest/shared/secrets/env
sudo systemctl restart climbcontest
```

Le lien et le QR d'installation apparaissent alors dans la console,
onglet **App juge** (`cles_acceptees` passe à 2).

### 2. La lire une fois, pour l'application

```bash
sudo grep '^CLIMBCONTEST_API_KEY=' /opt/climbcontest/shared/secrets/env
```

Copier la valeur dans `~/.gradle/gradle.properties` **sur le Mac** — ce fichier
est hors du dépôt :

```properties
releaseApiKey=la-valeur-lue
```

⚠️ **Jamais** dans le `gradle.properties` du projet : il est suivi par git, et
les deux dépôts ClimbContest sont publics.

### 3. Publier l'application

```bash
cd climbcontest-android
./gradlew assembleRelease -PreleaseServerUrl=https://climbcontest.adn-dev.fr
```

Le build **refuse de démarrer** sans clé : c'est voulu, un APK sans clé serait
refusé par le serveur et on le découvrirait le jour J.

### Changer de clé sans coupure

Le serveur accepte deux clés en même temps. On ne fait donc jamais de bascule
brutale :

1. `CLIMBCONTEST_API_KEY_PRECEDENTE=<l'ancienne>` et `CLIMBCONTEST_API_KEY=<la nouvelle>`, redémarrer ;
2. publier l'application avec la nouvelle clé, attendre que tous les téléphones l'aient ;
3. retirer `CLIMBCONTEST_API_KEY_PRECEDENTE`, redémarrer.

---

## Aide-mémoire

| Quoi | Où |
| --- | --- |
| VM | 110 `climbcontest`, `192.168.0.32`, hyperviseur `192.168.0.21` |
| Adresse publique | `https://climbcontest.adn-dev.fr` |
| Noms internes | `climbcontest` · `escalade` · `resultats` · `saisie` · `parametres` `.maison.adn-dev.fr` |
| Journal du déploiement | `journalctl -t climbcontest-deploy -f` |
| Journal de l'application | `journalctl -u climbcontest -f` |
| Reverse proxy | LXC 101 `edge`, `pct exec 101 -- ...` depuis l'hyperviseur |
| Régime de la clé d'API | `curl -s http://127.0.0.1:8000/health \| grep -o '"regime":"[a-z]*"'` sur la VM |
| Rouvrir l'API aux anciens téléphones | `CLIMBCONTEST_API_KEY_STRICTE=0` puis redémarrer — §3 du plan de repli |
