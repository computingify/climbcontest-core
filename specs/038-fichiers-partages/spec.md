# Spec 038 — les fichiers que toutes les PR se disputent

> **Porte 2 franchie le 03/09.** Cette spec ne contient toujours aucune
> implémentation : son livrable était une **décision**, et elle est prise
> (section 5). Le découpage d'exécution est dans [plan.md](plan.md), en trois
> lots dont un seul demande une fenêtre sans PR ouverte.

## 1. D'où vient cette spec

Journée du 03/09/2026. Cinq PR à faire passer (#95, #96, #97, #98, #101),
toutes mergées dans la même après-midi. **Neuf conflits** résolus à la main :

| Fichier | Entre qui | Combien | Nature |
| --- | --- | --- | --- |
| `docs/specs-index.md` | #97↔#98, #97↔master, #96↔master, #95↔master | **4** | une ligne de tableau chacun |
| `CHANGELOG.md` | #98↔master, #96↔master | **2** | les deux ajoutent dans `[Non publié]` |
| `resultats.html` | #98↔master | 1 | **vrai** — deux battements de rafraîchissement |
| `test_navigateur_fiche.py` | #97↔#98 | 1 | **vrai** — deux sondes dans la même fonction |
| `fiches.py` | #96↔master | 1 | **vrai** — la R7 contre une factorisation |

**Trois** de ces neuf étaient de vrais désaccords : quelqu'un devait trancher,
et le conflit a joué son rôle. Les **six autres** ne disaient rien du tout —
deux branches avaient ajouté chacune sa ligne, au même endroit, sans se
contredire une seconde. Git n'a pas les moyens de faire la différence.

Deux fichiers concentrent donc **les deux tiers** du travail de résolution de la
journée, et aucune de ces six fois il n'y avait quoi que ce soit à décider.

Ce n'est pas une mauvaise journée : c'est la journée normale d'un dépôt où
plusieurs sessions livrent en parallèle. `docs/specs-index.md` a été modifié par
**37 commits** — **tous** sur les trente derniers jours, soit à peu près une
fois par PR. `CHANGELOG.md`, **47 commits en quatorze jours**. Deux fichiers que
*toutes* les PR touchent, et qu'aucune ne se partage.

## 2. Ce qu'on cherche

Que deux PR qui n'ont **rien à se dire** ne se conflitent pas. Et que les trois
conflits qui portaient un vrai désaccord continuent, eux, de se déclencher : un
conflit est une bonne chose quand il y a quelque chose à trancher.

### Ce qui est déjà décidé, et ne se rediscute pas ici

- **Les specs gardent leur numérotation à trois chiffres et leur ordre.**
  L'index se lit par numéro croissant ; le commit #65 (« l'index des specs : 018
  repasse après 017 ») dit que cet ordre compte pour Adrien.
- **L'index reste lisible sur GitHub**, sans outil : `CLAUDE.md` y envoie toute
  session qui démarre, et Adrien le consulte à la main.
- **Le CHANGELOG reste tenu à la main, en français, en prose.** Ce n'est pas une
  liste de commits ; c'est le corps de la release GitHub, affiché dans la carte
  « Version du serveur » de la console (spec 031).

### La contrainte qui décide

Le dépôt **squashe** ses PR, et plusieurs sessions travaillent en parallèle sans
se voir. Une solution qui demanderait de la coordination entre sessions — « on
se met d'accord sur qui écrit la ligne » — ne tiendra pas : c'est exactement ce
qui n'existe pas ici.

## 3. Ce qui a été mesuré

Cinq scénarios rejoués sur un dépôt git jetable, avec
`docs/specs-index.md merge=union` dans `.gitattributes`. Git dispose en effet
d'une stratégie « garder les deux côtés », qui est exactement ce qu'on a fait à
la main six fois aujourd'hui.

| # | Scénario | Résultat mesuré | Verdict |
| --- | --- | --- | --- |
| 1 | Deux branches ajoutent chacune sa ligne | fusionne **sans conflit**, les deux lignes présentes | ✅ |
| 2 | Idem, mais les numéros s'entrecroisent | fusionne — et rend **037 avant 036** | ⚠️ ordre faux, **silencieux** |
| 3 | Les deux créent la rubrique `### Modifié` | **une** rubrique, les deux entrées dessous | ✅ meilleur qu'attendu |
| 4 | L'une corrige une ligne, l'autre en ajoute une | la correction tient, l'ajout aussi | ✅ |
| 5 | **Les deux modifient la même ligne** | **deux lignes pour la spec 033**, sans un mot | ❌ le piège |

