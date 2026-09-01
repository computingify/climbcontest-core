# Changelog

Toutes les évolutions notables de ClimbContest. Format
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnage
[sémantique](https://semver.org/lang/fr/).

**Ce fichier est contraignant, pas décoratif.** Le workflow de release échoue
avant même de construire l'archive s'il ne trouve pas la section de la version
taguée. Le contenu de cette section devient le corps de la release GitHub :
c'est ce qu'on lit pour savoir ce qui a changé.

Règle de version, sachant que l'application juge est déployée sur des téléphones
qu'on ne met pas à jour le matin d'une compétition :

- **MAJEUR** — rupture du contrat d'API avec l'application juge. Se prépare
  entre deux compétitions, jamais pendant.
- **MINEUR** — nouvelle fonctionnalité, compatible.
- **CORRECTIF** — correction, compatible.

## [Non publié]

### Ajouté

- **Le cycle de vie d'une édition se pilote depuis la console** (spec 018).
  Deux vues nouvelles, « Compétition » et « Archives », et le classeur gagne un
  test d'accès **en écriture**.
- **Tester l'accès en écriture.** Un aller-retour réel — écrire, relire,
  effacer — dans le **dernier coin de la grille** de l'onglet `Import`, jamais
  dans la matrice. C'est la seule façon de détecter une feuille partagée en
  **lecture seule** avec le compte du jeton : ce cas passe tous les contrôles de
  lecture sans broncher et ne se révèle qu'après le premier scan, quand les
  réussites commencent à s'empiler « en attente ». Le test signale aussi les
  plages protégées de `Import`, sans une requête de plus.
- **L'import a deux modes, annoncés.** *Mise à jour* (le défaut, le comportement
  d'avant) ajoute ce qui manque et corrige ce qui a changé ; *remplacement
  complet* efface les données du serveur avant d'importer. Le classeur est
  **lu avant** que quoi que ce soit soit effacé : si Google ne répond pas, la
  base n'a pas bougé. Le remplacement est réservé aux administrateurs.
- **Archiver une édition.** Le classement complet et les données brutes sont
  figés dans la base — pas dans un fichier à côté, parce que
  `climbcontest-sauvegarde` recopie la base et **rien d'autre**. La compétition
  passe « terminée », **rien n'est effacé**. Mesuré : 701 Ko pour 196 grimpeurs,
  50 blocs et 3 031 réussites, produits en 44 ms.
- **Revoir une édition archivée** — `/console/archives/<id>/resultats` — dans la
  **vraie** page de résultats : podium, colonnes, scratchs, mode mur. Le même
  gabarit, une source de données différente ; aucune seconde page à maintenir.
  C'est de la consultation seule : rien n'est restauré, et `/` continue
  d'afficher la compétition active. Le rafraîchissement automatique est coupé —
  les données sont figées.
- **Effacer les données du serveur**, sans avoir à changer de classeur. Les
  autres compétitions, les comptes, les archives et le classeur Google ne sont
  pas touchés. Fenêtre de confirmation avec les compteurs réels, mot à frapper,
  et la remarque « cette édition n'a jamais été archivée » quand elle s'applique.
- **Régler l'état de l'édition** — préparation, en cours, terminée.

### Corrigé

- **`Competition.statut` ne voulait rien dire.** Il était écrit à la création et
  **plus jamais** : `preparation` pour toujours sur une compétition créée
  normalement, `en_cours` pour toujours sur une compétition semée par
  `tools/semer_competition_test.py`. La garde de la spec 015 — refuser
  d'effacer une compétition en cours — était donc **exactement inversée** : elle
  ne se déclenchait jamais quand il aurait fallu, et bloquait en permanence les
  bases de test. Le statut se règle maintenant depuis la console, et
  l'effacement peut être **forcé** quand il est faux.
- **Un avertissement de la console ne s'efface plus tout seul.** `dire()`
  programmait un masquage à six secondes pour les messages « ok » **sans
  annuler le minuteur précédent** : un message de succès suivi d'un
  avertissement faisait disparaître **l'avertissement**. Trouvé en pilotant la
  console après un archivage — un avertissement qui s'efface est pire que pas
  d'avertissement, on croit avoir lu de travers.
- **Le cache de classement est invalidé après un effacement.** Il expirait seul
  en cinq secondes : sans conséquence en production, mais cinq secondes à
  regarder un classement qu'on vient de supprimer en se demandant si le bouton a
  marché. `classement_service.invalider()` existait depuis la spec 004 et
  n'était appelée nulle part.

### Modifié

- La construction de la charge de `/api/public/classement` sort du corps de la
  vue pour devenir `classement_service.charge_publique()`. Deux appelants
  désormais : la route publique et l'archivage. Écrite en double, elle aurait
  divergé au premier changement — et la page de résultats aurait cassé sur les
  archives uniquement, c'est-à-dire longtemps après. Réponse inchangée.
## [0.12.1] — 2026-09-01

Deux défauts d'affichage de l'écran projeté, vus en le regardant tourner.

### Corrigé

- **La colonne des noms récupère la place que les colonnes chiffrées gardaient
  pour elles.** Leurs largeurs avaient été réglées sur un écran 1920, où la
  ligne fait 96 px ; à 830 px de haut la ligne tombe vers 48 px et les mêmes
  proportions laissaient 77 px à un nombre de quatre chiffres. Des noms étaient
  tronqués alors qu'il restait de la largeur ailleurs.
- **Les titres de colonnes ne se superposent plus** quand une catégorie ne
  compte qu'un grimpeur. La ligne s'étire alors pour remplir le plateau et les
  titres, proportionnels à cette hauteur, grandissaient pendant que la fenêtre
  resserrait les colonnes : « GRIMPEUR » et « BLOCS » finissaient imprimés l'un
  sur l'autre. Le titre est plafonné, et la densité — qui décide des colonnes à
  retirer — se mesure désormais en hauteurs de ligne et non en pixels.

## [0.12.0] — 2026-09-01

La passe de lisibilité sur l'écran projeté, faite en le regardant tourner :
l'ordre des classements, les colonnes qui suivent la taille du texte, les
en-têtes qui restent en place, un défilement qui ne saccade plus, et un bouton
pour figer une catégorie.

### Modifié

- **Les scratchs passent avant leurs catégories.** L'ordre — donc celui de la
  barre, donc celui du cycle sur le mur — va du plus général au plus précis :
  `Scratch`, `Scratch F`, `Scratch H`, puis `U11 scratch`, `U11 F`, `U11 H`,
  puis `U13 scratch`… et le cumul par club en dernier. On passe de « U13
  scratch » à « U13 F » sans traverser la barre.
- **La rotation se met en pause.** Un bouton ⏸ / ▶ dans le bandeau du mur, pour
  figer une catégorie — pendant une remise de prix, ou quand quelqu'un demande
  « laisse la U13 F ». La jauge s'arrête où elle en est et repart de là.
- **Le temps d'affichage d'une catégorie découle du défilement**, et non d'une
  formule : une catégorie qui déborde reste le temps de descendre et de remonter
  en entier — à ~55 px/s, plus trois respirations de 2,5 s. Une catégorie qui
  tient à l'écran n'a rien à faire défiler : elle garde le plancher de 10 s.
  Mesuré : 10 s pour « U11 F », 40 s pour le scratch général et ses 891 px de
  débordement. `?mur&rotation=30` force toujours une durée fixe.
- **Le défilement automatique est deux fois plus lent** (~55 px/s) et **remonte
  aussi doucement qu'il descend**. L'assouplissement est maintenant posé sur
  chaque intervalle et non sur l'animation entière : appliqué globalement, il
  rendait la descente rapide et la remontée saccadée.
- **Les en-têtes de colonnes ne défilent plus** avec le classement : ils vivent
  au-dessus de la zone qui défile. Dedans, ils repartaient avec les lignes et
  revenaient d'un à-coup à la fin de la remontée.
- **Les tranches « 4 → 14 » disparaissent** des en-têtes de colonne : le premier
  rang de la colonne le disait déjà.

### Corrigé

- **Le défilement remonte à nouveau.** Les données sont relues toutes les quinze
  secondes, et chaque relecture recréait l'animation : elle repartait du haut
  avant d'avoir eu le temps de remonter, donc la remontée n'arrivait jamais. Une
  animation qui court sur le même plateau est maintenant laissée en place.
- **Le score n'est plus tronqué dans une petite catégorie.** Les colonnes d'une
  ligne se mesuraient en `em` — donc sur la police du conteneur, 16 px — pendant
  que leur contenu grandissait avec la hauteur de ligne. Sur une catégorie de
  deux grimpeurs, où cette hauteur monte, « 1473 » s'affichait en 67 px dans une
  colonne de 83 px. Elles se mesurent maintenant en proportion de la hauteur de
  ligne, ce qui corrige du même coup le **tableau qui ne suivait pas un
  redimensionnement de la fenêtre**.
- La hauteur de ligne des petites catégories est ramenée de 168 à 124 px : un
  seul grimpeur occupait un quart de mur en caractères de 67 px, ce qui se lit
  comme une erreur d'affichage.

## [0.11.0] — 2026-09-01

La page de résultats reprise de fond en comble, et trois classements de plus.
Le fil qui les relie : ce qu'on projette doit se lire d'un coup d'œil à huit
mètres, et ce qu'on tient dans la main doit se manipuler au pouce.

### Ajouté

- **Le spectateur peut suivre des grimpeurs.** Une **étoile** sur chaque ligne —
  dans la recherche comme dans un classement. Ce qu'elle change : la ligne du
  favori est surlignée, la catégorie où il grimpe porte une étoile dans la
  barre, et une entrée **« ★ Mes favoris »** en tête de barre donne la liste,
  avec le rang de chacun dans sa catégorie et l'étoile pour le retirer.
  Les favoris vivent dans le **stockage local du téléphone**, pas dans un
  cookie : un cookie repartirait dans chaque requête — vers une page que
  soixante personnes rafraîchissent toutes les quinze secondes — alors que ces
  noms n'ont rien à faire sur le réseau. Rien n'est envoyé, rien n'est stocké
  côté serveur. La liste est liée à **une** compétition : les identifiants de
  participant sont réattribués d'une édition à l'autre.
- **Un balayage horizontal change de catégorie** sur téléphone. Viser une
  pastille demande de regarder ce qu'on touche ; un balayage, non. Il est ignoré
  s'il part de la barre ou s'il est trop vertical — le défilement du classement
  reste le geste le plus fréquent.
- **Trois classements qui traversent les circuits** (spec 017) : `Scratch` avec
  tout le monde, `Scratch F` et `Scratch H`. La règle du classeur est appliquée
  telle quelle — chacun reste jugé sur les blocs de **son** circuit, et la valeur
  d'un bloc reste relative au groupe classé. Ils défilent sur le mur avec les
  autres et se choisissent au doigt sur téléphone.
  ⚠️ **Les scores d'un scratch ne sont comparables qu'entre eux.** 51 blocs sur
  67 appartiennent à plusieurs circuits : le dénominateur d'un scratch compte
  des grimpeurs que la catégorie ne comptait pas, et le score change. Un groupe
  plus petit donne des blocs plus chers — sur novembre 2025, la première du
  scratch féminin affiche 5110 quand le premier du général affiche 4978, sans
  avoir grimpé davantage. **La catégorie reste le résultat officiel.**
- **La page retire de l'information quand la place manque**, au lieu de tronquer :
  d'abord le numéro de dossard, puis le club, puis le compte de blocs. Le nom et
  le score ne partent jamais. « Les Lezards Vagab… · n° » ne renseignait personne.

### Modifié

- **Les ex æquo partagent leur marche.** Deux premiers à égalité sont côte à
  côte, au même niveau, sur le même socle et avec la même médaille — une marche
  porte un groupe de grimpeurs, pas un grimpeur. Il n'y a alors pas de deuxième
  marche : c'est ce que dit le classement.
- **Les couleurs du podium sont refaites.** La marche du milieu est en **argent
  gris**, celle de droite en **cuivre**, et l'or est un jaune franc qui ne se
  confond plus avec le bronze. La médaille suit désormais la **marche** et non
  le rang : deux ex æquo en tête gardent leur « 1 » affiché — c'est le chiffre
  qui dit la vérité sportive, la couleur dit la marche. Chaque médaille a deux
  valeurs, un aplat vif pour le socle et une encre plus sombre pour le chiffre,
  sans quoi un or assez vif pour se distinguer du bronze devient illisible.
- **Le classement se lit en colonnes**, et chaque colonne annonce sa tranche
  (« 4 → 10 »). La lecture en lignes, essayée d'abord, obligeait à balayer de
  gauche à droite pour suivre des rangs qui, eux, descendent. Deux autres mises
  en page restent atteignables par l'adresse pour comparer : `?sens=lignes` et
  `?sens=large` (une seule colonne, lignes hautes, le reste défile).
- **Le podium a la forme d'un podium** : le premier au centre et plus haut, le
  deuxième à gauche un peu en dessous, le troisième à droite plus bas encore,
  chacun sur son socle à la couleur de sa médaille.
- **Le classement devient un tableau.** En regardant comment les services de
  résultats sportifs présentent les leurs, trois choses reviennent partout et
  manquaient toutes : la colonne **Écart au premier** (« 1287 » ne dit rien
  seul ; « 1287, à −368 » dit la course), un **en-tête de colonnes** (sans lui,
  « 16 » et « −368 » sont deux nombres à deviner), et des **chiffres tabulaires
  alignés à droite** avec le texte à gauche. Les cartes détachées cèdent la
  place à des zébrures très peu saturées : des colonnes alignées se parcourent à
  la verticale, des cartes obligent à relire chaque ligne en entier.
- **Sur téléphone, le tableau se replie en deux lignes** — nom et score en
  grand, « club · 13 blocs · −285 » en dessous. Les cinq colonnes coûtent près
  de 300 px de gabarit : en dessous, il ne restait plus de place pour le nom, et
  c'est le nom qu'on vient lire.
- **Le classement se lit dans un seul sens.** Le podium est une rangée — 1, 2, 3
  de gauche à droite — et le reste enchaînait sur des colonnes lues de haut en
  bas : l'œil changeait de sens au milieu de l'écran. Les rangs se remplissent
  maintenant par lignes, 4, 5, 6 puis 7, 8, 9.
- **La barre de catégories est la même sur le mur et sur le téléphone.** Sur le
  mur, elle dit où on en est dans le cycle : la **jauge de rotation vit dans la
  pastille** de la catégorie affichée, au lieu d'un filet en haut de l'écran que
  personne ne reliait à rien. Sur un téléphone, c'est le sélecteur — on touche
  une catégorie, on ne voit qu'elle, et le cycle repart de là.
- **La page suit vraiment la fenêtre.** Le nombre de colonnes dépend de la
  largeur autant que de l'effectif (une colonne par tranche de 340 px, trois au
  plus), le podium en bandeau s'efface sous 900 px où trois cartes côte à côte
  s'écrasent, et toutes les tailles du bandeau sont fluides au lieu d'être
  figées — à 760 px, « U11 F » se cassait en deux lignes et la ligne d'état
  était tranchée.
