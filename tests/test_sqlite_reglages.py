"""Les PRAGMA de SQLite, et l'ordre dans lequel ils sont posés.

Ce fichier existe pour **une** raison, et elle vaut d'être écrite : le 05/09,
`PRAGMA busy_timeout` était exécuté APRÈS `PRAGMA journal_mode=WAL`.

Le passage en WAL demande un verrou **exclusif** sur la base. Quand quatre
workers gunicorn démarrent ensemble sur une base neuve — le démarrage réel du
service, et le scénario de `TestVerrouOrphelinAuRedemarrage` — celui qui arrive
pendant la transaction de schéma d'un autre échouait immédiatement sur
« database is locked » : son propre garde-fou n'existait pas encore.

Une attente ne protège que ce qui vient après elle. C'est le genre de défaut
qu'aucune relecture n'attrape, parce que les deux lignes sont justes prises
séparément — seul leur ORDRE est faux. D'où un test sur l'ordre.
"""

import sqlite3

import pytest

from climbcontest.sqlite_reglages import _regler_sqlite


def pragmas_executes() -> list[str]:
    """Les PRAGMA posés à la connexion, dans l'ordre.

    On appelle l'écouteur sur une VRAIE connexion SQLite et on écoute ce qu'elle
    exécute. Pas de fausse connexion : le premier geste de `_regler_sqlite` est
    un `isinstance(..., sqlite3.Connection)`, et une doublure le ferait sortir
    tout de suite — le test serait vert sans rien avoir vérifié.
    """
    vues = []
    cx = sqlite3.connect(":memory:")
    cx.set_trace_callback(lambda ordre: vues.append(ordre.strip()))
    try:
        _regler_sqlite(cx, None)
    finally:
        cx.set_trace_callback(None)
        cx.close()
    return [o for o in vues if o.upper().startswith("PRAGMA")]


def rang(pragmas: list[str], nom: str) -> int:
    for i, ordre in enumerate(pragmas):
        if nom in ordre.lower():
            return i
    raise AssertionError(f"« {nom} » n'est pas pose du tout : {pragmas}")


class TestLOrdreDesPragmas:
    def test_busy_timeout_est_pose_avant_le_passage_en_wal(self):
        """LE test de ce fichier. Le reste n'est que garde-fou autour."""
        pragmas = pragmas_executes()
        assert rang(pragmas, "busy_timeout") < rang(pragmas, "journal_mode"), (
            "busy_timeout doit venir AVANT journal_mode=WAL : le passage en WAL "
            f"prend un verrou exclusif et echouerait sans attente. Vu : {pragmas}")

    def test_les_quatre_pragmas_sont_poses(self):
        """Sans lui, retirer une ligne rendrait le test d'ordre vert par
        accident -- `rang()` leve, mais seulement sur les deux qu'il regarde."""
        pragmas = pragmas_executes()
        for attendu in ("busy_timeout", "journal_mode", "synchronous",
                        "foreign_keys"):
            rang(pragmas, attendu)


class TestLesValeursAppliquees:
    """Ce que la base répond vraiment, une fois l'écouteur passé."""

    @pytest.mark.parametrize("pragma,attendu", [
        ("busy_timeout", 5000),
        ("foreign_keys", 1),
        # NORMAL, et non FULL : le compromis est documente dans le module.
        ("synchronous", 1),
    ])
    def test_la_valeur_est_bien_celle_annoncee(self, pragma, attendu):
        cx = sqlite3.connect(":memory:")
        try:
            _regler_sqlite(cx, None)
            assert cx.execute(f"PRAGMA {pragma}").fetchone()[0] == attendu
        finally:
            cx.close()

    def test_une_connexion_qui_n_est_pas_sqlite_est_laissee_tranquille(self):
        """PostgreSQL un jour : l'ecouteur doit sortir sans rien tenter."""
        class PasSqlite:
            def cursor(self):
                raise AssertionError("l'ecouteur a touche a une connexion non-SQLite")

        _regler_sqlite(PasSqlite(), None)
