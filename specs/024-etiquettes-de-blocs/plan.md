# Plan — 024 étiquettes-de-blocs

## Étapes

1. [ ] `fiches.etiquettes()` — regroupement par zone, ordre `Bloc.numero`,
   `numero` sans préfixe, drapeau de coupure. Deux requêtes.
2. [ ] Tests de `fiches.etiquettes()` — le tableau ci-dessous.
3. [ ] `templates/etiquettes.html` — grille par zone, QR 45 mm.
4. [ ] `routes/admin.py` — `GET /admin/etiquettes` et son journal.
5. [ ] `templates/admin.html` — la carte dans la vue **Circuits**.
6. [ ] Tests de route.
7. [ ] Impression réelle : une planche, coupée, scannée avec un vrai téléphone.

## Plan de test

### `fiches.etiquettes()`

| Scénario | Attendu |
| --- | --- |
| 20 blocs sur 4 zones | 20 étiquettes, ordre `Bloc.numero` |
| Changement de zone | `coupure is True` sur le premier bloc de chaque zone… |
| Premier bloc de la planche | …mais `False` sur le tout premier : pas de page blanche en tête |
| `zone="Z"` | Seuls les blocs de `Z` ; `coupure` faux partout |
| `zone="Q"` inconnue | Liste vide, aucune exception |
| `tag="ZJ6"` | Une étiquette |
| `tag` inconnu | Liste vide |
| Bloc `tag="ZJ6"`, `zone="Z"` | `numero == "J6"` |
| Bloc sans zone | `numero == tag` |
| Bloc sans circuit | `circuits == []` |
| Bloc sur 3 circuits | Les trois, triés |
| Bloc sans couleur de prises | `couleur_prises is None` |
| Contenu du QR | `qr.svg` reçoit le `tag` complet, jamais le numéro seul |
| 100 blocs, 20 zones | Nombre de requêtes SQL constant (A11) |

### La route

| Scénario | Attendu |
| --- | --- |
| `GET /admin/etiquettes` | 200, `text/html`, une étiquette par bloc |
| `?zone=Z` / `?bloc=ZJ6` | Le sous-ensemble attendu |
| `?zone=Q` inconnue | 200, page qui nomme la zone |
| Aucun bloc en base | 200, message qui renvoie vers l'import |
| Aucune compétition active | 409 |
| Anonyme / organisateur / admin | 401 / 200 / 200 |
| Aucune dépendance externe | Aucun `http://` hors du `xmlns` du SVG |
| Journal | Une ligne avec le nombre et l'identifiant, jamais le contenu |

### `qr` — non-régression

| Scénario | Attendu |
| --- | --- |
| `qr.code("ZJ6")` | Jamais un Micro QR |
| Décodeur indépendant sur `ZJ6` à 45 mm | Relit `ZJ6` |

### À l'impression

| # | Geste | Attendu |
| --- | --- | --- |
| N1 | Imprimer toutes les étiquettes en PDF | Une zone par page, 6 par page, aucune coupée |
| N2 | Scanner une étiquette imprimée avec un vrai téléphone | `ZJ6`, du premier coup, à trente centimètres |
| N3 | Lire le numéro à deux mètres | Lisible |
