# Architecture — Spec 014

## 1. Fichiers touchés

| Fichier | Changement |
| --- | --- |
| `climbcontest/static/juge/jeton.js` | lit aussi la requête ; la requête prime |
| `climbcontest/static/juge/juge.js` | passe `location.search` à `choisirJeton` ; nettoyage revu |
| `climbcontest/templates/juge.html` | le `<link rel="manifest">` porte le jeton |
| `climbcontest/routes/pwa.py` | le manifeste devient rendu, plus statique |
| `climbcontest/static/juge/manifest.webmanifest` | devient un gabarit |
| `climbcontest/static/juge/sw.js` | ne met plus le manifeste en cache par URL fixe |
| `climbcontest/routes/admin.py` | `lien-juge` produit `?j=` |
| `vm101-edge/Caddyfile` | masquage du paramètre `j` dans le journal |

## 2. Le choix du jeton — `jeton.js`

La fonction devient :

```js
export function choisirJeton(requete, fragment, jetonRange)
```

Ordre de priorité, et la raison de chacun :

1. **la requête** (`?j=`) — c'est elle que porte `start_url`, donc la source la
   plus fraîche à chaque lancement de l'application installée ;
2. **le fragment** (`#j=`) — les liens déjà distribués, et les installations
   déjà faites ;
3. **le stockage** — le comportement actuel, qui reste le filet.

La règle qui ne change pas, et qui est la plus importante du module :
**une requête vide n'efface jamais un jeton rangé.** Sans elle, un lancement
depuis `/juge` nu viderait le jeton et bloquerait le juge — c'est le piège que
`choisirJeton` évite depuis la spec 007, et il vaut pour la requête comme pour
le fragment.

Le module reste **sans DOM ni réseau** : il continue de se tester sur Node.

## 3. Le manifeste dynamique — `pwa.py`

`manifest.webmanifest` passe de `send_from_directory` à un gabarit rendu :

```python
@bp.get("/manifest.webmanifest")
def manifeste():
    jeton = (request.args.get("j") or "").strip()
    depart = f"/juge?j={quote(jeton)}" if jeton else "/juge"
    ...  # Content-Type: application/manifest+json
```

**`scope` reste `/juge`**, sans jeton : c'est le périmètre de l'application, pas
son point d'entrée. Un `scope` porteur d'une requête restreindrait
l'application à cette seule adresse.

Sans `?j=`, le manifeste reste **exactement celui d'aujourd'hui**. Il doit rester
valide et servable seul : c'est ce que vérifie le critère A3.

### Le gabarit et le jeton

Le jeton n'est **jamais écrit dans un fichier du dépôt** : il arrive par la
requête et ressort dans la réponse. La règle « aucun secret dans un dépôt
public » est intacte.

## 4. Le gabarit `juge.html`

```html
<link rel="manifest" href="/juge/manifest.webmanifest{{ suffixe_jeton }}">
```

La route `/juge` lit `?j=` et transmet le suffixe. Une page ouverte sans jeton
lie le manifeste nu — donc rien ne change pour un visiteur de passage.

C'est ce lien qui fait tout : au moment où le navigateur propose d'installer, il
lit **ce** manifeste-là, et y trouve un `start_url` porteur du jeton.

## 5. Le nettoyage de l'adresse

Aujourd'hui, `installerLeJeton()` efface le fragment sitôt lu. La règle est
revue, et c'est le point qui décide si la solution marche **sur toutes les
plateformes** — exigence d'Adrien du 30/08.

| Ce qui porte le jeton | Effacé de l'adresse ? |
| --- | --- |
| Fragment `#j=` | **oui**, comme aujourd'hui |
| Requête `?j=` | **non, jamais** |

**Pourquoi ne jamais effacer la requête.** Deux générations d'iOS coexistent :

- iOS 16.4 et au-delà lit `start_url` dans le manifeste — le jeton y est, tout va bien ;
- les iOS antérieurs ignorent `start_url` et retiennent **l'adresse affichée au
  moment où on fait « Sur l'écran d'accueil »**.

