# Architecture — spec 008, l'import HelloAsso

Ce document répond à « comment c'est construit ». Le « quoi » et le « pourquoi »
sont dans [`spec.md`](spec.md).

## 1. Le principe

**HelloAsso alimente une salle d'attente ; c'est la salle d'attente qui décide
si un participant est créé.** Rien de ce qui vient du réseau n'écrit directement
dans `participant` — même séparation que la spec 002 entre la base et le
classeur : une source extérieure est une **entrée**, jamais une autorité.

```
   HelloAsso                   climbcontest                      humain
   ─────────                   ────────────                      ──────
                        ┌──────────────────────────┐
  /oauth2/token  ◄───── │ helloasso/client.py      │
                        │  jeton en base, 1 verrou │
                        └──────────┬───────────────┘
  /v5/.../items         ┌──────────▼───────────────┐
  ?from=…&withDetails ─►│ helloasso/releve.py      │
                        │  UNIQUE(compet, article) │ ← ne réimporte pas
                        └──────────┬───────────────┘
                        ┌──────────▼───────────────┐
                        │ categories.py            │  année → U(n)
                        │  la règle FFME, pure     │  le plus petit gagne
                        └──────────┬───────────────┘
                        ┌──────────▼───────────────┐
                        │ helloasso/rapprochement  │  nom + prénom + club
                        │  la clé vient de         │  ← formatage.identite()
                        │  formatage.py            │
                        └──────────┬───────────────┘
                                   ▼
                        ┌──────────────────────────┐     ┌──────────────┐
                        │ table `inscription`      │────►│ vue          │
                        │  a_trancher / a_imprimer │     │ Inscriptions │
                        │  faite / ignoree         │◄────│ + pastille   │
                        └──────────┬───────────────┘     └──────────────┘
                                   │ sans ambiguïté (D2)
                                   ▼
                   contest.ajouter_participant_numerote()
                   ← le MÊME chemin que le bouton « Ajouter »
```

Le dernier encadré compte : l'inscription en ligne n'a **pas** son propre chemin
de création. Deux chemins divergeraient au premier correctif — c'est ce qui est
arrivé à `Competition.statut` (spec 018).

## 2. `categories.py` — la règle, et pourquoi elle est en dehors

Un module **à la racine du paquet**, pas sous `helloasso/`. C'est délibéré : la
règle sert au relevé HelloAsso, **mais aussi** au formulaire d'ajout manuel
(D8), à l'édition en ligne et au bouton « Appliquer à tous ». La ranger sous
`helloasso/` ferait dépendre la saisie au guichet d'une intégration qui peut ne
pas être branchée.

```python
def annee_de_reference(jour: date) -> int:
    """L'annee civile qui sert de reference : celle ou FINIT la saison.

    La saison FFME va du 1er septembre au 31 aout. Une competition de novembre
    2026 est dans la saison 2026-2027, dont l'annee de reference est 2027.
    C'est ce qui fait qu'un grimpeur demarre l'annee dans une categorie et y
    reste : la reference ne bouge pas en cours de saison.
    """
    return jour.year + 1 if jour.month >= 9 else jour.year


def circuit(annee_naissance: int, reference: int, unders: list[int]) -> str | None:
    """« U » veut dire under : le PLUS PETIT Under qui contient l'age gagne."""
    age = reference - annee_naissance
    candidats = [n for n in unders if age < n]
    return f"U{min(candidats)}" if candidats else None


def bareme(reference: int, unders: list[int]) -> list[Tranche]:
    """Une tranche par Under : (circuit, premiere annee, derniere annee)."""
```

Trois fonctions **pures** : ni base, ni Flask, ni réseau — comme
`formatage.py` et `cascade.py`. C'est ce qui permet de les éprouver par une
table de cas, et surtout de **vérifier le calcul contre le tableau FFME publié**.
C'est le seul test qui prouve quelque chose ici : le reste n'est que de la
plomberie autour.

