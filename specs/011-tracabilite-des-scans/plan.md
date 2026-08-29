# 011 — Plan

Trois itérations, livrables séparément et dans cet ordre. L'ordre n'est pas
neutre : IT1 rend le téléphone utile **tout seul**, sans rien attendre du
serveur. Si la compétition arrivait avant la fin, on s'arrêterait là avec
quelque chose qui sert déjà.

## IT1 — Le téléphone se souvient

- [ ] `IdentiteAppareil` : création à la première ouverture, lecture, renommage.
- [ ] `HistoriqueScans` : ajout d'un scan, changement d'état, relecture
      (dernière ligne gagnante), purge à 30 jours.
- [ ] `Server` note chaque scan validé, puis son sort (partie / refusée).
- [ ] Écran « Mes scans » : liste inversée, filtre « pas parti », référence
      courte.
- [ ] Réglages : champ « nom de ce téléphone », lien vers l'écran des scans.

## IT2 — Le serveur retient qui a parlé

- [ ] Trois colonnes, ajoutées par `COLONNES_AJOUTEES`.
- [ ] `POST /api/v3/successes` lit `appareil` s'il est là, l'ignore sinon.
- [ ] L'application envoie son identité.
- [ ] Commentaire de `saisie_par` corrigé.

## IT3 — La page de contrôle

- [ ] `GET /api/v3/appareils` et `GET /api/v3/reussites`, réservées aux rôles.
- [ ] Onglet « Appareils » dans la console : liste, silence de plus de dix
      minutes mis en évidence, recherche par référence.

## Plan de test

Écrit **avant** l'implémentation, comme le veut la méthode.

### Android — JVM, sans émulateur

| Module | Scénario | Résultat attendu |
| --- | --- | --- |
| `IdentiteAppareil` | premier lancement | un identifiant est créé et écrit |
| `IdentiteAppareil` | deuxième lancement | **le même** identifiant, pas un nouveau |
| `IdentiteAppareil` | fichier corrompu | un identifiant neuf, aucune exception |
| `IdentiteAppareil` | renommage | l'identifiant ne bouge pas, le nom change |
| `HistoriqueScans` | un scan ajouté | il apparaît, état « en attente » |
| `HistoriqueScans` | scan puis acquittement | une seule entrée, état « partie » |
| `HistoriqueScans` | scan, refus, renvoi réussi | une seule entrée, état final « partie », motif conservé |
| `HistoriqueScans` | ligne illisible au milieu | les autres sont lues, aucune exception |
| `HistoriqueScans` | purge | ce qui a plus de 30 jours disparaît, le reste est intact |
| `HistoriqueScans` | purge alors que des scans sont **en attente** | **`file.jsonl` est intact** — c'est le test qui verrouille la garantie de la spec |
| `ClimbContestApi` | envoi avec identité | le corps contient `appareil.id` et `appareil.nom` |
| `ClimbContestApi` | envoi sans nom | `appareil.nom` absent, l'envoi passe |

### Backend — pytest

| Module | Scénario | Résultat attendu |
| --- | --- | --- |
| `lot` | lot avec `appareil` | les trois colonnes sont renseignées |
| `lot` | lot **sans** `appareil` | 200, colonnes vides, aucune régression |
| `lot` | `appareil` mal formé (nombre, tableau, nom de 500 caractères) | la réussite est **enregistrée quand même**, colonnes vides ou nom tronqué |
| `lot` | même lot envoyé deux fois | une seule réussite, comme aujourd'hui |
| `admin` | saisie manuelle | colonnes appareil vides, `saisie_par` renseigné |
| `schema` | base déjà créée sans les colonnes | les colonnes sont ajoutées, les données restent |
| `appareils` | deux appareils, l'un muet depuis 15 min | le silencieux est signalé |
| `appareils` | visiteur non authentifié | 401 |
| `reussites` | recherche d'une `ref` connue | grimpeur, bloc, heure |
| `reussites` | recherche d'une `ref` inconnue | réponse explicite, pas une liste vide ambiguë |
| `reussites` | aucune compétition active | pas de plantage |

### À l'écran

Les défauts qui ne sortent qu'en regardant — c'est la leçon de la refonte de
l'app juge, où trois défauts sur dix-neuf n'étaient visibles nulle part ailleurs.

| Écran | À vérifier |
| --- | --- |
| « Mes scans », vide | dit quelque chose d'utile, pas une page blanche |
| « Mes scans », 200 lignes | défile sans à-coups, la référence reste lisible |
| « Mes scans », filtre actif | on comprend qu'un filtre est actif |
| Réglages | le champ de nom se saisit au clavier d'un téléphone, sans masquer ce qu'on tape |
| Console, onglet Appareils | le silencieux **saute aux yeux** parmi cinq appareils sains |
| Console, recherche | une référence introuvable donne une réponse nette |
