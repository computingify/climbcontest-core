# 007 — L'application juge sur iPhone, sans payer de store

> ⚠️ **Le transport du jeton a changé depuis.** Cette spec le fait voyager
> dans le fragment (`#j=`) ; la [spec 014](../014-jeton-juge-dans-le-lien/)
> le déplace dans la requête (`?j=`), parce qu'un fragment n'est pas
> transmis à `start_url` du manifeste — donc l'application **installée**
> démarrait sans jeton. Le fragment reste accepté.

## Résumé

Un bénévole qui arrive avec un iPhone ne peut pas juger. L'application est
Android, et la publier sur l'App Store coûte 99 $/an — une dépense qu'Adrien
refuse, à raison, pour un club qui organise une compétition par an.

Une **PWA** — une page web installable sur l'écran d'accueil — lève la
contrainte : zéro compte développeur, zéro validation, zéro délai de
publication, et elle se met à jour toute seule.

Elle est servie par le backend qui sert déjà la page de résultats et la console.

## Décisions prises (29/08)

| Question | Décision d'Adrien |
| --- | --- |
| Authentification du juge | **Aucune.** « Un juge n'a que l'application et il n'a pas besoin de s'authentifier » |
| Décodeur de QR | **Verser une bibliothèque dans le dépôt**, en clair |
| Périmètre | **Parité complète** avec l'application Android |

## Le point que la première décision soulève, et comment je le traite

Adrien veut zéro friction pour les bénévoles, et il a raison : vingt-cinq
personnes qui doivent taper un mot de passe un dimanche matin, c'est vingt-cinq
occasions de perdre dix minutes.

Mais une page web sans authentification **n'a nulle part où cacher une clé**.
L'application Android en garde une dans son APK — extractible, mais il faut au
moins savoir démonter un APK. Une PWA publique, elle, livre son code source à
quiconque ouvre l'adresse. La clé d'API que la spec 012 vient de poser
deviendrait décorative dès la mise en ligne de la PWA.

**Ce que je fais donc**, et qui respecte « le juge ne s'authentifie pas » :

Le juge reçoit **un lien** — QR code affiché au mur, message dans le groupe des
bénévoles. Il l'ouvre, ajoute la page à son écran d'accueil, et n'a plus jamais
rien à faire. Le lien porte un **jeton**, que la page range une fois pour toutes
et renvoie à chaque appel. Aucun identifiant, aucun mot de passe, aucun compte.

Le juge ne fait donc rien de plus qu'ouvrir l'application. La différence tient
en une phrase : **il faut avoir reçu le lien**, comme il faut aujourd'hui avoir
reçu l'APK.

Ce que ça vaut, dit franchement : un lien se transfère, se photographie
par-dessus l'épaule. C'est **exactement** la même protection que la clé dans
l'APK — ni plus, ni moins — et pas une protection cryptographique. Elle arrête
un robot qui balaie Internet, pas quelqu'un qui veut fausser la compétition.

Si Adrien préfère une PWA totalement ouverte, une ligne de configuration suffit
à retirer le jeton — mais alors la spec 012 ne protège plus rien, et il faut le
savoir.

## Périmètre

### Inclus — la parité avec l'Android, par itérations

| Brique | Équivalent Android |
| --- | --- |
| Scan du grimpeur et du bloc | `GmsBarcodeScanner` → `BarcodeDetector`, repli jsQR |
| Catalogue local | `Catalogue.kt` → IndexedDB, même `If-None-Match` |
| File d'attente persistante | `FileDeReussites.kt` → IndexedDB, même invariant |
| Envoi par lots, retrait exponentiel | `Expediteur.kt` / `PolitiqueEnvoi` |
| Réussites refusées, renvoi | `mettreDeCote` / `renvoyerLesRefusees` |
| Journal de tous les scans | `HistoriqueScans.kt`, purge à 30 jours |
| Identité de l'appareil et son nom | `IdentiteAppareil.kt` |
| Voyant de connexion | sondage du catalogue, premier plan seulement |
| Réglages | `SettingsScreen.kt` |
| Installable, fonctionne hors ligne | service worker |

### Exclu

- **Remplacer l'application Android.** Elle marche et elle est publiée. Les deux
  coexistent ; on décidera après une vraie compétition (décision D6 de la
  feuille de route).
- **Le mode « garder le grimpeur entre deux blocs »** en première version. Il se
  rajoute en trois lignes une fois le reste éprouvé.
- **Toute dépendance chargée depuis Internet.** Même règle que la page de
  résultats et la console : rien ne doit dépendre d'un CDN le matin d'une
  compétition. jsQR (Apache-2.0) est **versé dans le dépôt**, en clair, avec sa licence.
- **Les notifications, la géolocalisation, le mode paysage forcé.** Rien de tout
  ça ne sert au geste du juge.

## Critères d'acceptation

### Le geste du juge

- [x] Sur iPhone, la PWA s'ajoute à l'écran d'accueil et s'ouvre en plein écran.
- [x] Elle scanne un QR code sur **Safari iOS** et sur **Chrome Android**.
- [x] Le juge ne saisit **jamais** d'identifiant ni de mot de passe.
- [x] Un scan est validé **sans réseau** quand le catalogue local le connaît.
- [x] « Validé » s'affiche quand la réussite est **sur le téléphone**, pas quand
      elle est sur le serveur.

### Ce qui ne doit jamais arriver

- [x] Une réussite validée par le juge n'est **jamais** perdue : ni par une
      coupure réseau, ni par une fermeture d'onglet, ni par un rechargement.
- [x] Une réussite ne quitte la file que si le serveur a **statué** sur elle.
- [x] Un rechargement de la page ne rejoue pas les envois déjà acquittés.

### Hors ligne

- [x] L'application s'ouvre et fonctionne **sans réseau**, une fois installée.
- [x] La file survit à la fermeture complète de l'application.
- [x] Le voyant de connexion dit la vérité, et jamais l'état d'avant la mise en
      veille.

### Sécurité

- [x] Aucune requête API ne part sans jeton.
- [x] Le jeton n'apparaît **pas** dans le code source servi publiquement.
- [x] Le jeton se révoque sans toucher aux applications Android.
- [x] Aucune ressource n'est chargée depuis un domaine tiers.

### Parité

- [x] Journal de tous les scans, avec leur état, purgé à 30 jours.
- [x] Identité d'appareil et nom, visibles dans la console à côté des réussites.
- [x] Réussites refusées conservées et renvoyables.

## Cas limites

| Cas | Comportement attendu |
| --- | --- |
| Safari refuse l'accès à la caméra | Message qui dit **quoi faire** (Réglages → Safari → Caméra), pas « erreur ». |
| Le juge ouvre la PWA dans un onglet normal, pas installée | Ça marche, avec un bandeau qui invite à l'installer. |
| iOS vide le stockage d'une PWA peu utilisée | Risque réel et connu. La file est en IndexedDB, qu'iOS conserve pour une PWA **installée** ; le bandeau d'installation n'est donc pas cosmétique. À vérifier sur un vrai iPhone. |
| Deux onglets de la PWA ouverts | Un seul envoie à la fois. Un verrou en IndexedDB, sinon les deux videraient la file en double. |
| Le lien avec jeton est ouvert deux fois | Sans effet : le jeton est rangé, pas accumulé. |
| Le jeton est révoqué pendant la compétition | Les envois reçoivent 401, **rien n'est perdu**, la file attend un jeton valide. |
