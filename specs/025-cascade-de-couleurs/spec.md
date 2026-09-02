# Spec 025 — La cascade de couleurs se règle depuis la console

> **Statut : validée (porte 2) le 02/09/2026.** Adrien, après avoir piloté les
> trois maquettes : « c'est ok pour cette spec ». Ce document met par écrit ce
> qui a été validé.
>
> Demande d'origine : « il faut qu'on puisse choisir le mode de calcul pour les
> cascades de couleur dans le classement. Ce que je veux c'est pouvoir
> sélectionner quelle couleur difficulté toutes validée déclenche la validation
> de quelle autre couleur. »
>
> Puis, après lecture de l'étude : « Car je veux la même feature que dans le
> classeur » — donc la règle doit pouvoir s'activer **catégorie par catégorie**.
>
> Écran retenu : **les phrases**, avec quantificateur et contrôle.

## 1. Ce qui manque

### M1 — La règle ne sait dire qu'un nombre

Le moteur porte la validation par couleur depuis la spec 004. Elle tient dans
une option d'édition, `options.validation_couleur`, lue par
`classement_service.couleurs_requises()` et appliquée par
`classement._valider_par_couleur()` : **N couleurs entièrement réussies**, la
plus facile d'entre elles fixe un seuil, tout ce qui est plus facile est validé
d'office.

Ce nombre impose deux choses qu'on ne veut pas :

- la cascade descend **toujours jusqu'en bas** — on ne peut pas dire « toutes
  les Rouge valident les Jaune, et rien d'autre » ;
- les six couleurs sont traitées **de la même façon**.

### M2 — Aucun endroit pour la saisir

`validation_couleur` n'apparaît nulle part dans la console. La seule façon de la
changer aujourd'hui est d'écrire du JSON dans la base, en SSH. Une option de
classement qu'on ne peut pas régler le matin d'une compétition n'est pas une
option.

### M3 — Le classeur active la règle par catégorie, le serveur non

C'est la divergence relevée par la campagne du 02/09, et elle n'est pas dans le
calcul. L'interrupteur du classeur est **par catégorie** (`Listes!D29:D38`,
colonne « Valid dif précé ») ; celui du serveur est **par compétition**. Activée
pour une seule catégorie, le serveur ne sait pas la reproduire : il
l'appliquerait aux huit.

### M4 — Un bloc crédité ne se distingue pas d'un bloc grimpé

La page de résultats affiche « 36 blocs » à côté du score. Avec la cascade, ce
nombre ne dit plus ce qu'il dit — le dossard 59 de novembre 2025 en aurait
grimpé 7. Rien, nulle part, ne permet de faire la différence.

## 2. Pourquoi ce n'est pas un réglage d'affichage

Mesuré en rejouant les **1 003 réussites réelles de novembre 2025** avec
`climbcontest/classement.py` tel quel :

| Réglage | Ce que ça change |
| --- | --- |
| Règle du classeur (deux couleurs pleines) | **rien** — sur 98 grimpeurs, 23 ont une couleur pleine, **aucun n'en a deux** |
| Déclenchement sur **une** couleur pleine | **264 rangs sur 392** changent |

En U15 F, sept grimpeuses finissent **premières ex æquo** avec le circuit
entier, et la gagnante réelle (dossard 22, 3 997 points) tombe **douzième** sans
avoir rien perdu. Et **259 grimpeurs changent de score sans gagner un seul
bloc** : un bloc crédité compte dans le dénominateur `1000/n`, donc la cascade
fait baisser la valeur des blocs faciles **pour tout le monde**.

**Conséquence pour l'écran** : un aperçu est obligatoire, pas décoratif. On ne
peut pas enregistrer ce réglage sans voir ce qu'il donne.

## 3. Ce qu'on fait

### F1 — Une règle qui se lit en phrases

La règle est une **liste de phrases**, dans l'ordre où on les a écrites :

> Quand **au moins 2** parmi ⟨Vert⟩ ⟨Bleu⟩ ⟨Mauve⟩ ⟨Rouge⟩ ⟨Noir⟩ sont validées
> → valider ⟨Jaune⟩

Le quantificateur (**au moins N**, ou **toutes**) n'est pas un ornement : sans
lui, une phrase ne déclenche que sur **une** couleur pleine, et la règle du
classeur — qui en exige **deux** — demanderait vingt phrases au lieu de quatre.

