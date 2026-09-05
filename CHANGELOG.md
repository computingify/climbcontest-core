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

- **Une catégorie ne peut plus être qu'une catégorie FFME** (spec 045). Le
  champ libre disparaît des trois endroits où l'on en choisit une : le
  formulaire d'ajout, la ligne ouverte au crayon, et la salle d'attente
  HelloAsso. La liste est celle du **§5.4 des Règles de participation
  2025-2026** — U9 à U21, Sénior, Vétéran — soit dix-huit libellés, les
  Vétérans 1 et 2 fusionnés comme le règlement le prévoit lui-même.

  **C'est la troisième tentative sur le même défaut, et la première qui ferme
  la porte.** La [013](specs/013-console-saisie-guidee/) avait mis des listes
  déroulantes, la [008](specs/008-helloasso-import/) avait étendu le formatage
  à toutes les sources — et le « U13 M » mesuré en production le 30/08 était
  toujours là, son grimpeur toujours seul dans un classement d'une personne.
  La liste se **déduisait des données** : elle proposait donc « U13 M » avec
  les autres, et gardait un « ＋ Autre… » pour en inventer d'autres.

  Ce qui arrive écrit de travers est **rattaché à l'entrée** : la casse,
  l'espace manquant, le **U manquant** (« 13 F »), le « M » pour « H », les
  accents, l'ordre inversé, « V2 » pour « Vétéran 2 ». Ce qu'on ne sait pas
  lire — « Poussin », un U12 qui n'existe pas — est importé **tel quel** et
  signalé dans le rapport d'import : ni ligne refusée, ni catégorie vidée. On
  rattache ou on laisse tel quel, jamais à moitié.

  Le rattachement est **dans `formatage.categorie()`**, le passage obligé de
  toute écriture depuis la 008 — et non dans une fonction à côté qu'il aurait
  fallu penser à appeler. Conséquence : le classeur Google peut continuer
  d'écrire « U13 M », le prochain import posera « U13 H ».

- **Le « U13 M » déjà en base se rattrape d'un clic**, dans l'écran Catégories,
  devant son aperçu — le motif d'« Appliquer le barème à tous ». Ce qui n'a pas
  de correspondance est montré mais pas actionnable : on ne choisit pas à la
  place de quelqu'un ce que « Poussin » voulait dire. Les téléphones des juges
  rechargent leur catalogue, sans quoi ils garderaient l'ancienne catégorie
  toute la compétition.

- **Une édition qui vient d'être créée connaît ses catégories.** Le barème se
  déduisait des inscrits, des circuits et des catégories déclarées : une
  édition neuve n'a aucun des trois, et son écran Catégories s'ouvrait
  entièrement **vide**. Il retombe désormais sur les neuf catégories
  officielles, dont les années se calculent depuis la date de l'édition.
  ⚠️ Sur le vide et seulement sur le vide : une édition qui annonce U11-U15
  garde trois tranches, et « le plus petit Under l'emporte » continue d'y
  ranger un grimpeur de 12 ans en U15.

### Modifié

- **L'écran Catégories ne fait plus qu'un seul tableau** (spec 045). Le barème
  et « les catégories de cette édition » parlaient des mêmes neuf lignes dans
  deux cartes : à gauche ce que la règle FFME calcule, au milieu le compte
  d'inscrits, à droite deux **interrupteurs** — F et H — là où il y avait un
  champ « catégories séparées par des virgules ». Une catégorie que l'édition
  ne fait pas grimper est grisée : ses années disent ce qu'elle *deviendrait*,
  pas ce qui s'applique.

  Les listes déroulantes s'ouvrent sur la **catégorie en cours** et non en tête
  de liste — le geste du `<select>` natif. Un participant qui porte encore une
  valeur hors liste la garde **en tête de sa propre ligne**, marquée : sans ça,
  ouvrir son crayon pour corriger son club changerait sa catégorie en silence,
  un `<select>` qui ne contient pas sa valeur courante en choisissant une autre
  tout seul.

- **Le dossard ne se change plus depuis la console** (spec 008). Il est imprimé
  sur le QR code déjà distribué, et le classeur Google porte le sien : deux
  écritures d'un même numéro finissaient toujours par se contredire. Le crayon
  affiche donc le dossard sans le laisser saisir, la route de réaffectation est
  **supprimée**, et la fonction métier qui la servait avec elle — une route
  neutralisée finit toujours par être rebranchée « puisqu'elle est là ».

### Corrigé

- **La console garde la vue qu'on regarde quand la page se recharge.** Un F5 —
  ou un onglet que le navigateur réveille après l'avoir mis en veille —
  ramenait toujours sur « Participants », quelle que soit la vue ouverte : le
  jour J, la console reste des heures sur les Réussites ou les Téléphones, et
  retrouver l'accueil à chaque rechargement fait refaire trois clics. La vue
  vit désormais dans l'adresse (`/console#telephones`), ce qui rend au passage
  le bouton **Retour** utile — il quittait la console — et permet d'envoyer un
  lien vers un écran précis. `/console` reste l'accueil, sans dièse. Une
  adresse ne rouvre pas ce que le tiroir ferme : `#classeur` chez un compte
  sans le rôle administrateur retombe sur l'accueil, comme un dièse inconnu.
- **Le message de retour du consentement Google ne s'efface plus aussitôt
  dit.** Il était posé puis emporté dans la même foulée par le changement
  d'écran, qui remet la zone de message à zéro : on revenait de chez Google sur
  un classeur muet, sans savoir si le consentement avait abouti.

## [0.20.0] — 2026-09-05

### Ajouté

- **La page de résultats ne s'indexe plus, et dit ce qu'elle publie**
  (spec 043). Elle nomme des grimpeurs, dont une majorité de mineurs. Cet
  affichage est légitime — c'est l'objet d'une compétition, et le micro les
  nomme aussi — mais le micro s'éteint à 18 h et ne se cherche pas par nom,
  alors qu'un moteur de recherche garde. Trois consignes qui ne se remplacent
  pas : `robots.txt` (« ne viens pas »), une balise `noindex` sur les pages
  HTML (« ne garde pas »), et un en-tête `X-Robots-Tag` sur `/api/public/*`,
  seul canal d'une réponse JSON — **y compris ses réponses d'erreur**, qui sont
  exactement les adresses qu'un robot fabrique en balayant. Le tout est posé
  dans l'application et non dans le proxy : la configuration de `edge` est
  recopiée à la main, elle dérive, et aucun test ne la lit.
- **Une mention discrète en pied de la page de résultats**, vers une page
  `/confidentialite` qui dit ce qui est publié, sur quelle base, et comment s'y
  opposer. Absente du mode mur : l'écran de la salle est accroché en hauteur,
  personne n'y cliquera. Elle se place à la fin de `#defile` et non après
  `<main>`, dont la boîte s'arrête bien avant le bas de la page.
- **Le droit d'opposition, exerçable depuis la console** (art. 21 RGPD). Un
  interrupteur « Anonymisé » dans la liste des participants : la ligne **reste**
  au classement, avec le même rang et le même score, et son nom devient
  « Dossard 42 ». La retirer décalerait tous les suivants — et un rang qui saute
  de 3 à 5 est une information sur celui qui manque. La console, elle, continue
  d'afficher le vrai nom : c'est elle qui sert à retrouver la personne au
  téléphone. L'archive fige le nom **réel** : elle n'est servie qu'après
  connexion d'un organisateur. On fige complet, on rend anonymisé.
- **Un registre des traitements** (`docs/registre-des-traitements.md`),
  obligatoire même pour une petite association (art. 30).



- **Les inscriptions HelloAsso arrivent toutes seules** (spec 008). La
  plateforme d'inscription du club alimente désormais une **salle d'attente**
  dans la console : c'est elle qui décide si un participant est créé, jamais le
  réseau. Trois piles dans l'ordre où on les traite — *à trancher*, *à
  imprimer*, *faites* — sur un écran rafraîchi toutes les trente secondes,
  qu'on laisse ouvert pendant la compétition. Une pastille dans le bandeau
  compte ce qui attend, depuis n'importe quel écran.

  **La catégorie se calcule.** « U » veut dire *under* : U13, ce sont les moins
  de 13 ans, et c'est le plus petit Under qui l'emporte. L'année de référence
  est celle où **finit** la saison FFME — septembre à août — ce qui est
  exactement ce qui fait qu'un grimpeur démarre l'année dans une catégorie et y
  reste. Le barème ne se saisit plus : il se déduit de la date de la compétition
  et des catégories de l'édition, et un écran **Catégories** permet de
  l'appliquer à tous les inscrits, avec son aperçu avant / après.

  **Deux mécanismes distincts, et il ne faut pas les confondre.** Ne pas
  réimporter tient à une contrainte SQL sur l'**article** HelloAsso ; rapprocher
  une personne déjà connue se fait sur nom + prénom + club. Le numéro de
  commande, lui, ne peut pas servir de clé anti-doublon : une commande porte
  souvent **deux enfants**, et s'en servir perdrait le second.

  Le relevé ne garde **rien du payeur** — ni nom, ni courriel, ni adresse — et
  seulement l'**année** de naissance de l'inscrit, qui est tout ce que la règle
  demande. Ce sont des mineurs.

- **La liste des participants change de geste** (spec 008). Une colonne
  **Source** dit d'où vient chacun — `G` classeur Google, `H` HelloAsso, `M`
  saisie au guichet — et deux pastilles sur une ligne veulent dire que le
  rapprochement a fait son travail. Un **crayon** ouvre la ligne sur place, avec
  des listes déroulantes qui savent créer une valeur. La **sélection par cases**
  remplace la tuile « Imprimer les fiches » : on filtre par catégorie, on coche,
  on imprime. Le formulaire d'ajout apprend l'**année de naissance**, et l'année
  et la catégorie se répondent l'une l'autre.

- **Un seul formatage, et plus de doublons** (spec 008). Le formatage
  s'applique désormais à **toutes** les sources, l'import du classeur compris —
  la spec 013 l'en tenait à l'écart, et c'est ce qui fabriquait des doublons :
  « ANNONAY ESCALADE » importé et « annonay escalade » tapé au guichet étaient
  deux clubs. Quand un club existe déjà sous une forme, **c'est la sienne qui
  fait référence**, quelle que soit la façon dont on vient de l'écrire.

  Créer quelqu'un qui porte le même nom **et** le même club est refusé, avec sa
  fiche à l'écran pour la reprendre d'un clic. Même nom mais club différent
  reste possible — deux « Martin Lea » existent vraiment — et se signale. Une
  carte **Doublons** paraît quand la base en porte déjà, et laisse choisir
  laquelle des deux fiches garde son dossard : c'est celui qui est déjà imprimé.

- **Les catégories d'une édition peuvent se déclarer** (spec 008). Le barème se
  déduisait des inscrits et des circuits — et les circuits ne viennent que de
  l'import du classeur Google, qui est temporaire et finira par disparaître. Une
  édition alimentée par HelloAsso seul n'aurait donc eu aucune catégorie
  calculable au premier relevé. Une ligne dans l'écran **Catégories** suffit
  désormais à les annoncer, et le calcul cesse de dépendre du classeur.

- **D'où viennent les inscrits se règle** (spec 008). Dans **Général**, trois
  positions : le classeur Google seul — ce qu'on fait aujourd'hui, et le défaut
  —, HelloAsso seul, ou les deux. Tant que HelloAsso n'est pas choisi,
  **aucun** écran ni aucune pastille HelloAsso n'apparaît dans la console.

  Le réglage porte sur les **participants** et sur rien d'autre : le miroir
  continue d'écrire les réussites dans le classeur, et l'import continue d'y
  lire les blocs et les circuits. Le classeur peut cesser de fournir les
  inscrits tout en restant la carte du mur.

  **Décocher n'efface rien** : la clé, le formulaire et la correspondance
  reviennent tels quels à la réactivation. Pour effacer, il y a « Débrancher »,
  qui dit ce qu'il fait.

- **Relier HelloAsso tient en deux champs** (spec 008). On colle l'identifiant
  et le secret, et la console **trouve l'association toute seule** — son nom
  s'affiche aussitôt, avec la liste de ses formulaires. Plus de nom court à
  taper, donc plus de faute de frappe dont le seul symptôme aurait été « aucun
  formulaire trouvé ».

  Un bouton **Tester** répond à « est-ce que ça marche ? » par des faits qu'on
  reconnaît : le nom du club, le nombre de formulaires, et le nombre
  d'inscriptions vues sur celui qui est choisi. Un verdict qui dirait seulement
  « relié » ne prouverait rien — il pourrait désigner la mauvaise association.

- **L'import HelloAsso devine ses champs** (spec 008). Choisir le formulaire lit
  un échantillon et reconnaît tout seul l'année de naissance, le genre et le
  club — par le nom du champ, et à défaut **par ses réponses** : un champ dont
  toutes les réponses sont « Fille » ou « Garçon » est un champ de genre, quel
  que soit son intitulé. « Fille », « F », « Féminin », « Girl » sont reconnus
  d'origine. Rien n'est deviné en silence : la console dit ce qu'elle a trouvé,
  et liste les réponses qu'elle n'a pas su ranger.

- **L'application juge choisit son thème** (spec 040). Trois pastilles dans les
  Réglages — *Système*, *Clair*, *Sombre*. « Système » reste la position de
  départ : rien ne change pour un juge qui n'y touche pas. Le choix est appliqué
  avant que l'écran ne se peigne, donc sans clignotement au lancement, et il
  survit à la fermeture de l'application.

