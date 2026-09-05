# Spec 045 — Le mode sans classeur

> **Statut : soumise à la porte 2.** Écrite avant le code.
>
> Demande d'Adrien du 05/09/2026 : « Si les blocs sont rentrés via la console,
> le fichier Google n'a plus lieu d'être, dans ce cas on va le supprimer. Donc
> mon point de vue c'est qu'il faut rendre ce dev optionnel activable dans les
> settings de la console, et lorsqu'il est activé on supprime totalement le
> Google Sheet — que ce soit pour source pour les participants comme le retour
> et l'écriture pour le calcul des podiums. Donc si on active le setting de
> voies sur la console, on retire totalement Google Sheet : je ne veux plus du
> tout le voir dans les paramètres et je ne veux plus qu'on lui remonte les
> infos. »

---

## 1. Le point d'arrivée d'une trajectoire écrite il y a huit jours

`docs/contraintes-metier.md` §2 annonçait trois étapes :

1. **Aujourd'hui** — le classeur est la source, le backend le lit et y écrit.
2. **Transition** — la base devient la source, le backend continue d'écrire un
   miroir dans le classeur. *Redondance gratuite des données du jour J.*
3. **Cible** — la page de paramétrage est la source, **le classeur n'est plus
   utilisé**. « C'est à ce moment qu'il faudra revoir la question de la
   sauvegarde (la redondance gratuite disparaît). »

Ce lot fait l'étape 3. Elle n'était pas datée ; elle l'est par la spec 044, qui
retire au classeur la dernière chose qu'il apportait et que rien d'autre ne
savait faire.

### Ce que le classeur fait encore, exactement

Le vérifier a changé la forme de ce lot, alors on l'écrit :

| Ce que le classeur faisait (contraintes-metier §2) | Aujourd'hui |
| --- | --- |
| Liste des participants (`Listes`) | **encore lui** — c'est le seul chargement en volume qui existe |
| Plan des blocs, zones, couleurs (`Plan`) | **encore lui** — jusqu'à la spec 044 |
| Affectation bloc ↔ circuit (`Plan`) | **encore lui** — jusqu'à la spec 044 |
| Réception des réussites (`Import`) | **encore lui** — c'est le miroir |
| Génération du contenu des QR codes | ✅ repris — `qr.py`, spec 024 |
| Fiches et dossards à imprimer | ✅ repris — `fiches.py`, specs 023 et 041 |
| **Calcul du classement** | ✅ repris — spec 004, **196 scores et rangs sur 196** |
| **Podium, statistiques** | ✅ repris — spec 006 |
| Option de validation par couleur | ✅ repris — `cascade.py`, spec 025 |
| Saisie manuelle | ✅ repris — spec 013 |
| Archives des éditions passées | ✅ repris — spec 018, en base |

⚠️ **Le classement et le podium ne passent plus par le classeur depuis la spec
004.** La demande dit « l'écriture pour le calcul des podiums » : cette écriture
n'existe plus. Ce qui part encore vers l'onglet `Import`, ce sont les réussites,
et elles n'y servent qu'à **redonder** ce que la base contient déjà.

### Le seul vrai trou

**Il n'existe aucun moyen de charger les participants en volume sans le
classeur.** Vérifié : pas d'import CSV, pas de collage, pas de dépôt de fichier.
Il ne reste que la saisie au guichet, une personne à la fois. Pour cent
grimpeurs, ce n'est pas une option.

Ce qui le comble existe et est écrit : la **spec 008 (import HelloAsso)**,
poussée sur `origin/feat/008-helloasso-import` — 40 fichiers, ~11 000 lignes,
avec le calcul de catégorie depuis l'année de naissance et le rapprochement des
doublons. Elle n'est ni relue ni mergée.

> **Arbitrage du 05/09** : « HelloAsso seul, la 008 devient un prérequis. »

---

## 2. Ce qu'on fait

### F1 — Un réglage, global, dans les paramètres

> **Arbitrage du 05/09** : global, pour le club — pas par compétition.

Une ligne dans la table `reglage`, à côté du plan de la salle :