`unders` n'est pas une constante : il se déduit des **catégories de l'édition**
(`U11 F`, `U13 H` → `{11, 13}`). Rien n'est codé en dur — `contraintes-metier.md`
§4 dit que les catégories changent d'une année sur l'autre.

## 3. Le modèle

### 3.1 Ce qui s'ajoute à `participant`

| Colonne | Type | Pourquoi |
| --- | --- | --- |
| `annee_naissance` | `Integer`, nullable | D9. Un entier, pas une date : c'est tout ce que la règle demande, et c'est la donnée la plus réduite qui la satisfait |
| `categorie_forcee` | `Boolean`, nullable | D10. La **trace d'un geste**, comme `hors_circuit_force` : quelqu'un a rangé cette personne à la main, « Appliquer à tous » ne doit pas le défaire en silence |

Les deux sont nullables et le restent : les participants venus du classeur n'ont
ni année ni geste, et un import de classeur ne doit pas se mettre à échouer.

### 3.2 La table `inscription`

```python
class Inscription(db.Model):
    """Une ligne de HelloAsso, et ce qu'on en a fait.

    Elle survit au participant qu'elle a cree : c'est la trace de ce que la
    plateforme a dit, et la seule chose qui rende le releve idempotent.
    """
    __tablename__ = "inscription"
    __table_args__ = (
        # L'anti-reimport tient ICI, pas dans le code du releve. Un article
        # revu a chaque tour de 60 secondes ne peut produire qu'une ligne.
        UniqueConstraint("competition_id", "article_id", name="uq_inscription_article"),
    )

    id              = Column(Integer, primary_key=True)
    competition_id  = Column(Integer, ForeignKey("competition.id"), nullable=False)

    article_id      = Column(Integer, nullable=False)   # item.id — la cle
    commande_id     = Column(Integer)                   # order.id — la fratrie

    etat            = Column(String(20), nullable=False, default=A_TRANCHER)
    motif           = Column(String(30))
    participant_id  = Column(Integer, ForeignKey("participant.id"))

    nom             = Column(String(80))
    prenom          = Column(String(80))
    annee_naissance = Column(Integer)
    club            = Column(String(80))
    categorie       = Column(String(20))

    etat_helloasso  = Column(String(20))                # Processed, Canceled…
    maj_le          = Column(DateTime)                  # item.meta.updatedAt
    recue_le        = Column(DateTime, default=func.now())
    traitee_le      = Column(DateTime)
    traitee_par     = Column(String(80))
```

**Pas de colonne `courriel`, pas de `detail`, pas de `tarif`.** Les deux
premières tombent avec D5 ; la troisième avec « tout le monde paie le même
tarif ». Il n'existe nulle part de copie du JSON reçu : les colonnes ci-dessus
*sont* l'enregistrement.

Quatre états, et ils décrivent un **geste physique** :

| `etat` | Ce que ça veut dire | Ce qui le fait bouger |
| --- | --- | --- |
| `a_trancher` | Un humain doit dire quelque chose | Il clique |
| `a_imprimer` | Le participant existe, le papier n'est pas sorti | « Imprimer » ou « Déjà remis » |
| `faite` | Le dossard est entre ses mains | — |
| `ignoree` | Mise de côté volontairement | Réouverture possible |

`motif` dit **pourquoi** ça attend, et c'est ce que la carte affiche :
`club_different`, `annee_absente`, `annee_hors_bareme`, `genre_indetermine`,
`sans_nom`, `annulee_apres_coup`.

### 3.3 Les réglages

Le club a **un** compte HelloAsso, mais **une** compétition par an.

| Quoi | Où | Pourquoi là |
| --- | --- | --- |
| `client_id`, `client_secret`, `refresh_token` | `shared/secrets/helloasso.json` | Comme `token.json` : hors dépôt, hors release |
| Environnement, organisation, dernier relevé, dernière erreur | table `reglage`, clé `helloasso` | Global au serveur, et en base — la sauvegarde ne recopie que la base |
| Formulaire choisi et **les trois champs** | `competition.options["helloasso"]` | Par édition |

