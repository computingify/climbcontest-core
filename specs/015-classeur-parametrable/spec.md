# Spec 015 — Le classeur se règle depuis la console

> **Statut : codée, en attente de relecture (31/08/2026).** Tu as demandé
> explicitement de ne pas t'attendre à la porte 2 : la spec et le code arrivent
> ensemble, la porte 7 (merge) reste la tienne.
> Demandée par Adrien le 31/08/2026 : « agrandir le tableau s'il manque une
> colonne », « que la feuille Google Sheet soit paramétrable », « prévoir aussi
> de pouvoir setter le jeton », « tout ça dans la console ».

## 1. Les trois manques

### M1 — Changer de classeur demande un accès SSH

`Competition.spreadsheet_id` existe en base depuis la spec 002, et c'est déjà un
progrès : plus rien n'est en dur dans le code. Mais **aucune route, aucun écran
ne l'écrit**. Vérifié : `spreadsheet` n'apparaît ni dans `routes/`, ni dans
`templates/admin.html`.

Le geste le plus fréquent des semaines qui précèdent une compétition — pointer
une autre feuille, essayer sur un classeur jetable, revenir sur le vrai —
demande aujourd'hui de se connecter en SSH à la VM 110 et d'écrire du SQL à la
main sur la base de production. C'est le genre de geste qu'on finit par faire à
23 h la veille, et c'est exactement là qu'on se trompe de classeur.

### M1 bis — Et la route d'import n'avait aucun bouton

`POST /admin/import/sheet` existe depuis la spec 002, protégée par rôle et
testée. **Aucun écran ne l'appelait** : `import/sheet` n'apparaît nulle part
dans `admin.html`. Relier un classeur sans pouvoir l'importer ne mène nulle
part — c'est le geste qui suit immédiatement, et il manquait.

### M2 — Le jeton Google se pose par `scp`

`tools/preparer-mon-test.sh` copie `token.pickle` depuis le Mac d'Adrien vers
`/opt/climbcontest/shared/secrets/`. Sans ce Mac-là, pas de jeton ; et un jeton
qui expire un dimanche matin n'a aucun moyen d'être remplacé depuis la salle.

### M3 — Un dossard au-delà de la largeur du classeur bloque le miroir

`ClasseurGoogle.marquer_reussites()` écrit en `colonne = dossard + 3`,
`ligne = numéro de bloc + 1`. L'API Google **refuse** une écriture hors de la
grille existante :

```
Range ('Import'!DZ12) exceeds grid limits.
Max rows: 1000, max columns: 120
```

Le miroir fait alors ce qu'il doit faire — il ne marque rien comme synchronisé
et retente (spec 002) — mais **il retentera indéfiniment** : la grille ne
s'agrandira jamais toute seule. Une réussite bloque le lot, donc toutes les
suivantes. Le scénario n'a rien de théorique : la spec 013 attribue un dossard
au premier numéro libre à un participant inscrit **à chaud**, et ce numéro sort
sans difficulté de la largeur préparée dans la feuille.

## 2. Ce qu'on fait

**Une vue « Classeur » dans la console**, réservée aux administrateurs, qui
porte quatre gestes :

| Geste | Ce qu'il fait |
| --- | --- |
| **Voir** | Le classeur relié à la compétition active, son titre, l'état du jeton |
| **Ouvrir** | Un bouton vers la feuille elle-même — « suis-je sur la bonne ? » se vérifie en l'ouvrant, pas en comparant deux identifiants de 44 caractères à l'œil |
| **Tester** | Lecture seule : titre, onglets présents, taille de la grille `Import`, dossards prévus |
| **Relier** | Coller un lien Google Sheets (ou un identifiant nu) → il devient celui de la compétition active |
| **Poser le jeton** | Coller le JSON d'identifiants Google → écrit dans le dossier des secrets |
| **Importer** | Relire `Listes` et `Plan` pour repeupler la base — le geste qui suit un changement de feuille |

**Et le client agrandit la grille avant d'écrire** : si le dossard demande une
colonne qui n'existe pas encore dans l'onglet `Import`, la feuille est élargie,
puis l'écriture a lieu. Idem pour les lignes.

### Les deux modes de bascule (décision d'Adrien, 31/08)

Relier un classeur pose une question à laquelle il n'y a pas de réponse unique,
et c'est donc **un choix explicite à l'écran**, jamais un effet de bord :

| Mode | Base | Nouveau classeur | Quand |
| --- | --- | --- | --- |
| **Relier seulement** (défaut) | intacte | intact | Le classeur est vide, ou on ne fait qu'essayer |
| **Même compétition, autre feuille** | intacte, **toutes les réussites repassent « en attente »** | reçoit tout l'historique par le miroir | On change de feuille en gardant les données |
| **Nouvelle compétition** | réussites, participants, blocs et circuits de la compétition active **effacés** | matrice `Import` **vidée** de ses « A » | On repart de zéro sur une nouvelle édition |

Le mode « Nouvelle compétition » est destructeur des deux côtés. Il exige une
confirmation frappée à la main (`EFFACER`), il est refusé pendant une
compétition `en_cours`, et il ne touche **que le classeur qu'on est en train de
relier** — jamais celui qu'on quitte.

