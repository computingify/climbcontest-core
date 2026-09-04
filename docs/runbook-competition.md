# Runbook — une compétition, de A à Z

À suivre tel quel. Chaque commande est faite pour être copiée-collée sans
réfléchir, parce qu'un jour de compétition on ne réfléchit pas bien.

Le script `climbcontest` vit dans le dépôt `homelab` (`scripts/climbcontest`).
Ajoute-le à ton `PATH` ou lance-le par son chemin complet.

---

## Quelques jours avant — préparer, jamais la veille

> **On ne met jamais à jour le matin d'une compétition.** La VM est mise à jour
> toutes les nuits par la fenêtre de maintenance de 05 h 00, comme les neuf
> autres invités — et elle est **en tête de séquence**, donc c'est sur elle
> qu'une mise à jour cassante se voit d'abord. La veille et le matin du jour J,
> on ne touche à rien.

> **La VM tourne en permanence depuis le 03/09/2026.** Il n'y a plus rien à
> allumer : `climbcontest status` doit répondre, et c'est tout. Si elle est
> éteinte, c'est une anomalie — voir `homelab/vm110-climbcontest/README.md`.

1. **Mise à jour du système** — normalement déjà faite par la fenêtre nocturne.
   Pour la forcer :
   ```bash
   ssh adrien@192.168.0.32 'sudo unattended-upgrade -v; sudo reboot'
   ```
   Attendre, puis `climbcontest status`.

