# L'application juge — inventaire et refonte (29 août 2026)

Inventaire de l'application Android telle qu'elle était après la spec 003
(catalogue local, file persistante, rétention des refus), et ce qui en a été
fait. Le code est dans `climbcontest-android/`, dépôt `computingify/ClimbContest`.

Le constat de départ tient en une phrase : **l'application marchait, mais elle
ne disait rien.** Elle scannait, elle envoyait, elle gardait tout en cas de
coupure — et le juge n'avait aucun moyen de savoir où il en était.

---

## 1. Ce que l'application fait, et bien

Rien de ce qui suit n'a été touché. C'est le socle.

| Brique | Fichier | Ce qu'elle garantit |
| --- | --- | --- |
| Catalogue local | `Catalogue.kt` | Un scan est validé en ~100 ns contre une table locale, sans réseau. Un QR inconnu déclenche un rafraîchissement : le participant inscrit dix minutes plus tôt marche sans que le juge fasse quoi que ce soit. |
| File persistante | `FileDeReussites.kt` | JSONL en ajout seul sur le disque du téléphone. « Validé » s'affiche quand la réussite est sur le disque, pas quand elle est sur la VM. |
| Envoi par lots | `Expediteur.kt`, `PolitiqueEnvoi` | Lots de 5, ou toutes les 10 s, avec retrait exponentiel plafonné à 60 s. |
| Refus conservés | `FileDeReussites.kt` | Une réussite refusée part dans `refusees.jsonl` au lieu d'être perdue. Le cas fréquent est « ce dossard n'existe pas **encore** ». |
| Contrat réseau | `ClimbContestApi.kt` | Testé sur la JVM contre un serveur factice, sans émulateur. |

---

## 2. Ce qui manquait — fonctionnel

