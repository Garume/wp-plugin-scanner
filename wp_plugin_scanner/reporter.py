import sqlite3
from pathlib import Path
from threading import Lock

from .config import DB_PATH
from .models import PluginResult

class SQLiteReporter:
    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self._lock = Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS results (
                    slug TEXT PRIMARY KEY,
                    upload TEXT,
                    timestamp REAL
                )
                """
            )

    def already_done(self, slug: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM results WHERE slug=?", (slug,))
        return cur.fetchone() is not None

    def add_result(self, result: PluginResult) -> None:
        with self._lock:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO results (slug, upload, timestamp) VALUES (?, ?, ?)",
                    (result.slug, result.status, result.timestamp),
                )

    def fetch_page(self, page: int = 1, per_page: int = 20) -> list[PluginResult]:
        offset = (page - 1) * per_page
        cur = self.conn.execute(
            "SELECT slug, upload, timestamp FROM results ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        )
        rows = cur.fetchall()
        return [PluginResult(slug, upload, ts) for slug, upload, ts in rows]

    def count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM results")
        return cur.fetchone()[0]