```json
{
  "form_type": "Event",
  "form_slug": "bloc-party-2026",
  "champs": { "naissance": "Date de naissance", "genre": "Sexe", "club": "Votre club" },
  "genre_valeurs": { "Fille": "F", "Garçon": "H", "F": "F" }
}
```

**Le barème n'est pas là.** Il se calcule à la lecture, depuis la date de la
compétition et ses catégories. L'enregistrer serait figer un calcul qui n'a
qu'une entrée — et rendre possible un barème stocké qui contredit la règle.
Seule une **correction manuelle** est enregistrée, et seulement si elle existe :
`options["helloasso"]["bareme_corrige"]`.

`genre_valeurs` range les réponses *réellement vues*. Une valeur absente n'est
pas `H` par défaut : elle rend le genre **indéterminé**, et l'inscription passe
en `a_trancher`.

### 3.4 Migration

- `inscription` : `db.create_all()`, comme `Archive` (spec 018).
- Les deux colonnes de `participant` : deux lignes dans `COLONNES_AJOUTEES` de
  `schema.py`. Le mécanisme existe, il est idempotent, il tourne sous le verrou
  de démarrage.

Aucune destruction, aucune réécriture. Un retour arrière de release laisse table
et colonnes en place : l'ancienne version les ignore.

## 4. `helloasso/client.py` — l'authentification

### Le jeton vit en base, et un seul worker le rafraîchit

Leur documentation est explicite :

> Lorsqu'un refresh token A est utilisé, un nouveau refresh token B est renvoyé.
> Si une nouvelle utilisation du refresh token A est faite, alors un nouveau
> refresh_token C est créé et **B est révoqué**.

Avec quatre workers gunicorn et un jeton en mémoire vive, deux rafraîchissements
simultanés **se révoquent l'un l'autre**. Le symptôme serait le pire qui soit :
ça marche en développement (un seul processus), et ça tombe en production au
bout de trente minutes, un jour de compétition.

1. Le couple `access_token` / `refresh_token` est **lu et écrit en base**.
2. Le rafraîchissement prend le verrou `helloasso_jeton` de la table `verrou` —
   celui-là même que le miroir utilise.
3. Celui qui n'obtient pas le verrou **relit** : le voisin vient d'y déposer un
   jeton frais.

Coût : **2 appels d'authentification par heure**, sur 50 autorisés.

### La surface

```python
class ClientHelloAsso:
    def formulaires(self) -> list[dict]
    def formulaire(self, type, slug) -> dict          # champs et réponses vues
    def articles(self, type, slug, depuis) -> Iterator[dict]
```

`articles()` est un **générateur** : il rend les articles page par page et ne
charge jamais tout en mémoire. Le relevé écrit au fil de l'eau, et une coupure
ne perd que la page en cours.

### Les erreurs, typées

`ErreurHelloAsso(message, code)`, sur le modèle d'`ErreurClasseur` : elle ne
fait jamais échouer une requête de juge, elle retarde un relevé.

| Famille | Ce que la console affiche |
| --- | --- |
| Pas de clé posée | « HelloAsso n'est pas relié » |
| Clé refusée, `refresh_token` périmé (401, 403) | « Clé à reconnecter » — et **le fil s'arrête** |
| Réseau, 429, 5xx | « HelloAsso injoignable » — retenté à la cadence normale |

La deuxième ligne compte : insister avec une clé morte brûlerait le quota
d'authentification et rendrait la reconnexion impossible.

## 5. `helloasso/releve.py`

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
  annulation, correction de nom — a une date de création ancienne. Trier par
  création la rendrait invisible pour toujours.
- **`from = dernier_vu − 5 min`** : recouvrement volontaire. Les horloges ne sont
  pas les mêmes des deux côtés. Le recouvrement ne coûte rien — la contrainte
  d'unicité absorbe.
- **`withDetails=true`** : sans lui, pas de `customFields`, donc ni année, ni
  genre, ni club.

Pagination selon **leur** règle, pas notre intuition :

