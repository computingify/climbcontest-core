# Spec 022 — Le jeton Google se pose en un clic

> **Statut : rédigée, en attente de la porte 2.**
> Demande d'Adrien du 01/09/2026 : « la tuile Jetons Google, ce n'est
> absolument pas clair ce qu'il faut faire. Fais-moi quelque chose où je puisse
> générer un jeton Google, l'importer. »
>
> Tranché par Adrien avant rédaction : **le consentement OAuth se fait depuis la
> console**, pas depuis le Mac. Le collage de JSON n'est plus le geste normal.

## 1. Ce qui cloche

La carte « Jeton Google » demande aujourd'hui, dans cet ordre :

1. retrouver un Mac où `token.pickle` existe ;
2. y créer un environnement Python avec `google-auth` ;
3. lancer `python3 tools/exporter_jeton.py` ;
4. copier une ligne de JSON qui contient un `refresh_token` — un secret au même
   titre qu'un mot de passe ;
5. la coller dans un `<textarea>` de la console.

Cinq gestes, dont deux en ligne de commande, pour une console dont toute la
raison d'être est justement de **remplacer le SSH**. Et le geste ne produit
aucun jeton neuf : il ne fait que **recopier** celui qui existait déjà sur le
Mac. Le jour où ce jeton meurt — révoqué, expiré, compte changé — la carte ne
sait rien faire.

`sheets/parametrage.py` le dit lui-même en tête de fichier : *« Ce qui n'est pas
ici : le consentement OAuth (il demande un navigateur). »* Or la console **est**
un navigateur. C'était vrai de la ligne de commande, pas de cet écran.

Deuxième défaut, plus discret : le message d'erreur du client, quand le jeton
n'est plus rafraîchissable, dit *« refaire le consentement depuis une machine
avec navigateur »* — une consigne que rien, nulle part, ne permet d'exécuter.

## 2. Ce qu'on fait

### F1 — Un bouton « Connecter le compte Google »

La carte « Jeton Google » devient :

```
Jeton Google
Le serveur écrit dans le classeur avec un compte Google. C'est ce compte
que tu autorises ici — celui qui a accès à la feuille.

  ÉTAT   posé le 31/08, valable jusqu'au 15/11, écrit dans …/token.json
         scope : spreadsheets

  [ Connecter le compte Google ]   [ Vérifier le jeton ]

▸ Autre méthode : coller un jeton produit sur le Mac
```

Le bouton emmène chez Google, affiche le consentement, revient sur la console
et le jeton est posé. Aucune ligne de commande, aucun copier-coller, aucun
secret qui traverse un presse-papier.

### F2 — Le flux, en trois routes

| Route | Rôle | Ce qu'elle fait |
| --- | --- | --- |
| `GET /admin/classeur/google/consentement` | ADMIN | Tire un `state` aléatoire, le range en session, **redirige** vers Google |
| `GET /admin/classeur/google/retour` | ADMIN | Vérifie le `state`, échange le code contre un jeton, l'**écrit**, redirige vers `/console?jeton=pose` |
| `GET /admin/classeur/jeton` | ADMIN | L'état du jeton, déjà servi par `/admin/classeur` — exposé à part pour le bouton « Vérifier » |

Le consentement demande `access_type=offline` et `prompt=consent` : sans le
second, Google ne redonne **pas** de `refresh_token` à un compte qui a déjà
consenti une fois, et on reposerait un jeton qui meurt dans l'heure. C'est le
piège classique de ce flux, et il est silencieux.

Le jeton obtenu est écrit par `ecrire_jeton_json()` — la fonction qui existe
déjà, avec sa copie `.precedent` et son écriture atomique en 0600. Rien de
nouveau côté fichier.

### F3 — Le collage de JSON reste, rangé

`POST /admin/classeur/jeton` et `tools/exporter_jeton.py` ne sont **pas
supprimés**. Ils passent dans un `<details>` replié, intitulé « Autre méthode ».

C'est un désaccord assumé avec la lettre de la réponse d'Adrien (« le bouton
OAuth », pas « les deux ») : ce qu'il demandait était de **ne plus avoir à
passer par le Mac**, et le `<details>` replié le lui donne. Mais le flux OAuth
dépend de trois choses hors de notre code — `credentials.json` présent, URI de
retour déclarée chez Google, écran de consentement en bon état. Si l'une lâche
le matin de la compétition, supprimer le chemin de secours laisserait le serveur
sans **aucun** moyen de recevoir un jeton, et les réussites s'empileraient toute
la journée. Le coût de le garder est un `<details>` replié.

**À trancher à la porte 2** : si Adrien préfère qu'il disparaisse, on le
supprime — c'est une ligne de gabarit.

### F4 — Ce qui doit être fait une fois, chez Google

Manip d'Adrien, une seule fois, dans la Google Cloud Console du projet qui porte
`credentials.json` :