Si on nettoie la requête, cette seconde famille capture `/juge` nu et
l'installation naît sans jeton — le défaut qu'on corrige, reconduit à
l'identique. Garder la requête couvre **les deux** générations, et Android par
la même occasion.

**Ce que ça expose, et pourquoi c'est acceptable.** Dans un navigateur ordinaire
le jeton reste visible dans la barre d'adresse. Une fois l'application
installée, `display: standalone` supprime cette barre : il n'y a plus rien à
exposer. Et le jeton est de toute façon **affiché au mur en QR** — la barre
d'adresse ne le révèle à personne qui ne puisse déjà le photographier.

Le fragment, lui, continue d'être nettoyé : il ne sert pas à l'installation, et
les anciens liens n'ont aucune raison de rester à l'écran.

## 5 bis. Le filet, quand tout a échoué

Une application qui démarre sans jeton affiche aujourd'hui une phrase et rien
d'autre — c'est une impasse pour le bénévole. On y ajoute une porte de sortie :
un bouton **« Scanner le QR de l'organisateur »**, qui ouvre le lecteur déjà
présent dans l'application et accepte une adresse `…/juge?j=…`.

Ça ne remplace pas le correctif : c'est ce qui évite qu'un juge reste bloqué le
jour J si un cas non prévu se présente. La demande est que ce soit automatique ;
ce filet ne se déclenche que lorsque l'automatique n'a pas marché.

## 6. Le service worker

`sw.js` met `/juge/manifest.webmanifest` en cache sous une **URL fixe**. Avec un
manifeste qui varie selon le jeton, cette entrée servirait le manifeste d'un
autre jeton — ou un manifeste nu à une application qui en attend un porteur.

Correctif : **retirer le manifeste de `COQUILLE`**. Il n'est lu qu'à
l'installation et à la mise à jour de l'application, jamais pendant une
compétition ; le mettre hors ligne n'apporte rien et introduit ici un faux.

`/juge` reste en cache : la requête `?j=` est ignorée par la mise en cache de la
navigation, et le jeton vient de l'adresse réelle au moment du lancement.

## 7. Caddy — masquer le jeton dans le journal

Sur `edge` (LXC 101), dans le bloc `climbcontest.adn-dev.fr` :

```caddy
log {
    output file /var/log/caddy/access.log {
        roll_size 10MiB
        roll_keep 5
    }
    format json
    # Le jeton des juges voyage en clair dans l'adresse depuis la spec 014.
    # Sans ce filtre, chaque lancement de l'application l'ecrit dans ce fichier.
    format filter {
        wrap json
        request>uri query {
            delete j
        }
    }
}
```

Le bloc `climbcontest.adn-dev.fr` cesse donc d'importer `(commun)` **pour sa
partie journal** : il garde les en-têtes et la compression, mais définit son
propre `log`. À écrire de façon à ne pas dupliquer le reste — un extrait
`(commun_sans_log)` est le plus lisible.

⚠️ La forme exacte de la directive doit être **vérifiée par
`caddy validate`** avant rechargement : c'est le proxy de tout le parc, une
erreur de syntaxe y coupe six services, pas un.

## 8. Ce qui pourrait mal tourner

| Risque | Parade |
| --- | --- |
| Un manifeste dynamique casse une installation existante | Le fragment reste accepté (§2) ; sans `?j=`, le manifeste est identique à l'actuel |
| Le service worker sert un manifeste périmé | Le manifeste sort du cache (§6) |
| La clé se retrouve dans les journaux d'`edge` | Filtre Caddy (§7), vérifié par A9 |
| Une erreur de Caddyfile coupe tout le parc | `caddy validate` avant `reload`, et sauvegarde datée du fichier — le geste est déjà rodé |
| `scope` avec requête casse la navigation | `scope` reste `/juge` nu (§3) |
| On croit avoir corrigé sans l'avoir prouvé | A10 : essai sur un vrai iPhone. **C'est le seul critère qui vaut preuve.** |