- **Quand ça défile, les lignes s'effacent aux deux bords** au lieu d'être
  tranchées net : une ligne coupée en deux se lit comme un bogue d'affichage.

### Corrigé

- **Une petite catégorie ne laisse plus les trois quarts du mur vides.** Constaté
  en production juste après la 0.10.0, sur la compétition de test : trois
  grimpeurs, trois lignes collées en haut de l'écran, et le reste blanc — ça se
  lit comme un écran cassé, pas comme une petite catégorie. Le plateau est
  maintenant **centré** quand il ne remplit pas la hauteur (jamais quand il
  déborde : le défilement doit partir du haut), les lignes ont droit à plus de
  hauteur en dessous de six, et le nombre de colonnes suit vraiment l'effectif —
  un seul grimpeur occupait une demi-largeur parce que les deux branches du
  calcul étaient identiques.
- **« 1 grimpeurs »** devient « 1 grimpeur ». En 25 px sur un mur, ça se voit.

## [0.10.0] — 2026-08-31

Deux écrans repris, et pour la même raison : ce qu'on ne peut pas faire sans
terminal SSH le jour d'une compétition ne se fera pas. Le classeur Google se
règle maintenant depuis la console ; la page de résultats est faite pour être
projetée, et montre enfin toute une catégorie.

