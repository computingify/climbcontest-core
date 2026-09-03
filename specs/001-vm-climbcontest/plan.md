# Plan d'implémentation : 001 — VM ClimbContest

> **Ce fichier est le journal de l'implémentation** des 28-29/08 : il dit ce qui
> a été fait, dans l'ordre où ça l'a été. Six de ses lignes ont été **défaites le
> 03/09/2026** avec l'abandon du régime intermittent ; elles portent la mention
> **⤫ défait le 03/09**. Le raisonnement, lui, a été retiré de la spec — voir
> [spec.md § Historique](spec.md#historique--ce-que-cette-spec-ne-dit-plus).

## Approche

Cinq itérations, chacune vérifiable seule et réversible seule. On ne passe à la
suivante qu'après avoir vu la précédente fonctionner — c'est la règle du runbook
de migration, elle a fait ses preuves.

L'ordre est choisi pour que **la chaîne de livraison existe avant qu'il y ait
quelque chose à livrer** : on la valide avec une application factice, ce qui
évite de déboguer en même temps le déploiement et le backend.

**Ce qui exige un mot de passe** (root Proxmox, Cloudflare, GitHub) : Claude
ouvre un terminal ou indique l'écran, **Adrien saisit lui-même**.

---

## IT1 — La machine nue

- [x] 1. ~~Vérifier que `192.168.0.32` est hors plage DHCP~~ — **validé** : DHCP de `.40` à `.200`
- [x] 2. Créer la VM 110 `climbcontest` : Debian 13, cloud-init, 4 vCPU / 4 Go / 24 Go, `onboot: 0`, tags `climbcontest` + `intermittent` — **⤫ défait le 03/09** : `onboot: 1`, tag `intermittent` retiré
- [x] 3. Installer `qemu-guest-agent` **dans** la VM, vérifier `qm agent 110 ping`
- [x] 4. Installer `node_exporter`, vérifier `:9100`
- [x] 5. Poser `110.fw`, vérifier `grep '^|'` vide et tester chaque règle
- [x] 6. Versionner `110.conf` et `110.fw` dans `homelab`
- [x] 7. **Vérification** : le redémarrage réel de `pve01` a eu lieu le 03/09 à 05 h 04, à l'occasion d'une mise à jour du noyau. Il a vérifié `onboot: 0` en le rendant intolérable — la VM est restée éteinte, seule du parc, sans que rien ne le signale. C'est ce qui a déclenché l'abandon du régime intermittent

## IT2 — Les contrôles adaptés

À faire **avant** d'exposer quoi que ce soit : sinon la VM passe une semaine à
déclencher des alertes.

- [x] 8. Collecteur `adn-guest-state` sur `pve01` + timer, écrivant `pve_guest_running`
- [x] 9. Ajouter la cible `.32` dans `prometheus.yml` avec `intermittent: 'oui'` — **⤫ défait le 03/09** : étiquette retirée
- [x] 10. Filtrer `MachineInjoignable` sur `intermittent!="oui"` — **⤫ défait le 03/09** : le filtre ne retire plus personne
- [x] 11. Créer l'alerte `ClimbcontestInjoignableEnService` — **⤫ défait le 03/09** : supprimée, la règle générique la couvre
- [x] 12. `promtool check config` + `check rules`, recharger Prometheus
- [x] 13. Vérifier que la 110 **n'est pas** dans `ADN_GUESTS` — **⤫ défait le 03/09** : elle y est, en tête
- [x] 14. **Vérification** : aucune alerte parasite constatée
- [x] 15. **Vérification** : les trois états testés — allumée+répond → silence, allumée+muette → alerte, éteinte → silence

## IT3 — La chaîne de livraison, à vide

- [x] 16. `CHANGELOG.md` initial (Keep a Changelog, français)
- [x] 17. `wsgi.py` + une route `/health` minimale (application factice)
- [x] 18. `climbcontest.service` : gunicorn, 4 workers × 4 threads
- [x] 19. `deployment/install.sh` : utilisateur, arborescence, venv, systemd
- [x] 20. `.github/workflows/release.yml` : tests → **vérification du CHANGELOG** → archive + `.sha256` → Release
- [x] 21. `scripts/release.sh` : bump, contrôle du changelog, tag, push
- [ ] 22. ~~PAT lecture seule~~ — **inutile** : le dépôt est public, les assets se tirent en anonyme. Le script gère quand même le cas « jeton présent » si le dépôt devenait privé
- [x] 23. `climbcontest-deploy` + service + timer, **avec les deux bugs de solio-map déjà corrigés**
- [x] 23 bis. `climbcontest-rollback` : retour arrière manuel instantané (décision Q2)
- [x] 24. **Vérification** : `v0.1.0` publiée → installée seule en moins de 3 min
- [x] 25. **Vérification** : `v0.1.1` volontairement cassée → retour arrière automatique vers `v0.1.0`
- [x] 26. **Vérification** : archive à l'empreinte falsifiée → refusée, rien d'installé
- [x] 27. **Vérification** : tag sans section de changelog → le workflow échoue

### Ce que les tests d'IT3 ont révélé

Jouer réellement les scénarios d'échec, plutôt que les supposer, a fait sortir
**trois défauts** de l'agent de déploiement — tous corrigés en v0.1.2 :

| Défaut | Conséquence si non corrigé |
| --- | --- |
| Release cassée retentée à chaque tick | boucle de redémarrages du service, toutes les 2 min |
| Retour arrière annoncé sans être vérifié | le journal dit « revenu sur vX » pendant que le service est à terre |
| Exécutions concurrentes (timer + manuel) | la seconde prend la version cassée pour « la précédente » et y revient |

Le troisième est celui qui aurait mordu le jour J : le déploiement manuel est
précisément la commande d'urgence de la décision Q2, et le timer continue de
tourner pendant qu'on l'utilise.

## IT4 — L'exposition

- [x] 28. Enregistrement DNS `climbcontest` dans `adn-dev.fr` chez Cloudflare, DNS uniquement
- [x] 29. Bloc Caddy sur `edge`, `import commun` + `import sondes`, plan d'URL des 5 surfaces
- [x] 30. Whitelist CrowdSec sur les chemins `/api/v2/contest/` et `/api/public/`
- [x] 31. Noms internes sur la LXC 109 (redirections + alias) et entrée sur la page d'accueil du portail
- [x] 32. **Vérification** : `https://climbcontest.adn-dev.fr/health` en 200 depuis le LAN, **404 depuis Internet**
- [x] 33. **Vérification** : chaque nom interne mène au bon chemin
- [x] 34. **Vérification** : `/.git/config` et `/.env` en 404
- [~] 35. **Charge vérifiée** (mesure externe à refaire par Adrien, Mac en partage 5G)
- [x] 35 bis. **Charge vérifiée** : 1489 requêtes en 4 min (368/min), 100 % de réussite, médiane 26 ms, p95 80 ms, charge machine 0,03. **Mais lancée depuis le LAN**, qui est déjà blanchi par `adn/whitelist-usage-legitime` — ce test prouve la capacité, pas le comportement de CrowdSec (voir 36)
- [x] 36. **CrowdSec vérifié autrement, et mieux** : `cscli explain` sur des événements fabriqués depuis une IP externe (203.0.113.7). API juge en 401 → blanchie ; `/admin/login` → **non** blanchi ; même chemin sur guestflow → **non** blanchi. Aucune décision déclenchée par le test de charge
- [x] 37. Documenter la commande de déblocage d'urgence dans le runbook du jour J

### Ce qu'IT4 a révélé

Un problème qui **dépassait la spec 001** : le pare-feu sortant d'`edge`,
resserré le 2026-08-24, bloquait le DNS vers Internet. Or la vérification de
propagation DNS-01 de Caddy interroge directement les serveurs autoritaires sur
le port 53.

Conséquence dépassant largement ClimbContest : **les cinq certificats de
production (expiration 17-18 novembre) n'auraient pas pu être renouvelés** vers
le 18 octobre — juste avant la compétition. Deux règles sortantes, posées après
les DROP du LAN, corrigent les deux problèmes à la fois. Cloisonnement interne
vérifié inchangé.

## IT5 — Exploitation et sauvegarde

- [x] 38. `homelab/scripts/climbcontest` : `start` / `stop` / `status` avec sonde. Depuis le 03/09, `competition` prend l'instantané et `cloture` le retire — plus aucune bascule d'`onboot`
- [x] 39. Sonde `probes/110.sh`
- [x] 40. Procédure en quatre temps — préparer / jour J (avec bascule `onboot`) / corriger en cours / clôturer — jouée **une fois** de bout en bout. **⤫ La bascule `onboot` a disparu le 03/09**
- [x] 41. Exclure la 110 du job `backup-nightly` — fait en IT2, le job était en `all 1`. **⤫ défait le 03/09** : elle y est entrée en même temps qu'elle entrait dans `ADN_GUESTS`
- [x] 42. Vérifier que `adn-watchdog` ne réclame pas sa sauvegarde — **⤫ sans objet depuis le 03/09** : il la réclame, et il la trouve
- [x] 43. ~~Copie de base toutes les 10 min~~ — abandonnée le 28/08, puis **reprise le 29/08** (Q7) : le miroir vers le classeur, sur lequel reposait l'abandon, était cassé en silence. La base est recopiée toutes les dix minutes dans `shared/sauvegardes/`, les 24 dernières conservées
- [x] 44. `README.md` du dossier `vm110-climbcontest` dans `homelab`
- [x] 45. Mettre à jour le parc dans `homelab/README.md` et les notes de migration

---

## Plan de test

### Ce qui est testé, et comment

| Domaine | Scénario | Attendu |
| --- | --- | --- |
| **Cycle de vie** | `pve01` redémarre | VM 110 revient seule (`onboot: 1`) |
| | `qm start 110` | service opérationnel en < 90 s |
| | `qm shutdown 110` | arrêt propre, 4 Go rendus à l'hôte |
| **Livraison** | release valide publiée | installée seule en < 3 min |
| | release qui ne répond pas à `/health` | retour arrière automatique, ancienne version en service |
| | `.sha256` falsifié | refus, journal explicite, rien d'installé |
| | GitHub injoignable | échec silencieux, réessai au tick suivant, service intact |
| | tag sans section CHANGELOG | workflow en échec **avant** construction |
| | 4 releases successives | 3 conservées, la plus ancienne purgée |
| | `climbcontest-rollback` | retour à la release précédente en < 10 s |
| | déploiement déclenché depuis la console ou par `systemctl start climbcontest-deploy.service` | installe la release publiée (plus aucun tick : minuteur retiré le 03/09, spec 031) |
| **Exposition** | `GET /health` depuis le LAN | 200, certificat valide |
| | `GET /health` depuis Internet | **404** |
| | chaque nom `*.maison.adn-dev.fr` | redirige vers le bon chemin public |
| | `GET /.git/config`, `/.env` | 404 |
| | API sans clé | 401 |
| | API avec clé | 200 |
| | `/admin` sans authentification | 401 ou redirection |
| **Charge** | 25 juges + 80 spectateurs × 10 min, **une seule IP source** | 0 erreur, médiane < 200 ms, 0 décision CrowdSec |
| | 300 rafraîchissements/min sur la page publique | CPU < 30 %, calculs plafonnés par le cache |
| | 10 validations simultanées, même grimpeur | aucune erreur 5xx |
| **Contrôles** | gunicorn arrêté | `MachineInjoignable` en < 10 min, comme pour tout invité |
| | fenêtre 05 h 00 | la 110 est mise à jour **en tête** de séquence, sans annuler celle des neuf autres |
| | chien de garde 08 h 00 | réclame sa sauvegarde PBS du jour, et la trouve |
| **Sauvegarde** | instantané `avant-compet` puis retour arrière | base rendue à son état de départ |
| | `vzdump` manuel de fin de compétition | restauration testée dans un VMID jetable |

### Test de charge — comment le faire honnêtement

Le point critique n'est pas le débit, c'est **l'IP source unique**. Un test lancé
depuis dix machines différentes ne prouverait rien : c'est précisément le NAT de
la salle qu'il faut simuler — 25 juges et plus de 100 spectateurs partagent une
seule adresse publique.

```bash
# depuis UNE machine hors du LAN (4G du téléphone en partage, par exemple)
# 25 juges (cycle scan -> scan -> envoi) + 80 spectateurs (rafraichissement 15 s)
python3 tools/charge.py --url https://climbcontest.adn-dev.fr \
        --juges 25 --spectateurs 80 --duree 600
```

Puis, immédiatement :

```bash
ssh adrien@192.168.0.22 'sudo cscli decisions list'   # doit être vide
ssh adrien@192.168.0.22 'sudo cscli alerts list'      # aucun débordement
```

⚠ **Ne pas réutiliser `tests/test_multi_clients.py`** : ces scripts écrivent
réellement dans le classeur de la compétition (risque R11). Le test de charge de
cette spec tape sur `/health` et sur une route factice, rien d'autre.

### Ce qui n'est pas testable maintenant

- Le comportement sous vraie compétition : ne sera validé qu'en novembre.
- `ClimbcontestInjoignableEnService` en conditions réelles de panne : on le
  déclenche à la main, ce qui ne prouve pas qu'il se déclenchera sur une vraie
  panne — même limite que `CorrectifsSecuriteEnAttente` (piège 8 des notes de
  maintenance).

---

## Ce que cette spec prépare pour les suivantes

| Élément posé ici | Utilisé par |
| --- | --- |
| Route `/health` | l'agent de tirage, la sonde, l'alerte |
| Séparation `/api/v2/contest/` — `/api/public/` — `/admin/` | specs 002, 004, 005, 006 |
| Clé d'API sur les routes juges | spec 002 (risque R8) |
| `shared/data/` hors des releases | spec 002 (la base survit aux déploiements) |
| `/admin/participants` | spec 005 — ajouts et réaffectations de dossard à chaud |
| `/admin/impression` | spec 005 — dossards en lot ou à l'unité |
| `/admin/archives` | spec 005 — éditions passées (base multi-compétition) |
| `/admin/utilisateurs` | spec 005 — comptes et rôles, modèle guestFlow |
| `/admin/inscriptions` | spec 008 — import HelloAsso temps réel |
| Cache 5 s sur `/api/public/*` | spec 006 — c'est ce qui rend la page tenable à 100 spectateurs |
| 4 workers gunicorn | ⚠ spec 002 : rend le risque R1 mortel, à traiter |
| Console d'administration protégée | specs 005 (saisie manuelle) et 006 (paramétrage) |
