# Architecture — spec 008, l'import HelloAsso

Ce document répond à « comment c'est construit ». Le « quoi » et le « pourquoi »
sont dans [`spec.md`](spec.md).

## 1. Le principe, en une phrase

**HelloAsso alimente une salle d'attente ; c'est la salle d'attente qui décide
si un participant est créé.**

Rien de ce qui vient du réseau n'écrit directement dans `participant`. C'est la
même séparation que la spec 002 a introduite entre la base et le classeur : la
source extérieure est une **entrée**, jamais une autorité.

```
   HelloAsso                    climbcontest                       humain
   ─────────                    ────────────                       ──────
                         ┌──────────────────────────┐
  /oauth2/token  ◄────── │ helloasso/client.py      │
                         │  jeton en base, 1 verrou │
                         └──────────┬───────────────┘
  /v5/.../items          ┌──────────▼───────────────┐
  ?from=…&withDetails ──►│ helloasso/releve.py      │
                         │  pagination, idempotence │
                         └──────────┬───────────────┘
                         ┌──────────▼───────────────┐
                         │ helloasso/correspondance │  naissance → circuit
                         │  le barème, le genre,    │  genre     → F / H
                         │  les deux champs         │  champ     → club
                         └──────────┬───────────────┘
                         ┌──────────▼───────────────┐
                         │ helloasso/rapprochement  │
                         │  homonyme ? même date ?  │
                         └──────────┬───────────────┘
                                    ▼
                         ┌──────────────────────────┐      ┌──────────────┐
                         │ table `inscription`      │─────►│ vue          │
                         │  a_trancher / a_imprimer │      │ Inscriptions │
                         │  faite / ignoree         │◄─────│ + pastille   │
                         └──────────┬───────────────┘      └──────────────┘
                                    │ sans ambiguïté (D2)          │ tranche
                                    ▼                              ▼
                         ┌──────────────────────────┐
                         │ contest.ajouter_participant_numerote()  │
                         │  le MÊME chemin que le bouton « Ajouter » │
                         └──────────────────────────┘
```

Le dernier encadré est important : l'inscription en ligne n'a **pas** son propre
chemin de création. Elle appelle la fonction que la console appelle déjà, avec
`source="helloasso"`. Deux chemins de création divergeraient au premier
correctif — c'est ce qui est arrivé à `Competition.statut` (spec 018).

## 2. Le modèle de données

### 2.1 Une table, `inscription`

```python
class Inscription(db.Model):
    """Une ligne de HelloAsso, et ce qu'on en a fait.

    Elle survit au participant qu'elle a créé : c'est la trace de ce que la
    plateforme a dit, et la seule chose qui rende le relevé idempotent.
    """
    __tablename__ = "inscription"
    __table_args__ = (
        # L'idempotence tient ICI, pas dans le code du relevé. Un article
        # HelloAsso relevé dix fois -- ce qui arrive a chaque fois que sa date
        # de mise a jour retombe dans la fenetre `from=` -- ne peut produire
        # qu'une ligne.
        UniqueConstraint("competition_id", "article_id", name="uq_inscription_article"),
    )

    id             = Column(Integer, primary_key=True)
    competition_id = Column(Integer, ForeignKey("competition.id"), nullable=False)

    article_id     = Column(Integer, nullable=False)   # item.id chez HelloAsso
    commande_id    = Column(Integer)                   # order.id, pour retrouver la fratrie

    etat           = Column(String(20), nullable=False, default=A_TRANCHER)
    motif          = Column(String(30))                # pourquoi ça attend
    participant_id = Column(Integer, ForeignKey("participant.id"))

    nom            = Column(String(80))
    prenom         = Column(String(80))
    date_naissance = Column(Date)                      # fait la catégorie ET le rapprochement
    club           = Column(String(80))
    categorie      = Column(String(20))                # composée : circuit + genre
    tarif          = Column(String(120))               # le nom du tarif, tel quel

    etat_helloasso = Column(String(20))                # Processed, Canceled…
    maj_le         = Column(DateTime)                  # item.meta.updatedAt
    recue_le       = Column(DateTime, default=func.now())
    traitee_le     = Column(DateTime)
    traitee_par    = Column(String(80))
```