### Ajouté

- **La page de résultats est refaite pour être projetée** (spec 016). Mesuré sur
  l'ancienne, en 1920×1080 : **six grimpeurs et demi visibles sur vingt-quatre**,
  les dix-sept autres sous la ligne de flottaison d'un écran accroché en hauteur
  que personne ne fera défiler. Désormais la catégorie **entière** tient à
  l'écran — podium en bandeau, le reste en colonnes dont la taille s'adapte au
  plateau — et quand ça déborde vraiment, ça **défile doucement** au lieu de
  couper.
- **Un changement de place se voit.** La ligne **glisse** jusqu'à sa nouvelle
  position, porte `▲3` ou `▼1`, et celui qui monte pulse une fois. Techniquement,
  les lignes sont devenues persistantes : l'ancienne page les détruisait et les
  recréait à chaque rafraîchissement — on n'anime pas ce qu'on détruit.
- **Le fond est clair**, et ce n'est pas une question de goût : un
  vidéoprojecteur **ajoute** de la lumière sur un mur, il n'en retire pas. Un
  fond sombre, c'est du mur non éclairé — dans une salle qu'on ne peut pas
  plonger dans le noir, le contraste s'effondre. `?mur&sombre` reste là pour un
  écran LED.
- **La rotation devient un vrai mode** : elle suit la taille du plateau (8 s +
  0,55 s par grimpeur, entre 12 et 35 s), montre une barre de progression et
  annonce la catégorie suivante. Réglable par `?mur&rotation=25`.
- **Le bandeau porte le logo du club**, l'heure, la fraîcheur du calcul et le
  nombre de blocs validés depuis le matin — un compteur qui monte dit que le
  système vit, même quand un classement ne bouge pas.

### Supprimé

- **`/resultats` n'existe plus** (404). Les deux adresses servaient la même vue :
  `climbcontest.adn-dev.fr` menait déjà au même endroit, et un doublon d'URL
  finit toujours par diverger dans les têtes. Retiré le même jour du proxy
  (`@public path`) et du portail interne — `resultats.maison.adn-dev.fr` et
  `classement.maison.adn-dev.fr` ne répondent plus, la tuile en double a disparu.

- **Le classeur se règle depuis la console** (spec 015). Une vue « Classeur »,
  réservée aux administrateurs : sur quel classeur pointe la compétition, l'état
  du jeton, un test d'accès en **lecture seule** (titre, onglets, taille de la
  grille), un bouton **« Ouvrir le classeur »** vers la feuille elle-même — on
  vérifie qu'on est sur la bonne en l'ouvrant, pas en comparant deux
  identifiants de quarante-quatre caractères à l'œil — et le champ où coller le
  lien d'une autre feuille. Jusqu'ici, changer
  de classeur demandait un accès SSH à la VM et une requête SQL sur la base de
  production — le genre de geste qu'on finit par faire à 23 h la veille.
- **Trois modes de bascule, choisis à l'écran** : *relier seulement* (rien
  d'autre ne bouge), *même compétition, autre feuille* (toutes les réussites
  déjà enregistrées repartent vers la nouvelle feuille), *nouvelle compétition*
  (efface participants, blocs et réussites du serveur **et** vide la matrice
  `Import` de la nouvelle feuille). Le mode destructeur exige `EFFACER` frappé à
  la main, est refusé pendant une compétition `en_cours`, et vide le classeur
  **avant** de toucher la base : si Google refuse, rien n'est détruit.
- **Un bouton « Importer le classeur »**, enfin. La route existait depuis la
  spec 002, testée et protégée par rôle, mais **aucun écran ne l'appelait** :
  relier une feuille ne menait nulle part. Le rapport d'import s'affiche avec
  ses lignes ignorées — un import muet qui perd un grimpeur est exactement ce
  qu'on ne veut pas.
- **Le jeton Google se pose depuis la console**, au format JSON
  (`tools/exporter_jeton.py` convertit le `token.pickle` existant). Écrit en
  `0600`, le précédent conservé. `token.json` est lu **avant** `token.pickle` et
  `token.base64`, qui restent acceptés : les installations en place ne bougent
  pas. La console n'accepte **pas** de pickle — le serveur ferait
  `pickle.loads()` sur du contenu venu du réseau.

### Corrigé

- **Un dossard au-delà de la largeur du classeur ne bloque plus le miroir.**
  L'API Google refuse une écriture hors grille (« exceeds grid limits ») ; le
  miroir, qui ne marque rien comme synchronisé en cas d'échec, retentait
  **indéfiniment** — une seule réussite bloquait son lot et tous les suivants.
  La feuille est maintenant élargie avant l'écriture, lignes comme colonnes,
  avec cinq de marge. Le cas n'a rien de théorique : un participant inscrit à
  chaud reçoit le premier dossard libre, qui sort vite de la largeur préparée.
  ⚠️ Les formules du classeur, elles, restent écrites pour 120 grimpeurs : la
  console le dit au moment du test.
