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

from app.models.execution_recovery_scheduler import (
    DEFAULT_RECOVERY_BATCH_SIZE,
    DEFAULT_RECOVERY_INTERVAL_SECONDS,
    ExecutionRecoveryScheduler,
    RecoverySchedulerRunStatus,
    RecoverySchedulerStatus,
    RecoverySchedulerVersionConflict,
)
from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
    canonical_authorization_json,
)


DEFAULT_RECOVERY_SCHEDULER_ID = (
    "recovery-scheduler:default"
)


class ExecutionRecoverySchedulerStore:
    """
    Persistent recovery scheduler state.

    This store manages scheduler configuration and run state only.
    It does not start background jobs and does not execute commands
    against managed devices.
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
                "Scheduler database path "
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
                execution_recovery_schedulers (
                    scheduler_id TEXT PRIMARY KEY,

                    status TEXT NOT NULL,
                    enabled INTEGER NOT NULL,

                    interval_seconds INTEGER NOT NULL,
                    batch_size INTEGER NOT NULL,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    last_run_started_at TEXT,
                    last_run_completed_at TEXT,
                    next_run_at TEXT,

                    last_run_status TEXT NOT NULL,

                    last_run_recovered INTEGER
                        NOT NULL DEFAULT 0,

                    last_run_skipped INTEGER
                        NOT NULL DEFAULT 0,

                    last_run_failed INTEGER
                        NOT NULL DEFAULT 0,

                    total_runs INTEGER
                        NOT NULL DEFAULT 0,

                    total_recovered INTEGER
                        NOT NULL DEFAULT 0,

                    total_skipped INTEGER
                        NOT NULL DEFAULT 0,

                    total_failed INTEGER
                        NOT NULL DEFAULT 0,

                    scheduler_version INTEGER
                        NOT NULL DEFAULT 1,

                    last_error TEXT,

                    metadata TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_recovery_scheduler_events (
                    event_id INTEGER
                        PRIMARY KEY AUTOINCREMENT,

                    scheduler_id TEXT NOT NULL,

                    event_type TEXT NOT NULL,

                    event_at TEXT NOT NULL,

                    scheduler_version INTEGER
                        NOT NULL,

                    details_payload TEXT NOT NULL,

                    FOREIGN KEY (
                        scheduler_id
                    )
                    REFERENCES
                    execution_recovery_schedulers (
                        scheduler_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_recovery_scheduler_events
                ON execution_recovery_scheduler_events (
                    scheduler_id,
                    event_at ASC,
                    event_id ASC
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
    def _record_from_row(
        cls,
        row: sqlite3.Row,
    ) -> ExecutionRecoveryScheduler:
        return ExecutionRecoveryScheduler(
            scheduler_id=
                row["scheduler_id"],
            status=RecoverySchedulerStatus(
                row["status"]
            ),
            enabled=bool(
                row["enabled"]
            ),
            interval_seconds=int(
                row["interval_seconds"]
            ),
            batch_size=int(
                row["batch_size"]
            ),
            created_at=cls._parse_datetime(
                row["created_at"]
            ),
            updated_at=cls._parse_datetime(
                row["updated_at"]
            ),
            last_run_started_at=
                cls._parse_datetime(
                    row[
                        "last_run_started_at"
                    ]
                ),
            last_run_completed_at=
                cls._parse_datetime(
                    row[
                        "last_run_completed_at"
                    ]
                ),
            next_run_at=cls._parse_datetime(
                row["next_run_at"]
            ),
            last_run_status=
                RecoverySchedulerRunStatus(
                    row["last_run_status"]
                ),
            last_run_recovered=int(
                row["last_run_recovered"]
            ),
            last_run_skipped=int(
                row["last_run_skipped"]
            ),
            last_run_failed=int(
                row["last_run_failed"]
            ),
            total_runs=int(
                row["total_runs"]
            ),
            total_recovered=int(
                row["total_recovered"]
            ),
            total_skipped=int(
                row["total_skipped"]
            ),
            total_failed=int(
                row["total_failed"]
            ),
            scheduler_version=int(
                row["scheduler_version"]
            ),
            last_error=row["last_error"],
            metadata=json.loads(
                row["metadata"]
            ),
        )

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        *,
        scheduler_id: str,
        event_type: str,
        scheduler_version: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO
            execution_recovery_scheduler_events (
                scheduler_id,
                event_type,
                event_at,
                scheduler_version,
                details_payload
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                scheduler_id,
                event_type,
                datetime.now(
                    timezone.utc
                ).isoformat(),
                int(
                    scheduler_version
                ),
                canonical_authorization_json(
                    details or {}
                ),
            ),
        )

    @staticmethod
    def _validate_interval(
        interval_seconds: int,
    ) -> int:
        normalized = int(
            interval_seconds
        )

        if normalized < 5:
            raise ValueError(
                "interval_seconds must be "
                "at least 5"
            )

        if normalized > 86400:
            raise ValueError(
                "interval_seconds must not "
                "exceed 86400"
            )

        return normalized

    @staticmethod
    def _validate_batch_size(
        batch_size: int,
    ) -> int:
        normalized = int(
            batch_size
        )

        if normalized < 1:
            raise ValueError(
                "batch_size must be at least 1"
            )

        if normalized > 1000:
            raise ValueError(
                "batch_size must not exceed 1000"
            )

        return normalized

    def create_default(
        self,
        *,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        interval_seconds: int = (
            DEFAULT_RECOVERY_INTERVAL_SECONDS
        ),
        batch_size: int = (
            DEFAULT_RECOVERY_BATCH_SIZE
        ),
    ) -> ExecutionRecoveryScheduler:
        normalized_id = str(
            scheduler_id
        ).strip()

        if not normalized_id:
            raise ValueError(
                "scheduler_id must not be empty"
            )

        interval_seconds = (
            self._validate_interval(
                interval_seconds
            )
        )

        batch_size = (
            self._validate_batch_size(
                batch_size
            )
        )

        now = datetime.now(
            timezone.utc
        )

        metadata = {
            "scheduler_enabled":
                False,
            "execution_enabled":
                False,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        }

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            existing = connection.execute(
                """
                SELECT *
                FROM execution_recovery_schedulers
                WHERE scheduler_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

            if existing is not None:
                connection.commit()

                return self._record_from_row(
                    existing
                )

            connection.execute(
                """
                INSERT INTO
                execution_recovery_schedulers (
                    scheduler_id,
                    status,
                    enabled,
                    interval_seconds,
                    batch_size,
                    created_at,
                    updated_at,
                    last_run_started_at,
                    last_run_completed_at,
                    next_run_at,
                    last_run_status,
                    last_run_recovered,
                    last_run_skipped,
                    last_run_failed,
                    total_runs,
                    total_recovered,
                    total_skipped,
                    total_failed,
                    scheduler_version,
                    last_error,
                    metadata
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    normalized_id,
                    RecoverySchedulerStatus
                    .DISABLED.value,
                    0,
                    interval_seconds,
                    batch_size,
                    now.isoformat(),
                    now.isoformat(),
                    None,
                    None,
                    None,
                    RecoverySchedulerRunStatus
                    .NEVER_RUN.value,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    1,
                    None,
                    canonical_authorization_json(
                        metadata
                    ),
                ),
            )

            self._event(
                connection,
                scheduler_id=
                    normalized_id,
                event_type="created",
                scheduler_version=1,
                details={
                    "interval_seconds":
                        interval_seconds,
                    "batch_size":
                        batch_size,
                },
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        scheduler = self.get(
            normalized_id
        )

        if scheduler is None:
            raise RuntimeError(
                "Created scheduler could "
                "not be loaded"
            )

        return scheduler

    def get(
        self,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
    ) -> ExecutionRecoveryScheduler | None:
        normalized = str(
            scheduler_id
        ).strip()

        if not normalized:
            raise ValueError(
                "scheduler_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM execution_recovery_schedulers
                WHERE scheduler_id = ?
                """,
                (
                    normalized,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._record_from_row(
            row
        )

    def enable(
        self,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        *,
        expected_version: int,
    ) -> ExecutionRecoveryScheduler:
        return self._set_enabled(
            scheduler_id,
            enabled=True,
            expected_version=
                expected_version,
        )

    def disable(
        self,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        *,
        expected_version: int,
    ) -> ExecutionRecoveryScheduler:
        return self._set_enabled(
            scheduler_id,
            enabled=False,
            expected_version=
                expected_version,
        )

    def _set_enabled(
        self,
        scheduler_id: str,
        *,
        enabled: bool,
        expected_version: int,
    ) -> ExecutionRecoveryScheduler:
        normalized_id = str(
            scheduler_id
        ).strip()

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

            row = connection.execute(
                """
                SELECT *
                FROM execution_recovery_schedulers
                WHERE scheduler_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Recovery scheduler not found"
                )

            actual_version = int(
                row["scheduler_version"]
            )

            if actual_version != expected_version:
                raise RecoverySchedulerVersionConflict(
                    scheduler_id=
                        normalized_id,
                    expected_version=
                        expected_version,
                    actual_version=
                        actual_version,
                )

            if bool(
                row["enabled"]
            ) == bool(enabled):
                raise ValueError(
                    "Recovery scheduler already "
                    + (
                        "enabled"
                        if enabled
                        else "disabled"
                    )
                )

            current_version = (
                actual_version + 1
            )

            status = (
                RecoverySchedulerStatus.IDLE
                if enabled
                else RecoverySchedulerStatus
                .DISABLED
            )

            next_run_at = (
                (
                    now
                    + __import__(
                        "datetime"
                    ).timedelta(
                        seconds=int(
                            row[
                                "interval_seconds"
                            ]
                        )
                    )
                ).isoformat()
                if enabled
                else None
            )

            cursor = connection.execute(
                """
                UPDATE execution_recovery_schedulers
                SET
                    enabled = ?,
                    status = ?,
                    next_run_at = ?,
                    updated_at = ?,
                    scheduler_version =
                        scheduler_version + 1,
                    metadata = ?
                WHERE scheduler_id = ?
                  AND scheduler_version = ?
                """,
                (
                    int(enabled),
                    status.value,
                    next_run_at,
                    now.isoformat(),
                    canonical_authorization_json(
                        {
                            **json.loads(
                                row["metadata"]
                            ),
                            "scheduler_enabled":
                                bool(enabled),
                        }
                    ),
                    normalized_id,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                raise RecoverySchedulerVersionConflict(
                    scheduler_id=
                        normalized_id,
                    expected_version=
                        expected_version,
                    actual_version=
                        actual_version,
                )

            self._event(
                connection,
                scheduler_id=
                    normalized_id,
                event_type=(
                    "enabled"
                    if enabled
                    else "disabled"
                ),
                scheduler_version=
                    current_version,
                details={
                    "previous_version":
                        actual_version,
                    "current_version":
                        current_version,
                },
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        scheduler = self.get(
            normalized_id
        )

        if scheduler is None:
            raise RuntimeError(
                "Updated scheduler could "
                "not be loaded"
            )

        return scheduler

    def update_configuration(
        self,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        *,
        expected_version: int,
        interval_seconds: int | None = None,
        batch_size: int | None = None,
    ) -> ExecutionRecoveryScheduler:
        normalized_id = str(
            scheduler_id
        ).strip()

        expected_version = int(
            expected_version
        )

        if expected_version < 1:
            raise ValueError(
                "expected_version must be "
                "at least 1"
            )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT *
                FROM execution_recovery_schedulers
                WHERE scheduler_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Recovery scheduler not found"
                )

            actual_version = int(
                row["scheduler_version"]
            )

            if actual_version != expected_version:
                raise RecoverySchedulerVersionConflict(
                    scheduler_id=
                        normalized_id,
                    expected_version=
                        expected_version,
                    actual_version=
                        actual_version,
                )

            new_interval = (
                self._validate_interval(
                    interval_seconds
                )
                if interval_seconds is not None
                else int(
                    row["interval_seconds"]
                )
            )

            new_batch = (
                self._validate_batch_size(
                    batch_size
                )
                if batch_size is not None
                else int(
                    row["batch_size"]
                )
            )

            if (
                new_interval
                == int(
                    row["interval_seconds"]
                )
                and new_batch
                == int(
                    row["batch_size"]
                )
            ):
                raise ValueError(
                    "Scheduler configuration "
                    "did not change"
                )

            now = datetime.now(
                timezone.utc
            )

            current_version = (
                actual_version + 1
            )

            cursor = connection.execute(
                """
                UPDATE execution_recovery_schedulers
                SET
                    interval_seconds = ?,
                    batch_size = ?,
                    updated_at = ?,
                    scheduler_version =
                        scheduler_version + 1
                WHERE scheduler_id = ?
                  AND scheduler_version = ?
                """,
                (
                    new_interval,
                    new_batch,
                    now.isoformat(),
                    normalized_id,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                raise RecoverySchedulerVersionConflict(
                    scheduler_id=
                        normalized_id,
                    expected_version=
                        expected_version,
                    actual_version=
                        actual_version,
                )

            self._event(
                connection,
                scheduler_id=
                    normalized_id,
                event_type=
                    "configuration_updated",
                scheduler_version=
                    current_version,
                details={
                    "interval_seconds":
                        new_interval,
                    "batch_size":
                        new_batch,
                    "previous_version":
                        actual_version,
                    "current_version":
                        current_version,
                },
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        scheduler = self.get(
            normalized_id
        )

        if scheduler is None:
            raise RuntimeError(
                "Configured scheduler could "
                "not be loaded"
            )

        return scheduler

    def mark_run_started(
        self,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        *,
        expected_version: int,
    ) -> ExecutionRecoveryScheduler:
        normalized_id = str(
            scheduler_id
        ).strip()

        now = datetime.now(
            timezone.utc
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT *
                FROM execution_recovery_schedulers
                WHERE scheduler_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Recovery scheduler not found"
                )

            actual_version = int(
                row["scheduler_version"]
            )

            if actual_version != int(
                expected_version
            ):
                raise RecoverySchedulerVersionConflict(
                    scheduler_id=
                        normalized_id,
                    expected_version=
                        int(expected_version),
                    actual_version=
                        actual_version,
                )

            if not bool(
                row["enabled"]
            ):
                raise ValueError(
                    "Disabled scheduler cannot run"
                )

            if (
                row["status"]
                == RecoverySchedulerStatus
                .RUNNING.value
            ):
                raise ValueError(
                    "Recovery scheduler is "
                    "already running"
                )

            current_version = (
                actual_version + 1
            )

            connection.execute(
                """
                UPDATE execution_recovery_schedulers
                SET
                    status = ?,
                    last_run_started_at = ?,
                    last_run_completed_at = NULL,
                    last_run_recovered = 0,
                    last_run_skipped = 0,
                    last_run_failed = 0,
                    last_error = NULL,
                    updated_at = ?,
                    scheduler_version =
                        scheduler_version + 1
                WHERE scheduler_id = ?
                  AND scheduler_version = ?
                """,
                (
                    RecoverySchedulerStatus
                    .RUNNING.value,
                    now.isoformat(),
                    now.isoformat(),
                    normalized_id,
                    actual_version,
                ),
            )

            self._event(
                connection,
                scheduler_id=
                    normalized_id,
                event_type="run_started",
                scheduler_version=
                    current_version,
                details={
                    "batch_size":
                        int(
                            row["batch_size"]
                        ),
                },
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        scheduler = self.get(
            normalized_id
        )

        if scheduler is None:
            raise RuntimeError(
                "Running scheduler could "
                "not be loaded"
            )

        return scheduler

    def mark_run_completed(
        self,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        *,
        expected_version: int,
        recovered: int,
        skipped: int,
        failed: int,
    ) -> ExecutionRecoveryScheduler:
        counters = [
            int(recovered),
            int(skipped),
            int(failed),
        ]

        if any(
            counter < 0
            for counter in counters
        ):
            raise ValueError(
                "Run counters must not "
                "be negative"
            )

        normalized_id = str(
            scheduler_id
        ).strip()

        now = datetime.now(
            timezone.utc
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT *
                FROM execution_recovery_schedulers
                WHERE scheduler_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Recovery scheduler not found"
                )

            actual_version = int(
                row["scheduler_version"]
            )

            if actual_version != int(
                expected_version
            ):
                raise RecoverySchedulerVersionConflict(
                    scheduler_id=
                        normalized_id,
                    expected_version=
                        int(expected_version),
                    actual_version=
                        actual_version,
                )

            if (
                row["status"]
                != RecoverySchedulerStatus
                .RUNNING.value
            ):
                raise ValueError(
                    "Only running scheduler "
                    "can complete a run"
                )

            run_status = (
                RecoverySchedulerRunStatus
                .SUCCEEDED
                if int(failed) == 0
                else RecoverySchedulerRunStatus
                .PARTIAL
            )

            current_version = (
                actual_version + 1
            )

            next_run_at = (
                now
                + __import__(
                    "datetime"
                ).timedelta(
                    seconds=int(
                        row["interval_seconds"]
                    )
                )
            )

            connection.execute(
                """
                UPDATE execution_recovery_schedulers
                SET
                    status = ?,
                    last_run_completed_at = ?,
                    next_run_at = ?,
                    last_run_status = ?,
                    last_run_recovered = ?,
                    last_run_skipped = ?,
                    last_run_failed = ?,
                    total_runs = total_runs + 1,
                    total_recovered =
                        total_recovered + ?,
                    total_skipped =
                        total_skipped + ?,
                    total_failed =
                        total_failed + ?,
                    last_error = NULL,
                    updated_at = ?,
                    scheduler_version =
                        scheduler_version + 1
                WHERE scheduler_id = ?
                  AND scheduler_version = ?
                """,
                (
                    RecoverySchedulerStatus
                    .IDLE.value,
                    now.isoformat(),
                    next_run_at.isoformat(),
                    run_status.value,
                    int(recovered),
                    int(skipped),
                    int(failed),
                    int(recovered),
                    int(skipped),
                    int(failed),
                    now.isoformat(),
                    normalized_id,
                    actual_version,
                ),
            )

            self._event(
                connection,
                scheduler_id=
                    normalized_id,
                event_type="run_completed",
                scheduler_version=
                    current_version,
                details={
                    "recovered":
                        int(recovered),
                    "skipped":
                        int(skipped),
                    "failed":
                        int(failed),
                    "run_status":
                        run_status.value,
                },
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        scheduler = self.get(
            normalized_id
        )

        if scheduler is None:
            raise RuntimeError(
                "Completed scheduler could "
                "not be loaded"
            )

        return scheduler

    def mark_run_failed(
        self,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        *,
        expected_version: int,
        error_message: str,
    ) -> ExecutionRecoveryScheduler:
        normalized_error = str(
            error_message
        ).strip()

        if not normalized_error:
            raise ValueError(
                "error_message must not be empty"
            )

        normalized_id = str(
            scheduler_id
        ).strip()

        now = datetime.now(
            timezone.utc
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT *
                FROM execution_recovery_schedulers
                WHERE scheduler_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Recovery scheduler not found"
                )

            actual_version = int(
                row["scheduler_version"]
            )

            if actual_version != int(
                expected_version
            ):
                raise RecoverySchedulerVersionConflict(
                    scheduler_id=
                        normalized_id,
                    expected_version=
                        int(expected_version),
                    actual_version=
                        actual_version,
                )

            if (
                row["status"]
                != RecoverySchedulerStatus
                .RUNNING.value
            ):
                raise ValueError(
                    "Only running scheduler "
                    "can fail a run"
                )

            current_version = (
                actual_version + 1
            )

            connection.execute(
                """
                UPDATE execution_recovery_schedulers
                SET
                    status = ?,
                    last_run_completed_at = ?,
                    last_run_status = ?,
                    last_run_failed = 1,
                    total_runs = total_runs + 1,
                    total_failed = total_failed + 1,
                    last_error = ?,
                    next_run_at = NULL,
                    updated_at = ?,
                    scheduler_version =
                        scheduler_version + 1
                WHERE scheduler_id = ?
                  AND scheduler_version = ?
                """,
                (
                    RecoverySchedulerStatus
                    .FAILED.value,
                    now.isoformat(),
                    RecoverySchedulerRunStatus
                    .FAILED.value,
                    normalized_error,
                    now.isoformat(),
                    normalized_id,
                    actual_version,
                ),
            )

            self._event(
                connection,
                scheduler_id=
                    normalized_id,
                event_type="run_failed",
                scheduler_version=
                    current_version,
                details={
                    "error_message":
                        normalized_error,
                },
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        scheduler = self.get(
            normalized_id
        )

        if scheduler is None:
            raise RuntimeError(
                "Failed scheduler could "
                "not be loaded"
            )

        return scheduler

    def events(
        self,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
    ) -> list[dict[str, Any]]:
        normalized = str(
            scheduler_id
        ).strip()

        if not normalized:
            raise ValueError(
                "scheduler_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM
                execution_recovery_scheduler_events
                WHERE scheduler_id = ?
                ORDER BY event_at ASC,
                         event_id ASC
                """,
                (
                    normalized,
                ),
            ).fetchall()

        return [
            {
                "event_id":
                    row["event_id"],
                "scheduler_id":
                    row["scheduler_id"],
                "event_type":
                    row["event_type"],
                "event_at":
                    row["event_at"],
                "scheduler_version":
                    row["scheduler_version"],
                "details":
                    json.loads(
                        row["details_payload"]
                    ),
            }
            for row in rows
        ]
