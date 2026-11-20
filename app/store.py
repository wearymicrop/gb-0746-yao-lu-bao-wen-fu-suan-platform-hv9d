from contextlib import contextmanager
import json
import sqlite3

from app.errors import BusinessError
from app.manifest import canonical


class Ledger:
    def __init__(self, path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def source(self, identifier):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM sources WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise BusinessError("SOURCE_NOT_FOUND", "未找到数据来源", 404)
        return json.loads(row[0])

    def put_source(self, identifier, payload):
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO sources VALUES (?, ?)",
                (identifier, canonical(payload)),
            )
            return cursor.rowcount == 0

    def run(self, identifier):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM runs WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise BusinessError("RUN_NOT_FOUND", "未找到归档记录", 404)
        return json.loads(row[0])

    def put_run(self, payload):
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO runs VALUES (?, ?)",
                (payload["id"], canonical(payload)),
            )
            return cursor.rowcount == 0
