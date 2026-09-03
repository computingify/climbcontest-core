# Plan — spec 037

Branche : `feat/037-recherche-qui-se-deploie`, partie de `origin/master`.

⚠️ Elle part de `master` et **non** de `fix/revue-du-03-09`, alors que le code
final dépendra de cette dernière : la maquette, elle, ne dépend de rien. C'est
délibéré — Adrien mergeait ses PR au moment où cette branche a été créée, et une
branche de maquette qui ne dépend d'aucune autre se merge quel que soit l'ordre.

## 1. Étapes

- [x] **1. La maquette** — quatre variantes, au doigt, avec un ralenti ×4 et une
      bascule d'ordre des boutons. `maquettes/index.html`.
- [x] **2. La spec** — la question, ce qui est déjà décidé, les critères, et les
      trois points à trancher.
- [ ] **3. La décision d'Adrien** — porte 2. **Rien ne se code avant.**
- [ ] **4. L'implémentation**, dans une PR qui suit celle-ci, une fois la
      spec 033 mergée (elle porte les icônes dessinées dont ce lot dépend).
- [ ] **5. Les tests** du §2 ci-dessous.
- [ ] **6. Captures avant/après**, et revue du diff complet.

## 2. Plan de test

Écrit avant l'implémentation, comme le veut la méthode.

### Nominal

| Module | Scénario | Attendu |
| --- | --- | --- |
| `resultats.html` | L'ordre des commandes sur téléphone | La loupe est le dernier élément de la rangée |
| `resultats.html` | Appui sur la loupe | `aria-expanded="true"`, le champ reçoit le focus |
| `resultats.html` | On tape trois lettres | La liste se filtre, tous classements confondus |
| `resultats.html` | Second appui sur la loupe | Le champ se referme **et se vide**, la liste est complète |
| navigateur | Le geste entier : ouvrir, taper, filtrer, fermer | La liste revient à son état de départ |

### Cas limites

| Module | Scénario | Attendu |
| --- | --- | --- |
| `resultats.html` | Champ fermé | Il n'est **pas** dans l'ordre de tabulation |
| `resultats.html` | Échap, champ ouvert | Referme, et rend le focus à la loupe |
| `resultats.html` | Fermeture avec du texte | Le filtre est vidé avec le champ |
| `resultats.html` | `prefers-reduced-motion` | Aucune transition, le champ est simplement là |
| `resultats.html` | Écran de 320 px | Le champ se déploie ; seul le placeholder est tronqué |
| `resultats.html` | Fiche d'un grimpeur ouverte | La recherche ne s'ouvre pas derrière |

### Non-régression

| Module | Scénario | Attendu |
| --- | --- | --- |
| `resultats.html` | Mode `?mur` | Aucune recherche, aucun bouton — inchangé |
| `resultats.html` | La recherche part masquée | Décision D1, inchangée |
| `resultats.html` | Le réglage survit au rechargement | Inchangé (spec 033, R4/R6) |
| `resultats.html` | Les deux boutons disent leur état dès le gabarit | Inchangé (spec 033) |

## 3. Ce qui reste à trancher

Les trois points du §5 de la spec : la variante, le sens de l'échange, et ce
qu'on fait sur grand écran.
