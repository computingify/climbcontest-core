# Spec 030 — Les versions se voient, et le catalogue se force

> **Statut : soumise à la porte 2.** Écrite avant le code.
> Demande d'Adrien du 02/09/2026 : « Je voudrais que tu m'affiches sur les PWA
> iPhone et Android un numéro de version dans les paramètres ainsi que la
> version de ce qui est en local sur le téléphone. Je veux la même chose côté
> console, un numéro de version (le tag git) et la version des données qui sont
> échangées (le catalogue) afin que je puisse m'assurer qu'il n'y a pas de
> désynchro entre des téléphones et le serveur. Du coup sur téléphone je veux
> dans option pouvoir forcer la réception du catalogue. »

## 1. Ce qui manque

Tout est déjà versionné. **Rien n'est lisible.**

- Le **tag git** est posé par la CI dans un fichier `VERSION` à la racine de la
  release, lu au démarrage par `routes/sante.py`, et exposé sur `/health`. Or
  `/health` est fermé aux téléphones par Caddy, et la console ne l'appelle pas.
  Personne ne voit jamais ce numéro.
- Le **catalogue** porte un numéro depuis la spec 002 (`Competition.catalogue_
  version`). Il circule à chaque requête, en `If-None-Match`, et c'est lui qui
  décide du `304`. Il ne s'affiche nulle part, ni sur le téléphone, ni dans la
  console.
- Le **service worker** sert la coquille depuis le cache et la rafraîchit
  derrière : une correction publiée la veille est prise **au lancement
  suivant**. C'est un choix assumé — recharger la page toute seule couperait un
  juge en plein geste. Mais rien ne dit si ce lancement suivant a eu lieu.

Conséquence, et c'est la seule qui compte : **un téléphone en retard est
indiscernable d'un téléphone à jour.** Ni le juge qui le tient, ni Adrien devant
sa console, ne peuvent le savoir. Les deux pannes que ça produit sont connues :

1. un catalogue périmé fait répondre « grimpeur inconnu » à un dossard inscrit
   à 14 h, ou dessine un mur qui n'est plus celui de la salle ;
2. une coquille périmée fait tourner un correctif qu'on croit déployé.

Et il n'y a **aucun geste** à la portée du juge : le catalogue se rafraîchit
tout seul, sur un minuteur de cinq minutes, sans bouton pour dire « maintenant ».

## 2. Ce qu'on fait

### F1 — Le serveur dit sa version à qui télécharge le catalogue

`GET /api/v2/catalog` répond avec un en-tête `X-Server-Version`, **sur les deux
branches** : le `200` et le `304`.

⚠️ Le `304` est le cas **majoritaire** le jour J — le catalogue ne bouge presque
jamais, et la PWA revalide toutes les cinq minutes. Un en-tête posé seulement
sur le `200` serait un en-tête qui n'arrive presque jamais.

Pourquoi cette route et pas `/health` : Caddy ferme `/health` depuis Internet, et
la PWA le sait déjà (`juge.js`, la sonde de connexion passe délibérément par le
catalogue). Ajouter un appel serait ajouter une requête ; l'en-tête est gratuit.

### F2 — Le téléphone s'annonce, sur la requête qu'il fait déjà

Trois en-têtes **facultatifs** sur cette même requête :

| En-tête | Contenu |
| --- | --- |
| `X-Device-Id` | l'identifiant du téléphone, celui qui est déjà envoyé avec les lots |
| `X-Device-Name` | le nom donné par le juge (« Mur jaune »), percent-encodé |
| `X-App-Version` | la version de la coquille que ce téléphone exécute |

Le serveur les range dans une table `appareil`. Rien d'autre ne change : pas de
nouvelle route, **pas une requête de plus**.

⚠️ **Des en-têtes, pas des paramètres d'URL.** Le nom d'un poste n'a rien à faire
dans le journal d'accès de Caddy — la spec 014 a justement dû y poser un filtre
pour en retirer le jeton. Un en-tête n'y est pas journalisé.

⚠️ **Facultatifs, et le serveur s'en passe.** Une requête sans ces en-têtes se
comporte exactement comme aujourd'hui. L'application Android du Play Store ne
les envoie pas : elle doit continuer de marcher sans rien changer.

### F3 — L'écran « Réglages » du téléphone montre ce qu'il a