Le scénario 5 est celui qui interdit d'utiliser `merge=union` tout seul : il
transforme un conflit bruyant, que quelqu'un aurait tranché, en un doublon
silencieux que personne ne voit. C'est précisément la forme de défaut qu'Adrien
refuse — « je préfère que le piège soit impossible ou détectable, pas
documenté ».

Le scénario 2 est plus discret mais de la même famille : l'index sort dans le
désordre, et rien ne le dit.

## 4. Les trois variantes

### A — Le pansement : `merge=union` plus un garde — **écartée**

`.gitattributes` marque les deux fichiers `merge=union`, et un test refuse un
index dont les numéros ne sont pas **triés** et **uniques**.

Les scénarios 1, 3 et 4 passent tout seuls. Les scénarios 2 et 5 ne conflitent
plus mais **deviennent rouges au test**, et se réparent en dix secondes.

- **Coût** : deux lignes de `.gitattributes`, un test d'une vingtaine de lignes.
- **Ce que ça ne fait pas** : la ligne de l'index reste écrite à la main dans un
  fichier partagé. On a rendu le piège détectable, pas impossible.
- ⚠️ **Écartée** au profit de B + C, qui suppriment le fichier partagé au lieu
  de l'aménager. `merge=union` n'apparaît donc **nulle part** dans le plan :
  une fois que plus personne n'écrit dans un fichier commun, il n'a plus
  d'objet — et il aurait gardé le scénario 5 comme piège dormant.

### B — La ligne vit avec sa spec, et l'index se fabrique

Chaque `specs/XXX-nom/` porte son propre `resume.md` (numéro, nom, statut,
résumé). `tools/index_specs.py` fabrique `docs/specs-index.md` à partir des
dossiers, dans l'ordre des numéros. Le fichier reste **committé** — la
contrainte « lisible sur GitHub sans outil » est tenue — et un test vérifie
qu'il est bien ce que l'outil produit.

Une PR n'écrit alors plus que **des fichiers qu'elle est seule à posséder**.
Les cinq scénarios disparaissent à la racine : il n'y a plus de ligne partagée à
se disputer. Et une PR ne régénère même pas l'index — c'est la CI qui le fait
sur master après le merge (D5), donc un seul écrivain, jamais deux en même
temps.

- **Coût** : un générateur (~80 lignes), la migration d'**une ligne d'index
  par spec** en autant de `resume.md`, un test. (36 lignes au 03/09 au soir ;
  le compte bouge à chaque spec, d'où un critère qui compare plutôt qu'il ne
  chiffre.)
- **Bénéfice de bord** : le statut d'une spec vit **à côté** de la spec. C'est
  là qu'on le change quand on la livre, et l'oubli se voit dans le diff de la
  PR au lieu de se voir trois merges plus tard.

### C — Un fragment de changelog par PR

`CHANGELOG.md` cesse d'être écrit pendant le développement. Chaque PR dépose
`changelog.d/<numéro>-<slug>.md` — sa prose, sa rubrique. À la release, un outil
les assemble sous le nouveau titre de version et vide le dossier.

C'est le motif classique (`towncrier`, `scriv`), et il répond ici à **un second
problème, déjà rencontré** : les PR n'écrivent pas toujours leur section, et il
a fallu relire le changelog commit par commit avant de taguer. Avec un fragment
par PR, l'absence se voit — et un contrôle de CI peut l'exiger.

- **Coût** : un assembleur (~60 lignes), un contrôle de CI, et le geste de
  release change (une commande de plus avant de taguer).
- **Ce que ça change pour Adrien** : au moment de taguer, il relit un dossier de
  fragments au lieu d'une section — même prose, même travail.

## 5. Ce qu'Adrien a tranché

