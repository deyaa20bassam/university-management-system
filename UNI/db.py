"""Database helpers (SQLite). All SQL uses parameters (?) - never string formatting of user input."""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("UNI_DB", os.path.join(BASE_DIR, "university.db"))


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # SQLite needs this on every connection
    return conn


def init_db(path=None, with_sample_data=True):
    """(Re)create the database from schema.sql (+ sample_data.sql)."""
    path = path or DB_PATH
    if path != ":memory:" and os.path.exists(path):
        os.remove(path)
    conn = connect(path)
    for name in ["schema.sql"] + (["sample_data.sql"] if with_sample_data else []):
        with open(os.path.join(BASE_DIR, name), encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    return conn


def query(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn, sql, params=()):
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None
