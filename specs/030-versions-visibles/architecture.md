# Architecture — spec 030

## 1. Qui dit quoi à qui

```
                  GET /api/v2/catalog
   téléphone  ─────────────────────────────────►  serveur
              X-Device-Id / -Name, X-App-Version
              If-None-Match: "42"

              ◄─────────────────────────────────
                  200 + corps, ou 304 nu
                  ETag: "42"
                  X-Server-Version: v0.16.0        (les DEUX branches)

                                                   └─► table `appareil`
                                                       (id, nom, version, n°, vu_le)

   console    ─────────────────────────────────►  GET /admin/versions
              ◄─────────────────────────────────   serveur + catalogue + comptes
              ─────────────────────────────────►  GET /admin/appareils
              ◄─────────────────────────────────   une ligne par téléphone
```

Aucune route nouvelle côté juge. Une seule côté console.

## 2. Modèle de données

Une table neuve, donc **aucune migration** : `db.create_all()` crée les tables
absentes, et `COLONNES_AJOUTEES` ne sert qu'aux colonnes greffées sur une table
existante.

```python
class Appareil(db.Model):
    __tablename__ = "appareil"
    id = Column(String(40), primary_key=True)      # l'identifiant du telephone
    nom = Column(String(60))                       # dernier nom connu
    version_app = Column(String(20))               # ce que la coquille dit etre
    catalogue_version = Column(Integer)            # cf. ci-dessous
    catalogue_vu_le = Column(DateTime)             # dernier ECHANGE de catalogue
    premiere_vue_le = Column(DateTime, nullable=False)
    vu_le = Column(DateTime, nullable=False, index=True)   # dernier contact, tout confondu
```

⚠️ **Deux horodatages, et il ne faut pas les fusionner.** `vu_le` avance à
n'importe quel contact — catalogue *ou* envoi de lot. `catalogue_vu_le` n'avance
que sur un échange de catalogue. C'est leur **écart** qui trahit un cache posé
devant `/api/v2/catalog` : le téléphone envoie (POST, jamais mis en cache) mais
ne s'annonce plus (GET, absorbé). Un seul horodatage rendrait cette panne
invisible — voir F8 de la spec.

**Globale, pas par compétition** — un téléphone est un téléphone, et il traverse
les éditions. Le rattachement à une édition se fait déjà par les réussites.

⚠️ **`catalogue_version` est le numéro que le téléphone détient À LA FIN de
l'échange**, c'est-à-dire le numéro courant du serveur au moment du contact —
pas celui qu'il a annoncé. Les deux ne diffèrent que dans un sens : un `304`
signifie qu'ils sont égaux, un `200` que le téléphone vient de recevoir le
courant. Enregistrer le numéro *annoncé* ferait clignoter en ambre, pendant cinq
minutes après chaque import, des téléphones qui viennent précisément de se
mettre à jour.

Limite connue, écrite pour qu'on ne la redécouvre pas : un téléphone qui reçoit
le catalogue mais **échoue à l'écrire** en IndexedDB apparaîtra à jour dans la
console alors que son propre écran affichera l'ancien numéro. Les deux écrans se
contredisent, et c'est le téléphone qui dit vrai.

## 3. Le numéro de catalogue est une empreinte, pas un compteur

Depuis la PR #85 (session parallèle, fermeture d'une incohérence de la
spec 029), redessiner le mur donne un numéro **neuf et distinct à chaque
édition** : le numéro saute, et il saute pour toutes les éditions à la fois.

Conséquence tenue par toute cette spec : **on ne compare que par égalité.**
Aucun écran n'écrit « N mises à jour », n'ordonne deux numéros, ni ne parle
d'« avance » ou de « retard » en termes arithmétiques. Un numéro identifie un
couple *(édition, état de son catalogue)* ; il vaut ou il ne vaut pas celui du
serveur.

## 4. Contrats d'API

### `GET /api/v2/catalog` — inchangé, sauf en-têtes

**Requête** — trois en-têtes facultatifs :

| En-tête | Longueur | Traitement |
| --- | --- | --- |
| `X-Device-Id` | 40 | tronqué ; absent ⇒ aucune annonce n'est enregistrée |
| `X-Device-Name` | 60 après décodage | `unquote` ; un décodage qui lève ⇒ nom ignoré |
| `X-App-Version` | 20 | tronqué, stocké tel quel |

