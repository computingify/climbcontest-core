# Spec 020 — La page de résultats se règle depuis la console

> **Statut : validée (porte 2) et codée — 01/09/2026.** Adrien : « tu merges
> la PR du lot A puis tu fais les lots B et C ». La porte 7 (merge) reste la
> sienne.
> Quatre demandes d'Adrien du 01/09/2026, à l'issue du test de bout en bout.
> Elles portent toutes sur la même page et se recoupent — elles tiennent donc
> dans une seule spec plutôt que quatre.
>
> Trois points tranchés par Adrien avant rédaction :
> - masquer la recherche = **un bouton bascule** sur la page, mémorisé ;
> - le filtre des catégories s'applique à **toute** la page (mur et téléphones) ;
> - il se règle **depuis la console d'administration uniquement**.

## 1. Ce qui manque

### M1 — On ne peut pas nommer la compétition

Le bandeau affiche déjà `competition.nom` — c'est du code qui marche. Mais
**aucune route ne renomme une compétition**. Le nom est celui donné à la
création, et la compétition de production s'appelle aujourd'hui d'après ce qui a
servi à la créer. Sur un vidéoprojecteur, en salle, le titre de l'événement est
la première chose qu'on lit.

La date a exactement le même défaut, et elle sort dans le **nom de fichier des
archives** (`climbcontest-2026-11-15-…json`). On la traite en même temps.

### M2 — La catégorie n'apparaît nulle part sur les scratchs

Un classement de catégorie (« U13 F ») n'a pas besoin de rappeler la catégorie
de chaque ligne : elle est dans le titre. Un **scratch** — général, ou par
circuit — mélange les catégories, et rien ne dit qui est qui. On lit une liste
de noms sans savoir lesquels se comparent entre eux.

L'information est **déjà servie** par l'API : `charge_publique` enrichit chaque
ligne de `nom`, `club` et `categorie`. La page l'ignore.

### M3 — La recherche reste à l'écran au vidéoprojecteur

Le champ « Chercher un nom ou un dossard » est indispensable sur le téléphone
d'un parent, et parasite sur un mur. Il n'est masqué qu'en mode `?mur`, qui
emporte aussi la rotation automatique et le grand format — donc pas toujours ce
qu'on veut.

### M4 — Toutes les catégories s'affichent, toujours

La barre montre chaque classement calculé. Une compétition qui n'a que trois
circuits sur les quatre habituels, une catégorie à deux grimpeurs qu'on ne veut
pas projeter, une catégorie de test restée en base : rien ne permet de les
retirer de l'affichage. Sur un mur en rotation automatique, une catégorie qu'on
ne veut pas voir revient toutes les deux minutes, toute la journée.

## 2. Ce qu'on fait

### F1 — Renommer la compétition depuis la console

Vue **Compétition**, carte « État de l'édition » : un champ nom, un champ date,
un bouton. Rôle `ADMIN` — le nom part sur un écran public et dans les archives.

Le bandeau de la page de résultats le reprend au rafraîchissement suivant (15 s),
sans rien changer à `resultats.html`.

### F2 — La catégorie sur les scratchs, et seulement là

