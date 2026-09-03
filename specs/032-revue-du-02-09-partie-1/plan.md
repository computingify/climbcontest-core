# 032 — Plan et plan de test

> ⚠️ **Le plan de test s'écrit avant l'implémentation** (`docs/workflow.md`).
> Ici il a été écrit **après**, en même temps que la spec — comme pour la 027,
> la veille.
>
> **Ce que ça a coûté cette fois-ci : rien de mesurable, et c'est un coup de
> chance, pas une méthode.** La consigne d'Adrien — « tu me mets un test en face
> de chaque problème » — a joué le rôle du plan de test : elle a forcé un test
> par point, et chacun a été vérifié rouge sur le code d'avant. La 027, elle,
> avait payé six corrections sur treize sans aucun test.
>
> **La correction, pour la partie 2 qui vient** : quand Adrien dicte une liste
> de défauts, la première réponse est une spec avec sa liste de critères — pas
> un diagnostic suivi de code. Le diagnostic reste nécessaire, il devient le § 2
> de la spec au lieu d'un commit.

## Étapes

- [x] Diagnostic des neuf points, sur le dépôt réel et les deux PDF joints
- [x] Question posée à Adrien sur R5/R6 (périmètre de la rotation), réponse
      obtenue avant de coder
- [x] Console — cascade (R1, R2) et Circuits (R3)
- [x] Page de résultats — masque (R4), rotation (R5), bouton (R6)
- [x] Éditeur du plan — lien de retour (R7)
- [x] Impressions — géométrie (R8), étiquettes (R9), couleurs (R10)
- [x] Défaut trouvé en mesurant — grille bornée (R11)
- [x] Un test par point, chacun **vérifié rouge** sur `origin/master`
- [x] Fusion à blanc avec `master`, suite complète au vert
- [x] PR #87 ouverte, CI verte
- [x] **Porte 7 — mergée par Adrien** (`2bb4316`), pendant la rédaction de cette
      spec
- [x] Spec écrite (ce dossier), après le merge — voir l'encadré de `spec.md`
- [ ] ~~Porte 2~~ — **sans objet désormais** : elle ne peut plus précéder un
      code déjà mergé. Ce qui reste à Adrien est de **relire ce dossier** et de
      dire s'il décrit bien ce qu'il voulait
- [ ] Décision sur le point ouvert (§ 6 de la spec) : taille du numéro U15
- [ ] Le tirage papier chez Adrien, seule validation qui reste pour R8

## Plan de test

### Un test par point, tous rouges avant

| Point | Test | Ce qu'il tient |
| --- | --- | --- |
| R1 | `test_console_lisible.py::TestCarteCascade::test_sans_cascade_la_carte_ne_montre_pas_de_regle` | Le groupe existe, il se cache sur « aucune », et le titre est **dedans** |
| R2 | `…::test_sur_mesure_est_selectionnable_depuis_comme_le_classeur` | L'intention est mémorisée et prime sur la déduction |
| R2 | `…::test_l_avertissement_reste_calcule_sur_les_phrases` | Et surtout **pas** sur le bouton coché |
| R3 | `TestLaVueCircuitsNeMontreQueLaPastille` (3 tests) | Plus de texte, le nom reste au survol et pour les lecteurs d'écran, les en-têtes restent |
| R4 | `test_page_resultats.py::…::test_la_barre_AUSSI_respecte_les_classements_masques` | La barre passe par `groupesVisibles()` des deux côtés |
| R4 | `test_navigateur_reglages_resultats.py::TestUnClassementEteintDisparaitVRAIMENT` | **Dans un navigateur** : la pastille a disparu, et ce qui reste est là |
| R5 | `TestLaRotationDesPodiums::test_la_rotation_ne_renonce_plus_quand_il_n_y_a_rien_a_montrer` | Le réarmement existe |
| R5 | `test_navigateur_reglages_resultats.py::TestLeMurSeMetAJouerToutSeul` | **Dans un navigateur** : mur ouvert sans classement, ils arrivent, l'écran change de catégorie sans qu'on touche à rien |
| R6 | `TestLaRotationDesPodiums` (3 tests) | Le bouton est visible hors mur, part à l'arrêt, et dit son état avant le premier clic |
| R7 | `test_plan_du_mur.py::…::test_le_retour_a_la_console_mene_a_la_console` | L'adresse est **demandée au serveur**, pas comparée à une chaîne |
| R8 | `test_fiches.py::…::test_la_feuille_est_plus_PETITE_que_la_page` + jumeau étiquettes | L'**invariant**, calculé sur les nombres lus dans le CSS |
| R8 | `…::test_la_feuille_elle_meme_est_insecable` | La deuxième ligne de défense |
| R9 | `TestLEtiquetteRemplitSonPapier` (8 tests) | Les quatre lignes ≥ 4 mm, la pastille suit, et le numéro tient dans sa colonne sur toutes les longueurs |
| R10 | `TestLesCouleursSImpriment` des deux côtés | Le préfixe `-webkit-` **et** la propriété, plus les six teintes |
| R11 | `TestLaLargeurDUneFiche` (9 tests) | La grille tient dans sa colonne sur les vrais circuits et sur les cas extrêmes ; le couple retenu tient en hauteur ; c'est le plus gros texte qui gagne |

**Vérification décisive** : les nouveaux fichiers de test ont été rejoués tels
quels sur `origin/master`. **29 tests rouges**, aucun faux positif. Un test de
régression qui passe déjà avant ne prouve rien.

### Ce qui a été mesuré, et qu'aucun test ne rejoue

Ces mesures demandent un navigateur et une planche de 120 fiches. Elles sont
consignées ici pour qu'on sache ce qui a été vérifié, et comment.

| Mesure | Avant | Après |
| --- | --- | --- |
| Pages pour 120 fiches, zone imprimable 6 → 14 mm | 20 / **40 / 40 / 40 / 40** | 20 / 20 / 20 / 20 / 20 |
| Pages pour 60 étiquettes, idem | 8 / 8 / 8 / 8 / 8 | 8 / 8 / 8 / 8 / 8 |
| Hauteur rendue d'une feuille de fiches | **198,01** mm dans 198 utiles | 186,01 dans 190 |
| Cases de bloc hors de leur colonne | **120 / 120**, de 5,75 mm | **0 / 120** |
| Vide sous le texte d'une étiquette | **15,76** mm | 8,85 mm (soit ~4,4 en haut et en bas) |

### Ce qui n'est PAS couvert, et pourquoi

| Point | Pourquoi |
| --- | --- |
| Le rendu visuel des étiquettes agrandies | Purement visuel. Vérifié sur aperçu, montré à Adrien avant merge |
| L'accord des six constantes mesurées avec le CSS | **Aucun test ne peut le faire.** Se remesure au navigateur quand le gabarit change — c'est écrit en tête de `fiches.py` |
| L'impression sur la vraie imprimante d'Adrien | Hors du dépôt. C'est précisément ce qui a laissé passer R8 : la simulation remplace la mesure sur 6 → 14 mm de zone imprimable, elle ne remplace pas un tirage papier |

Le dernier est le seul qui reste vraiment ouvert : **la validation finale de R8
est un tirage papier chez Adrien**, pas un test.
