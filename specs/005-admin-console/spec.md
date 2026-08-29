# 005 — La console d'administration

## Résumé

Tout ce qui a été livré jusqu'ici s'adresse aux juges (l'application), aux
spectateurs (la page de résultats) ou à personne (le backend). Il n'existe
**aucun endroit où un organisateur puisse agir** le jour de la compétition.

Concrètement, aujourd'hui : un participant qui s'inscrit le matin ne peut pas
être ajouté sans passer par le classeur puis un réimport ; une réussite perdue
— QR illisible, téléphone à plat — est perdue pour de bon ; et les deux routes
d'administration qui existent sont protégées par une **clé d'API partagée**,
mesure d'attente posée en urgence le 28/08 après avoir constaté qu'elles étaient
ouvertes sur Internet.

## Périmètre pour novembre 2026

Adrien a retenu les quatre briques, le 29/08 :

| # | Brique | Pourquoi elle compte le jour J |
| --- | --- | --- |
| 1 | **Comptes et connexion** | Tout le reste doit vivre derrière. Remplace la clé partagée |
| 2 | **Participants à chaud et réaffectation** | Quelqu'un s'inscrit à 8 h 45 ; un dossard change de main |
| 3 | **Saisie manuelle d'une réussite** | Le seul moyen de rattraper ce qui n'a pas été scanné |
| 4 | **Impression des dossards** | Un lot à l'installation, un seul pour un retardataire |

### Explicitement exclu

- Les archives et la consultation des éditions passées.
- Le paramétrage de la compétition (options, connexion au classeur).
- L'import HelloAsso (spec 008).
- Le remplacement complet du classeur : **il reste le miroir**, la console
  devient la source de saisie (décision du 29/08).

## Les décisions déjà prises

| Sujet | Décision, 29/08 |
| --- | --- |
| Rôles | **deux** : `admin` et `organisateur` |
| Le classeur | reste le **miroir**, la console devient la source |
| Format des dossards | celui de l'onglet `QR Code` du classeur, **répété** sur des pages à découper |
| Ordre de livraison | comptes → participants → saisie → impression |

### Les deux rôles, et rien de plus

```
admin          comptes, compétitions, paramètres, classeur
               + tout ce que fait l'organisateur

organisateur   participants à chaud, réaffectation,
               saisie manuelle, impression des dossards

(personne)     la page de résultats, déjà publique
```

Assez pour que personne ne casse rien par accident, sans transformer une journée
bénévole en gestion de droits.

## Critères d'acceptation

### Comptes et connexion — IT1

- [ ] Un compte a un identifiant, un mot de passe **haché**, et un ou plusieurs rôles.
- [ ] Le mot de passe n'est **jamais** stocké ni journalisé en clair.
- [ ] Une session expire, et l'expiration est vérifiée à chaque requête.
- [ ] Une route d'administration sans session valide répond `401` — **fail closed**.
- [ ] Un `organisateur` ne peut pas gérer les comptes.
- [ ] Le **premier admin** se crée par une commande, jamais par une route ouverte.
- [ ] Les tentatives échouées sont journalisées, avec l'adresse d'origine.
- [ ] Les routes des juges (`v2`, `v3`) ne sont **pas** touchées.

### Participants à chaud — IT2

- [ ] Ajouter un participant en cours de compétition, sans redémarrage.
- [ ] Le **catalogue est incrémenté** : les téléphones le voient en moins de 20 s.
- [ ] Réaffecter un dossard libre.
- [ ] Réaffecter un dossard **portant des réussites** est refusé, avec un message clair.
- [ ] Deux homonymes peuvent coexister.
- [ ] Un dossard déjà pris dans la compétition est refusé.

### Saisie manuelle — IT3

- [ ] Enregistrer une réussite `(grimpeur, bloc)` depuis la console.
- [ ] Elle compte au classement **exactement comme un scan**.
- [ ] Elle porte `source = manuel` et **l'identifiant de qui l'a saisie**.
- [ ] Elle part au classeur comme les autres.
- [ ] Saisir deux fois le même couple ne crée qu'une réussite.
- [ ] **Supprimer** une réussite saisie par erreur, en laissant une trace.

### Impression — IT4

- [ ] Une page imprimable reproduisant le format du classeur, répétée.
- [ ] Un lot (toute une catégorie, ou toute la compétition).
- [ ] Un dossard seul, pour un arrivant de dernière minute.
- [ ] Le QR est généré **localement**, sans service extérieur.

Ce dernier point n'est pas un détail : le classeur fabrique ses QR en appelant
`api.qrserver.com`, ce qui **envoie les dossards à un tiers** et ne marche pas
si la connexion tombe. On génère nous-mêmes.

## Cas limites

| Situation | Comportement |
| --- | --- |
| Session expirée en pleine saisie | `401`, la page ramène à la connexion sans perdre le formulaire |
| Deux organisateurs saisissent la même réussite | une seule ligne, les deux voient un succès |
| Ajout d'un participant sans dossard | accepté — c'est l'inscrit qui n'est pas venu |
| Dossard déjà attribué | refusé, avec le nom de celui qui le porte |
| Suppression d'une réussite qui n'existe pas | message clair, pas une erreur serveur |
| Impression avant tout import | page vide et lisible, pas un plantage |
| Le premier admin n'existe pas encore | la console le dit, et donne la commande à lancer |

## Ce qui reste ouvert

**Le mot de passe oublié.** Il n'y a pas de serveur de courriel dans le
périmètre. Proposition : l'admin réinitialise depuis la console, et le tout
premier admin par la commande en ligne. À confirmer.