- **Les versions se voient, et le catalogue se force** (spec 030). Tout était
  déjà versionné — le tag git dans un fichier `VERSION` lu par `/health`, le
  numéro de catalogue qui décide du `304` — et **rien n'était lisible**. Un
  téléphone en retard était indiscernable d'un téléphone à jour, et le juge
  n'avait aucun geste à sa portée.

  Sur le téléphone, l'écran **Réglages** gagne deux sections : le **catalogue**
  (numéro local, verdict, contenu, âge) avec un bouton **« Retélécharger
  maintenant »**, et l'**application** (version, verdict) avec un bouton
  **« Mettre à jour et redémarrer »** qui n'apparaît que si la coquille est en
  retard. La version affichée est celle de la **coquille en cache** — le code
  qui tourne vraiment, pas celui que le serveur sert : afficher le second
  dirait « à jour » à un téléphone qui ne l'est pas.

  Dans la console, la version et le numéro de catalogue en **pied de tiroir**,
  sur tous les écrans ; une carte **« Versions en circulation »** ; et dans le
  tableau des téléphones **deux colonnes** disant, par poste, quelle version et
  quel catalogue il porte. Les téléphones qui se sont annoncés **sans rien
  envoyer** y figurent aussi : c'est le contrôle du matin, avant la première
  grimpe.

  Le téléphone s'annonce sur la requête de catalogue qu'il fait déjà — trois
  en-têtes facultatifs, **aucune requête supplémentaire**. Le serveur répond
  avec `X-Server-Version`, sur le `200` **comme sur le `304`**, qui est le cas
  majoritaire le jour J.

  Le **retard normal se distingue de la panne** : redessiner le mur renumérote
  toutes les éditions d'un coup, donc tous les téléphones passent à l'ambre en
  même temps. La console le dit en ocre, et **distingue deux populations** —
  écran allumé l'application rafraîchit toutes les trente secondes, écran
  éteint elle ne fait rien du tout. La phrase donne donc le geste qui débloque
  un téléphone en veille (rallumer son écran) au lieu de promettre qu'il n'y en
  a pas.

- **Le module `climbcontest/version.py`.** Le tag git était lu par une fonction
  privée de `routes/sante.py` : trois appelants en avaient besoin, aucun ne
  pouvait l'atteindre sans importer une route.

### Modifié

- **Le dossard ne se change plus depuis la console** (spec 008). Il est imprimé
  sur le QR code déjà distribué, et le classeur Google porte le sien : deux
  écritures d'un même numéro finissaient toujours par se contredire. Le crayon
  affiche donc le dossard sans le laisser saisir, la route de réaffectation est
  **supprimée**, et la fonction métier qui la servait avec elle — une route
  neutralisée finit toujours par être rebranchée « puisqu'elle est là ».

  Ce qui disparaît avec : donner le dossard d'un absent à un arrivant de
  dernière minute. C'était une économie de papier, jamais une nécessité —
  l'ajout attribue le premier numéro libre, et la console imprime la fiche.


- **Les Réglages de l'application juge, au pouce** (spec 042) — deux retouches
  du même écran.
  - **La demande de scan s'éteint quand elle n'a plus lieu d'être.** Un
    téléphone qui porte déjà un nom affichait toujours « Scanner le QR de mon
    poste » en aplat bleu pleine largeur, avec son explication dessous. La
    demande s'en va ; le **geste reste**, en lien discret à la place de « Voir
    mes scans » — un téléphone change parfois de table en cours de journée, et
    il faut pouvoir rescanner sans vider le champ d'abord. Vider le nom ramène
    la demande. Le déclencheur est le **nom**, pas la façon dont il est arrivé :
    un nom scanné éteint la demande comme un nom tapé.
  - **La case à cocher « Garder le grimpeur entre deux blocs » devient un
    interrupteur**, aux cotes de celui d'iOS et d'Android. C'était la seule de
    l'application. La case native est conservée sous le visuel : le clavier, le
    focus et le lecteur d'écran ne perdent rien, et `role="switch"` la fait
    annoncer « interrupteur, activé ».

  Le cache du service worker passe en **v10** : la coquille porte le gabarit
  `/juge`, donc tout le CSS. Sans ce changement de nom, un téléphone déjà
  installé aurait rouvert l'ancienne page sans que rien ne le dise.

- **La documentation dit l'état réel** — trois textes décrivaient encore un
  système qui n'existe plus.
  - Le **runbook de compétition** faisait allumer puis éteindre la VM, et
    annonçait qu'« un timer s'en charge seul en 2 minutes ». La VM tourne en
    permanence depuis le 03/09 et **plus rien ne s'installe tout seul** : une
    release publiée attend qu'on clique dans la console. Un jour de compétition,
    ces deux phrases coûtaient cher.
  - La **spec 001** portait tout l'argumentaire du régime intermittent. Il a été
    **retiré**, pas seulement signalé caduc : laissé en place, il se relit comme
    un raisonnement complet et se ré-applique. Ce qu'il en reste tient dans une
    section « Historique », avec les deux autres décisions défaites depuis
    (la copie de base toutes les dix minutes, le minuteur de déploiement).
  - L'**index des specs** marquait « codée, en attente de relecture » vingt
    specs qui tournent en production depuis des jours. Chaque ligne porte
    maintenant la version qui l'a livrée.
  - Ajouté au passage : **le trou du numéro 030** est expliqué là où on le
    remarque. La spec `030-versions-visibles` existe, codée et testée, mais
    seulement sur une branche locale jamais poussée.
- **L'application juge prend la matière imprimée de « Plein Jour »** (spec 041,
  qui referme la spec 035). La carte du bloc scanné passe d'un simple trait à un
  **aplat** de la couleur de son circuit, cerclé d'un liseré d'encre ; la
  pastille du bloc prend le même liseré — la matière des étiquettes collées sous
  les blocs. Le bouton « Envoyer » gagne un liseré et une ombre, et le bouton
  désactivé passe en trait **pointillé** : un emplacement qui attend, plus une
  surface pleine. Tout est pris sur l'encre du thème, si bien que la matière
  devient de la craie en thème sombre au lieu de disparaître.
- **Le circuit « Noir » garde sa carte en papier.** C'est le seul dont la teinte
  est déjà l'encre : sa carte teintée virait au gris quand toutes les autres
  prennent leur couleur, et le liseré de sa pastille se confondait avec l'aplat.
- **Le job de CI passe de 4 min 39 à ~1 min 10**, et son étape « Tests » de
  4 min 15 à **43 s** — mesuré sur le runner, pas extrapolé. En
  local : 2 min 26 → 45 s **en série**, 13 s en parallèle. Aucun test retiré,
  dix-sept ajoutés (1 872, tous verts). Le parallélisme est un multiplicateur ;
  les deux tiers du gain viennent du travail supprimé.
  - **Un tiers de la suite dérivait des mots de passe.** `scrypt` est lent à
    dessein (54 ms), et chaque fixture de connexion en payait deux — création
    du compte, puis vérification — soit ~105 ms, quatre cents fois. La
    configuration de test dérive désormais au minimum. **Le défaut reste
    `scrypt` partout ailleurs**, et aucune variable d'environnement ne peut
    l'affaiblir ; les deux tests dont le *coût* est le sujet redemandent la
    vraie méthode. `tests/test_hachage.py` échoue si l'allégement déborde du
    test.
  - **Une application Flask était rebâtie à chaque test** (11,8 ms × 1 200) :
    Werkzeug y recompilait ses soixante-sept règles de routage, ce qui pesait
    78 % du coût. Elle est construite une fois ; la base, la configuration et
    la classe de client sont remises à neuf avant chaque test. Deux gardes
    tiennent l'isolement — un refus de sortie si un test modifie l'application
    partagée, et `tests/test_isolation.py`, qui salit puis vérifie **dans
    n'importe quel ordre**.
  - **Le test le plus cher de la suite testait le harnais** : 7,5 s, dont 5 s
    passées à regarder gunicorn renoncer à prendre un port occupé. Le harnais
    vérifie maintenant que le port est libre *avant* de lancer gunicorn — un
    vrai gain aussi hors des tests — et le test tombe à 0,6 s.
  - **Une sonde navigateur dormait 2,4 s pour constater qu'il ne se passait
    rien.** C'était lent *et* faux : sur une machine lente, la feuille aurait
    pu s'ouvrir après le réveil sans que le test la voie. Le harnais attend
    désormais une condition — plus aucune requête en vol, puis deux
    rafraîchissements d'écran — et le test passe de 2,5 s à 0,13 s.
  - **Deux serveurs de test se fermaient en 0,5 s chacun** : `serve_forever`
    sonde son drapeau d'arrêt à cet intervalle par défaut, une attente logée
    dans le *teardown* où personne ne lit les durées.
  - **Les tests E2E ne relancent plus un interpréteur Python par test** pour
    peupler leur base : elle est bâtie une fois, puis copiée.
  - **Quatre parcours navigateur pour quatre sondes** de l'écran Réglages du
    juge : quatre démarrages de l'application pour rejouer chaque fois la même
    ouverture. Un seul parcours, 4,8 s → 2,3 s. Les sondes restent quatre
    textes séparés — deux PR qui en touchent deux différentes ne se disputent
    toujours rien — et chacune tourne dans son propre `try` : une sonde qui
    casse ne fait pas tomber les trois autres.
  - **Le navigateur de la CI change** : `/usr/bin/chromium` est un paquet
    confiné dont le premier lancement coûte **9,6 à 22,2 s** — le même geste,
    du simple au double, mesuré sur cinq passages. Le Chrome de la même image
    est un paquet ordinaire : **7,2 s**, et sans cette variance qui a fait
    échouer deux jobs sur le budget par test. Même moteur, donc rien ne change
    de ce que les tests mesurent — une cascade CSS, un `display` calculé. Une
    étape de CI nomme désormais le binaire retenu et chronomètre son démarrage :
    l'en-tête de pytest, qui l'aurait dit, est masqué par le `-q` de `addopts`.
    ⚠️ Cette étape paie le premier lancement, si bien qu'une part du gain de
    l'étape « Tests » est un **déplacement** — le job entier, lui, ne ment pas.
  - **Ce premier lancement était facturé au premier test navigateur** par ordre
    alphabétique — le même geste, du simple au double selon la charge — et
    ce prix était facturé au premier test navigateur par ordre alphabétique —
    qui affichait 20 s en CI contre 0,13 s sur le Mac, et faisait échouer le
    budget par test en accusant un innocent. Il est rendu à un test dont c'est
    le sujet, placé en tête du groupe ; les autres trouvent un navigateur
    chaud. Le harnais nomme désormais ce démarrage dans son avertissement : il
    se produisait *avant* le chronomètre, donc rien ne le voyait.
  - **La suite tourne en parallèle par défaut** (`pytest-xdist`, `-n logical
    --dist loadgroup`). `pytest -n 0` revient à l'exécution en série.
  - **Un seul chromium pour toute l'exécution**, au lieu d'un par fichier.
    Chaque parcours ouvre un **contexte isolé** — cookies, `localStorage` et
    service workers propres, comme un profil neuf, mais en 2 à 5 ms au lieu de
    300. Les tests navigateur sont regroupés sur un même worker pour que ce
    « un seul » reste vrai en parallèle.
  - `test_navigateur_fiche.py` **rejoint le harnais partagé** : il portait sa
    propre copie de `piloter`, donc son propre chromium.

### Corrigé

- **Un worker gunicorn sur quatre pouvait mourir au démarrage.**
  `PRAGMA busy_timeout` était posé **après** `PRAGMA journal_mode=WAL`. Or le
  passage en WAL demande un verrou exclusif : quand les quatre workers démarrent
  ensemble sur une base neuve, celui qui arrive pendant la transaction de schéma
  d'un autre échouait tout de suite sur « database is locked » — son propre
  garde-fou n'existait pas encore. Une attente ne protège que ce qui vient après
  elle.

  Le symptôme était un rouge intermittent de la CI. Le vrai risque était le
  démarrage du service sur la VM, après une coupure : c'est exactement le
  moment où quatre workers ouvrent une base ensemble. Mesuré, 30 puis 70
  exécutions du test du verrou orphelin : **1 échec sur 30**, puis **0 sur 70**.
  Un test verrouille désormais l'ordre, et il rougit si on l'inverse.

- **L'import du classeur pouvait fabriquer un doublon, ou pire.** Il rapprochait
  une ligne par son **seul dossard**. Deux conséquences, reproduites par un test
  avant d'être corrigées : un participant dont le numéro avait changé de main
  n'était plus retrouvé et sa fiche était **recréée** ; et si son ancien numéro
  était désormais porté par quelqu'un d'autre, l'import **écrasait le nom de ce
  quelqu'un d'autre**, dont les réussites étaient déjà enregistrées.

  Le dossard reste la première clé — c'est le cas courant. Mais il ne conclut
  plus seul : l'**identité** le confirme, et prend le relais quand il ne dit
  rien. C'est la comparaison du rapprochement HelloAsso, pas une seconde écrite
  à côté. Le classeur ne réécrit plus que les fiches **qu'il possède**, et
  jamais une qui porte des réussites.

- **Une correction faite au crayon survit à l'import suivant.** Un champ modifié
  dans la console est marqué, et le classeur ne le réécrit plus — « la console
  gagne, définitivement ». La protection est **par champ** : corriger le club ne
  fige pas la catégorie. La liste teinte les cellules protégées, et le rapport
  d'import compte les corrections conservées plutôt que de les taire.