Les phrases ne font qu'**ajouter** : le résultat est l'union de celles dont la
condition tient. Le déclenchement se lit sur les blocs **réellement grimpés**,
en une seule passe (D2).

### F2 — Trois préréglages, qui écrivent les mêmes phrases

| Préréglage | Ce qu'il écrit |
| --- | --- |
| **Aucune cascade** | la liste vide. C'est le **défaut**, et le réglage de novembre 2025 |
| **Comme le classeur** | quatre phrases — « au moins 2 parmi les couleurs plus dures » pour Jaune, Vert, Bleu, Mauve |
| **Sur mesure** | ne touche à rien : c'est l'état où l'on écrit ses propres phrases |

Le bouton actif se **déduit** de la liste, il ne se stocke pas : éditer une
phrase fait passer l'écran sur « sur mesure » tout seul.

⚠️ Le préréglage « comme le classeur » laisse **Rouge et Noir non validables**.
C'est volontaire et conforme : une seule couleur est plus dure que Rouge, donc
« deux plus dures » lui est impossible.

### F3 — Le contrôle des phrases

Deux phrases ne peuvent **pas** se contredire — le résultat étant une union, une
phrase ne fait qu'ajouter. Vérifié par énumération exhaustive sur les 64
combinaisons de couleurs pleines. Ce qu'elles peuvent, c'est **mentir à qui les
écrit** : on pose une condition qu'on croit plus stricte, et une autre phrase,
plus facile à satisfaire, a déjà tout donné.

| Défaut | Détection | Niveau |
| --- | --- | --- |
| **Règle morte** — sa condition ne peut pas tenir sans qu'une autre, plus facile, ait déjà validé tout ce qu'elle valide | `seuil(B) − card(parmi(B) hors parmi(A)) ≥ seuil(A)` **et** `cibles(B) ⊆ cibles(A)` | avertit |
| **Cascade qui remonte** — « toutes les Jaune → valider les Rouge » | une cible doit être plus facile que la plus facile de ses déclencheurs | **bloque** |
| **Deux phrases sur la même couleur** — elles s'additionnent, elles ne se remplacent pas | intersection des cibles, hors phrases mortes | informe |
| **Phrase incomplète** — déclencheur ou cible vide | ensemble vide | **bloque** |

Le test de règle morte est **exact** : 3 890 paires tirées au hasard ont été
confrontées à une vérification par force brute sur les 64 combinaisons, **0
désaccord**. Il ne signale pas à tort et ne laisse rien passer.

### F4 — Où la règle s'applique : un interrupteur par catégorie

Une **seule** règle pour l'édition, et **huit interrupteurs** — un par catégorie
— qui disent où elle s'applique. Tout est allumé au départ ; éteindre « U11 F »
reproduit l'interrupteur `Listes!D29:D38` du classeur. Quatre raccourcis :
toutes, aucune, les filles, les garçons.

Une catégorie apparue en cours de journée — une inscription à chaud — est
**allumée** par défaut, comme les groupes de la spec 020 : on range ce qu'on
éteint, jamais ce qu'on allume.

### F5 — L'aperçu, sous la règle

On choisit un circuit, on coche les couleurs qu'un grimpeur aurait entièrement
réussies, et l'écran affiche ce que la règle lui crédite : **« 36 / 36 blocs
comptés au classement — 3 réellement grimpés · 33 crédités »**, avec une jauge
qui montre chaque couleur en grimpé / crédité / reste à faire.

Les couleurs **absentes du circuit** y sont désactivées et le disent (D3) —
aucun des quatre circuits de novembre 2025 n'a de Noir.

### F6 — Un bloc crédité se voit

Partout où les blocs d'un grimpeur sont montrés : **aplat plein = grimpé,
hachures à 45° sur la même teinte = crédité**, et le compteur écrit
« **7 grimpés · 29 crédités** ». Sur le mur, la place manque : un astérisque sur
le compteur suffit.

