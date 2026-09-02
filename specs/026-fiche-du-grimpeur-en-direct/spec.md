# Spec 026 — La fiche du grimpeur, en direct

> **Statut : approuvée (porte 2) le 02/09/2026, puis codée.**
> Demande d'Adrien du 02/09 : « il faut qu'on travaille sur une fiche
> d'avancement par grimpeur, mon but c'est que dans la page résultat on puisse
> cliquer sur un grimpeur et voir un peu comme ce qu'on a sur son dossard avec
> le circuit et les voies validées d'une couleur succès et les restantes. »
> Puis : « au clic sur un bloc dans la liste on ouvre le plan de la salle et on
> met en évidence la zone où se trouve le bloc avec une belle animation comme
> un rebond. Fais attention de bien gérer les retours arrière dans ces écrans
> et fais en sorte que ce soit beau et ergonomique sur téléphone. »
>
> **Spécifiée sur maquette avant d'être écrite.** Dix-huit versions d'un
> prototype cliquable ont précédé ce document ; les décisions ci-dessous sont
> celles qui ont survécu à l'essai, pas celles qu'on a devinées. Trois défauts
> ont été trouvés là plutôt qu'en production — ils sont en § 6.

## 1. Ce qui manque

La spec 023 imprime, avant la compétition, une fiche qui dit à un grimpeur
**quels blocs comptent pour lui** et **où ils sont dans la salle**. C'est le
seul papier qu'il a en main de la journée, et il est juste — mais il sort de
l'imprimante le matin : il ne peut rien dire de ce qu'il a fait.

La page de résultats, elle, sait ce qu'il a fait, et n'en montre qu'un nombre.
Un parent lit « 12 blocs » sans savoir **lesquels**, ni **ce qu'il reste**, ni
**où aller**. Les deux moitiés existent, séparément.

## 2. Ce qu'on fait

### F1 — Une ligne du classement s'ouvre

Toucher une ligne — ou une carte du podium — ouvre une **feuille** par-dessus
le classement. Elle porte l'identité du grimpeur dans la mise en page de son
dossard (gros numéro, nom, club, catégorie · circuit), son rang et son score
dans le classement d'où l'on vient, les autres classements où il figure, puis
**tous les blocs de son circuit**.

L'étoile des favoris garde son propre clic. Une ligne de **club** ne s'ouvre
pas : elle porte `participant_id = 0` et n'a personne derrière.

**Jamais en mode mur.** Personne ne touche l'écran projeté, et une feuille
ouverte figerait la rotation des catégories devant la salle.

### F2 — Les blocs, dans le vocabulaire du papier

Groupés par couleur de difficulté, dans l'ordre du classeur (la difficulté
d'abord, le numéro ensuite). Chaque case porte **la zone en petit au-dessus et
le numéro en gros dessous** — « Z » puis « J6 », et non le tag brut « ZJ6 ».

Ce n'est pas de la coquetterie : les blocs sont numérotés par zone et par
couleur, donc `MB8` et `DB8` affichent tous deux « B8 ». **Sans la zone, la
fiche serait fausse.** Le jour où quelqu'un voudra gagner de la place en la
retirant, c'est cette phrase qui doit l'arrêter.

Trois états :

| État | Signe | Ce qu'il dit |
| --- | --- | --- |
| **grimpé** | aplat vert | il l'a fait |
| **crédité** | hachures 45° sur la même teinte | la cascade de couleurs le lui accorde — **pas grimpé mais compté** |
| **reste** | contour pointillé, en creux | il lui reste à faire |

Le crédité **n'ouvre pas le mur** : on n'envoie personne grimper ce qu'il n'a
pas besoin de grimper. Et la légende ne le nomme **que s'il existe** —
`validation_couleur` vaut 0 par défaut et la cascade n'a servi ni en novembre
2025 ni en mars 2026 ; une légende qui nomme un état impossible fait chercher
ce qui n'existe pas.

### F3 — Le mur, et la zone qui rebondit

Toucher un bloc ouvre **le mur** — le plan de la spec 028 — avec la zone de ce
bloc mise en évidence : un anneau, une lueur, et **un rebond**. Le bouton
« Le mur » de la fiche l'ouvre aussi, sans zone visée : on cherche parfois « où
me reste-t-il du travail », pas « où est ce bloc-là ».

Chaque zone porte l'état du grimpeur, dans le vocabulaire des cases :

- **elle s'efface** s'il n'a rien à y faire ;
- **elle reste pleine** s'il lui reste des blocs ;
- **elle prend le vert de la réussite**, en contour, quand il l'a terminée.

Toucher une zone l'ouvre — **sans rebond** : le rebond dit « tu arrives ici »,
pas « tu regardes ici ». Le panneau du bas montre alors **tous les blocs du
circuit de cette zone**, avec le code exact de la fiche.

