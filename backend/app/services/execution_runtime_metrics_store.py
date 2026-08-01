from __future__ import annotations

import json
import sqlite3

from contextlib import closing
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

from app.models.execution_runtime_observability import (
    RecoveryRuntimeObservability,
    RuntimeHealthStatus,
)
from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
    canonical_authorization_json,
)


DEFAULT_RUNTIME_METRICS_ID = (
    "recovery-runtime:default"
)


class RuntimeMetricsStoreError(
    RuntimeError
):
    """
    Base class for persistent runtime-metrics failures.
    """


class RuntimeMetricsVersionConflict(
    RuntimeMetricsStoreError
):
    def __init__(
        self,
        *,
        metrics_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.metrics_id = str(
            metrics_id
        ).strip()

        self.expected_version = int(
            expected_version
        )

        self.actual_version = int(
            actual_version
        )

        super().__init__(
            "Runtime metrics version conflict: "
            f"expected={self.expected_version}, "
            f"actual={self.actual_version}"
        )


class ExecutionRuntimeMetricsStore:
    """
    Persistent runtime-observability snapshots.

    The current snapshot is updated atomically using optimistic
    locking. Every successful write also creates an immutable history
    record.

    This store performs database persistence only. It does not start
    the runtime and does not execute managed-device commands.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTHORIZATION_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Runtime metrics database path "
                "must not be empty"
            )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        return connection

    def initialize(
        self,
    ) -> None:
        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_runtime_metrics (
                    metrics_id TEXT PRIMARY KEY,

                    runtime_enabled INTEGER NOT NULL,
                    runtime_running INTEGER NOT NULL,

                    scheduler_enabled INTEGER NOT NULL,
                    scheduler_due INTEGER NOT NULL,

                    health_status TEXT NOT NULL,

                    cycle_count INTEGER NOT NULL,
                    successful_cycle_count INTEGER NOT NULL,
                    failed_cycle_count INTEGER NOT NULL,

                    last_recovered_count INTEGER NOT NULL,
                    last_skipped_count INTEGER NOT NULL,
                    last_failed_count INTEGER NOT NULL,

                    started_at TEXT,
                    stopped_at TEXT,

                    last_cycle_started_at TEXT,
                    last_cycle_completed_at TEXT,

                    last_error TEXT,

                    metadata TEXT NOT NULL,

                    metrics_version INTEGER
                        NOT NULL DEFAULT 1,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_runtime_metrics_history (
                    history_id INTEGER
                        PRIMARY KEY AUTOINCREMENT,

                    metrics_id TEXT NOT NULL,

                    metrics_version INTEGER NOT NULL,

                    recorded_at TEXT NOT NULL,

                    snapshot_payload TEXT NOT NULL,

                    FOREIGN KEY (
                        metrics_id
                    )
                    REFERENCES execution_runtime_metrics (
                        metrics_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_runtime_metrics_history
                ON execution_runtime_metrics_history (
                    metrics_id,
                    recorded_at DESC,
                    history_id DESC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _parse_datetime(
        value: str | None,
    ) -> datetime | None:
        if not value:
            return None

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    @classmethod
    def _metrics_from_row(
        cls,
        row: sqlite3.Row,
    ) -> RecoveryRuntimeObservability:
        return RecoveryRuntimeObservability(
            runtime_enabled=bool(
                row["runtime_enabled"]
            ),
            runtime_running=bool(
                row["runtime_running"]
            ),
            scheduler_enabled=bool(
                row["scheduler_enabled"]
            ),
            scheduler_due=bool(
                row["scheduler_due"]
            ),
            health_status=RuntimeHealthStatus(
                row["health_status"]
            ),
            cycle_count=int(
                row["cycle_count"]
            ),
            successful_cycle_count=int(
                row[
                    "successful_cycle_count"
                ]
            ),
            failed_cycle_count=int(
                row["failed_cycle_count"]
            ),
            last_recovered_count=int(
                row["last_recovered_count"]
            ),
            last_skipped_count=int(
                row["last_skipped_count"]
            ),
            last_failed_count=int(
                row["last_failed_count"]
            ),
            started_at=cls._parse_datetime(
                row["started_at"]
            ),
            stopped_at=cls._parse_datetime(
                row["stopped_at"]
            ),
            last_cycle_started_at=
                cls._parse_datetime(
                    row[
                        "last_cycle_started_at"
                    ]
                ),
            last_cycle_completed_at=
                cls._parse_datetime(
                    row[
                        "last_cycle_completed_at"
                    ]
                ),
            last_error=row["last_error"],
            metadata=json.loads(
                row["metadata"]
            ),
        )

    @staticmethod
    def _snapshot_payload(
        metrics: RecoveryRuntimeObservability,
        *,
        metrics_id: str,
        metrics_version: int,
    ) -> dict[str, Any]:
        return {
            "metrics_id":
                metrics_id,
            "metrics_version":
                int(metrics_version),
            **metrics.to_dict(),
        }

    @classmethod
    def _insert_history(
        cls,
        connection: sqlite3.Connection,
        *,
        metrics: RecoveryRuntimeObservability,
        metrics_id: str,
        metrics_version: int,
        recorded_at: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO
            execution_runtime_metrics_history (
                metrics_id,
                metrics_version,
                recorded_at,
                snapshot_payload
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                metrics_id,
                int(metrics_version),
                recorded_at.isoformat(),
                canonical_authorization_json(
                    cls._snapshot_payload(
                        metrics,
                        metrics_id=metrics_id,
                        metrics_version=
                            metrics_version,
                    )
                ),
            ),
        )

    def save(
        self,
        metrics: RecoveryRuntimeObservability,
        *,
        metrics_id: str = (
            DEFAULT_RUNTIME_METRICS_ID
        ),
        expected_version: int | None = None,
    ) -> tuple[
        RecoveryRuntimeObservability,
        int,
    ]:
        if not isinstance(
            metrics,
            RecoveryRuntimeObservability,
        ):
            raise TypeError(
                "metrics must be a "
                "RecoveryRuntimeObservability"
            )

        normalized_id = str(
            metrics_id
        ).strip()

        if not normalized_id:
            raise ValueError(
                "metrics_id must not be empty"
            )

        if expected_version is not None:
            expected_version = int(
                expected_version
            )

            if expected_version < 1:
                raise ValueError(
                    "expected_version must be "
                    "at least 1"
                )

        now = datetime.now(
            timezone.utc
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            existing = connection.execute(
                """
                SELECT *
                FROM execution_runtime_metrics
                WHERE metrics_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

            if existing is None:
                if expected_version is not None:
                    raise RuntimeMetricsVersionConflict(
                        metrics_id=normalized_id,
                        expected_version=
                            expected_version,
                        actual_version=0,
                    )

                version = 1

                connection.execute(
                    """
                    INSERT INTO
                    execution_runtime_metrics (
                        metrics_id,
                        runtime_enabled,
                        runtime_running,
                        scheduler_enabled,
                        scheduler_due,
                        health_status,
                        cycle_count,
                        successful_cycle_count,
                        failed_cycle_count,
                        last_recovered_count,
                        last_skipped_count,
                        last_failed_count,
                        started_at,
                        stopped_at,
                        last_cycle_started_at,
                        last_cycle_completed_at,
                        last_error,
                        metadata,
                        metrics_version,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        normalized_id,
                        int(
                            metrics.runtime_enabled
                        ),
                        int(
                            metrics.runtime_running
                        ),
                        int(
                            metrics.scheduler_enabled
                        ),
                        int(
                            metrics.scheduler_due
                        ),
                        metrics.health_status.value,
                        metrics.cycle_count,
                        metrics
                        .successful_cycle_count,
                        metrics.failed_cycle_count,
                        metrics
                        .last_recovered_count,
                        metrics
                        .last_skipped_count,
                        metrics
                        .last_failed_count,
                        (
                            metrics.started_at
                            .isoformat()
                            if metrics.started_at
                            else None
                        ),
                        (
                            metrics.stopped_at
                            .isoformat()
                            if metrics.stopped_at
                            else None
                        ),
                        (
                            metrics
                            .last_cycle_started_at
                            .isoformat()
                            if metrics
                            .last_cycle_started_at
                            else None
                        ),
                        (
                            metrics
                            .last_cycle_completed_at
                            .isoformat()
                            if metrics
                            .last_cycle_completed_at
                            else None
                        ),
                        metrics.last_error,
                        canonical_authorization_json(
                            metrics.metadata
                        ),
                        version,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )

            else:
                actual_version = int(
                    existing["metrics_version"]
                )

                if expected_version is None:
                    raise ValueError(
                        "expected_version is required "
                        "when updating runtime metrics"
                    )

                if (
                    actual_version
                    != expected_version
                ):
                    raise RuntimeMetricsVersionConflict(
                        metrics_id=normalized_id,
                        expected_version=
                            expected_version,
                        actual_version=
                            actual_version,
                    )

                version = actual_version + 1

                cursor = connection.execute(
                    """
                    UPDATE execution_runtime_metrics
                    SET
                        runtime_enabled = ?,
                        runtime_running = ?,
                        scheduler_enabled = ?,
                        scheduler_due = ?,
                        health_status = ?,
                        cycle_count = ?,
                        successful_cycle_count = ?,
                        failed_cycle_count = ?,
                        last_recovered_count = ?,
                        last_skipped_count = ?,
                        last_failed_count = ?,
                        started_at = ?,
                        stopped_at = ?,
                        last_cycle_started_at = ?,
                        last_cycle_completed_at = ?,
                        last_error = ?,
                        metadata = ?,
                        metrics_version =
                            metrics_version + 1,
                        updated_at = ?
                    WHERE metrics_id = ?
                      AND metrics_version = ?
                    """,
                    (
                        int(
                            metrics.runtime_enabled
                        ),
                        int(
                            metrics.runtime_running
                        ),
                        int(
                            metrics.scheduler_enabled
                        ),
                        int(
                            metrics.scheduler_due
                        ),
                        metrics.health_status.value,
                        metrics.cycle_count,
                        metrics
                        .successful_cycle_count,
                        metrics.failed_cycle_count,
                        metrics
                        .last_recovered_count,
                        metrics
                        .last_skipped_count,
                        metrics
                        .last_failed_count,
                        (
                            metrics.started_at
                            .isoformat()
                            if metrics.started_at
                            else None
                        ),
                        (
                            metrics.stopped_at
                            .isoformat()
                            if metrics.stopped_at
                            else None
                        ),
                        (
                            metrics
                            .last_cycle_started_at
                            .isoformat()
                            if metrics
                            .last_cycle_started_at
                            else None
                        ),
                        (
                            metrics
                            .last_cycle_completed_at
                            .isoformat()
                            if metrics
                            .last_cycle_completed_at
                            else None
                        ),
                        metrics.last_error,
                        canonical_authorization_json(
                            metrics.metadata
                        ),
                        now.isoformat(),
                        normalized_id,
                        actual_version,
                    ),
                )

                if cursor.rowcount != 1:
                    current = connection.execute(
                        """
                        SELECT metrics_version
                        FROM execution_runtime_metrics
                        WHERE metrics_id = ?
                        """,
                        (
                            normalized_id,
                        ),
                    ).fetchone()

                    raise RuntimeMetricsVersionConflict(
                        metrics_id=normalized_id,
                        expected_version=
                            expected_version,
                        actual_version=(
                            int(
                                current[
                                    "metrics_version"
                                ]
                            )
                            if current
                            else actual_version
                        ),
                    )

            self._insert_history(
                connection,
                metrics=metrics,
                metrics_id=normalized_id,
                metrics_version=version,
                recorded_at=now,
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        loaded = self.get(
            normalized_id
        )

        if loaded is None:
            raise RuntimeError(
                "Saved runtime metrics could "
                "not be loaded"
            )

        return (
            loaded[0],
            loaded[1],
        )

    def get(
        self,
        metrics_id: str = (
            DEFAULT_RUNTIME_METRICS_ID
        ),
    ) -> tuple[
        RecoveryRuntimeObservability,
        int,
    ] | None:
        normalized_id = str(
            metrics_id
        ).strip()

        if not normalized_id:
            raise ValueError(
                "metrics_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM execution_runtime_metrics
                WHERE metrics_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return (
            self._metrics_from_row(
                row
            ),
            int(
                row["metrics_version"]
            ),
        )

    def history(
        self,
        metrics_id: str = (
            DEFAULT_RUNTIME_METRICS_ID
        ),
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        normalized_id = str(
            metrics_id
        ).strip()

        if not normalized_id:
            raise ValueError(
                "metrics_id must not be empty"
            )

        limit = max(
            1,
            min(
                int(limit),
                1000,
            ),
        )

        offset = max(
            0,
            int(offset),
        )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_runtime_metrics_history
                WHERE metrics_id = ?
                ORDER BY recorded_at DESC,
                         history_id DESC
                LIMIT ?
                OFFSET ?
                """,
                (
                    normalized_id,
                    limit,
                    offset,
                ),
            ).fetchall()

        return [
            {
                "history_id":
                    row["history_id"],
                "metrics_id":
                    row["metrics_id"],
                "metrics_version":
                    row["metrics_version"],
                "recorded_at":
                    row["recorded_at"],
                "snapshot":
                    json.loads(
                        row["snapshot_payload"]
                    ),
            }
            for row in rows
        ]