**Il n'y a pas de colonne `detail`, et pas de colonne `courriel`** — décision D5
du 03/09. Les colonnes ci-dessus *sont* l'enregistrement ; il n'existe nulle part
de copie du JSON reçu. Deux conséquences, et elles vont dans le bon sens :

- pour relire une inscription avec une correspondance corrigée, on **redemande**
  l'article à HelloAsso au lieu de rejouer une copie locale. L'idempotence rend
  l'opération gratuite, et c'est moins de code que le rejeu ;
- `commande_id` reste, parce que c'est un entier qui ne décrit personne. C'est
  lui qu'on lit à l'écran pour retrouver la commande dans le back-office quand
  il faut joindre quelqu'un — le courriel est là-bas, et il y a sa place.

Quatre états, et ils décrivent un **geste physique**, pas un état informatique :

| `etat` | Ce que ça veut dire | Ce qui le fait bouger |
| --- | --- | --- |
| `a_trancher` | Un humain doit dire quelque chose | Il clique |
| `a_imprimer` | Le participant existe, le papier n'est pas sorti | « Imprimer » ou « Déjà remis » |
| `faite` | Le dossard est entre ses mains | — |
| `ignoree` | Mise de côté volontairement | Réouverture possible |

`motif` dit **pourquoi** ça attend, et c'est ce que la carte affiche :
`doublon_possible`, `categorie_inconnue`, `sans_nom`, `annulee_apres_coup`.

### 2.2 Les réglages, à deux étages

C'est le point de conception le moins évident, et il vient d'un fait : le club a
**un** compte HelloAsso, mais **une** compétition par an.

| Quoi | Où | Pourquoi là |
| --- | --- | --- |
| `client_id`, `client_secret`, `refresh_token` | `shared/secrets/helloasso.json` | Même raisonnement que `token.json` : hors du dépôt, hors des releases, hors de la sauvegarde. Un secret ne se restaure pas, il se repose |
| Environnement (`production` / `sandbox`), `organisation_slug`, date du dernier relevé, dernière erreur | table `reglage`, clé `helloasso` | **Global au serveur**, comme le plan du mur. Et en base : `climbcontest-sauvegarde` ne recopie que la base |
| Formulaire choisi (`form_type` + `form_slug`) et **la correspondance** | `competition.options["helloasso"]`, via `cycle.ecrire_options()` | **Par édition.** Le formulaire change chaque année, les tarifs aussi |

`cycle.ecrire_options()` fusionne sans écraser les clés voisines — c'est déjà sa
raison d'être, on n'ajoute rien.

Forme de la correspondance, après la décision D1 :

```json
{
  "form_type": "Event",
  "form_slug": "bloc-party-2026",

  "champs": { "naissance": "Date de naissance", "club": "Votre club" },

  "bareme": [
    { "circuit": "U11", "de": 2016, "a": 2017, "mixte": false },
    { "circuit": "U13", "de": 2014, "a": 2015, "mixte": false },
    { "circuit": "U15", "de": 2012, "a": 2013, "mixte": false },
    { "circuit": "Adulte", "de": 1950, "a": 2008, "mixte": true }
  ],

  "genre": {
    "source": "champ",
    "champ": "Sexe",
    "valeurs": { "Fille": "F", "Garçon": "H", "F": "F", "M": "H" }
  }
}
```

Trois choses à ne pas confondre dans ce document :

- **`bareme` est une liste, pas un dictionnaire.** Deux circuits peuvent se
  recouvrir — c'est une erreur, mais elle doit pouvoir être *enregistrée* pour
  être *montrée*. Un dictionnaire indexé par année rendrait le recouvrement
  inexprimable, donc invisible, donc impossible à corriger.
- **`genre.source`** vaut `"champ"` ou `"tarif"`. Une seule source, choisie ;
  pas deux mécanismes qui se marchent dessus.
