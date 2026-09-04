# Spec 043 — les mentions, et la page qui ne s'indexe pas

## 1. D'où vient cette spec

Adrien, le 04/09/2026 :

> « Regarde comment on peut faire pour sécuriser aussi les APIs de résultat car
> comme nous affichons des infos sur des enfants je pense qu'on est obligé de
> sécuriser un minimum, regarde ce que nous sommes obligés de faire au regard
> de la loi et vois ce que tu peux adapter dans notre projet, mais il faut que
> ça reste simple pour les spectateurs. »

L'étude complète est dans
[docs/rapports/2026-09-04-donnees-personnelles-resultats.html](../../docs/rapports/2026-09-04-donnees-personnelles-resultats.html) :
inventaire de ce qui sort de `/api/public/*`, les huit obligations du RGPD avec
l'état du dépôt en face, et un plan en quatre niveaux.

Après lecture, Adrien a **réduit le périmètre à quatre livrables** :

> « Je veux que tu ajoutes le pas d'indexation, la mention et page de
> confidentialité qui doit être accessible depuis la page de résultat via une
> mention discrète, pareil pour le droit d'opposition. Enfin ajoute le registre
> des traitements. Tout le reste est écarté. »

## 2. Ce qu'on cherche

Que la page de résultats reste **exactement aussi simple qu'aujourd'hui pour un
spectateur** — aucun compte, aucun jeton, aucun geste — tout en cessant d'être
une publication de noms d'enfants qui laisse une trace durable et dont personne
n'a été informé.

Le résultat visé tient en trois phrases : les moteurs de recherche n'indexent
plus la page ; qui la regarde peut savoir en un clic ce qui est publié et
comment s'y opposer ; et le club détient le document que la loi lui demande de
tenir.

## 3. Ce qui est décidé

### D1 — Les noms restent complets

Trois rendus ont été montrés côte à côte dans l'étude (§4) : nom complet, abrégé
« Prénom N. », dossard seul. **Adrien retient le nom complet, inchangé.**

⚠️ **La conséquence est à écrire, pas à sous-entendre.** La minimisation était
l'amortisseur du dossier ; sans elle, la non-indexation et l'information cessent
d'être des améliorations pour devenir ce qui rend la position tenable. Ce n'est
pas une objection à la décision — c'est ce qui donne son poids à D2 et D3.

Corollaire : **le mur affiche la même chose que les téléphones**, et aucune
route séparée pour le vidéoprojecteur n'est à construire. La réponse JSON est
mise en cache 5 s par Caddy pour tout le monde ; elle ne peut pas dépendre de
qui regarde.

### D2 — La page ne s'indexe pas, et c'est l'application qui le dit

Trois surfaces, une seule origine :

| Où | Quoi |
| --- | --- |
| `GET /robots.txt` | servi par l'application, `Disallow: /` |
| Page de résultats | `<meta name="robots" content="noindex, nofollow">` |
| `/api/public/*` | en-tête de réponse `X-Robots-Tag: noindex` |

⚠️ **Posé dans Flask, pas dans le Caddyfile de `edge`.** La configuration du
proxy est recopiée à la main et dérive dans les deux sens ; un en-tête écrit
ici voyage avec le code, se relit dans le dépôt et **se teste**. Caddy peut le
doubler un jour ; il ne doit pas le porter seul.

⚠️ La console (`/console`) et l'application juge (`/juge`) prennent le même
traitement : elles n'ont aucune raison d'être indexées non plus, et l'oubli se
verrait plus tard que la pose.

### D3 — La mention discrète, variante A

Trois formulations ont été injectées dans la **page de résultats réelle** et
capturées : `maquettes/index.html`. **La variante A est proposée** :

```
Confidentialité   ·   Retirer un nom des résultats
```

Une ligne, deux liens. C'est ce que demande « pareil pour le droit
d'opposition » : les deux chemins sont atteignables **depuis la page**, et non
seulement depuis la page de confidentialité une fois qu'on y est arrivé.