Le remplissage d'un mur dit son **profil** (l'échelle froid → chaud de la spec
028), une trame le redouble à faible contraste, et l'état est une **emphase**.
Jamais un aplat : il mangerait la trame, et précisément sur les zones qui
comptent.

### F4 — Le retour arrière

Trois niveaux — classement, fiche, mur — et **une seule règle** :

> **L'historique est la seule source de vérité.** Ouvrir écrit le dièse, fermer
> appelle `history.back()`, et c'est `hashchange` — lui seul — qui repeint.

L'adresse porte tout : `#g=42` la fiche, `#g=42&z=M` le mur sur une zone,
`#g=42&z=` le mur sans zone. **Le dièse et pas un paramètre** : il ne part
jamais au serveur, alors que `?g=42` créerait une entrée de cache Caddy par
grimpeur et par zone pour un HTML rigoureusement identique — et laisserait
`?mur`, `?sombre` et le rejeu d'archive intacts.

| Situation | Ce qui doit se passer |
| --- | --- |
| Retour depuis le mur | la fiche, **à sa position de défilement** |
| Retour depuis la fiche | le classement, sur la même catégorie |
| Retour depuis le classement | on quitte la page, normalement |
| Changer de zone | un seul retour ramène à la fiche (`replaceState`) |
| Rouvrir la même fiche | pas de doublon dans l'historique |
| Arriver sur `/#g=42` | le classement se dessine, **puis** la fiche par-dessus |
| Dossard inconnu | la fiche le dit et **l'adresse se nettoie** |

### F5 — Ergonomie du téléphone

