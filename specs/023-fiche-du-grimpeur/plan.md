# Plan — 023 fiche-du-grimpeur

## Étapes

1. [ ] `climbcontest/fiches.py` — `PLAN`, `ZONES_DU_PLAN`, `_rang()`,
   `_blocs_par_circuit()`, `_plan_pour()`, `construire()`. Aucun Flask.
2. [ ] Tests de `fiches.py` — le tableau ci-dessous, avant le gabarit. C'est là
   qu'est la logique ; le reste est de la mise en page.
3. [ ] `routes/admin.py` — `page_dossards()` appelle `construire()`. Les
   paramètres et le journal ne changent pas.
4. [ ] `templates/dossards.html` réécrit : fiche A5, en-tête, tableau des blocs
   groupé par couleur, plan, légende, QR 28 mm.
5. [ ] `templates/admin.html` — la carte parle de « fiches », le bouton devient
   « Ouvrir les fiches ».
6. [ ] Tests de route — non-régressions comprises.
7. [ ] `docs/technical/classeur-google.md` — l'onglet `Fiches` passe à
   « ✅ repris » dans le tableau du § 5 bis.
8. [ ] Impression réelle : une page, coupée, mesurée.

## Plan de test

### `fiches` — la logique

| Scénario | Attendu |
| --- | --- |
| Circuit avec Jaune, Vert, Bleu mélangés | Ordre Jaune → Vert → Bleu, et par numéro dans chaque couleur |
| Deux blocs de même couleur, `J10` et `J9` | `J10` avant `J9` — le classeur trie sur la **chaîne**, pas sur le nombre. On reproduit, on ne corrige pas |
| Bloc sans couleur | En dernier, après Noir |
| Bloc de la compétition hors du circuit du grimpeur | **Absent** de la fiche |
| Grimpeur sans catégorie | `circuit is None`, `blocs == []`, `manque` renseigné |
| Catégorie « U11 F » sans circuit « U11 » en base | `manque` = circuit inconnu |
| Circuit existant, zéro bloc | `manque` = circuit vide |
| `tag = "ZJ6"`, `zone = "Z"` | `numero == "J6"` |
| `tag = "AB12"`, `zone = "AB"` | `numero == "12"` — la zone n'est pas supposée tenir sur une lettre |
| Bloc sans zone | `numero == tag`, aucune zone allumée |
| Zones du grimpeur = {Z, D, A} | Ces trois cases `sienne is True` sur le plan, les autres `False` |
| Un bloc en zone `U` | `hors_plan == ["U"]` |
| Aucun bloc hors plan | `hors_plan == []` |
| `PLAN` | 8 lignes de 7 cases ; `ZONES_DU_PLAN` en contient 17 |
| `PLAN` vs `classement.COULEURS` | `fiches` n'a **pas** sa propre liste de couleurs |
| 100 participants, 3 circuits | Nombre de requêtes SQL constant (A12), mesuré au compteur d'événements SQLAlchemy |

### `admin` — la route

| Scénario | Attendu |
| --- | --- |
| `GET /admin/dossards` | 200, `text/html`, une fiche par participant numéroté — **non-régression** |
| `?dossard=1` | Une seule fiche, celle-là — **non-régression** |
| `?categorie=U11 F` | Le lot de la catégorie — **non-régression** |
| Tri | Fiches par dossard croissant — **non-régression** |
| Aucun participant numéroté | La page le dit, 200 — **non-régression** |
| Anonyme, puis rôle insuffisant | 401, puis 403 — **non-régression** |
| Contenu | Nom, club, catégorie, circuit, numéros de bloc et lettres de zone présents |
| Aucune dépendance externe | Aucun `http://` ni `https://` hors du `xmlns` du SVG (A11) — **non-régression** |
| Le QR | `qr.svg` appelé avec le dossard nu ; les tests de décodage indépendant ne bougent pas (A3) |

### Ce qui ne se vérifie qu'à l'impression

| # | Geste | Attendu |
| --- | --- | --- |
| N1 | Imprimer la planche complète en PDF | Exactement 2 fiches par page, aucune coupée |
| N2 | Mesurer une fiche imprimée à 100 % | 142,5 mm de haut, QR de 28 mm |
| N3 | Scanner le QR d'une fiche imprimée avec un vrai téléphone | Le dossard, du premier coup |
| N4 | Imprimer un circuit de 50 blocs | Tout tient, rien ne déborde |
| N5 | Imprimer en noir et blanc | Le tableau et le plan restent lisibles |