- **Le harnais des tests navigateur pouvait rendre un verdict qu'il n'avait pas
  produit.** `piloter` attend que le pilote poste son relevé, mais il tenait
  pour acquis qu'on lui remettait un verdict vierge sans jamais l'écrire : le
  pari ne tenait qu'à la portée des fixtures. Le jour où une fixture partagée
  aurait servi deux appels, le second aurait trouvé le relevé du premier, rendu
  aussitôt, et **n'aurait lancé aucun navigateur** — les tests suivants passant
  au vert sur les mesures du parcours précédent. Un test qui ne mesure plus rien
  et qui ne le dit pas. `piloter` pose désormais lui-même l'état dont il dépend,
  et un test le prouve en le lui reprenant.


- **Le pied du tiroir de la console disait la version sans le catalogue** tant
  qu'on n'avait pas ouvert l'écran « Téléphones » (spec 030, critère A9). Le
  numéro vient de `/admin/versions`, et cette route n'était appelée que par cet
  écran-là : un organisateur qui ouvrait la console et restait sur
  « Participants » lisait un pied à moitié rempli, sans que rien ne lui dise où
  aller chercher le reste. La console la demande maintenant **à l'ouverture** —
  une requête de plus, ~200 octets — et l'écran « Téléphones » continue de la
  rafraîchir, donc le numéro ne vieillit pas.

  Trouvé en reprenant les dix-huit critères d'acceptation de la spec un par un
  avant de publier. Les dix-sept autres étaient tenus ; **sept ne l'étaient que
  par un relevé fait à la main**, sans qu'aucun test ne touche les écrans
  concernés. Ils en ont un désormais : les deux sections des Réglages du juge,
  ce que le bouton « Retélécharger maintenant » envoie **vraiment** (observé
  côté serveur : ni `If-None-Match`, ni chaîne de requête), son refus propre
  hors ligne, le bouton de mise à jour qui n'apparaît que si la coquille est en
  retard, le pied du tiroir, et la phrase du rattrapage qui doit **nommer le
  geste** plutôt que promettre que ça se répare tout seul.

- Le circuit **« Noir »** suivait le thème du téléphone et non celui qui est
  réellement affiché : un juge qui imposait le sombre sur un téléphone en clair
  aurait vu un aplat presque noir sur un fond presque noir, sans savoir s'il
  avait scanné (spec 040).

⚠️ La coquille hors-ligne de la PWA passe en `v8` : sur un téléphone déjà
installé, le réglage n'apparaît qu'après avoir **fermé et rouvert**
l'application.


- **Un test passait en héritant du voisin.**
  `test_la_garde_et_la_confirmation_sont_partagees_avec_relier` ne demandait
  pas la fixture `classeur` : il lisait le registre laissé par un test
  précédent. Lancé seul, il échouait déjà sur `master` — le parallélisme n'a
  fait que le montrer. La fixture remet désormais le registre à `None` en
  sortant, si bien que l'oubli échoue **toujours**, au lieu de dépendre de
  l'ordre de passage.
- **`piloter` remet le verdict à zéro** avant chaque parcours. Sans ça, un
  second appel sur le même dictionnaire trouvait la valeur du premier, rendait
  un verdict périmé, n'ouvrait aucun navigateur — et le test passait au vert
  sur les mesures du parcours précédent, sans rien dire.
- **La pulsation du bouton « Envoyer » effaçait son ombre** deux fois par
  seconde : `box-shadow` est une propriété unique, et les images-clés du souffle
  la réécrivaient entièrement. Elles reportent désormais l'ombre et ne font
  varier que la lueur du circuit.
- **Les rouges intermittents des tests navigateur avaient une cause, et elle
  est réparée.** Ce n'était pas un aléa de machine : deux fichiers relançaient
  un navigateur **par test** pour rejouer exactement le même parcours — trente
  fois pour `test_navigateur_juge_claire.py`, treize pour celui du thème au
  choix. Chaque démarrage coûte de 0,3 s à chaud à 7,2 s au premier lancement,
  bien plus sur une machine chargée : le fichier finissait par dépasser le
  délai, sur un test différent à chaque exécution, et le rouge se lisait comme
  un contraste en faute alors que les valeurs mesurées étaient bonnes. Un seul
  navigateur suffit : 19,2 s → 1,6 s pour l'un, plusieurs minutes → 1,5 s pour
  l'autre. Aucun délai n'a été allongé — on a supprimé les attentes, pas
  rallongé la dernière.
- **Le numéro de la coquille du service worker a été revendiqué trois fois par
  trois specs différentes le même jour** — deux fois `v7`, deux fois `v8`. Ce
  n'est pas cosmétique : le navigateur ne jette une ancienne coquille que si le
  **nom** change, donc deux specs sous un même numéro laissent les téléphones
  déjà installés sur l'ancienne version de l'une des deux, sans rien casser de
  visible. Un test échoue désormais si le nom du cache ne porte pas le plus haut
  numéro que son propre journal documente — la trace d'une fusion résolue à
  moitié.
- **Une variable de couleur avait survécu à son dernier lecteur.**
  `--trait-circuit` ne servait plus une fois la carte du bloc cerclée d'encre ;
  elle est revenue par la fusion avec le thème au choix, qui avait recopié le
  bloc sombre avant sa suppression — sans que git signale quoi que ce soit. Une
  variable sans lecteur ment à la prochaine lecture : un test échoue désormais
  dès qu'il en reste une.

## [0.19.0] — 2026-09-03

### Ajouté

- **La pastille du compteur de zone se remplit de vert** à hauteur de
  l'avancement, sur le plan du mur de la fiche (spec 036 § 2 ter). « Je veux
  que le truc avec le nombre de blocs restant se remplisse de vert en fonction
  de l'avancement. » Une zone à 1 bloc sur 4 porte donc « 1/4 » sur une pastille
  verte au quart, et une zone terminée une pastille pleine. Le compte est le
  même que celui du chiffre — les deux dérivent d'une seule fonction, ils ne
  peuvent pas se contredire — et le vert suit une réussite **en direct**, sans
  que le mur soit redessiné.
  - Le vert est un rectangle franc **découpé dans la forme du socle** : il en
    épouse le bord arrondi à gauche et se coupe net à droite. On lit un
    **niveau** ; arrondi de son côté, il ferait une petite pastille dans la
    grande, donc deux objets.
  - **L'ovale s'élargit à 1,6 fois la lettre** — et uniquement en largeur : sa
    hauteur et le corps du chiffre ne bougent pas. Un vert qui remplit un rond
    ne dit pas une proportion. Effet de bord bienvenu : « 12/15 » tient
    maintenant à sa taille pleine au lieu de rétrécir.
  - **La lettre de la zone monte**, et la pastille se pose plus haut : les trois
    espaces du pan — au-dessus de la lettre, entre la lettre et la pastille,
    sous la pastille — deviennent **égaux**. Ce n'était pas un problème de
    place mais un chevauchement : le halo de la lettre recouvrait la pastille de
    près d'une unité de plan. Sous elle, il ne restait que 0,009 × taille — un
    cinquième de pixel sur un téléphone.
  - **Le chiffre d'une zone terminée ne vire plus au vert** : sur une pastille
    pleine, vert sur vert ne se lit pas. C'est le remplissage qui dit
    « terminée ».
  - **Le cadre de la zone ne change pas** : il garde son tout-ou-rien et dit
    « terminée », rien d'autre. Une première version faisait l'inverse — le
    cadre épaissi qui se remplissait — et elle a été retirée en entier après
    l'avoir regardée à l'écran.

### Modifié

- **L'application juge s'ouvre en clair** (spec 039). Son fond était sombre **en
  dur** : rien ne regardait `prefers-color-scheme`, et un bénévole qui ouvrait
  l'application en plein jour, dans une salle à baie vitrée, lisait un écran
  noir sans l'avoir demandé — luminosité poussée à fond, donc batterie. Le clair
  devient le **défaut** ; le sombre reste, **inchangé au point près**, sous la
  requête media. **Aucun réglage dans l'application** : le système décide, comme
  sur la console depuis la spec 021.
  ⚠️ Le circuit **« Noir »** prend désormais l'encre du thème — presque noir sur
  le papier, craie sur l'ardoise. La craie n'était pas un choix de couleur,
  c'était une rustine du fond sombre, et elle ne se voit pas davantage sur du
  papier sable. Les cinq autres circuits ne bougent pas.
  ⚠️ La coquille hors-ligne passe en **v6** : elle porte le gabarit, donc tout le
  CSS. Un téléphone déjà installé prend la nouvelle version **au lancement
  suivant** — fermer et rouvrir l'application, jamais en pleine compétition.
  ⚠️ L'**app juge Android reste sombre** : les deux clients ne se ressemblent
  plus tant qu'une spec ne l'a pas fait suivre.

## [0.18.1] — 2026-09-03
### Corrigé

- **Le bouton « Installer » de la console n'a jamais pu fonctionner**, depuis
  qu'il existe (spec 031, v0.17.0). Il répondait « Le service de déploiement n'a
  pas pu être démarré » **à tous les coups**. Découvert le 03/09 au premier vrai
  clic, en installant la 0.18.0.

  L'application lançait
  `sudo -n systemctl start --no-block climbcontest-deploy.service`. La règle
  sudoers l'autorisait mot pour mot, l'appel était correct — et il ne pouvait
  pas aboutir : `climbcontest.service` tourne avec **`NoNewPrivileges=true`**,
  qui interdit à ses processus de gagner des privilèges par un binaire
  **setuid**. `sudo` en est un. Le drapeau ne se contourne pas depuis
  l'intérieur : c'est exactement son rôle.

  ```
  $ systemd-run --uid=climbcontest -p NoNewPrivileges=yes /usr/bin/sudo -n -l
  sudo: The "no new privileges" flag is set, which prevents sudo
        from running as root.
  ```

  La vérification du 03/09 avait pourtant « rejoué le chemin exact du bouton ».
  Elle rejouait la même **commande**, depuis un shell de connexion — pas depuis
  le **contexte** durci du service. C'est tout l'écart, et il valait le bouton.

  À la place, plus aucune élévation de privilège ne traverse l'application :
  elle **écrit un fichier** (`shared/deploiement-demande`, le seul chemin que
  `ReadWritePaths` lui laisse), et une nouvelle unité
  **`climbcontest-deploy.path`** — qui, elle, appartient à root — démarre
  l'agent en le voyant changer. Le durcissement est conservé **en entier** ;
  c'est la quatrième règle sudoers, devenue sans objet, qui est retirée.

  `PathChanged` et non `PathExists`, pour deux raisons distinctes : un second
  clic réécrit le même fichier — `PathExists` ne se déclenche qu'à l'apparition,
  et le bouton n'aurait marché qu'une fois ; et une demande qui traîne
  relancerait l'agent **au démarrage de la machine**, c'est-à-dire une
  installation automatique le matin d'une compétition, exactement ce que la
  spec 031 a supprimé.

  ⚠️ **Ce que les tests d'alors prouvaient** : ils remplaçaient
  `subprocess.run` par un leurre. Ils vérifiaient qu'on **appelait** `sudo` —
  la seule chose qui, en production, ne pouvait pas marcher. Un test qui simule
  la partie qui casse ne surveille rien. Ils exercent désormais le vrai
  mécanisme sur un vrai dossier, et
  `tests/test_deploiement_sans_privileges.py` tient le contrat entre les trois
  fichiers que personne ne lit ensemble : aucun module de l'application ne
  lance de processus tant que son unité porte `NoNewPrivileges=true`, le chemin
  écrit est celui qui est surveillé, et il est sous un `ReadWritePaths`.
  Vérifié rouge sur le code d'avant.

  🔧 **Geste à faire une fois sur la VM 110** : les unités systemd ne voyagent
  pas dans une release. Poser et activer le guetteur, en root —
  `install -m 0644 climbcontest-deploy.path /etc/systemd/system/`,
  `systemctl daemon-reload`, `systemctl enable --now climbcontest-deploy.path`.
  Tant que ce n'est pas fait, le bouton dépose sa demande et rien ne l'écoute.

## [0.18.0] — 2026-09-03

### Modifié

- **La recherche de la page de résultats se déploie** au lieu d'apparaître. Un
  appui sur la loupe — qui **termine** désormais la rangée, la lecture passant
  devant — ouvre le champ **par-dessus** les commandes, sur toute la largeur.
  Un second appui, la croix ou **Échap** le referme et le vide. Sur grand écran,
  le bandeau de droite s'efface le temps de la recherche.
  ⚠️ Le réglage mémorisé « masquer la recherche » **disparaît** : le champ est
  replié tant qu'on ne le demande pas, ce qui est « masquée par défaut » sans
  rien avoir à retenir. Ouvrir la recherche est un geste, pas un réglage
  (spec 037).

### Ajouté

- **L'avancement par zone, sur le plan du mur** de la fiche du grimpeur
  (spec 036). Une zone où il a des blocs de son circuit porte « 1/4 » : blocs
  validés sur blocs de son circuit qui s'y trouvent. Le mur ne disait que « il
  t'en reste » — cinq zones allumées à l'identique se comparaient en cinq
  gestes, en touchant chacune pour lire le compteur du panneau. Une zone sans
  bloc de son circuit ne porte **rien** : l'absence est l'information, « 0/4 »
  se dit, « 0/0 » non. Un bloc **crédité** par la cascade compte comme fait,
  comme partout ailleurs sur cet écran. Le chiffre est posé sur une **pastille**
  — un socle arrondi qui le détache des six aplats de profil du plan, choisi par
  Adrien parmi quatre poses maquettées. La pastille se dimensionne sur la
  **lettre** de la zone et jamais sur son texte : c'est ce qui la borne, un
  libellé long rétrécit dedans au lieu de l'élargir.
