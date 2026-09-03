# Plan — Spec 014

Branche : `feat/jeton-juge-dans-le-lien`.
**Rien n'est écrit avant la validation de la spec (porte 2).**

## IT1 — Le choix du jeton

- [ ] `jeton.js` : `choisirJeton(requete, fragment, jetonRange)`, requête prioritaire
- [ ] `juge.js` : appel mis à jour, nettoyage conditionné au mode d'affichage
- [ ] `tests/js/jeton.test.mjs` : les cas ci-dessous

## IT2 — Le manifeste dynamique

- [ ] `pwa.py` : manifeste rendu, `start_url` porteur du jeton, `scope` inchangé
- [ ] `manifest.webmanifest` devient un gabarit
- [ ] `juge.html` : le `<link rel="manifest">` transmet le jeton
- [ ] `sw.js` : le manifeste sort de `COQUILLE`
- [ ] `tests/test_pwa_juge.py` : les cas de route

## IT3 — Le lien produit par la console

- [ ] `/admin/lien-juge` produit `?j=` au lieu de `#j=`
- [ ] Le QR est régénéré à partir de cette adresse

## IT4 — Le proxy

- [ ] Caddyfile d'`edge` : filtre de journal sur `j`
- [ ] `caddy validate` **avant** rechargement, sauvegarde datée du fichier
- [ ] Vérification : une requête avec `?j=` n'écrit pas la clé dans `access.log`

## IT5 — L'essai réel

- [x] Installation sur un **vrai téléphone** depuis le QR
- [x] Fermeture, relance depuis l'icône : **aucun message de jeton manquant**
- [x] Un scan de bout en bout — fait, et refait plusieurs fois depuis
- [x] Même essai sur Android, en non-régression

## IT6 — Documentation

- [ ] `docs/specs-index.md` : la ligne 014
- [ ] `CHANGELOG.md`
- [ ] `docs/runbook-competition.md` : la procédure d'installation d'un bénévole
- [ ] `specs/007-pwa-juge/` : une note renvoyant vers 014, le fragment n'étant plus le seul chemin

## Plan de test

### `tests/js/jeton.test.mjs`

| Requête | Fragment | Rangé | Jeton retenu | Écrit ? | Ce que ça protège |
| --- | --- | --- | --- | --- | --- |
| `?j=A` | — | — | `A` | oui | le nouveau chemin |
| — | `#j=A` | — | `A` | oui | l'ancien, toujours valide |
| `?j=A` | `#j=B` | — | `A` | oui | la requête prime |
| — | — | `A` | `A` | non | **le lancement depuis l'icône ne perd rien** |
| `?j=` | — | `A` | `A` | non | une requête vide n'efface pas |
| `?j=B` | — | `A` | `B` | oui | changer de clé par un nouveau lien |
| — | — | — | `null` | non | le message « besoin du lien » reste juste |

La quatrième ligne est celle du défaut corrigé : c'est le cas de tous les jours.

### `tests/test_pwa_juge.py`

| Appel | Attendu |
| --- | --- |
| `GET /juge/manifest.webmanifest` | `start_url` = `/juge`, JSON valide |
| `GET /juge/manifest.webmanifest?j=X` | `start_url` = `/juge?j=X` |
| `GET /juge/manifest.webmanifest?j=` | comme sans paramètre |
| `GET /juge/manifest.webmanifest?j=a b&c` | jeton correctement échappé dans l'URL |
| `GET /juge?j=X` | le HTML lie le manifeste **avec** `?j=X` |
| `GET /juge` | le HTML lie le manifeste nu |
| Content-Type du manifeste | `application/manifest+json` |
| `GET /admin/lien-juge` | l'URL contient `?j=`, le QR l'encode |

### Non-régression

- `pytest` en entier
- `node --test "tests/js/*.test.mjs"`
- `GET /juge` répond 200 et la PWA démarre sans jeton, avec son message

### Vérification sur le proxy

```bash
curl -s "https://climbcontest.adn-dev.fr/juge?j=UN-FAUX-JETON" -o /dev/null
pct exec 101 -- grep -c "UN-FAUX-JETON" /var/log/caddy/access.log   # doit valoir 0
```

C'est le critère A9, et il se vérifie en deux commandes.