Deux sections nouvelles, sous « Serveur ». Maquette montrée à Adrien le
02/09 — `maquette-versions-pwa.png`, à la racine du plan de travail et **hors
dépôt**, comme les maquettes des specs 016, 025 et 026 :

**Catalogue** — le numéro local, le verdict (« identique au serveur » en vert, ou
« le serveur en est au n° 42 » en ambre), ce qu'il contient (« 98 grimpeurs ·
67 blocs · le plan du mur »), et quand il est arrivé.

**Application** — la version, et le verdict (« à jour », ou « le serveur sert
v0.16.0 »).

⚠️ La version affichée est celle de la **coquille en cache**, c'est-à-dire du
code que ce téléphone exécute vraiment — pas celle que le serveur sert. C'est
tout l'intérêt : afficher la seconde ferait dire « à jour » à un téléphone qui ne
l'est pas.

### F4 — Un bouton « Retélécharger maintenant »

Il envoie la requête de catalogue **nue** : ni `?depuis`, ni `If-None-Match`,
donc un `200` complet, donc un catalogue neuf écrit en base locale.

⚠️ C'est le **seul** moyen propre d'obtenir un `200`. Le serveur décide du `304`
par égalité stricte — un client annonçant un autre numéro n'est pas « en
avance », il vient d'ailleurs (autre compétition, base restaurée), et le
correctif du 30/08 lui refuse le `304` exprès. Un bouton qui bricolerait le
numéro annoncé se heurterait à cette garde, et à son test.

Le bouton dit ce qu'il a fait : « catalogue n° 42 reçu — 98 grimpeurs,
67 blocs », ou « serveur injoignable — le téléphone garde ce qu'il a ».

### F5 — Un bouton « Mettre à jour et redémarrer »

Visible **seulement quand la coquille est en retard**. Il demande au service
worker de retélécharger la coquille (`cache: "reload"`), puis recharge la page.

⚠️ **Il n'efface rien avant d'avoir reçu.** Vider le cache puis échouer à le
remplir laisserait un téléphone sans application hors ligne — exactement la
panne que le service worker existe pour empêcher. Chaque fichier n'est remplacé
que quand sa version fraîche est arrivée ; sans réseau, le bouton refuse et
l'installation reste intacte.

⚠️ **Un scan en cours est perdu par le rechargement.** Le bouton prévient quand
un grimpeur ou un bloc est déjà scanné. La file d'attente, elle, est en
IndexedDB : elle survit.

### F6 — La console affiche ce qu'elle sert

- **En pied de tiroir**, visible depuis n'importe quel écran :
  `ClimbContest v0.16.0 · catalogue n° 42`.
- Dans **Téléphones**, une carte **« Versions en circulation »** : la version du
  serveur et depuis quand elle est posée, le numéro du catalogue et ce qu'il
  contient, et le compte des téléphones à jour / en retard.

### F7 — La console dit quel téléphone est en retard

Le tableau « Qui envoie quoi » gagne deux colonnes, **Application** et
**Catalogue**, avec une pastille verte quand c'est identique au serveur, ambre
sinon (maquette `maquette-versions-console.png`, même remarque).

⚠️ La couleur ne porte pas seule : le numéro divergent est **écrit** à côté de sa
pastille. Même règle que le voyant de connexion de l'app juge — le rouge et le
vert seuls sont indistinguables pour environ 8 % des hommes.

Le tableau liste désormais aussi les téléphones qui **se sont annoncés sans rien
envoyer** : c'est le cas du matin, quand les juges ouvrent l'application avant
la première grimpe. Un téléphone qui n'a jamais parlé ne peut pas apparaître,
mais c'est déjà un renseignement — il en manque un à l'appel.

⚠️ **Le retard normal se distingue de la panne, en toutes lettres.** Depuis la
fermeture de l'incohérence du plan (PR #85), redessiner le mur donne un numéro
neuf à **toutes** les éditions d'un coup : un organisateur qui retouche le plan
en pleine compétition verrait ses vingt-cinq téléphones passer à l'ambre **en
même temps**, et croirait avoir tout cassé. Ils sont bien en retard — c'est le
correctif qui veut ça — mais ils se remettent à jour seuls en cinq minutes. La
carte affiche donc une phrase calme, en ocre et non en rouge : « le catalogue
vient de changer, N téléphones ne l'ont pas encore repris, rien à faire ».

