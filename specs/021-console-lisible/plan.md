# Plan — 021 console-lisible

## Étapes

1. [ ] **Les jetons de couleur.** Remplacer le bloc `:root` par les deux jeux
   (clair par défaut, sombre sous la requête média), déclarer
   `color-scheme: light dark`, ajouter `--accent-texte` et `--sur-accent`.
2. [ ] **Purger les couleurs en dur.** Le fond translucide de `.barre`, le
   `#17111f` de `button.action`, le `var(--carte2)` inexistant de
   `montrerConnexion()`, le liseré de `peindreRapport()`.
3. [ ] **Relire tout le style** avec les nouveaux jetons : cartes, tableaux,
   `dl.etat`, `fieldset.choix`, `dialog`, `#message`, le QR (`.qr-cadre` reste
   blanc, un QR sur fond sombre ne se lit pas).
4. [ ] **Le tiroir épinglé.** Media query `min-width: 1080px`, `--tiroir` en
   variable, `tiroirEpingle()` dans le script, Échap et le clic d'entrée qui en
   tiennent compte.
5. [ ] **La page Classeur.** Titre dans `VUES` et `<h1>`, retrait du bouton
   « Importer le classeur » et de son écouteur, phrase de renvoi vers
   Compétition.
6. [ ] **Le bouton à maintenir.** Retrait de `#dlgMot` et de son label, anneau,
   `demarrer/annuler/aboutir`, clavier, `aria-describedby`,
   `prefers-reduced-motion`. Les trois appelants de `confirmer()` gagnent un
   `libelle` qui nomme le volume détruit.
7. [ ] **`cycle.py`** : docstring de `exiger_confirmation()` et message d'erreur
   réécrits (marqueur de protocole, plus « frappé à la main »).
8. [ ] **Tests** : ceux du tableau ci-dessous.
9. [ ] **Vérification au navigateur** : la liste du bas, captures à l'appui.

## Plan de test

### Ce qu'un test Python peut vérifier honnêtement

| Module | Scénario | Attendu |
| --- | --- | --- |
| `pages` | La console est servie | 200, `text/html`, `<!doctype html>` |
| `pages` | Aucune dépendance extérieure | aucun `src=`/`href=` vers un domaine tiers, aucune police distante — non-régression de la règle des specs 005/016 |
| `pages` | Le nom de la page | « Classeur Google » n'apparaît plus comme titre ; « Classeur » est dans le tiroir, la barre et le `<h1>` |
| `pages` | Le bouton retiré | `id="btnImporterClasseur"` absent du gabarit |
| `pages` | La frappe retirée | `id="dlgMot"` absent du gabarit |
| `pages` | Le seuil du tiroir | `min-width: 1080px` présent une fois |
| `pages` | Les deux thèmes | `prefers-color-scheme: dark` présent ; `--fond` défini **hors** de toute requête média (le clair est le défaut, pas un cas particulier) |
| `cycle` | `exiger_confirmation("")` | `ErreurMetier` 400, rien touché — **non-régression** |
| `cycle` | `exiger_confirmation("EFFACER")` | passe — **non-régression** |
| `cycle` | `POST /admin/donnees/effacer` sans `confirmation` | 400, base intacte — **non-régression** |
| `cycle` | `POST /admin/donnees/effacer` avec `confirmation` | efface, comme aujourd'hui — **non-régression** |
| `import` | `POST /admin/import/sheet` depuis la vue Compétition | rapport identique à aujourd'hui — **non-régression** |

### Ce qui ne se vérifie qu'au navigateur

Le comportement du tiroir, du maintien et des couleurs est du CSS et du
JavaScript de page : le simuler en Python donnerait une fausse assurance (même
raison qu'en tête de `test_page_resultats.py`). Il se vérifie à la main, avec
capture, sur la console de développement :

| # | Geste | Attendu |
| --- | --- | --- |
| N1 | Ouvrir à 1280 px | Tiroir ouvert, pas de voile, pas de burger, contenu non recouvert (A10) |
| N2 | Cliquer « Réussites » à 1280 px | La vue change, le tiroir reste ouvert (A12) |
| N3 | Réduire à 900 px | Tiroir replié, burger de retour (A11) |
| N4 | Élargir à 1400 px, tiroir fermé | Tiroir ouvert : la media query décide (cas limite) |
| N5 | Compétition → Effacer, maintenir 2 s | Le geste part, le libellé nommait le volume (A5, A7) |
| N6 | Même fenêtre, relâcher à 1 s | Rien n'est envoyé, la fenêtre reste ouverte (A5) |
| N7 | Même fenêtre au clavier (Tab puis Entrée maintenue) | Même comportement (A6) |
| N8 | Effacer sur une compétition « en cours » sans cocher | Le maintien n'active rien (A8) |
| N9 | Mac en clair, puis en sombre | La page suit sans rechargement (A14) |
| N10 | Thème clair, lire chaque carte | Contraste confortable, aucun reste de mauve (A13) |

Captures attendues : `console-clair-1280.png`, `console-sombre-1280.png`,
`console-clair-900.png`, `console-maintien.png`.