Écartées : **B** (« Les résultats affichent le nom des participants. En savoir
plus et s'y opposer ») — dit plus, mais prend deux lignes sur un téléphone et
cesse d'être discrète ; **C** (un seul lien « Confidentialité ») — la plus
légère, mais l'opposition n'est plus annoncée.

Deux propriétés, vérifiées dans le navigateur avant d'écrire une ligne :

1. **Elle disparaît en mode mur.** Avec `body.mur`, le pied calcule
   `display: none`. Le vidéoprojecteur ne montre aucune mention — personne n'y
   cliquera jamais.
2. **Elle se place à la fin de `#defile`, pas après `<main>`.** La page est une
   colonne flex, `main` vaut `flex: 1`, et la liste **déborde visiblement** de
   sa boîte sur téléphone. Un pied posé après `main` s'affiche à 790 px du haut,
   recouvert par le classement. C'est arrivé à la première tentative de capture.

### D4 — Une page `/confidentialite`, servie par l'application

Un gabarit du dépôt, pas un lien vers un site extérieur. Trois raisons : elle
est versionnée avec le code qu'elle décrit ; elle reste joignable si le wifi de
la salle ne sort pas ; et elle suit le thème clair/sombre de la page de
résultats.

Elle dit, en français simple et court :

- **qui** est responsable du traitement (le club, avec son adresse de contact) ;
- **ce qui est publié** : nom, prénom, club, catégorie, dossard, score, rang et
  nombre de blocs des participants classés ;
- **pourquoi** : l'intérêt légitime à publier les résultats d'une compétition
  sportive (art. 6.1.f) ;
- **comment s'y opposer** — l'ancre `#opposition`, cible du second lien, avec
  l'adresse de contact **`adrien.jouve@adn-dev.fr`** (choix d'Adrien du 04/09 :
  « pour le moment laisse la mienne ») ;
- **les droits** (accès, rectification, effacement, opposition), le fait que
  l'effacement des données collectées pendant la **minorité** se traite « dans
  les meilleurs délais » et que la réponse est due sous **un mois**, et la
  possibilité de saisir la CNIL.

⚠️ La politique du dépôt `climbcontestConfidentiality` **n'est pas celle-ci** :
elle couvre l'application juge du Play Store et affirme « aucune donnée
personnelle liée à l'utilisateur de l'Application n'est collectée ». C'est exact
pour le juge et faux pour le système. Sa réécriture est **hors périmètre de
cette spec** mais reste à faire ; elle est notée dans la section 6.

### D5 — Le droit d'opposition est annoncé, et il est **exerçable**

Le lien « Retirer un nom des résultats » mène à `/confidentialite#opposition`,
qui dit à qui écrire et ce qui se passe ensuite.

**Décidé le 04/09**, après que la spec l'ait signalé comme point ouvert :

> « Oui je suis d'accord pour avoir une sorte d'interrupteur dans la liste des
> participants pour anonymiser un participant. »

Un droit qu'on annonce sans pouvoir le servir ne vaut rien : sans cet
interrupteur, satisfaire un parent qui appelle supposait de **supprimer le
grimpeur**, ce qui décale le rang de tous ceux qui le suivent.

#### La colonne

`participant.publication_refusee` — booléen, **faux par défaut**.

⚠️ **Le nom dit le sens de la case, et le sens décide de ce que vaut le vide.**
L'article 21 est un droit d'*opposition*, pas un consentement : **on publie sauf
refus**. Un champ `diffusion_autorisee` inverserait la charge et rendrait muet
tout inscrit qui n'a rien exprimé — c'est-à-dire presque tous. Un champ qu'on ne
peut pas lire à l'envers est un champ qui ne se retourne pas dans six mois.

#### Dans la console — colonne « Anonymisé »

Deux formes ont été capturées sur la console réelle
(`maquettes/index.html`, §3). **La variante A est proposée** : une colonne
« Anonymisé », interrupteur **allumé = anonymisé**.

