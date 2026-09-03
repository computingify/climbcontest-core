# Plan : 031 — Mettre à jour depuis la console

## Étapes

- [x] 1. Arrêter, désactiver et supprimer `climbcontest-deploy.timer` sur la VM 110
- [x] 2. Le retirer de `deployment/` et de `install.sh` ; corriger le commentaire
      de `climbcontest-deploy` qui parlait du minuteur
- [x] 3. Maquette des cinq états, validée avant tout code
      ([`maquettes/carte-version.html`](maquettes/carte-version.html))
- [x] 4. `climbcontest/maj.py` — vérification quotidienne, blocage, délégation
- [x] 5. Trois routes `@exige_role(ADMIN)` dans `routes/admin.py`
- [x] 6. Console : pastille du bandeau, carte des Réglages, fenêtre de confirmation
- [x] ~~7. Élargir `/etc/sudoers.d/climbcontest` au démarrage du service de
      déploiement~~ 🔴 **défait le 2026-09-03** : `sudo` ne peut pas aboutir
      sous `NoNewPrivileges=true`. Remplacé par `climbcontest-deploy.path`, et
      la règle est retirée. Voir `architecture.md` § 4.
- [x] 8. `tests/test_maj_serveur.py` — ⚠️ ces tests remplaçaient
      `subprocess.run` par un leurre : ils prouvaient qu'on **appelait** `sudo`,
      la seule chose qui ne pouvait pas marcher. Complétés le 03/09 par
      `tests/test_deploiement_sans_privileges.py`.
- [x] ~~9. Poser le sudoers sur la VM 110~~ → **poser le guetteur** sur la
      VM 110 : `install -m 0644 climbcontest-deploy.path /etc/systemd/system/`,
      `systemctl daemon-reload`, `systemctl enable --now climbcontest-deploy.path`.
      Fait le 2026-09-03 au soir, chaîne vérifiée de bout en bout.
- [ ] 10. Relecture, PR, merge (portes 5 à 7)

## Plan de test

| Module | Scénario | Attendu |
| --- | --- | --- |
| Cadence | première consultation | 1 requête GitHub |
| Cadence | trois consultations d'affilée | toujours 1 |
| Cadence | dernière vérification il y a 25 h | 2 |
| Cadence | bouton « Vérifier » | appel forcé, sans attendre l'échéance |
| Cadence | horodatage vu **pendant** l'appel | déjà écrit — le worker suivant ne repart pas |
| Lecture | GitHub rend le même tag | `disponible: null`, aucune erreur |
| Lecture | GitHub rend un tag plus récent | tag + changelog remontés |
| Lecture | 403 avec `x-ratelimit-remaining: 0` | le mot « quota » dans l'erreur |
| Lecture | GitHub muet après une version connue | l'erreur s'ajoute, le tag connu reste |
| Compétition | statut `en_cours` | `blocage` renseigné |
| Compétition | statut `en_cours` + `installer()` | `ErreurMaj`, **aucun** `systemctl` |
| Compétition | statut `preparation` | rien ne bloque |
| Installation | cas nominal | `systemctl start --no-block climbcontest-deploy.service` |
| Installation | tag périmé à l'écran | refus |
| Installation | issue lue après 2 h | plus annoncée |
| Portes | sans session | 401 |
| Portes | organisateur, lecture | 403 |
| Portes | organisateur, installation | 403 |
| Portes | admin, lecture | 200 |
| Portes | admin, installation pendant une compétition | 409 |
| Rangement | après une vérification | la ligne `reglage` existe |

**Résultat : 21 tests, tous verts.** Suite complète : **1453 passés, 11 ignorés**.

## Ce qui n'est pas couvert par des tests

**Le redémarrage réel.** Personne ne peut, en test, tuer le processus qui répond
et vérifier que la console s'en remet. Ça se vérifie une fois à la main, sur la
VM, hors compétition : cliquer « Installer », voir la carte passer à
« Installation en cours… », puis à « v0.17.0 installée » sans avoir été
déconnecté.

**Le quota GitHub réel.** La réponse 403 est simulée. Le vrai dépassement s'est
produit le 30/08 et c'est ce qui a motivé la spec ; on ne va pas le reproduire.
