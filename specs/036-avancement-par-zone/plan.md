# Plan — 036, l'avancement par zone

## Étapes

- [ ] **1. La spec, avant tout.** `spec.md`, `architecture.md`, ce fichier, et
      la ligne dans `docs/specs-index.md`. C'est la correction de ce qui a été
      reproché aux specs 027 et 032 : l'ordre doit se voir dans l'historique.
- [ ] **2. La maquette.** `maquettes/compteurs.html` — le vrai plan d'Annonay,
      la vraie géométrie, trois façons de poser le compteur, en clair et en
      sombre, en large et en 390 px. Trancher **dans la maquette**, écrire
      pourquoi dans `spec.md` / `architecture.md`.
- [ ] **3. Le compte, une seule fois.** `suivi.js` : `comptesDesZones` et
      `libelleCompte` ; `etatsDesZones` et `compteDeZone` en dérivent.
- [ ] **4. Le nœud.** `plan.js` : `COMPTE_ECHELLE`, `COMPTE_DESCENTE`,
      `PASTILLE_HAUTEUR`, `PASTILLE_LARGEUR`, `tailleDuCompte`, le
      `<rect class="socle-compte">` et le `<text class="compte-zone">` dans
      `decrire`, le quatrième argument de `decorer`.
- [ ] **5. Le style et le branchement.** `resultats.html` : les règles
      `.plan .socle-compte` et `.plan .compte-zone` (clair et sombre), le
      retrait de la pastille sur les zones sans compteur
      (`:not(.a-compte)`), l'appel `decorer(..., comptes)`,
      et `estFait` à la place du `b.etat !== "reste"` écrit à la main.
- [ ] **6. Les tests.** Un en face de chaque comportement — voir le tableau.
- [ ] **7. La vérification à l'écran.** `tools/serveur_de_demo.py`, un vrai
      navigateur : clair, sombre, 1280 px, 390 px. Captures dans la PR.
- [ ] **8. Le diff complet**, relu avec la grille de la phase 5, puis la PR.
      **Pas de merge** : la porte 7 appartient à Adrien.

## La pastille qui se remplit — le second lot, 03/09

Les étapes 1 à 8 ont livré le **compteur**. Le § 2 ter de la spec a ensuite
demandé qu'un objet **se remplisse** à hauteur de l'avancement — et il a fallu
deux passes pour savoir lequel :

- [x] **9. La première lecture, écrite puis jetée.** C'était le **cadre** de la
      zone : épaissi ×2, rogné dans le pan, rempli sur la longueur de son
      contour, avec la garantie de coin côté serveur que ça demandait. Montré à
      Adrien sur le rendu réel : « ce n'est pas ce que je voulais ». Retiré en
      entier. **La leçon est dans la spec** — une phrase qui décrit un objet à
      l'écran se vérifie en montrant l'objet.
- [x] **10. Le rendu réel, en HTML, avant de recoder.**
      `maquettes/pastille.html` : le SVG que `plan.js` monte vraiment, avec les
      quatre largeurs d'ovale, les trois forces de vert et les deux bouts de
      remplissage. Adrien a choisi **×1,6, franc, bout droit**.
- [x] **11. La position, mesurée puis choisie.** Six positions chiffrées sur le
      vrai dessin, parce que « descends la pastille » ne pouvait rien donner —
      il ne restait que 0,009 × taille dessous. Adrien a choisi **E,
      l'équilibre** : les trois airs égaux.
- [x] **12. Le code.** `plan.js` : `LETTRE_MONTEE`, `partFaite`, la découpe du
      socle, la couche des compteurs, la largeur du vert posée par `decorer`.
      `resultats.html` : la couleur du vert, la couche, le rebond sans lueur.
- [x] **13. Les tests, un en face de chaque décision.** La part, la découpe, la
      remise à zéro, l'ordre de peinture, les trois airs, et le vert mesuré
      dans un vrai navigateur.
- [ ] **14. La relecture d'Adrien, puis la PR.** Porte 7 : elle est à lui.

## Plan de test

Écrit **avant** l'implémentation, comme le veut `docs/workflow.md`.

### `tests/js/suivi.test.mjs` — le compte