| | | Verdict |
| --- | --- | --- |
| **A** | « Anonymisé », allumé = anonymisé. La liste reste calme, l'exception saute aux yeux, et la colonne lit `publication_refusee` **sans l'inverser** | **proposée** |
| B | « Nom publié », allumé = publié. Cent interrupteurs ocre allumés, et c'est l'*éteint* qu'il faut repérer : la couleur souligne la règle au lieu de l'exception | écartée |

⚠️ **La console continue d'afficher le vrai nom.** C'est elle qui sert à
retrouver la personne ; un organisateur qui ne peut plus lire un nom ne peut
plus travailler. Une pastille discrète dit à côté ce que le public voit :
« publié : Dossard 3 ».

L'interrupteur reprend `label.bascule` + `.glissiere` de la spec 021, avec sa
case native conservée sous le visuel et `role="switch"` — le motif de la
spec 042, repris tel quel.

#### Côté public — « Dossard 42 », et le rang ne bouge pas

Deux rendus ont été capturés sur la vraie page (`maquettes/index.html`, §4) :

| | | Verdict |
| --- | --- | --- |
| **« Dossard 42 »** | Le rang, le score et la place sont inchangés. Tient dans la largeur d'un téléphone | **proposé** |
| « Participant anonyme » | Ne dit rien du dossard, mais **ne tient pas** : la colonne le coupe en « Participant an… ». Défaut invisible sur une maquette dessinée | écarté |

⚠️ **On anonymise une ligne, on ne la retire jamais.** Un rang qui saute de 3 à
5 est une information sur celui qui manque.

⚠️ **La sous-ligne garde le club et la catégorie.** Le dossard étant imprimé sur
le bracelet, quelqu'un présent dans la salle peut recouper — c'est-à-dire
exactement le public que couvre déjà l'argument « annoncé au micro ». Les
retirer rendrait le classement moins lisible pour tout le monde, contre un gain
qui ne vaut que hors de la salle, là où le nom a précisément disparu. Ce choix
est **écrit dans la page de confidentialité** plutôt que passé sous silence.

#### Les trois surfaces qui doivent suivre

1. `charge_publique()` — le nom de la ligne devient « Dossard N » ;
2. `suivi.fiche()` — la fiche du grimpeur porte le même nom, sinon le réglage se
   contourne en un clic depuis le classement ;
3. la **recherche** de la page de résultats porte sur le nom de la charge : un
   grimpeur anonymisé cesse donc d'être trouvable par son nom, sans code de
   plus.

⚠️ **L'archive fige le nom réel.** `cycle.archiver` appelle `charge_publique` ;
il l'appellera avec `anonymiser=False`. L'archive est servie derrière la session
organisateur (`@exige_role`) — c'est un usage interne légitime, et une archive
amputée serait irréparable. La règle est celle de l'étude : **on fige complet,
on rend anonymisé.**

### D6 — Le registre des traitements

`docs/registre-des-traitements.md` — trois traitements : **inscriptions**,
**déroulement de la compétition**, **publication des résultats**. Pour chacun :
finalité, base légale, catégories de personnes et de données, destinataires,
durée de conservation, mesures de sécurité. Document, aucun code.

## 4. Hors périmètre, écarté explicitement

| Écarté | Pourquoi c'est écrit ici |
| --- | --- |
| Abrègement des noms | Tranché par D1. Réouvrable sans rien casser. |
| Fenêtre de publication (7 jours) | Retenue au premier tour d'arbitrage, **écartée au second**. Les noms restent en ligne sans terme. |
| Purge des noms dans les archives à un an | Idem. Les archives restent derrière la session organisateur. |
| Jeton dans le lien de la page publique | Écarté : la page reste ouverte à qui a l'adresse. |
| Verrou par liste blanche de la charge publique | Écarté du périmètre. ⚠️ C'est ce qui empêcherait `annee_naissance` (spec 008) d'atteindre la page publique le jour où quelqu'un élargit la jointure de `charge_publique`. |
| Case d'opposition au formulaire HelloAsso | Le champ existe (type `YesNo` de l'API v5, posé par participant) mais il appartient à la spec 008. Elle saura remplir `publication_refusee` dès que cette spec l'a déclarée. |
| Réécriture de la politique du Play Store | Autre dépôt, autre PR. |

