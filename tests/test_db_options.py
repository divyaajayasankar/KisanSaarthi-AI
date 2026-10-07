from app.db import engine_options


def test_sqlite_gets_thread_flag():
    assert engine_options("sqlite:///./kisansaarthi.db") == {"connect_args": {"check_same_thread": False}}
    assert engine_options("sqlite://") == {"connect_args": {"check_same_thread": False}}


def test_postgres_gets_no_sqlite_argument():
    options = engine_options("postgresql+psycopg2://user:pw@db:5432/kisan")
    assert "connect_args" not in options and options["pool_pre_ping"] is True
