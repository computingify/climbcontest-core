# Spec 020 — Architecture

## 1. Modèle de données

**Aucune colonne nouvelle.** Tout tient dans ce qui existe :

| Donnée | Où elle vit | Pourquoi là |
| --- | --- | --- |
| Nom, date | `Competition.nom`, `Competition.date` | colonnes existantes, jamais écrites après création |
| Classements masqués | `Competition.options["groupes_masques"]` | déjà du JSON en texte, déjà porteur de `validation_couleur` |
| Recherche masquée | `localStorage` du navigateur | choix d'un appareil, jamais du serveur |

⚠️ `options` est un texte JSON lu par `classement_service._options()`. Toute
écriture doit **relire, modifier, réécrire** — écraser le champ ferait perdre
`validation_couleur`. Un helper unique :

```python
def ecrire_options(comp, **champs):
    """Fusionne. N'écrase JAMAIS les clés qu'on ne touche pas."""
```

Il vit dans `cycle.py` : c'est le module qui parle de la compétition et ne parle
qu'à la base.

## 2. Contrats

### `GET /admin/competition` — nouveau, rôle `ORGANISATEUR`

```json
{"success": true,
 "competition": {"id": 1, "nom": "Contest Annonay novembre 2026",
                 "date": "2026-11-15", "statut": "en_cours"},
 "groupes": [{"nom": "Scratch", "type": "scratch", "participants": 98},
             {"nom": "U13 F",   "type": "categorie", "participants": 21}],
 "groupes_masques": ["U19 F"]}
```

`groupes` vient de `classement_service.classements(comp)` — le cache de 5 s, pas
un calcul forcé : la liste des groupes ne change qu'à l'import.

La vue **Compétition** de la console appelle déjà `/admin/classeur` pour ses
compteurs ; cette route s'y ajoute plutôt que d'élargir l'autre, qui parle du
classeur et pas de la compétition.

### `POST /admin/competition` — nouveau, rôle `ADMIN`

```json
{"nom": "Contest Annonay novembre 2026", "date": "2026-11-15"}
```

Les deux champs sont facultatifs et traités indépendamment. Validation : nom non
vide, 120 caractères au plus (la colonne), date ISO. **Rien n'est écrit si un
champ est invalide** — un nom accepté et une date refusée dans le même appel
laisserait une compétition à moitié renommée.

### `POST /admin/competition/affichage` — nouveau, rôle `ADMIN`

```json
{"groupes_masques": ["U19 F", "Clubs"]}
```

Une liste de chaînes. Les noms inconnus sont **acceptés et rangés** : un groupe
peut réapparaître au prochain import, et le silence serait pire que l'oubli.

### `GET /api/public/classement` — un champ de plus

```json
{"competition": {"id": 1, "nom": "…", "statut": "en_cours",
                 "groupes_masques": ["U19 F"]},
 "classements": [ … tous, sans exception … ]}
```

`charge_publique` **ne filtre rien**. Le filtrage est un geste d'affichage, il
appartient à la page. Trois raisons, dans cet ordre :

1. `charge_publique` est aussi ce que `cycle.archiver` fige — une archive
   amputée serait irréparable ;
2. démasquer un classement l'après-midi ne doit rien recalculer ;
3. la réponse est mise en cache 5 s par Caddy pour tout le monde : elle ne peut
   pas dépendre de qui regarde.

## 3. La page de résultats

### La catégorie sur les scratchs

Un seul endroit, dans `dessiner()`, la branche qui construit les lignes d'un
groupe — celle qui pose aujourd'hui `contexte: null` :

```js
var avecCategorie = groupe.type === "scratch" || groupe.type === "circuit";
… contexte: avecCategorie ? (l.categorie || null) : null
```

`l.categorie` est déjà servi. `contexte` est déjà affiché par `remplir()`, avec
sa dégradation par densité — l'appoint tombe en premier quand la place manque,
ce qui est exactement le bon ordre de sacrifice sur un mur.

La branche « recherche » garde `libelleDe(c)` : pendant une recherche, savoir de
quel **classement** vient la ligne prime sur la catégorie du grimpeur.

### Le bouton « masquer la recherche »

```html
<button id="masquerRecherche" class="commande hors-mur" type="button"
        aria-pressed="false" aria-label="Masquer la recherche">⌕</button>
```

⚠️ Le CSS actuel ne montre `.commande` **qu'en mode mur**
(`body.mur .commande { display: block }`). Il faut une classe distincte —
`.hors-mur` — visible par défaut et masquée sous `body.mur`. Ne pas toucher à la
règle existante : `#pause` en dépend.

État dans `localStorage`, clé `climbcontest.affichage`, à côté de
`climbcontest.favoris` et lue avec le même `try/catch` : navigation privée,
stockage plein, JSON abîmé — la page doit continuer.

### Le filtre des groupes

```js
function groupesVisibles() {
  var tous = MUR ? etat.classements.filter(parType) : etat.classements;
  var restants = tous.filter(function (c) {
    return etat.groupesMasques.indexOf(c.groupe) === -1;
  });
  // Tout masqué : on ignore le réglage. Une page vide se lit comme une panne.
  return restants.length ? restants : tous;
}
```

Le filtre s'applique **après** `TYPES_MUR`, pour que la garde « tout masqué »
raisonne sur ce qui était réellement affichable.

`dessiner()` retombe déjà sur `visibles[0]` quand le groupe courant n'est plus
dans la liste — A15 est couvert par l'existant, il reste à le tester.

En mode **archive** (`data-source` pointe sur la console), `groupes_masques`
n'est pas dans la charge : la liste reste vide, l'archive se revoit en entier.

## 4. Fichiers touchés

| Fichier | Ce qui change |
| --- | --- |
| `climbcontest/cycle.py` | `ecrire_options()`, `renommer()`, `groupes_masques()` |
| `climbcontest/classement_service.py` | `charge_publique` ajoute `groupes_masques` |
| `climbcontest/routes/admin.py` | `GET`/`POST /admin/competition`, `POST /admin/competition/affichage` |
| `climbcontest/templates/admin.html` | champs nom/date, carte des cases à cocher |
| `climbcontest/templates/resultats.html` | `contexte`, bouton, `groupesVisibles()`, CSS `.hors-mur` |

Rien côté application juge, rien côté classeur, rien côté modèle.