2. **Dernière release en place.** ⚠️ **Plus aucun tirage automatique** depuis la
   spec 031 : une release publiée reste sur GitHub tant que personne ne clique.
   L'installer depuis `/console` → **Réglages** → « Version du serveur » →
   **Installer**, ou à la main :
   ```bash
   ssh adrien@192.168.0.32 'sudo systemctl start climbcontest-deploy.service'
   ssh adrien@192.168.0.32 'sudo climbcontest-rollback --list'   # ce qui est installé
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

   > `reussites_en_attente` ne parle que de la compétition **active** : c'est
   > ce que le miroir va écrire, donc ce qui doit retomber à zéro. Un
   > `reussites_inenvoyables` non nul à côté n'est pas une alerte — ce sont des
   > réussites d'anciennes compétitions, ou de grimpeurs sans dossard, que le
   > classeur d'aujourd'hui ne recevra jamais. Elles restent en base et dans
   > l'archive de leur propre compétition.

7. **Un scan de bout en bout** avec un vrai téléphone et un vrai QR code —
   et un iPhone de bénévole via l'onglet **App juge** de la console
   (le QR d'installation s'y trouve).

8. **Instantané de secours**
   ```bash
   ssh root@192.168.0.21 'qm snapshot 110 prete-compet --description "Prete pour la competition"'
   ```

   La VM **reste allumée** : elle l'est toute l'année. Ne pas l'éteindre — la
   supervision la déclarerait injoignable au bout de dix minutes, et la fenêtre
   de 05 h 00 la rallumerait pour la mettre à jour.

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
| `/?periode=5` | relire les données toutes les 5 s au lieu de 15 |
| `/?periode-reglages=1` | relire les **réglages** toutes les 1 s au lieu de 3 |
| `/` | ce que voient les parents sur leur téléphone : recherche par nom ou dossard |

⚠️ `/resultats` **n'existe plus** (spec 016) : c'était un doublon de la racine.

## Le matin du jour J

```bash
climbcontest competition
```

Cette seule commande fait trois choses :

- vérifie que la VM **répond vraiment** (pas juste qu'elle tourne) ;
- prend l'instantané `avant-compet` ;
- affiche le pense-bête des trois commandes d'urgence.

Il n'y a plus rien à basculer : `onboot` vaut `1` toute l'année, donc si
l'hyperviseur redémarre en pleine compétition (coupure de courant), la VM
revient seule.

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

Deux chemins, au choix :

- `/console` → **Réglages** → « Version du serveur » → **Installer**. ⚠️ Ce
  bouton **refuse de travailler pendant une compétition en cours** : c'est
  voulu, et sans contournement dans l'interface. Le jour J, c'est donc l'autre
  chemin.
- ```bash
  # depuis le Mac, après avoir poussé une release
  ssh adrien@192.168.0.32 'sudo systemctl start climbcontest-deploy.service'
  ```

⚠️ **Rien ne s'installe tout seul** : le minuteur qui tirait GitHub toutes les
2 minutes a été retiré le 03/09/2026 (spec 031). Publier une release ne la met
pas en production ; il faut demander l'installation.

Si la nouvelle version ne répond pas, l'agent **revient tout seul** à la
précédente et le vérifie.

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

### Savoir qui est en retard, avant que ça ne se voie

Console → **Téléphones** → carte **« Versions en circulation »** (spec 030).
Elle dit ce que sert le serveur, et le tableau juste en dessous donne, par
poste, la version d'application et le numéro de catalogue qu'il porte
réellement. Une pastille ambre et un numéro écrit en toutes lettres = ce
téléphone ne travaille pas sur les mêmes données que les autres.

C'est le **contrôle du matin** : il fonctionne dès que les juges ouvrent
l'application, avant la première réussite envoyée. Un téléphone absent du
tableau n'a jamais parlé au serveur — c'est déjà un renseignement.

Côté juge, le même constat est dans **Réglages**, en bas.

### Un correctif publié ne semble pas arriver sur les téléphones

**PWA (iPhone).** Elle sert son code depuis son propre cache, pour pouvoir
s'ouvrir sans réseau. La version fraîche est téléchargée en arrière-plan et
prend effet **au lancement suivant** — c'est volontaire : recharger la page
toute seule couperait un juge en plein geste.

Concrètement : demande aux juges de **fermer complètement l'application et de la
rouvrir**. Sur iPhone, glisser vers le haut depuis la barre d'accueil puis
balayer la carte de l'application. Depuis la spec 030, il y a plus rapide :
**Réglages → Application → « Mettre à jour et redémarrer »**, qui n'apparaît
que si ce téléphone est effectivement en retard. Sans réseau, ce bouton refuse
et ne détruit rien.

### ⚠️ Ne jamais mettre `/api/v2/catalog` en cache sur le proxy

Cette route enregistre le passage de chaque téléphone (spec 030) : c'est ce qui
alimente les colonnes de version de la console. Un module de cache activé
devant elle sur `edge` (LXC 101) — ou un proxy quelconque sur le wifi de la
salle — absorberait ces requêtes, et la console montrerait des téléphones
**absents pendant qu'ils grimpent**.

La réponse porte `Cache-Control: no-cache, private` pour l'interdire, et un
test le verrouille côté application. Ce qui ne peut pas se tester, c'est la
configuration du proxy : si la carte « Versions en circulation » affiche
« *N téléphones envoient des réussites mais ne s'annoncent plus* », c'est
exactement cette panne-là, et c'est du côté de Caddy qu'il faut regarder.

**Android.** ⚠️ **L'application Android native est hors périmètre depuis le
03/09/2026** : plus aucune version n'en sera publiée. Un téléphone qui la porte
encore garde la version installée, avec sa file locale — elle continue
d'envoyer, elle ne se corrige plus. Le chemin d'un correctif, pour tout le
monde, c'est la PWA. L'APK `V3.1.4` reste installable comme filet de secours,
au titre du [plan de repli](plan-de-repli.md).

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

# 3. Clôturer : retire l'instantané 'avant-compet'. La VM reste allumée,
#    la sauvegarde PBS de 02 h 30 emporte la competition des cette nuit.
climbcontest cloture
```

---

## Poser le jeton Google

À faire **une fois** (et à refaire si le jeton est révoqué). Sans lui, le
miroir vers le classeur tourne mais n'écrit jamais — les réussites restent en
base, `/health` montre `reussites_en_attente` qui monte et
`miroir_derniere_erreur` qui dit pourquoi.

### Depuis la console, en un clic (spec 022) — le chemin normal