**Réponse** — `X-Server-Version: <tag ou "dev">` et `Cache-Control: no-cache,
private`, en `200` **et** en `304`.

`private` est ajouté à `no-cache` : le premier interdit à un cache **partagé**
de stocker la réponse, le second demande une revalidation avant de servir. Les
deux ensemble disent exactement ce que cette route exige — et sans le premier,
un cache partagé aurait le droit de servir la réponse d'un téléphone à un autre,
ce qui priverait le serveur de toutes les annonces suivantes.

⚠️ **Le piège du retour anticipé.** `catalogue()` construit sa réponse `304`
séparément, avec `make_response("", 304)`, et repose ses en-têtes à la main. Tout
ce qui suit cette garde n'est jamais atteint quand le téléphone est à jour —
c'est-à-dire dans le cas **majoritaire**. L'enregistrement de l'annonce se fait
donc **avant** le calcul de `a_jour`, et l'en-tête de version est posé sur les
deux branches. Une annonce enregistrée après la garde ne montrerait dans la
console que les téléphones **en retard** : l'exact inverse de ce qu'on veut voir.

⚠️ **Cette route devient un `GET` avec effet de bord.** C'est acceptable ici —
`Cache-Control: no-cache` veut dire « revalide avant de servir », donc la requête
atteint l'application à chaque fois, ce qui est exactement ce qui rend le `304`
possible. Mais **qui mettra un jour `/api/v2/catalog` derrière un vrai cache
cassera silencieusement le tableau des appareils.** C'est écrit ici et dans le
code.

### `GET /admin/versions` — nouvelle, réservée à un organisateur

```json
{
  "success": true,
  "serveur": { "version": "v0.16.0", "posee_le": "2026-09-02T18:04:11" },
  "catalogue": { "version": 42, "participants": 98, "blocs": 67 },
  "appareils": { "vus": 6, "a_jour": 4, "en_retard": 2, "muets": 1,
                 "annonces_perdues": 0 }
}
```

`annonces_perdues` compte les téléphones qui **savent s'annoncer** (on connaît
leur version d'application), qui ont **envoyé une réussite dans les dix
dernières minutes**, et dont l'annonce de catalogue date de **plus d'un quart
d'heure**.

⚠️ **Ce croisement repose sur une hypothèse à surveiller : aucun lot ne part
hors du premier plan.** Elle tient aujourd'hui — la boucle de `juge.js` teste
`visibilityState`, les autres chemins d'envoi sont des gestes du juge, et
`sw.js` n'écoute ni `sync` ni `periodicsync`. Ajouter une synchronisation en
arrière-plan ferait partir des lots sans annonce, et le détecteur accuserait un
cache sur un téléphone en veille parfaitement sain. L'avertissement est posé
dans `sw.js`, à l'endroit exact où on écrirait cet écouteur. Zéro en marche normale — écran allumé, la PWA s'annonce toutes les
trente secondes.
Au-dessus de zéro, la console nomme la cause : quelque chose met
`/api/v2/catalog` en cache entre les téléphones et le serveur.

`posee_le` est la date de modification du fichier `VERSION` — c'est-à-dire le
moment où la release a été posée sur la VM. Absente en développement.

### `GET /admin/appareils` — étendue

Chaque ligne gagne `version_app`, `catalogue_version`, `vu_le`, `annonce`
(booléen : ce téléphone s'annonce-t-il ?), en plus des champs actuels.

La liste devient l'**union** de deux ensembles :

1. les téléphones qui ont envoyé une réussite sur l'édition en cours (source
   actuelle : `Success`) ;
2. les téléphones vus depuis moins de 24 h (source nouvelle : `Appareil`).

Un téléphone du second ensemble seulement sort avec `reussites: 0` — c'est le
cas du matin, et c'est celui qu'Adrien veut voir.

## 5. Le service worker et la mise à jour forcée

Le message `{ type: "rafraichir-la-coquille" }` déclenche, dans `sw.js` :

```
pour chaque URL de COQUILLE :
    reponse = fetch(url, { cache: "reload" })     // court-circuite le cache HTTP
    si reponse.ok : cache.put(url, reponse)       // on ne remplace qu'apres reception
répondre { ok, remplaces, echecs }
```

