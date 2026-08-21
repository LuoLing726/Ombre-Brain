"""独立桶共激活边表的字段与生命周期边界。"""

import sqlite3

from ombrebrain.projection.bucket_edges import BucketEdgeSQLiteStore


def test_bucket_edge_table_has_only_the_six_coactivation_fields(tmp_path):
    database = tmp_path / "bucket_edges.sqlite3"

    BucketEdgeSQLiteStore(database).initialize()

    with sqlite3.connect(database) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(bucket_edges)")
        ]

    assert tables == {"bucket_edges"}
    assert columns == [
        "source_bucket",
        "target_bucket",
        "created_at",
        "last_activated_at",
        "activation_count",
        "weight",
    ]


def test_bucket_edge_table_initialization_is_idempotent_and_non_destructive(tmp_path):
    database = tmp_path / "bucket_edges.sqlite3"
    store = BucketEdgeSQLiteStore(database)
    store.initialize()

    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            INSERT INTO bucket_edges (
                source_bucket,
                target_bucket,
                created_at,
                last_activated_at,
                activation_count,
                weight
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("bucket-a", "bucket-b", "2026-07-30T00:00:00Z", "2026-07-30T00:00:00Z", 1, 1.0),
        )

    store.initialize()

    with sqlite3.connect(database) as conn:
        row = conn.execute(
            "SELECT source_bucket, target_bucket, activation_count, weight "
            "FROM bucket_edges"
        ).fetchone()

    assert row == ("bucket-a", "bucket-b", 1, 1.0)


def test_bucket_edge_table_rejects_self_edges_and_non_positive_counts(tmp_path):
    database = tmp_path / "bucket_edges.sqlite3"
    BucketEdgeSQLiteStore(database).initialize()

    with sqlite3.connect(database) as conn:
        for source, target, count in (
            ("same", "same", 1),
            ("bucket-a", "bucket-b", 0),
        ):
            try:
                conn.execute(
                    """
                    INSERT INTO bucket_edges (
                        source_bucket,
                        target_bucket,
                        created_at,
                        last_activated_at,
                        activation_count,
                        weight
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (source, target, "2026-07-30T00:00:00Z", "2026-07-30T00:00:00Z", count, 0.0),
                )
            except sqlite3.IntegrityError:
                continue
            raise AssertionError("非法边记录未被表约束拒绝")
