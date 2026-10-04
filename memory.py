"""Neural's dual memory.

Short-term: the recent messages of the current conversation.
Long-term:  facts about you that persist across every conversation.
Everything is stored locally in a SQLite file (data/neural.db).
"""
import os
import sqlite3
import time
from contextlib import contextmanager


class Memory:
    def __init__(self, data_dir):
        self.path = os.path.join(data_dir, "neural.db")
        self._init()

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self):
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    ts REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conv_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    ts REAL NOT NULL
                );
                """
            )

    # ---- conversations -------------------------------------------------
    def new_conversation(self, title="New chat"):
        with self._db() as db:
            cur = db.execute(
                "INSERT INTO conversations (title, ts) VALUES (?, ?)", (title, time.time())
            )
            return cur.lastrowid

    def list_conversations(self):
        with self._db() as db:
            rows = db.execute(
                "SELECT id, title, ts FROM conversations ORDER BY ts DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def conversation_exists(self, conv_id):
        with self._db() as db:
            return db.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone() is not None

    def rename_conversation(self, conv_id, title):
        with self._db() as db:
            db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))

    def delete_conversation(self, conv_id):
        with self._db() as db:
            db.execute("DELETE FROM messages WHERE conv_id = ?", (conv_id,))
            db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))

    # ---- messages ------------------------------------------------------
    def add_message(self, conv_id, role, content):
        with self._db() as db:
            db.execute(
                "INSERT INTO messages (conv_id, role, content, ts) VALUES (?, ?, ?, ?)",
                (conv_id, role, content, time.time()),
            )
            db.execute("UPDATE conversations SET ts = ? WHERE id = ?", (time.time(), conv_id))

    def get_messages(self, conv_id, limit=None):
        with self._db() as db:
            rows = db.execute(
                "SELECT role, content, ts FROM messages WHERE conv_id = ? ORDER BY id",
                (conv_id,),
            ).fetchall()
        msgs = [dict(r) for r in rows]
        return msgs[-limit:] if limit else msgs

    # ---- long-term facts ----------------------------------------------
    def add_fact(self, text):
        text = text.strip()
        if not text:
            return None
        with self._db() as db:
            dup = db.execute(
                "SELECT id FROM facts WHERE lower(text) = lower(?)", (text,)
            ).fetchone()
            if dup:
                return dup["id"]
            cur = db.execute("INSERT INTO facts (text, ts) VALUES (?, ?)", (text, time.time()))
            return cur.lastrowid

    def list_facts(self):
        with self._db() as db:
            rows = db.execute("SELECT id, text, ts FROM facts ORDER BY id").fetchall()
            return [dict(r) for r in rows]

    def delete_fact(self, fact_id):
        with self._db() as db:
            cur = db.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
            return cur.rowcount > 0
