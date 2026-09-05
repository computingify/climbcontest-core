# Spec 046 — Plan de travail

## 1. Les étapes

### Étape 0 — la porte 2
- [ ] Adrien valide la spec et la maquette
- [ ] **L'ordre de merge** est arrêté : 008 → 044 → 046
- [ ] **B1 en refus dur** est confirmé (ou passe en avertissement)

### Étape 1 — le réglage
- [ ] `climbcontest/reglages.py` : `mode_sans_classeur()`, `basculer()`
- [ ] le repli sur `False`, et son test — une base illisible **n'éteint pas** l'import
- [ ] `GET` / `POST /admin/mode-sans-classeur`, réservées à l'admin

### Étape 2 — les gardes
- [ ] les six points de décision, dont **les trois du miroir** (démarrage, boucle, métier)
- [ ] les 409 sur les six routes classeur et les deux d'import
- [ ] `/health` : le champ, les compteurs à `null`, **et le statut qui reste `ok`**

### Étape 3 — le contrôle avant bascule
- [ ] `controle_avant_bascule(comp)` : deux refus, quatre avertissements
- [ ] l'enveloppe `try/ImportError` autour de la source d'inscrits de la 008

### Étape 4 — l'écran
- [ ] la carte dans Réglages, ses trois états, préfixes `sansClasseur*`
- [ ] la confirmation par **geste** : `confirmerParGeste` (créé par la 044)
- [ ] **en dernier** : `dlgConfirmer` d'`admin.html` passe sur le composant
      partagé — un déplacement de ~90 lignes, à faire quand les autres branches
      ont fusionné
- [ ] le masquage de `navClasseur` et `vueClasseur`
- [ ] un test de navigateur sur les trois états

### Étape 5 — la fermeture
- [ ] `docs/contraintes-metier.md` §2 : l'étape 3 est atteinte, avec sa date
- [ ] `docs/runbook-competition.md` : la sauvegarde de la base est le seul filet
- [ ] `docs/specs-index.md`, `CHANGELOG.md` (⚠️ toujours laisser un `[Non publié]`)
- [ ] **retirer l'enveloppe `try/ImportError`** une fois la 008 mergée
- [ ] fusion à blanc avec les branches en cours, console ouverte au navigateur
- [ ] PR, revue sur le diff complet, porte 7

---

## 2. Le plan de test

### 2.1 Le réglage

| Scénario | Résultat attendu |
| --- | --- |
| Base neuve | mode **éteint**, aucun comportement modifié |
| Ligne `reglage` illisible | `mode_sans_classeur()` rend **False** — l'import continue |
| Base injoignable | **False** aussi, et aucune exception ne remonte |
| Bascule par un organisateur, par un ouvreur | **403** |
| Le réglage change pendant que l'application tourne | le tour de boucle **suivant** le voit — pas au redémarrage |

### 2.2 Les gardes

| Scénario | Résultat attendu |
| --- | --- |
| Mode allumé, application démarrée | le fil de synchronisation **ne démarre pas** |
| Mode allumé **pendant** que le fil tourne | il s'arrête au tour suivant, sans tuer le lot en vol |
| `mirror.synchroniser()` appelé directement | sort en `ignoree` — la garde est dans le métier |
| Les six routes `/admin/classeur*` | **409**, message nommant le mode |
| `POST /admin/import/sheet` | **409** |
| Aucun appel réseau vers Google | vérifié par un client de classeur factice qui **lève** dès qu'on le touche |

### 2.3 `/health` — le piège du déploiement

| Scénario | Résultat attendu |
| --- | --- |
| Mode allumé, base saine | **200 `ok`**, `mode_sans_classeur: true`, compteurs à `null` |
| Mode allumé, base **injoignable** | **503 `degraded`** — le vrai défaut se voit toujours |
| Mode éteint | strictement le comportement actuel |

### 2.4 Le contrôle avant bascule

| Scénario | Résultat attendu |
| --- | --- |
| Aucune source d'inscrits | **B1**, bascule refusée |
| Compétition sans bloc | **B2**, bascule refusée |
| Compétition sans circuit | **B2** |
| 12 réussites en attente | **A1** en avertissement, bascule possible |
| Des blocs orphelins de circuit | **A2** |
| Des participants sans catégorie | **A3** |
| Tout est bon | `peut_basculer` vrai, **A4 affiché quand même** |
| La spec 008 est absente du dépôt | l'enveloppe tient, B1 se déclenche, rien ne casse |

### 2.5 Le retour arrière

| Scénario | Résultat attendu |
| --- | --- |
| Rallumer le classeur | vue, routes et fil reviennent |
| Les archives | lisibles dans les deux modes |
| Le jeton Google déposé | **toujours là** — aucun réglage ne détruit un fichier |

### 2.6 Le navigateur

| Scénario | Résultat attendu |
| --- | --- |
| État « impossible » | l'interrupteur est inerte, le refus est nommé |
| État « prêt » | les avertissements sont lus avant que le bouton s'active |
| Pointeur fin | le **maintien** est rendu ; tenu 2 s, il actionne |
| Pointeur grossier | le **glissement** est rendu ; poussé au bout, il actionne |
| Relâcher à mi-course | rien ne s'actionne, le curseur **revient au départ** |
| Entrée maintenue sur le curseur de glissement | actionne aussi — le clavier ne tombe pas du côté du glissement |
| `dlgConfirmer` (effacement des données) | se comporte **exactement** comme avant l'extraction |
| Mode allumé, compte **admin** | `navClasseur` et `vueClasseur` **absents** |

---

## 3. Ce qui pourrait mal tourner

| Risque | Ce qu'on fait |
| --- | --- |
| **Le déploiement se retire tout seul** parce que `/health` passe en `degraded` | le mode se nomme dans la réponse, le statut reste `ok`, et les **deux** cas sont testés |
| **Trois workers sur quatre continuent d'appeler Google** | le réglage est relu en base à chaque décision, jamais mémorisé |
| **Le fil déjà lancé ignore la bascule** | garde dans la boucle en plus du garde au démarrage |
| **On bascule et il manque des données que seul le classeur avait** | le contrôle avant bascule, avec deux refus durs |
| **On bascule sans pouvoir inscrire personne** | B1, et l'ordre de merge 008 → 044 → 046 |
| **L'enveloppe `try/ImportError` survit au merge de la 008** | une case à cocher de l'étape 5, et un test qui échoue si `inscriptions` existe sans être importé |
| **Deux implémentations du maintien dans `admin.html`** | l'extraction de `dlgConfirmer` vers le composant partagé est une étape du plan, pas une intention |
| **L'extraction casse un geste qui marche** | elle se fait en dernier, et `dlgConfirmer` garde ses tests existants — ils doivent passer sans être modifiés |
