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

3. **Le classeur est-il le bon ?** ⚠️ Point le plus souvent oublié.
   Vérifier que l'identifiant du classeur pointe sur **la** compétition à venir.

4. **Un scan de bout en bout** avec un vrai téléphone et un vrai QR code.

5. **Instantané de secours**
   ```bash
   ssh root@192.168.0.21 'qm snapshot 110 prete-compet --description "Prete pour la competition"'
   ```

6. **Éteindre**
   ```bash
   climbcontest stop
   ```

---

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

## Après la compétition

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

## Si tout est cassé : le plan de repli

La version 2025-2026 tourne toujours sur Render et reste déployable en une
trentaine de minutes. Tout est dans [plan-de-repli.md](plan-de-repli.md) :
tags `V2.1.1` (backend) et `V3.1.4` (app), bundles hors-ligne, APK installable,
secrets Google.

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