- **`genre.valeurs`** range les réponses *réellement vues* dans le formulaire.
  « Fille », « F » et « Féminin » sont trois écritures de la même chose, et
  aucune règle générale ne les couvre toutes. Une valeur absente de ce
  dictionnaire n'est pas `H` par défaut : elle rend le genre **indéterminé**, et
  l'inscription passe en `a_trancher`.

### 2.3 bis Le barème, et son contrôle

`correspondance.proposer_bareme(competition, circuits)` calcule une proposition
depuis la date de l'édition : pour une saison qui commence en `A`, `U(n)` prend
les années `A-n+1` et `A-n+2`. Une compétition du 15/11/2026 est dans la saison
2026-2027, donc `U13` → 2014-2015.

C'est une **proposition**, jamais une contrainte : `contraintes-metier.md` §4
dit que les catégories changent d'une édition à l'autre, et rien ne garantit des
tranches de deux ans. La fonction propose, la console affiche, l'organisateur
corrige.

`correspondance.controler(bareme, categories_connues)` rend une liste d'anomalies
— même forme que `cascade.controler()`, qui attrape les phrases mortes :

| Anomalie | Ce qui la déclenche |
| --- | --- |
| `recouvrement` | Une année dans deux circuits |
| `trou` | Une année entre deux circuits, sans circuit |
| `circuit_vide` | Un circuit dont l'intervalle ne prend aucune année |
| `categorie_inconnue` | `circuit + genre` ne figure pas dans les catégories de l'édition |

Le dernier contrôle est celui qui compte : il attrape le circuit `Adulte` qu'on
a oublié de marquer *mixte* et qui compose « Adulte F » — une catégorie qui
n'existe nulle part, et donc un classement d'une personne. C'est le même défaut
que les « catégories orphelines » de la spec 019, pris en amont.

### 2.4 Une colonne de plus sur `participant`

D1 en fait une nécessité : `participant.date_naissance`, **nullable**.

Sans elle, la date de naissance ne vivrait que sur l'inscription. Un participant
saisi au guichet n'en aurait jamais, et le rapprochement devrait aller la
chercher par un chemin détourné — l'inscription qui a créé le participant, quand
il y en a une. C'est exactement le genre d'indirection qui se casse au premier
cas particulier.

Elle est nullable et le restera : les participants venus du classeur n'en ont
pas, et un import de classeur ne doit pas se mettre à échouer pour ça.

### 2.5 Migration

- La table `inscription` : `db.create_all()`, comme `Archive` (spec 018) et
  `Reglage` (spec 029).
- La colonne `participant.date_naissance` : une entrée dans `COLONNES_AJOUTEES`
  de `schema.py`. Le mécanisme existe, il est idempotent, il tourne sous le
  verrou de démarrage — rien à écrire d'autre qu'une ligne.

**Aucune destruction, aucune réécriture.** Un retour arrière de release laisse la
table et la colonne en place : l'ancienne version les ignore, elle ne tombe pas
dessus.

## 3. `helloasso/client.py` — l'authentification

### Le jeton vit en base, et un seul worker le rafraîchit

C'est la contrainte la plus dure du fournisseur, et elle est explicite dans sa
documentation :

> Lorsqu'un refresh token A est utilisé, un nouveau refresh token B est renvoyé.
> Si une nouvelle utilisation du refresh token A est faite, alors un nouveau
> refresh_token C est créé et **B est révoqué**.

Avec quatre workers gunicorn et un jeton gardé en mémoire vive, deux
rafraîchissements simultanés **se révoquent l'un l'autre**. Le symptôme serait le
pire qui soit : ça marche en développement (un seul processus), et ça tombe en
production au bout de trente minutes, un jour de compétition.

D'où :

1. le couple `access_token` / `refresh_token` est **lu et écrit en base** ;
2. le rafraîchissement prend le verrou `helloasso_jeton` de la table `verrou` —
   celui-là même que le miroir utilise déjà ;
3. celui qui n'obtient pas le verrou **relit** la base : le voisin vient
   probablement d'y déposer un jeton frais.

Les quotas d'authentification (10 / 10 s, 20 / 10 min, **50 / h**) sont alors
consommés à raison de **2 appels par heure** : un rafraîchissement toutes les
30 minutes.

### La surface

