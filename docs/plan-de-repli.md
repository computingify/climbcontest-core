# Plan de repli — revenir à la version qui marche

> **À quoi ça sert** : si la refonte n'est pas prête pour la compétition, ou si
> elle se comporte mal le jour J, ce document permet de remettre en service la
> version 2025-2026 en une trentaine de minutes, sans réfléchir.

Gel réalisé le **28 août 2026**.

---

## 1. Ce qui est gelé, et où

### Le code — en trois exemplaires

| Version | Tag git | Commit | Où |
| --- | --- | --- | --- |
| Backend en production | `V2.1.1` | `3248abc` | GitHub `computingify/climbcontest-core` — **poussé le 28/08** ✅ |
| App juge (source en cours) | `V3.1.4` | `5404a3f` | GitHub `computingify/ClimbContest` — tag poussé ✅ |
| App juge (version Play Store) | `V3.1.3` | `16ab890` | GitHub `computingify/ClimbContest` — tag poussé ✅ |

Plus une copie hors-ligne complète, historique inclus, dans
`archive/gel-2026-08/code/` sous forme de *git bundles* — un fichier unique par
dépôt, restaurable sans réseau :

```bash
git clone archive/gel-2026-08/code/climbContestServer-V2.1.1.bundle serveur-repli
git clone archive/gel-2026-08/code/ClimbContest-V3.1.4.bundle app-repli
```

### L'application installable

`archive/gel-2026-08/app/`

| Fichier | Usage |
| --- | --- |
| `ClimbContest-3.1.4-release.apk` | **Installable directement** sur un téléphone Android (sideload). C'est le filet de sécurité si le Play Store pose problème. |
| `ClimbContest-3.1.4-playstore.aab` | Le bundle de publication d'origine. |

L'APK est signé avec la clé de debug (c'est ce que fait `build.gradle.kts`
aujourd'hui) : il s'installe hors Play Store en autorisant les sources inconnues,
mais **ne peut pas remplacer par mise à jour** une app installée depuis le Play
Store — il faut désinstaller d'abord.

### Les secrets — le vrai point de fragilité

`archive/gel-2026-08/secrets/`

| Fichier | Rôle | Sans lui |
| --- | --- | --- |
| `token.pickle` | Jeton OAuth Google Sheets | Le backend ne peut plus écrire dans le classeur |
| `token.base64` | Le même, encodé pour Render | Idem en hébergement distant |
| `credentials.json` | Client OAuth Google | Impossible de refabriquer un jeton |
| `security/cert.pem`, `key.pem` | Certificat auto-signé (mode Raspberry Pi) | HTTPS local indisponible |

Ces fichiers ne sont dans **aucun dépôt git** — volontairement. Ils n'existaient
jusqu'ici que sur ce Mac.

> ⚠ **Action à faire de ta main** : copier `archive/gel-2026-08/secrets/` sur un
> support hors de ce Mac — NAS, gestionnaire de mots de passe, disque chiffré.
> Une archive qui vit sur la seule machine qu'elle protège n'est pas une
> sauvegarde. Le reste de l'archive (code, APK) est redondé sur GitHub&nbsp;;
> les secrets, non.

### Les données des éditions précédentes

`archive/gel-2026-08/dump_*.json` — export intégral des trois classeurs
(valeurs **et** formules), figé au 28 août 2026 :

| Fichier | Classeur | Contenu |
| --- | --- | --- |
| `dump_1h3e8QUSXnCJ.json` | U11 U15 Mars 2026 | celui que vise le code aujourd'hui |
| `dump_1ilQ2-ogmTfp.json` | U11 U17 Nov 2025 | **1003 réussites réelles** |
| `dump_1lOWe3j-4KG6.json` | Édition 2024 | 1678 réussites réelles |

---

## 2. Redémarrer le backend de repli

### Option A — Render (le plus rapide si le service existe encore)

1. Vérifier que le service `climbcontest-core` répond&nbsp;:
   `curl -m 60 https://climbcontestserver.onrender.com/api/v2/contest/worker-status`
