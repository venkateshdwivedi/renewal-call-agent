# db.py
# SQLite connection helper. SQLite keeps this demo deployable anywhere
# (Render/Railway free tier) with zero extra infra to manage.

import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "renewals.db")


def get_db_connection():
    """Returns a connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Runs schema.sql once at startup if the DB doesn't exist yet."""
    if os.path.exists(DB_PATH):
        return
    conn = get_db_connection()
    with open("schema.sql", "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
