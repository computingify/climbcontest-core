# Spec 045 — Architecture

## 1. Le principe

**Un réglage lu en base, un point de décision unique, et des gardes en bordure.**

Le mode ne se propage pas de proche en proche : il est lu par une fonction, et
cette fonction est appelée aux six endroits qui décident d'appeler Google. Tout
le reste du code ignore qu'il existe.

⚠️ **Jamais mis en cache dans le processus.** Quatre workers gunicorn tournent :
un réglage mémorisé au démarrage laisserait trois d'entre eux continuer
d'appeler Google après la bascule, et le défaut serait intermittent — un scan
sur quatre. Le réglage se lit en base à chaque décision, comme
`plan_du_mur.lire()`. Le coût est une requête sur une table d'une ligne ; le
prix de l'autre solution est une panne qu'on ne reproduit pas.

---

## 2. Le réglage

`climbcontest/reglages.py` — **nouveau module**, minuscule, sans Flask.

```python
CLE = "mode_sans_classeur"

def mode_sans_classeur() -> bool:
    """Le classeur Google est-il debranche ? Ne leve JAMAIS.

    Meme contrat que `plan_du_mur.lire()` : une base indisponible ou une ligne
    abimee rend False, c'est-a-dire le comportement d'aujourd'hui. Un reglage
    illisible ne doit pas eteindre un import dont quelqu'un depend.
    """
```

⚠️ **Le repli est `False`, et c'est le sens de la sécurité ici.** Ailleurs dans
ce dépôt on *fail closed* — `auth_session` refuse au moindre doute. Ici, le
défaut sûr est l'inverse : replier sur `True` couperait l'import et le miroir
d'un club qui n'a rien demandé, sur une simple lecture ratée. Le mode retire des
fonctions, il n'en protège aucune.

La table `reglage` existe (spec 029) : `cle`, `valeur`, `modifie_par`. Aucune
migration.

---

## 3. Les six points de décision

| # | Où | Ce que le garde fait |
| --- | --- | --- |
| 1 | `sheets/planificateur.demarrer(app)` | ne lance pas le fil |
| 2 | `sheets/planificateur._boucle` | sort du tour sans appeler `synchroniser` |
| 3 | `sheets/mirror.synchroniser` | sort en `ignoree`, avec la raison |
| 4 | `routes/admin` — les 6 routes `/classeur*` et les 2 d'import | **409** en nommant le mode |
| 5 | `routes/sante.health` | `mode_sans_classeur: true`, compteurs à `null`, statut **`ok`** |
| 6 | `templates/admin.html` | l'entrée de tiroir et la vue, masquées |

⚠️ **Le garde 2 en plus du garde 1 n'est pas une ceinture de plus.** Le fil est
démarré une fois, au lancement de l'application ; la bascule se fait pendant que
l'application tourne. Sans le garde dans la boucle, le fil déjà lancé
continuerait d'appeler Google jusqu'au prochain redémarrage — c'est-à-dire
jusqu'à ce que quelqu'un s'en aperçoive.

⚠️ **Le garde 3 en plus des deux autres non plus.** `synchroniser` est aussi
appelable depuis un script et depuis les tests. La règle du dépôt vaut ici comme
ailleurs : **la garde est dans le métier**, pas seulement sur la route. C'est
exactement ce que la spec 008 écrit de `relever()`.

### 3.1 Le cas de `/health`

```python
corps["mode_sans_classeur"] = mode
corps["reussites_en_attente"] = None if mode else reussites_en_attente()
corps["reussites_inenvoyables"] = None if mode else reussites_inenvoyables()
```

⚠️ **Et le statut reste `ok`.** Aujourd'hui, `reussites_en_attente` à `null`
signifie « base injoignable » et fait répondre **503 degraded** — ce qui
déclenche le retour arrière de l'agent de déploiement. Poser `null` sans dire
pourquoi ferait donc **désinstaller la version** au premier déploiement suivant
la bascule. C'est le défaut le plus cher de ce lot, et il est silencieux : la
sonde a l'air de marcher.