```python
class ClientHelloAsso:
    def formulaires(self) -> list[dict]          # GET /organizations/{slug}/forms
    def formulaire(self, type, slug) -> dict     # GET .../public — tarifs et champs
    def articles(self, type, slug, depuis) -> Iterator[dict]
```

`articles()` est un **générateur** : il rend les articles page par page et ne
charge jamais la totalité en mémoire. Le relevé peut ainsi écrire au fil de
l'eau, et une coupure au milieu ne perd que la page en cours.

### Les erreurs, typées

`ErreurHelloAsso(message, code)` sur le modèle exact d'`ErreurClasseur` : elle ne
fait jamais échouer une requête de juge, elle retarde un relevé. Trois familles,
parce que les trois appellent trois gestes différents :

| Famille | Ce que la console affiche |
| --- | --- |
| Pas de clé posée | « HelloAsso n'est pas relié » |
| Clé refusée / `refresh_token` périmé (401, 403) | « Clé à reconnecter » — et **le fil s'arrête d'essayer** |
| Réseau, 429, 5xx | « HelloAsso injoignable » — on retente à la cadence normale |

La deuxième ligne est celle qui compte : continuer à retenter avec une clé morte
brûlerait le quota d'authentification et rendrait la reconnexion impossible.

## 4. `helloasso/releve.py` — le relevé incrémental

### La requête

```
GET /v5/organizations/{org}/forms/{type}/{slug}/items
    ?from={dernier_vu - 5 min}
    &sortField=UpdateDate
    &sortOrder=Asc
    &withDetails=true
    &pageSize=100
    &continuationToken=…
```

Trois choix, trois raisons :

- **`sortField=UpdateDate`** et non `Date` : une commande modifiée après coup —
  une annulation, une correction de nom — a une date de création ancienne. Trier
  par date de création la rendrait invisible pour toujours.
- **`from = dernier_vu − 5 min`** : un recouvrement volontaire. Les horloges ne
  sont pas les mêmes des deux côtés, et un article pile à la seconde de la borne
  serait perdu. Le recouvrement ne coûte rien — la contrainte d'unicité absorbe.
- **`withDetails=true`** : sans lui, pas de `customFields`, donc pas de club et
  pas de date de naissance. C'est la moitié de l'information.

### La pagination, telle que HelloAsso la décrit

> Le signal de fin n'est pas l'absence de `continuationToken`, mais **l'absence
> de résultats**.

On suit leur règle, pas notre intuition :

```python
while True:
    page = appel(continuation_token=jeton)
    articles = page.get("data") or []
    if not articles:
        break                       # ← la seule condition d'arrêt
    yield from articles
    jeton = (page.get("pagination") or {}).get("continuationToken")
    if not jeton:
        break                       # ceinture : le token a disparu
```

`totalCount` vaut `-1`. Aucun compteur ne s'en déduit ; le total affiché par la
console est celui qu'on a compté nous-mêmes.

### Ce qui est écrit pour chaque article

| Champ HelloAsso | Devient |
| --- | --- |
| `item.id` | `article_id` — la clé d'idempotence |
| `item.user.firstName / lastName` | `prenom` / `nom`, passés par `formatage.mots()` |
| *(à défaut)* `order.payer.firstName / lastName` | idem, **et** `motif = sans_nom` |
| `item.name` ou `item.tierDescription` | `tarif` — conservé **pour l'affichage**, il ne décide plus de rien (D1) |
| `customFields[nom == champs.naissance].answer` | `date_naissance` |
| `bareme` ∋ année de `date_naissance` | le **circuit** |
| `genre.valeurs[réponse]` *(champ ou tarif selon `genre.source`)* | le **genre** |
| circuit + genre | `categorie` — ou le circuit seul s'il est `mixte` |
| `customFields[nom == champs.club].answer` | `club`, par `formatage.mots(sigles=True)` |
| `order.id` | `commande_id` |
| `item.state` | `etat_helloasso` |
| `item.meta.updatedAt` | `maj_le` — c'est lui qui fait avancer le curseur |
| Tout le reste — payeur, montants, moyens de paiement, reçus | **jeté, jamais écrit** (D5) |

