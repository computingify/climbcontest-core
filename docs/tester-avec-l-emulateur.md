# Tester

> ⚠️ **L'émulateur n'est pas le socle de test.** Il s'est révélé instable sur la
> machine de développement — crash QEMU au démarrage, `GPU: UNKNOWN`, avec ou
> sans fenêtre. Les garanties reposent donc sur des tests qui **n'en ont pas
> besoin** :
>
> | Quoi | Où | Combien | Durée |
> | --- | --- | --- | --- |
> | Couche réseau de l'application | `climbcontest-android`, JVM + serveur factice | 17 | ~5 s |
> | Backend, unitaire | `tests/test_*.py`, base en mémoire | 69 | ~1 s |
> | Backend, **bout en bout** | `tests/test_e2e.py`, vrai gunicorn, vraie base | 16 | ~17 s |
>
> ```bash
> cd climbcontest-core    && python -m pytest tests/
> cd climbcontest-android && ./gradlew testDebugUnitTest
> ```
>
> L'émulateur reste utile pour ce que ces tests ne couvrent pas : **l'interface**
> — la caméra, les gros boutons, ce que voit le juge. Le reste de cette page
> décrit cette boucle-là, quand l'émulateur veut bien démarrer.

## La boucle avec l'émulateur

Un backend sur le Mac, l'application dans l'émulateur Android Studio. Deux
commandes, rien à configurer.

---

## En deux terminaux

**Terminal 1 — le backend**

```bash
cd climbcontest-core
./scripts/dev-server.sh
```

Il crée son environnement Python au premier lancement, peuple une compétition
réaliste, et affiche les requêtes au fur et à mesure. `--neuf` repart d'une base
vide.

**Terminal 2 — l'application**

```bash
cd climbcontest-android
./gradlew installDebug
```

C'est tout. L'application compilée en debug pointe déjà sur
`http://10.0.2.2:5007` — l'adresse par laquelle l'émulateur voit le Mac.

---

## Le jeu de données

Reprend la **structure** de novembre 2025 avec des noms fictifs :

| | |
| --- | --- |
| Participants | 98 avec dossard (1 à 98) |
| Blocs | 67, répartis sur 5 zones |
| Circuits | U11, U13, U15, U17 |
| Catégories | les 8, filles et garçons |
| QR codes de bloc | `ZJ1`, `ZJ2`, `ZV3`… — la vraie convention zone + couleur + rang |
| QR codes de grimpeur | le dossard, `1` à `98` |

Deux cas limites sont dans le jeu volontairement, pour ne pas avoir à les
fabriquer :

- **un inscrit absent, sans dossard** — celui dont on peut reprendre le numéro ;
- **un homonyme dans un autre club** — le cas qui faisait échouer tout l'import
  dans l'ancienne version. C'est le dossard **99**, jumeau du dossard **1** :
  même nom, même prénom, club différent. Les 98 autres identités sont toutes
  distinctes, et le script le vérifie au démarrage.

La graine aléatoire est fixe : le jeu est le même à chaque fois.

---

## Scanner sans imprimer de QR code

L'émulateur n'a pas de vraie caméra, mais il en simule une : elle filme une
**scène 3D virtuelle** dans laquelle on peut afficher une image.

1. Générer un QR code contenant `12` (un dossard) ou `ZJ1` (un bloc).
2. Dans l'émulateur : **⋯ → Camera → Add image** et charger le QR code.
3. Lancer le scan dans l'application, viser le mur virtuel avec les touches
   `WASD`.

Plus rapide au quotidien, et c'est ce que je recommande pour l'essentiel des
tests : **frapper l'API directement** pendant que l'application tourne, pour
vérifier le comportement du backend, et ne se servir de l'émulateur que pour ce
qui touche à l'interface.

```bash
curl -X POST localhost:5007/api/v2/contest/success \
     -H 'Content-Type: application/json' \
     -d '{"bib":"12","bloc":"ZJ1"}'
```

---

## Viser un autre backend

L'adresse n'est plus une constante dans le code : elle vient de
`BuildConfig.SERVER_URL`, posée par le type de build et surchargeable en ligne
de commande.

```bash
# la VM 110 par son adresse publique (VM allumee)
./gradlew installDebug -PserverUrl=https://climbcontest.adn-dev.fr

# la VM en direct sur le LAN, depuis un telephone reel
./gradlew installDebug -PserverUrl=http://192.168.0.32:5007

# Note : `serverUrl` n'agit QUE sur les builds debug. Un build release lit
# `releaseServerUrl`, et refuse toute adresse qui n'est pas en https. Deux noms
# distincts, pour qu'une valeur posée un jour dans gradle.properties ne puisse
# pas se retrouver, trois semaines plus tard, dans un APK du Play Store.

# production (aucune surcharge)
./gradlew assembleRelease
```