Le test dédié : `mode allumé + base saine → 200 ok`, `mode allumé + base
injoignable → 503 degraded`. Les deux, pas seulement le premier.

---

## 4. Le contrôle avant bascule

`climbcontest/reglages.py::controle_avant_bascule(comp) -> dict`

```python
{
  "peut_basculer": bool,
  "refus":         [{"code": "B1", "message": "..."}],
  "avertissements":[{"code": "A1", "message": "..."}],
}
```

Aucune de ces vérifications n'est nouvelle : elles réutilisent ce qui existe.

| Contrôle | Ce qui le calcule |
| --- | --- |
| B1 — une source d'inscrits | le réglage de la spec 008 (`d'où viennent les inscrits`) |
| B2 — des blocs et des circuits | `Bloc.query.filter_by(competition_id=…).count()`, idem `Circuit` |
| A1 — des réussites en attente | `contest.reussites_en_attente()` |
| A2 — des blocs sans circuit | `circuits.anomalies()` — il les connaît déjà |
| A3 — des participants sans catégorie | `circuits.anomalies()` |
| A4 — la sauvegarde | une phrase, toujours affichée |

⚠️ **B1 dépend d'un module que ce lot n'a pas.** Tant que la 008 n'est pas
mergée, l'appel est enveloppé :

```python
try:
    from .inscriptions import source_active          # spec 008
except ImportError:
    source_active = lambda comp: None                # la 008 n'est pas la
```

C'est laid, et c'est assumé : la solution propre — attendre la 008 — bloquerait
la relecture de ce lot sur une branche qui n'est pas encore relue. ⚠️ **À
retirer au merge de la 008**, et c'est une ligne du plan, pas une intention.

---

## 5. L'écran

Une carte dans **Réglages**, réservée à l'administrateur, sous les réglages
existants. Rendu validé : [`maquettes/index.html`](maquettes/index.html).

Trois états, et le troisième est celui qui compte :

1. **Impossible** — un refus tient. La carte le dit, l'interrupteur est inerte.
2. **Prêt** — aucun refus, les avertissements listés. L'interrupteur est actif.
3. **Allumé** — la carte devient le rappel de ce qui a été retiré, et le seul
   chemin de retour arrière.

La confirmation est une boîte à **saisie de confirmation** — il faut écrire
`SUPPRIMER` — et non un simple « Confirmer ». C'est le seul geste de la console
dont la conséquence vit **hors** de la console : Adrien va ensuite supprimer un
fichier dans son Drive.

⚠️ Préfixes `sansClasseur*` (`carteSansClasseur`, `sansClasseurControle`,
`sansClasseurBasculer`) — deux autres branches travaillent dans `admin.html`, et
git fusionne sans conflit deux blocs ajoutés à des endroits différents.

---

## 6. Les fichiers touchés

| Fichier | Nature |
| --- | --- |
| `climbcontest/reglages.py` | **nouveau** — le réglage et le contrôle |
| `climbcontest/routes/admin.py` | 2 routes (`GET`/`POST /admin/mode-sans-classeur`), 8 gardes |
| `climbcontest/routes/sante.py` | le champ et le statut |
| `climbcontest/sheets/planificateur.py` | les gardes 1 et 2 |
| `climbcontest/sheets/mirror.py` | le garde 3 |
| `climbcontest/templates/admin.html` | la carte, et le masquage de la vue Classeur |
| `tests/test_mode_sans_classeur.py` | **nouveau** |
| `docs/contraintes-metier.md` | §2 : l'étape 3 est atteinte |
| `docs/runbook-competition.md` | la sauvegarde devient le seul filet |
| `docs/specs-index.md`, `CHANGELOG.md` | l'index et la section `[Non publié]` |