2. Sur Render, déployer le tag `V2.1.1` (branche `master` si elle n'a pas bougé).
3. Vérifier que la variable d'environnement contenant le jeton Google est
   toujours en place (le code lit `token.pickle`, sinon `token.base64`).

### Option B — Machine locale ou VM (indépendant de Render)

```bash
git clone archive/gel-2026-08/code/climbContestServer-V2.1.1.bundle serveur-repli
cd serveur-repli && git checkout V2.1.1
cp -r ../archive/gel-2026-08/secrets/token.pickle .
cp -r ../archive/gel-2026-08/secrets/credentials.json .
mkdir -p security && cp ../archive/gel-2026-08/secrets/security/*.pem security/

python3 -m venv venv && source venv/bin/activate
pip install -r deployement/requirements.txt
python main.py          # écoute en HTTPS sur le port 5007
```

L'app juge pointe en dur sur Render&nbsp;: pour la faire parler à un serveur
local, il faut modifier `sendPostToServer()` dans `Server.kt` et recompiler.
**C'est le point de rigidité le plus gênant de la version gelée** — à garder en
tête dans le choix de l'option.

---

## 3. ⚠ Le PREMIER geste : rouvrir l'API aux anciens téléphones

Depuis la spec 012, le backend **exige une clé d'API** des applications juges.
Le gel `V3.1.4` — celui vers lequel ce plan replie — **n'en envoie aucune**.

Y revenir sans rien faire d'autre donnerait donc, sur chaque téléphone, un
`401` à chaque envoi. Les réussites ne seraient pas perdues (l'application garde
sa file et réessaie), mais **rien n'arriverait sur le serveur**, et la seule
trace serait dans le journal.

Sur la VM 110, **avant** de remettre l'ancienne version en service :

```bash
ssh adrien@192.168.0.32
sudo systemctl edit climbcontest        # ou le fichier d'environnement du service
#   Environment=CLIMBCONTEST_API_KEY_STRICTE=0
sudo systemctl restart climbcontest
curl -s http://127.0.0.1:8000/health | python3 -m json.tool | grep regime
#   "regime": "tolere"      <- c'est ce qu'on veut voir
```

Vérification que ça a bien pris, sans clé :

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST https://climbcontest.adn-dev.fr/api/v2/contest/climber/name \
  -H 'Content-Type: application/json' -d '{"id":"1"}'
#   201  -> l'ancienne application peut de nouveau travailler
#   401  -> la variable n'a pas ete prise en compte, recommencer
```

> **Pourquoi c'est en tête de ce document** : c'est une étape qui n'existait pas
> avant, qui ne se voit nulle part, et qu'on découvrirait au pire moment — vingt
> juges qui scannent et un classement qui ne bouge pas.

Le régime redevient strict en retirant la variable et en redémarrant.

---

## 4. ⚠ Le geste à ne pas oublier : changer le classeur

`climbcontest-core/google_sheets.py`, ligne 12 :

```python
SPREADSHEET_ID = '1h3e8QUSXnCJLSYSFyB8X92cppDubeDx0yi8mn3NSh5s'
```

**Cet identifiant est en dur.** Pour une nouvelle compétition, il faut le
remplacer par celui du nouveau classeur et redéployer. Sans ça, les réussites
partent dans le classeur de mars 2026.

Où trouver l'identifiant : dans l'URL du classeur, entre `/d/` et `/edit`.

Deux autres points de vigilance sur la version gelée :

- le backend attend l'onglet `Plan` avec les blocs à partir de la **ligne 29**
  et l'onglet `Listes` à partir de la **ligne 2**. Si le nouveau classeur décale
  ces lignes, l'import échoue silencieusement&nbsp;;
- un grimpeur dont la ligne `Listes` n'a pas exactement 6 colonnes remplies
  (F à K) est **ignoré sans message** (risque R5 de l'état des lieux). Vérifier
  que club et catégorie sont saisis pour tout le monde.

---

## 5. Vérification avant le jour J

À faire une fois, quelques jours avant, pas le matin même :

- [ ] Le backend répond&nbsp;: `POST /api/v2/contest/climber/name` avec un dossard connu → `201`
- [ ] Un `POST /api/v2/contest/success` de test fait bien apparaître un `A` dans l'onglet `Import`
- [ ] La ligne de test est ensuite effacée du classeur
- [ ] L'app scanne un QR grimpeur et un QR bloc, et l'envoi affiche « Validé »
- [ ] Le `SPREADSHEET_ID` pointe sur le bon classeur (§3)
- [ ] Les secrets sont bien présents sur une machine *autre* que ce Mac

---

## 6. Reste à faire (une action de ta part)

- [x] ~~Pousser le tag `V2.1.1`~~ — **fait le 28/08**.
- [ ] **Copier `archive/gel-2026-08/secrets/` hors de ce Mac** (NAS, gestionnaire
      de mots de passe, disque chiffré). C'est la seule partie du gel qui n'est
      redondée nulle part : le code est sur GitHub, l'APK est reconstructible,
      les secrets non.

> Note : le dépôt a été renommé `climbContestServer` → **`climbcontest-core`** le
> 28/08. GitHub redirige les anciennes URL, mais les commandes de ce document
> utilisent le nouveau nom.