- **Le QR de poste, posé sur la table du juge** (spec 034). Le juge arrive à sa
  table, ouvre l'application, scanne le carton posé devant lui : son téléphone
  s'appelle « Zone C » dans la console. Il n'a rien tapé. Le nom du poste
  existait depuis la spec 011 et se **tapait à la main** — un réglage optionnel,
  invisible depuis l'écran principal, dans une application qu'on ouvre pour
  scanner : personne ne le faisait, et quand c'était fait, deux téléphones du
  même mur portaient deux noms différents.
  - Le QR porte **`CCPOSTE:` + la lettre de la zone**, et c'est
    **l'application qui compose le libellé** — « Zone A ». Un QR minimal se lit
    mieux, et le jour où le libellé change, on ne réimprime pas dix-sept
    affiches. Le préfixe, lui, n'est pas décoratif : le même viseur voit aussi les dossards (`42`), les blocs
    (`ZJ6`) et le lien de l'organisateur. Sans lui, un bloc scanné par erreur
    depuis cet écran renommerait le poste « ZJ6 » **sans que personne le
    voie**, et la console afficherait « ZJ6 » en face de tous les envois de la
    journée. Chaque refus porte **son** message, jamais « QR invalide ».
  - Du **texte brut**, pas une URL : une URL scannée par l'appareil photo natif
    ouvrirait un navigateur, et le juge se retrouverait hors de son
    application, dans une instance sans file d'attente.
  - **Une nouvelle page `/admin/postes`** dans la console (vue Téléphones) :
    une affiche par zone, **huit par A4** en deux colonnes, QR de 48 mm généré
    localement — six millimètres au-dessus du plancher mesuré des étiquettes de
    blocs. Les 17 zones tiennent sur **3 feuilles**. La densité est **une
    constante nommée** dont descend toute la géométrie : repasser à six est une
    valeur à changer, pas une refonte du CSS. Les zones se déduisent du **plan
    courant**, jamais d'une liste tenue à la main : un mur ajouté dans
    « Dessiner le plan du mur » sort son QR à l'impression suivante. C'est la
    seule page d'impression qui marche **sans compétition active** — on imprime
    ces cartons la veille au soir, avant l'import du classeur.
  - **Le carton ne porte pas de mode d'emploi**, et c'est l'application qui le
    donne : tant qu'un téléphone n'a pas de poste, son **écran d'accueil**
    affiche un petit texte et le bouton qui scanne, puis les efface dès que le
    poste est nommé. Un mode d'emploi imprimé se lit une fois, quand on n'en a
    pas besoin. Le geste reste ensuite dans les Réglages.
  - **Deux téléphones peuvent porter le même nom**, et c'est désormais la
    norme : deux juges sur la même zone scannent le même carton. La console les
    distingue par le **code court de l'appareil** — « Zone A (3f9a1c2b) » —
    partout où un poste est nommé. Rien de nouveau n'est stocké : c'est
    l'identifiant que chaque téléphone porte depuis la spec 011, rendu lisible.
  - Le préfixe est écrit **deux fois**, en Python et en JavaScript. Un test lit
    `poste.js` et le compare à `fiches.PREFIXE_QR_POSTE` : le jour où les deux
    divergent, tous les QR imprimés cesseraient d'être lus sans qu'une ligne ait
    l'air fausse. Un décodeur indépendant (OpenCV) relit par ailleurs ce qu'on
    produit.

- **Un simulateur de juges** (`tools/simulateur_juges.py`). Un panneau local
  ouvre une compétition entière depuis le Mac : nombre de juges, cadence,
  répartition dans le temps, aléas du terrain, démarrage et arrêt en un clic.
  Ce qui part sur le réseau est ce qu'envoie un téléphone — mêmes routes, même
  politique d'envoi, recopiée de `static/juge/politique.js` — et le protocole
  bascule entre les lots `v3` et les trois appels `v2` de l'application gelée.
  Bibliothèque standard uniquement : aucune installation. L'adresse, la clé et
  les derniers réglages sont retenus d'une session à l'autre, **hors du dépôt**
  (`~/.config/climbcontest/`, `0600`), et la barre du haut affiche la version du
  serveur en face. Voir
  [docs/tester-avec-l-emulateur.md](docs/tester-avec-l-emulateur.md).
- **Les réglages d'affichage arrivent en trois secondes** sur la page de
  résultats, sans rechargement : éteindre ou rallumer un classement dans la
  console se voit tout de suite sur l'écran d'à côté. Une route publique
  **légère** (`GET /api/public/reglages`, ~200 octets, aucun calcul de
  classement) est relue toutes les 3 s, là où la charge complète reste à 15 s —
  l'accélérer aurait multiplié par cinq le trafic du wifi de la salle
  (spec 033, R3).
- **La liste des dernières réussites** dans la console, vue « Réussites » :
  grimpeur, bloc, heure, téléphone et référence, filtrable **par téléphone**,
  rafraîchie toute seule tant qu'on la regarde. La route existait depuis la
  spec 011 sans que rien ne l'appelle pour ce cas (spec 033, R12).
- **La légende des profils de mur** revient sur le plan de la fiche du
  grimpeur : dalle, vertical, incliné, dévers, surplomb, toit — du moins au
  plus déversant, et seulement ceux que le plan utilise (spec 033, R11).

### Modifié

- **Plus aucun test de CI n'attend une horloge.** Le job `tests` virait au rouge
  par intermittence, toujours pour la même raison : deux tests navigateur
  attendaient **pour de vrai** le battement de 15 s de la page de résultats, et
  un runner chargé en mettait seize. Cinq tests coûtaient 66 s à eux seuls.

  | test | avant | après |
  | --- | --- | --- |
  | `TestUneZoneQueLePlanNeConnaitPlus` | 29,3 s\* | 1,0 s |
  | `TestLeMurSeMetAJouerToutSeul` | 16,5 s | 2,5 s |
  | `test_reprend_un_autre_port_si_le_sien_est_pris` | 15,9 s | 7,5 s |
  | `test_le_parcours_complet` (fiche) | 15,3 s | 0,9 s |
  | `TestVerrouOrphelinAuRedemarrage` | 10,7 s | 1,6 s |
  | rotation des sauvegardes (2 tests) | 7,8 s | 0,2 s |

  \* celui-là ne coûtait **rien** sur le Mac : il attendait le même battement,
  mais le premier chargement gagnait toujours la course en local et la perdait
  sur un runner chargé. C'est lui qui a expiré à 120 s le 02/09. Le budget par
  test l'a nommé au premier passage de CI ; sans lui il serait encore invisible.

  Aucun test n'a été supprimé ni affaibli : chacun a été vérifié en cassant ce
  qu'il surveille. Trois réglages apparaissent, **tous à défaut inchangé** :

  - **`?periode=`** sur la page de résultats — le battement du rafraîchissement,
    à côté du `?rotation=` qui existait déjà et pour la même raison. Ce qui
    n'est pas réglable ne se teste qu'en le regardant passer.
  - **`CLIMBCONTEST_ATTENTE_VERROU_S`** — combien de temps un worker attend
    derrière le verrou de schéma (10 s). Un verrou **orphelin** encore frais
    n'est jamais volé : chaque worker attend ce délai en entier avant de
    forcer, et c'est aussi la durée d'un redémarrage après plantage.
  - la sonde `/health` du banc d'essai E2E passe **court** (2 s au lieu de 15).
    Un port squatté par une socket qui écoute sans jamais répondre laisse la
    connexion s'établir, puis se tait : la sonde attendait ses 15 s pleines.

  Et trois défauts du harnais navigateur lui-même, tous invisibles sur le Mac
  et tous payés sur le runner :

  - il attendait « que le document contienne **plus de vingt éléments** », un
    pari sur la vitesse de l'analyseur. `admin.html` fait 1600 lignes,
    `#connexion` est à la 850ᵉ et `#console` à la 889ᵉ : dès que le runner
    ralentissait, la sonde qui attendait le premier lisait `null` sur le second
    et rendait un échec qui n'accusait personne. Il attend désormais un document
    **fini**, sur une adresse qui n'est plus `about:blank`.
  - son serveur servait **une requête à la fois** (`wsgiref`). Un navigateur en
    ouvre six en parallèle, et une page qui relit ses données pendant ce
    temps-là passe devant les fichiers qu'elle attend encore. Il est fileté.
  - le **premier** lancement de chromium coûte **7,2 s** sur un runner, les
    suivants 0,33 s (mesuré le 03/09 ; Google Chrome fait 5,3 puis 0,25). Ce
    n'est pas un défaut, c'est un disque froid — mais la facture allait au
    premier test navigateur venu, celui de la couture des zones par ordre
    alphabétique, qui affichait 15 s en CI contre 0,7 s ici et passait pour un
    test qui attend. Le navigateur se **chauffe** maintenant en fond dès la fin
    de la collecte, pendant les quinze cents tests qui n'en ont pas besoin.

  Enfin, un test navigateur qui met plus de 5 s à rendre son verdict lève un
  **avertissement** qui nomme ses attentes de plus de 500 ms — ou dit qu'il n'y
  en a aucune, et que le temps est passé avant le pilote. C'est ce qui manquait
  pour diagnostiquer : un test qui passe ne montre rien de ce qu'il a fait.
- **La page de résultats démarre sans le champ de recherche**, et le bouton
  `⌕` de l'en-tête l'ouvre. Le choix est retenu pour l'appareil. Renversement
  du défaut de la spec 020 (spec 033, R6).
- **Les étiquettes de blocs** sortent zone par zone **dans l'ordre
  alphabétique** — A d'abord, Z en dernier —, les blocs sans zone à la fin. Et
  le **numéro a désormais une taille fixe** (19 mm) : il était dimensionné
  étiquette par étiquette, ce qui donnait « J6 » à 26 mm et « J24 » à 19,5 sur
  la même planche (spec 033, R7 et R8).
