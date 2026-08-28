# Migrations

Fichiers `NNN_description.sql`, joués **en ordre** et **une seule fois** par
`climbcontest/schema.py`, sous verrou porté par la base — quatre workers
gunicorn démarrent en même temps, un seul doit migrer.

Le schéma initial n'a pas de fichier : il est créé par `db.create_all()` à
partir de `models.py`, qui reste la référence. Les migrations servent aux
**changements** ultérieurs.

Règles :

- une migration ne détruit jamais de données ;
- elle est **idempotente** autant que possible (`IF NOT EXISTS`) ;
- une fois jouée en production, elle ne se modifie plus — on en ajoute une.
