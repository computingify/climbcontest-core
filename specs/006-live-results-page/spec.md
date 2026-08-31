# 006 — La page de résultats

> **⚠️ Reprise par la [spec 016](../016-page-resultats-projetee/) le 31/08/2026.**
> Ce qui tient toujours : les deux modes, le refus de vider la page sur une
> erreur réseau, l'absence totale de dépendance externe. Ce qui a changé : le
> fond (clair), la mise en page (podium + colonnes, toute la catégorie à
> l'écran), le mouvement (les lignes glissent), la rotation (proportionnelle),
> et l'adresse `/resultats`, **supprimée** au profit de la racine.

## Résumé

Le moteur de classement (spec 004) et ses routes publiques sont livrés. Il ne
manque que la page — celle qu'on projette dans la salle, et que les spectateurs
ouvrent sur leur téléphone.

C'est la demande d'Adrien formulée dès le premier jour : *« une page internet
très belle avec l'effet ouhaou »*.

## Deux modes, une seule page

Adrien a désigné le **vidéoprojecteur de la salle** comme support prioritaire,
tout en demandant une **recherche par nom ou dossard** — qu'on n'utilise pas sur
un écran que personne ne touche. Les deux ne se contredisent pas : ce sont deux
usages du même classement.

| Mode | Pour qui | Ce qui change |
| --- | --- | --- |
| **Mur** (`/resultats?mur`) | l'écran de la salle | lu à 5 m, rotation automatique des catégories, aucun bouton, aucune interaction |
| **Spectateur** (`/resultats`) | les téléphones | recherche par nom ou dossard, choix de la catégorie, tenu à bout de bras |

Le mode mur est le prioritaire : c'est lui qui décide de l'échelle typographique
et du rythme.

## Périmètre

### Inclus

1. Une page **autonome**, servie par le backend, sans dépendance externe.
2. **Mode mur** : rotation automatique entre les catégories, gros caractères.
3. **Mode spectateur** : recherche par nom ou dossard, sélection de catégorie.
4. **Rafraîchissement en douceur** toutes les ~15 s, avec l'heure du calcul
   affichée en clair.
5. Les **six couleurs de circuit** du club comme repères visuels.
6. Fonctionne quand le classement est vide (avant le premier scan).

### Explicitement exclu

- Toute écriture. La page ne fait que lire.
- L'authentification : elle est publique, c'est le but.
- Les classements club et finales (specs 009 et 010) — la page devra les
  accueillir, elle ne les invente pas.
- Une application installable. C'est une URL, on l'ouvre, c'est tout.

## La contrainte qui décide de la technique

> **Aucune dépendance réseau extérieure.**

Une page projetée pendant une compétition ne peut pas dépendre d'un CDN ni d'un
service de polices. Si la box Internet tombe à 10 h, l'écran de la salle doit
continuer d'afficher le classement — le backend, lui, est sur le réseau local.

Conséquences, assumées :

- **polices système**, pas de Google Fonts. La personnalité vient de l'échelle,
  de la graisse et de l'espacement, pas d'une fonte téléchargée ;
- **aucune bibliothèque** : pas de framework, pas de moteur de rendu. Le
  classement est une liste ordonnée ; c'est un problème de 2003, pas de 2026 ;
- **un seul fichier**, servi tel quel. Rien à construire, rien à déployer à part
  le backend.

## Ce que le classement a de particulier, et qu'il faut assumer à l'écran

Un score **peut baisser** sans que le grimpeur n'ait rien fait. La valeur d'un
bloc est `1000 / nombre de personnes l'ayant réussi` : quand quelqu'un d'autre
réussit un bloc qu'on avait, ce bloc vaut moins pour tout le monde.

C'est le cœur de la cotation par la difficulté observée, et c'est juste. Mais
projeté sur un mur, un score qui descend tout seul se lit comme un bug.

**Décision d'Adrien (28/08) : rafraîchissement en douceur, avec l'heure du
calcul.** On n'affiche donc **pas** de flèches ni de « −40 points » : ils
attireraient l'œil sur des baisses qui sont normales et qu'on ne peut pas
expliquer en une ligne sur un écran. On affiche l'heure du calcul, pour que
personne ne prenne un classement figé pour la vérité.

## Critères d'acceptation

| # | Critère | Vérification |
| --- | --- | --- |
| A1 | La page s'affiche sans **aucune** requête vers un domaine externe | inventaire des ressources chargées |
| A2 | Le classement est celui de l'API, sans recalcul côté page | comparaison avec `/api/public/classement` |
| A3 | Elle se rafraîchit seule et affiche l'âge du calcul | observation sur 60 s |
| A4 | Mode mur : les catégories défilent sans intervention | observation sur 2 cycles |
| A5 | Mode spectateur : chercher un nom ou un dossard isole le grimpeur | test navigateur |
| A6 | Aucune compétition active → message clair, pas une page blanche | `409` simulé |
| A7 | Classement vide → la page tient debout | avant le premier scan |
| A8 | Le backend tombe → la page garde le dernier classement et le dit | serveur arrêté |
| A9 | Lisible à 5 m sur un écran 1080p | mesure de la taille de caractère |
| A10 | Pas de débordement horizontal sur un téléphone 360 px | test à 360 px |
| A11 | Les noms sont affichés, **et rien d'autre** | inventaire des champs |
| A12 | La page ne coûte pas plus au serveur que le cache ne le permet | ~1 requête / 15 s / écran |

`A11` n'est pas une formalité : ces pages sont ouvertes à tout Internet et
portent des données de **mineurs**. Le classement expose nom, club, catégorie,
score, rang et un compte de blocs. Rien de plus n'a de raison d'être affiché.

## Cas limites

| Situation | Comportement |
| --- | --- |
| Aucune compétition active | message explicite, la page réessaie |
| Classement vide | « en attente des premiers résultats », pas un tableau vide |
| Une seule catégorie | pas de rotation, pas de sélecteur inutile |
| Un grimpeur sans club | la ligne s'affiche quand même |
| Deux homonymes | le dossard les distingue |
| Recherche sans résultat | on le dit, on ne vide pas l'écran |
| Réseau coupé après chargement | dernier classement conservé, âge affiché en rouge |
