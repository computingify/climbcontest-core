# 027 — Plan et plan de test

> ⚠️ **Le plan de test s'écrit avant l'implémentation** (`docs/workflow.md`).
> Ici il a été écrit **après**, en même temps que la spec. C'est le manquement
> que ce dossier documente plutôt que de le masquer, et il a un coût mesurable :
> la relecture a trouvé **six corrections sur treize sans aucun test**, et le
> cœur du calcul d'impression sans une seule assertion.
>
> Ce fichier décrit donc l'état RÉEL de la couverture après la relecture.

## Étapes

- [x] Console — bouton à maintenir, import enchaîné, ordre et libellés, couleurs, aides
- [x] Impressions — colonnes calculées, pagination en feuilles, densité des étiquettes
- [x] Page de résultats — podium toujours affiché
- [x] Application juge — écran d'accueil, fond, cache v3
- [x] Relecture par un agent, et application de ses remarques
- [ ] Porte 2 — validation d'Adrien
- [ ] Porte 7 — merge

## Plan de test

### Ce qui est couvert par des tests

| Correction | Test |
| --- | --- |
| Colonnes calculées | `TestLaHauteurDUneFiche`, `TestLeNombreDeColonnes` — monotonie, coût d'une ligne, coût d'une marge, le cas des 43 blocs, la saturation du plafond |
| Pagination en feuilles | `TestLeDecoupageEnFeuilles` — liste vide, compte exact, dernière feuille incomplète, aucun élément perdu, 120 → 20 et 53 → 7 |
| Densité des étiquettes | `test_une_feuille_se_remplit` — compte les feuilles **réellement rendues** |
| Podium, tous les cas | `tests/js/podium.test.mjs` — 12 cas, dont les ex æquo qui sautent un rang et le masquage au-delà de six |
| Ordre des classements | `TestLOrdreDesClassementsVientDuServeur` — la règle, le circuit absent, et l'absence de copie en JavaScript |
| Cache du service worker | `test_la_coquille_prechargee_existe_vraiment` — chaque ressource répond 200 |

### Ce qui n'est PAS couvert, et pourquoi

| Correction | Pourquoi |
| --- | --- |
| Bouton à maintenir (F1) | Geste de deux secondes dans un `<dialog>` : le dépôt n'a pas d'infrastructure de test navigateur, et en ajouter une pour ce seul cas n'est pas justifié |
| Import enchaîné (F2) | Idem — enchaînement de deux appels réseau dans la console |
| Écran d'accueil (F11), fond (F12) | Purement visuels |
| Aides allégées (F6) | Du texte |

Ces quatre-là sont **vérifiés à la main**, et c'est dit ici plutôt que laissé
implicite.

### Ce que la relecture a mesuré, et qu'aucun test ne rejoue

- **0 chevauchement, 0 débordement** sur les 120 fiches — mesuré au navigateur.
- Le modèle de hauteur **ne sous-estime jamais** : sur dix configurations, il est
  de 0,03 à 0,35 mm **au-dessus** de l'encre réellement posée.

Ces mesures ne sont pas rejouables depuis le dépôt : elles demandent un
navigateur et un jeu de 120 grimpeurs. Elles sont consignées ici pour qu'on
sache ce qui a été vérifié, et comment.