- **Un jeton rafraîchi est réécrit** dans `token.json` : chaque redémarrage
  repartait sinon d'un jeton périmé et redemandait un rafraîchissement à Google.
- **Le message de retour de la console reste visible.** Il est désormais collant
  sous la barre du haut : un bouton en bas d'une vue longue affichait sa réponse
  hors de l'écran, et on croyait qu'il ne s'était rien passé.

## [0.9.0] — 2026-08-30

La console cesse de faire taper ce qui devrait être choisi. Le défaut qui a
motivé cette version se lisait en production : 26 « U13 H » et **un** « U13 M ».
Ce grimpeur était seul dans sa catégorie, donc premier d'un classement d'une
personne, et absent du vrai « U13 H ». Un champ libre produit ça ; une liste ne
le peut pas.

### Ajouté

- **La console guide la saisie** (spec 013). Catégorie et club deviennent des
  listes déroulantes, remplies avec ce que la compétition connaît déjà, et
  terminées par « ＋ Autre… » pour une valeur inédite — qui rejoint la liste dès
  l'enregistrement. La motivation est mesurée, pas théorique : la production
  portait 26 « U13 H » et **un** « U13 M ». Ce grimpeur était seul dans sa
  catégorie, donc premier d'un classement d'une personne.
- **Le dossard est attribué, plus saisi.** Le serveur prend le premier numéro
  **libre** — un trou dans la suite s'il y en a un. L'organisateur n'a plus à
  savoir lesquels sont pris au moment où il a le moins de temps. Deux
  inscriptions simultanées ne peuvent pas recevoir le même : c'est la contrainte
  d'unicité qui tranche, et la tentative perdante recommence.
- **`GET /admin/referentiels`** : les catégories et les clubs connus de la
  compétition en cours, pour remplir ces listes.

### Modifié

- **Ce qui est tapé à la main est mis en forme avant d'être enregistré**, côté
  serveur — donc y compris pour un appel direct à l'API. Nom et prénom en casse
  stricte (« MARTIN » → « Martin ») ; club avec les sigles préservés (« CAF
  annonay » → « CAF Annonay ») ; catégorie tout en majuscules et l'espace avant
  le genre rétabli (« U13F » → « U13 F »). L'import du classeur, lui, n'est
  **pas** reformaté : le classeur fait autorité sur ses lignes.
- La vue « Dossards » choisit sa catégorie dans une liste, entrée vide =
  toutes.

### Corrigé

- **La console sait sur quelle compétition elle agit dès la connexion.** Le
  bandeau prévu pour dire *sur quoi on agit* affichait « aucune compétition
  active » alors qu'une compétition l'était, et ne se corrigeait qu'au
  rechargement de la page. `/admin/moi` portait la compétition, la réponse de
  connexion non — deux réponses écrites séparément avaient divergé. C'est le
  pire moment pour ce message : un organisateur qui se connecte le matin de la
  compétition lisait l'exact contraire de la vérité.

### Sécurité

- **L'import du classeur n'écrase plus un participant ajouté à la main.** Il
  retrouvait les fiches *par leur dossard* : un inscrit sur place ayant reçu le
  numéro 3 était remplacé si le classeur apportait un jour un dossard 3 — et ses
  réussites, attachées à la ligne, changeaient de propriétaire sans que rien ne
  le dise. L'import refuse désormais, et le signale dans son rapport.

## [0.8.1] — 2026-08-30

### Corrigé

- **Le catalogue d'une compétition n'est plus servi pour une autre.** Scénario
  certain : on répète le jour J sur une compétition de test, puis on crée celle
  de novembre — les téléphones de la répétition gardaient la liste de test.

  Les téléphones valident leur catalogue avec un simple entier
  (`If-None-Match: "3"`), et `catalogue_version` repartait à 1 à chaque
  compétition : deux compétitions portaient le même numéro, et le serveur
  répondait `304` sur une liste qui n'était pas la sienne.

  Ce n'est pas une corruption de données — le serveur enregistre bien la
  réussite sur la bonne compétition. C'est **le contrôle humain** qui saute :
  le juge lit le nom affiché pour vérifier qu'il a le bon grimpeur, et il
  lisait un nom de test pour un dossard bien réel.

  `catalogue_version` devient globalement croissante (un numéro ne ressert
  jamais) et `?depuis=N` exige `==` au lieu de `>=`. Rien à changer sur les
  téléphones, et le `304` continue d'économiser les 15 ko de chaque sondage.

## [0.8.0] — 2026-08-30

### Ajouté

- **La console d'administration est refondue.** Sept onglets ajoutés au fil des
  specs — et ça se voyait : *deux* parlaient des téléphones des juges, et
  « retrouver un scan » était rangé sous « Appareils » alors qu'on y cherche une
  réussite. Quatre vues désormais, groupées par la question qu'on se pose le
  jour J : **Participants** (inscrire, chercher, imprimer), **Réussites**
  (saisir, retrouver), **Téléphones** (installer l'app juge *et* suivre les
  envois), **Réglages** (mon mot de passe, les comptes).

  Navigation par burger et tiroir latéral, contenu en cartes, et la barre du
  haut affiche **la compétition active** — « le classeur est-il le bon ? » est
  le point le plus souvent oublié du runbook, et la console était le seul
  endroit où l'on agissait sans jamais voir sur quoi.

- `/admin/moi` renvoie la compétition active, pour l'afficher.

### Corrigé

- **Le jeton du juge survit à l'installation de l'application** (spec 014).
  Symptôme : l'application ajoutée à l'écran d'accueil affichait « cette
  application a besoin du lien fourni par l'organisateur », alors qu'elle avait
  été installée depuis le lien qui porte le jeton.

  Deux causes, toutes deux dans notre code. L'adresse était nettoyée aussitôt
  lue, donc « Sur l'écran d'accueil » capturait `/juge` sans jeton ; et
  `start_url` du manifeste ne portait aucun jeton, donc l'application lancée
  depuis son icône ne pouvait le retrouver que dans son stockage local — lequel
  est **cloisonné sur iPhone**, séparé de Safari.

  Le jeton passe donc du fragment (`#j=`) à la requête (`?j=`), et le manifeste
  devient dynamique : son `start_url` porte le jeton. L'application le reçoit
  dans son adresse **à chaque lancement, sur toutes les plateformes**, sans plus
  dépendre d'un stockage qui peut être vidé ou cloisonné.

  Les liens déjà distribués en `#j=` restent acceptés.

### Ajouté

- **Un bouton « Scanner le QR de l'organisateur »**, affiché uniquement quand
  l'application démarre sans jeton. Une installation faite avant ce correctif ne
  peut pas se réparer toute seule ; sans ce bouton, le juge lit un constat et
  n'a aucun geste à sa portée.

### Sécurité

- ⚠️ **Le jeton voyage désormais dans une partie de l'adresse qui est
  journalisée.** C'est le prix assumé du correctif ci-dessus, et il se paie sur
  le proxy : **un filtre masquant le paramètre `j` dans le journal de `edge`
  reste à poser** — il n'est pas dans ce dépôt, et doit accompagner le
  déploiement. Rappel de proportion : ce jeton est affiché au mur en QR ; il
  arrête un robot qui balaie Internet, pas quelqu'un présent dans la salle.

