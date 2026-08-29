# 007 — Architecture

## Où ça vit

Servi par le backend, comme la page de résultats et la console. Pas de second
serveur, pas de build front, **aucune dépendance à installer**.

```
climbcontest/
  templates/juge.html          la coquille
  static/juge/
    juge.js                    l'application
    sw.js                      le service worker
    jsqr.js                    la bibliotheque, VERSEE en clair
    manifest.webmanifest       ce qui la rend installable
    icone-192.png  icone-512.png
  routes/pwa.py                /juge, /juge/sw.js, /juge/manifest
```

Un dossier `static/` apparaît : le projet n'en avait pas. La page de résultats
et la console sont des fichiers uniques, tout en ligne — tenable pour une page,
intenable pour une application avec un service worker, qui **doit** être servi
depuis son propre fichier à la racine de sa portée.

## Le jeton, sans authentification

### Ce que le juge fait

1. il ouvre `https://climbcontest.adn-dev.fr/juge#j=<jeton>` — QR au mur ou
   message dans le groupe des bénévoles ;
2. la page range le jeton et **nettoie l'adresse** ;
3. il ajoute à l'écran d'accueil. Terminé.

Le jeton est dans le **fragment** (`#`), pas dans la requête (`?`) : un fragment
n'est jamais envoyé au serveur, donc il n'entre ni dans les journaux d'accès de
Caddy, ni dans ceux de gunicorn, ni dans un `Referer`. Une adresse avec `?jeton=`
laisserait la trace du secret dans trois fichiers de logs.

### Ce que le serveur fait

Le jeton est une **clé d'API de plus** — le mécanisme de la spec 012 accepte
déjà plusieurs clés :

```
CLIMBCONTEST_API_KEY             l'application Android
CLIMBCONTEST_API_KEY_PWA         la PWA
CLIMBCONTEST_API_KEY_PRECEDENTE  la rotation
```

Trois entrées, une seule vérification. Révoquer la PWA n'est alors qu'une
variable retirée, sans toucher aux téléphones Android — ce que ne permettrait
pas une clé partagée.

⚠️ La coquille HTML et le JavaScript sont servis **publiquement**, sans jeton :
ils ne contiennent aucun secret, et un service worker ne s'installe pas depuis
une page protégée par un cookie de session. Ce qui est gardé, c'est l'API.

## Le stockage

Trois magasins IndexedDB, qui reprennent exactement les fichiers de l'Android :

| Magasin | Équivalent | Contenu |
| --- | --- | --- |
| `file` | `file.jsonl` | les réussites en attente, plus leurs acquittements |
| `historique` | `historique.jsonl` | tous les scans et leur état |
| `reglages` | `appareil.json` | identité, nom, jeton |

**IndexedDB et non `localStorage`** : `localStorage` est synchrone (il bloque le
fil pendant qu'on scanne), plafonné à ~5 Mo, et surtout il ne sait pas faire de
transaction. Or l'invariant central — « une réussite ne quitte la file que si le
serveur a statué » — est une transaction : lire un lot, l'envoyer, acquitter.

### Le verrou entre onglets

Deux onglets ouverts videraient la file en double. Un seul envoie à la fois,
grâce à un bail posé dans `reglages` : identifiant d'onglet + horodatage, repris
s'il a plus de trente secondes. Le même motif que le verrou de schéma côté
serveur, et pour la même raison : un détenteur peut mourir sans rendre son bail.

## Le scan

```js
if ('BarcodeDetector' in window) { /* Chrome Android : natif, rapide */ }
else { /* jsQR sur les images d'un <video> */ }
```

`BarcodeDetector` n'existe pas sur Safari, et n'y existera peut-être jamais. Le
repli n'est donc pas un cas dégradé : c'est **le** chemin des iPhone, celui pour
lequel cette spec existe. Il est donc testé en premier.

jsQR est **versé dans le dépôt en clair**, pas minifié. Une bibliothèque
illisible dans un dépôt public est une bibliothèque que personne ne relira
jamais. Sa licence (MIT) et sa provenance sont notées en tête du fichier.

⚠️ Je n'écris pas mon propre décodeur. J'ai produit cette semaine un encodeur QR
dont les matrices étaient indécodables, et j'ai mis longtemps à admettre que la
faute venait de moi. Un décodeur est plus dur qu'un encodeur.

## Le service worker

Il ne fait **qu'une** chose : servir la coquille hors ligne.

Il ne met **pas** les appels API en cache, et ne rejoue rien. Un service worker
qui rejouerait un `POST` créerait des doublons — l'idempotence serveur les
absorberait, mais la file du téléphone, elle, se croirait vidée. La file est
gérée par l'application, pas par le cache.

## Ce qui bouge côté backend

| Fichier | Nature |
| --- | --- |
| `routes/pwa.py` | nouveau : `/juge`, le manifeste, le service worker |
| `config.py` | `CLIMBCONTEST_API_KEY_PWA` entre dans `API_KEYS` |
| `routes/admin.py` | le QR d'installation, pour l'afficher au mur |

Aucune route API nouvelle : la PWA parle **exactement** le même protocole que
l'Android. C'est voulu — deux clients, un contrat, et les tests de contrat
existants couvrent les deux.

## Itérations

| # | Contenu | Utile seule ? |
| --- | --- | --- |
| IT1 | coquille, jeton, scan, envoi direct | oui : un iPhone peut juger |
| IT2 | catalogue local, file persistante, envoi par lots | oui : hors ligne |
| IT3 | journal, identité, refusés, réglages | parité |
| IT4 | service worker, installable, hors ligne complet | parité |
