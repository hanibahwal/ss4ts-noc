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

from app.models.execution_heartbeat import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    ExecutionWorkerHeartbeat,
    WorkerHeartbeatOwnerMismatch,
    WorkerHeartbeatStatus,
    WorkerHeartbeatVersionConflict,
)
from app.models.execution_lease import (
    ExecutionLeaseStatus,
)
from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
    canonical_authorization_json,
)


class ExecutionHeartbeatStore:
    """
    Persistent worker-heartbeat coordination.

    The heartbeat tables share the execution-authorization database
    with execution leases. Registration validates the active lease and
    its owner inside one SQLite transaction.

    This service never executes managed-device commands.
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
                "Heartbeat database path "
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
            lease_table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'execution_leases'
                """
            ).fetchone()

            if lease_table is None:
                raise RuntimeError(
                    "Execution lease database "
                    "must be initialized before "
                    "the heartbeat store"
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_heartbeats (
                    worker_id TEXT PRIMARY KEY,

                    lease_id TEXT NOT NULL UNIQUE,

                    authorization_id TEXT NOT NULL,

                    owner_id TEXT NOT NULL,

                    status TEXT NOT NULL,

                    registered_at TEXT NOT NULL,

                    last_heartbeat_at TEXT NOT NULL,

                    heartbeat_interval_seconds
                        INTEGER NOT NULL,

                    heartbeat_timeout_seconds
                        INTEGER NOT NULL,

                    heartbeat_version INTEGER
                        NOT NULL DEFAULT 1,

                    stopped_at TEXT,

                    metadata TEXT NOT NULL,

                    created_at TEXT NOT NULL,

                    updated_at TEXT NOT NULL,

                    FOREIGN KEY (
                        lease_id
                    )
                    REFERENCES execution_leases (
                        lease_id
                    )
                    ON DELETE CASCADE,

                    FOREIGN KEY (
                        authorization_id
                    )
                    REFERENCES execution_authorizations (
                        authorization_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_heartbeats_lease
                ON execution_heartbeats (
                    lease_id
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_heartbeats_auth
                ON execution_heartbeats (
                    authorization_id,
                    status
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_heartbeats_status
                ON execution_heartbeats (
                    status,
                    last_heartbeat_at
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_heartbeat_events (
                    event_id INTEGER
                        PRIMARY KEY AUTOINCREMENT,

                    worker_id TEXT NOT NULL,

                    lease_id TEXT NOT NULL,

                    authorization_id TEXT NOT NULL,

                    event_type TEXT NOT NULL,

                    event_at TEXT NOT NULL,

                    heartbeat_version INTEGER NOT NULL,

                    details_payload TEXT NOT NULL,

                    FOREIGN KEY (
                        worker_id
                    )
                    REFERENCES execution_heartbeats (
                        worker_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_heartbeat_events
                ON execution_heartbeat_events (
                    worker_id,
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
    ) -> ExecutionWorkerHeartbeat:
        return ExecutionWorkerHeartbeat(
            worker_id=row["worker_id"],
            lease_id=row["lease_id"],
            authorization_id=
                row["authorization_id"],
            owner_id=row["owner_id"],
            status=WorkerHeartbeatStatus(
                row["status"]
            ),
            registered_at=cls._parse_datetime(
                row["registered_at"]
            ),
            last_heartbeat_at=
                cls._parse_datetime(
                    row[
                        "last_heartbeat_at"
                    ]
                ),
            heartbeat_interval_seconds=int(
                row[
                    "heartbeat_interval_seconds"
                ]
            ),
            heartbeat_timeout_seconds=int(
                row[
                    "heartbeat_timeout_seconds"
                ]
            ),
            heartbeat_version=int(
                row["heartbeat_version"]
            ),
            stopped_at=cls._parse_datetime(
                row["stopped_at"]
            ),
            metadata=json.loads(
                row["metadata"]
            ),
        )

    @staticmethod
    def _validate_timing(
        *,
        heartbeat_interval_seconds: int,
        heartbeat_timeout_seconds: int,
    ) -> tuple[int, int]:
        interval = int(
            heartbeat_interval_seconds
        )

        timeout = int(
            heartbeat_timeout_seconds
        )

        if interval < 1:
            raise ValueError(
                "heartbeat_interval_seconds "
                "must be at least 1"
            )

        if interval > 3600:
            raise ValueError(
                "heartbeat_interval_seconds "
                "must not exceed 3600"
            )

        if timeout < 2:
            raise ValueError(
                "heartbeat_timeout_seconds "
                "must be at least 2"
            )

        if timeout > 7200:
            raise ValueError(
                "heartbeat_timeout_seconds "
                "must not exceed 7200"
            )

        if timeout <= interval:
            raise ValueError(
                "heartbeat_timeout_seconds must "
                "be greater than "
                "heartbeat_interval_seconds"
            )

        return interval, timeout

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        *,
        worker_id: str,
        lease_id: str,
        authorization_id: str,
        event_type: str,
        heartbeat_version: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO
            execution_heartbeat_events (
                worker_id,
                lease_id,
                authorization_id,
                event_type,
                event_at,
                heartbeat_version,
                details_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                worker_id,
                lease_id,
                authorization_id,
                event_type,
                datetime.now(
                    timezone.utc
                ).isoformat(),
                int(
                    heartbeat_version
                ),
                canonical_authorization_json(
                    details or {}
                ),
            ),
        )

    def register_worker(
        self,
        *,
        worker_id: str,
        lease_id: str,
        heartbeat_interval_seconds: int = (
            DEFAULT_HEARTBEAT_INTERVAL_SECONDS
        ),
        heartbeat_timeout_seconds: int = (
            DEFAULT_HEARTBEAT_TIMEOUT_SECONDS
        ),
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionWorkerHeartbeat:
        normalized_worker_id = str(
            worker_id
        ).strip()

        normalized_lease_id = str(
            lease_id
        ).strip()

        if not normalized_worker_id:
            raise ValueError(
                "worker_id must not be empty"
            )

        if not normalized_lease_id:
            raise ValueError(
                "lease_id must not be empty"
            )

        interval, timeout = (
            self._validate_timing(
                heartbeat_interval_seconds=
                    heartbeat_interval_seconds,
                heartbeat_timeout_seconds=
                    heartbeat_timeout_seconds,
            )
        )

        now = datetime.now(
            timezone.utc
        )

        heartbeat_metadata = {
            "execution_enabled":
                False,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
            **dict(metadata or {}),
        }

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            lease_row = connection.execute(
                """
                SELECT *
                FROM execution_leases
                WHERE lease_id = ?
                """,
                (
                    normalized_lease_id,
                ),
            ).fetchone()

            if lease_row is None:
                raise KeyError(
                    "Execution lease not found"
                )

            lease_expires_at = (
                self._parse_datetime(
                    lease_row["expires_at"]
                )
            )

            if (
                lease_row["status"]
                != ExecutionLeaseStatus
                .ACTIVE.value
                or lease_expires_at is None
                or lease_expires_at <= now
            ):
                raise ValueError(
                    "Execution lease is not active"
                )

            lease_owner_id = str(
                lease_row["owner_id"]
            ).strip()

            if (
                normalized_worker_id
                != lease_owner_id
            ):
                raise WorkerHeartbeatOwnerMismatch(
                    worker_id=
                        normalized_worker_id,
                    lease_owner_id=
                        lease_owner_id,
                )

            existing_worker = (
                connection.execute(
                    """
                    SELECT worker_id
                    FROM execution_heartbeats
                    WHERE worker_id = ?
                    """,
                    (
                        normalized_worker_id,
                    ),
                ).fetchone()
            )

            if existing_worker is not None:
                raise ValueError(
                    "Worker heartbeat is "
                    "already registered"
                )

            existing_lease = (
                connection.execute(
                    """
                    SELECT worker_id
                    FROM execution_heartbeats
                    WHERE lease_id = ?
                    """,
                    (
                        normalized_lease_id,
                    ),
                ).fetchone()
            )

            if existing_lease is not None:
                raise ValueError(
                    "Execution lease already has "
                    "a registered heartbeat"
                )

            connection.execute(
                """
                INSERT INTO execution_heartbeats (
                    worker_id,
                    lease_id,
                    authorization_id,
                    owner_id,
                    status,
                    registered_at,
                    last_heartbeat_at,
                    heartbeat_interval_seconds,
                    heartbeat_timeout_seconds,
                    heartbeat_version,
                    stopped_at,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    normalized_worker_id,
                    normalized_lease_id,
                    lease_row[
                        "authorization_id"
                    ],
                    lease_owner_id,
                    WorkerHeartbeatStatus
                    .HEALTHY.value,
                    now.isoformat(),
                    now.isoformat(),
                    interval,
                    timeout,
                    1,
                    None,
                    canonical_authorization_json(
                        heartbeat_metadata
                    ),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

            self._event(
                connection,
                worker_id=
                    normalized_worker_id,
                lease_id=
                    normalized_lease_id,
                authorization_id=
                    lease_row[
                        "authorization_id"
                    ],
                event_type="registered",
                heartbeat_version=1,
                details={
                    "heartbeat_interval_seconds":
                        interval,
                    "heartbeat_timeout_seconds":
                        timeout,
                },
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise ValueError(
                "Worker or lease heartbeat "
                "already registered"
            ) from exc

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        heartbeat = self.get(
            normalized_worker_id
        )

        if heartbeat is None:
            raise RuntimeError(
                "Registered heartbeat "
                "could not be loaded"
            )

        return heartbeat

    def get(
        self,
        worker_id: str,
    ) -> ExecutionWorkerHeartbeat | None:
        normalized = str(
            worker_id
        ).strip()

        if not normalized:
            raise ValueError(
                "worker_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM execution_heartbeats
                WHERE worker_id = ?
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

    def get_by_lease(
        self,
        lease_id: str,
    ) -> ExecutionWorkerHeartbeat | None:
        normalized = str(
            lease_id
        ).strip()

        if not normalized:
            raise ValueError(
                "lease_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM execution_heartbeats
                WHERE lease_id = ?
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

    def record_heartbeat(
        self,
        worker_id: str,
        *,
        expected_version: int,
    ) -> ExecutionWorkerHeartbeat:
        normalized_worker_id = str(
            worker_id
        ).strip()

        expected_version = int(
            expected_version
        )

        if not normalized_worker_id:
            raise ValueError(
                "worker_id must not be empty"
            )

        if expected_version < 1:
            raise ValueError(
                "expected_version must "
                "be at least 1"
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
                SELECT
                    heartbeat.*,
                    lease.status
                        AS lease_status,
                    lease.owner_id
                        AS lease_owner_id,
                    lease.expires_at
                        AS lease_expires_at
                FROM execution_heartbeats
                    AS heartbeat
                JOIN execution_leases
                    AS lease
                  ON lease.lease_id
                   = heartbeat.lease_id
                WHERE heartbeat.worker_id = ?
                """,
                (
                    normalized_worker_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Worker heartbeat not found"
                )

            actual_version = int(
                row["heartbeat_version"]
            )

            if (
                actual_version
                != expected_version
            ):
                raise WorkerHeartbeatVersionConflict(
                    worker_id=
                        normalized_worker_id,
                    expected_version=
                        expected_version,
                    actual_version=
                        actual_version,
                )

            if (
                row["status"]
                == WorkerHeartbeatStatus
                .STOPPED.value
            ):
                raise ValueError(
                    "Stopped worker cannot "
                    "record heartbeat"
                )

            if (
                row["owner_id"]
                != row["lease_owner_id"]
            ):
                raise WorkerHeartbeatOwnerMismatch(
                    worker_id=
                        normalized_worker_id,
                    lease_owner_id=
                        row["lease_owner_id"],
                )

            lease_expires_at = (
                self._parse_datetime(
                    row["lease_expires_at"]
                )
            )

            if (
                row["lease_status"]
                != ExecutionLeaseStatus
                .ACTIVE.value
                or lease_expires_at is None
                or lease_expires_at <= now
            ):
                raise ValueError(
                    "Execution lease is not active"
                )

            cursor = connection.execute(
                """
                UPDATE execution_heartbeats
                SET
                    status = ?,
                    last_heartbeat_at = ?,
                    heartbeat_version =
                        heartbeat_version + 1,
                    updated_at = ?
                WHERE worker_id = ?
                  AND status != ?
                  AND heartbeat_version = ?
                """,
                (
                    WorkerHeartbeatStatus
                    .HEALTHY.value,
                    now.isoformat(),
                    now.isoformat(),
                    normalized_worker_id,
                    WorkerHeartbeatStatus
                    .STOPPED.value,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                current = connection.execute(
                    """
                    SELECT heartbeat_version
                    FROM execution_heartbeats
                    WHERE worker_id = ?
                    """,
                    (
                        normalized_worker_id,
                    ),
                ).fetchone()

                raise WorkerHeartbeatVersionConflict(
                    worker_id=
                        normalized_worker_id,
                    expected_version=
                        expected_version,
                    actual_version=(
                        int(
                            current[
                                "heartbeat_version"
                            ]
                        )
                        if current
                        else actual_version
                    ),
                )

            current_version = (
                actual_version + 1
            )

            self._event(
                connection,
                worker_id=
                    normalized_worker_id,
                lease_id=row["lease_id"],
                authorization_id=
                    row["authorization_id"],
                event_type="heartbeat",
                heartbeat_version=
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

        heartbeat = self.get(
            normalized_worker_id
        )

        if heartbeat is None:
            raise RuntimeError(
                "Updated heartbeat "
                "could not be loaded"
            )

        return heartbeat

    def stop_worker(
        self,
        worker_id: str,
        *,
        expected_version: int,
        reason: str | None = None,
    ) -> ExecutionWorkerHeartbeat:
        normalized_worker_id = str(
            worker_id
        ).strip()

        normalized_reason = (
            str(reason).strip()
            if reason is not None
            else ""
        )

        expected_version = int(
            expected_version
        )

        if expected_version < 1:
            raise ValueError(
                "expected_version must "
                "be at least 1"
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
                FROM execution_heartbeats
                WHERE worker_id = ?
                """,
                (
                    normalized_worker_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Worker heartbeat not found"
                )

            actual_version = int(
                row["heartbeat_version"]
            )

            if (
                actual_version
                != expected_version
            ):
                raise WorkerHeartbeatVersionConflict(
                    worker_id=
                        normalized_worker_id,
                    expected_version=
                        expected_version,
                    actual_version=
                        actual_version,
                )

            if (
                row["status"]
                == WorkerHeartbeatStatus
                .STOPPED.value
            ):
                raise ValueError(
                    "Worker heartbeat is "
                    "already stopped"
                )

            cursor = connection.execute(
                """
                UPDATE execution_heartbeats
                SET
                    status = ?,
                    stopped_at = ?,
                    heartbeat_version =
                        heartbeat_version + 1,
                    updated_at = ?
                WHERE worker_id = ?
                  AND status != ?
                  AND heartbeat_version = ?
                """,
                (
                    WorkerHeartbeatStatus
                    .STOPPED.value,
                    now.isoformat(),
                    now.isoformat(),
                    normalized_worker_id,
                    WorkerHeartbeatStatus
                    .STOPPED.value,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                current = connection.execute(
                    """
                    SELECT heartbeat_version
                    FROM execution_heartbeats
                    WHERE worker_id = ?
                    """,
                    (
                        normalized_worker_id,
                    ),
                ).fetchone()

                raise WorkerHeartbeatVersionConflict(
                    worker_id=
                        normalized_worker_id,
                    expected_version=
                        expected_version,
                    actual_version=(
                        int(
                            current[
                                "heartbeat_version"
                            ]
                        )
                        if current
                        else actual_version
                    ),
                )

            current_version = (
                actual_version + 1
            )

            self._event(
                connection,
                worker_id=
                    normalized_worker_id,
                lease_id=row["lease_id"],
                authorization_id=
                    row["authorization_id"],
                event_type="stopped",
                heartbeat_version=
                    current_version,
                details={
                    "reason":
                        normalized_reason
                        or None,
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

        heartbeat = self.get(
            normalized_worker_id
        )

        if heartbeat is None:
            raise RuntimeError(
                "Stopped heartbeat "
                "could not be loaded"
            )

        return heartbeat

    def list_workers(
        self,
        *,
        authorization_id: str | None = None,
        lease_id: str | None = None,
        status: WorkerHeartbeatStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExecutionWorkerHeartbeat]:
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

        clauses: list[str] = []
        parameters: list[Any] = []

        if authorization_id:
            clauses.append(
                "authorization_id = ?"
            )

            parameters.append(
                str(
                    authorization_id
                ).strip()
            )

        if lease_id:
            clauses.append(
                "lease_id = ?"
            )

            parameters.append(
                str(lease_id).strip()
            )

        if status is not None:
            clauses.append(
                "status = ?"
            )

            parameters.append(
                status.value
            )

        where = (
            " WHERE "
            + " AND ".join(clauses)
            if clauses
            else ""
        )

        parameters.extend([
            limit,
            offset,
        ])

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM execution_heartbeats
                {where}
                ORDER BY registered_at DESC
                LIMIT ?
                OFFSET ?
                """,
                parameters,
            ).fetchall()

        return [
            self._record_from_row(
                row
            )
            for row in rows
        ]

    def stale_workers(
        self,
        *,
        now: datetime | None = None,
    ) -> list[ExecutionWorkerHeartbeat]:
        current = (
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )

        if current.tzinfo is None:
            current = current.replace(
                tzinfo=timezone.utc
            )

        current = current.astimezone(
            timezone.utc
        )

        workers = self.list_workers(
            limit=1000,
        )

        return [
            worker
            for worker in workers
            if worker.is_stale_at(
                now=current
            )
        ]

    def events(
        self,
        worker_id: str,
    ) -> list[dict[str, Any]]:
        normalized = str(
            worker_id
        ).strip()

        if not normalized:
            raise ValueError(
                "worker_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_heartbeat_events
                WHERE worker_id = ?
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
                "worker_id":
                    row["worker_id"],
                "lease_id":
                    row["lease_id"],
                "authorization_id":
                    row["authorization_id"],
                "event_type":
                    row["event_type"],
                "event_at":
                    row["event_at"],
                "heartbeat_version":
                    row[
                        "heartbeat_version"
                    ],
                "details":
                    json.loads(
                        row["details_payload"]
                    ),
            }
            for row in rows
        ]