`/console` → **Classeur** → « Jeton Google » → **Connecter le compte Google**.
Google demande le consentement, on revient sur la console, le jeton est posé.
Pas de Mac, pas de terminal, pas de copier-coller d'un secret.

Le serveur l'écrit dans `/opt/climbcontest/shared/secrets/token.json`, en
`0600`, et garde le précédent en `.precedent`.

#### ⚠️ Deux choses à régler UNE FOIS chez Google

Dans la Google Cloud Console du projet qui porte `credentials.json` :

1. **Identifiants** → le client OAuth de type « Web » → **URI de redirection
   autorisés** → ajouter, *au caractère près* :

   ```
   https://climbcontest.adn-dev.fr/admin/classeur/google/retour
   http://localhost:5000/admin/classeur/google/retour     ← développement
   ```

   La console **affiche** cette URI, prête à copier, sous le bouton. Si elle
   n'est pas déclarée, Google refuse avec `redirect_uri_mismatch` **avant** de
   revenir chez nous — rien n'est cassé, mais rien n'aboutit non plus.

2. **Écran de consentement** → vérifier l'**état de publication**.

   🔴 **En « Test », Google fait expirer le `refresh_token` au bout de
   7 jours.** Un jeton posé le lundi serait mort le samedi de la compétition,
   sans que rien ne prévienne — les réussites s'empileraient toute la journée.
   L'application doit être **« En production »**. Même avec un seul
   utilisateur, même non vérifiée : l'écran « application non vérifiée » se
   franchit par « Paramètres avancés », c'est notre propre compte.

   ⚠️ **Ce point est en cours de vérification sur le terrain** (03/09/2026) :
   le jeton en service permet de trancher tout seul. S'il fonctionne encore
   plus de 7 jours après avoir été posé, c'est que le projet n'est **pas** en
   état « Test », et cette alerte tombe. S'il cesse de fonctionner sans que
   personne n'ait rien touché, c'est exactement ce cas — et le symptôme est
   `reussites_en_attente` qui monte, avec `miroir_derniere_erreur` qui le dit.
   Le relire une fois par semaine d'ici la compétition coûte dix secondes.

Le scope demandé est `spreadsheets`, et rien de plus : le jeton n'a jamais eu
à lister ni supprimer des fichiers du Drive.

### Autre méthode — coller un jeton produit sur le Mac (spec 015)

Le chemin de secours, pour le jour où le consentement ne passe pas depuis la
salle. Replié dans un `<details>` sous le bouton.

Le jeton vit sur le Mac (`climbcontest-core/token.pickle`, hors dépôt). Le
convertir en JSON :

```bash
python3 tools/exporter_jeton.py            # cherche token.pickle dans le dossier courant
```

Puis coller la sortie dans `/console` → **Classeur** → « Jeton Google » →
« Autre méthode ». Le serveur l'écrit au même endroit, de la même façon, et la
carte affiche aussitôt l'état du jeton et sa date d'expiration.

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
révoquer séparément :

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

### 3. Publier l'application — **caduc**

⚠️ **L'application Android native est hors périmètre depuis le 03/09/2026** ;
il n'y a plus de build à publier. Ce qui reste vrai : la clé qui voyage vers
les téléphones est `CLIMBCONTEST_API_KEY_PWA`, et elle est **dans le lien
d'installation** de la PWA, que la console affiche en QR dans l'onglet
**App juge**. Changer cette clé change le lien : il faut refaire installer la
PWA, ou au minimum rouvrir le lien à jour.

Pour mémoire, la commande d'alors :

```bash
cd climbcontest-android
./gradlew assembleRelease -PreleaseServerUrl=https://climbcontest.adn-dev.fr
```

### Changer de clé sans coupure

Le serveur accepte deux clés en même temps. On ne fait donc jamais de bascule
brutale :

1. `CLIMBCONTEST_API_KEY_PRECEDENTE=<l'ancienne>` et `CLIMBCONTEST_API_KEY=<la nouvelle>`, redémarrer ;
2. faire réinstaller la PWA depuis le lien à jour, attendre que tous les téléphones l'aient ;
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