## [0.7.0] — 2026-08-30

L'audit de préparation de novembre, appliqué. Le détail : rapport
`docs/rapports/2026-08-30-audit-novembre.html`.

### Ajouté

- **Console → onglet « App juge »** : le lien d'installation de l'application
  iPhone et son QR à afficher au mur, avec le mode d'emploi en trois étapes.
  Demande `CLIMBCONTEST_API_KEY_PWA` sur le serveur — la réponse le dit si
  elle manque.
- **`/health` → `miroir_derniere_erreur`** : la dernière plainte du miroir
  Google Sheets, lisible sans SSH (« aucun classeur relié… », « Aucun jeton
  Google… »).
- **La PWA au niveau de la refonte Android** : étapes numérotées, couleurs de
  circuit (le catalogue les porte désormais), police Archivo servie
  localement, pastilles de file dans l'en-tête. Cache du service worker en v2 :
  les téléphones déjà installés récupèrent la nouvelle coquille seuls.
- `tools/load/charge_novembre.py` : le banc de charge du scénario de
  novembre — à ne jamais pointer vers la production.

### Sécurité

- Le cookie de session de la console porte `Secure`, `HttpOnly` et
  `SameSite=Lax` (`CLIMBCONTEST_COOKIE_SECURE=0` pour un développement en
  http).
- Le réimport du classeur exige le rôle organisateur.
- Code d'authentification mort supprimé (`exige_cle_api_stricte`).

### À savoir pour le jour J

- Trois nouveaux gestes au runbook : **poser le jeton Google sur la VM**
  (constaté absent — sans lui le classeur ne se remplit jamais), poser la
  **clé PWA**, et vérifier que **le miroir écrit vraiment** avant la
  compétition.

## [0.6.0] — 2026-08-29

### Ajouté

- **Le classement par club** (spec 010). Somme des scores de tous les grimpeurs
  du club, comme décidé le 29/08. Il apparaît comme un groupe de plus dans
  `/api/public/classement` et sur la page de résultats — aucune route n'a
  changé.

  **Dérivé, jamais recalculé** : il additionne les classements par catégorie
  déjà produits. C'est ce qui garantit qu'il ne pourra pas diverger d'eux.

  Chaque grimpeur ne compte **qu'une fois**, par sa catégorie. Un grimpeur
  figure aussi dans le scratch de son circuit ; additionner les deux l'aurait
  compté deux fois. La catégorie est son résultat officiel, celui du podium.

  Le **nombre de grimpeurs** du club est affiché : sans lui, le classement
  serait illisible vu la règle retenue.

### À savoir pour le jour J

Un club nombreux est avantagé — c'est la règle, choisie en connaissance de
cause. Mais **s'agglutiner sur les mêmes blocs ne rapporte presque rien** : un
bloc vaut `1000 / nombre de personnes l'ayant réussi`. Trois grimpeurs qui font
tous le même bloc facile gagnent 999 à eux trois, moins qu'un seul ayant tenu
deux blocs que personne d'autre n'a réussis.

« Le gros club gagne » est donc vrai **à niveau égal**, pas dans l'absolu.

## [0.5.1] — 2026-08-29

### Ajouté

- **Recopie locale de la base toutes les dix minutes**, les 24 dernières
  conservées — quatre heures de recul. Chaque copie fait ~160 ko, est produite
  par l'API de sauvegarde en ligne de SQLite (donc cohérente sans bloquer les
  écritures) et **relue immédiatement** : une sauvegarde qu'on n'a pas relue
  n'est pas une sauvegarde, c'est un fichier.

  La stratégie disait « pendant la journée : rien », en s'appuyant sur la
  redondance offerte par le miroir Google. Or ce miroir était cassé en silence
  ce matin-là : la redondance était une espérance, pas une garantie.

  ⚠️ Ces copies sont sur le **même disque** : elles protègent d'une fausse
  manœuvre ou d'une corruption, pas de la perte du disque.

- `/health` expose l'**âge de la dernière copie**. Une sauvegarde qui s'arrête
  doit se voir — c'est la leçon du miroir.

## [0.5.0] — 2026-08-29

**La gestion des comptes se fait depuis la console.** La ligne de commande ne
sert plus qu'à créer le tout premier administrateur — demander un accès SSH à
chaque nouveau bénévole n'avait aucun sens.

### Ajouté

- Écran **Comptes**, visible des seuls administrateurs : créer un compte,
  remettre un mot de passe oublié, changer un rôle, désactiver ou réactiver.
- Onglet **Mon mot de passe** : chacun change le sien sans déranger un
  administrateur. **L'ancien est exigé**, même en session ouverte — sinon un
  ordinateur laissé déverrouillé dans la salle suffirait à s'approprier un
  compte.
- **Le dernier administrateur ne peut plus se retirer ses droits ni se
  désactiver.** C'est un piège sans retour : plus personne ne peut gérer les
  comptes, et il faut ressortir SSH et la ligne de commande — typiquement un
  dimanche matin. Le message dit quoi faire : nommer d'abord quelqu'un d'autre.

  La console grise les boutons concernés, mais c'est le **serveur** qui
  protège : l'interface évite seulement une fausse manœuvre.

### Corrigé

- Une **faute de frappe sur l'ancien mot de passe déconnectait**. Le serveur
  répond `401`, que la console interprétait comme une session expirée. Trouvé
  en le faisant à la main dans un navigateur : aucun test de route ne pouvait
  le voir, les deux cas répondent `401`.

### Le mot de passe oublié

Tranché : pas de serveur de courriel — en monter un pour un usage annuel serait
une pièce de plus à maintenir. L'administrateur pose un nouveau mot de passe
depuis la console et le transmet de vive voix ; l'intéressé le change ensuite
lui-même.

## [0.4.2] — 2026-08-29

### Ajouté

- **Frein anti-force-brute** sur la connexion à la console. Au-delà de trois
  échecs depuis une même adresse, l'attente double à chaque tentative — 2 s,
  4 s, 8 s… — plafonnée à cinq minutes, et l'ardoise s'efface après trente
  minutes de silence ou à la première connexion réussie.

  Le compteur est **en base**, pas en mémoire : avec quatre workers, un
  compteur par processus diviserait la protection par quatre. Il est **par
  adresse** et non par identifiant — compter par identifiant offrirait à
  n'importe qui le moyen de bloquer le compte d'un organisateur en se trompant
  exprès.

  Le frein agit **avant** la vérification du mot de passe : `scrypt` est lent à
  dessein, et laisser un robot le déclencher à chaque tentative reviendrait à
  lui offrir un moyen d'épuiser le serveur.

### Modifié

- **La console est de nouveau joignable depuis Internet.** La restriction au
  LAN posée le 28/08 était une mesure d'attente, quand la console n'avait
  qu'une clé d'API partagée. Elle avait surtout un défaut de fond : le jour de
  la compétition, **les organisateurs sont au gymnase et la VM est à la
  maison**. Le filtre rendait la console inutilisable exactement quand elle
  sert.

  `/health` reste au LAN : c'est une sonde interne.

## [0.4.1] — 2026-08-29

### Ajouté

