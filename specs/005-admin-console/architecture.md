# 005 — Architecture

## Ce qui existe déjà, et qu'on n'invente pas

| Pièce | État |
| --- | --- |
| `Utilisateur`, `UtilisateurRole` | **en base depuis la spec 002**, jamais utilisées |
| `reaffecter_dossard()` | livrée, avec sa règle métier et ses tests |
| `enregistrer_reussite(source=...)` | livrée, `SOURCE_MANUEL` existe |
| `incrementer_catalogue()` | livrée — c'est ce qui fait voir un ajout aux téléphones |
| Le miroir vers le classeur | livré, indifférent à l'origine d'une réussite |

La console est donc surtout une **façade** sur de la logique déjà écrite et
testée. C'est voulu : ce qui décide reste dans `contest.py`, la console ne fait
que l'exposer à un humain.

## L'authentification

```
  POST /admin/connexion     identifiant + mot de passe  ->  cookie de session
  POST /admin/deconnexion
  GET  /admin/*             session valide exigee, sinon 401
```

**Session par cookie signé**, pas de jeton à gérer côté client. Flask signe avec
`SECRET_KEY` ; le cookie porte l'identifiant, la date d'émission et les rôles.

Trois choix, et leurs raisons :

**Le hachage est `scrypt`**, via `werkzeug.security` — déjà présent, aucune
dépendance nouvelle, et paramétré pour être lent à dessein.

**La session expire au bout de 12 heures.** Une compétition dure une journée :
plus court obligerait à se reconnecter en plein rush, plus long laisserait une
session ouverte sur un ordinateur de salle jusqu'à l'édition suivante.

**`SECRET_KEY` doit être posée.** Elle vaut `dev-non-secret` par défaut ; avec
cette valeur, n'importe qui peut fabriquer un cookie valide. Le démarrage
**refuse** de servir l'administration si elle n'a pas été changée — mieux vaut
une console indisponible qu'une console ouverte.

### Le premier admin

Par une commande, jamais par une route :

```bash
flask creer-admin <identifiant>       # le mot de passe est demandé, jamais en argument
```

Une route de création ouverte « juste pour le premier » est le genre de chose
qui reste. En argument de commande, le mot de passe finirait dans l'historique
du shell et dans la liste des processus.

## Les routes

| Méthode | Route | Rôle | Ce que ça fait |
| --- | --- | --- | --- |
| `POST` | `/admin/connexion` | — | ouvre une session |
| `POST` | `/admin/deconnexion` | connecté | ferme la session |
| `GET` | `/admin/moi` | connecté | qui je suis, mes rôles |
| `GET` | `/admin/participants` | organisateur | la liste |
| `POST` | `/admin/participants` | organisateur | ajoute à chaud |
| `POST` | `/admin/participants/<id>/dossard` | organisateur | réaffecte |
| `POST` | `/admin/reussites` | organisateur | saisie manuelle |
| `DELETE` | `/admin/reussites/<id>` | organisateur | corrige une erreur |
| `GET` | `/admin/dossards` | organisateur | la page imprimable |
| `GET/POST` | `/admin/comptes` | **admin** | gestion des comptes |

Les deux routes existantes (`/admin/import/*`) passent de la clé d'API à la
session, sans changer de comportement.

## Le contrôle d'accès

```python
@exige_role("organisateur")     # admin l'a implicitement
```

**Fail closed** : le défaut est de refuser. Un rôle inconnu, une session
illisible, une session expirée, un utilisateur supprimé entre-temps — tous
donnent `401`. Il n'y a pas de branche « on laisse passer en cas de doute ».

C'est la leçon directe du 28/08 : `@exige_cle_api` en mode toléré **laissait
passer** une requête sans clé, et cette tolérance — parfaitement justifiée pour
les routes des juges — avait contaminé l'administration.

## L'impression des dossards

Une page HTML, imprimée par le navigateur. Pas de PDF : ça ajouterait une
dépendance pour reproduire ce que `Ctrl+P` fait déjà.

Format repris du classeur (onglet `QR Code`), **répété** sur des pages à
découper : le dossard en gros, le QR qui l'encode, le nom et la catégorie pour
qu'un organisateur donne le bon papier à la bonne personne.

**Le QR est généré localement**, en SVG, sans aucun appel extérieur. Le classeur
appelle `api.qrserver.com` : cela envoie les dossards à un tiers, et ne
fonctionne pas si la connexion tombe — deux raisons suffisantes.

L'encodeur QR tient en ~150 lignes pour ce qu'on encode (un nombre, donc le mode
numérique, correction M). Écrire un encodeur QR générique serait déraisonnable ;
en écrire un qui encode des dossards ne l'est pas.

## Fichiers

| Fichier | Nature |
| --- | --- |
| `climbcontest/auth_session.py` | **nouveau** — sessions, rôles, décorateurs |
| `climbcontest/comptes.py` | **nouveau** — création, mot de passe, rôles |
| `climbcontest/qr.py` | **nouveau** — encodeur QR local, en SVG |
| `climbcontest/routes/admin.py` | les routes ci-dessus |
| `climbcontest/templates/admin.html` | **nouveau** — la console |
| `climbcontest/templates/dossards.html` | **nouveau** — la page imprimable |
| `climbcontest/cli.py` | **nouveau** — `flask creer-admin` |

## Ce qui pourrait mal tourner

| Risque | Parade |
| --- | --- |
| `SECRET_KEY` laissée par défaut | l'administration refuse de démarrer, et le dit |
| Un cookie volé sur le wifi de la salle | HTTPS obligatoire, cookie `Secure` + `HttpOnly` + `SameSite=Lax` |
| Force brute sur la connexion | temporisation après échec, et journalisation avec l'adresse |
| Un organisateur supprime une réussite par erreur | la suppression laisse une trace |
| La console tombe pendant la compétition | les juges continuent : elle est **indépendante** des routes `v2`/`v3` |