Ce qui sépare ce cas de la vraie panne, c'est la **fraîcheur de l'annonce de
catalogue** : ici elle date de quelques secondes — le téléphone parle, il n'a
simplement pas encore repris le numéro. Quand un cache absorbe les annonces,
c'est l'inverse : elles vieillissent, et c'est l'alerte rouge de F8 qui
s'allume. Les deux ne peuvent pas se confondre, et c'est la raison pour
laquelle `vu_le` et `catalogue_vu_le` sont deux colonnes distinctes.

### F8 — Le cache qui casserait tout ça ne pourra pas s'installer en silence

L'annonce voyage sur un `GET`. Un cache posé un jour devant `/api/v2/catalog` —
un module Caddy, un CDN, un proxy d'entreprise sur le wifi de la salle —
absorberait ces requêtes : le serveur ne verrait plus personne s'annoncer, et la
console montrerait des téléphones « absents » alors qu'ils grimpent. Rien ne le
dirait.

Demande d'Adrien du 02/09, au moment de valider la spec : « fais tout ce qu'il
faut pour que ça n'arrive jamais ». Quatre mesures, dont deux qui tiennent même
si la faute vient de la configuration de Caddy, hors de ce dépôt :

1. **On le déclare à la source.** La réponse porte `Cache-Control: no-cache,
   private` — `private` interdit à un cache **partagé** de stocker la réponse,
   là où `no-cache` seul se contente de demander une revalidation. C'est le
   mécanisme standard, et c'est le seul qu'un intermédiaire correct respecte.
2. **On le verrouille par un test.** Un test vérifie l'en-tête sur les **deux**
   branches, un autre prouve que l'annonce est enregistrée sur le chemin du
   `304`. Les retirer fait rougir la CI.
3. **On rend la donnée redondante.** La version de l'application est **aussi**
   enregistrée depuis le lot (`POST /api/v3/successes`), qu'aucun cache
   n'absorbe jamais. Le numéro de catalogue, lui, ne l'est pas — et ne peut pas
   l'être : seul l'échange de catalogue prouve ce que le téléphone détient.
4. **On le détecte en marche.** L'appareil porte **deux** horodatages :
   `vu_le`, dernier contact quel qu'il soit, et `catalogue_vu_le`, dernier
   échange de catalogue. Un téléphone qui envoie des réussites mais ne s'est
   plus annoncé depuis un quart d'heure est la **signature exacte** d'un cache
   posé devant la route. La console le dit en toutes lettres, avec la phrase
   qui nomme la cause — pas un compteur à interpréter.

⚠️ La mesure 4 est la seule qui attrape une faute commise **hors du dépôt**.
C'est aussi la raison pour laquelle les deux horodatages sont distincts : les
fusionner en un seul rendrait la détection impossible, et c'est le genre de
simplification qu'une relecture pressée propose.


## 3. Ce qui est explicitement exclu

| Exclu | Pourquoi |
| --- | --- |
| L'application **Android native** | Autre dépôt, autre release, délai Play Store. Elle continue de fonctionner sans rien changer ; la console la marque « ne le dit pas ». Décision d'Adrien du 02/09. |
| Une **mise à jour poussée** depuis la console | Il faudrait un canal serveur → téléphone (WebPush, sondage). Le bouton du téléphone couvre le besoin réel : réparer un poste identifié. |
| **Renommer** `catalogue_version` / `version` | La réponse de lot dit `catalogue_version`, celle du catalogue dit `version`. Deux clients tournent avec ces noms. On documente l'écart (`architecture.md`), on ne le corrige pas dans une spec d'affichage. |
| Une **date de dernière modification** du catalogue | Il faudrait horodater les trois — bientôt quatre — endroits qui incrémentent le numéro, et un oubli produirait une date fausse. Le « vu il y a X » par téléphone répond à la même question sans ce risque. |

## 4. Critères d'acceptation

- [ ] **A1** — `GET /api/v2/catalog` répond avec `X-Server-Version` en `200`
      **et** en `304`.
- [ ] **A2** — Une requête portant `X-Device-Id` crée ou met à jour une ligne
      `appareil`, **y compris quand la réponse est un `304`**.
- [ ] **A3** — Une requête sans aucun de ces en-têtes se comporte exactement
      comme avant : même corps, même ETag, même code.
