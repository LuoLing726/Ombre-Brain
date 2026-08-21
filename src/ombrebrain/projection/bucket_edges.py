"""桶共激活边的独立 SQLite 表定义。"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class BucketEdgeSQLiteStore:
    """只负责创建独立边表；本阶段不采集、不计算也不消费边。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def initialize(self) -> None:
        """幂等创建只含共激活事实字段的 ``bucket_edges`` 表。"""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bucket_edges (
                    source_bucket TEXT NOT NULL,
                    target_bucket TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_activated_at TEXT NOT NULL,
                    activation_count INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    PRIMARY KEY (source_bucket, target_bucket),
                    CHECK (source_bucket <> target_bucket),
                    CHECK (activation_count >= 1)
                ) WITHOUT ROWID
                """
            )