```python
while True:
    page = appel(continuation_token=jeton)
    articles = page.get("data") or []
    if not articles:
        break                       # ← la seule condition d'arret
    yield from articles
    jeton = (page.get("pagination") or {}).get("continuationToken")
    if not jeton:
        break                       # ceinture
```

### Ce qui est écrit pour chaque article

| Champ HelloAsso | Devient |
| --- | --- |
| `item.id` | `article_id` — la clé anti-réimport |
| `order.id` | `commande_id` — la fratrie, et le back-office |
| `item.user.firstName / lastName` | `prenom` / `nom`, par `formatage.mots()` |
| *(à défaut)* `order.payer.firstName / lastName` | idem, **et** `motif = sans_nom` |
| `customFields[champs.naissance].answer` | `annee_naissance` — **l'année seule est retenue** |
| `customFields[champs.genre].answer` → `genre_valeurs` | le genre, `F` ou `H` |
| `categories.circuit(annee, reference, unders)` + genre | `categorie` |
| `customFields[champs.club].answer` | `club`, par `formatage.mots(sigles=True)` |
| `item.state` | `etat_helloasso` |
| `item.meta.updatedAt` | `maj_le` — il fait avancer le curseur |
| Tout le reste — payeur, montants, moyens de paiement, tarif | **jeté, jamais écrit** |

`formatage.py` est réutilisé tel quel. Sa réserve — « ce module ne touche jamais
à ce qui est importé du classeur » — ne s'applique pas ici : HelloAsso n'est pas
une source qui fait autorité sur sa mise en forme, c'est **du texte tapé par un
parent sur un téléphone**.

Un article = un `commit`. Cent qui passent et un qui échoue laissent cent
inscriptions écrites, pas zéro.

## 6. `helloasso/rapprochement.py`

Fonction pure, sans base ni Flask.

```python
def cle(nom, prenom) -> str        # minuscules, sans accent, separateurs reduits
def confronter(candidat, existants) -> Verdict
```

`Verdict` ∈ `NOUVEAU` · `MEME_PERSONNE(id)` · `A_TRANCHER(motif)`.

La table de décision est celle du §5 de la spec. Ce qui compte
architecturalement : **le club est la seule preuve acceptée** pour rattacher
sans demander. Deux enfants du même nom dans un club d'escalade, ça se voit ;
deux enfants du même nom **dans le même club**, non.

La catégorie ne décide pas, elle **contrôle** : un rattachement dont les
catégories diffèrent se fait quand même, et se signale. Refuser sur ce critère
bloquerait le cas le plus banal — un classeur importé avant que le barème ne
soit appliqué.


## 6 bis. Un seul formatage — le 04/09

> « Débrouille-toi pour uniformiser le formatage, je ne veux pas de doublon. »

### La clé d'identité a déménagé

`formatage.identite()` et `formatage.identite_club()` vivent dans
`formatage.py`, avec les règles de mise en forme qui les rendent vraies — et
non plus dans `helloasso/rapprochement.py`, qui les importe désormais.

Ce n'est pas un rangement. Un doublon naît toujours d'un écart entre **la
forme** qu'on écrit et **la clé** qu'on compare ; les tenir dans deux fichiers,
c'est garantir qu'ils divergeront — l'un gagnera une règle que l'autre n'a pas,
et le doublon reviendra par la porte qu'on n'a pas refermée. Un test vérifie
que les deux modules pointent sur **la même fonction**, pas sur deux copies.

### Trois portes d'entrée, un seul formatage

| Entrée | Avant le 04/09 | Depuis |
| --- | --- | --- |
| `sheets/importer.py` | brut, volontairement | `formatage.*` + `club_canonique()` |
| `contest.ajouter_participant` | `formatage.*` | idem, + garde anti-doublon |
| `PATCH /admin/participants/<id>` | `formatage.*` | idem |
| `helloasso/releve.py` | `formatage.*` | inchangé |

### `club_canonique()` — la première orthographe fait référence

