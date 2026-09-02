# 029 — Plan et plan de test

## Étapes

- [x] Table `reglage`, module `plan_du_mur` (lecture, validation, écriture)
- [x] `fiches.PLAN` devient le défaut ; `plan_courant()` lit la base d'abord
- [x] Page `/admin/plan`, routes `POST` et `DELETE`, carte dans la console
- [x] Le plan voyage avec le catalogue et incrémente sa version
- [x] `tools/plan-du-mur/` supprimé
- [x] Relecture par un agent, et application de ses remarques
- [ ] Porte 2 — validation d'Adrien
- [ ] Porte 7 — merge

## Plan de test

### La validation, ligne par ligne du tableau F5

| Contrôle | Test |
| --- | --- |
| Structure, `vue`, bornes 40–400 | `TestLaValidationRefuseCeQuiDoitLEtre` |
| Au plus 200 murs / 50 repères / 60 points / 60 points de contour | `TestLesBornesAnnonceesParLaSpec`, `TestLesQuatreCheminsDeCoordonneesSontBornes` |
| **Les quatre** chemins de coordonnées bornés à la vue | `TestLesQuatreCheminsDeCoordonneesSontBornes` |
| **Le non-fini refusé partout** | `TestLeNonFiniNeDoitJamaisPasser` |
| Document > 256 ko → **413**, contrôlé avant l'analyse | `test_un_document_trop_gros_repond_413` |
| Profil inconnu replié, zone tronquée et capitalisée, repère vide ignoré | `TestCeQuiEstReparableEstRepare` |
| Ce que le serveur a réparé revient à la page | `test_l_enregistrement_renvoie_le_plan_TEL_QU_IL_A_ETE_RANGE` |

### Le repli, qui est la deuxième règle du module

| Cas | Test |
| --- | --- |
| JSON tronqué, document absurde, texte quelconque | `TestUneLigneAbimeeNeCassePasUneImpression` |
| Le repli est journalisé | `test_le_repli_est_journalise` |

### Le tour complet

| Ce qu'on protège | Test |
| --- | --- |
| Le dossard porte le plan enregistré, et **plus l'ancien** | `test_le_dossard_porte_le_nouveau_plan` |
| Un plan refusé ne touche à rien | `test_un_plan_refuse_ne_touche_a_rien` |
| Retour à l'usine, et il renvoie le plan d'usine | `TestLesRolesEtLesReparationsSontVisibles` |
| Un plan vide fait **disparaître** la colonne | `TestUnPlanVideNeLaissePasUnCadreVide` |
| Anonyme → 401, **compte sans rôle → 403** | `TestLaRouteDeLaConsole`, `test_un_role_insuffisant_est_refuse` |
| Aucune ressource extérieure dans la page | `test_la_page_n_appelle_rien_a_l_exterieur` |
| Qui a enregistré est tracé | `test_qui_a_enregistre_est_trace` |

### Le catalogue

| Ce qu'on protège | Test |
| --- | --- |
| Il porte le plan **enregistré**, pas celui d'usine | `test_il_porte_le_plan_ENREGISTRE_pas_celui_d_usine` |
| Enregistrer, et revenir à l'usine, incrémentent la version | `test_enregistrer_un_plan_incremente_la_version` |
| **Le scénario complet du 304** : à jour, puis plus à jour | `test_un_client_a_jour_avant_le_changement_recoit_le_nouveau_plan` |
| Il reste lisible par un analyseur **strict** | `test_le_catalogue_reste_lisible_par_un_analyseur_strict` |
| Dessiner hors saison n'échoue pas | `test_dessiner_hors_saison_ne_fait_pas_echouer` |

### ⚠️ Ce qui n'est PAS couvert

**Le JavaScript de `plan.html`** — environ mille lignes — n'a aucun test, alors
que `tests/js/` en porte pour huit autres gabarits. `versLeServeur()` et
`depuisLeServeur()` sont des fonctions **pures**, donc testables : c'est le trou
le plus facile à combler du lot, et il est signalé ici plutôt que passé sous
silence. Les deux défauts que la relecture y a trouvés — le retour à l'usine qui
réaffiche le plan supprimé, `"use strict"` rendue inerte — auraient été pris par
des tests.
