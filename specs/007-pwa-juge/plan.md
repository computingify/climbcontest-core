# 007 — Plan

Quatre itérations. Chacune laisse une application **utilisable** : si novembre
arrive trop vite, on s'arrête à la dernière terminée.

## IT1 — Un iPhone peut juger

- [x] `routes/pwa.py` : `/juge` sert la coquille.
- [x] Le jeton : lu dans le fragment, rangé, adresse nettoyée.
- [x] `CLIMBCONTEST_API_KEY_PWA` entre dans les clés acceptées.
- [x] Scan : `BarcodeDetector`, repli jsQR versé dans le dépôt.
- [x] Envoi direct, avec le même écran que l'Android : deux cartes, un bouton.

## IT2 — Elle survit au réseau

- [x] Catalogue local en IndexedDB, `If-None-Match`.
- [x] File persistante, acquittements, invariant « rien ne sort sans verdict ».
- [x] Envoi par lots, retrait exponentiel.
- [x] Verrou entre onglets.

## IT3 — La parité

- [x] Journal de tous les scans, purge à 30 jours.
- [x] Identité d'appareil et nom.
- [x] Refusées conservées et renvoyables.
- [x] Réglages, voyant de connexion.

## IT4 — Installable

- [ ] Manifeste et icônes.
- [ ] Service worker : la coquille hors ligne, **jamais** les appels API.
- [ ] Bandeau d'installation.

## Plan de test

Écrit avant l'implémentation.

### Ce qui se teste sans navigateur

La logique pure est extraite dans des modules sans `document` ni `fetch`, et
testée sur Node — le même partage que côté Android, où `DecisionEnvoi`,
`Catalogue` et `FileDeReussites` se testent sans émulateur.

| Module | Scénario | Attendu |
| --- | --- | --- |
| jeton | fragment présent | rangé, adresse nettoyée |
| jeton | fragment absent, jeton déjà rangé | on garde l'ancien |
| jeton | fragment vide | on ne l'écrase pas avec du vide |
| file | ajout puis acquittement | disparaît de la file |
| file | envoi sans réponse | **reste** en file |
| file | réponse partielle | seul l'acquitté sort |
| file | même lot envoyé deux fois | une seule entrée |
| politique | 5 en attente | envoi |
| politique | 1 en attente depuis 2 s | pas d'envoi |
| politique | après 3 échecs | attente de 8 s |
| catalogue | 304 | version conservée |
| catalogue | version plus récente | remplacé |
| historique | scan, refus, renvoi réussi | une entrée, état final « partie » |
| historique | purge à 30 jours | la file reste **intacte** |
| verrou | deux onglets | un seul envoie |
| verrou | détenteur mort depuis 30 s | le bail est repris |

### Ce qui ne se teste qu'à l'écran

| À vérifier | Où |
| --- | --- |
| Le scan fonctionne | **Safari iOS d'abord**, puis Chrome Android |
| Caméra refusée | le message dit quoi faire |
| Installation sur l'écran d'accueil | iPhone réel |
| La file survit à la fermeture complète | iPhone réel, wifi coupé |
| Le voyant ne ment pas au retour au premier plan | iPhone réel |

⚠️ **Aucun émulateur ne remplace un vrai iPhone ici.** Safari iOS a ses propres
règles sur la caméra, le stockage des PWA et le cycle de vie. C'est le point du
plan de test qui demande un appareil d'Adrien.
