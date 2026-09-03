# Architecture : 031 — Mettre à jour depuis la console

## 1. Le partage des rôles

Rien de ce qui installe n'est réécrit. `/usr/local/bin/climbcontest-deploy`
reste le seul code qui télécharge, vérifie l'empreinte SHA-256, bascule le lien
`current`, sonde `/health` et revient en arrière. Python **décide et délègue**.

```
console (admin.html)
   │  GET /admin/maj              ← déclenche la vérification quotidienne
   │  POST /admin/maj/verifier    ← force l'appel
   │  POST /admin/maj/installer   ← lance, et rend la main
   ▼
routes/admin.py  ──►  climbcontest/maj.py
                          │  requests.get(api.github.com/…/releases/latest)
                          │  reglage[maj_verification]  ← ce qu'on sait
                          │  reglage[maj_installation]  ← ce qu'on a demandé
                          ▼
                      sudo systemctl start --no-block climbcontest-deploy.service
                          ▼
                      /usr/local/bin/climbcontest-deploy   (inchangé)
```

## 2. L'état, en base

Deux clés dans la table `reglage`, et non deux fichiers :
`climbcontest-sauvegarde` ne recopie que la base. Un JSON posé à côté serait le
seul fichier sans sauvegarde — c'est le raisonnement déjà écrit sur le modèle
`Reglage` pour le plan du mur.

| Clé | Contenu |
| --- | --- |
| `maj_verification` | `{fait_le, tag, changelog, publiee_le, erreur?}` |
| `maj_installation` | `{tag, demandee_le}` |

**L'issue d'une installation n'est pas stockée : elle se lit.** `VERSION` dit ce
qui tourne vraiment, `.failed-tag` ce que l'agent a refusé après sa sonde. Un
état recopié à la main mentirait le jour où le processus est tué entre les deux
écritures — ce qui est précisément ce qui arrive ici, puisque le déploiement
redémarre l'application.

## 3. Les contrats

### `GET /admin/maj` — `@exige_role(ADMIN)`

```json
{
  "success": true,
  "en_service": "v0.16.0",
  "verifie_le": "2026-09-03T08:12:00+00:00",
  "erreur": null,
  "disponible": { "tag": "v0.17.0", "publiee_le": "…", "changelog": "…" },
  "blocage": "Compétition en cours (Bloc de novembre) — installation bloquée.",
  "installation": { "tag": "v0.17.0", "etat": "en_cours" }
}
```

`disponible`, `erreur`, `blocage` et `installation` valent `null` quand ils ne
s'appliquent pas. `blocage` n'est calculé que s'il y a quelque chose à
installer : dire « bloqué » quand il n'y a rien à faire serait du bruit.

### `POST /admin/maj/verifier` — même corps, appel forcé.

### `POST /admin/maj/installer` — `{"tag": "v0.17.0"}` → **202**

Refus en **409** : compétition en cours, aucune version connue, ou tag différent
de la dernière version connue.

## 4. Le droit de démarrer le service

L'application tourne sous le compte `climbcontest`, comme le service de
déploiement. Elle ne l'exécute pas elle-même : elle demande à systemd, ce qui
conserve le journal, le type `oneshot` et le cloisonnement de l'unité.

Une quatrième entrée dans `/etc/sudoers.d/climbcontest` :

```
climbcontest ALL=(root) NOPASSWD: …, /bin/systemctl start --no-block climbcontest-deploy.service
```

⚠️ Les arguments sont listés **en entier**. `sudo` compare la ligne de commande
complète : cette autorisation ne permet pas de démarrer un autre service.

## 5. La console

| Élément | Où | Visible quand |
| --- | --- | --- |
| `#pastilleMaj` | `.barre .droite` | une version est disponible, et aucune installation en cours |
| `#blocMaj` | en tête de `#vueReglages` | l'utilisateur est administrateur |
| `#dlgMaj` | à côté de `#dlgConfirmer` | au clic sur « Installer » |

**`#dlgMaj` est une fenêtre à part, et pas `dlgConfirmer`.** Celle-ci confirme un
geste **réversible** : l'agent sonde `/health` et revient en arrière tout seul.
Le maintien de deux secondes de la spec 018 est réservé à ce qui efface.

**Le suivi passe par `fetch` et non par `appeler`.** Pendant l'installation les
requêtes échouent une quinzaine de secondes ; le traitement des 401 de `appeler`
déconnecterait l'utilisateur au pire moment.

**La pastille de couleur ne porte jamais seule** : le verdict est écrit à côté.
Même règle que le voyant de connexion de l'app juge.

## 6. Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/maj.py` | **nouveau** — la décision |
| `climbcontest/routes/admin.py` | trois routes, deux imports |
| `climbcontest/templates/admin.html` | pastille, carte, fenêtre, styles, JS |
| `deployment/climbcontest-deploy.timer` | **supprimé** |
| `deployment/install.sh` | plus d'installation du minuteur, sudoers élargi |
| `deployment/climbcontest-deploy` | un commentaire qui parlait du minuteur |
| `tests/test_maj_serveur.py` | **nouveau** — 21 tests |

Côté `homelab` : mêmes suppressions dans `vm110-climbcontest/deployment/`, et le
tableau de `vm110-climbcontest/README.md`.
