# Plan — 022 jeton-google-en-un-clic

## Étapes

1. [x] `client.chemin_credentials()` / `etat_credentials()` — chercher
   `credentials.json` dans les mêmes dossiers que le jeton, dire ce qu'on a
   trouvé sans jamais lever.
2. [x] `sheets/consentement.py` — `disponible()`, `url_de_consentement()`,
   `echanger()`. Aucune écriture disque, aucun Flask hors `session`.
3. [x] `routes/admin.py` — extraire `base_publique()` de `lien_juge()` (et
   l'appeler depuis `lien_juge`, pour qu'il n'y ait qu'une règle), puis les deux
   routes du flux.
4. [x] `GET /admin/classeur` — le bloc `consentement` dans `jeton`.
5. [x] Tests (tableau ci-dessous), avec un `Flow` factice — **aucun appel
   réseau**.
6. [x] `admin.html` — la carte refaite : état, bouton, URI de retour à copier,
   `<details>` « Autre méthode », lecture de `?jeton=` et nettoyage de l'URL.
7. [x] `client._identifiants()` — le message d'erreur de F5.
8. [x] `docs/runbook-competition.md` — la manip Google (F4), expiration en mode
   « Test » comprise. `docs/technical/classeur-google.md` § 5 ter — l'origine
   « console (OAuth) » dans le tableau des formes de jeton.
9. [ ] Essai réel de bout en bout, une fois l'URI déclarée chez Google.

## Plan de test

| Module | Scénario | Attendu |
| --- | --- | --- |
| `client` | `credentials.json` présent | `etat_credentials()["pret"] is True`, chemin exact |
| `client` | absent | `pret is False`, message qui nomme les dossiers cherchés, **aucune exception** |
| `client` | JSON illisible | `pret is False`, message distinct du précédent |
| `client` | JSON sans clé `web` ni `installed` | `pret is False`, message distinct |
| `consentement` | `url_de_consentement()` | l'URL porte `scope=…/spreadsheets`, `access_type=offline`, `prompt=consent`, `state` de ≥ 32 caractères, `redirect_uri` exacte |
| `consentement` | deux appels successifs | deux `state` différents |
| `consentement` | `echanger()` avec un `Flow` factice qui rend un jeton complet | rend le JSON, `refresh_token` présent |
| `consentement` | `Flow` factice sans `refresh_token` | lève `ErreurClasseur`, **rien n'est rendu** |
| `admin` | `GET /consentement` en anonyme | 401 |
| `admin` | `GET /consentement` en organisateur | 403 |
| `admin` | `GET /consentement` en admin | 302 vers `accounts.google.com`, `state` en session |
| `admin` | `GET /consentement` sans `credentials.json` | 409, message d'A6, pas de 302 |
| `admin` | `GET /retour` sans `state` en session | 400, **`ecrire_jeton_json` jamais appelé** |
| `admin` | `GET /retour` avec un `state` différent | 400, idem |
| `admin` | `GET /retour?error=access_denied` | 302 vers `/console?jeton=refuse`, rien écrit |
| `admin` | `GET /retour` nominal (échange factice) | jeton écrit, 302 vers `/console?jeton=pose` |
| `admin` | deux `GET /retour` avec le même `state` | le second échoue : le `state` a été retiré |
| `admin` | échec d'écriture disque | 302 vers `?jeton=erreur&d=ecriture`, ancien jeton intact |
| `admin` | `GET /admin/classeur` | l'objet `jeton` porte `consentement.pret` et `consentement.uri_retour` |
| `admin` | journal après un retour réussi | la ligne nomme l'identifiant, **jamais** le jeton |
| `parametrage` | `POST /admin/classeur/jeton` (collage) | inchangé — **non-régression** |
| `parametrage` | collage d'un jeton sans `refresh_token` | refusé — **non-régression** |
| `pages` | `admin.html` | l'URI de retour affichée est celle que la route construit |

**Aucun test ne parle à Google.** Le `Flow` est injecté ; l'échange réel se
vérifie une fois, à la main, à l'étape 9.

## Vérification finale, à la main

| # | Geste | Attendu |
| --- | --- | --- |
| N1 | Déclarer l'URI chez Google, cliquer « Connecter le compte Google » | Écran de consentement Google, compte du classeur |
| N2 | Accepter | Retour sur la console, « jeton posé », état à jour |
| N3 | « Tester l'accès en écriture » dans la foulée | Aller-retour réel réussi sur la feuille |
| N4 | Refuser le consentement | Retour propre, message, ancien jeton toujours en place |
| N5 | Vérifier l'état de publication de l'écran de consentement | « En production » — sinon le jeton meurt sous 7 jours (F4) |