| Scénario | Attendu |
| --- | --- |
| Zone avec 2 blocs, 2 faits | `{ total: 2, faits: 2, grimpes: 2, credites: 0 }` |
| Zone avec 1 bloc crédité | `faits: 1`, `credites: 1` — le crédité compte (spec § 6) |
| Zone entamée | `{ total: 2, faits: 1 }` |
| Zone absente du circuit | **absente** de `comptesDesZones`, pas `{0,0}` |
| Bloc sans zone | n'invente pas de zone |
| Groupes vides / `undefined` | `{}`, aucune exception |
| `libelleCompte({total:4, faits:1})` | `"1/4"` |
| `libelleCompte({total:4, faits:0})` | `"0/4"` — le zéro se dit |
| `libelleCompte(undefined)` et `{total:0}` | `""` — l'absence ne se dit pas |
| **Invariant A12** | pour toute zone, `etatsDesZones()[z] === "finie"` ⟺ `faits === total` — vérifié sur un jeu **contenant un crédité** |
| **Invariant A11** | `compteDeZone(g, z)` et `comptesDesZones(g)[z]` donnent le même couple |
| `etatsDesZones` / `compteDeZone` | les tests existants passent inchangés |

### `tests/js/plan.test.mjs` — le nœud et sa décoration

| Scénario | Attendu |
| --- | --- |
| `decrire` d'un plan sain | chaque groupe de zone porte `mur`, `trame`, `lettre`, `socle-compte`, `compte-zone` |
| Le nœud décrit | texte **vide**, `x` = étiquette, `y` = étiquette + `taille × COMPTE_DESCENTE` |
| La pastille décrite | centrée sur l'axe de la lettre et sur la descente, `rx` = sa demi-hauteur |
| Un libellé long | le **chiffre** rétrécit, la **pastille** ne bouge pas |
| Mur sans `taille` | repli à 6, comme la lettre — la taille du compteur reste > 0 |
| `decorer` avec des comptes | la zone porte `a-compte`, le texte vaut `"1/4"` |
| Zone sans bloc du circuit | pas de `a-compte`, texte vide |
| Zone terminée | `compte-finie` sur le texte |
| `decorer` **sans** comptes (4ᵉ argument omis) | aucun compteur, aucune exception — l'ancien appel reste valide |
| Deux décorations successives | le compteur suit, l'ancien ne persiste pas (le direct, F5) |
| Zone des comptes absente du plan | ignorée, aucune exception |
| Plan de format inconnu | `decrire` rend `null` : pas de nœud, donc pas de compteur |
| `tailleDuCompte(9, "1/4")` | `9 × 0.42` — pas de rétrécissement à trois caractères |
| `tailleDuCompte(9, "12/15")` | rétrécit ; largeur estimée ≤ `taille` |
| `tailleDuCompte(0, …)` | ne rend ni `0`, ni `NaN`, ni négatif |

### `tests/test_suivi.py` — l'accord entre les deux langages

| Scénario | Attendu |
| --- | --- |
| Le compteur tient dans son pan | pour **chaque** mur de `plan_public()`, la boîte du compteur (ratios relus **dans `plan.js`**) reste dans la boîte du pan |
| Les ratios sont introuvables dans `plan.js` | le test échoue en le disant, il ne se saute pas |

### `tests/test_navigateur_fiche.py` — dans un vrai navigateur

Le jeu semé porte déjà exactement ce qu'il faut : zone `Z` terminée (2 blocs,
2 faits), zone `A` entamée (2 blocs, 1 fait), zone `M` intacte (1 bloc, 0 fait),
et quatorze zones où le grimpeur n'a rien à faire.

| Scénario | Attendu |
| --- | --- |
| Le mur ouvert | trois compteurs, et trois seulement |
| Zone `Z` | `"2/2"` |
| Zone `A` | `"1/2"` |
| Zone `M` | `"0/1"` |
| Zone `D` (hors circuit) | compteur vide |
| Une réussite arrive pendant qu'on regarde | `A` passe à `"2/2"` **sans** remonter le mur |

### Ce qu'aucun test ne peut dire

Le contraste du chiffre sur les six remplissages de profil, en clair et en
sombre, et sa lisibilité à 390 px. Ça se regarde — étape 7 — et les captures
vont dans la PR.

## Commandes

```bash
.venv-dev/bin/python -m pytest tests/ -q
node --test "tests/js/*.test.mjs"
python3 tools/serveur_de_demo.py
```