1. Identifiants → le client OAuth **de type « Web »** qui existe déjà → **URI de
   redirection autorisés** → ajouter :
   - `https://climbcontest.adn-dev.fr/admin/classeur/google/retour`
   - `http://localhost:5000/admin/classeur/google/retour` (développement)
2. Écran de consentement → vérifier l'**état de publication**.
   ⚠️ **En « Test », Google fait expirer le `refresh_token` au bout de 7 jours.**
   Un jeton posé le lundi serait mort le samedi de la compétition, sans que rien
   ne prévienne. L'application doit être **« En production »** — même avec un
   seul utilisateur, même non vérifiée (l'écran « application non vérifiée »
   s'accepte, c'est notre propre compte).

Cette manip est **documentée dans `docs/runbook-competition.md`**, et la console
la rappelle en toutes lettres quand le flux échoue avec `redirect_uri_mismatch`.

### F5 — Le message d'erreur qui ne mène nulle part

`client._identifiants()` dit aujourd'hui *« refaire le consentement depuis une
machine avec navigateur »*. Il dira : *« refaire le consentement depuis la
console : Classeur → Connecter le compte Google »*.

## 3. Périmètre

**Inclus** : les deux routes du flux, un module `sheets/consentement.py`, la
carte « Jeton Google » de `admin.html`, le runbook, deux messages d'erreur.

**Exclu, à dessein** :

- **le scope Drive.** On demande `spreadsheets`, rien de plus — c'est ce qu'il
  faut pour lire et écrire une feuille partagée. Supprimer les trois classeurs
  jetables du Drive (geste en attente depuis le 30/08) restera un geste manuel ;
- **plusieurs comptes Google.** Un jeton, un fichier, comme aujourd'hui ;
- **un rafraîchissement forcé depuis la console.** Le client le fait déjà tout
  seul et réécrit le fichier (spec 015) ;
- **le stockage du jeton en base.** Il reste un fichier dans le dossier des
  secrets, hors des releases, comme les autres.

## 4. Critères d'acceptation

- [ ] **A1** — « Connecter le compte Google » emmène chez Google avec les bons
  paramètres : scope `spreadsheets`, `access_type=offline`, `prompt=consent`,
  `state` non devinable.
- [ ] **A2** — Au retour, `token.json` contient un `refresh_token` et la console
  affiche « jeton posé ».
- [ ] **A3** — L'ancien `token.json` est conservé en `.precedent`
  (non-régression de la spec 015).
- [ ] **A4** — Un `state` absent ou différent de celui de la session fait
  échouer le retour **sans écrire** quoi que ce soit, et le dit.
- [ ] **A5** — Un retour avec `error=access_denied` (consentement refusé)
  ramène à la console avec un message clair, pas une 500.
- [ ] **A6** — `credentials.json` absent : le bouton est **désactivé** et la
  carte dit où poser le fichier. Pas de 500, pas de bouton qui ne marche pas.
- [ ] **A7** — Les deux routes sont refusées à un organisateur non
  administrateur (403) et à un anonyme (401).
- [ ] **A8** — Le jeton n'apparaît **jamais** dans un journal, ni dans une
  réponse HTTP, ni dans une URL.
- [ ] **A9** — `POST /admin/classeur/jeton` (le collage) répond exactement comme
  avant — **non-régression**.
- [ ] **A10** — `tools/exporter_jeton.py` fonctionne toujours — **non-régression**.
- [ ] **A11** — Le runbook porte la manip F4, expiration en mode « Test »
  comprise.

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| `credentials.json` absent du dossier des secrets | Bouton désactivé, message qui nomme le dossier cherché (A6) |
| `credentials.json` illisible ou sans clé `web`/`installed` | Même traitement, message distinct |
| URI de retour non déclarée chez Google | Google affiche `redirect_uri_mismatch` **avant** de revenir chez nous. La carte affiche à l'avance l'URI exacte à déclarer, prête à copier |
| Session expirée pendant l'aller-retour chez Google | Le retour répond 401 : on se reconnecte, on recommence. **Rien n'est écrit à moitié** |
| Google ne renvoie pas de `refresh_token` | Refusé, jeton **non écrit**, message : « recommence, le consentement n'a pas donné de jeton durable ». Même garde que le collage (spec 015) |
| Le disque refuse l'écriture | 500 explicite, `.precedent` intact, ancien jeton toujours en place |
| Deux administrateurs lancent le flux en même temps | Deux sessions, deux `state` : le dernier revenu écrit. Le `.precedent` garde l'avant-dernier |
| Consentement lancé depuis `http://` en local | Fonctionne si l'URI locale est déclarée ; sinon Google refuse avant nous |
| Le jour J, le flux échoue | Le `<details>` « Autre méthode » reste : `tools/exporter_jeton.py` sur le Mac, collage, comme en 2026 (F3) |