- **La console d'administration elle-même**, sur `/console`. La `0.4.0` livrait
  ses routes JSON — et la spec la déclarait livrée — mais pas la page. Un
  organisateur ne peut pas utiliser `curl` un dimanche matin.

  Quatre écrans : connexion, participants, saisie manuelle, impression. En
  mauve là où la page publique est en bleu, pour qu'on sache d'un coup d'œil si
  on regarde ce que voient les spectateurs ou ce qu'on peut modifier.

  Pensée pour le jour J : une session qui expire ramène à la connexion **en le
  disant** plutôt que de ressembler à une panne ; une saisie en double
  s'affiche en jaune et non en rouge — ce n'est pas une faute, c'est une
  précaution qui a fonctionné ; après une saisie le curseur revient sur le
  champ « bloc », pour enchaîner plusieurs blocs du même grimpeur.

## [0.4.0] — 2026-08-29

**La console d'administration.** Spec 005 — les quatre briques retenues pour
novembre.

### Ajouté

- **Comptes et rôles.** Deux rôles : `admin` et `organisateur`. Mot de passe
  haché, session signée de 12 heures, et un contrôle d'accès **fail closed** —
  session absente, illisible, expirée, cookie forgé, utilisateur désactivé
  entre-temps, rôle inconnu : tout donne `401`.
  Le premier compte se crée par `flask creer-admin`, jamais par une route.
- **Participants à chaud** : ajouter quelqu'un pendant la compétition, et
  réaffecter un dossard. Le catalogue est incrémenté, donc les téléphones
  voient le nouveau venu en moins de vingt secondes.
- **Saisie manuelle** d'une réussite, et sa suppression. Elle compte au
  classement exactement comme un scan, porte `source = manuel` et
  **l'identifiant de qui l'a saisie**.
- **Impression des dossards** : format repris du classeur, en bandes à
  découper, dimensionné en millimètres. Un lot, une catégorie, ou un seul.
  Le QR est généré **localement** — le classeur, lui, appelle
  `api.qrserver.com`, ce qui envoie les dossards à un tiers et ne fonctionne
  pas si la connexion tombe.

### Sécurité

- La clé d'API ne donne **plus** accès à l'administration. Elle est partagée
  entre 25 téléphones ; en faire un droit d'administration reviendrait à donner
  les clés de la base à tout le monde. C'était une mesure d'attente, posée en
  urgence la veille.
- Le temps de réponse à la connexion est le même que l'identifiant existe ou
  non. Répondre plus vite pour un compte inconnu révélerait quels identifiants
  sont valides.

### ⚠️ À faire au déploiement

`CLIMBCONTEST_SECRET_KEY` doit être définie sur la VM. Sans elle, la console
répond **503** et refuse de servir — avec la clé de développement, un cookie de
session se forge en trois lignes. Mieux vaut une console indisponible qu'une
console ouverte. Le reste du service n'est pas affecté.

## [0.3.4] — 2026-08-28

### Corrigé

- **Le miroir répétait la même plainte toutes les 40 secondes.** Le garde-fou de
  la `0.3.3` évitait bien l'appel Google inutile, mais l'avertissement partait
  encore à chaque cycle et sur chacun des quatre workers. Sur une journée, des
  milliers de lignes identiques — et c'est ainsi qu'on rate la vraie panne
  quand elle arrive.

  Une cause n'est journalisée **qu'une fois**. Le retour à la normale, lui, est
  annoncé : le silence qui suit une plainte serait autrement ambigu — on ne
  saurait pas si le miroir est reparti ou s'il est mort.
- Le garde-fou annonçait « 0 en attente ». C'est le chiffre qui compte : il dit
  combien de réussites seront reportées le jour où un classeur sera relié.

## [0.3.3] — 2026-08-28

### Corrigé

- **Une compétition sans classeur relié remplissait le journal.** Entre la
  création d'une compétition et son paramétrage, il n'y a pas encore de
  `spreadsheet_id` — c'est normal. Le miroir tentait pourtant l'écriture toutes
  les 40 secondes et journalisait une erreur Google à chaque fois, sur chacun
  des quatre workers : **six erreurs par minute** pour une situation
  parfaitement normale.

  C'est ainsi qu'un journal devient illisible, et qu'on rate la vraie panne
  quand elle arrive. Le miroir passe désormais son tour, et le dit une fois.

## [0.3.2] — 2026-08-28

### Corrigé

- **Le miroir ne trouvait jamais le jeton Google en production.** Le client le
  cherchait en chemin *relatif* — donc dans le répertoire de travail du service,
  où il n'a jamais été. Il vit dans `shared/secrets/`, hors des releases, comme
  les données ; l'unité systemd définissait déjà `CLIMBCONTEST_SECRETS_DIR`, que
  le code n'avait jamais lu.

  Constaté sur la VM : « Aucun jeton Google » toutes les 40 secondes. **Aucune
  réussite n'aurait atteint le classeur le jour de la compétition.** Les données
  n'étaient pas perdues pour autant — elles restent en base, marquées non
  synchronisées, et sont retentées : c'est exactement ce que la spec 002 avait
  prévu. Mais le classeur serait resté vide.

  Le message d'erreur cite désormais **les chemins essayés**. Le précédent
  disait « le déposer dans token.pickle », sans chemin — c'est ce qui a masqué
  le vrai problème : le fichier existait, mais ailleurs.

## [0.3.1] — 2026-08-28

### Corrigé

- **Avant le premier scan, l'écran de la salle affichait tout le monde à zéro,
  sans rien dire.** Le classement était juste — tous ex æquo — mais projeté sur
  un mur pendant la première demi-heure de chaque compétition, il se lisait
  comme un écran figé. La page l'annonce désormais, tout en gardant la liste :
  voir les inscrits affichés rassure sur le fait que le système tourne.

## [0.3.0] — 2026-08-28

La page de résultats. Spec 006.

C'est la première version que les **spectateurs** voient : jusqu'ici, tout ce qui
avait été livré s'adressait aux juges ou aux organisateurs.

### Ajouté

- **La page de résultats**, en deux modes servis par un seul fichier :
  - `/resultats?mur` — l'écran de la salle. Rotation automatique des catégories
    toutes les 20 s, nom à **42 px** sur un écran 1080p (lisible à cinq mètres),
    aucun bouton. Elle ne s'arrête jamais et n'attend aucune interaction.
  - `/resultats` — les téléphones. Recherche par nom ou par dossard, et choix de
    la catégorie.
- La recherche traverse **tous** les classements, pas seulement celui affiché :
  un parent qui cherche son enfant ne connaît pas forcément sa catégorie.
- `age_s` dans `/api/public/classement` : l'âge réel du calcul, vu par le
  serveur. La page ne peut pas le déduire — son horloge n'est pas celle du
  serveur — et affichait donc « calculé il y a 1 s » pour un classement que le
  cache gardait depuis 5 s.
- `tools/mesurer_volume.py` — le critère A12 de la spec 003.

### Modifié

- La racine `/` sert la page de résultats, et non plus un JSON de service.
- **Aucune dépendance extérieure** dans la page : polices système, aucune
  bibliothèque, un seul fichier servi tel quel. Une page projetée pendant une
  compétition ne peut pas dépendre d'un CDN — si la box tombe à 10 h, l'écran de
  la salle doit continuer. Vérifié dans un navigateur : **2 requêtes en tout**.
