# 003 — L'application juge devient locale d'abord

## Résumé

Aujourd'hui, chaque validation coûte au juge **trois allers-retours réseau
bloquants** : un pour vérifier le dossard, un pour vérifier le bloc, un pour
envoyer. Il attend devant son téléphone à chacun des trois, et chacun des trois
peut échouer.

Cette spec renverse la charge : l'application **télécharge le catalogue une
fois**, valide les QR codes **en local et instantanément**, et envoie les
réussites **par lots, en arrière-plan, depuis une file qui survit à la mort de
l'application**.

Le juge ne dépend plus du réseau pour travailler. Le réseau redevient ce qu'il
aurait toujours dû être : un détail d'acheminement.

## Pourquoi maintenant

C'est la demande initiale d'Adrien, mot pour mot : *« en premier on fiabilise
l'existant en faisant en sorte de minimiser le volume de données échangé […]
nous pouvons avoir plusieurs dizaines de requêtes en même temps »*.

Le chiffrage est dans
[etat-des-lieux.md §7](../../docs/etat-des-lieux.md#7-volume-de-données-échangé--mesure-et-cible) :

| | Aujourd'hui | Estimé | **Mesuré le 28/08** |
| --- | --- | --- | --- |
| Requêtes HTTP | ~10 800 | ~360 | **817** |
| Octets sur le fil | ~8 Mo | ~110 ko | **696 ko** |
| Allers-retours **bloquants pour le juge** | **10 800** | 0 | **0** |

> **L'estimation était trop optimiste, et c'est la mesure qui fait foi.**
> Mesuré contre la VM 110 par `tools/mesurer_volume.py`, sur 200 validations
> réelles extrapolées à 3 600.
>
> L'écart vient de deux endroits. D'abord un lot de **5** et non de 10 — c'est
> le réglage retenu, pour qu'une réussite atteigne l'écran de résultats en moins
> de dix secondes. Ensuite le coût réel d'une réussite sur le fil : ~180 octets
> une fois les en-têtes HTTP amortis sur le lot, pas 30.
>
> Le gain reste de **13× sur les requêtes** et **6,5× sur le volume**. Mais le
> chiffre qui compte n'est aucun des deux : c'est **10 800 → 0** allers-retours
> pendant lesquels un juge attendait devant son téléphone.
>
> Détail du coût, par téléphone et par journée : catalogue complet **14 ko** une
> seule fois, 96 rafraîchissements `304` pour **27 ko** au total, et **655 ko**
> pour les 3 600 réussites.

Le problème n'a jamais été le débit. C'est le **nombre d'allers-retours**,
chacun avec sa latence, chacun capable d'échouer, chacun bloquant un juge.

Et ça règle **R9** — l'application est inutilisable dès que le réseau tombe,
ce qui, dans une salle d'escalade en sous-sol avec 125 personnes sur le même
point d'accès, n'est pas un cas d'école.

## Périmètre

### Inclus

1. **Catalogue local** téléchargé au démarrage : participants, blocs, et la
   version du catalogue. ~6 à 10 ko compressés.
2. **Validation des QR codes hors ligne**, instantanée, sans requête.
3. **Rafraîchissement du catalogue en cours de compétition** — obligatoire :
   des participants sont ajoutés quelques minutes avant, voire *pendant*, et
   des dossards sont réaffectés (voir
   [contraintes-metier.md](../../docs/contraintes-metier.md)).
4. **Repli réseau sur QR inconnu** : un dossard absent du catalogue local n'est
   pas refusé sèchement — l'application demande au serveur et rafraîchit son
   catalogue. C'est le cas du participant inscrit il y a dix minutes.
5. **File d'attente persistante** des réussites, qui survit à la fermeture de
   l'application, au redémarrage du téléphone et à la batterie vide.
6. **Envoi par lots** en arrière-plan, avec reprise et retrait exponentiel.
7. **Indicateur visible** du nombre de réussites en attente.
8. **Nouvelle route serveur** d'envoi par lots, versionnée `v3`, **à côté** des
   trois routes figées `v2` qui restent en service.
9. **Tests JVM** pour toute la logique, sans émulateur.

### Explicitement exclu

- La version iPhone (spec 007) — mais la logique métier extraite ici doit être
  celle qu'on portera.
- Le moteur de classement (spec 004) et la page résultats (spec 006).
- La console d'administration (spec 005), donc **le catalogue reste alimenté
  par l'import du classeur** pour l'instant.
- Le mode « auto-évaluation » existant : conservé tel quel, non retravaillé.

## La contrainte qui commande le reste

> **Les trois routes `v2` restent en service, inchangées, pendant toute la
> transition.**

Raisons, dans l'ordre d'importance :

1. Un juge peut arriver le jour J avec une version ancienne installée. Adrien a
   confirmé que republier sur le Play Store n'est pas un problème — mais rien ne
   garantit que les 25 téléphones auront pris la mise à jour.
2. Le plan de repli ([plan-de-repli.md](../../docs/plan-de-repli.md)) suppose
   que la `v3.1.4` gelée fonctionne contre le backend de production.

La route de lot est donc **ajoutée**, jamais substituée. Les deux coexistent
jusqu'à ce qu'une compétition entière se soit passée sans un seul appel `v2`.

## Critères d'acceptation

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| A1 | Un scan de dossard connu est validé **sans aucune requête réseau** | Test JVM : serveur factice, zéro requête enregistrée |
| A2 | Un scan de bloc connu est validé sans requête | idem |
| A3 | Mode avion complet : 20 validations passent, rien n'est perdu | Test JVM avec transport en échec permanent, puis rétabli |
| A4 | L'application tuée entre la validation et l'envoi ne perd rien | Test JVM : on écrit la file, on instancie un dépôt neuf sur le même dossier |
| A5 | Un dossard **inconnu du catalogue** déclenche un repli réseau, pas un refus | Test JVM : catalogue sans le dossard, serveur qui le connaît → accepté |
| A6 | Un dossard inconnu **du serveur aussi** est refusé clairement | Test JVM |
| A7 | Le même couple envoyé deux fois ne crée qu'une réussite | Test E2E backend, sur vrai gunicorn |
| A8 | Un lot partiellement invalide est accepté **pour ce qui est valide** | Test E2E : 3 valides + 1 dossard inconnu → 3 enregistrées, 1 signalée |
| A9 | Le catalogue se rafraîchit sans redémarrer l'application | Test JVM : version change, nouveau participant reconnu |
| A10 | Le juge voit le nombre de réussites en attente | Test JVM sur l'état exposé |
| A11 | Les trois routes `v2` répondent exactement comme avant | Les tests de contrat existants, inchangés |
| A12 | Le volume est **mesuré**, pas supposé | Banc : 3 600 validations, octets comptés, comparés au tableau ci-dessus |

`A12` est un critère à part : la spec existe pour réduire un chiffre. Si le
chiffre n'est pas mesuré après coup, on n'a rien prouvé.

## Cas limites, et ce qu'on en fait

| Situation | Décision |
| --- | --- |
| Participant inscrit **pendant** la compétition | Repli réseau (A5) + rafraîchissement du catalogue. Le cas est explicitement au programme, pas une exception |
| **Dossard réaffecté** pendant la compétition | Le catalogue rafraîchi fait foi. La file contient des dossards, pas des identités : le serveur résout le dossard **au moment de l'enregistrement**, donc une réaffectation ne réécrit pas le passé |
| Réussite en file dont le dossard a été réaffecté depuis | Le serveur l'enregistre sur le participant **actuellement** porteur du dossard. C'est le comportement voulu : la contrainte métier interdit de réaffecter un dossard qui a déjà des résultats, donc la file ne peut pas être ambiguë. **À confirmer avec Adrien** — voir Q3 |
| Deux juges valident le même couple | Absorbé par l'unicité `(participant, bloc)`. Les deux voient un succès |
| Téléphone à court de batterie, file non vide | La file est sur disque. Au rallumage, l'envoi reprend seul |
| Le serveur répond 401 (mode strict activé par erreur) | La file **n'est pas vidée**. C'est un échec permanent côté client, signalé au juge, pas une perte |
| Catalogue jamais téléchargé (premier lancement hors ligne) | L'application ne peut pas valider en local : elle bascule en mode `v2`, avec les trois requêtes. Dégradé, mais fonctionnel |
| Horloge du téléphone fausse | L'horodatage client est **indicatif** ; le serveur pose le sien. On ne trie jamais sur l'heure du client |

## Questions ouvertes pour Adrien

**Q1 — Taille de lot et délai d'envoi.** Je propose : envoyer dès qu'il y a
**5 réussites en attente**, ou au bout de **10 secondes**, le premier des deux.
Sur un rythme de compétition, ça met une réussite dans le classeur en moins de
10 s tout en divisant les requêtes par ~5. Plus court = plus de requêtes ; plus
long = un écran de résultats en retard. Est-ce que 10 s te va ?

**Q2 — Faut-il un bouton « tout envoyer maintenant » ?** Utile en fin de
compétition, pour être sûr que rien ne traîne avant d'éteindre les téléphones.
Je penche pour oui, discret, sur l'écran de réglages.

**Q3 — Réaffectation de dossard et file d'attente.** Tu as dit qu'on ne
réaffecte un dossard que s'il n'a **aucun résultat**. Mais avec une file
d'attente, une réussite peut exister sans être encore arrivée. Scénario : le
dossard 42 est scanné par un juge, la réussite reste 8 s en file ; pendant ce
temps un organisateur réaffecte le 42 à quelqu'un d'autre parce qu'il « n'a
aucun résultat ». La réussite arrive ensuite et se colle au **nouveau**
porteur. Je propose que la console d'administration (spec 005) **refuse une
réaffectation tant qu'il reste des réussites non consolidées** pour ce dossard,
et que la route de lot renvoie le nombre de réussites en attente. Est-ce que ça
te paraît la bonne barrière, ou tu préfères qu'on interdise la réaffectation
pendant toute la durée de la compétition ?

**Q4 — Le mode dégradé `v2` doit-il être visible ?** Si le catalogue n'a jamais
pu être téléchargé, l'application marche mais lentement. Faut-il l'afficher au
juge (« mode dégradé, vérifie le réseau ») ou rester silencieux ?
