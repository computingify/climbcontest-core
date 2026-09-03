# Spec 038 — les fichiers que toutes les PR se disputent

> **Cette spec ne contient aucune implémentation, et c'est volontaire.** Son
> livrable est une **décision** d'Adrien entre trois variantes, chacune chiffrée
> et chacune mesurée sur un dépôt d'essai — pas estimée.
>
> Le code viendra une fois la variante choisie, dans une PR qui suivra celle-ci.

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

### A — Le pansement : `merge=union` plus un garde

`.gitattributes` marque les deux fichiers `merge=union`, et un test refuse un
index dont les numéros ne sont pas **triés** et **uniques**.

Les scénarios 1, 3 et 4 passent tout seuls. Les scénarios 2 et 5 ne conflitent
plus mais **deviennent rouges au test**, et se réparent en dix secondes.

- **Coût** : deux lignes de `.gitattributes`, un test d'une vingtaine de lignes.
- **Ce que ça ne fait pas** : la ligne de l'index reste écrite à la main dans un
  fichier partagé. On a rendu le piège détectable, pas impossible.

### B — La ligne vit avec sa spec, et l'index se fabrique

Chaque `specs/XXX-nom/` porte son propre `resume.md` (numéro, nom, statut,
résumé). `tools/index_specs.py` fabrique `docs/specs-index.md` à partir des
dossiers, dans l'ordre des numéros. Le fichier reste **committé** — la
contrainte « lisible sur GitHub sans outil » est tenue — et un test vérifie
qu'il est bien ce que l'outil produit.

Une PR n'écrit alors plus que **des fichiers qu'elle est seule à posséder**.
Les cinq scénarios disparaissent à la racine : il n'y a plus de ligne partagée à
se disputer. Quand deux PR régénèrent l'index, `merge=union` évite le conflit et
le test dit s'il faut relancer l'outil — une commande, aucune relecture de
prose.

- **Coût** : un générateur (~80 lignes), la migration des **34 lignes**
  existantes en 34 `resume.md`, un test.
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

## 5. Ce qu'Adrien doit trancher

| # | Question | Ma recommandation |
| --- | --- | --- |
| D1 | Une variante, ou plusieurs ? | **A tout de suite** (ça peut partir aujourd'hui et ça soulage la semaine), **puis B**. A et B se composent : B a besoin du `merge=union` de A sur le fichier généré. |
| D2 | Le CHANGELOG passe-t-il en fragments (C) ? | **Oui**, mais dans une PR séparée : il touche le geste de release, qui est le tien. |
| D3 | Le `resume.md` de B, ou une en-tête dans `spec.md` ? | Un `resume.md` **séparé** : `spec.md` est long, et on ne veut pas rouvrir une prose de 200 lignes pour changer un statut. |
| D4 | Qui met le statut à jour quand une spec est livrée ? | Inchangé : la PR qui livre. B rend juste l'oubli visible dans son propre diff. |

## 6. Critères d'acceptation

| # | Critère | Comment on le vérifie |
| --- | --- | --- |
| C1 | Deux branches qui ajoutent chacune sa spec fusionnent **sans conflit** | Le scénario 1, rejoué en test |
| C2 | Un index dont les numéros ne sont pas triés est **refusé** | Le scénario 2, rejoué en test |
| C3 | Un index qui contient **deux fois le même numéro** est refusé | Le scénario 5, rejoué en test |
| C4 | L'index committé est exactement ce que l'outil produit (variante B) | Un test qui régénère et compare |
| C5 | L'index reste lisible sur GitHub, sans outil | Relecture d'Adrien sur la PR |
| C6 | Un vrai conflit de code **conflite toujours** | `.gitattributes` ne nomme que ces fichiers-là ; un test le vérifie |
| C7 | Aucune ligne de l'index actuel n'est perdue à la migration | 34 lignes avant, 34 après, comparées texte à texte |

## 7. Cas limites

- **Une spec supprimée ou renumérotée.** Le commit #65 l'a déjà fait une fois
  (018 après 017). En B, c'est un dossier qu'on déplace et l'index suit ; le
  test C3 attrape un numéro resté en double.
- **Les specs pressenties (008, 009) et les trous.** 030 est pris par une
  branche non mergée, 008 et 009 sont réservés sans dossier. Le générateur doit
  lire le **second** tableau tel quel, sans chercher de dossier en face.
- **Deux PR qui livrent la même spec.** Ne devrait pas arriver, arrive quand
  même : deux `resume.md` identiques fusionnent sans bruit, et le statut retenu
  est celui de la seconde mergée. C6 ne couvre pas ce cas ; il est laissé
  ouvert, à dessein — le coût d'un garde dépasse celui du défaut.
- **`merge=union` sur un fichier binaire** : sans objet, `.gitattributes` ne
  nomme que deux fichiers texte.

## 8. Hors périmètre

- Les **vrais** conflits de code (`fiches.py`, `resultats.html`,
  `test_navigateur_fiche.py` aujourd'hui). Ils doivent continuer de se
  déclencher — c'est le sujet de la fusion à blanc, pas de celui-ci.
- Le format du changelog lui-même, et le contenu des résumés de specs.
- L'ordre de merge des PR, et la stratégie squash du dépôt.