| # | Constat | Traité |
| --- | --- | --- |
| F1 | Aucun état du serveur à l'écran. Le juge apprenait la panne **en plein geste**, au moment où quelque chose échouait. | Voyant permanent dans la barre. |
| F2 | Le voyant, une fois ajouté, **mentait**. Il ne se mettait à jour qu'à l'occasion d'un échange utile : un envoi (il n'y en a que si le juge scanne) ou le catalogue, **toutes les cinq minutes**. Un téléphone posé pendant que le réseau tombe affichait « Serveur joignable » cinq minutes durant. | Vérification `/health` toutes les 30 s, sautée dès qu'autre chose vient de parler. ~200 octets par téléphone et par demi-minute. |
| F3 | Aucune trace de ce qui venait d'être envoyé. « Est-ce que j'ai bien envoyé ? » n'avait pas de réponse. | Journal des cinq dernières validations. |
| F4 | Les compteurs de file et de refus n'apparaissaient nulle part sur l'écran principal. | Bande sous la barre, qui ouvre les réglages. |
| F5 | « Reset » avait exactement le poids d'« Envoyer » et se trouvait **juste dessous** : un pouce qui glisse perdait le scan. | Dé-emphasé, renommé, et confirmé par un dialogue. |
| F6 | Le toast de scan affichait l'identifiant interne anglais : « climber Identifiant 42 valide ». | Libellé français. Le toast de **succès** est supprimé : la carte passe au vert et garde le nom, alors que le toast recouvrait « Envoyer » deux secondes — exactement où le pouce va ensuite. |
| F7 | Une carte pouvait passer au vert **en affichant « À scanner »** : le serveur accepte le QR sans renvoyer de libellé. Deux informations contradictoires. | Repli sur le dossard brut : moins joli, mais vrai. |
| F8 | Les réglages n'avaient ni titre ni retour visible, et ouvraient sur le numéro de version — l'information la moins utile de l'écran. | Barre avec titre et flèche, sections, version reléguée en bas. |
| F9 | Rien n'indiquait **à quel serveur** le téléphone parle. C'est la première question qu'on pose à un juge qui dit « ça ne marche pas », et il fallait démonter l'APK pour y répondre. | Adresse affichée dans les réglages. |
| F10 | Français fautif ou non accentué dans presque tous les libellés (« Envoi refuse », « Error dans l'adresse »), et un réglage nommé « Mode auto evalutation » — faute de frappe **et** nom qui ne dit rien à un bénévole. | Libellés repris. Le réglage devient « Garder le grimpeur entre deux blocs », avec son explication sous le titre. |

---

## 3. Ce qui manquait — visuel

| # | Constat | Traité |
| --- | --- | --- |
| D1 | `dynamicColor` était actif : Android reprend les couleurs du fond d'écran. Sur 25 téléphones de bénévoles, **25 palettes** — alors qu'ici la couleur porte l'information (vert = scanné). Sur certains appareils, le « vert » n'était plus vert. | Thème fixe, palette tirée des couleurs de circuit du club. |
| D2 | L'application suivait le mode clair/sombre du système. Une salle d'escalade est mal éclairée, et un écran clair éblouit quand on lève les yeux vers le mur. | Sombre, toujours. |
| D3 | La **fenêtre Android** héritait de `Material.Light` : flash blanc à chaque lancement, et icônes de barre d'état sombres posées sur notre barre sombre. | Fenêtre sombre, icônes claires. |
| D4 | Trois boutons de même poids. Pire : « Envoyer » désactivé était rempli de la couleur exacte d'une carte non scannée — trois cartes grises identiques, et rien ne disait laquelle était l'action. | Cartes à remplir → bouton cerclé d'un trait qui attend → bouton bleu plein quand il est prêt. |
| D5 | Le logo occupait 100 dp, un quart de la hauteur utile sur un petit téléphone. Réduit, il devenait un **carré blanc** : le PNG fait 1414×1000 à fond blanc opaque, avec beaucoup de marge autour du dessin. | 34 dp, recadré au carré (`logo_rond.png`) pour pouvoir être détouré en rond. Le dessin d'origine reste dans `AnnonayEscaladeLogo/`. |
| D6 | Photo en fond plein écran : contraste variable sous le texte selon l'endroit, et 1,6 Mo d'APK. | Retirée. |
| D7 | L'interligne par défaut était fixé à **24 sp**, appliqué tel quel à des textes de 13 sp — près du double de ce qu'il faut. | Interligne naturel, proportionnel à la taille. |
| D8 | L'interrupteur des réglages, éteint, était presque invisible : sa piste est `surfaceVariant`, à deux points de gris de la carte qui la porte. C'est pourtant l'état qu'un bénévole doit lire d'un coup d'œil. | Couleurs d'état explicites, les mêmes que le reste de l'application. |
| D9 | Les compteurs, posés dans le slot `actions` de la barre, passaient **par-dessus** « Serveur joignable » dès qu'il y en avait deux. Le slot `actions` ne comprime pas le titre. | Bande dédiée sous la barre. |

---

## 4. Comment ça a été vérifié

Trois des défauts ci-dessus — D5, F10 et D9 — **ne sont apparus qu'à l'écran**.
Relire le code ne les montrait pas : le logo semblait correct, la chaîne
« Reset » se lisait dans un fichier qu'on ne relit pas, et le chevauchement des
pastilles dépend d'une règle de mise en page qu'aucun test ne couvrait.

Tout a donc été regardé sur l'émulateur, avec un backend local et le jeu de
données de développement :

- l'écran au repos, l'écran prêt à envoyer, la bande de file, le dialogue de
  confirmation, les réglages ;
- la bascule **joignable → injoignable → joignable**, obtenue en gelant puis en
  relançant gunicorn, pour voir le voyant suivre dans les deux sens.

Côté tests : 129 tests JVM verts. Les trois nouveaux (le sondage `/health`)
ont été vérifiés en **retirant la protection pour les voir tomber** — sans
quoi un test qui passe ne prouve rien.

---

## 5. Ce qui reste ouvert

- **Le scan d'un QR imprimé sur un vrai téléphone n'a pas été testé.**
  L'émulateur n'a pas de caméra exploitable pour ML Kit. À faire avant
  novembre, avec la coupure de wifi en cours de saisie.
- **Aucun test d'interface automatisé.** Les écrans sont vérifiés à l'œil, avec
  captures. Un socle Compose UI test serait le prochain filet utile.
- **Le poids de l'APK n'a pas été mesuré en release.** Le build de debug pèse
  64 Mo, dominé par ML Kit ; le retrait de la photo de fond en enlève 1,6.
