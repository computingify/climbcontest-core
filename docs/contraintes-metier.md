# Contraintes métier

Ce que le terrain impose et que le code doit encaisser. Recueilli auprès
d'Adrien le 28 août 2026. Ces contraintes traversent plusieurs specs — d'où ce
document séparé plutôt qu'une répétition dans chacune.

---

## 1. Les participants bougent pendant la compétition

C'est la contrainte la plus structurante, et celle que le code actuel encaisse le
plus mal.

| Situation | Quand | Fréquence |
| --- | --- | --- |
| Ajout d'un participant | quelques minutes avant le début | courant |
| Ajout d'un participant | **compétition déjà commencée** | ça arrive |
| **Réaffectation d'un dossard** | **en pleine compétition** | ça arrive |

### Ce que ça interdit

- **Charger la liste une fois au démarrage et ne plus y toucher.** C'est ce que
  fait le backend aujourd'hui.
- **Faire du dossard l'identité du grimpeur.** Le modèle actuel
  (`Climber.bib UNIQUE`) l'impose : si le dossard 42 change de main, il n'y a
  aucun moyen de distinguer les deux personnes.
- **Un catalogue figé dans l'app juge.** Le mode « local d'abord » de la spec 003
  doit prévoir un rafraîchissement en cours de compétition, sinon un participant
  ajouté à 14 h est refusé par toutes les tablettes.

### Ce que ça impose

1. **Une identité stable, distincte du dossard.** Le dossard devient un
   *attribut* du participant (celui qui est imprimé sur le QR), pas sa clé.
2. **Un journal des réaffectations**, horodaté : à quel moment le dossard 42 est
   passé de telle personne à telle autre.
3. **Un catalogue versionné** côté app : un numéro de version qui s'incrémente à
   chaque modification, et un delta à télécharger. Quelques centaines d'octets,
   pas un rechargement complet.
4. **Une page d'administration** (`/admin/participants`) permettant l'ajout et la
   réaffectation en direct, utilisable sous pression, depuis un téléphone.

### La règle de réaffectation — tranchée le 28/08

**Un dossard ne peut être réaffecté que s'il n'a aucun résultat.** Jamais sur un
dossard en cours de participation. C'est une règle dure, que la page dédiée doit
**interdire**, pas seulement déconseiller.

Le cas d'usage réel : un participant inscrit ne vient pas. Plutôt que d'imprimer
un nouveau dossard pour un arrivant de dernière minute, on lui donne celui de
l'absent.

Ce que ça simplifie — et c'est considérable :

- **aucune réécriture d'historique n'est jamais nécessaire.** Le dossard change
  de main alors qu'il ne porte rien ;
- le classement n'est jamais affecté rétroactivement ;
- il n'y a pas de choix à proposer à l'utilisateur au moment de la réaffectation.

Ce que ça n'enlève pas : il faut quand même une **identité stable** distincte du
dossard, parce que l'absent continue d'exister en base (inscrit, non présent,
sans dossard). Mais le modèle reste simple, et la contrainte « zéro résultat »
garantit qu'on n'a jamais à démêler des réussites.

**Contrôle à implémenter** : la réaffectation est refusée, avec un message
explicite, si le dossard porte au moins une réussite.

---

## 2. La page de paramétrage doit remplacer le classeur Google

Objectif énoncé le 28/08. Ce n'est pas un confort : c'est la fin de la
dépendance à un document externe pour faire tourner une compétition.

### Ce que fait le classeur aujourd'hui, et qu'il faudra reprendre

| Fonction du classeur | Onglet | Repris par |
| --- | --- | --- |
| Liste des participants | `Listes` | `/admin/participants` |
| Plan des blocs, zones, couleurs | `Plan` | `/admin/parametres` |
| Affectation bloc ↔ circuit | `Plan` | `/admin/parametres` |
| **Génération du contenu des QR codes** | `Plan` + `QR Code` | `/admin/impression` |
| Fiches et dossards à imprimer | `Fiches`, `QR Code` | `/admin/impression` (lot + unitaire) |
| Calcul du classement | `Résultats`, `Scratchs` | spec 004, déjà validé à 196/196 |
| Option de validation par couleur | `Inter` | `/admin/parametres`, **par compétition** |
| Saisie manuelle | `Saisie manuelle` | `/admin/saisie` |
| Podium, statistiques | `Podium`, `Stats` | spec 006 |
| Archives des éditions passées | `Archives / Bilan` | `/admin/archives` |