## 3. Critères d'acceptation

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A1 | Un dossard au-delà de la largeur de `Import` déclenche l'agrandissement de la feuille, puis l'écriture réussit | Test sur faux service Google : la grille passe de 26 à ≥ dossard+3 colonnes, `batchUpdate` de valeurs appelé après |
| A2 | Un numéro de bloc au-delà de la hauteur agrandit les lignes de la même façon | Idem, sur `rowCount` |
| A3 | Aucun appel d'agrandissement quand la grille suffit | Le faux service ne voit qu'un `values.batchUpdate` |
| A4 | Coller `https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0` relie le classeur `<ID>` | Test de route : la compétition active porte `<ID>` |
| A5 | Un lien qui n'est pas un classeur est refusé avec un message qui dit quoi coller | 400, message explicite, base inchangée |
| A6 | « Tester » dit le titre, les onglets manquants s'il y en a, et la taille de la grille | Test de route sur classeur fictif |
| A7 | Mode « autre feuille » : toutes les réussites de la compétition repassent `sheet_synced_at = NULL` | Compte en base avant / après |
| A8 | Mode « nouvelle compétition » sans le mot `EFFACER` : refusé, rien n'est touché | 400, compteurs inchangés |
| A9 | Mode « nouvelle compétition » : base vidée **et** matrice `Import` vidée, ligne 1 et colonnes A–C préservées | Faux classeur : la plage effacée commence en `D2` |
| A10 | Le jeton collé en JSON est écrit dans le dossier des secrets, en `0600` | Test de route + `stat` |
| A11 | Un JSON sans `refresh_token` est refusé, le jeton en place n'est pas remplacé | 400, fichier inchangé |
| A12 | `token.json` est lu **avant** `token.pickle` et `token.base64` | Test unitaire sur la résolution du jeton |
| A13 | Un organisateur non-admin ne peut ni relier, ni poser un jeton | 403 sur les quatre routes |
| A14 | La console affiche l'état sans jeton Google installé côté serveur | La vue répond « aucun jeton » plutôt qu'une erreur 500 |
| A15 | Le classeur relié peut être importé depuis la console | La vue appelle `POST /admin/import/sheet` et affiche le rapport, lignes ignorées comprises |

## 4. Les cas limites, et ce qu'on en fait

**Aucune compétition active.** La vue le dit et n'offre rien à relier — c'est
déjà la règle des autres écrans de la console.

**Le classeur est inaccessible** (jeton absent, feuille partagée avec un autre
compte, identifiant faux). « Tester » répond en clair *ce que Google a dit*, et
relier reste possible : on prépare parfois le lien avant le partage.

**Changer de classeur en pleine compétition.** Autorisé pour « relier » et
« autre feuille » — c'est précisément la réparation d'urgence dont on peut avoir
besoin. Refusé pour « nouvelle compétition » : effacer les réussites d'une
compétition en cours n'est jamais ce qu'on voulait dire.

**La capacité du classeur reste celle du classeur.** Agrandir la grille fait
que *l'écriture aboutit* et que *rien ne se perd*. Mais les formules de
`Résultats` et `Inter` sont dimensionnées pour 120 grimpeurs et 50 blocs
(`docs/technical/classeur-google.md`) : un dossard au-delà **apparaîtra dans
`Import` sans être compté par le classeur**. Le backend, lui, le compte — sa
page de résultats reste juste. La console le dit noir sur blanc au moment du
test, avec les deux chiffres : largeur de la grille, et dossard le plus haut
déjà attribué.

**Le jeton expiré.** Rien de neuf : le client rafraîchit tout seul tant que le
`refresh_token` est valide. La nouveauté est qu'un jeton rafraîchi **est
réécrit** dans `token.json`, donc le rafraîchissement ne recommence pas à chaque
redémarrage.

## 5. Hors périmètre

- **Le consentement OAuth depuis la console.** Il demande un navigateur, une
  URL de redirection déclarée chez Google et un secret client posé sur la VM :
  hors sujet ici. On colle un jeton obtenu ailleurs (`tools/exporter_jeton.py`).
- **Créer ou choisir une compétition depuis la console.** La vue règle le
  classeur de la compétition **active**. Gérer plusieurs compétitions est un
  autre écran, et une autre spec.
- **Supprimer des classeurs dans le Drive.** Le jeton n'a que le scope
  `spreadsheets` — c'est volontaire, et ça le reste.

## 6. Ce qu'on ne fera pas, et pourquoi

**La console n'acceptera pas un `token.pickle`,** ni son base64. Le serveur
appellerait `pickle.loads()` sur un contenu venu du réseau, et une session
d'administrateur volée deviendrait une exécution de code arbitraire sur la VM.
Le format JSON (`Credentials.to_json()`) porte exactement la même information —
`client_id`, `client_secret`, `refresh_token`, `scopes` — et n'est que des
données. `tools/exporter_jeton.py` convertit le `token.pickle` existant, sur ton
Mac, en une commande.

Les fichiers `token.pickle` et `token.base64` **restent lus** : les
installations en place ne bougent pas.