| `cle` | `valeur` |
| --- | --- |
| `mode_sans_classeur` | `"1"` ou absent |

**Global et non par édition**, pour la raison qu'Adrien donne lui-même : il va
**supprimer le fichier**. Un réglage par compétition laisserait la vue
« Classeur » dans les paramètres pour les éditions qui ne l'ont pas éteint — et
c'est précisément ce qu'il ne veut plus voir. Le club a un mur, il aura une
façon de travailler.

Réservé à l'**administrateur**. Ce n'est pas un réglage de journée.

### F2 — On ne débranche pas à l'aveugle

Avant d'autoriser la bascule, la console vérifie que **ce que le classeur
détient est bien en base**. C'est le seul moment où la vérification est encore
possible : après, le fichier sera supprimé.

**Deux refus durs** — la bascule est impossible tant qu'ils tiennent :

| # | Contrôle | Pourquoi c'est un refus |
| --- | --- | --- |
| B1 | Une **source d'inscrits** est reliée sur la compétition active (HelloAsso, spec 008) | Sans elle, plus personne ne peut charger cent participants. C'est le prérequis, et il se vérifie plutôt qu'il ne se rappelle |
| B2 | La compétition active porte **au moins un bloc et un circuit** | Zéro bloc = le classeur n'a jamais été importé. Éteindre laisserait une compétition sans mur, et sans moyen d'en récupérer un |

**Quatre avertissements** — ils s'affichent, on peut passer outre, mais en les
ayant lus :

| # | Contrôle | Ce qu'on dit |
| --- | --- | --- |
| A1 | Des réussites attendent d'être écrites au classeur | Elles n'y arriveront jamais. Elles ne sont perdues pour personne — elles sont en base |
| A2 | Des blocs ne sont rattachés à **aucun** circuit | `circuits.anomalies()` le sait déjà. Un bloc orphelin ne compte pour personne, et après la bascule c'est la console qui devra le corriger |
| A3 | Des participants sont sans catégorie | Même raisonnement |
| A4 | La sauvegarde | « Le classeur ne redondera plus rien : la copie de la base toutes les dix minutes devient le seul filet. » Ce n'est pas une case à cocher, c'est une phrase à lire |

⚠️ **Aucun contrôle ne repose sur `_dernier_rapport`.** C'est une variable
globale de module, propre à un worker gunicorn et perdue au redémarrage : elle
ne dit pas quand le dernier import a eu lieu, elle dit quand *ce worker-là* en a
vu un. On compte ce qui est **en base**, et rien d'autre.

### F3 — Ce qui s'éteint

Une fois le mode allumé, **le classeur disparaît de la console** :

| Ce qui disparaît | Où |
| --- | --- |
| L'entrée **« Classeur »** du tiroir et sa vue entière | `admin.html` |
| **Relier un classeur**, tester l'accès, les trois modes de bascule | vue Classeur |
| **Importer le classeur** et son rapport | vue Classeur |
| Le **consentement Google** et le dépôt du **jeton** | vue Classeur |
| L'avertissement « **le classeur ne saura pas** » de la cascade | vue Réglages |
| Le lien « Ouvrir le classeur ↗ » | partout |

Et **il cesse d'être appelé** :

| Ce qui s'arrête | Comment |
| --- | --- |
| Le **fil de synchronisation** (40 s, lot de 50) | il ne démarre pas |
| `POST /admin/import/sheet` | 409, en nommant le mode |
| Les six routes `/admin/classeur*` | 409, en nommant le mode |
| Les compteurs `reussites_en_attente` / `inenvoyables` de `/health` | à `null`, avec `mode_sans_classeur: true` à côté |

⚠️ **`/health` ne doit pas passer en `degraded` pour autant.** Le champ à `null`
signifie aujourd'hui « base injoignable » et déclenche un retour arrière
automatique de l'agent de déploiement. Il faut donc que le mode **se nomme** dans
la réponse, et que le statut reste `ok`. C'est le piège le plus coûteux de ce
lot : livré sans ça, le premier déploiement après la bascule se retire tout seul.

