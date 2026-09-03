# Plan : 035 — Refonte du design de l'application juge

Deux étapes, séparées par une décision d'Adrien. **La seconde ne commence pas
tant que la première n'est pas validée.**

## Étape 1 — Les maquettes (cette PR)

- [x] Relire l'existant : `juge.html`, `juge.js`, `couleurs.js`,
      `docs/inventaire-app-juge.md`, specs 007, 019, 027 — et lister ce qui ne
      doit **pas** être perdu (les huit contraintes C1→C8 de la spec)
- [x] Poser quatre directions qui se distinguent sur deux axes — clair/sombre,
      et jusqu'où va la couleur du circuit — plutôt que quatre nuances
- [x] Écrire la page de maquettes : un fichier, aucune dépendance, ouvrable en
      `file://`
- [x] Les cinq écrans, les cinq états, les six couleurs de circuit, les
      pastilles de file et le voyant réseau
- [x] Le scan simulé : appuyer sur une carte ouvre le viseur, qui rend un
      résultat — on essaie le geste, pas seulement l'image
- [x] Le mode plein écran, pour essayer au doigt sur le vrai téléphone
- [x] L'adresse rejouable (`?d=…&e=…&s=…&c=…`)
- [x] Captures à 390 × 844 exactement, une par direction et une par écran
- [x] Écrire `spec.md`, `architecture.md`, `plan.md`, mettre à jour
      `docs/specs-index.md`
- [ ] **Porte 2 — Adrien tranche D1 à D5** (§ 7 de la spec)

## Étape 2 — L'implémentation (spec et PR séparées, pas encore ouvertes)

Le découpage dépend de la direction retenue ; l'ossature, non.

- [ ] Ouvrir la spec d'implémentation, avec la direction retenue et les réponses
      à D2 → D5 recopiées en tête
- [ ] Réécrire le bloc `<style>` de `climbcontest/templates/juge.html` — et lui
      seul si la direction retenue n'est pas la D
- [ ] Direction D uniquement : introduire le conteneur `.textes` dans les deux
      cartes, et vérifier que `redessiner()` écrit toujours au bon endroit
- [ ] Mettre `<meta name="theme-color">` en accord avec le fond retenu.
      Il vaut `#0B0D11`, une couleur qui n'existe plus dans la feuille depuis le
      02/09 : c'est déjà faux aujourd'hui, ça se verrait sur un fond clair
- [ ] Vérifier l'écran d'accueil, qui hérite du fond par `background: inherit`
- [ ] Incrémenter la version de la coquille dans `static/juge/sw.js`, sinon les
      téléphones déjà installés gardent l'ancien CSS
- [ ] D4 tranchée « le Noir cesse d'être de la craie » : changer `couleurs.js`,
      **et prévenir que l'Android lit la même table**
- [ ] Essai sur un vrai téléphone, en salle, avant toute mise en production

## Plan de test

### Ce qui se teste sans navigateur

Le CSS ne se teste pas ; la **table des couleurs**, si. C'est la seule donnée
que la refonte peut casser en silence.

| Module | Scénario | Résultat attendu |
| --- | --- | --- |
| `couleurs.js` | `couleurDeCircuit("Jaune")`, `" vert "`, `"VIOLET"` | `#F5B72E`, `#34C56A`, `#A86CF0` — la casse et les espaces restent sans effet |
| `couleurs.js` | `couleurDeCircuit("turquoise")` | `null` — un circuit inconnu n'empêche pas de valider, l'écran reste neutre |
| `couleurs.js` | `encreSur("#F5B72E")` / `encreSur("#3E8CF7")` | encre sombre / encre claire — le seuil de luminance ne bouge pas |
| `couleurs.js` | D4 tranchée : le « Noir » change de valeur | Le test qui fixe la valeur du noir **tombe**, et c'est le but : il force à relire l'Android |

### Ce qui se teste à l'écran, et nulle part ailleurs

Trois des neuf défauts visuels de l'inventaire — D5, D9 et F10 — **ne sont
apparus qu'à l'écran**. La relecture de code ne les montrait pas. Cette grille
est donc à repasser en entier, sur un vrai téléphone, dans la direction
retenue.

| # | Ce qu'on regarde | Attendu |
| --- | --- | --- |
| V1 | Les 5 états de l'écran principal | Une seule étape active à la fois, jamais deux, jamais zéro |
| V2 | Les 6 circuits, un par un | La teinte prend l'écran ; le texte reste lisible dessus — **le Noir compris** |
| V3 | Hors-circuit | Bandeau jaune d'attention, bouton « Envoyer quand même », **jamais de rouge**, jamais de blocage |
| V4 | « Effacer » | Ne pèse pas autant qu'« Envoyer », et n'est pas collé dessous |
| V5 | Serveur injoignable | Voyant rouge **barré** — vérifié en coupant gunicorn, puis en le relançant, pour voir le voyant suivre dans les deux sens |
| V6 | File et refus | Pastilles dans l'en-tête ; la mise en page ne bouge pas sous le pouce quand elles apparaissent |
| V7 | iPhone à encoche | Rien sous l'encoche, rien sous la barre d'accueil, en portrait et après rotation |
| V8 | Cibles tactiles | ≥ 44 px, mesurées à l'inspecteur, y compris « Effacer » et le retour des écrans secondaires |
| V9 | Hors ligne | Wifi coupé, application relancée : elle s'habille — police et logo viennent du cache du service worker |
| V10 | Écran d'accueil | Le logo tient sur le nouveau fond, sans halo ni carré |
| V11 | Barre d'état iOS | `theme-color` en accord avec le fond : pas de bandeau noir au-dessus d'un écran clair |
| V12 | En salle, un vrai jour | La question de l'éblouissement (D2) ne se tranche que là |

### Ce qui n'est pas couvert par des tests

- **Le « waouh ».** Il se juge, il ne se mesure pas. C'est la raison d'être des
  maquettes et de la porte 2.
- **L'éblouissement en salle**, la lisibilité au soleil, la fatigue sur deux
  cents validations : aucun ne se simule sur un Mac.
- **L'écart avec l'app Android** si D5 conclut que le web part seul. Rien ne le
  détectera automatiquement : deux clients, deux dépôts, une seule identité par
  convention.
