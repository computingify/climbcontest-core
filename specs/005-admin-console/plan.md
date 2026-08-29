# 005 — Plan

Quatre itérations, dans l'ordre décidé par Adrien le 29/08. Chacune est
livrable seule.

> **Une brique manquait.** L'architecture prévoyait `templates/admin.html` — la
> console elle-même. J'ai livré les routes JSON et marqué la spec « livrée »
> sans elle. Un organisateur ne peut pas utiliser `curl` un dimanche matin.
> Corrigé : voir IT5 ci-dessous.

## IT1 — Comptes et connexion

- [x] `comptes.py` — créer, vérifier un mot de passe, attribuer des rôles
- [x] `auth_session.py` — session signée, expiration, `@exige_role`
- [x] `flask creer-admin` — le premier compte, sans route ouverte
- [x] Refus de démarrer l'administration si `SECRET_KEY` est celle de dev
- [x] Les deux routes `/admin/import/*` passent de la clé d'API à la session
- [x] Tests

## IT2 — Participants à chaud

- [x] `GET`/`POST /admin/participants`, `POST .../dossard`
- [x] Le catalogue est incrémenté à chaque écriture — et un test vérifie qu'un
      ajout à chaud est **scannable dans la seconde** par la route du juge
- [x] La règle de réaffectation est respectée (déjà écrite, exposée)
- [x] Tests

## IT3 — Saisie manuelle

- [x] `POST /admin/reussites`, `DELETE /admin/reussites/<id>`
- [x] `source = manuel`, et l'identifiant du saisisseur
- [x] Tests

## IT4 — Impression

- [x] `qr.py` — QR local, en SVG. **Pas un encodeur maison** : j'en ai écrit un,
      il produisait des matrices d'allure correcte que *aucun* décodeur ne
      lisait. Remplacé par `segno` — Python pur, aucune dépendance
- [x] `GET /admin/dossards` — lot, par catégorie, ou un seul
- [x] Tests, dont le **décodage réel** par un décodeur indépendant

## IT5 — La console elle-même

- [x] `templates/admin.html` — connexion, participants, saisie, impression
- [x] Servie sur `/console`, **sans** authentification : c'est la page qui
      demande la connexion. Protéger le HTML n'apporterait rien — il ne contient
      aucune donnée — et un `401` afficherait une erreur de navigateur au lieu
      d'un écran de connexion
- [x] Une session qui expire ramène à la connexion **en le disant**, plutôt que
      de ressembler à une panne
- [x] Parcours complet exercé dans un navigateur : connexion, ajout d'un
      retardataire, saisie manuelle, doublon, dossard déjà pris, impression

---

## Plan de test

Écrit avant l'implémentation.

### Connexion et rôles

| Scénario | Attendu |
| --- | --- |
| Bon identifiant, bon mot de passe | session ouverte |
| Bon identifiant, mauvais mot de passe | `401`, journalisé avec l'adresse |
| Identifiant inconnu | `401`, **et le même délai** qu'un mot de passe faux |
| Route admin sans session | `401` |
| Session expirée | `401` |
| Cookie forgé | `401` |
| Utilisateur supprimé, session encore valide | `401` |
| `organisateur` sur une route `admin` | `403` |
| `admin` sur une route `organisateur` | accepté |
| Rôle inconnu en base | refusé — **fail closed** |
| `SECRET_KEY` par défaut | l'administration refuse de démarrer |
| Le mot de passe en base | **jamais en clair**, jamais journalisé |
| Les routes `v2`/`v3` des juges | **inchangées** |

La ligne « identifiant inconnu » compte : répondre plus vite pour un compte qui
n'existe pas révélerait quels identifiants sont valides.

### Participants à chaud

| Scénario | Attendu |
| --- | --- |
| Ajout complet | créé, catalogue incrémenté |
| Ajout sans dossard | accepté — l'inscrit qui n'est pas venu |
| Ajout sans nom | refusé |
| Dossard déjà pris | refusé, **avec le nom de celui qui le porte** |
| Deux homonymes | acceptés |
| Réaffectation d'un dossard vierge | acceptée |
| Réaffectation d'un dossard avec réussites | refusée, message clair |
| Sans session | `401`, rien n'est écrit |

### Saisie manuelle

| Scénario | Attendu |
| --- | --- |
| Couple valide | créée, `source = manuel`, saisisseur enregistré |
| Deux fois le même couple | une seule ligne |
| Dossard inconnu | refusé |
| Bloc inconnu | refusé |
| Elle compte au classement | **comme un scan** |
| Elle part au classeur | comme les autres |
| Suppression | effective, et tracée |
| Suppression d'un identifiant inexistant | message clair, pas un `500` |

### Impression

| Scénario | Attendu |
| --- | --- |
| Un QR encodant « 42 » | relu correctement par un décodeur |
| Page d'une catégorie | un dossard par participant ayant un numéro |
| Un dossard seul | une seule fiche |
| Aucun participant | page vide et lisible |
| Aucune requête extérieure | vérifié comme pour la page de résultats |