### F4 — Ce qui reste allumé

- **Les archives** des éditions passées. Elles sont en base (spec 018) et se
  relisent dans la vraie page de résultats. Le `spreadsheet_id` qu'elles portent
  reste, comme trace historique de l'endroit d'où venaient les données.
- **Le code du classeur.** `sheets/` n'est pas supprimé : le mode est un
  interrupteur, pas une amputation. Retirer six modules et leurs tests pour un
  réglage réversible serait un travail qu'il faudrait refaire à l'envers le jour
  où une édition doit repartir d'une feuille.
- **`Participant.source` et `Bloc.source`.** Une donnée venue du classeur reste
  marquée comme telle : c'est ce qui permet de dire, dans deux ans, d'où venait
  une ligne.

### F5 — Ce qui devient la source

| | Avant | Après |
| --- | --- | --- |
| Les participants | onglet `Listes` | **HelloAsso** (spec 008) + le guichet (spec 013) |
| Les blocs et circuits | onglet `Plan` | **l'écran d'ouverture** (spec 044) |
| Les réussites | base, miroir vers `Import` | **base**, point |
| Le classement | déjà la base | la base |
| La sauvegarde | la base **et** le classeur | **la base seule**, copiée toutes les dix minutes |

### F6 — Le retour arrière, et ce qu'il ne fait pas

Le réglage se rallume : la vue Classeur revient, l'import et le miroir aussi.

⚠️ **Mais ça ne fait pas revenir le fichier supprimé.** Il faudra en relier un
neuf, et le repeupler. La confirmation de bascule le dit en toutes lettres, avec
le mot « supprimé » : c'est une décision qui se prend une fois.

### F6 bis — Le geste de confirmation, uniformisé

> **Arbitrage du 05/09** : « tout uniformiser avec le reste, c'est-à-dire le
> bouton qu'il faut rester appuyé sur ordinateur et un bouton slide comme sur
> Sowel pour l'ouverture de portail sur mobile. »

Une première rédaction demandait d'**écrire `SUPPRIMER`**. ⚠️ **C'était un pas
en arrière**, et le dépôt le disait déjà : le commentaire de
`admin.html` (spec 032, 02/09) explique que le bouton à maintenir **remplace**
un mot qu'il fallait frapper — « sept caractères, sur un ordinateur posé sur un
coin de table dans une salle d'escalade ». Ce que le mot apportait, c'est
l'**arrêt** ; c'est ça qu'on garde, en jetant la frappe.

Le geste a donc **deux surfaces, une décision** :

| Surface | Geste | D'où il vient |
| --- | --- | --- |
| Souris / trackpad | **maintenir 2 s** — anneau de progression, jauge, décompte | `admin.html`, `button.detruire` (spec 032) |
| Doigt | **glisser** le curseur jusqu'au bout | Sowel, `SlideToConfirm.tsx` (spec 146) |

⚠️ **C'est le POINTEUR qui décide, pas la largeur de l'écran.**
`(hover: hover) and (pointer: fine)` → le maintien ; sinon le glissement. Un
portable tactile et un téléphone en paysage se rangeraient du mauvais côté d'une
simple largeur.

⚠️ **Relâcher trop tôt annule, dans les deux cas.** C'est ce que les deux gestes
ont en commun, et c'est tout leur objet : une pression accidentelle ne
déclenche rien. Le curseur revient à sa place, la jauge se vide.

⚠️ **Les cotes du glissement viennent de Sowel et ne se réinventent pas** :
piste plafonnée à **260 px et centrée**, bouton de 50, marge de 4, donc une
course de **202 px**. La raison est écrite là-bas : pleine largeur sur un
téléphone de 393 px, le geste part du coin inférieur gauche — le point le plus
loin du pouce de la main qui tient l'appareil, sur un contrôle fait pour être
utilisé d'une seule main devant un portail. Ici, c'est devant un mur.

Le même geste sert à **renuméroter** dans la spec 044 : c'est le deuxième
endroit où un clic accidentel coûterait cher.

