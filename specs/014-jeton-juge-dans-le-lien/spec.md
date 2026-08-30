# Spec 014 — Le jeton du juge survit à l'installation

> **Statut : rédigée, en attente de validation (porte 2).**
> Demandée par Adrien le 30/08/2026, après l'essai d'installation de la PWA.

## 1. Le symptôme

L'application juge installée sur l'écran d'accueil affiche, à l'ouverture :

> Cette application a besoin du lien fourni par l'organisateur.

Elle est pourtant installée depuis le lien qui contient le jeton.

## 2. Ce qui se passe vraiment

**Le jeton est déjà dans le QR.** `/admin/lien-juge` produit
`https://climbcontest.adn-dev.fr/juge#j=<clé>` : la demande « mettre le jeton
dans le QR » est donc **déjà satisfaite**. Ce n'est pas là qu'est le défaut.

Le défaut est que **deux endroits de notre propre code effacent ce jeton entre
le scan du QR et le lancement de l'application installée.**

### Cause 1 — l'adresse est nettoyée aussitôt

`static/juge/juge.js`, dans `installerLeJeton()` :

```js
if (location.hash) {
  history.replaceState(null, "", location.pathname);   // le #j= disparaît
}
```

L'intention est bonne et documentée : ne pas laisser le jeton dans la barre
d'adresse, l'historique et les captures d'écran. Mais le nettoyage est
**immédiat**. Le bénévole scanne le QR, la page s'ouvre, l'adresse redevient
`/juge` — et c'est cette adresse-là, sans jeton, que « Sur l'écran d'accueil »
capture s'il fait le geste à ce moment.

### Cause 2 — `start_url` ne porte aucun jeton

`static/juge/manifest.webmanifest` :

```json
"start_url": "/juge",
"scope": "/juge",
```

L'application lancée depuis son icône ouvre donc **toujours** `/juge` nu. Elle
ne peut retrouver son jeton que dans son stockage local. Tout repose sur ce
stockage.

### Pourquoi ça marche sur Android et pas sur iPhone

Sur Android, l'application installée **partage** le stockage de Chrome : le
jeton rangé pendant la navigation est encore là. Sur iPhone, une application
ajoutée à l'écran d'accueil possède **son propre stockage**, séparé de Safari.
Le jeton rangé dans Safari lui est invisible : elle démarre vide, sans jeton, et
affiche le message.

> Les deux causes ci-dessus sont **certaines** — elles se lisent dans le code.
> Le cloisonnement du stockage iOS est l'explication la plus probable du reste,
> et se confirme d'un essai : la même installation sur Android doit fonctionner.
> Le correctif proposé ici **ne dépend pas** de cette confirmation : il supprime
> la dépendance au stockage sur toutes les plateformes.

## 3. Ce qu'on fait

Le jeton passe du **fragment** (`#j=`) à la **requête** (`?j=`), et le manifeste
devient **dynamique** pour que `start_url` le porte.

```
QR / lien       https://climbcontest.adn-dev.fr/juge?j=<clé>
manifeste       /juge/manifest.webmanifest?j=<clé>
  start_url     "/juge?j=<clé>"
```

Conséquence : **l'application lancée depuis son icône reçoit son jeton dans son
adresse, à chaque lancement.** Elle ne dépend plus d'un stockage qui peut être
cloisonné, vidé, ou perdu. C'est exactement ce qu'Adrien a demandé — « à chaque
fois ce sera le même token » —, mené jusqu'au bout de la chaîne.

Le fragment `#j=` **reste accepté** : les installations déjà faites continuent
de fonctionner, et un lien ancien ne devient pas mort.

## 4. Ce que ça coûte, dit franchement

Un fragment n'est pas envoyé au serveur ; une requête l'est. Le jeton
apparaîtrait donc dans le journal d'accès de Caddy et dans celui de gunicorn —
**c'est précisément ce que le choix du fragment évitait**, et c'est écrit noir
sur blanc dans `jeton.js`.

La parade est dans Caddy (v2.11.4 sur `edge`, qui sait le faire) : le paramètre
`j` est **masqué dans le journal** par un filtre, sur ce seul hôte. L'adresse
reste diagnosticable, la clé n'y figure pas.