`formatage.py` est réutilisé tel quel. La remarque de son en-tête — « ce module
ne touche jamais à ce qui est importé du classeur » — ne s'applique pas ici :
HelloAsso n'est pas une source qui fait autorité sur sa propre mise en forme,
c'est **du texte tapé par un parent sur un téléphone**. « DUPONT », « dupont » et
« Dupont » doivent tomber dans la même liste déroulante que la saisie manuelle.

### L'écriture est transactionnelle par article

Un article = un `commit`. Cent articles qui passent et un qui échoue laissent
cent inscriptions écrites, pas zéro. C'est le comportement du `Rapport` de
l'import du classeur, et pour la même raison : **un import muet qui perd un
grimpeur est pire qu'un import bruyant**.

## 5. `helloasso/rapprochement.py` — le doublon

Une fonction pure, sans base ni Flask, comme `formatage.py` — c'est ce qui
permet de l'éprouver par une table de cas.

```python
def confronter(candidat: Personne, existants: list[Personne]) -> Verdict
```

`Verdict` ∈ `NOUVEAU` · `MEME_PERSONNE(id)` · `DEUX_PERSONNES` · `A_TRANCHER`.

La clé de comparaison :

```python
def cle(nom, prenom) -> str:
    """« Jean-Luc DUPONT » et « jean luc dupont » donnent la même chaîne."""
    # minuscules, accents retirés, séparateurs de formatage.SEPARATEURS
    # ramenés à un espace, blancs réduits
```

Et la table de décision est exactement celle du §4 de la spec. Ce qui compte
architecturalement, c'est que la **date de naissance est la seule preuve
acceptée** pour fusionner sans demander. Deux enfants du même club portant le
même prénom et le même nom, ça se voit dans un club d'escalade ; deux enfants du
même nom **et** de la même date de naissance, non.

## 6. `helloasso/planificateur.py` — le fil

Copie conforme de `sheets/planificateur.py`, y compris ses deux qualités qui ont
été payées cher :

1. **il ne meurt jamais** — un `except Exception` autour du corps de boucle, et
   il continue ;
2. **il ne répète pas sa plainte** — on journalise ce qui *change*, pas ce qui
   dure. Une heure sans réseau produit une ligne, pas soixante.

La cadence n'est pas une constante mais une fonction de l'état de la compétition
(§F3 de la spec). Le fil **ne démarre pas du tout** si aucune clé n'est posée :
zéro appel réseau tant que HelloAsso n'est pas relié.

La dernière erreur est exposée par `/health`, comme celle du miroir. Le 30/08,
714 réussites attendaient et il a fallu ouvrir un SSH pour apprendre pourquoi ;
on ne recommence pas.

## 7. Les routes

Toutes sous `/admin`, toutes derrière `@exige_role`.

| Méthode | Route | Rôle | Ce qu'elle fait |
| --- | --- | --- | --- |
| `GET` | `/admin/helloasso` | **admin** | État : clé posée ou non, environnement, formulaire, dernier relevé, dernière erreur. **Jamais le secret** |
| `POST` | `/admin/helloasso/cle` | **admin** | Pose `client_id` + `client_secret`, demande un premier jeton. Répond « posée » ou « refusée » |
| `DELETE` | `/admin/helloasso/cle` | **admin** | Débranche. Le fichier de secret est effacé, le fil s'arrête |
| `GET` | `/admin/helloasso/formulaires` | **admin** | La liste des formulaires du club |
| `POST` | `/admin/helloasso/formulaire` | **admin** | Choisit le formulaire de la compétition active, et **découvre** ses tarifs et ses champs |
| `GET` · `POST` | `/admin/helloasso/correspondance` | organisateur | Lit et enregistre la correspondance tarifs → catégories, champs → club / naissance |
| `POST` | `/admin/helloasso/relever` | organisateur | Relève maintenant. Répond le compte de ce qui est arrivé |
| `GET` | `/admin/inscriptions` | organisateur | Les trois piles, avec leurs compteurs |
| `POST` | `/admin/inscriptions/<id>/trancher` | organisateur | `{"choix": "meme_personne" \| "deux_personnes" \| "ignorer" \| "categorie", …}` |
| `POST` | `/admin/inscriptions/<id>/remise` | organisateur | Marque le dossard remis |

