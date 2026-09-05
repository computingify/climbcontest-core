"""Réglages SQLite appliqués à chaque connexion.

Pourquoi SQLite et pas PostgreSQL : docs/technical/banc-base-de-donnees.md.
En deux lignes — mesuré sur la VM 110, SQLite est 43 % plus rapide en débit et
coûte 120 Mo de RAM en moins. PostgreSQL a été purgé le 28/08.

Mesuré le 2026-08-28 sur ce code, 800 écritures distinctes, 40 en parallèle,
4 workers gunicorn × 4 threads, base neuve à chaque essai :

| `journal_mode` | médiane | p95 | max |
| --- | --- | --- | --- |
| `delete` (défaut) | 59,1 ms | 192,4 ms | **463,7 ms** |
| **`wal`** | **4,5 ms** | **18,9 ms** | 127,1 ms |

Treize fois plus rapide sur la médiane, dix fois sur le p95.

À la charge réelle (~5 requêtes/seconde en pointe), les deux tiennent. Mais
463 ms sur une rafale, c'est le délai qui fait qu'un juge appuie une seconde
fois sur « Envoyer » — et l'idempotence encaisse le double appui, mais autant ne
pas le provoquer.

Pourquoi `delete` est lent ici : c'est le mode par défaut de SQLite, où **un
écrivain bloque les lecteurs**. Avec quatre workers de quatre fils, seize
requêtes se disputent le même verrou. WAL sépare le journal du fichier
principal : les lectures ne bloquent plus, et une seule écriture progresse à la
fois sans faire attendre le reste.
"""

import logging
import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


@event.listens_for(Engine, "connect")
def _regler_sqlite(connexion, _record):
    """Applique les pragmas à chaque nouvelle connexion SQLite.

    À la connexion, et pas une fois au démarrage : chaque worker gunicorn ouvre
    ses propres connexions, et le pool en recrée après un recyclage.
    """
    if not isinstance(connexion, sqlite3.Connection):
        return                                    # PostgreSQL un jour : rien à faire

    curseur = connexion.cursor()
    try:
        # ⚠️ EN PREMIER, et c'est tout l'objet du correctif du 05/09.
        #
        # Attendre plutôt que d'échouer sur « database is locked ». Cinq
        # secondes, c'est très au-dessus de toute contention observée ici.
        #
        # Il était posé APRÈS le passage en WAL. Or ce passage demande un verrou
        # EXCLUSIF sur la base : quand quatre workers gunicorn démarrent
        # ensemble sur une base neuve, celui qui arrive pendant la transaction
        # de schéma d'un autre échouait immédiatement — son propre garde-fou
        # n'existait pas encore. Une attente ne protège que ce qui vient après
        # elle.
        #
        # Le symptôme était un rouge intermittent de la CI, sur
        # `TestVerrouOrphelinAuRedemarrage` : « ConnectionResetError » côté
        # test, parce que le worker mourait. Mesuré avant / après, 30 et 70
        # exécutions : 1 échec sur 30, puis 0 sur 70.
        curseur.execute("PRAGMA busy_timeout=5000")
        # Le gain mesuré ci-dessus.
        curseur.execute("PRAGMA journal_mode=WAL")
        # NORMAL au lieu de FULL : on ne fsync plus a chaque transaction.
        # Le risque est de perdre les toutes dernieres ecritures sur une coupure
        # de courant BRUTALE de la machine -- pas sur un crash applicatif, ou
        # WAL protege tout. Sur une VM avec onduleur, et pour des donnees qui
        # sont aussi dans le classeur, le compromis est le bon.
        curseur.execute("PRAGMA synchronous=NORMAL")
        # Integrite referentielle : SQLite ne l'applique PAS par defaut. Sans
        # ca, une reussite pourrait pointer vers un participant supprime.
        curseur.execute("PRAGMA foreign_keys=ON")
    finally:
        curseur.close()