`formatage.club()` ne préserve un sigle que s'il est **déjà** en capitales :
« caf vivarais » devient « Caf Vivarais », à côté du « CAF Vivarais » du
classeur. C'est la dernière porte par laquelle un doublon revenait, et elle a
été trouvée par un test, pas par relecture.

Une liste de sigles connus serait à tenir à jour pour chaque club de la région.
La règle retenue ne demande rien : **le club existe déjà sous une forme, on
reprend la sienne**. Elle vit dans `contest.py` parce qu'elle a besoin de la
base — c'est ce qui la distingue de `formatage.py`, qui reste pur.

### La garde, et pourquoi elle porte un marqueur

`ErreurMetier` gagne un attribut `doublon`. Sans lui,
`ajouter_participant_numerote` prend **tout** 409 pour une course sur le
dossard : il réessaie cinq fois et rend « trop de saisies simultanées », qui n'a
aucun rapport avec ce qui s'est passé — et le message le plus utile est perdu.

### La fusion déplace par une mise à jour

`Participant.reussites` porte `cascade="all, delete-orphan"`. Tant qu'un objet
est dans la collection, supprimer le participant l'emporte — **même si sa clé
étrangère vient d'être changée**. Les réussites disparaissaient donc au lieu de
changer de main, ce qui est exactement le contraire de ce que « fusionner »
promet. Elles se déplacent par `UPDATE`, et la session est expirée ensuite.

## 6 ter. `helloasso/correspondance.py` — l'import devine

> « Lors des imports je veux un maximum d'automatisation. »

Module **pur** : ni base, ni Flask, ni réseau. Deux mécanismes de
reconnaissance, et le second est celui qui sert le plus.

| Mécanisme | Ce qu'il attrape |
| --- | --- |
| Par le **nom** du champ | *date de naissance*, *né(e) le*, *sexe*, *genre*, *club*, *association*… |
| Par ses **réponses** | Un champ dont **toutes** les réponses sont des écritures de genre connues — quel que soit son intitulé |

Le second rattrape « Votre enfant est », « Il/Elle », et tous les libellés
qu'aucune liste de mots-clés ne prévoira. L'ordre compte : le nom d'abord, les
réponses ensuite — un champ nommé « Sexe » est un champ de genre même si
personne n'y a encore répondu.

### Deux garde-fous, aussi importants que l'automatisation

**Un intrus suffit à disqualifier.** `_ressemble_a_des_genres()` exige que
*tout* soit reconnu. « La plupart ressemblent à des genres » ne vaut jamais
reconnaissance : une erreur de colonne rangerait un formulaire entier de
travers, et personne ne saurait où regarder.

**Rien n'est deviné en silence.** `POST /admin/helloasso/formulaire` rend
`trouves` — ce qui a été reconnu — et `genres_inconnus` — les réponses qu'on n'a
pas su ranger. Ce sont les seules lignes qui demandent encore un geste.

### La table intégrée, et qui gagne

`GENRES_CONNUS` reconnaît « Fille », « F », « Féminin », « Girl »… quatre
écritures de la même chose, qu'il serait absurde de faire saisir à chaque
édition. `releve.genre_de()` consulte **d'abord** la table de l'édition — c'est
un humain qui l'a écrite, elle l'emporte — puis la table intégrée. Ce qui n'est
dans ni l'une ni l'autre rend `None`, **jamais** « H » par défaut.

## 7. `helloasso/planificateur.py`

Copie conforme de `sheets/planificateur.py`, avec ses deux qualités payées cher :

1. **il ne meurt jamais** — un `except Exception` autour du corps de boucle ;
2. **il ne répète pas sa plainte** — on journalise ce qui *change*. Une heure
   sans réseau produit une ligne, pas soixante.

La cadence est une fonction de l'état de la compétition (§F8 de la spec). Le fil
**ne démarre pas** sans clé posée : zéro appel réseau. La dernière erreur est
exposée par `/health`, comme celle du miroir — le 30/08, il a fallu ouvrir un
SSH pour apprendre pourquoi 714 réussites attendaient.

## 8. Les routes

