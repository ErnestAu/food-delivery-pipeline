import pytest

import db


class FakeResult:
    def to_pandas(self):
        return "rows"


class FakeCursor:
    def __init__(self, fail):
        self.fail = fail

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params=None):
        if self.fail:
            raise ConnectionError("session expired")

    def fetchall_arrow(self):
        return FakeResult()


class FakeConnection:
    def __init__(self, fail):
        self.fail, self.closed = fail, False

    def cursor(self):
        return FakeCursor(self.fail)

    def close(self):
        self.closed = True


@pytest.fixture
def connect(monkeypatch):
    """Patch sql.connect; each call hands out the next connection from `plan` (True = broken)."""
    made = []

    def install(*plan):
        def fake_connect(**kwargs):
            conn = FakeConnection(plan[len(made)])
            made.append(conn)
            return conn

        monkeypatch.setattr(db.sql, "connect", fake_connect)
        return made

    db._connection.clear()
    yield install
    db._connection.clear()


def test_queries_reuse_one_connection(connect):
    made = connect(False)
    assert db._execute("SELECT 1") == "rows" and db._execute("SELECT 2") == "rows"
    assert len(made) == 1


def test_a_dropped_connection_is_replaced_once(connect):
    made = connect(True, False)
    assert db._execute("SELECT 1") == "rows"
    assert len(made) == 2 and made[0].closed


def test_a_second_failure_reaches_the_caller(connect):
    connect(True, True)
    with pytest.raises(ConnectionError):
        db._execute("SELECT 1")