Le même signe est repris par la spec 026 (la fiche du grimpeur à l'écran) : une
seule convention à retenir, jamais deux.

### F7 — L'avertissement quand le classeur ne suit plus

Dès que la liste s'écarte de ce que les formules du classeur savent faire, la
carte affiche : « **Le classeur ne saura pas suivre cette règle.** Ses formules
ne connaissent que “deux couleurs plus dures”. Tant que ce message est là, c'est
la page de résultats qui fait foi. »

Il se **calcule** en comparant la liste à la règle du classeur. Aucun drapeau
stocké : un état écrit en double finit toujours par mentir.

## 4. Ce qu'on ne fait pas

- **La variante par genre du classeur** (`Listes!A23`/`B23`) — trois premières
  couleurs d'un côté, deux de l'autre. Documentée par la relecture du 30/08,
  **jamais mesurée**, jamais utilisée. Décision D6 : on ne la code pas. Une
  seule règle par édition la rend d'ailleurs inexprimable, et c'est assumé.
- **Une règle par catégorie.** Décision D1 : huit règles différentes, ce sont
  huit classements qu'on ne saurait plus expliquer au micro.
- **Exclure les blocs crédités du dénominateur.** Décision D4 : ce serait
  s'écarter du classeur. On garde la règle et on écrit la contrepartie dans
  l'aide de l'écran.
- **Écrire quoi que ce soit dans le classeur.** La cascade est calculée côté
  serveur ; le classeur garde son propre interrupteur, qu'on n'active pas.

## 5. Les décisions, tranchées le 02/09/2026

| # | Question | Réponse |
| --- | --- | --- |
| D1 | Une règle par catégorie, ou une règle activable par catégorie ? | **Une seule règle**, activable ou non par catégorie. Pas d'exceptions |
| D2 | Une couleur créditée peut-elle en déclencher une autre ? | **Non.** Les déclencheurs se lisent sur les blocs réellement grimpés, une seule passe |
| D3 | Une couleur absente du circuit ? | **Jamais pleine**, et l'écran l'affiche |
| D4 | Les blocs crédités comptent-ils dans la valeur des blocs ? | **Oui**, comme le classeur |
| D5 | Un bloc crédité se distingue-t-il ? | **Oui** : hachures, et « N grimpés · N crédités » |
| D6 | La variante par genre ? | **On ne fait rien** |
| D7 | Divergence avec le classeur ? | **Le serveur fait foi**, avec avertissement à l'écran |

## 6. Critères d'acceptation

| # | Critère |
| --- | --- |
| A1 | Cascade éteinte (défaut), `tools/verify_ranking.py fixtures/contest-nov2025.json` sort **196 conformes, 0 écart** |
| A2 | Préréglage « comme le classeur », les quatre cas mesurés le 02/09 se rejouent : K1 Rouge+Noir → 36 blocs, K2 Noir seul → 1, K3 Noir+Bleu → 27, K4 Mauve+Rouge+Noir → 36 |
| A3 | Une édition portant l'ancien `options.validation_couleur = 2` produit **exactement** le même classement qu'avant la spec |
| A4 | Éteindre « U11 F » ne change que le classement de « U11 F » — et le scratch U11, qui contient ses grimpeuses, reste calculé grimpeur par grimpeur |
| A5 | Une phrase « toutes les Jaune → valider les Rouge » **empêche** l'enregistrement, avec un message qui nomme la phrase |
| A6 | La phrase « toutes les Rouge et Noir → valider Jaune », ajoutée au préréglage du classeur, est signalée **sans effet**, sans bloquer |
| A7 | L'aperçu affiche le nombre de blocs par couleur du circuit choisi, et désactive les couleurs absentes |
| A8 | Un grimpeur créditant des blocs affiche « N grimpés · N crédités » dans la console |
| A9 | La carte est réservée au rôle `ADMIN` |
| A10 | Aucune dépendance extérieure ajoutée à la console — non-régression des specs 005/016/021 |

## 7. Cas limites

| Cas | Comportement |
| --- | --- |
| Couleur absente du circuit (zéro bloc) | jamais pleine ; une phrase qui ne parle que d'elle ne se déclenche jamais |
| Bloc sans couleur (`couleur` NULL) | ignoré par la cascade, comme aujourd'hui — il compte au classement s'il est grimpé |
| Circuit sans aucun bloc coloré | la cascade ne fait rien, aucun message d'erreur |
| Catégorie sans genre (« U13 M » de la compétition de test) | l'interrupteur existe pour elle comme pour les autres ; les raccourcis « filles »/« garçons » ne la touchent pas |
| Catégorie apparue après le réglage | **allumée** par défaut |
| Liste de phrases vide | équivaut à « aucune cascade » ; le préréglage s'affiche en conséquence |
| Une phrase dont tous les déclencheurs sont absents du circuit | ne se déclenche jamais ; ce n'est pas une erreur, un circuit n'a pas à porter les six couleurs |
| `options.cascade` illisible | lu comme vide, avertissement au journal — même tolérance que `lire_options()` |