- [ ] **A4** — L'écran Réglages de la PWA affiche le numéro de catalogue local,
      le nombre de grimpeurs et de blocs, et l'âge de la dernière réception.
- [ ] **A5** — Il affiche la version de l'application, et le dit quand le
      serveur en sert une autre.
- [ ] **A6** — « Retélécharger maintenant » émet une requête **sans**
      `If-None-Match` et **sans** `?depuis`, et remplace le catalogue local.
- [ ] **A7** — Hors ligne, ce bouton laisse le catalogue local intact et le dit.
- [ ] **A8** — « Mettre à jour et redémarrer » n'apparaît que si la coquille est
      en retard ; hors ligne, il ne détruit rien.
- [ ] **A9** — Le pied du tiroir de la console affiche la version et le numéro
      de catalogue, sur tous les écrans.
- [ ] **A10** — La vue Téléphones affiche, par téléphone, sa version
      d'application et son numéro de catalogue, et marque ceux qui divergent.
- [ ] **A11** — Un téléphone qui s'est annoncé **sans envoyer de réussite**
      apparaît dans le tableau, avec 0 réussite.
- [ ] **A12** — Un téléphone qui n'annonce rien (app Android) apparaît avec
      « ne le dit pas », et ses colonnes existantes restent justes.
- [ ] **A13** — En développement, sans fichier `VERSION`, la console et le
      téléphone affichent `dev` sans rien casser.
- [ ] **A14** — La réponse du catalogue porte `Cache-Control: no-cache, private`
      en `200` **et** en `304`.
- [ ] **A15** — Un lot envoyé avec une version d'application met à jour la ligne
      `appareil` **sans** toucher à `catalogue_version` ni à `catalogue_vu_le`.
- [ ] **A16** — Un téléphone qui envoie des réussites mais ne s'est plus annoncé
      depuis un quart d'heure est signalé dans la console, avec la cause nommée.
- [ ] **A17** — Un téléphone en retard sur le catalogue mais annoncé il y a
      moins de six minutes est présenté comme **en train de rattraper**, pas
      comme une panne — et un téléphone dont les annonces sont absorbées par un
      cache ne l'est **jamais**, même si ses lots continuent d'arriver.

## 5. Cas limites

| Cas | Comportement attendu |
| --- | --- |
| Le téléphone n'a jamais reçu de catalogue | « Aucun catalogue » ; le bouton reste offert |
| Réseau coupé | Le verdict affiche la dernière comparaison connue, avec son âge. Rien n'est effacé |
| L'édition active change | Le numéro de catalogue change de portée : le téléphone reçoit un `200` au rafraîchissement suivant. Aucun traitement particulier ici |
| Deux téléphones, même nom | Ils restent deux lignes : le regroupement est fait par identifiant, comme aujourd'hui |
| Un téléphone vu il y a trois semaines | Il sort du tableau : on n'affiche que ceux vus depuis 24 h ou ayant envoyé sur l'édition en cours |
| `X-App-Version` fantaisiste | Stocké tel quel, tronqué à 20 caractères, affiché tel quel. Le serveur ne valide pas une chaîne qu'il ne fait que rendre |
| Nom avec accents | Percent-encodé côté client, décodé côté serveur ; un décodage qui échoue donne un nom absent, jamais une erreur 500 |
| Un téléphone n'envoie que des lots (app Android) | `vu_le` avance, `catalogue_vu_le` reste vide. **Pas d'alerte de cache** : elle ne vise que les clients qui savent s'annoncer |
| L'application juge est simplement fermée | `vu_le` et `catalogue_vu_le` vieillissent ensemble. Le téléphone ressort « muet », comme aujourd'hui, et non « cache suspecté » |

## 6. Ce qui casse le jour J, si ça casse

L'annonce est **facultative de bout en bout**. Une table absente, un en-tête
malformé, un décodage raté : le catalogue part quand même. C'est la règle qui
doit tenir en revue de code — **rien de ce qui est ajouté ici n'a le droit de
faire échouer une requête de catalogue**, parce qu'un catalogue qui n'arrive pas
arrête les scans, alors qu'une colonne vide dans la console ne fait rien de plus
que rendre Adrien aveugle sur un point.

Le bouton « Mettre à jour et redémarrer » est le seul geste destructeur de la
spec, et il ne détruit qu'un cache reconstructible — jamais la file, jamais
l'identité du téléphone, jamais le catalogue.