> ⚠️ Le port `5007` de la VM n'est ouvert que depuis `edge`. Pour l'atteindre en
> direct depuis le LAN, il faudrait ajouter une règle dans `110.fw` — ce qui n'a
> pas été fait, volontairement. Passer par l'adresse publique.

---

## Ce que ça a changé dans l'application

Trois choses, sur la branche `feat/emulator-test-config` :

**L'adresse du serveur devient un paramètre de build.** Avant, deux constantes
(`RUN_LOCAL_SERVER`, `RUN_ON_EMULATOR`) qu'il fallait éditer dans le code et
recompiler. Le mode local visait `https://10.0.2.2` — HTTPS sur le port 443, sans
gestionnaire de confiance : un certificat auto-signé aurait été refusé. **Ce mode
ne pouvait pas fonctionner en l'état.**

**Le HTTP en clair est autorisé, uniquement en debug**, et uniquement vers
`10.0.2.2`, `192.168.0.32` et `localhost`. Le fichier vit dans le jeu de sources
`debug` : le build release ne le voit pas. Vérifié — le manifeste du release ne
contient aucune référence à cette configuration.

**La vérification du nom d'hôte TLS est rétablie.** `hostnameVerifier { _, _ ->
true }` acceptait n'importe quel certificat valide pour n'importe quel domaine :
une interception sur un réseau hostile passait sans bruit. C'était le risque R10
de l'[état des lieux](etat-des-lieux.md). Le développement local n'en a plus
besoin puisqu'il passe en HTTP en clair.

---

## Ce qui a été vérifié, et ce qui reste à confirmer

| | |
| --- | --- |
| L'APK debug se construit | ✅ |
| `BuildConfig.SERVER_URL` vaut `http://10.0.2.2:5007` en debug | ✅ |
| La surcharge `-PserverUrl=` fonctionne, **y compris en clair** | ✅ vérifié : `assembleDebug -PserverUrl=http://192.168.0.32:5007` produit bien cette adresse |
| `-PserverUrl=` ne peut **pas** contaminer un build release | ✅ le release lit `releaseServerUrl`, une propriété distincte |
| Un build release refuse une adresse non-https | ✅ `-PreleaseServerUrl=http://…` échoue à la compilation |
| Le build release garde HTTPS et **n'embarque pas** la config cleartext | ✅ vérifié dans le manifeste de l'APK |
| Le backend de dev répond exactement ce que l'app attend | ✅ les 3 routes testées |
| **L'application dans l'émulateur atteint le backend** | ⏳ **à confirmer** |

La dernière ligne demande un émulateur **avec fenêtre**. En mode `-no-window` sur
Apple Silicon, il plante sur OpenGL — je n'ai pas voulu ouvrir une fenêtre sur
ton écran pour le vérifier. C'est un test d'une minute la prochaine fois que tu
lances l'émulateur depuis Android Studio : le backend affiche chaque requête,
tu verras le scan arriver.

## Dépannage

| Symptôme | Cause probable |
| --- | --- |
| « Aucun accès au serveur » dans l'app | le backend n'est pas lancé, ou pas sur le port 5007 |
| Erreur réseau alors que `curl` marche depuis le Mac | l'application a été compilée en `release`, pas en `debug` |
| « Grimpeur inconnu » sur un dossard valide | mauvaise base — relancer avec `--neuf` |
| L'émulateur ne voit rien sur `10.0.2.2` | le backend n'est pas lancé. `10.0.2.2` pointe sur la **boucle locale** du Mac : l'écoute sur `127.0.0.1` suffit, pas besoin de `--reseau` |
| Un téléphone **physique** ne voit rien | il passe par le wifi, pas par la boucle locale : lancer `dev-server.sh --reseau` et viser l'IP du Mac |
| Le scan ne s'ouvre pas | ML Kit télécharge son module au premier lancement — il faut que l'émulateur ait accès à Internet et aux services Google Play (choisir une image système **avec Play Store**) |
| L'émulateur ne répond plus à `adb` | ne pas le lancer en `-no-window` sur Apple Silicon : il plante sur OpenGL (`swiftshader_indirect`). Le lancer depuis Android Studio, avec sa fenêtre |

L'avant-dernière ligne compte pour le choix de l'image :
l'application utilise **ML Kit via Google Play Services**. Une image « AOSP »
sans Play Services ne pourra pas ouvrir le scanner.
