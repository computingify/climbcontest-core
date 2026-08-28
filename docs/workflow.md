# Méthode de travail

Reprise de la méthode utilisée sur Sowel : **rien ne se code avant qu'une spec
ne soit écrite et validée.**

## Le principe

Chaque évolution vit dans un dossier `specs/XXX-nom-court/` contenant trois
fichiers :

| Fichier | Contenu | Question à laquelle il répond |
| --- | --- | --- |
| `spec.md` | Besoin, périmètre, critères d'acceptation, cas limites | *Qu'est-ce qu'on fait, et comment sait-on que c'est fini ?* |
| `architecture.md` | Modèle de données, contrats d'API, flux, fichiers touchés | *Comment c'est construit ?* |
| `plan.md` | Découpage en étapes cochables + **plan de test** | *Dans quel ordre, et qu'est-ce qu'on vérifie ?* |

Numérotation séquentielle à trois chiffres (`001-`, `002-`…), nom en
kebab-case. L'index de toutes les specs est dans
[specs-index.md](specs-index.md).

## Les portes (gates)

Le déroulé complet, avec ses conditions de passage, est dans la skill
`.claude/skills/climbcontest-feature/SKILL.md`. En résumé :

| Porte | Condition | Ce qui casse si on la saute |
| --- | --- | --- |
| 1 | Besoin clair, questions posées et répondues | On construit la mauvaise chose |
| 2 | **Tu as validé la spec explicitement** | Implémentation jetée |
| 3 | Code sur une branche dédiée, jamais sur `master` | Prod cassée |
| 4 | Tests verts, pas de régression | Bug livré |
| 5 | Revue de code sur le diff complet | Bug évitable en prod |
| 6 | PR ouverte avec résumé + plan de test | Pas de relecture possible |
| 7 | **Tu as validé le merge explicitement** | Merge non désiré |

Les portes 2 et 7 sont les tiennes : je ne les franchis jamais seul.

## Deux règles de fond

**La spec avant le code.** Si je me rends compte en codant que la spec est
fausse, je m'arrête, je corrige la spec, je te la représente. Je ne « répare pas
en douce » en s'éloignant de ce qui a été validé.

**Le plan de test s'écrit avant l'implémentation.** Il est dans `plan.md`, sous
forme de tableau module × scénario × résultat attendu. Ça force à réfléchir aux
cas limites avant d'avoir le nez dans le code.

## Langue

Les specs et la documentation sont **en français** — projet francophone, un seul
mainteneur, relecture plus facile. Le code, les identifiants, les messages de
commit et les noms de branches restent en anglais.

## Branches et commits

- Préfixes de branche : `feat/`, `fix/`, `refactor/`, `docs/`
- Commits conventionnels : `feat(api): ...`, `fix(sheets): ...`
- Portées : `api`, `sheets`, `db`, `ranking`, `android`, `web`, `deploy`, `docs`
- Jamais de commit direct sur `master`, sauf correction triviale d'une ligne
