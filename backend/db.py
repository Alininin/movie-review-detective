"""SQLite 历史记录存储。

设计文档 6.2.2：单条情感分析历史保存到 SQLite，至少记录文本、两种结果、分数和时间；
支持查看和删除；刷新页面或重启服务后仍然存在。
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from common import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    text            TEXT    NOT NULL,
    char_len        INTEGER NOT NULL,
    word_len        INTEGER NOT NULL,
    tfidf_label     INTEGER NOT NULL,
    tfidf_label_name TEXT   NOT NULL,
    tfidf_score     REAL    NOT NULL,
    hf_label        INTEGER NOT NULL,
    hf_label_name   TEXT    NOT NULL,
    hf_score        REAL    NOT NULL,
    elapsed_ms      REAL,
    source          TEXT    NOT NULL DEFAULT 'single',
    created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history (created_at DESC);
"""


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.getenv("DATABASE_PATH", str(config.DATA_DIR / "history.db")))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------ 写
    def add(
        self,
        *,
        text: str,
        char_len: int,
        word_len: int,
        tfidf_label: int,
        tfidf_label_name: str,
        tfidf_score: float,
        hf_label: int,
        hf_label_name: str,
        hf_score: float,
        elapsed_ms: float | None = None,
        source: str = "single",
    ) -> int:
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO history (text, char_len, word_len,
                    tfidf_label, tfidf_label_name, tfidf_score,
                    hf_label, hf_label_name, hf_score,
                    elapsed_ms, source, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    text, char_len, word_len,
                    tfidf_label, tfidf_label_name, tfidf_score,
                    hf_label, hf_label_name, hf_score,
                    elapsed_ms, source, created_at,
                ),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    # ------------------------------------------------------------------ 读
    def list(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            rows = self._conn.execute(
                "SELECT * FROM history ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return {"total": int(total), "limit": limit, "offset": offset,
                "items": [dict(row) for row in rows]}

    def get(self, record_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM history WHERE id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ 删
    def delete(self, record_id: int) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
            self._conn.commit()
            return cursor.rowcount > 0

    def clear(self) -> int:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM history")
            self._conn.commit()
            return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()


store: HistoryStore | None = None


def init_store() -> HistoryStore:
    global store
    if store is None:
        store = HistoryStore()
    return store


def get_store() -> HistoryStore:
    if store is None:
        return init_store()
    return store
