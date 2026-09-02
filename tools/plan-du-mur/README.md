# La planche de dessin du plan du mur

Ouvre `index.html` dans un navigateur. Aucun serveur, aucune dépendance, aucun
appel réseau — sauf les polices Google, qui dégradent proprement si tu es hors
ligne.

## À quoi ça sert

Le plan de la salle imprimé sur le dossard de chaque grimpeur est une constante
Python, `PLAN`, dans `climbcontest/fiches.py`. Le relever à la main dans du code
est pénible et se relit mal. Cette planche le dessine, et **exporte exactement
la constante** que lit le serveur.

## Le geste

1. Ouvre `index.html`. Le dessin en cours est retenu dans le navigateur ; à la
   première ouverture, il part des lettres de zones du club.
2. **« Voir un exemple »** montre ce que la planche sait faire — proues
   triangulaires, îlot en biais, les six profils.
3. Pose des murs, tire leurs sommets, donne à chacun sa lettre et son profil.
4. **« Copier »**, et colle le bloc dans le chat.

Pour **reprendre un plan existant** : colle-le dans le cadre « À me recoller »
et clique **« Recoller un plan »**. L'aller-retour est fidèle au caractère près.

## Ce que la planche montre, et pourquoi

Deux aperçus, parce qu'il y a deux supports et qu'ils ne pardonnent pas les
mêmes choses :

- **Papier** — à la taille réelle : la colonne du dossard fait **37 mm**. Si une
  lettre ne se lit pas là, elle ne se lira pas à l'impression.
- **Téléphone** — sur le fond sombre de l'application juge.

Le profil du mur se lit à la **trame**, jamais à la couleur : la couleur est
déjà prise par les six difficultés du classeur, et un second code couleur les
ferait lire de travers. La trame se densifie à mesure que le mur déverse, et
elle survit à l'encre noire.

⚠️ Deux règles s'inversent d'un support à l'autre, et c'est voulu : sur papier,
plus un mur déverse, plus il **fonce** ; sur écran sombre, plus il **éclaircit**.
Dans les deux cas la règle perçue est identique — plus ça déverse, plus ça
tranche sur le fond.

⚠️ L'**état** d'une zone vit dans l'aplat, le **profil** dans la trame posée
par-dessus. Si la trame prenait le remplissage, une zone du grimpeur perdrait
son profil — et c'est justement celle qu'il regarde.

## L'unique couleur

Les zones où **ce** grimpeur a des blocs. Noir plein sur le papier, ocre du club
à l'écran. C'est ce qui transforme une carte en itinéraire, et c'est la seule
chose que la couleur dit ici.