| Méthode | Route | Rôle | Ce qu'elle fait |
| --- | --- | --- | --- |
| `GET` | `/admin/categories` | organisateur | Le barème calculé, la saison, les compteurs |
| `POST` | `/admin/categories/appliquer` | organisateur | Recalcule. `?apercu=1` rend l'avant/après **sans écrire** |
| `PATCH` | `/admin/participants/<id>` | organisateur | L'édition en ligne. Passe par `formatage`, respecte la règle du dossard |
| `GET` | `/admin/helloasso` | **admin** | État. **Jamais le secret** |
| `POST` · `DELETE` | `/admin/helloasso/cle` | **admin** | Poser, débrancher |
| `GET` | `/admin/helloasso/formulaires` | **admin** | Les formulaires du club |
| `POST` | `/admin/helloasso/formulaire` | **admin** | Choisir, et **découvrir** champs et réponses |
| `GET` · `POST` | `/admin/helloasso/champs` | organisateur | Les trois champs et les valeurs de genre |
| `POST` | `/admin/helloasso/relever` | organisateur | Relever maintenant |
| `GET` | `/admin/inscriptions` | organisateur | Les trois piles |
| `POST` | `/admin/inscriptions/<id>/trancher` | organisateur | Le choix humain |
| `POST` | `/admin/inscriptions/<id>/remise` | organisateur | Dossard remis |
| `GET` | `/admin/doublons` | organisateur | Les fiches de même identité **et même club** |
| `POST` | `/admin/doublons/fusionner` | organisateur | `{"garder", "absorber"}`. C'est l'humain qui dit lequel garde son dossard |
| `GET` | `/admin/doublons` | organisateur | Les fiches de même identité **et même club** |
| `POST` | `/admin/doublons/fusionner` | organisateur | `{"garder", "absorber"}`. C'est l'humain qui dit lequel garde son dossard |

Le compteur de la pastille voyage dans `/admin/moi`, comme celui des mises à
jour : la console l'a déjà sous la main à chaque écran.

**L'impression ne prend pas de route nouvelle.** `/admin/dossards` accepte déjà
une sélection ; la sélection par cases lui passe une liste de dossards.

## 9. Le webhook — ce qu'on n'active pas, et pourquoi c'est écrit ici

Trois raisons, vérifiées dans leur documentation le 03/09 :

1. **On ne peut pas vérifier qu'elles viennent d'eux.** La signature HMAC
   `x-ha-signature` est « disponible **uniquement pour les partenaires** ». Une
   association n'a que l'adresse IP source — un contrôle qui traverse un reverse
   proxy, un NAT domestique et un `X-Forwarded-For`.
2. **Le corps ne porte pas `customFields`.** Il faudrait rappeler l'API.
3. **Le gain est de quelques dizaines de secondes**, contre une route publique
   non authentifiée sur une ligne domestique.

Si le besoin apparaissait : `POST /api/helloasso/notification` qui **ne lit rien
du corps** et se contente de réveiller le fil. Un réveil n'est pas une donnée,
il ne peut donc pas mentir.

## 10. Les fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/categories.py` | **nouveau** — la règle FFME, pure |
| `climbcontest/helloasso/{__init__,client,releve,rapprochement,salle,planificateur}.py` | **nouveaux** |
| `climbcontest/helloasso/correspondance.py` | **nouveau** — la reconnaissance automatique, pure |
| `climbcontest/formatage.py` | +`identite()`, +`identite_club()` ; l'en-tête change de doctrine |
| `climbcontest/sheets/importer.py` | Passe par le formatage — **changement de doctrine** |
| `climbcontest/bareme.py` | **nouveau** — la règle branchée sur une édition |
| `climbcontest/models.py` | +`Inscription`, +2 colonnes sur `Participant` |
| `climbcontest/schema.py` | +2 lignes dans `COLONNES_AJOUTEES` |
| `climbcontest/routes/admin.py` | +12 routes ; `/admin/moi` porte le compteur |
| `climbcontest/templates/admin.html` | Sources, sélection d'impression, édition en ligne, écran Catégories, vue Inscriptions, pastille. **La tuile « Imprimer les fiches » est retirée** |
| `climbcontest/contest.py` | L'ajout accepte `annee_naissance` |
| `climbcontest/__init__.py` | Démarrage conditionnel du fil |
| `climbcontest/routes/sante.py` | `/health` expose la dernière erreur HelloAsso |
| `climbcontest/cycle.py` | L'effacement emporte les inscriptions |
| `tools/dump_helloasso.py` | **nouveau** — lecture seule |
| `.gitleaks.toml` | Motif pour les clés HelloAsso |
| `requirements.txt` | rien — `requests` est déjà là |

