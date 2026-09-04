"""L'intégration HelloAsso — spec 008.

**HelloAsso alimente une salle d'attente ; c'est la salle d'attente qui décide
si un participant est créé.** Rien de ce qui vient du réseau n'écrit directement
dans `participant` : même séparation que la spec 002 entre la base et le
classeur — une source extérieure est une *entrée*, jamais une autorité.

| Module | Ce qu'il fait |
| --- | --- |
| `client.py` | Parler à l'API : jeton en base sous verrou, pagination |
| `releve.py` | Relever les articles et remplir la salle d'attente |
| `rapprochement.py` | Décider si cette personne est déjà dans la liste |
| `planificateur.py` | Le fil de fond, à cadence variable |

La règle des catégories n'est **pas** ici : elle vit dans `climbcontest/categories.py`,
parce qu'elle sert aussi au formulaire d'ajout manuel, à l'édition en ligne et
au bouton « Appliquer à tous ». La ranger sous `helloasso/` ferait dépendre la
saisie au guichet d'une intégration qui peut ne pas être branchée.
"""