- Quand le backend devient injoignable, la page **garde** le dernier classement
  connu et affiche son âge en rouge. Une page de résultats qui se vide sur une
  erreur réseau fait croire que la compétition s'est arrêtée.

### Mesuré

Le volume échangé par l'application juge, contre la VM, sur 200 validations
réelles extrapolées à 3 600 :

| | v2 | v3 |
| --- | --- | --- |
| Requêtes HTTP | 10 800 | **817** |
| Octets sur le fil | 4,53 Mo | **696 ko** |
| Allers-retours **bloquants** | 10 800 | **0** |

L'estimation de la spec 003 (~360 requêtes, ~110 ko) était trop optimiste ; la
spec a été corrigée avec les chiffres mesurés, pas l'inverse.

## [0.2.1] — 2026-08-28

### Sécurité

- **La console d'administration n'exigeait aucune authentification.** Ses deux
  routes (`/admin/import/sheet`, `/admin/import/rapport`) étaient protégées par
  le garde-fou de clé d'API **en mode toléré** — lequel accepte, par
  construction, une requête sans clé. Cette tolérance existe pour que
  l'application `v3.1.4` du Play Store continue de fonctionner ; elle n'avait
  rien à faire ici.

  Constaté en production, exposé sur Internet :
  `GET https://climbcontest.adn-dev.fr/admin/import/rapport` répondait `200`, et
  un `POST` sur `/admin/import/sheet` aurait déclenché un **réimport complet du
  classeur** — réécriture de la base et rafale d'appels Google — à la demande de
  n'importe qui.

  Ces routes exigent désormais une clé **valide**, sans tolérance, et chaque
  refus est journalisé. Les trois routes du juge restent tolérantes ; un test le
  verrouille explicitement pour qu'on ne durcisse pas la `v3.1.4` par accident.

  Corrigé en parallèle côté `edge` : `/admin/*` ne sort plus du LAN, sur le même
  motif que `/health`. Les deux couches sont voulues — la spec 005 ouvrira cette
  console à de vrais comptes, et il vaut mieux que le filtre réseau soit déjà là
  le jour où l'authentification applicative change.

## [0.2.0] — 2026-08-28

La base devient la source de vérité, le classeur en devient un miroir. C'est le
préalable de tout le reste : ni classement live, ni page résultats, ni saisie
manuelle tant que les données ne sont pas fiables. Spec 002.

**L'application juge `v3.1.4` du Play Store continue de fonctionner sans mise à
jour** : ses trois routes gardent leur contrat au caractère près, et une suite de
tests dédiée le vérifie à chaque build.

### Ajouté

- Modèle multi-compétition. L'identité d'un participant est son identifiant, pas
  son dossard : un dossard est un attribut, nullable, unique par compétition, qui
  peut changer de main tant qu'aucune réussite n'y est attachée.
- Table `Success` avec contrainte d'unicité `(participant, bloc)` : un double
  appui sur « Envoyer » renvoie `201` et ne crée qu'une seule réussite.
- Colonne `sheet_synced_at` : ce qui reste à écrire dans le classeur est
  désormais une requête SQL, pas une file en mémoire vive.
- `GET /api/v2/catalog` versionné, avec `304` quand rien n'a changé — de quoi
  faire valider les scans hors ligne par la future application juge.
- Clé d'API en **mode toléré** : absente elle est acceptée mais comptée, fausse
  elle est refusée. Le compteur, exposé par `/health`, dira quand on pourra la
  rendre obligatoire sans casser l'application déployée.
- `/health` expose le nombre de réussites en attente de synchronisation.
- Comptes et rôles, posés vides pour éviter une migration en spec 005.

- **Moteur de classement** (spec 004), pur et sans dépendance à Flask ou SQL.
  Reproduit **196 scores et rangs sur 196** du classeur de novembre 2025, sur
  1003 réussites et 12 groupes. Validation par couleur en option par
  compétition, désactivée par défaut ; variante retenue quand elle sera activée :
  **deux couleurs pleines** (décision du 28/08).
- `GET /api/public/classement` et `/api/public/groupes` — sans authentification,
  avec cache de 5 s. Ce sont les routes de la future page spectateurs.
- **Envoi par lots** : `POST /api/v3/successes` (spec 003, IT1). Un lot n'échoue
  jamais en bloc — un dossard inconnu sur cinq n'empêche pas les quatre autres
  d'être enregistrés. Verdict par élément, et la version du catalogue voyage
  dans la réponse. Les trois routes `v2` restent en service, **inchangées**.
- `ETag` / `If-None-Match` sur le catalogue : quand rien n'a bougé, la réponse
  fait ~150 octets au lieu de 6–8 ko.
- Traçabilité des réaffectations de dossard. Avec la file d'attente à venir, une
  réussite peut arriver après que son dossard ait changé de main ; la décision du
  28/08 est de **l'accepter** — elle suit le nouveau porteur. `reussites_suspectes()`
  permet de retrouver ces cas au lieu de les laisser passer en silence.

### Corrigé

- **R1** — La base n'est plus effacée au démarrage. `drop_all()` s'exécutait au
  niveau module, donc dans chacun des quatre workers gunicorn. Vérifié : quatre
  processus démarrés simultanément laissent la base intacte.
- **R2** — Les réussites survivent à un redémarrage.
- **R3** — Un échec d'écriture Google ne détruit plus rien : rien n'est marqué
  comme synchronisé, et le cycle suivant réessaie.
- **R4** — Toute réussite est tracée, horodatée, rejouable.
- **R5** — Un grimpeur sans club ni catégorie est importé et signalé, au lieu
  d'être ignoré en silence.
- **R6** — Le numéro de bloc est lu à une position explicite. Il était deviné par
  `line[-1]`, ce qui donnait le numéro de zone sur une ligne tronquée, et
  envoyait les réussites sur la mauvaise ligne du classeur.
- **R7** — Un dossard inconnu ne déclenche plus de lecture du classeur.
- **R12** — Les doublons ne sont plus possibles.

- **La sonde `/health` interroge la base.** Elle répondait `"ok"` sans jamais
  l'ouvrir : quatre workers démarrés sur une base sans tables passaient pour un
  déploiement réussi, alors que chaque scan renvoyait 500. Elle répond
  désormais **503 `degraded`**, ce qui déclenche le retour arrière.
- **Verrou de schéma : un orphelin ne bloque plus les démarrages.** Un processus
  tué entre la prise et la libération laissait la ligne en base. Le délai
  d'expiration de 60 s ne suffisait pas — `RestartSec=5s` fait toujours
  redémarrer le service à l'intérieur de ce délai. La question posée n'est plus
  « le verrou est-il vieux » mais « le schéma est-il prêt ».
- `_rendre_verrou()` supprimait le verrou de n'importe qui, y compris celui,
  tout frais, du processus qui venait de le lui voler.
- **L'archive de release ne contenait pas l'application.** Le script copiait
  `climb_contest` — un nom qui n'a jamais existé — et un `|| true` avalait
  l'échec. Le premier tag portant le vrai backend aurait produit une archive
  sans une ligne de code, et gunicorn serait mort au démarrage. Une vérification
  refuse désormais de publier une archive sans application.