Feuille montant du bas, poignée, 46 px de haut par case (c'est une commande
qu'on touche avec un pouce), `env(safe-area-inset-bottom)` pour que la dernière
case ne passe pas sous la barre d'accueil, et le classement figé derrière —
sinon on fait défiler le mauvais plan sous le doigt.

### F6 — Le plan peut changer de forme sans casser la page

`fiches.PLAN` a déjà changé de forme une fois (spec 028). C'est un relevé de
salle : il rechangera.

- Le serveur **estampille** ce qu'il envoie (`suivi.FORMAT_PLAN`).
- La page **vérifie l'estampille** avant de dessiner. Format inconnu → elle
  n'affiche pas le mur et laisse les blocs non cliquables. Dessiner un plan
  qu'on ne comprend qu'à moitié enverrait chercher un bloc au mauvais endroit :
  c'est pire que de ne rien montrer.
- La page ne connaît du mur **que `data-zone`**. Ni géométrie, ni nombre de
  zones, ni disposition. Une lettre absente du plan rend simplement son bloc
  non cliquable.
- Un mur abîmé est **ignoré un par un**, pas fatal : un relevé auquel il manque
  une lettre montre les seize autres zones.

## 3. Périmètre

**Dans** : la route publique, la feuille, le mur, la pile d'historique, les
tests.

**Hors** :

- **Les réussites hors circuit.** Elles existent (spec 019 : le juge est
  averti, il peut forcer) et ne comptent pas. Elles ont eu leur place en bas de
  la fiche, numéro barré ; Adrien les a fait retirer le 02/09. L'anomalie
  redevient donc invisible pour le grimpeur — **à traiter dans la console**, où
  un organisateur peut agir, plutôt que sur un écran public où un parent ne
  pourrait que s'inquiéter. Le moteur continue de les servir.
- **Le mur seul**, sans fiche derrière. La pile devient un graphe dès qu'on
  peut y arriver par deux chemins, et le retour arrière avec.
- **La fiche en rejeu d'archive.** La route publique ne parle que de la
  compétition active. L'archive contient tout ce qu'il faudrait ; c'est une
  itération, pas un oubli.
- **La couleur des prises** (`couleur_prises`, spec 019). À vérifier d'abord
  sur le classeur de novembre : le champ n'est peut-être pas renseigné.

## 4. Critères d'acceptation

| # | Situation | Attendu |
| --- | --- | --- |
| A1 | Clic sur une ligne | la fiche s'ouvre, l'adresse devient `#g=<id>` |
| A2 | Fiche ouverte | tous les blocs du circuit, groupés par couleur, dans l'ordre du classeur |
| A3 | Un bloc grimpé | aplat vert ; un bloc crédité, hachuré ; le reste en creux |
| A4 | Clic sur un bloc | le mur s'ouvre sur sa zone, qui rebondit |
| A5 | Clic sur une autre zone | elle s'ouvre **sans** rebond |
| A6 | Zone terminée | contour vert ; zone sans blocs pour lui, effacée |
| A7 | Un retour depuis le mur | la fiche, à sa position de défilement |
| A8 | Deux retours | la fiche est fermée, l'adresse nettoyée |
| A9 | Changer trois fois de zone puis revenir | **un** retour suffit |
| A10 | Arriver sur `/#g=42` | classement **et** fiche |
| A11 | `/#g=999999` | la fiche ne s'ouvre pas, l'adresse se nettoie |
| A12 | Grimpeur d'une autre compétition | 404 |
| A13 | Format de plan inconnu | pas de mur, blocs non cliquables, aucune erreur |
| A14 | Zone absente du plan | le bloc reste inerte |
| A15 | Mode mur (`?mur`) | rien de tout ça n'existe |
| A16 | Sans catégorie, circuit inconnu ou vide | la fiche se rend et **dit** ce qui manque |
| A17 | Bloc réussi puis retiré du circuit | le compteur suit le tableau, pas les ensembles bruts |

## 5. Cas limites

| Cas | Décision |
| --- | --- |
| Ligne de club (`participant_id = 0`) | non cliquable |
| Grimpeur sans dossard | la fiche s'ouvre, le numéro affiche « — » |
| Bloc crédité | n'ouvre pas le mur |
| Deux blocs de même numéro dans deux zones | la zone les distingue (voir F2) |
| Le plan change de coordonnées | rien à faire : la page ne les lit pas |
| Le plan change de **forme** | estampille non reconnue → pas de mur |
| Fiche ouverte pendant un rafraîchissement | elle se met à jour, elle ne se ferme pas |

## 6. Sept défauts trouvés avant la production

Ils sont ici parce qu'ils se reproduiraient à l'identique dans n'importe quelle
page qui empile des vues, et qu'aucun ne ressemble à sa cause.

1. **La transition jouait le retour avant l'aller.** La pile recevait sa
   position *après* avoir été insérée dans la page, et la lecture de la
   position de défilement — glissée entre les deux — forçait un calcul de
   style. **Règle : aucune mesure entre l'insertion d'un élément animé et la
   pose de sa classe de position.**
2. **Toute la page est devenue traversante au clic.** Une couche de contours
   SVG avait pris le nom de classe `cadre`, déjà porté par le gabarit du
   téléphone, et lui appliquait `pointer-events: none`. La page s'affichait
   parfaitement et n'attrapait plus rien. **Règle : le style du contenu se
   préfixe** (`sf-` ici) quand il partage une feuille avec le style de
   l'application. Deux collisions ont été payées avant celle-ci — `.fin`, puis
   `peindre()` en JavaScript.
3. **Un drapeau contredisait l'historique.** « Je suis au mur » était gardé
   dans une variable posée *avant* l'écriture du dièse : tout rendu tombant
   entre les deux montrait le mur sans zone visée. L'état est maintenant lu
   dans l'adresse, et nulle part ailleurs.

Les quatre suivants viennent d'une relecture, et trois d'entre eux ne se
voyaient qu'à l'usage.

4. **Un lien partagé ouvrait une fiche qu'on ne pouvait plus fermer.**
   `quitter()` faisait `history.back()` sans condition ; sur `/#g=42` ouvert
   directement — l'usage même pour lequel le dièse existe — il n'y a rien à
   remonter. La croix, Échap et le voile devenaient inertes,
   `overflow: hidden` figeait le classement, et seul un rechargement s'en
   sortait. La page compte maintenant **les entrées qui sont les siennes**.
5. **La fiche « en direct » ne l'était pas.** `rafraichirFiche()` existait sans
   appelant : le bloc validé restait en pointillé pendant que la ligne du
   classement, juste derrière la feuille, affichait déjà un bloc de plus. La
   page se contredisait elle-même.
6. **Le plan pouvait sortir de son bloc `<script>`.** `json.dumps` n'échappe
   pas `<` : depuis la spec 029 le plan est de la donnée saisie, et un
   `</script>` dans un libellé de repère fermait le bloc — sur une page
   publique, projetée dans la salle. `|tojson` au lieu de `|safe`.
7. **Les classements masqués reparaissaient.** « Aussi classé » lisait tous les
   classements de la charge sans passer par le filtre de la spec 020 : un
   organisateur qui cachait un classement contesté le voyait ressortir dans
   chaque fiche.

Trois autres écarts, moins graves, ont été corrigés au passage : la carte du
podium n'était pas cliquable alors que F1 le promet ; la position de défilement
n'était jamais restaurée alors que F4 le promet ; et une zone **nommée dans
l'adresse** n'était pas vérifiée contre le plan — `#g=42&z=QQQ` affichait un
panneau « Zone QQQ » au-dessus d'un dessin qui ne la porte pas. Ce dernier
n'existait que depuis la spec 029 : tant que le plan était figé, une zone
nommée dans une adresse était forcément dessinable.
