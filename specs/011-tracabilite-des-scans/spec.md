# 011 — Tracer les scans, du téléphone jusqu'au serveur

## Résumé

Aujourd'hui, une réussite qui n'arrive pas ne laisse **aucune trace exploitable**.
Le juge dit « je l'ai envoyée », l'organisateur regarde le classement et ne la
voit pas, et personne ne peut trancher. Le téléphone efface sa file dès que tout
est acquitté (compactage), et le serveur ne sait pas quel appareil lui a parlé.

Cette spec ajoute les deux moitiés qui manquent, et le point de rencontre entre
elles :

1. côté téléphone, **la liste de tous les scans** qu'il a faits, avec l'état de
   chacun — parti, en attente, refusé ;
2. côté serveur, **quel appareil a envoyé quelle réussite**, et sous quelle
   référence ;
3. une **page de contrôle** dans la console, qui répond à la seule question qui
   compte le jour J : « ce scan-là est-il arrivé ? »

## Ce qui existe déjà, et pourquoi ça ne suffit pas

La spec 003 a donné au téléphone une file persistante (`file.jsonl`), un fichier
d'acquittements et un fichier de refus. Elle a résolu le bon problème — **ne rien
perdre** — mais elle a aussi, délibérément, effacé l'histoire :

> Le compactage n'a lieu que lorsque **tout** est acquitté, donc quand il n'y a
> plus rien à perdre.
> — `FileDeReussites`

Rien à perdre **pour l'envoi**. Mais pour un contrôle a posteriori, tout est
perdu : à la fin de la compétition, un téléphone qui a tout envoyé a une file
vide, et ne peut plus rien montrer.

Côté serveur, `Success` porte déjà `dossard_scanne`, `scanne_le` et `saisie_par`.
Ce dernier est documenté ainsi :

> Qui a saisi, quand c'est une saisie manuelle. NULL pour un scan : le juge n'est
> pas identifié, et il n'y a aucune raison de le devenir.
> — `models.py`

**Cette phrase est révisée par la présente spec.** La raison a été trouvée : le
contrôle. Mais la révision est étroite, et il faut la dire précisément — voir
ci-dessous.

## On trace un appareil, pas une personne

C'est la limite de la spec, et elle est volontaire.

`saisie_par` identifie **quelqu'un** : c'est un compte, avec un nom, et ça n'a de
sens que parce qu'une saisie manuelle est une intervention humaine sur les
données. Ici, on trace **un téléphone** : un identifiant technique, plus un nom
que le juge peut lui donner, du genre « Mur jaune ».

Ce que ça permet : repérer un téléphone qui n'envoie plus rien depuis vingt
minutes, retrouver un scan précis, comprendre qu'une zone entière manque au
classement.

Ce que ça ne permet pas, et qu'on ne cherche pas : savoir qui, parmi les
bénévoles, a validé quoi. Les téléphones changent de main dans la journée. Le nom
que le juge saisit désigne **un poste**, pas lui.

## Décisions prises (29/08)

| Question | Décision d'Adrien |
| --- | --- |
| Comment identifier le téléphone | **Un identifiant unique généré par l'application**, plus **un nom que le juge peut définir** lui-même dans l'application |
| Ce que la page doit permettre | **Voir ET retrouver un scan précis** — donc le serveur garde la référence donnée par le téléphone |
| Rétention sur le téléphone | **Effacement automatique au bout de 30 jours** |

## Périmètre

### Inclus

**Sur le téléphone**

- Un identifiant d'appareil, généré au premier lancement, stable ensuite.
- Un nom d'appareil, saisi par le juge dans les réglages, facultatif.
- Un journal de **tous** les scans, jamais compacté, avec l'état de chacun.
- Un écran qui liste ces scans, du plus récent au plus ancien, avec un filtre
  « seulement ce qui n'est pas parti ».
- Un effacement automatique de ce qui a plus de 30 jours.

**Sur le serveur**

- Trois colonnes sur `Success` : l'identifiant de l'appareil, son nom au moment
  de l'envoi, et la référence client.
- L'envoi par lots accepte l'identité de l'appareil, **sans l'exiger**.
- Deux routes de lecture, réservées aux comptes admin et organisateur.

**Dans la console**