| Type de classement | Ligne d'appoint |
| --- | --- |
| `scratch` (général, F, H) | **la catégorie** — « U13 F » |
| `circuit` (« U13 scratch ») | **la catégorie** — « U13 F » ou « U13 H » |
| `categorie` (« U13 F ») | rien de plus (c'est le titre) |
| `club` | rien (une ligne de club n'a pas de catégorie) |
| recherche | inchangé — le nom du classement, comme aujourd'hui |

La page a déjà le véhicule : `l.contexte`, la ligne d'appoint sous le nom, avec
sa dégradation par densité. On ne crée rien.

### F3 — Masquer la recherche, d'un bouton

Un bouton dans le bandeau, à côté de « pause », **visible hors mode mur**.
`aria-pressed`, état mémorisé dans le stockage local du navigateur — le même
endroit que les favoris, et pour la même raison : ça ne regarde que cet appareil
et ça ne doit jamais partir sur le réseau.

Masquer **vide** la recherche en cours : masquer un filtre encore actif
laisserait une liste filtrée sans rien pour expliquer pourquoi.

En mode `?mur`, rien ne change : le champ reste masqué et le bouton n'apparaît
pas.

### F4 — Choisir les classements affichés, depuis la console

Vue **Compétition**, carte « Ce qu'affiche la page de résultats » : **une liste
de cases à cocher**, une par classement (scratchs, circuits, catégories, clubs).
Cochée = affichée. Rôle `ADMIN`.

**On range ce qu'on CACHE, pas ce qu'on montre.** Une catégorie qui apparaît en
cours de journée — une inscription à chaud crée « U15 F » qui n'existait pas ce
matin — doit s'afficher par défaut. Avec une liste de « ce qu'on montre », elle
disparaîtrait en silence, et personne ne comprendrait pourquoi.

Le réglage s'applique à **toute** la page : mur et téléphones. Une seule vérité,
rien à expliquer le jour J.

## 3. Ce qu'on ne fait pas

- **On ne filtre pas au calcul.** Tous les classements restent calculés et
  servis. Une archive doit rester complète — c'est déjà l'argument de
  `cycle.archiver`, et un classement masqué le matin doit pouvoir être
  démasqué l'après-midi sans rien recalculer.
- **Ce n'est pas un secret.** Un classement masqué reste dans la réponse JSON.
  C'est un réglage d'**affichage**, pas un contrôle d'accès ; le présenter
  autrement serait mentir.
- **La consultation d'une archive ne suit pas le réglage.** Une archive fige ce
  qu'elle fige ; on la revoit en entier.
- **Pas de tri ni de renommage des classements.** L'ordre est déjà tranché
  (spec 016, `classement_service.ordre`).

## 4. Critères d'acceptation

| # | On vérifie | Attendu |
| --- | --- | --- |
| A1 | `POST /admin/competition` avec un nom | 200, nom changé, servi par `/api/public/classement` |
| A2 | Nom vide, ou 200 caractères | 400, rien n'est modifié |
| A3 | Même route en organisateur | 403 |
| A4 | Date invalide | 400, le nom n'est pas modifié non plus |
| A5 | Page : classement de type `scratch` | la catégorie apparaît sous le nom |
| A6 | Page : classement de type `circuit` | idem |
| A7 | Page : classement de type `categorie` | **pas** de catégorie sous le nom |
| A8 | Page : classement `club` | inchangé |
| A9 | Page : bouton « masquer la recherche » | le champ disparaît, le choix survit au rechargement |
| A10 | Page : masquer avec une recherche en cours | la recherche est vidée, la liste redevient entière |
| A11 | Page en `?mur` | pas de bouton, champ masqué comme avant |
| A12 | `POST /admin/competition/affichage` | `groupes_masques` rangé dans `options` |
| A13 | `/api/public/classement` | **tous** les classements servis, plus `groupes_masques` |
| A14 | Page : un groupe masqué | absent de la barre et de la rotation |
| A15 | Le groupe affiché vient d'être masqué | bascule sur le premier visible |
| A16 | **Tous** les groupes masqués | le filtre est ignoré, la page reste utilisable |
| A17 | `validation_couleur` déjà dans `options` | toujours là après écriture de `groupes_masques` |
| A18 | Archive relue depuis la console | tous les classements, réglage ignoré |

## 5. Cas limites

**Un groupe masqué qui n'existe plus.** On a masqué « U19 F », l'import suivant
ne le crée pas. Le nom reste dans `options` sans effet — on ne fait pas le
ménage : le réimporter le ferait réapparaître, et l'oubli serait pire.

**Un groupe qui apparaît en cours de journée.** Il s'affiche : c'est tout
l'argument de ranger ce qu'on cache.

**Tout masqué.** Le filtre est ignoré plutôt que de servir une page vide. Une
page vide se lit comme une panne, et le jour J personne n'ira chercher le
réglage.

**Les favoris.** Ils sont composés à partir des classements de type `categorie`.
Un favori dans une catégorie masquée reste dans « ★ Mes favoris » — c'est un
choix du spectateur sur son propre téléphone, pas un classement projeté.

**Le nom porte des accents, une apostrophe, des chevrons.** Il est saisi à la
main et affiché sur une page publique : `textContent` partout, jamais
`innerHTML`. La console le fait déjà pour les noms d'archive.