### F7 — Les prérequis

| Prérequis | État |
| --- | --- |
| **Spec 008** — l'import HelloAsso, qui remplace l'onglet `Listes` | codée, poussée, **non relue et non mergée** |
| **Spec 044** — l'écran d'ouverture, qui remplace l'onglet `Plan` | à la porte 2 |

⚠️ **B1 vérifie le premier au moment de la bascule**, pas au moment du merge :
ce lot peut donc être relu et mergé avant la 008, il refusera simplement de
s'allumer.

---

## 3. Critères d'acceptation

| # | Ce qu'on vérifie |
| --- | --- |
| A1 | Par défaut le mode est **éteint**, et rien ne change nulle part |
| A2 | La bascule est refusée si aucune source d'inscrits n'est reliée (B1) |
| A3 | La bascule est refusée si la compétition active n'a ni bloc ni circuit (B2) |
| A4 | Les quatre avertissements s'affichent quand ils s'appliquent, et n'empêchent rien |
| A5 | Mode allumé : `navClasseur` et `vueClasseur` sont absents pour **tous** les rôles, admin compris |
| A6 | Mode allumé : les sept routes classeur et l'import répondent **409** en nommant le mode |
| A7 | Mode allumé : le fil de synchronisation ne démarre pas ; aucun appel Google n'est émis |
| A8 | Mode allumé : `/health` répond **`ok`**, `mode_sans_classeur: true`, compteurs à `null` |
| A9 | Le mode se rallume, et tout revient — routes, vue, fil |
| A10 | La confirmation de bascule dit ce que le retour arrière ne fait pas |
| A10 bis | Sur pointeur fin, le **maintien** est présenté ; sur pointeur grossier, le **glissement** |
| A10 ter | Relâcher avant la fin **n'actionne rien**, dans les deux gestes |
| A11 | Les archives restent lisibles dans les deux modes |
| A12 | Le réglage est refusé (403) à un organisateur et à un ouvreur |

---

## 4. Cas limites

| Situation | Ce qui doit se passer |
| --- | --- |
| La bascule est faite pendant une compétition en cours | Autorisé mais **averti** : les réussites déjà en attente n'iront jamais au classeur |
| Le fil de synchronisation tourne au moment de la bascule | Il finit son lot, puis s'arrête au tour suivant. On ne tue pas un lot en vol |
| Quatre workers gunicorn | Le réglage est lu **en base à chaque décision**, jamais mis en cache dans le processus : sinon trois workers sur quatre continueraient d'appeler Google |
| Le mode est allumé et la base n'a aucune compétition active | L'écran de contrôle le dit, et B2 refuse |
| Un jeton Google est encore déposé | Il reste sur le disque, inutilisé. On ne le supprime pas : ce serait une destruction déclenchée par un réglage d'affichage |

---

## 5. Ce qui n'est PAS dans ce lot

- **Supprimer le code `sheets/`.** Voir F4.
- **Supprimer le classeur Google lui-même.** C'est un geste d'Adrien, dans son
  Drive. La console ne supprime pas un document qu'elle ne possède pas.
- **Révoquer le jeton Google.** Souhaitable, mais c'est une action de sécurité
  qui mérite sa propre décision, pas un effet de bord.
- **Un import CSV de secours.** Écarté le 05/09 au profit de HelloAsso seul.
  ⚠️ C'est le point à rouvrir si la 008 traîne : sans elle, ce lot ne s'allume
  pas.

---

## 6. Ce qui reste à confirmer (porte 2)

1. **L'ordre de merge.** 044 seule ne donne qu'un écran de consultation ; 045
   seule ne s'allume pas sans la 008. L'ordre naturel est **008 → 044 → 045**,
   et il suppose de faire relire la 008.
2. **B1 comme refus dur.** Si tu préfères pouvoir allumer le mode et charger les
   participants à la main pour une petite édition, B1 devient un avertissement.
   Je le propose en refus parce qu'un mode qu'on allume sans avoir de quoi
   inscrire personne est un piège qui ne se voit que le jour J.