## 5. Critères d'acceptation

| # | Critère |
| --- | --- |
| A1 | `GET /robots.txt` répond `200` avec `User-agent: *` et `Disallow: /` |
| A2 | La page de résultats porte `<meta name="robots" content="noindex, nofollow">` |
| A3 | Toute réponse de `/api/public/*` porte l'en-tête `X-Robots-Tag: noindex` — y compris les réponses d'erreur `404` et `409` |
| A4 | `/console` et `/juge` portent aussi la balise `noindex` |
| A5 | La page de résultats affiche en pied, après la dernière ligne du classement, la mention à deux liens |
| A6 | En mode `?mur`, cette mention n'est pas rendue |
| A7 | Le premier lien ouvre `/confidentialite` ; le second `/confidentialite#opposition`, et la section visée est bien celle de l'opposition |
| A8 | `/confidentialite` répond `200`, suit le thème clair/sombre, et se lit sur un téléphone de 390 px sans défilement horizontal |
| A9 | La page de confidentialité nomme le responsable, ce qui est publié, la base légale, les droits, le délai d'un mois, et la CNIL |
| A10 | La mention ne décale ni ne masque aucune ligne de classement : le nombre de lignes affichées est le même avec et sans elle |
| A11 | `docs/registre-des-traitements.md` existe et décrit les trois traitements |
| A12 | Aucune donnée personnelle nouvelle ne sort de `/api/public/*` : la charge est identique, champ pour champ, à celle d'avant la spec |
| A13 | La colonne `publication_refusee` existe, vaut faux pour tout participant existant après migration, et la migration se rejoue sans effet |
| A14 | La liste des participants de la console affiche la colonne « Anonymisé » et son interrupteur reflète l'état en base |
| A15 | Basculer l'interrupteur appelle le serveur et l'état survit à un rechargement |
| A16 | Un participant anonymisé sort de `/api/public/classement` avec `nom = "Dossard N"`, **et son rang, son score et son dossard inchangés** |
| A17 | Le même participant sort de `/api/public/grimpeur/<id>` avec le même nom anonymisé |
| A18 | La recherche de la page de résultats ne trouve plus ce participant par son vrai nom |
| A19 | `cycle.archiver` fige le **nom réel** : l'archive relue par `/admin/archives/<id>/classement` porte le patronyme |
| A20 | La console, elle, affiche toujours le vrai nom, avec la pastille « publié : Dossard N » |

## 6. Cas limites

- **La page servie depuis une archive** (`/console/archives/<id>/resultats`)
  utilise le même gabarit : la mention s'y affiche aussi, ce qui est correct —
  les noms y sont également visibles pour qui a la session.
- **Un moteur qui ignore `robots.txt`** existe. C'est pourquoi la balise et
  l'en-tête sont posés en plus : `noindex` est une consigne de *désindexation*,
  `robots.txt` une consigne de *non-visite*, et les deux ne se remplacent pas.
- **Le cache de Caddy** porte 5 s sur `/api/public/*` : l'en-tête `X-Robots-Tag`
  doit être dans la réponse mise en cache, donc posé par l'application et non
  ajouté après coup.
- **La PWA juge** ne doit pas se mettre à demander `/confidentialite` : la
  mention n'est ajoutée qu'à la page de résultats.

## 7. Ce qui reste ouvert

1. **Comment une opposition reçue est honorée** (D5). Sans mécanisme, la seule
   réponse possible casse le classement.
2. **L'adresse de contact** à écrire sur la page de confidentialité : celle du
   club, ou `adrien.jouve@adn-dev.fr` ? Une adresse d'association survit mieux
   à un changement de bénévole.
3. **Le nom exact du responsable de traitement** — l'association telle qu'elle
   est déclarée.
