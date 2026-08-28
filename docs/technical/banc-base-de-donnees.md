# SQLite ou PostgreSQL — les mesures

Banc réalisé le **28 août 2026**, à la demande d'Adrien : « si PostgreSQL est
plus performant et prend moins de ressources, il faut faire la migration
maintenant plutôt que d'attendre que les interactions soient énormes ».

**Les mesures disent le contraire.** Sur cette charge, SQLite est plus rapide et
moins gourmand. PostgreSQL a été purgé de la VM le jour même.

Ce document existe pour ne pas refaire le banc, et pour savoir **à quelle
condition** il faudrait le refaire.

---

## Conditions

| | |
| --- | --- |
| Machine | VM 110, 4 vCPU / 4 Go, Debian 13 — l'environnement réel, pas un poste de dev |
| Code | branche `feat/002-reliable-success-storage`, inchangé entre les deux essais |
| Serveur | gunicorn 4 workers × 4 threads (la configuration de production) |
| SQLite | `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL` |
| PostgreSQL | 17.11 Debian, réglages par défaut, `psycopg2` |
| Base | recréée vide avant **chaque** essai |
| Client | fils Python sur la VM — pas 800 processus `curl`, qui affamaient le serveur |

---

## Écritures pures — 1600 réussites distinctes, 40 en parallèle

| | médiane | p95 | max | débit | RAM gunicorn | RAM serveur DB |
| --- | --- | --- | --- | --- | --- | --- |
| **SQLite/WAL** | **25,9 ms** | **82,4 ms** | 448,8 ms | **1127 req/s** | 240 Mo | **0** |
| PostgreSQL | 46,7 ms | 91,6 ms | **118,0 ms** | 788 req/s | 288 Mo | 74 Mo |

## Lectures pendant écritures — 10 juges + 40 spectateurs, 20 s

C'est le scénario de la page résultats (spec 006) : celui où SQLite pourrait
souffrir, puisque dans son mode par défaut un écrivain bloque les lecteurs.

| | lectures servies | médiane lecture | p95 lecture | écritures |
| --- | --- | --- | --- | --- |
| **SQLite/WAL** | **9 510** | **75,6 ms** | **172,1 ms** | 1 600 |
| PostgreSQL | 4 776 | 136,4 ms | 383,4 ms | 1 555 |

WAL fait exactement ce qu'on attend de lui : les lectures ne sont pas bloquées.

---

## Ce que les chiffres disent

**PostgreSQL n'est ici ni plus rapide ni moins gourmand.** 43 % plus lent en
débit, deux fois plus lent sur la médiane, et **~120 Mo de RAM en plus**
(74 Mo de serveur + 48 Mo de pools de connexions côté gunicorn).

La raison est structurelle, pas conjoncturelle : PostgreSQL paie un aller-retour
réseau et une négociation de protocole à chaque requête. SQLite est une
bibliothèque **dans le processus** — ni socket, ni processus séparé. À notre
échelle, ce coût fixe domine tout ce que PostgreSQL peut regagner par ailleurs.

Le seul point où PostgreSQL gagne : **la latence maximale** en rafale
d'écritures, 118 ms contre 449 ms. Il est plus régulier. Mais c'est une queue de
distribution mesurée sur une charge 200 fois supérieure au réel.

### La marge réelle

| | |
| --- | --- |
| Débit mesuré | **1127 req/s** |
| Pointe estimée un jour de compétition | **~6 req/s** ([contraintes-metier §3 bis](../contraintes-metier.md)) |
| Marge | **×180** |

Et au test de charge grandeur nature de la spec 001 — 25 juges + 80 spectateurs,
368 req/min — la VM était à **0,03 de charge**.

À 1127 req/s, le facteur limitant est **Python et gunicorn**, pas la base.
Changer de base n'améliorerait donc pas le débit.

---

## ⚠️ Une erreur de banc, à ne pas reproduire

Le premier essai mixte affichait **1730 erreurs pour SQLite et zéro pour
PostgreSQL**. Pris au mot, ce chiffre justifiait la migration à lui seul.

Il ne venait pas de SQLite. Le harnais numérotait les couples
`participant = (i // 40) + 1`. SQLite ayant été plus rapide, il a épuisé les
1600 couples valides et continué sur des dossards 41, 42… qui n'existent pas et
répondent `400` — exactement comme prévu. `1600 + 1730 = 3330` tentatives, le
compte est exact. PostgreSQL, plus lent, n'a jamais atteint la limite.

**Un banc dont le client se comporte différemment selon la vitesse du serveur ne
mesure pas ce qu'on croit.** Deux autres pièges rencontrés :

- **Client trop lourd.** 800 processus `curl` lancés par `xargs -P 40` sur une VM
  à 4 vCPU affament le serveur : on mesure le client. Corrigé par un client à
  fils.
- **Comparaison inéquitable.** Un premier essai rejouait des réussites déjà
  existantes (un simple `SELECT`, sortie anticipée par idempotence) tandis que
  l'autre faisait de vraies insertions. Base neuve et couples tous distincts à
  chaque essai.

---

## Décision

**SQLite**, avec les réglages posés dans
[`climbcontest/sqlite_reglages.py`](../../climbcontest/sqlite_reglages.py) :

```
journal_mode = WAL          13× plus rapide que le mode par defaut (mesure separee)
busy_timeout = 5000         attendre plutot qu'echouer sur « database is locked »
synchronous  = NORMAL       plus de fsync a chaque transaction
foreign_keys = ON           SQLite ne l'applique PAS par defaut
```

`foreign_keys` mérite une mention à part : sans lui, une réussite pouvait
pointer vers un participant supprimé. Ce n'est pas une optimisation, c'est une
correction.

PostgreSQL a été **purgé** de la VM le 28/08 (paquets, données, compte système).

Le code reste agnostique : `CLIMBCONTEST_DATABASE_URI` accepte les deux, et
`sqlite_reglages.py` ne s'applique qu'aux connexions SQLite. Rebasculer coûterait
une variable d'environnement et `apt install postgresql`.

---

## Quand refaire ce banc

Un seul scénario le justifie, et il est identifié : **la page résultats de la
spec 006**, si elle recalcule le classement en continu pendant que les juges
écrivent, et qu'on voit la latence de lecture monter.

Le signal à surveiller : la médiane de lecture sur `/api/public/*` qui dépasse
~200 ms en compétition. Le cache de 5 s posé dans le Caddyfile devrait
l'empêcher — il plafonne le calcul à 12 fois par minute quel que soit le nombre
de spectateurs — mais c'est à vérifier sur le vrai code, pas à supposer.

Les scripts du banc ne sont pas versionnés : ils étaient jetables et dépendaient
d'un jeu de données temporaire. Ce document contient tout ce qu'il faut pour les
réécrire.
