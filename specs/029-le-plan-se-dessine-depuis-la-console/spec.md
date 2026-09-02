# Spec 029 — Le plan du mur se dessine depuis la console

> **Statut : soumise à la porte 2.** Écrite avant le code.
> Question d'Adrien du 02/09/2026 : « Est-ce que tu as prévu une page dans la
> console d'admin qui permet de lancer l'outil de design que tu as créé et qui
> enfin permet d'injecter ce nouveau plan via un bouton ? Sinon il faut le
> faire. »

## 1. Ce qui manque

La spec 028 a donné au club un plan qui ressemble à sa salle, et un outil pour
le dessiner. Mais l'outil vit dans `tools/`, **hors de l'application**, et le
plan est une **constante Python**.

Conséquence : changer le plan demande de modifier du code, d'ouvrir une PR et de
redéployer. Autrement dit, **il faut moi**. Un mur qui bouge un samedi matin
attend lundi.

Ce n'était pas visible tant que le plan était un relevé figé du classeur. Ça
l'est devenu au moment où il est devenu quelque chose qu'Adrien dessine.

## 2. Ce qu'on fait

### F1 — Le plan vit en base, et il est GLOBAL

Nouvelle table `reglage`, clé-valeur, une ligne :

| `cle` | `valeur` |
| --- | --- |
| `plan_du_mur` | le document JSON du plan |

⚠️ **En base, et pas dans un fichier du dossier de données.** Le runbook est
formel : c'est **la base seule** qui est recopiée toutes les dix minutes
(`docs/runbook-competition.md`). Un JSON posé à côté ne serait pas sauvegardé —
et une restauration ramènerait silencieusement l'ancien plan.

⚠️ **Global, et pas par compétition.** Le club a **un** mur ; c'est déjà la
position de la spec 028. Le ranger dans `competition.options` obligerait à le
redessiner à chaque édition, ou à inventer une reprise automatique — deux
mauvaises réponses à une question qui ne se pose pas.

### F2 — La constante devient le défaut, pas la source

`fiches.PLAN` reste dans le code et **ne bouge plus** : c'est le plan livré
d'usine, celui qui s'applique tant que personne n'a rien dessiné. `plan_pour()`
lit la base d'abord, la constante ensuite.

Un plan enregistré illisible ou invalide **retombe sur la constante** et le
journalise. Une impression de dossards la veille au soir ne doit pas échouer
parce qu'une ligne de base est abîmée.

### F3 — Une page de console, pas un fichier à ouvrir

`GET /admin/plan`, réservée à un organisateur, atteignable depuis une carte
**« Le plan de la salle »** dans la vue **Circuits**.

> Cette section annonçait « Compétition → Le mur », et aucune entrée de menu de
> ce nom n'a été créée. La carte a été posée dans **Circuits**, à côté des
> étiquettes de blocs et de l'impression des dossards — c'est-à-dire avec le
> reste du papier qu'on prépare. Le placement est meilleur ; c'est la spec qui
> est corrigée, pas le code rattrapé en douce.

Elle sert la planche de dessin — la même que `tools/plan-du-mur/`, à trois
différences près :

1. elle **charge le plan courant** au lieu du dernier dessin du navigateur ;
2. elle porte un bouton **« Enregistrer dans ClimbContest »** ;
3. **aucune police Google** : la règle du dépôt est qu'une page servie
   n'appelle rien à l'extérieur — on imprime parfois sans réseau. La planche
   prend la pile de polices de la console.

Le fichier de `tools/` **disparaît** : deux copies de 1 400 lignes divergeraient
en une semaine.

### F4 — Un bouton qui enregistre, et un qui revient en arrière

`POST /admin/plan` enregistre. `DELETE /admin/plan` efface la ligne et
**revient au plan d'usine** — c'est la sortie de secours si un dessin part de
travers un jour de compétition.

L'enregistrement dit ce qu'il a fait : « 17 murs, 3 repères enregistrés. Les
prochains dossards imprimés porteront ce plan. »

### F5 — La validation, côté serveur

⚠️ **Le plan cesse d'être du code pour devenir de la donnée saisie.** Elle est
rendue en SVG sur un document que 120 personnes reçoivent sur papier. Le
serveur ne fait donc confiance à rien :

| Contrôle | Refus |
| --- | --- |
| Structure (`vue`, `murs`, `reperes`) | 400 |
| `vue` : deux nombres, 40 à 400 | 400 |
| Au plus 200 murs, 50 repères | 400 |
| Chaque mur : 3 à 60 points, coordonnées dans la vue | 400 |
| `profil` inconnu | replié sur `vertical`, accepté |
| `zone` : au plus 3 caractères | tronqué |
| `texte` d'un repère : au plus 24 caractères | tronqué |
| Document au-delà de 256 ko | 413 |

Ce qui est réparable est réparé, ce qui ne l'est pas est refusé avec un message
qui nomme le mur fautif.

### F6 — Ce que la page montre avant d'enregistrer

Les trois aperçus existent déjà : papier à 37 mm, page web, téléphone. La page
de console y ajoute **ce qui va changer** — « 17 murs au lieu de 14, la zone Q
disparaît » — parce qu'enregistrer un plan modifie les dossards de tout le
monde.

## 3. Périmètre

**Exclu, à dessein :**

- **Un plan par compétition.** Voir F1.
- **L'historique des plans.** La table garde la dernière version. Revenir en
  arrière se fait en recollant un bloc qu'on a copié — la planche sait déjà le
  relire. Un historique serait une table de plus pour un besoin qui ne s'est
  jamais manifesté.
- **Le rendu à l'écran** (page de résultats, fiche en direct). Il appartient à
  la spec 026 depuis la décision d'Adrien du 02/09.

## 4. Critères d'acceptation

- [ ] **A1** — `GET /admin/plan` rend la planche, chargée du plan courant.
- [ ] **A2** — Anonyme → 401, rôle insuffisant → 403.
- [ ] **A3** — `POST` valide → la ligne est écrite, les dossards changent **sans
  redémarrage**.
- [ ] **A4** — `DELETE` → retour au plan d'usine.
- [ ] **A5** — Chaque contrôle de F5 refuse ce qu'il doit refuser.
- [ ] **A6** — Une ligne de base illisible → repli sur la constante, journalisé,
  aucune erreur rendue.
- [ ] **A7** — La page n'appelle **aucune** ressource extérieure.
- [ ] **A8** — `tools/plan-du-mur/` a disparu du dépôt.
- [ ] **A9** — Le tour complet — dessiner, enregistrer, imprimer — se fait sans
  toucher au code.

## 5. Cas limites

| Situation | Attendu |
| --- | --- |
| Base vide, aucun plan enregistré | La constante s'applique, la page l'affiche |
| Plan enregistré à zéro mur | Accepté ; la colonne « Le mur » disparaît du dossard |
| Deux organisateurs enregistrent en même temps | Le dernier gagne ; pas de verrou pour un geste aussi rare |
| Enregistrement pendant une impression en cours | La page déjà rendue garde l'ancien plan — c'est du papier, il est déjà parti |
| Un bloc en zone absente du nouveau plan | « Hors plan : zone Q. », comme aujourd'hui |
| Coordonnées hors de la vue | 400, en nommant le mur |
| JSON tronqué par le réseau | 400, rien n'est écrit |
