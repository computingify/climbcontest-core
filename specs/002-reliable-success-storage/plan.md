# Plan d'implémentation : 002 — La base devient la source de vérité

## Approche

Quatre itérations. La première pose le modèle et les tests ; les suivantes ne
touchent qu'une couche à la fois. **Le contrat de l'application `v3.1.4` est
vérifié à chaque itération**, pas seulement à la fin : c'est la seule chose qui
ne doit jamais casser.

Branche : `feat/002-reliable-success-storage`. PR à la fin, merge par Adrien.

---

## IT1 — Le modèle et son socle

- [ ] 1. `climbcontest/` : fabrique d'application, configuration, session
- [ ] 2. `models.py` : `Competition`, `Participant`, `Bloc`, `Circuit`, `BlocCircuit`, `Success`, `Utilisateur`, `UtilisateurRole`
- [ ] 3. `migrations/001_initial.sql` + exécuteur idempotent sous verrou
- [ ] 4. **Fin du `drop_all()`** — création si absent, jamais de destruction
- [ ] 5. `conftest.py` : base en mémoire, jeux de données
- [ ] 6. Tests du modèle : unicité, nullabilité, cascades
- [ ] 7. **Vérification** : 4 workers gunicorn démarrent sans effacer la base

## IT2 — Les réussites survivent

- [ ] 8. `Success` avec `UNIQUE (participant_id, bloc_id)` et `sheet_synced_at`
- [ ] 9. `enregistrer_reussite()` : idempotent, écrit avant de répondre
- [ ] 10. Routes `/climber/name`, `/bloc/name`, `/success` réécrites, **contrat inchangé**
- [ ] 11. Plus aucun appel Google dans le chemin d'une requête juge
- [ ] 12. `/health` expose le nombre de réussites non synchronisées
- [ ] 13. **Vérification** : redémarrage en charge, aucune perte
- [ ] 14. **Vérification** : double envoi → une ligne, `201` deux fois

## IT3 — Le classeur devient un miroir

- [ ] 15. `sheets/client.py` : lecture seule, timeouts, erreurs typées
- [ ] 16. `sheets/mirror.py` : rejeu depuis la base, marquage **après** succès
- [ ] 17. Verrou consultatif : un seul worker synchronise
- [ ] 18. `sheets/importer.py` : import tolérant, idempotent, avec rapport
- [ ] 19. Route `POST /admin/import/sheet` + `GET /admin/import/rapport`
- [ ] 20. **Vérification** : API Google en erreur → rien n'est perdu, retenté
- [ ] 21. **Vérification** : classeur injoignable 10 min → tout est rattrapé
- [ ] 22. **Vérification** : import du jeu de novembre 2025 → 98 participants, 67 blocs

## IT4 — Catalogue, clé d'API, livraison

- [ ] 23. `catalogue_version` incrémentée à chaque changement
- [ ] 24. `GET /api/v2/catalog` complet et delta
- [ ] 25. Clé d'API en **mode toléré**, avec compteur d'appels sans clé
- [ ] 26. Réaffectation de dossard : refusée si le dossard porte une réussite
- [ ] 27. `CHANGELOG.md`, release `v0.2.0`
- [ ] 28. **Vérification** : déploiement sur la VM 110, sonde verte
- [ ] 29. **Vérification** : l'application `v3.1.4` fonctionne contre le nouveau backend

---

## Plan de test

| Module | Scénario | Attendu |
| --- | --- | --- |
| **modèle** | deux homonymes, clubs différents | les deux créés |
| | participant sans dossard | accepté |
| | même dossard, deux compétitions | accepté |
| | même dossard, même compétition | refusé |
| | participant sans club ni catégorie | accepté |
| **réussite** | même (participant, bloc) deux fois | une ligne, pas d'erreur |
| | deux juges simultanés, même passage | une ligne, `201` pour les deux |
| | bloc hors du circuit du participant | **acceptée** et stockée |
| | dossard inconnu | `400`, **aucun appel Google** |
| | redémarrage avec 40 réussites non synchronisées | les 40 sont toujours là |
| **miroir** | l'API Google renvoie une erreur | `sheet_synced_at` reste `NULL` |
| | l'API réussit | `sheet_synced_at` renseigné |
| | 3 workers, un seul verrou | une seule synchronisation |
| | 120 réussites en attente | envoyées par lots, toutes marquées |
| **import** | ligne à 4 colonnes | importée, signalée dans le rapport |
| | ligne de bloc trop courte | rejetée **explicitement** |
| | import rejoué | aucun doublon |
| | correction dans le classeur | reprise au réimport |
| | structure du classeur changée | échec explicite, rien de modifié |
| **catalogue** | ajout d'un participant | version incrémentée |
| | `?depuis=<version courante>` | `304` |
| | `?depuis=<ancienne>` | delta seul |
| **dossard** | réaffectation, dossard vierge | acceptée |
| | réaffectation, dossard avec réussite | **refusée**, message explicite |
| **compatibilité** | les 3 routes de `v3.1.4` | contrat identique, octet pour octet |
| **clé d'API** | absente | acceptée, comptée |
| | valide | acceptée |
| | invalide | `401` |

### Ce qui ne sera pas testé automatiquement

- L'application Android réelle contre le nouveau backend : test manuel, un
  téléphone, un vrai QR code (tâche 29).
- Le comportement sous vraie compétition : novembre.

---

## Ce que cette spec débloque

| Spec | Ce qu'elle attend d'ici |
| --- | --- |
| 003 app juge | `GET /api/v2/catalog` versionné |
| 004 classement | `Success` fiable + `BlocCircuit` pour le filtre par circuit |
| 005 console | `Utilisateur`/`UtilisateurRole`, `source=manuel`, réaffectation |
| 006 résultats | données fiables à afficher |
| 008 HelloAsso | `Participant.source`, identité stable |
