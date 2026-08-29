# 012 — Architecture

## Serveur

### Configuration — `config.py`

```python
API_KEYS          # tuple des clés acceptées, dans l'ordre de configuration
API_KEY_STRICTE   # défaut : True
```

Deux variables d'environnement alimentent `API_KEYS` :

| Variable | Rôle |
| --- | --- |
| `CLIMBCONTEST_API_KEY` | la clé courante |
| `CLIMBCONTEST_API_KEY_PRECEDENTE` | l'ancienne, le temps que tous les téléphones aient la nouvelle |

Une valeur vide ou absente n'entre pas dans le tuple : une chaîne vide n'est pas
une clé, et l'accepter reviendrait à ouvrir la porte à `X-Api-Key: ` — c'est
précisément le genre de trou qu'on ferme ici.

`API_KEY` (singulier) **disparaît**. Le garder à côté de `API_KEYS` créerait deux
sources de vérité, et un jour l'une des deux serait consultée seule.

### Vérification — `auth.py`

```python
def cle_valide(fournie: str | None) -> bool:
    if not fournie:
        return False
    # `any(...)` court-circuiterait au premier succès : le temps de reponse
    # dirait alors LAQUELLE des cles a ete reconnue. On les compare toutes.
    resultat = False
    for attendue in current_app.config.get("API_KEYS", ()):
        resultat |= hmac.compare_digest(str(fournie), str(attendue))
    return resultat
```

Deux propriétés, et la seconde n'est pas de la coquetterie : sans elle, mesurer
le temps de réponse distinguerait « clé courante » de « clé précédente », ce qui
indique à un attaquant laquelle des deux il vient de deviner.

### Le régime devient strict par défaut

`API_KEY_STRICTE = os.environ.get("CLIMBCONTEST_API_KEY_STRICTE", "1") == "1"`

Une installation qui oublie la variable est désormais **fermée**. C'est le sens
de la spec : le défaut doit être l'état sûr, pas l'état pratique.

### Le garde-fou de la configuration incohérente

Mode strict + aucune clé configurée = personne ne peut plus rien envoyer, et le
message serait « Clé d'API requise » — ce qui enverrait chercher un problème de
clé alors que la variable est absente sur le serveur.

On répond donc **503**, avec le nom de la variable manquante. Le même choix que
`auth_session` fait déjà pour une `SECRET_KEY` absente : une erreur de
configuration doit se lire comme telle.

### `/health`

```json
"api": {"regime": "strict", "cles_acceptees": 2, "sans_cle": 0, ...}
```

Le nombre, jamais les clés — ni même un préfixe. Un préfixe réduit l'espace de
recherche et ne sert à rien qu'on ne sache faire en regardant la configuration
de la VM.

## Application

### `build.gradle.kts`

```kotlin
val cleDebug   = trouverCle("apiKey") ?: "dev"
val cleRelease = trouverCle("releaseApiKey")
```

`trouverCle` lit, dans l'ordre :

1. `-PapiKey=…` sur la ligne de commande ;
2. la variable d'environnement `CLIMBCONTEST_API_KEY` — pour la CI ;
3. `~/.gradle/gradle.properties`, **hors du dépôt** (couvert par `findProperty`).

⚠️ **Jamais** le `gradle.properties` du projet : il est suivi par git, et les
deux dépôts sont publics.

Le débogage a une valeur par défaut (`dev`, celle du serveur de développement) :
`installDebug` doit marcher sans rien configurer, sinon la première chose que
fera un développeur pressé sera de la mettre dans un fichier commité.

Le release, lui, n'a pas de défaut. La vérification passe par
`gradle.taskGraph.whenReady` et **pas** par un `require()` dans le bloc
`release { }` : ce bloc est évalué à la configuration de Gradle pour n'importe
quelle tâche, donc un `require` y ferait échouer `installDebug` — le piège déjà
rencontré et documenté sur `serverUrl`.

### `ClimbContestApi`

Un seul point d'ajout : chaque `Request.Builder()` reçoit l'en-tête.

```kotlin
private fun Request.Builder.avecCle(): Request.Builder =
    if (cle.isNotBlank()) header(ENTETE_CLE, cle) else this
```

L'en-tête plutôt que le corps — le serveur accepte les deux depuis la spec 001 :

- il marche sur les `GET` (le catalogue n'a pas de corps) ;
- il ne modifie pas la charge utile, donc les tests de contrat existants sur le
  format des lots restent valables ;
- il n'apparaît pas dans un journal applicatif qui enregistrerait un corps.

## Fichiers touchés

| Dépôt | Fichier | Nature |
| --- | --- | --- |
| core | `config.py` | `API_KEYS`, défaut strict |
| core | `auth.py` | plusieurs clés, comparaison sans court-circuit, 503 de configuration |
| core | `routes/sante.py` | régime et nombre de clés |
| core | `docs/plan-de-repli.md` | l'étape à ne pas oublier |
| core | `specs/001-vm-climbcontest/spec.md` | le critère resté ouvert |
| android | `app/build.gradle.kts` | `API_KEY` et son garde-fou release |
| android | `ClimbContestApi.kt` | l'en-tête sur toutes les requêtes |