Côté gunicorn, le journal d'accès porte la ligne de requête complète. Deux
options, à trancher (**question ouverte Q1**) : réduire le format de log de
gunicorn, ou accepter que la clé figure dans le journal de la VM — machine sur
laquelle la clé est de toute façon présente en clair dans
`shared/secrets/env`.

> À garder en tête pour proportionner l'effort : **ce jeton est affiché au mur
> sous forme de QR**. Quiconque le photographie l'a. Il arrête un robot qui
> balaie Internet, pas quelqu'un présent dans la salle. La protection contre les
> journaux est utile, elle n'est pas la ligne de défense principale.

## 4 bis. Pourquoi cette solution vaut pour toutes les plateformes

Exigence d'Adrien du 30/08 : « automatique, et pour toutes les plateformes ».

| Plateforme | Ce qui porte le jeton au lancement |
| --- | --- |
| Android / Chrome | `start_url` du manifeste, **et** le stockage partagé avec le navigateur |
| iOS 16.4 et plus | `start_url` du manifeste |
| iOS antérieur | l'adresse capturée à l'installation, jamais nettoyée (architecture §5) |
| Navigateur, sans installation | la requête `?j=`, puis le stockage |

Aucune de ces quatre lignes ne demande un geste au bénévole au-delà du scan du
QR. C'est ce qui rend la solution automatique partout — et le
[filet](architecture.md) du §5 bis n'existe que pour le cas non prévu.

## 5. Ce qu'on ne fait pas

- Pas de compte ni de mot de passe pour les juges. Décision d'Adrien du 29/08,
  inchangée.
- Pas de jeton par téléphone ni de jeton à durée de vie. Le besoin exprimé est
  l'inverse : **un jeton constant**.
- Pas de code d'appairage à saisir : ce serait un geste manuel, alors que la
  demande est que ce soit automatique. Le seul repli manuel est le scan d'un QR
  (architecture §5 bis), et il ne sert qu'en cas d'échec.

## 6. Critères d'acceptation

| # | Critère | Vérifié par |
| --- | --- | --- |
| A1 | `/admin/lien-juge` produit une adresse en `?j=` | test de route |
| A2 | `/juge/manifest.webmanifest?j=X` a `start_url` = `/juge?j=X` | test de route |
| A3 | Le manifeste sans `?j=` garde `start_url` = `/juge` — il reste servable et valide | test de route |
| A4 | Le gabarit lie le manifeste **avec** le jeton quand il en a un | test de route |
| A5 | `?j=` ouvre une session utilisable ; `#j=` aussi, toujours | test JS `jeton.test.mjs` |
| A6 | Un jeton en requête l'emporte sur un jeton rangé différent | test JS |
| A7 | Ni requête ni fragment : le jeton rangé est conservé, jamais effacé | test JS (existant) |
| A8 | Le service worker ne sert pas un manifeste d'un autre jeton | test JS / revue |
| A9 | Caddy ne journalise pas la valeur de `j` | `curl` puis lecture du journal |
| A10 | Une PWA installée et relancée **sans stockage** fonctionne | essai réel sur iPhone |

**A10 est le critère qui compte.** C'est le seul qui prouve que le défaut est
corrigé, et il exige un vrai iPhone — jamais essayé à ce jour.

## 7. Cas limites

| Situation | Comportement |
| --- | --- |
| Lien avec `?j=` **et** `#j=` | la requête l'emporte, le fragment est ignoré |
| `?j=` vide (`/juge?j=`) | traité comme absent : le jeton rangé survit |
| Jeton invalide dans le lien | l'app démarre, l'API répond 401, le voyant passe au rouge — comportement actuel |
| Clé changée sur le serveur | un nouveau QR suffit ; l'ancien lien cesse de fonctionner |
| Installation déjà faite avec `#j=` | continue de fonctionner sans rien faire |

## 8. Question ouverte

**Q1 — le journal de gunicorn.** Masquer le paramètre côté Caddy est simple.
Côté gunicorn, il faudrait modifier `--access-logfile` ou son format. Vu que la
clé vit déjà en clair dans `shared/secrets/env` **sur la même machine**, la
recommandation est de **ne rien faire côté gunicorn** et de s'en tenir au
masquage sur `edge`, qui est le seul journal susceptible d'être recopié
ailleurs.