### Le point le moins évident : l'impression

Le classeur ne sert pas qu'à calculer, il **produit du papier**. Détail en
[§5](#5-limpression-des-dossards).

### La trajectoire

On ne débranche pas le classeur d'un coup. Trois étapes :

1. **Aujourd'hui** — le classeur est la source, le backend le lit et y écrit.
2. **Transition** — la base devient la source, le backend continue d'**écrire un
   miroir** dans le classeur. Redondance gratuite des données du jour J.
3. **Cible** — la page de paramétrage est la source, le classeur n'est plus
   utilisé. C'est à ce moment qu'il faudra revoir la question de la sauvegarde
   (la redondance gratuite disparaît).

---

## 3. Les inscriptions viennent de deux endroits

**HelloAsso** est la plateforme d'inscription à la compétition. Une amorce de
connexion existe déjà dans `climbBackEnd` (le projet de badgeuse), en
environnement bac à sable.

Mais — et c'est le point à ne pas oublier — **des inscriptions se font sur place
le jour de la compétition, sans passer par HelloAsso.**

### Ce que ça impose

- L'import HelloAsso est un **flux d'alimentation**, jamais la source unique.
- La saisie manuelle d'un participant reste indispensable et doit être aussi
  rapide que l'import.
- Il faudra un **rapprochement** : quelqu'un peut s'être inscrit en ligne *et*
  se présenter au guichet. Détection de doublon sur nom + date de naissance,
  probablement, avec validation humaine.
- L'import doit être **temps réel**, pas seulement rejouable : quelqu'un peut
  s'inscrire en ligne le matin de la compétition, **ou pendant**. Il faut
  récupérer l'inscription directement.
- **Et la rendre visible sur un tableau de bord**, pas seulement dans un journal.
  Précision d'Adrien : « il faut pouvoir avoir un dashboard dans la page admin et
  le voir sur cet écran ». Concrètement, la page `/admin/` affiche en permanence
  les inscriptions arrivées et non traitées — parce que derrière, il faut
  imprimer un dossard et l'apporter à la personne. Un message qui défile ou une
  ligne de log ne suffit pas : l'écran d'administration doit être **regardable
  en continu** pendant la compétition.

> ✅ **Traité par la [spec 008](../specs/008-helloasso-import/), livrée le
> 04/09/2026.** Les quatre points ci-dessus sont construits : l'import est un
> flux qui alimente une **salle d'attente**, la saisie manuelle est intacte, le
> rapprochement se fait sur nom + prénom + club avec validation humaine, et la
> vue *Inscriptions* est l'écran qu'on laisse ouvert. Une précision est venue de
> la règle FFME : la catégorie ne se saisit plus, elle **se calcule** sur
> l'année de naissance.
>
> 🔴 **Sécurité, à traiter indépendamment** : le `README.md` du dépôt public
> `climbBackEnd` contient l'identifiant, le **secret client** et des jetons
> HelloAsso (bac à sable). À révoquer avant toute reprise de ce code.
> C'est le risque R13 de l'[état des lieux](etat-des-lieux.md), et il reste
> **ouvert** : il demande d'être connecté au compte HelloAsso du club.

---

## 3 bis. Combien de monde, vraiment

Relevé le 28/08. Ces chiffres corrigent mes estimations initiales, qui étaient
basses.

| Population | Nombre | Ce qu'ils font |
| --- | --- | --- |
| **Juges** | **~25** | scannent et valident, en rafales |
| **Spectateurs** | **plus de 100** | consultent les résultats — mais tous n'ont pas de téléphone |
| Écran de la salle | 1 | rafraîchit en continu |

### La conséquence qui change la conception

**Le trafic dominant n'est pas celui des juges, c'est celui des spectateurs.**

| Source | Estimation en pointe |
| --- | --- |
| 25 juges, application « locale d'abord » (envois par lots) | ~5 req/min |
| 25 juges, application actuelle (3 requêtes par validation) | ~90 req/min |
| ~60 spectateurs rafraîchissant toutes les 15 s | **~240 req/min** |
| Écran de la salle | ~4 req/min |

Soit **250 à 350 requêtes/minute en pointe**, dont les trois quarts viennent des
spectateurs. C'est modeste en absolu, mais ça inverse la priorité :

- le **cache de la page résultats n'est pas un confort, c'est la pièce
  maîtresse** : avec un cache de 5 secondes, le classement est calculé au plus
  12 fois par minute quel que soit le nombre de spectateurs ;
- tout ce monde est derrière **le NAT de la salle**, donc **une seule IP
  publique** : le risque de bannissement CrowdSec est encore plus élevé
  qu'estimé ;
- le test de charge doit simuler **25 juges + 80 spectateurs depuis une seule
  adresse**, pas 40 clients indifférenciés.

---

## 4. Le format d'une compétition

| Fait | Conséquence |
| --- | --- |
| Une compétition dure **une journée** | pas de reprise multi-jours, pas d'état à conserver entre deux sessions |
| ~120 participants, ~50 à 67 blocs | dimensionnement confirmé |
| Catégories variables selon les éditions (U10→U17 selon les années) | rien ne doit être codé en dur |
| Un circuit par tranche d'âge, filles et garçons ensemble | déjà intégré au moteur de classement |
| La validation par couleur change d'une édition à l'autre | **option par compétition**, pas une constante |

---

## 5. L'impression des dossards

Sur **une imprimante ordinaire**, en deux modes :

| Mode | Quand | Contenu |
| --- | --- | --- |
| **Lot** | à l'installation de la compétition | tous les dossards, en planches |
| **Unitaire** | un participant s'inscrit le jour même | un seul dossard, tout de suite |

C'est ce qui rend le remplacement du classeur crédible : sans impression à la
demande, un ajout de dernière minute reste bloqué sur le Google Sheet.

Le mode unitaire est celui qui compte le jour J — il doit tenir en deux clics
depuis la fiche du participant qu'on vient de créer.

---

## 6. La base est multi-compétition

Décision du 28/08. Les éditions passées restent en base, avec une **page
d'archives** dans la partie administration : consulter les résultats d'une
compétition passée, comparer, ressortir un classement.

Conséquences :

- toute donnée porte une **référence de compétition** : participants, blocs,
  réussites, paramètres, classements ;
- les paramètres (validation par couleur, catégories, circuits) sont **propres à
  chaque édition** — c'est cohérent avec « la validation par couleur est une
  option par compétition » ;
- un dossard n'est unique **qu'au sein d'une compétition**, pas globalement. Le
  modèle actuel (`bib UNIQUE` sur toute la table) ne le permet pas.

---

## 7. Authentification et gestion des utilisateurs

La partie paramétrage est protégée par **login et mot de passe, avec gestion des
utilisateurs** — « comme c'est fait sur Sowel ou guestFlow ».

Le précédent le plus proche est **guestFlow**, et il a exactement la bonne forme :

| Élément | Chez guestFlow | Ici |
| --- | --- | --- |
| Session | `requireAuth` sur session serveur | même modèle |
| Rôles | table de jointure `user_roles`, plusieurs rôles par personne | même modèle |
| Contrôle d'accès | `enforceRoleAccess` : liste blanche de chemins par rôle, **fail-closed** | même modèle |
| Clé d'API | `requirePublicApiKey`, **middleware distinct** de la session | même modèle — c'est exactement la séparation dont on a besoin entre l'app juge et la console |

Cette séparation en deux mécanismes est déjà celle prévue dans la spec 001 :
**clé d'API** pour `/api/v2/contest/*` (l'app juge), **session + rôles** pour
`/admin/*`.

Rôles pressentis, à confirmer : `admin` (tout), `organisateur` (participants,
saisie, impression), `lecture` (consultation des archives).

---

## 8. L'application juge peut évoluer librement

Adrien a confirmé le 28/08 que **republier sur le Play Store ne pose pas de
problème**, et qu'il souhaite faire évoluer l'application.

Ça lève une contrainte que j'avais posée à tort : le contrat d'API n'a pas besoin
d'être figé pour l'éternité. On peut faire évoluer l'app et le backend ensemble.

Reste une prudence de bon sens : **ne pas casser le contrat entre deux versions
le jour d'une compétition**, parce que les téléphones des juges ne sont pas mis à
jour dans la matinée. Une version majeure d'API se prépare entre deux éditions.