| # | Question | Décision (03/09) |
| --- | --- | --- |
| D1 | Une variante, ou plusieurs ? | **B et C, ensemble.** La variante A est écartée : on supprime le fichier partagé plutôt que de l'aménager. |
| D2 | Le CHANGELOG passe-t-il en fragments ? | **Oui**, et l'assemblage se fait **à la release**. `## [Non publié]` disparaît. |
| D3 | Un `resume.md`, ou une en-tête dans `spec.md` ? | **Un `resume.md` séparé** : on ne rouvre pas 200 lignes de prose pour changer un statut. |
| D4 | Quand migre-t-on ? | **Quand la release est publiée et qu'aucune PR n'est ouverte.** C'est le seul moment où `## [Non publié]` est vide, donc où la migration ne déplace aucune prose. |
| D5 | Quand l'index se fabrique-t-il ? | **La CI le régénère sur master après chaque merge.** Assembler l'index seulement à la release l'aurait laissé périmé entre deux — or `CLAUDE.md` y envoie toute session qui démarre. |

## 6. Critères d'acceptation

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| C1 | Deux branches qui ajoutent chacune sa spec fusionnent **sans conflit** | Le scénario 1, rejoué en test — aucune ne touche l'index |
| C2 | Deux dossiers `specs/NNN-*` de même numéro sont **refusés** | Le scénario 5, rejoué en test |
| C3 | Un `resume.md` dont le numéro ou le slug ne colle pas à son dossier est refusé | Test dédié |
| C4 | L'index sur master est exactement ce que l'outil produit | La CI le régénère et pousse si ça diffère |
| C5 | Une PR qui modifie `docs/specs-index.md` à la main est **refusée** | Garde de CI (lot C) |
| C6 | L'index reste lisible sur GitHub, sans outil | Relecture d'Adrien |
| C7 | Un vrai conflit de code **conflite toujours** | Aucun `merge=union` n'est posé nulle part ; un test le vérifie sur un fichier de prose |
| C8 | Aucune ligne de l'index actuel n'est perdue à la migration | Même nombre de lignes avant et après, et le diff de l'index régénéré est **vide** |
| C9 | Taguer avec des fragments non assemblés est **impossible** | `release.sh`, étape 0 |
| C10 | Un numéro de spec pris sur une branche non poussée est **visible** | `tools/numero_de_spec.py` lit aussi les branches locales et les PR ouvertes |

## 7. Cas limites

- **Une spec supprimée ou renumérotée.** Le commit #65 l'a déjà fait une fois
  (018 après 017). Désormais c'est un dossier qu'on déplace et l'index suit ; le
  test C2 attrape un numéro resté en double.
- **Les specs pressenties (008, 009) et les trous.** 030 est pris par une
  branche non mergée, 008 et 009 sont réservés sans dossier. Le générateur doit
  lire le **second** tableau tel quel, sans chercher de dossier en face.
- **Deux PR qui livrent la même spec.** Ne devrait pas arriver, arrive quand
  même : deux `resume.md` identiques fusionnent sans bruit, et le statut retenu
  est celui de la seconde mergée. C2 ne couvre pas ce cas ; il est laissé
  ouvert, à dessein — le coût d'un garde dépasse celui du défaut.
- **Le numéro pris sur une branche jamais poussée.** C'est le cas de `030` au
  03/09 : `specs/030-versions-visibles` n'existe que sur une branche locale, donc
  ni `git ls-remote` ni GitHub ni master ne le savent, et 030 passe pour libre.
  L'outil de numérotation lit donc aussi les branches **locales** — et pousse la
  réservation, parce qu'une réservation qui ne quitte pas le disque n'en est pas
  une.
- **Deux sessions qui réservent dans la même minute.** L'allocation ne peut pas
  les départager. C'est assumé : la garde de CI nomme le doublon avant le merge,
  quand renommer un dossier coûte encore trois secondes.

## 8. Hors périmètre

- Les **vrais** conflits de code (`fiches.py`, `resultats.html`,
  `test_navigateur_fiche.py` aujourd'hui). Ils doivent continuer de se
  déclencher — c'est le sujet de la fusion à blanc, pas de celui-ci.
- Le format du changelog lui-même, et le contenu des résumés de specs.
- L'ordre de merge des PR, et la stratégie squash du dépôt.
