# 028 — Plan et plan de test

## Étapes

- [x] Relevé de la salle par Adrien, avec la planche de dessin
- [x] `PLAN` en polygones, `PROFILS` ordonnés, `plan_pour()` réécrit
- [x] Le dossard rend un SVG, en noir et blanc
- [x] Relecture par un agent, et application de ses remarques
- [ ] Porte 2 — validation d'Adrien
- [ ] Porte 7 — merge

## Plan de test

### Ce qui se teste en Python

| Ce qu'on protège | Test |
| --- | --- |
| Le relevé : 17 murs, 3 repères, pas de contour | `TestLePlanEstUneConstanteDeLaSalle` |
| `ZONES_DU_PLAN` déduit, jamais recopié | `test_les_zones_sont_deduites_du_plan_pas_recopiees` |
| L'ordre des profils **est** l'information | `test_les_profils_vont_du_moins_au_plus_deversant` |
| Un profil inconnu ne fait pas tomber une impression | `TestUnProfilInconnuNeCassePasUneImpression` |
| Le cadrage déborde la vue de chaque côté | `TestLeCadrageNeRogneAucunTrait` |
| **Des murs touchent bien le bord** — si le relevé change, la marge se rediscute | `test_des_murs_touchent_bien_le_bord` |
| La lettre tient dans sa boîte, au pire glyphe | `TestLaLettreTientDansSonMur` |
| Le centroïde d'aire, et le repli sur un polygone dégénéré | `TestLaLettreVaAuCentreDeSurface` |

### Ce qui ne se teste QU'AU NAVIGATEUR

Ces quatre-là demandent un moteur de rendu ; ils sont mesurés à la main et le
résultat est consigné ici plutôt que laissé implicite.

| Mesure | Résultat |
| --- | --- |
| Lettres qui débordent de leur mur, halo compris | **0 sur 17**, marge minimale 1,02 unité |
| Traits rognés par le bord du dessin | **0** |
| Identifiants de motif en double dans le document | **0** |
| Hauteur du plan dans sa colonne | 42,8 mm pour 46 disponibles |

⚠️ `LARGEUR_CAPITALE` borne l'estimation, mais **aucun test Python ne peut
vérifier qu'elle décrit encore la police servie**. Si le gabarit change de
fonte, c'est une mesure au navigateur qui le dira, pas la suite.