⚠️ `admin.html` est le fichier que la spec 038 désigne comme « celui que toutes
les PR se disputent ». Les ajouts sont additifs — une `<section class="vue">` de
plus, des colonnes en fin de tableau — sauf le **retrait** de la tuile
d'impression, qui est une suppression franche et se verra au conflit.

## 10 bis. Le jour où le classeur Google s'en va

Rappelé par Adrien le 04/09 : **le classeur est temporaire**, il finira par
disparaître. `docs/contraintes-metier.md` §2 décrit déjà la trajectoire en trois
temps — source, puis miroir, puis plus rien. Pour l'instant on vit avec ; ce qui
suit dit ce que la spec 008 lui doit encore, et ce qu'elle ne lui doit plus.

| Ce que la 008 utilise | Vient du classeur ? | Le jour où il s'en va |
| --- | --- | --- |
| Les **participants** | Oui, pour partie | HelloAsso et le guichet suffisent — c'est l'objet même de cette spec |
| Les **catégories** des participants | Oui, pour partie | Se calculent depuis l'année de naissance |
| Les **circuits** (`Circuit`) | **Oui, exclusivement** | Remplacés par les **catégories déclarées** |
| Le **barème** | Non | Se déduit de la date et des Under |
| Le **rapprochement** | Non | Nom + prénom + club |
| Le **relevé** | Non | — |

### La seule dépendance qui restait, et comment elle est levée

`Circuit` n'est créé que par `sheets/importer.py`. Sans lui, une édition
alimentée par HelloAsso seul n'aurait **aucun Under** au premier relevé : la
liste serait vide, aucune catégorie ne se calculerait, et les cent inscriptions
partiraient en attente avec « année hors barème » pour seul message — le défaut
d'amorçage déjà fermé une fois, revenant par une autre porte.

D'où la **troisième source** de `bareme.unders()` : les catégories que l'édition
**déclare**, rangées dans `competition.options["categories_declarees"]` et
saisies en une ligne depuis l'écran Catégories. Elle ne remplace rien tant que le
classeur est là ; elle rend simplement le calcul indépendant de lui.

### Ce qui reste à faire le jour venu, et qui n'est pas de cette spec

- Les **blocs** et les **liens bloc ↔ circuit** ne viennent que du classeur. Ils
  n'entrent pas dans la spec 008, mais ils entreront dans celle qui débranchera
  le classeur pour de bon.
- Le **miroir** (`sheets/mirror.py`) écrit les réussites dans le classeur. Il
  s'éteindra avec lui, et la question de la sauvegarde se reposera —
  `contraintes-metier.md` §2 le dit déjà : « la redondance gratuite disparaît ».

## 11. Ce qui ne bouge pas

- **Le miroir vers le classeur.** Il envoie des réussites.
- **L'import du classeur.** Les deux flux cohabitent et ne se connaissent pas ;
  c'est le rapprochement qui les fait se rencontrer, au niveau du participant.
- **Le catalogue de l'app juge.** Créer un participant incrémente déjà
  `catalogue_version` : les vingt-cinq téléphones voient l'inscrit en moins de
  vingt secondes, sans une ligne de code de plus.
- **Le classement.** Il ne connaît que `participant`.
- **La règle du dossard.** Un dossard qui porte des réussites ne change pas de
  main ; l'édition en ligne ne l'ouvre pas.
