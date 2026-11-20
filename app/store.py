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
                CREATE TABLE IF NOT EXISTS corrections (
                    id TEXT PRIMARY KEY,
                    base_sha TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS corrections_by_base
                    ON corrections(base_sha, id);
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        """写事务：更正链的读取、归并与落库必须互斥，避免并发分叉。"""
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
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

    @staticmethod
    def correction_in(conn, identifier):
        row = conn.execute(
            "SELECT payload FROM corrections WHERE id = ?", (identifier,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def chain_in(conn, base_sha):
        return [
            json.loads(row[0])
            for row in conn.execute(
                "SELECT payload FROM corrections WHERE base_sha = ? ORDER BY rowid",
                (base_sha,),
            )
        ]

    @staticmethod
    def insert_in(conn, record):
        """同一身份只落一次；返回是否本次写入。"""
        cursor = conn.execute(
            "INSERT OR IGNORE INTO corrections VALUES (?, ?, ?, ?)",
            (
                record["id"],
                record["base_input_sha256"],
                record["status"],
                canonical(record),
            ),
        )
        return cursor.rowcount == 1

    def correction(self, identifier):
        with self.connect() as conn:
            record = self.correction_in(conn, identifier)
        if record is None:
            raise BusinessError("CORRECTION_NOT_FOUND", "未找到更正结论", 404)
        return record

    def correction_chain(self, base_sha):
        """按提交顺序返回同一基础炉单的更正结论，末条为当前生效结论。"""
        with self.connect() as conn:
            return [
                json.loads(row[0])
                for row in conn.execute(
                    "SELECT payload FROM corrections WHERE base_sha = ? ORDER BY rowid",
                    (base_sha,),
                )
            ]
