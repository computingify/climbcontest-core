# 006 — Plan

## IT1 — La page et ses deux modes

- [x] `resultats.html` — page autonome, sans dépendance externe
- [x] Mode spectateur : catégories, classement, recherche
- [x] Mode mur : rotation automatique, grande échelle
- [x] Rafraîchissement toutes les 15 s, âge du calcul affiché
- [x] Les états dégradés : pas de compétition, classement vide, backend tombé
- [x] Routes `/resultats` et `/` côté Flask
- [x] Tests — 20, plus la vérification navigateur ci-dessous

## IT2 — Vérification réelle

- [x] Ouverte dans un navigateur, avec le jeu de développement (98 grimpeurs,
      742 réussites, 10 groupes)
- [x] Lisibilité vérifiée à l'échelle d'un écran 1080p → nom **42 px**,
      score 48 px, rang 53 px, titre 82 px
- [x] Aucune requête externe → **2 requêtes en tout** : la page, et l'API.
      Mesuré dans le navigateur, pas déduit du source
- [x] Comportement quand on arrête le backend → **24 lignes conservées**,
      « hors ligne — dernier classement il y a 30 s » en rouge
- [x] Rotation du mode mur → vérifiée sur 23 s, deux catégories vues
- [x] Recherche → par nom, par dossard, et sans résultat
- [x] Contrastes → tous ≥ **5,6:1**
- [x] Largeur 390 px → aucun débordement horizontal

---

## Plan de test

Écrit avant l'implémentation.

### Ce que le serveur doit rendre

| Scénario | Attendu |
| --- | --- |
| `GET /resultats` | 200, du HTML |
| `GET /resultats?mur` | 200, la même page |
| `GET /` | la page, pas un JSON de service |
| La page ne contient aucune URL externe | aucun `http://` ou `https://` vers un autre domaine |
| La page est servie même sans compétition active | 200 — c'est la page qui gère le cas, pas le serveur |
| Content-Type | `text/html` |

### Ce que la page doit faire

| Scénario | Attendu | Comment |
| --- | --- | --- |
| Classement normal | les lignes s'affichent, triées par rang | navigateur |
| Recherche par nom | le grimpeur est isolé | navigateur |
| Recherche par dossard | idem | navigateur |
| Recherche sans résultat | message, l'écran ne se vide pas | navigateur |
| Mode mur | rotation entre catégories | navigateur |
| Une seule catégorie | pas de rotation | navigateur |
| Backend arrêté | dernier classement gardé, âge en rouge | navigateur + arrêt du serveur |
| Aucune compétition | message explicite | navigateur |
| Classement vide | message d'attente | navigateur |
| Nom très long | tronqué, pas de débordement | navigateur |
| Largeur 360 px | aucun débordement horizontal | navigateur |
| Contraste | ≥ 4,5:1 partout | mesure |

### Ce qui ne doit PAS sortir

| Champ | Affiché ? |
| --- | --- |
| nom, club, catégorie | oui — publics, imprimés sur les dossards |
| dossard, score, rang, nombre de blocs | oui |
| date de naissance, contact, identifiant interne | **non**, et rien ne les expose |