Le compteur de la pastille voyage dans la réponse de `/admin/moi`, comme celui
des mises à jour : la console l'a déjà sous la main à chaque écran, aucune
requête supplémentaire.

## 8. Le webhook — ce qu'on n'active pas, et pourquoi c'est écrit ici

Un lecteur qui reprendra ce dossier dans six mois se demandera pourquoi le
temps réel se fait par sondage alors que HelloAsso propose des notifications.
Trois raisons, toutes vérifiées dans leur documentation le 03/09 :

1. **On ne peut pas vérifier qu'elles viennent d'eux.** La signature HMAC
   `x-ha-signature` est « disponible **uniquement pour les partenaires** ». Une
   association ne dispose que de l'adresse IP source (`51.138.206.200`) —
   c'est-à-dire d'un contrôle qui traverse un reverse proxy, un NAT domestique
   et un `X-Forwarded-For`.
2. **Le corps ne porte pas les champs utiles.** L'exemple de notification
   `Order` de leur documentation n'a **pas** de `customFields`. Il faudrait
   rappeler l'API de toute façon.
3. **Le gain est de quelques dizaines de secondes**, contre une route publique
   non authentifiée ouverte sur Internet, sur une ligne domestique.

Si le besoin apparaissait, la forme est déjà écrite : `POST /api/helloasso/notification`
qui **ne lit rien du corps** et se contente de réveiller le fil. Le réveil n'est
pas une donnée, il ne peut donc pas mentir.

## 9. Les fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/helloasso/__init__.py` | **nouveau** |
| `climbcontest/helloasso/client.py` | **nouveau** — OAuth, verrou, pagination |
| `climbcontest/helloasso/correspondance.py` | **nouveau** — découverte, barème, `proposer_bareme()`, `controler()` |
| `climbcontest/helloasso/releve.py` | **nouveau** — le relevé et son rapport |
| `climbcontest/helloasso/rapprochement.py` | **nouveau** — fonction pure |
| `climbcontest/helloasso/planificateur.py` | **nouveau** — le fil |
| `climbcontest/models.py` | +`Inscription`, +constantes d'état, +`Participant.date_naissance` |
| `climbcontest/schema.py` | +1 ligne dans `COLONNES_AJOUTEES` |
| `climbcontest/routes/admin.py` | +10 routes ; `/admin/moi` porte le compteur |
| `climbcontest/templates/admin.html` | +vue *Inscriptions*, +page *HelloAsso*, +pastille |
| `climbcontest/__init__.py` | démarrage conditionnel du fil |
| `climbcontest/routes/sante.py` | `/health` expose la dernière erreur HelloAsso |
| `climbcontest/cycle.py` | l'effacement des données emporte les inscriptions |
| `tools/dump_helloasso.py` | **nouveau** — lecture seule |
| `.gitleaks.toml` | motif pour les clés HelloAsso |
| `requirements.txt` | rien — `requests` est déjà là |
| `docs/specs-index.md`, `CHANGELOG.md` | une ligne chacun |

⚠️ `admin.html` et `docs/specs-index.md` sont les deux fichiers que la spec 038
désigne comme ceux « que toutes les PR se disputent ». Trois autres sessions
touchent l'index en ce moment. Le conflit sera additif ; il se résout à la main.

## 10. Ce qui ne bouge pas

- **Le miroir vers le classeur.** Il envoie des réussites. Une inscription n'en
  est pas une.
- **L'import du classeur** (`sheets/importer.py`). Les deux flux d'alimentation
  cohabitent et ne se connaissent pas ; c'est le rapprochement qui les fait se
  rencontrer, au niveau du participant.
- **Le catalogue de l'app juge.** La création d'un participant incrémente déjà
  `catalogue_version` — les vingt-cinq téléphones voient l'inscrit en moins de
  vingt secondes, sans une ligne de code de plus.
- **Le classement.** Il ne connaît que `participant`. La table `inscription` lui
  est invisible.
