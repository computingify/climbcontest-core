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

⚠️ **Une incohérence connue, latente aujourd'hui** : `catalogue_version` porte
sur la compétition **active**, alors que le plan est **global**. Dessiner hors
saison, sans compétition active, n'incrémente donc rien — il n'y a personne à
prévenir, et l'enregistrement réussit quand même. Le jour où deux compétitions
coexisteront, ce sera un vrai défaut de fraîcheur.