- Un corps JSON qui n'est pas un objet (`[1,2]`, `"x"`, `42`) donnait **500** sur
  les routes de juge. Il donne 400.
- La journalisation applicative n'écrivait nulle part : le logger racine est à
  `WARNING` sans destination, et le service ne passe aucun niveau. La ligne qui
  doit décider du passage en mode strict de la clé d'API était donc muette.

### Modifié

- Point d'entrée : `wsgi:app` via une fabrique d'application. `main.py`,
  `models.py` et `google_sheets*.py` sont remplacés.
- L'identifiant du classeur vit en base, par compétition — plus jamais en dur
  dans le code. C'était le geste le plus souvent oublié d'une édition à l'autre.

## [0.1.2] — 2026-08-28

Trois défauts de l'agent de déploiement, trouvés en jouant réellement les
scénarios d'échec de la spec 001 plutôt qu'en les supposant.

- **Moteur de classement** (spec 004), pur et sans dépendance à Flask ou SQL.
  Reproduit **196 scores et rangs sur 196** du classeur de novembre 2025, sur
  1003 réussites et 12 groupes. Validation par couleur en option par
  compétition, désactivée par défaut ; variante retenue quand elle sera activée :
  **deux couleurs pleines** (décision du 28/08).
- `GET /api/public/classement` et `/api/public/groupes` — sans authentification,
  avec cache de 5 s. Ce sont les routes de la future page spectateurs.
- **Envoi par lots** : `POST /api/v3/successes` (spec 003, IT1). Un lot n'échoue
  jamais en bloc — un dossard inconnu sur cinq n'empêche pas les quatre autres
  d'être enregistrés. Verdict par élément, et la version du catalogue voyage
  dans la réponse. Les trois routes `v2` restent en service, **inchangées**.
- `ETag` / `If-None-Match` sur le catalogue : quand rien n'a bougé, la réponse
  fait ~150 octets au lieu de 6–8 ko.
- Traçabilité des réaffectations de dossard. Avec la file d'attente à venir, une
  réussite peut arriver après que son dossard ait changé de main ; la décision du
  28/08 est de **l'accepter** — elle suit le nouveau porteur. `reussites_suspectes()`
  permet de retrouver ces cas au lieu de les laisser passer en silence.

### Corrigé

- **Boucle de redémarrages.** Une release défectueuse était retentée à chaque
  tick de 2 minutes, et chaque tentative redémarrait le service deux fois. Un
  tag qui a échoué est désormais mémorisé et n'est plus réessayé ; publier une
  version suivante suffit à débloquer.
- **Retour arrière non vérifié.** Le script annonçait « revenu sur vX » sans
  sonder. Si la version précédente était cassée elle aussi, le journal disait
  que tout allait bien alors que le service était à terre. Le retour arrière se
  vérifie maintenant, et dit clairement quand il échoue.
- **Exécutions concurrentes.** Le timer et un déploiement manuel pouvaient se
  croiser : constaté en recette, deux exécutions à 14 secondes d'intervalle. La
  seconde a lu le lien `current` après la bascule de la première, a pris la
  version cassée pour « la précédente », et y est « revenue ». Un verrou
  garantit une seule opération à la fois, déploiement et retour arrière
  compris — c'est indispensable puisque le déploiement manuel est la commande
  du jour J.

- **La sonde `/health` interroge la base.** Elle répondait `"ok"` sans jamais
  l'ouvrir : quatre workers démarrés sur une base sans tables passaient pour un
  déploiement réussi, alors que chaque scan renvoyait 500. Elle répond
  désormais **503 `degraded`**, ce qui déclenche le retour arrière.
- **Verrou de schéma : un orphelin ne bloque plus les démarrages.** Un processus
  tué entre la prise et la libération laissait la ligne en base. Le délai
  d'expiration de 60 s ne suffisait pas — `RestartSec=5s` fait toujours
  redémarrer le service à l'intérieur de ce délai. La question posée n'est plus
  « le verrou est-il vieux » mais « le schéma est-il prêt ».
- `_rendre_verrou()` supprimait le verrou de n'importe qui, y compris celui,
  tout frais, du processus qui venait de le lui voler.
- **L'archive de release ne contenait pas l'application.** Le script copiait
  `climb_contest` — un nom qui n'a jamais existé — et un `|| true` avalait
  l'échec. Le premier tag portant le vrai backend aurait produit une archive
  sans une ligne de code, et gunicorn serait mort au démarrage. Une vérification
  refuse désormais de publier une archive sans application.
- Un corps JSON qui n'est pas un objet (`[1,2]`, `"x"`, `42`) donnait **500** sur
  les routes de juge. Il donne 400.
- La journalisation applicative n'écrivait nulle part : le logger racine est à
  `WARNING` sans destination, et le service ne passe aucun niveau. La ligne qui
  doit décider du passage en mode strict de la clé d'API était donc muette.

### Modifié

- Le journal ne double plus chaque ligne sous systemd.

## [0.1.0] — 2026-08-28

Première release. Elle ne contient **aucun backend** : son seul but est de
valider la chaîne de livraison de bout en bout avant qu'il y ait quelque chose à
livrer — spec 001, itération 3.

### Ajouté

- Point d'entrée `wsgi.py` avec une route `/health` qui renvoie la **version
  déployée**. L'agent de déploiement vérifie ainsi que le service répond *avec
  la version qu'il vient d'installer*, et pas seulement qu'il répond.
- Service systemd `climbcontest` : gunicorn, 4 workers × 4 threads, durci
  (`ProtectSystem=strict`, écriture limitée à `shared/`).
- Agent de tirage `climbcontest-deploy` : lit la dernière release GitHub,
  **vérifie l'empreinte SHA-256**, construit l'environnement Python dans la
  release, bascule un lien symbolique, sonde, et **revient en arrière tout seul**
  si la nouvelle version ne répond pas.
- `climbcontest-rollback` : retour arrière manuel instantané, pour corriger sous
  pression un jour de compétition.
- `deployment/install.sh` : pose le socle sur une VM neuve, de façon idempotente.

### Sécurité

- Le compte de service n'a le droit de redémarrer que `climbcontest`, via une
  règle `sudoers` limitée à ce seul service.
- Les données et les secrets vivent dans `shared/`, hors des releases : un
  déploiement ou un retour arrière ne peut pas les toucher.

[Non publié]: https://github.com/computingify/climbcontest-core/compare/v0.12.0...HEAD
[0.12.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.12.0
[0.11.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.11.0
[0.10.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.10.0
[0.6.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.6.0
[0.5.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.5.1
[0.5.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.5.0
[0.4.2]: https://github.com/computingify/climbcontest-core/releases/tag/v0.4.2
[0.4.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.4.1
[0.4.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.4.0
[0.3.4]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.4
[0.3.3]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.3
[0.3.2]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.2
[0.3.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.1
[0.3.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.3.0
[0.2.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.2.1
[0.2.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.2.0
[0.1.2]: https://github.com/computingify/climbcontest-core/releases/tag/v0.1.2
[0.1.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.1.0