- **L'application juge** : l'engrenage des réglages est un dessin au trait, au
  même trait que le voyant de connexion, et **le dernier élément** de la barre
  du haut ; c'était un caractère emoji, posé avant le voyant. La carte du
  grimpeur passe en deux colonnes et affiche **sa catégorie à droite**, à la
  taille de son nom — le contrôle du juge avant de valider. Le catalogue rangé
  sur le téléphone passe en **forme 4** (il garde la catégorie complète, le
  circuit s'en déduit) : les téléphones le retéléchargent tout seuls
  (spec 033, R9 et R10).
- **La cascade de couleurs** : « Aucune cascade » cache aussi l'interrupteur
  par catégorie, et le bouton coché se voit — pastille dessinée à l'accent,
  carte teintée — là où le point natif était presque invisible en thème sombre
  (spec 033, R1 et R2).

### Corrigé

- **`/health` annonçait un retard de classeur qui n'existait pas.** Le compteur
  `reussites_en_attente` comptait toutes les réussites non synchronisées,
  **toutes compétitions confondues**, alors que le miroir ne sert que la
  compétition active. Le 03/09 il affichait `714` en attente pendant que le
  miroir n'avait plus rien à écrire : 714 réussites d'ailleurs, inenvoyables par
  construction, qui seraient restées affichées à jamais. Le coût n'est pas
  cosmétique — un vrai retard de cinquante aurait affiché `764`, indistinguable
  de `714` au coup d'œil, et c'est le chiffre qu'on regarde le jour J pour
  savoir si le classeur suit. Le compteur et le miroir partagent désormais **le
  même filtre**, et ce qui n'est pas envoyable se compte à part dans
  `reussites_inenvoyables` — sorti du chiffre, pas caché.
- **Deux sauvegardes dans la même seconde n'en faisaient qu'une.** Le nom de la
  copie vient d'un horodatage **à la seconde** ; deux appels rapprochés
  portaient donc le même nom, et le second écrasait le premier sans un mot. Le
  minuteur tourne toutes les dix minutes, alors ça ne se voyait pas — mais une
  sauvegarde à la main juste avant un import et une juste après, c'est
  exactement le geste qu'on veut pouvoir faire. Un ordinal tranche l'égalité,
  et seulement quand il y en a une : le nom habituel ne change pas.

  Le défaut était **caché par ses propres tests**. Ceux de la rotation dormaient
  1,05 s entre deux lancements, « parce que l'horodatage est à la seconde » :
  ils prouvaient que la rotation marche quand les noms diffèrent, et rien du
  tout sur le cas où ils ne différaient pas.
- **Le bouton lecture/pause de la page de résultats repartait à l'arrêt à
  chaque rechargement.** L'état est retenu pour l'écran, comme le choix de la
  recherche. Et les deux glyphes venaient de deux familles — l'un géométrique,
  l'autre emoji : ce sont maintenant deux icônes dessinées dans la même boîte
  (spec 033, R4 et R5).
- Au passage, le bouton affichait **« pause » alors que la rotation était à
  l'arrêt** : `svg.hidden = false` ne fait rien, `hidden` appartient à
  `HTMLElement`. C'est le défaut corrigé en 0.15.0, revenu par la porte du SVG ;
  le choix d'icône passe désormais par une classe CSS.

- **Le simulateur de juges jetait ce qui restait en file**, et **cumulait ses
  compteurs** d'un lancement à l'autre. Les deux défauts ont été trouvés en
  *analysant* un test grandeur nature (25 juges, ~1 350 scans) : l'instrument
  faussait la mesure qu'il existe pour produire. « Arrêter » coupe désormais les
  scans **puis laisse les expéditeurs finir** — onze réussites étaient perdues à
  l'arrêt du run du 03/09, là où un vrai téléphone garde sa file dans IndexedDB
  et la repart à la reprise ; un simulateur qui perd des réussites que le vrai
  client ne perd pas fait douter du vrai client. Le vidage se fait **en tâche de
  fond** (bloquer gèlerait le bouton vingt secondes, et un bouton qui ne répond
  pas est un bouton sur lequel on appuie trois fois), un second appui coupe
  court quand le serveur ne répond plus, et ce que le serveur n'a pas tranché
  **reste en file** et est annoncé comme tel : rien n'est inventé enregistré.
  Les compteurs, eux, repartent de zéro à chaque lancement — un écart de sept
  entre les tuiles et le tableau des juges avait coûté une enquête sur une perte
  de données qui n'existait pas. `paires` fait exception, et volontairement : le
  serveur, lui, se souvient toujours des passages déjà validés.
- **« terminee » s'écrivait sans accent** sous le plan du mur de la fiche du
  grimpeur, quand toutes les cases d'une zone sont cochées. Vu à l'écran, pas à
  la relecture : le mot est court et l'œil le complète. La règle du dépôt
  distingue deux choses et la coquille est passée entre les deux — les littéraux
  **Python** restent en ASCII (messages d'erreur, journaux, JSON), mais tout ce
  qui **s'affiche** est du français accentué, gabarits et JavaScript compris.

## [0.17.0] — 2026-09-03

MINEUR : le serveur se met à jour depuis la console. Le reste est du correctif,
dont **trois occurrences d'un même défaut de cascade** — un `hidden` battu par
une règle de mise en page — trouvées l'une après l'autre.

### Modifié

- **Le serveur se met à jour depuis la console, et plus tout seul** (spec 031).
  Le minuteur `climbcontest-deploy.timer` interrogeait GitHub **toutes les deux
  minutes** : 30 requêtes par heure sur un quota **anonyme de 60 par heure et
  par adresse IP publique**, partagée par toute la maison. Cinq déploiements
  avaient échoué le 30/08 pour dépassement, sans que rien ne le signale ailleurs
  que dans le journal. Et depuis que la VM 110 tourne en permanence, publier un
  tag mettait en production en moins de deux minutes, sans que personne ne l'ait
  demandé.

  À la place, une carte **Version du serveur** dans les Réglages, réservée aux
  administrateurs : elle vérifie **une fois par jour**, affiche le changelog de
  la release — c'est le corps de la release GitHub, donc déjà la section de ce
  fichier — et installe en un clic. Une **pastille** paraît dans le bandeau
  quand une version est disponible, et mène aux Réglages.

  **Une compétition en cours bloque l'installation**, sans contournement dans
  l'interface : redémarrer coupe vingt-cinq téléphones au milieu des scans. Le
  geste de secours reste `sudo systemctl start climbcontest-deploy.service`.

  Coût du nouveau rythme : 1 requête sur 60 par heure, contre 30.

  ⚠️ **À poser sur la VM avant que cette version n'y arrive** : la quatrième
  ligne de `/etc/sudoers.d/climbcontest`, qui autorise l'application à démarrer
  `climbcontest-deploy.service`. Sans elle, le bouton répond « le service de
  déploiement n'a pas pu être démarré ».

### Corrigé

- **Trois endroits où « masqué » ne masquait pas** (#86, #89). Une règle
  d'auteur qui pose un `display` bat le `[hidden] { display: none }` de la
  feuille du navigateur, quelle que soit sa spécificité. Trois fois le même
  défaut, trouvés l'un après l'autre :

  - **la console s'affichait sous le formulaire de connexion.** Déconnecté, sur
    tout écran de 1080 px ou plus, le tiroir, les formulaires et le bouton
    d'effacement des données étaient là, sous le formulaire, et cliquables.
    Aucune donnée ne fuyait — les 44 routes `/admin` répondaient déjà 401 — mais
    la page invitait à cinquante clics qui ne pouvaient que rater ;
  - **l'écran de réglages du juge offrait un bouton « Renvoyer » inerte**, à
    côté de « 0 refusées », toute la journée, sur tous les téléphones. Le
    toucher répondait « aucune réussite refusée » ;
  - **la barre de catégories du mur dessinait une bande** en travers de
    l'écran projeté quand il n'y avait qu'une catégorie : 21 px et sa bordure,
    mesurés dans un navigateur.

  Les rustines locales qui traitaient le problème un élément à la fois — sept
  au total — sont remplacées par la règle globale `[hidden] { display: none
  !important }`, désormais dans les quatre pages. La console porte en plus
  `inert` : même si un style la rendait visible, rien n'y serait cliquable.
  Aucun test ne pouvait voir ça — le gabarit disait la vérité, `hidden` était
  bien posé. Seul le `display` calculé le raconte, donc les tests de
  non-régression pilotent un vrai navigateur.

- **Les neuf points de la revue du 02/09** (#87). Les plus coûteux étaient à
  l'impression : **une planche de 20 feuilles sortait en 40 pages**, et 7 en 14,
  parce que la feuille occupait la surface utile exacte à 6 mm de marge — zéro
  marge d'erreur, et une vraie imprimante coupait chaque feuille en deux. Le
  défaut apparaît dès 8 mm de zone imprimable. Les aplats de couleur, eux, ne
  s'imprimaient pas faute de `print-color-adjust: exact` : les pastilles
  sortaient en ronds vides. Et **les 120 fiches débordaient toutes** sur le plan
  du mur, de 5,75 mm — `1fr` vaut `minmax(auto, 1fr)`, neuf colonnes de « M52 »
  faisaient 70 mm dans une colonne de 60.

  Le reste : « Aucune cascade » masque la partie règle, « Sur mesure » redevient
  sélectionnable depuis « Comme le classeur » (le bouton coché était *déduit*
  des phrases et se décochait sous le doigt), les colonnes Difficulté et Prises
  ne gardent que la pastille, la barre de catégories respecte les classements
  masqués, la rotation du mur ne renonce plus quand il n'y a rien à montrer, et
  « ← La console » de l'éditeur de plan ne mène plus à `/admin`, qui n'existe
  pas. Un test en face de chaque point, tous rouges sur le code d'avant.

- **Un mur redessiné entre deux compétitions ne peut plus rester invisible sur
  le téléphone d'un juge** (spec 029). Le plan voyage dans le catalogue
  précisément pour être **versionné** — servi à part, un client garderait un
  mur périmé sans moyen de le savoir. Mais `catalogue_version` appartient à une
  compétition, alors que le plan est **global** : redessiner sans édition
  active ne prévenait personne, et à la réouverture le téléphone recevait un
  **304** en gardant l'ancien mur.

  Le geste concerné n'a rien d'exotique : c'est entre deux compétitions qu'on
  retouche le mur. Une seconde bouche existait, moins visible — une édition non
  active portait le nouveau plan sans que son numéro ait bougé, et le trou se
  rouvrait dès qu'on basculait dessus.

  ⚠️ **Ce ne pouvait pas être un compteur global unique.** Le 304 se décide par
  **égalité stricte** (correctif du 30/08) : un numéro identifie un couple
  (édition, état de son catalogue). Un numéro partagé aurait fait répondre
  « rien de neuf » à un téléphone qui vient de changer d'édition et qui a
  besoin d'une autre liste de participants. Chaque édition reçoit donc un
  numéro **neuf et distinct**, tiré de l'horloge commune.

  **Le contrat de `/api/v2/catalog` ne change pas** : l'étiquette reste un
  entier, `?depuis=N` et `If-None-Match` se comportent comme avant. Les
  téléphones déjà déployés n'ont rien à apprendre — l'application juge n'est
  pas mise à jour le matin d'une compétition.

- **La fiche du grimpeur ne s'ouvre plus en rejeu d'archive** (spec 026). La
  spec la mettait hors périmètre — « la route publique ne parle que de la
  compétition active » — mais la garde n'existait que pour le mode mur. Une
  ligne d'archive restait cliquable, et `GET /api/public/grimpeur/<id>`
  répondait avec la compétition **active**.

  Ce n'était pas une fiche vide. `Participant.id` est un rowid SQLite : effacer
  une édition (spec 018) **libère** ses identifiants, et la suivante les
  reprend. Mesuré en rejouant la séquence — archiver mars, l'effacer, semer
  novembre : les nouveaux participants reprennent les id 1 et 2. Toucher la
  ligne « MARS-Alice » ouvrait la fiche de « NOV-Chloe », une autre personne,
  réelle et nommée, sous le nom affiché par la ligne. Le curseur, lui,
  promettait le clic.

  Trouvé en fusionnant les specs de la 0.16.0 et en regardant le résultat, pas
  en relisant l'une d'elles : le rejeu vient de la 018, la fiche de la 026, et
  la réutilisation d'identifiants de la 018 encore. Aucune ne le voit seule.

### Ajouté

- **Les coutures entre les specs 025, 026 et 028/029 sont tenues par des
  tests** (`tests/test_coherence_console_ecran.py`). Elles ont été écrites en
  parallèle et se sont rencontrées au merge ; trois défauts y vivaient, dont
  aucun n'était visible depuis une seule branche. Ces dix-huit tests vérifient
  ce qu'aucune spec ne possède seule : la cascade réglée dans la console et lue
  par la fiche du parent, le compte de blocs affiché par deux chemins, et le
  plan du mur servi à l'identique au juge, au parent et au dossard imprimé.

  Aucune assertion ne fige un score : la cascade rend le dénominateur `1000/n`
  solidaire entre catégories, et comparer des classements avant et après un
  réglage échouerait sur un déplacement qui n'est pas un défaut.

- **Un seul harnais de pilotage du navigateur** (`tests/navigateur.py`), qui
  réunit les trois corrections payées séparément par trois sessions : le
  verdict qui remonte par `fetch` plutôt que par le titre, `contentDocument`
  relu à chaque accès parce que le premier rendu est un `about:blank` déjà
  « complete », et `make_server` + `shutdown()` au lieu d'un `app.run` qui
  survit au test en gardant son port.

## [0.16.0] — 2026-09-02

Cinq specs de la journée du 02/09 : la **cascade de couleurs** réglable depuis
la console (025), la **fiche du grimpeur en direct** (026), le lot de **treize
corrections** dicté après le pilotage de la 0.15.0 (027), et le **plan du mur**
qui passe aux polygones (028) puis se dessine depuis la console (029).

Le classement a par ailleurs été **confronté au classeur de bout en bout** sur
une compétition simulée — 120 grimpeurs, 53 blocs, 192 réussites posées pour
éprouver seize cas — score **et** rang, un grimpeur à la fois : **480
comparaisons, 0 écart**. Le détail :
`docs/rapports/2026-09-02-validation-classement.html`.

### Ajouté

- **La cascade de couleurs se règle depuis la console** (spec 025). Réussir tous
  les blocs d'une couleur peut en valider d'autres, plus faciles. La règle
  s'écrit en **phrases** — « quand au moins 2 parmi ⟨Vert⟩ ⟨Bleu⟩ ⟨Mauve⟩
  ⟨Rouge⟩ ⟨Noir⟩ sont validées → valider ⟨Jaune⟩ » — dans la vue **Général**,
  réservée aux administrateurs. Trois préréglages : aucune cascade (le défaut),
  comme le classeur, sur mesure.
- **Un interrupteur par catégorie**, qui reproduit `Listes!D29:D38` du
  classeur : c'était la dernière divergence de portée entre les deux moteurs.
- **Un contrôle des phrases.** Deux phrases ne peuvent pas se contredire — le
  résultat est leur union — mais elles peuvent mentir à qui les écrit. Le
  contrôle refuse une cascade qui remonte, et signale les règles sans effet et
  les couleurs validées deux fois.
- **Un aperçu** sous la règle : sur un circuit donné, ce qu'un grimpeur se voit
  créditer. Il n'est pas décoratif — sur les données réelles de novembre 2025,
  une règle déclenchée par une seule couleur pleine déplace 264 rangs sur 392.
- **Les blocs crédités se distinguent** : la page de résultats marque le
  compteur d'un astérisque, dit « 7 grimpés · 29 crédités » en infobulle, et
  porte la légende de l'astérisque dans la ligne de comptage — la colonne
  « Blocs » disparaît sur téléphone, et une infobulle ne s'atteint ni au doigt
  ni sur un vidéoprojecteur. Dans la console, l'aperçu peint les blocs crédités
  en hachures sur la teinte de leur couleur.
- `classement_service.blocs_du_grimpeur()` rend `{grimpes, credites}` — deux
  ensembles disjoints par construction, pour la fiche du grimpeur à l'écran.
- **La fiche du grimpeur, en direct** (spec 026). On touche un nom dans le
  classement : sa fiche s'ouvre — l'identité dans la mise en page de son
  dossard, son rang, et **tous les blocs de son circuit** avec ce qu'il en a
  fait. Grimpé en vert plein, **crédité en hachures** (la cascade de couleurs le
  lui accorde sans qu'il l'ait grimpé), le reste en creux.

  La spec 023 imprime la même chose sur papier, mais elle sort de l'imprimante
  le matin : elle ne peut rien dire de la journée. La page de résultats, elle,
  savait, et n'en montrait qu'un nombre — « 12 blocs », sans dire lesquels, ni
  ce qu'il reste, ni où aller. Les deux moitiés existaient séparément.

- **Le mur, depuis un bloc** (spec 026). Toucher un bloc ouvre le plan de la
  salle sur sa zone, qui **rebondit**. Chaque zone porte l'état du grimpeur :
  effacée s'il n'a rien à y faire, pleine s'il lui reste des blocs, **cerclée
  de vert** quand il l'a terminée. Toucher une autre zone l'ouvre sans rebond —
  le rebond dit « tu arrives ici », pas « tu regardes ici ».

- **Une adresse par écran** : `#g=42` la fiche, `#g=42&z=M` le mur. Le bouton
  retour du téléphone ferme la fiche au lieu de sortir du site, et
  `/#g=42` est un lien partageable qui ouvre la fiche par-dessus le classement.

  Le **dièse** et pas un paramètre : il ne part jamais au serveur, alors que
  `?g=42` créerait une entrée de cache Caddy par grimpeur et par zone pour un
  HTML rigoureusement identique.

- **Le plan du mur devient un jeu de polygones** (spec 028). Adrien : « je
  voudrais un truc où je puisse faire des formes plus triangulaires, peut-être
  même en symbolisant les surplombs et pans inclinés ». `PLAN` rangeait
  dix-sept zones dans un **damier de 8 × 7 cases**, qui ne savait dire ni la
  forme de la salle, ni le profil d'un mur, ni les proportions — rien de ce
  qu'on voit en entrant. Chaque mur porte maintenant son **profil**, de la
  dalle au toit. Le relevé est celui d'Adrien, dessiné avec
  `tools/plan-du-mur/` : **17 murs**, six profils, **3 repères** dont « Bas »,
  qui n'existait pas dans la grille.

  **Le dossard reste en noir et blanc** : il s'imprime à l'encre noire sur du
  papier de couleur, où une teinte serait perdue. Le profil s'y lit à la
  **trame**, qui se densifie et fonce à mesure que le mur déverse — deux
  variables redondantes sur un seul axe ordonné, une seule règle à apprendre.

  Trois pièges, tous mesurés au navigateur et tous gardés par un test : le
  **cadrage** — sept murs touchent le bord, et un `viewBox` naïf rogne la
  moitié de leur trait ; la marge se prend sur le `viewBox` et **jamais sur les
  coordonnées**, décaler les points maquillerait le relevé pour arranger un
  problème d'affichage. La **lettre de zone**, qui tenait par chance : 0,25
  unité de marge, qu'une zone à deux caractères crevait. Et l'**état contre le
  profil** : l'aplat d'une zone « sienne » mangeait sa trame, donc le grimpeur
  perdait le profil précisément sur les zones qui l'intéressent. Les motifs
  sont déclarés **une seule fois pour tout le document** : un identifiant SVG y
  vaut partout, et 120 fiches × 6 motifs feraient 720 identifiants en double
  dont `url(#…)` résoudrait le premier trouvé.

- **Le plan se dessine depuis la console** (spec 029), sur `/admin/plan`,
  atteignable par la carte **« Le plan de la salle »** de la vue *Circuits* —
  avec le reste du papier qu'on prépare. Le plan cesse d'être une constante
  Python : il vit dans la nouvelle table `reglage`, sous la clé `plan_du_mur`,
  et voyage avec le catalogue versionné. Changer le mur ne demande plus une PR,
  un déploiement, et quelqu'un pour les faire : un mur qui bouge un samedi matin
  n'attend plus lundi.

  **En base, et pas dans un fichier** posé à côté : `climbcontest-sauvegarde`
  recopie **la base seule** toutes les dix minutes. Un JSON à côté serait le
  seul fichier sans sauvegarde, et une restauration ramènerait silencieusement
  l'ancien plan. **Global, et pas par compétition** : le club a **un** mur — le
  ranger dans `competition.options` obligerait à le redessiner à chaque
  édition. `fiches.PLAN` reste dans le code comme **plan d'usine** : le défaut,
  et le repli journalisé si la ligne enregistrée est illisible, pour qu'une
  impression de dossards la veille au soir n'échoue pas sur une ligne abîmée.

- **Un écran d'accueil au logo du club dans l'application juge** (spec 027),
  effacé dès que l'application est prête, mais avec un **plancher de 750 ms** :
  sans lui, sur un téléphone rapide, il clignotait sans être vu — pire que pas
  d'écran du tout.

### Modifié

- Le moteur de classement prend une `Cascade` au lieu d'un entier, et la
  **résout par grimpeur, via sa catégorie**. Les scratchs héritent donc de la
  règle de chacun, comme le fait `Inter!DJ19` du classeur, qui se calcule ligne
  par ligne.
- `options.validation_couleur` reste lu **en repli** : une édition d'avant la
  spec 025 se classe exactement comme avant. L'ancien algorithme est rejoué,
  épinglé dans les tests, et confronté aux phrases sur toutes les combinaisons
  de couleurs pleines — 0 écart.
- La couleur d'un bloc est **rapprochée de son nom canonique** avant tout calcul.
  Le classeur écrit « rouge » aussi bien que « Rouge » ; sans ce rapprochement la
  couleur passait pour pleine alors qu'il restait un bloc à faire, et la cascade
  se déclenchait à tort.
- Le classement des **clubs** reporte les blocs crédités : sa ligne portait
  jusqu'ici un total gonflé par la cascade sans l'astérisque qui le dit.
- **`GET /api/public/grimpeur/<id>`**, route publique nouvelle. Les blocs d'un
  grimpeur ne rejoignent PAS la charge de classement : elle est relue toutes
  les 15 s par une soixantaine de téléphones, et y mettre ce qu'une personne
  consulte au clic ferait payer tout le monde.

- **Le plan du mur est estampillé** (`polygones/1`) et la page vérifie
  l'estampille avant de dessiner. `fiches.PLAN` a déjà changé de forme une fois
  (spec 028) et rechangera : une page servie depuis un cache doit **refuser**
  un plan qu'elle ne sait pas dessiner plutôt que de le dessiner de travers, ce
  qui enverrait chercher un bloc au mauvais endroit. Deux tests empêchent le
  numéro de pourrir, dont un qui lit le JavaScript depuis Python pour vérifier
  que les deux côtés sont d'accord.

- **Le bouton à maintenir dit ce qu'il attend** (spec 027). Adrien : « ce n'est
  pas très visible, l'histoire du maintien du bouton ». Le défaut n'était pas
  le geste mais sa **découvrabilité** : rien sur le bouton n'annonçait qu'il
  fallait le tenir. Trois signes le disent — le libellé porte l'instruction
  (« Maintenir 2 s pour effacer 715 réussites »), un **anneau de progression**
  l'entoure pendant le maintien, et le libellé **décompte**, pour que relâcher
  trop tôt se lise comme un abandon et non comme une panne. Le mot `EFFACER` à
  frapper au clavier disparaît.

- **Après « tout effacer », l'import du nouveau classeur suit tout seul** (spec
  027). Ce second geste n'apportait **aucun choix** : après un effacement total
  il ne reste rien à préserver, donc rien à décider — et un geste sans décision
  est un oubli en puissance.

- **Quatre retouches de lisibilité dans la console** (spec 027). **Général**
  passe en tête de « La compétition ». Les classements se lisent **« U11
  Scratch »** et suivent l'ordre du terrain : le tri alphabétique du serveur
  séparait un scratch de ses catégories, qu'on regarde ensemble. Dans
  **Circuits**, la difficulté et les prises deviennent des pastilles — **ronde**
  pour la difficulté, qui est ordonnée, **carrée** pour les prises, qui ne le
  sont pas — toutes avec un **contour**, sans quoi « Blanc », la couleur de
  prises la plus courante du classeur, disparaît sur fond clair. Et **dix-huit
  paragraphes d'aide allégés**, dont deux supprimés parce qu'ils étaient devenus
  **faux** : « deux fiches par page » (il y en a six depuis la 023) et « le mot
  EFFACER se frappe » (plus depuis ci-dessus). Une aide fausse est pire qu'une
  aide absente.

- **Le fond de l'application juge, réchauffé vers l'ocre du logo** (spec 027),
  et le **cache du service worker passé en v3** — sans ce changement de version
  les téléphones déjà équipés garderaient l'ancienne coquille, et l'oubli ne se
  verrait qu'en compétition. ⚠️ Une lueur en haut d'écran, **jamais un aplat
  coloré** : dans cette application la couleur **porte de l'information** — la
  teinte du circuit prend l'écran dès qu'un bloc est scanné, c'est le retour
  visuel du juge — et une teinte franche au repos entrerait en concurrence avec
  elle.

### Corrigé

- **Le podium disparaissait exactement là où on le regarde** (spec 027). Deux
  conditions l'effaçaient — moins de quatre grimpeurs, et « tout le monde est
  déjà sur le podium » — soit précisément les catégories à une ou deux
  personnes. Il s'affiche désormais **toujours**, trois marches, les places
  sans gagnant en **pointillé** : un podium en attente, pas un podium absent.
  Et un grimpeur n'y monte qu'en ayant **marqué**, sans quoi une catégorie qui
  n'a pas commencé couronnait dix-sept personnes à zéro point.

- **Les impressions se chevauchaient, débordaient, et coupaient les fiches en
  deux** (spec 027). Adrien : « si j'essaye d'imprimer, je me retrouve avec des
  dossards entre 2 feuilles ». Deux causes distinctes : `auto-fit` choisissait
  ses colonnes d'après la **largeur** disponible sans rien savoir de la
  **hauteur** produite — dès qu'un groupe de couleur passait sur deux lignes,
  la fiche débordait sur sa voisine, 43 fois ; et une grille dont les éléments
  portent `break-inside: avoid` est fragmentée « au mieux » par le navigateur,
  qui n'a **aucune obligation** de respecter un nombre d'éléments par page.
  Colonnes et pagination passent en Python (`fiches.en_feuilles`), sur des
  hauteurs **mesurées dans le navigateur** — la première estimation se trompait
  de 25 % sur le coût d'une ligne, 5,9 mm supposés contre 7,27 mm réels. Le
  saut de page porte sur la **feuille**, jamais sur un élément de grille.
  Mesuré : **120 fiches → 20 feuilles**, zéro chevauchement, zéro débordement,
  aucune à cheval.

- **Les étiquettes de blocs gaspillaient des feuilles** (spec 027) : le saut de
  page par zone en laissait à moitié vides — une zone d'un seul bloc gaspillait
  sept places. Les blocs sortent déjà dans l'ordre du `Plan`, donc zone par
  zone, et chaque étiquette porte **sa zone en tête** : le regroupement
  physique tient sans payer une feuille par zone. **Huit par A4** — au-dessus
  des six demandés — soit 53 étiquettes sur **7 feuilles**, aucune page vide.

Et sept défauts de la fiche en direct (spec 026), trouvés avant d'atteindre la
production — trois sur la maquette, quatre par une relecture — chacun gardé par
un test :

- Un **lien partagé ouvrait une fiche qu'on ne pouvait plus fermer** : sur
  `/#g=42` ouvert directement il n'y a aucune entrée d'historique à remonter,
  donc la croix, Échap et le voile devenaient inertes et le classement restait
  figé derrière. Seul un rechargement s'en sortait.
- La fiche **« en direct » ne l'était pas** : la fonction de rafraîchissement
  n'avait aucun appelant. Le bloc validé restait en pointillé pendant que la
  ligne du classement, juste derrière, affichait déjà un bloc de plus.
- Le plan pouvait **sortir de son bloc `<script>`** : `json.dumps` n'échappe pas
  `<`, et depuis la spec 029 le plan est de la donnée saisie depuis la console.
  Un `</script>` dans un libellé de repère devenait du balisage vivant sur une
  page publique.
- Les **classements masqués reparaissaient** dans « aussi classé » : la fiche
  court-circuitait le filtre de la spec 020.

- Une **transition qui jouait le retour avant l'aller** : la pile recevait sa
  position après son insertion, et une mesure glissée entre les deux forçait un
  calcul de style.
- **Toute la page devenue traversante au clic** : une couche de contours SVG
  avait pris le nom de classe `cadre`, déjà porté par le gabarit du téléphone,
  et lui appliquait `pointer-events: none`. La page s'affichait parfaitement et
  n'attrapait plus rien. Le test de pointage du navigateur est le seul capable
  d'attraper ça — `.click()` appelle le gestionnaire sans test de pointage.
- Un **drapeau qui contredisait l'historique** : « je suis au mur » était posé
  avant l'écriture du dièse, et tout rendu tombant entre les deux montrait le
  mur sans zone visée.

## [0.15.0] — 2026-09-01

Quatre specs, toutes sorties d'une même session de pilotage de la console par
Adrien le 01/09 au soir.

### Ajouté

- **Le jeton Google se pose en un clic** (spec 022). Classeur → **« Connecter
  le compte Google »** : l'écran de consentement, le retour, le jeton écrit.

  Il fallait jusqu'ici **cinq gestes, dont deux en ligne de commande** —
  retrouver un Mac où `token.pickle` existe, y créer un environnement Python
  avec `google-auth`, lancer `tools/exporter_jeton.py`, copier une ligne de JSON
  qui contient un `refresh_token` (un secret au même titre qu'un mot de passe),
  la coller. Cinq gestes pour un écran dont toute la raison d'être est de
  **remplacer le SSH**. Et aucun ne produit un jeton neuf : ils recopient celui
  qui existait déjà. Le jour où il meurt — révoqué, expiré, compte changé — la
  carte ne savait rien faire.

  `parametrage.py` disait en tête : « ce qui n'est pas ici : le consentement
  OAuth (il demande un navigateur) ». C'était vrai de la ligne de commande. La
  console, elle, **est** un navigateur.

  Le `state` est aléatoire, rangé en session, comparé à temps constant puis
  **retiré** : sans lui, n'importe quel site pourrait faire aboutir chez nous un
  code obtenu ailleurs, et poser **son** compte Google comme identité du
  serveur. Le flux demande `prompt=consent`, sans quoi Google ne redonne **pas**
  de `refresh_token` à un compte qui a déjà consenti — on reposerait un jeton
  qui meurt dans l'heure, et la panne se découvrirait le lendemain matin. Un
  jeton sans `refresh_token` est refusé et **n'est pas écrit**. Rien du jeton ne
  sort : ni journal, ni réponse, ni URL.

  Le collage JSON **reste**, replié sous « Autre méthode » : le flux dépend de
  trois choses hors de notre code, et s'il lâche le matin de la compétition,
  supprimer le repli laisserait le serveur sans **aucun** moyen de recevoir un
  jeton.

  ⚠️ **Deux réglages à faire une fois chez Google, sinon le bouton ne mène
  nulle part.** Déclarer l'URI de retour — la console **l'affiche, prête à
  copier**, sous le bouton. Et surtout vérifier l'**état de publication** de
  l'écran de consentement : 🔴 **en « Test », Google fait expirer le
  `refresh_token` au bout de 7 jours**. Un jeton posé le lundi serait mort le
  samedi de la compétition, sans que rien ne prévienne. Voir
  `docs/runbook-competition.md`.

- **Les étiquettes de blocs à coller au mur** (spec 024). Le juge scanne
  **deux** QR : celui du grimpeur, puis celui du bloc. Le second est collé au
  mur, et rien ne savait l'imprimer — préparer une compétition demandait encore
  d'ouvrir le classeur et d'imprimer son onglet `Fiches`, dont les QR sont
  produits par `api.qrserver.com` : un appel vers un tiers, qui ne marche pas
  si la connexion tombe la veille au soir, quand on colle les étiquettes.

  `/admin/etiquettes`, **huit par A4**, filtrable par zone ou par bloc. Le
  numéro est le plus gros élément (18 mm) : c'est ce qu'on lit à deux mètres
  pour savoir si on est devant le bon bloc. Le QR fait 40 mm — il se scanne d'un
  bras tendu, pas à trente centimètres.

  **Une zone par page** : on prend la page de la zone Z, on va coller ses cinq
  étiquettes, on ne trie rien à la main.

  Et l'étiquette dit **pour qui le bloc compte**. Un bloc rattaché à aucun
  circuit ne compte pour personne : c'est l'anomalie que la vue Circuits traque
  depuis la spec 019, et le papier qu'on va coller est le dernier moment pour la
  rattraper. Elle l'écrit en rouge.

### Modifié

- **La console suit le thème du système** (spec 021). Les couleurs étaient
  figées dans `:root` et rien ne regardait `prefers-color-scheme` : sur un Mac
  réglé en clair, en plein jour, dans une salle éclairée, on lisait un écran
  noir sans l'avoir demandé. Le clair devient le **défaut**, le sombre une
  redéfinition. **Aucun réglage dans la console** — rien à choisir, rien à
  mémoriser, rien qui puisse rester coincé sur un mauvais choix.

  L'accent mauve laisse la place à l'**ocre du logo du club**, qui garde sa
  fonction : distinguer d'un coup d'œil la console de la page publique
  projetée, qui reste bleue.

- **Le tiroir reste ouvert quand l'écran le permet** — au-delà de 1080 px, dans
  le flux, sans voile ni burger. Sur un écran de 1920 px il restait 1600 px
  vides à droite : le recouvrir puis le refermer obligeait à rouvrir le menu à
  chaque changement de vue. C'est une **requête média**, pas un test
  JavaScript : redimensionner bascule sans rien recalculer.

- **Confirmer une destruction, c'est maintenir le bouton deux secondes** — à la
  souris, au doigt, ou avec Entrée. Il fallait frapper `EFFACER` : sept
  caractères au clavier, sur un ordinateur posé sur un coin de table dans une
  salle d'escalade. Ce que le mot apportait, c'est l'**arrêt** ; c'est lui qu'on
  garde, en jetant la frappe. Le libellé nomme ce qu'on détruit — « Effacer 715
  réussite(s) » — et ce chiffre sous les yeux remplace la frappe comme dernier
  garde-fou.

  **Le contrat HTTP ne bouge pas** : `cycle.exiger_confirmation()` exige
  toujours `confirmation: "EFFACER"`. Le mot cesse d'être un geste humain pour
  devenir un **marqueur de protocole**, qui ferme la route à un `POST` nu, à un
  onglet resté ouvert, à un script qui l'appellerait sans passer par la fenêtre.

- **Deux écrans d'administration au lieu d'un et demi.** « Compétition » devient
  **« Général »** — l'édition, ce qu'on en montre, l'archive — et « Importer »
  et « Effacer » rejoignent **« Classeur »** : ils ne parlent que de la relation
  entre la feuille et la base. Trois redites disparaissent, dont deux cartes qui
  posaient la même question et un compteur affiché à deux endroits.

  Le tiroir se lit désormais : Participants · **Circuits · Réussites** ·
  Téléphones · Général · Classeur · Archives · Réglages — on regarde les blocs
  pour savoir ce qui existe, puis ce qui a été validé dessus.

- **Les classements affichés se règlent à l'interrupteur.** Une case à cocher
  dit « je consens » ; ces lignes-là disent « c'est allumé ou c'est éteint ».

- **La fiche du grimpeur remplace la bande à découper** (spec 023).
  `/admin/dossards` imprimait des bandes de 30 mm : un QR, un numéro, un nom.
  Le classeur, lui, imprime une **fiche** (onglet `Fiches`) qui porte ce qui
  manquait : **quels blocs comptent pour ce grimpeur, et où ils sont dans la
  salle**. C'est le seul papier qu'il a en main de la journée.

  **A4 paysage, six fiches en 2 × 3.** Identité, catégorie, circuit, QR ; tous
  les blocs de son circuit groupés par difficulté, dans l'ordre du classeur —
  `Plan!AM` trie sur la couleur puis la **chaîne** (« J10 » avant « J9 »), on
  reproduit sans corriger pour que les deux listes se lisent dans le même
  ordre ; et le **plan de la salle**, relevé de `Fiches!V4:X11` et identique
  dans les trois classeurs archivés, avec **les zones du grimpeur allumées**.

  Deux ajouts sur le classeur : la **zone** au-dessus de chaque numéro — sans
  elle « J6 » ne dit pas où aller, ni à quoi sert le plan — et une zone **hors
  plan** qui se dit au lieu de disparaître.

  La fiche s'imprime **toujours**, même quand il n'y a rien à y mettre : c'est
  elle qui porte le QR. Les quatre cas — pas de catégorie, circuit inconnu,
  circuit vide, aucun bloc — se disent en toutes lettres.

### Corrigé

- **Les QR ne respectaient pas la norme.** L'ISO/IEC 18004 exige une zone de
  silence de **quatre modules** autour d'un QR Code ; nous en posions **deux**.
  Ça marche sur un fond parfaitement blanc et ça lâche dès que le code touche
  autre chose — une bordure de case, le trait de coupe voisin — que le décodeur
  lit alors comme des modules noirs. C'est précisément ce que rapprochent des
  fiches serrées sur une planche. Deux gardes qui n'existaient pas
  l'accompagnent : `qr.taille_de_module_mm()` et un plancher
  `qr.MODULE_MINI_MM`, vérifiés à la taille réelle d'impression.

- **Les cases à cocher s'étalaient sur toute la largeur de leur carte**, leur
  libellé rejeté hors du cadre : la règle globale des champs de saisie
  s'appliquait aussi à elles. Visible dans « Ce qu'affiche la page de
  résultats » et dans la fenêtre de confirmation. Corrigé à la racine.

- **« Ouvrir le classeur » s'affichait alors qu'aucun classeur n'est relié**, et
  proposait d'ouvrir un lien vide : `display: inline-block` bat le `[hidden]` du
  navigateur.

- **Le bouton pause de la page projetée ne disait pas son état.** Il ne recevait
  `aria-pressed` qu'au **premier clic** — le seul moment où l'attribut n'apprend
  plus rien. Avant ça, un lecteur d'écran annonçait « bouton » et non « bouton à
  bascule, non activé » : rien ne disait que la rotation tourne, ni qu'on peut
  l'arrêter. Son voisin, pourtant la même sorte de bouton, portait l'attribut
  depuis toujours.

- **La compétition de test mentait sur deux points** (`tools/semer_competition_test.py`).
  Ses 24 blocs n'avaient **aucune couleur de prises** et vivaient **tous en zone
  Z** : la colonne « Prises » de la vue Circuits affichait « — » partout, ce qui
  donnait l'impression que l'import ne lisait pas la colonne H du `Plan` — il la
  lit depuis la spec 019, c'est la donnée semée qui n'existait pas. Et une seule
  zone rendait invérifiables le plan des fiches comme la planche d'étiquettes.

## [0.14.0] — 2026-09-01

### Ajouté

- **La page de résultats se règle depuis la console** (spec 020). Quatre
  demandes d'Adrien du 01/09, toutes sur cette page.

- **On peut enfin nommer la compétition.** Le bandeau affichait déjà
  `competition.nom` — mais **aucune route ne le changeait** : il restait celui
  donné à la création, et la compétition de production portait le nom de ce qui
  avait servi à la créer. La date suit, parce qu'elle a le même défaut et
  qu'elle sort dans le nom de fichier des archives. Les deux valident **avant**
  d'écrire : une date refusée n'enregistre pas non plus le nom, sinon la
  compétition resterait à moitié renommée.

- **Choisir les classements affichés, d'une liste de cases à cocher.** Décocher
  une catégorie la retire de la barre et de la rotation — sur le mur **et** sur
  les téléphones des spectateurs. Une seule vérité, rien à expliquer le jour J.

  On range **ce qu'on cache**, jamais ce qu'on montre : une catégorie créée en
  cours de journée — une inscription à chaud — doit apparaître par défaut. Avec
  une liste de « ce qu'on montre », elle disparaîtrait en silence.

  C'est un réglage d'**affichage** : tous les classements restent calculés,
  servis et archivés. Filtrer à la source amputerait les archives, et démasquer
  l'après-midi imposerait un recalcul. Et si **tout** est masqué, le réglage est
  ignoré plutôt que de servir une page vide — une page vide se lit comme une
  panne.

- **Un bouton pour masquer la recherche.** Le champ est indispensable sur le
  téléphone d'un parent et parasite sur un vidéoprojecteur. Il n'était masqué
  qu'en mode `?mur`, qui emporte aussi la rotation automatique et le grand
  format — or on projette souvent sans. Le choix est retenu par le navigateur,
  ce qui compte sur une machine qui projette toute la journée. Masquer vide la
  recherche en cours : un filtre actif sans champ visible serait indéchiffrable.

- **Les circuits se voient, et le juge est prévenu** (spec 019). Trois choses,
  toutes sorties du test de bout en bout d'Adrien du 01/09.

- **La couleur des prises entre en base.** L'onglet `Plan` porte deux couleurs
  par bloc : la **difficulté** en colonne F (ordonnée, elle sert au classement)
  et les **prises** en colonne H — celle qu'on cherche des yeux quand deux blocs
  de même difficulté sont dans la même zone. La seconde n'était simplement
  jamais lue.

- **Une vue « Circuits » dans la console.** Quels blocs composent quel circuit,
  quelles catégories les grimpent, et surtout un **contrôle de cohérence** :
  blocs rattachés à aucun circuit, circuits sans aucun bloc, catégories dont le
  circuit n'existe pas. Les trois anomalies sont **silencieuses** aujourd'hui —
  rien n'échoue, rien n'est journalisé, et elles se paient à la remise des prix.
  C'est cet écran qui aurait montré, en une seconde, les 37 blocs orphelins du
  correctif précédent. Il est masqué quand tout va bien : le voir en permanence
  apprendrait à ne plus le lire.

- **L'application juge prévient quand le bloc n'est pas dans le circuit du
  grimpeur.** Adrien, en scannant : « ce participant-là n'est pas censé le
  réaliser […] il faut l'afficher sur l'application avant même de l'envoyer ».
  La réussite partait, et ne comptait pour rien — le classement filtre déjà par
  circuit. Le juge croyait avoir validé, le grimpeur croyait avoir marqué.

  Le contrôle se fait **hors ligne**, sur le téléphone, avant l'envoi :
  `/api/v2/catalog` envoyait déjà la catégorie et les circuits, c'est le
  catalogue local qui les jetait. **Aucun changement d'API.**

  Il **avertit**, il ne bloque jamais : le classeur peut être faux — il l'a été
  le 01/09 — et un juge bloqué en pleine compétition n'a aucun recours. Le
  bouton devient « Envoyer quand même », et le forçage est tracé.

  Quand l'information manque — dossard inconnu, participant sans catégorie, bloc
  rattaché à aucun circuit — l'application **se tait**. Un avertissement qu'on ne
  sait pas justifier apprend à ignorer les avertissements.

  ⚠️ **À l'exploitation** : la forme du catalogue rangé sur les téléphones passe
  de 2 à 3. Chaque téléphone **retéléchargera son catalogue** au premier
  lancement après ce déploiement — une requête, quelques kilo-octets. C'est le
  marqueur de format qui le déclenche, et c'est voulu : sans lui, un téléphone
  garderait un catalogue illisible que le `304` du serveur ne remplacerait
  jamais. Le contrat d'API, lui, **ne bouge pas** — l'application Android
  publiée (`V3.1.4`) parle aux mêmes routes qu'avant.

### Modifié

- **La catégorie apparaît sur les scratchs, et seulement là.** Un scratch —
  général ou par circuit — mélange les catégories, et rien ne disait qui se
  comparait à qui. Sur « U13 F », elle est déjà dans le titre : la répéter à
  chaque ligne prendrait la place du club sans rien apprendre.

- **Le podium et les tableaux côte à côte ne dépendent plus du mode mur, mais
  de la largeur.** Adrien, 01/09 : « je veux toujours avoir le podium […] et je
  veux toujours ton système pour afficher plusieurs tableaux en même temps côte
  à côte **lorsque la page le permet** ». « Lorsque la page le permet » est une
  condition de place, pas de mode — or les deux étaient réservés à `?mur`
  depuis la spec 016. Sur le portable de la salle, et sur la relecture d'une
  archive depuis la console (la même page, sans le paramètre), il n'y avait ni
  marche ni colonnes : un tableau d'une seule colonne au milieu de 1 800 px,
  1 500 px de blanc entre le nom et le score, et neuf lignes visibles là où il
  en tient trente. C'est le même écran et la même page ; ce qui tranche est
  désormais la largeur seule. Le téléphone ne change pas — sous 900 px, ni
  podium ni colonnes, et un podium y mangerait tout l'écran.

  Une colonne coûte plus cher hors du mur que sur le mur : le gabarit y porte
  une colonne de plus — l'étoile des favoris — et se mesure en `rem`. Ce coût
  n'est pas recopié, il se **déduit** des deux constantes dont le calcul de
  densité se sert déjà (389 px de mobilier, plus 140 px pour lire un nom).

### Corrigé

- **Les options de l'édition se lisaient en deux endroits.**
  `classement_service` et `cycle` désérialisaient chacun le même JSON, avec
  leurs propres tolérances. Une seule lecture désormais, dans `cycle` — deux
  lectures d'un même document finissent toujours par diverger sur ce qu'elles
  acceptent. L'écriture fusionne au lieu de remplacer : y poser
  `groupes_masques` ne peut plus faire disparaître `validation_couleur`, ce qui
  aurait changé le classement sans que personne n'ait touché au classement.

- **L'écran du juge disait « Circuit Jaune ».** C'était faux : « Jaune » est une
  couleur de **difficulté**, le circuit c'est « U13 ». La confusion venait de ce
  qu'aucun circuit réel n'était disponible sur le téléphone. Il affiche
  maintenant les deux, chacun sous son vrai nom : « U11 · U13 — Jaune ».

- **La console répondait « Trouvé » sur un scan qui ne compte pas.** Chercher la
  référence d'une réussite posée sur un bloc hors circuit répondait « ce scan est
  bien arrivé », ce qui est vrai et trompeur : il est arrivé, et il ne compte pas.
  Elle le dit maintenant, et renvoie vers la vue « Circuits ».

- **Le quatrième circuit n'était jamais importé.** `importer.py` figeait les
  colonnes de circuit de l'onglet `Plan` à **J, L, N** — trois — parce que la
  structure avait été relevée sur le classeur de mars 2026, qui n'en a que
  trois. Le classeur de novembre 2025 en a **quatre** : `U17` vit en colonne
  **P**, jamais lue.

  Le circuit n'était donc pas créé, ses **37 blocs** n'étaient rattachés à rien,
  et le classement `U17` sortait vide sur « aucun bloc n'appartient au circuit ».
  Chaque réussite d'un grimpeur de ce circuit comptait pour **zéro**. Aucun
  message, nulle part : ni dans le rapport d'import, ni dans le journal.

  Les colonnes sont maintenant **découvertes dans la ligne d'en-tête** (J, L, N,
  P, R — une sur deux, cinq au plus, ce que le classeur annonce lui-même en
  `Listes!A1`). Et l'import **dit ce qu'il a lu** : « Circuits lus — U11
  (colonne J) · U13 (colonne L) · U15 (colonne N) · U17 (colonne P) », dans le
  rapport de la console comme dans le journal. C'est la ligne qu'on compare de
  tête à ce qu'on attend ; sans elle, le prochain circuit manquant se
  reperdrait en silence.

- **« Enregistrer » ne restait plus muet en reliant un classeur.** Signalé par
  Adrien pendant un test de bout en bout : mode *nouvelle compétition*, mot
  `EFFACER` frappé, clic sur **Enregistrer** — rien. Il a fallu passer la
  compétition en *préparation* depuis une autre vue pour que le geste aboutisse.

  Deux causes. Le bouton posait un `window.confirm` nu et **n'envoyait jamais**
  `forcer`, alors que la route l'accepte depuis la spec 018 ; et le refus 409 du
  serveur s'affichait dans la zone de message, **tout en haut d'une page où l'on
  se trouve 180 lignes plus bas**. Le message existait ; personne ne le voyait.

  « Enregistrer » passe désormais par le **même dialogue** que « Importer » et
  « Effacer » — compteurs, alerte d'archive, et la case « Cette compétition est
  marquée EN COURS. Effacer quand même. » Le mot `EFFACER` se frappe dans la
  fenêtre, plus dans la carte. Et toute la console fait maintenant **défiler sa
  zone de message dans la vue** : un refus ne peut plus passer inaperçu, quelle
  que soit la vue et la longueur de la page.

- **Le classement par club n'affichait qu'une ligne.** `participant_id` vaut
  `0` pour toutes ses lignes — un club n'est pas un participant — et c'est lui
  qui servait de clé pour apparier une ligne à son nœud d'une repeinture à
  l'autre. Les cinq clubs se disputaient donc le même nœud, déplacé de l'un à
  l'autre : il n'en restait qu'un à l'écran, le dernier. Le défaut est antérieur
  et passait inaperçu ; il devient visible dès que le podium existe hors du mur,
  sous la forme de deux marches vides à côté d'une troisième. La clé retombe sur
  le nom quand l'identifiant manque.

- **Les titres de colonnes n'étaient au-dessus de leurs colonnes nulle part.**
  Signalé par Adrien sur téléphone : « SCORE » sortait de l'écran et l'étoile
  des favoris retombait à la ligne suivante. Deux causes distinctes, l'une et
  l'autre présentes depuis la spec 016, l'une et l'autre dans `--grille-ligne`.

  Cette propriété est **héritée**, donc résolue par élément : les lignes la
  prennent de `#liste`, les titres de `#entetes`. Or `#liste` en portait sa
  propre valeur — et un `id` l'emporte sur tout. Les lignes recevaient donc
  cinq colonnes pendant que les titres en recevaient six, ce qui explique
  l'étoile sans colonne, tombée à la ligne. Effet de bord du même défaut : les
  largeurs proportionnelles à `--h`, posées pour l'écran projeté, **n'ont
  jamais atteint les lignes** — elles sont restées sur des `em` figés.

  Seconde cause, sur téléphone : les colonnes s'y mesuraient en `em`, qui se
  résout sur l'élément qui s'en sert — 16 px pour une ligne, 10,88 px pour un
  titre écrit en `0.68rem`. La même valeur donnait deux grilles différentes :
  38 px de colonne « Rang » sur la ligne, 26 px sur son titre, qui sortait en
  « RAN ». Les colonnes hors du mur se mesurent maintenant en `rem`.

- **La colonne « Blocs » ne pouvait pas contenir son propre titre.** Son titre
  cesse de rétrécir à 0,6 rem, son plancher, pendant que la colonne continue de
  suivre la hauteur de ligne : sous 62 px, « BLOCS » sortait en « BLOC ». La
  colonne a désormais un plancher, elle aussi.

- **La densité, sur téléphone, se décidait sur la largeur totale** — sans
  compter l'étoile, les gouttières ni le rembourrage de la ligne. À 470 px de
  fenêtre, la page gardait donc les cinq colonnes chiffrées en laissant **75 px
  au nom**, quand « Vialle Jade » en demande 88 et « Nieuviarts Martin » 139
  (mesuré au canevas). Elle mesure maintenant ce qui reste vraiment au nom, et
  replie le tableau en deux lignes avant de le tronquer. Vérifié de 320 à
  1920 px : aucune largeur ne déborde, aucun titre n'est rogné, et le nom garde
  au moins 140 px partout au-dessus de 360 px de fenêtre.

## [0.13.0] — 2026-09-01

Le pilotage d'une édition passe entièrement dans la console — la créer, régler
son état, tester le classeur en écriture, importer, effacer, archiver, revoir
une archive dans la vraie page de résultats (spec 018). Plus besoin de SSH ni de
SQL un dimanche matin.

Et l'écran projeté finit sa passe de lisibilité : le classement se lit d'un
seul bloc, podium compris, les cartes ne débordent plus, et aucun nombre ne se
coupe plus au milieu.

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

### Modifié

- **Le tableau de la page de résultats reprend le podium.** Il commençait au
  rang 4 : pour savoir ce qu'avait fait le premier, il fallait remonter les yeux
  à l'autre bout de l'écran — et à quatre ex æquo, la marche ne le disait déjà
  plus. Le classement se lit maintenant d'un bloc, de 1 à N, et un liseré de
  médaille marque les trois premières lignes — **toujours**, y compris sur un
  téléphone, où aucune marche n'est dessinée et où ils passaient jusqu'ici
  inaperçus. En contrepartie, la carte de podium **perd le compte de blocs et
  l'écart** : sans étiquette et à côté d'un score deux fois plus gros, ils se
  déchiffraient plus qu'ils ne se lisaient, et ils volaient au nom la largeur
  qui lui manque justement quand des ex æquo se partagent une marche. Ils sont
  deux lignes plus bas, sous un en-tête qui les nomme.
- La construction de la charge de `/api/public/classement` sort du corps de la
  vue pour devenir `classement_service.charge_publique()`. Deux appelants
  désormais : la route publique et l'archivage. Écrite en double, elle aurait
  divergé au premier changement — et la page de résultats aurait cassé sur les
  archives uniquement, c'est-à-dire longtemps après. Réponse inchangée.

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
- **Le podium débordait de ses cartes.** Signalé par Adrien en regardant
  l'écran : « sur scratch H, ça dépasse au niveau du podium ». Deux causes,
  et la seconde est la vraie.

  La colonne de contenu de la carte était un `1fr` **nu**. Le `min-width` par
  défaut d'une piste de grille vaut `auto` : elle ne peut donc jamais devenir
  plus étroite que son contenu, et `.chiffres` est en `nowrap`. La grille
  réclamait 404 px dans une carte de 373 — le nom, le club et les chiffres
  sortaient de 9 px **par la droite, par-dessus le bord arrondi de la carte**.
  L'ellipse du nom ne servait à rien : elle se calculait sur une largeur qui
  débordait déjà. Corrigé en `minmax(0, 1fr)`.

  Conséquence directe : un écart rogné au milieu affichait « −17 » pour
  « −1700 ». Sur un mur, ça se lit comme un écart de dix-sept points — **un
  nombre coupé ment, un nom coupé non**. Le sujet est clos autrement depuis :
  l'écart et les blocs ont quitté la carte pour le tableau (voir *Modifié*),
  et il ne reste sur la carte aucun nombre qu'un manque de place puisse couper.

- **Le mobilier de la carte suit le nombre d'ex æquo.** La largeur de la marche
  se divisait entre les cartes, mais le gros numéro de place, les marges et la
  taille du nom ne bougeaient pas. À six ex æquo, les six noms étaient tronqués
  d'un coup. Ils tiennent maintenant en entier.

- **La carte de podium était réglée sur la hauteur du classement, pas sur la
  sienne.** `.nom`, `.club` et `.score` existent des deux côtés — ligne de
  tableau et carte de podium — et `body.mur .nom` l'emportait sur `.pod .nom` :
  même nombre de classes, mais un `body` en plus. Une carte se dessinait donc à
  la taille d'une ligne de tableau, 16,72 px là où elle en demandait 40, et ce
  depuis la spec 016. Personne ne l'a vu tant que **toutes** les cartes
  tombaient dedans ; ça saute aux yeux depuis que le mobilier suit les ex
  æquo — une marche à une seule carte se retrouvait deux fois plus petite que
  sa voisine à deux.

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

[0.20.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.20.0
[0.19.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.19.0
[0.18.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.18.1
[0.18.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.18.0
[0.17.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.17.0
[0.16.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.16.0
[0.15.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.15.0
[0.14.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.14.0
[0.13.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.13.0
[0.12.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.12.1
[0.12.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.12.0
[0.11.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.11.0
[0.10.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.10.0
[0.9.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.9.0
[0.8.1]: https://github.com/computingify/climbcontest-core/releases/tag/v0.8.1
[0.8.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.8.0
[0.7.0]: https://github.com/computingify/climbcontest-core/releases/tag/v0.7.0
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