- Une page « Appareils » : la liste des téléphones vus, ce que chacun a envoyé,
  et quand pour la dernière fois.
- Une recherche par référence, qui répond par oui ou par non.

### Exclu

- **Identifier le juge.** Voir plus haut : on trace un poste, pas une personne.
- **Refuser un appareil inconnu.** Le jour de la compétition, un téléphone qui
  marche doit marcher. Pas d'enregistrement préalable, pas de liste blanche.
- **Un identifiant matériel** (`ANDROID_ID`, IMEI, adresse MAC). Un UUID généré
  par l'application suffit, ne survit pas à une désinstallation — ce qui est
  exactement le comportement voulu — et n'expose rien de l'appareil.
- **Rejouer un scan depuis la console.** Le bouton « Renvoyer » existe déjà côté
  téléphone, et c'est là qu'il doit rester : la donnée est sur le téléphone.

## Critères d'acceptation

### Le téléphone

- [x] L'identifiant d'appareil est créé au premier lancement et **ne change
      plus** — ni au redémarrage, ni à la mise à jour de l'application.
- [x] Le juge peut donner un nom à son téléphone, et le changer. Le nom est
      facultatif : sans lui, tout fonctionne.
- [x] Le journal contient **tous** les scans validés, y compris ceux déjà partis
      et ceux refusés. Il n'est jamais compacté.
- [x] L'état de chaque scan est juste : en attente, parti, ou refusé avec son
      motif.
- [x] L'écran liste les scans du plus récent au plus ancien, et sait n'afficher
      que ce qui n'est pas parti.
- [x] Chaque ligne montre une référence courte, lisible à voix haute.
- [x] Un scan de plus de 30 jours disparaît du journal.
- [x] **L'effacement du journal ne peut jamais perdre une réussite non envoyée.**
      Le journal est une *vue* ; la file d'envoi de la spec 003 reste la source.

### Le serveur

- [x] Une réussite envoyée par un téléphone porte son identifiant, son nom au
      moment de l'envoi, et la référence client.
- [x] Le nom est **figé** à l'envoi : renommer le téléphone ne réécrit pas
      l'historique.
- [x] Une version de l'application qui n'envoie pas d'identité continue de
      fonctionner. Les colonnes restent vides.
- [x] Une saisie manuelle ou un import n'invente pas d'appareil : colonnes
      vides, `saisie_par` inchangé.
- [x] Le double envoi reste idempotent, exactement comme aujourd'hui.
- [x] Les deux routes de lecture refusent un visiteur non authentifié.

### La console

- [x] La page liste les appareils vus sur la compétition active, avec pour
      chacun le nombre de réussites et l'heure de la dernière.
- [x] Un appareil qui n'a plus rien envoyé depuis plus de dix minutes est
      **visible d'un coup d'œil** — c'est le signal qu'un juge est bloqué.
- [x] Chercher une référence répond : trouvée, avec le grimpeur, le bloc et
      l'heure ; ou non trouvée.
- [x] Aucune compétition active, ou aucune réussite : pas de plantage.

## Cas limites

| Cas | Comportement attendu |
| --- | --- |
| Le juge efface les données de l'application | Nouvel identifiant. L'ancien reste visible dans la console, avec ce qu'il avait envoyé. C'est une information, pas une anomalie. |
| Deux téléphones portent le même nom | Autorisé. L'identifiant les distingue, la page affiche les deux. Le jour J, personne n'a le temps de vérifier l'unicité d'un nom. |
| Le juge renomme son téléphone en pleine compétition | Les réussites déjà envoyées gardent l'ancien nom. La page montre donc deux lignes pour le même identifiant si on regroupe par nom — on regroupe par **identifiant**. |
| Une réussite est refusée puis renvoyée avec succès | Une seule ligne dans le journal du téléphone, dont l'état final est « partie ». Le motif du refus reste consultable. |
| Le téléphone est réinitialisé alors qu'il restait des réussites en file | **Elles sont perdues, et c'était déjà vrai.** La présente spec ne change rien à ça — mais la console montre désormais que cet appareil s'est tu, ce qui est la seule façon de s'en apercevoir le jour même. |
| Le serveur reçoit une référence déjà connue | Rien de nouveau : la contrainte d'unicité `(participant, bloc)` fait déjà l'idempotence. La référence n'est pas une clé. |
