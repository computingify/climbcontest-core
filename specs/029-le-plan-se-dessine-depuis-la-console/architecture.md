# 029 — Architecture

## Où vit le plan

| | |
| --- | --- |
| **Table `reglage`** | clé-valeur globale ; une ligne, `plan_du_mur`, le document JSON |
| **`fiches.PLAN`** | le plan **d'usine** : le défaut, et le repli |
| **`fiches.plan_courant()`** | la base d'abord, la constante ensuite |

⚠️ **En base et pas dans un fichier.** `climbcontest-sauvegarde` recopie la base
SQLite et **rien d'autre** — c'est déjà l'argument que porte le modèle
`Archive`. Un JSON posé dans le dossier de données serait le seul fichier de la
VM sans sauvegarde, et une restauration ramènerait silencieusement l'ancien plan.

⚠️ **Global et pas par compétition.** Le club a un mur. Le ranger dans
`competition.options` obligerait à le redessiner à chaque édition, ou à inventer
une reprise automatique.

## Le chemin de la donnée

```
la planche (/admin/plan)  --POST-->  valider()  -->  reglage.plan_du_mur
                                                          |
                     incrementer_catalogue(competition active)
                                                          |
       plan_courant()  <----------------------------------+
         |         |
    le dossard   /api/v2/catalog  --304 si rien n'a bouge-->  les clients
```

## La validation : le point critique

Le plan a **changé de nature**. Tant qu'il était une constante, c'était du
**code** — relu en revue, impossible à casser depuis un navigateur. C'est
maintenant de la **donnée saisie**, rendue en SVG sur un papier distribué à cent
vingt personnes, **et servie dans le catalogue**.

Deux règles gouvernent `plan_du_mur.py` :

1. **On ne fait confiance à rien.** Les **quatre** chemins de coordonnées —
   points de mur, étiquette, point de repère, contour — passent par
   `_dans_la_vue()`. Trois d'entre eux ne l'ont pas toujours fait, et le contour
   hors vue était atteignable par le recollage que cette spec documente comme le
   chemin de retour arrière.
2. **Une lecture ne peut pas échouer.** Une ligne abîmée retombe sur le plan
   d'usine et le journalise : imprimer les dossards la veille au soir ne doit
   pas dépendre de l'intégrité d'une ligne de base.

### ⚠️ Le non-fini, et pourquoi il ne touche pas que le plan

`json.loads` accepte `NaN` et `Infinity` par défaut ; `json.dumps` les réécrit
tels quels. Un seul `NaN` dans le plan rendait le **catalogue entier** illisible
pour un analyseur strict — kotlinx.serialization, Moshi, `JSON.parse`. Le
téléphone du juge ne perdait pas le plan : il perdait la synchronisation des
participants, des blocs et des circuits, **en silence**.

D'où `math.isfinite` dans `_nombre()`, et un test qui relit le catalogue avec
`parse_constant` pour le prouver.

## La page de console

`GET /admin/plan` sert la planche. Trois différences avec l'outil autonome
qu'elle remplace :

1. elle charge le **plan courant** ;
2. elle porte « Enregistrer dans ClimbContest » et « Revenir au plan d'usine » ;
3. **aucune ressource extérieure** — pas de police Google : la règle du dépôt
   est qu'une page servie n'appelle rien dehors, on imprime parfois sans réseau.

⚠️ **`POST` et `DELETE` renvoient le plan tel qu'il a été rangé**, et la page le
reprend. Sans ça, le serveur réparait en silence — zone en capitales et tronquée
à trois, profil inconnu replié — pendant que la page affirmait « le plan
enregistré est celui affiché ».

⚠️ **La table des profils vient du serveur**, en entier. La page n'y ajoute que
le nom lisible, l'indice et les couleurs d'écran. Elle en portait une copie :
changer le pas d'une trame côté Python laissait l'aperçu « papier à 37 mm »
mentir sur ce qui serait imprimé.

## Le catalogue

Le plan y voyage (`"plan"`), et l'enregistrer incrémente `catalogue_version`.
Ce n'est pas une économie de requêtes : c'est ce qui rend le plan **versionné**.
Servi par une route à part, un client garderait un mur périmé sans aucun moyen
de le savoir.

### La portée du numéro, et pourquoi il en fallait un par édition

Cette section portait une **incohérence connue, laissée latente** : le plan est
global (F1) alors que `catalogue_version` appartient à une compétition. Dessiner
hors saison n'incrémentait donc rien, et l'enregistrement réussissait quand
même. Elle a été fermée le 02/09/2026 — `plan_du_mur._signaler_le_changement()`
appelle désormais `contest.incrementer_tous_les_catalogues()`.

Le trou n'était pas seulement « hors saison ». Il se refermait mal parce qu'il
avait **deux bouches** :

- **aucune édition active** — on redessine le mur entre deux compétitions, ce
  qui est le moment le plus naturel pour le faire. Personne à prévenir ; le
  compteur de l'édition suivante restait celui qu'un téléphone connaissait
  déjà, et à la réouverture ce téléphone recevait un **304** en gardant
  l'ancien mur ;
- **une édition non active** — elle porte le nouveau plan sans que son numéro
  ait bougé, et le trou se rouvre dès qu'on bascule dessus.

⚠️ **La correction ne pouvait pas être un compteur global unique**, et c'est le
piège de ce coin du code. Deux propriétés se contredisent :

1. `/api/v2/catalog` décide son 304 par **égalité stricte** (correctif du
   30/08) : un numéro identifie un couple (édition, état de son catalogue), et
   un client qui en annonce un venu d'ailleurs n'est pas à jour ;
2. le plan est global : le changer doit périmer le catalogue de **toutes** les
   éditions.

Un numéro partagé satisferait (2) et casserait (1) — un téléphone qui vient de
changer d'édition recevrait « rien de neuf » alors qu'il lui faut une autre
liste de participants. On tire donc **un numéro neuf par édition** sur
l'horloge commune (`prochaine_version_catalogue()`), avec un `flush` entre
chaque : sans lui, le maximum relu est celui d'avant et deux éditions
repartiraient avec le même numéro.

L'étiquette reste **un entier**, et le contrat de `/api/v2/catalog` ne bouge
pas : les téléphones déjà déployés n'ont rien à apprendre. C'était une
contrainte, pas une facilité — l'application juge n'est pas mise à jour le
matin d'une compétition.

Vérifié par `tests/test_fraicheur_du_plan.py`, dont quatre tests tombent si l'on
revient au comportement précédent, et cinq gardent ce qu'il ne fallait pas
casser.