Puis la page recharge **si et seulement si** au moins un fichier a été remplacé
et qu'aucun essentiel n'a échoué. Le cache n'est jamais vidé d'abord : un
remplacement raté laisse la coquille précédente en place, et l'application
continue de fonctionner hors ligne.

⚠️ `CACHE` (`"climbcontest-juge-v3"`) ne change pas et **ne doit pas devenir
dépendant de la version** : un nom de cache neuf à chaque release ferait
réinstaller la coquille de vingt-cinq téléphones à chaque publication, y compris
pendant une compétition, avec le risque qu'une installation partielle laisse un
téléphone sans hors-ligne. La mise à jour reste **à la demande** ou au lancement
suivant.

## 6. D'où vient la version, côté client

| Client | Source | Pourquoi |
| --- | --- | --- |
| Backend | `VERSION` à la racine, lu une fois au démarrage | déjà en place (`routes/sante.py`) |
| Console | `render_template("admin.html", version=…)` | la console est servie à chaque ouverture, jamais mise en cache |
| PWA | `<meta name="climbcontest-version">` dans la coquille | la coquille EST le code exécuté ; elle voyage avec sa propre version dans le cache du service worker |

Le module `climbcontest/version.py` porte `VERSION` et `posee_le()`.
`routes/sante.py` l'importe au lieu de relire le fichier lui-même : une seule
lecture, un seul endroit à corriger.

## 7. Fichiers touchés

| Fichier | Ce qu'on y fait |
| --- | --- |
| `climbcontest/version.py` | **neuf** — lecture du fichier `VERSION`, date de pose |
| `climbcontest/routes/sante.py` | importe le module au lieu de lire lui-même |
| `climbcontest/models.py` | table `Appareil` |
| `climbcontest/contest.py` | `enregistrer_annonce()`, `appareils()` étendue |
| `climbcontest/routes/catalogue.py` | annonce **avant** la garde, en-tête sur les deux branches |
| `climbcontest/routes/admin.py` | `GET /admin/versions`, `/admin/appareils` étendue |
| `climbcontest/routes/lot.py` | enregistre l'annonce à la réception d'un lot (redondance, cf. F8) |
| `climbcontest/routes/pwa.py` | passe la version à la coquille |
| `climbcontest/templates/juge.html` | balise `meta`, sections « Catalogue » et « Application » |
| `climbcontest/static/juge/api.js` | en-têtes d'annonce, lecture de `X-Server-Version`, téléchargement forcé |
| `climbcontest/static/juge/juge.js` | branchement des deux boutons et des verdicts |
| `climbcontest/static/juge/sw.js` | message `rafraichir-la-coquille` |
| `climbcontest/templates/admin.html` | pied de tiroir, carte « Versions en circulation », deux colonnes |
| `tests/` | cf. `plan.md` |

**Non touchés, et c'est voulu** : `climbcontest/schema.py` (table neuve),
`climbcontest-android` (hors périmètre).

⚠️ Le **contrat** du lot ne change pas : `appareil.app` est un champ facultatif
de plus dans un objet déjà facultatif. Un client qui ne l'envoie pas se comporte
exactement comme avant, et `catalogue_version` n'est **jamais** écrit depuis
cette route — recevoir un lot ne prouve rien sur le catalogue que le téléphone
détient.

## 8. Ce qui aurait pu être fait autrement

| Option écartée | Pourquoi |
| --- | --- |
| Une route d'annonce dédiée (`POST /api/v2/annonce`) | 25 téléphones × 12/h × 8 h = 2 400 requêtes ajoutées, pour une donnée qui tient dans une requête déjà émise. La spec 003 s'est battue pour passer de 10 800 à 817 requêtes |
| Annoncer dans le lot (`POST /api/v3/successes`) | Un téléphone qui n'a rien scanné n'apparaîtrait pas — or c'est exactement le contrôle du matin. Le lot reste inchangé ; il porte déjà le nom et l'identifiant |
| Stocker l'annonce dans `reglage` (clé-valeur) | Quatre workers gunicorn écrivent en concurrence sur la même ligne. Une table indexée par identifiant est le bon outil |
| Nommer le cache du service worker d'après la version | Réinstallation forcée de toutes les coquilles à chaque release. Cf. §5 |
