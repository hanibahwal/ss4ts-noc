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
from uuid import uuid4

from app.models.execution_heartbeat import (
    ExecutionWorkerHeartbeat,
    WorkerHeartbeatStatus,
)
from app.models.execution_lease import (
    ExecutionLeaseStatus,
)
from app.models.execution_recovery import (
    ExecutionRecovery,
    RecoveryDecision,
    RecoveryReason,
    RecoveryStatus,
)
from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
    canonical_authorization_json,
)


class ExecutionRecoveryService:
    """
    Atomic stale-worker lease recovery.

    Heartbeat, lease, recovery record, and recovery events are updated
    inside one SQLite transaction.

    This service performs coordination only. It never executes managed
    device commands or performs network I/O.
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
                "Recovery database path "
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
            required_tables = {
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

            required = {
                "execution_leases",
                "execution_heartbeats",
            }

            missing = (
                required
                - required_tables
            )

            if missing:
                raise RuntimeError(
                    "Recovery dependencies "
                    "are not initialized: "
                    + ", ".join(
                        sorted(missing)
                    )
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_recoveries (
                    recovery_id TEXT PRIMARY KEY,

                    worker_id TEXT NOT NULL,
                    lease_id TEXT NOT NULL,
                    authorization_id TEXT NOT NULL,

                    status TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,

                    detected_at TEXT NOT NULL,
                    completed_at TEXT,

                    previous_lease_version INTEGER,
                    current_lease_version INTEGER,

                    previous_heartbeat_version INTEGER,
                    current_heartbeat_version INTEGER,

                    recovery_version INTEGER
                        NOT NULL DEFAULT 1,

                    error_message TEXT,

                    metadata TEXT NOT NULL,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    FOREIGN KEY (
                        lease_id
                    )
                    REFERENCES execution_leases (
                        lease_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_execution_recovery_worker_lease
                ON execution_recoveries (
                    worker_id,
                    lease_id
                )
                WHERE status = 'recovered'
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_recovery_status
                ON execution_recoveries (
                    status,
                    detected_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_recovery_events (
                    event_id INTEGER
                        PRIMARY KEY AUTOINCREMENT,

                    recovery_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    lease_id TEXT NOT NULL,
                    authorization_id TEXT NOT NULL,

                    event_type TEXT NOT NULL,
                    event_at TEXT NOT NULL,

                    details_payload TEXT NOT NULL,

                    FOREIGN KEY (
                        recovery_id
                    )
                    REFERENCES execution_recoveries (
                        recovery_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_recovery_events
                ON execution_recovery_events (
                    recovery_id,
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
    ) -> ExecutionRecovery:
        return ExecutionRecovery(
            recovery_id=
                row["recovery_id"],
            worker_id=
                row["worker_id"],
            lease_id=
                row["lease_id"],
            authorization_id=
                row["authorization_id"],
            status=RecoveryStatus(
                row["status"]
            ),
            decision=RecoveryDecision(
                row["decision"]
            ),
            reason=RecoveryReason(
                row["reason"]
            ),
            detected_at=
                cls._parse_datetime(
                    row["detected_at"]
                ),
            completed_at=
                cls._parse_datetime(
                    row["completed_at"]
                ),
            previous_lease_version=
                row[
                    "previous_lease_version"
                ],
            current_lease_version=
                row[
                    "current_lease_version"
                ],
            previous_heartbeat_version=
                row[
                    "previous_heartbeat_version"
                ],
            current_heartbeat_version=
                row[
                    "current_heartbeat_version"
                ],
            recovery_version=int(
                row["recovery_version"]
            ),
            error_message=
                row["error_message"],
            metadata=json.loads(
                row["metadata"]
            ),
        )

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        *,
        recovery_id: str,
        worker_id: str,
        lease_id: str,
        authorization_id: str,
        event_type: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO
            execution_recovery_events (
                recovery_id,
                worker_id,
                lease_id,
                authorization_id,
                event_type,
                event_at,
                details_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                recovery_id,
                worker_id,
                lease_id,
                authorization_id,
                event_type,
                datetime.now(
                    timezone.utc
                ).isoformat(),
                canonical_authorization_json(
                    details or {}
                ),
            ),
        )

    @classmethod
    def _heartbeat_is_stale(
        cls,
        row: sqlite3.Row,
        *,
        now: datetime,
    ) -> bool:
        if (
            row["heartbeat_status"]
            == WorkerHeartbeatStatus
            .STOPPED.value
        ):
            return False

        last_heartbeat_at = (
            cls._parse_datetime(
                row["last_heartbeat_at"]
            )
        )

        if last_heartbeat_at is None:
            return True

        timeout_seconds = int(
            row[
                "heartbeat_timeout_seconds"
            ]
        )

        age_seconds = (
            now
            - last_heartbeat_at
        ).total_seconds()

        return (
            age_seconds
            >= timeout_seconds
        )

    def _recover_worker_atomic(
        self,
        worker_id: str,
    ) -> ExecutionRecovery:
        normalized_worker_id = str(
            worker_id
        ).strip()

        if not normalized_worker_id:
            raise ValueError(
                "worker_id must not be empty"
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
                    heartbeat.worker_id,
                    heartbeat.lease_id,
                    heartbeat.authorization_id,
                    heartbeat.owner_id,
                    heartbeat.status
                        AS heartbeat_status,
                    heartbeat.last_heartbeat_at,
                    heartbeat
                        .heartbeat_timeout_seconds,
                    heartbeat.heartbeat_version,

                    lease.owner_id
                        AS lease_owner_id,
                    lease.status
                        AS lease_status,
                    lease.expires_at
                        AS lease_expires_at,
                    lease.lease_version
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

            existing = connection.execute(
                """
                SELECT *
                FROM execution_recoveries
                WHERE worker_id = ?
                  AND lease_id = ?
                  AND status = ?
                LIMIT 1
                """,
                (
                    row["worker_id"],
                    row["lease_id"],
                    RecoveryStatus
                    .RECOVERED.value,
                ),
            ).fetchone()

            if existing is not None:
                connection.commit()

                return self._record_from_row(
                    existing
                )

            recovery_id = (
                f"recovery:"
                f"{now.strftime('%Y%m%dT%H%M%S%fZ')}:"
                f"{uuid4().hex[:12]}"
            )

            previous_lease_version = int(
                row["lease_version"]
            )

            previous_heartbeat_version = int(
                row["heartbeat_version"]
            )

            lease_expires_at = (
                self._parse_datetime(
                    row["lease_expires_at"]
                )
            )

            metadata = {
                "execution_enabled":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
                "atomic_transaction":
                    True,
            }

            if (
                row["heartbeat_status"]
                == WorkerHeartbeatStatus
                .STOPPED.value
            ):
                recovery = self._insert_completed(
                    connection,
                    recovery_id=recovery_id,
                    row=row,
                    now=now,
                    status=(
                        RecoveryStatus.SKIPPED
                    ),
                    decision=(
                        RecoveryDecision.NO_ACTION
                    ),
                    reason=(
                        RecoveryReason
                        .HEARTBEAT_STOPPED
                    ),
                    previous_lease_version=
                        previous_lease_version,
                    current_lease_version=
                        previous_lease_version,
                    previous_heartbeat_version=
                        previous_heartbeat_version,
                    current_heartbeat_version=
                        previous_heartbeat_version,
                    metadata=metadata,
                )

                connection.commit()
                return recovery

            if (
                row["owner_id"]
                != row["lease_owner_id"]
            ):
                recovery = self._insert_completed(
                    connection,
                    recovery_id=recovery_id,
                    row=row,
                    now=now,
                    status=(
                        RecoveryStatus.SKIPPED
                    ),
                    decision=(
                        RecoveryDecision.NO_ACTION
                    ),
                    reason=(
                        RecoveryReason
                        .OWNER_MISMATCH
                    ),
                    previous_lease_version=
                        previous_lease_version,
                    current_lease_version=
                        previous_lease_version,
                    previous_heartbeat_version=
                        previous_heartbeat_version,
                    current_heartbeat_version=
                        previous_heartbeat_version,
                    metadata=metadata,
                )

                connection.commit()
                return recovery

            if not self._heartbeat_is_stale(
                row,
                now=now,
            ):
                recovery = self._insert_completed(
                    connection,
                    recovery_id=recovery_id,
                    row=row,
                    now=now,
                    status=(
                        RecoveryStatus.SKIPPED
                    ),
                    decision=(
                        RecoveryDecision.NO_ACTION
                    ),
                    reason=(
                        RecoveryReason
                        .LEASE_NOT_ACTIVE
                    ),
                    previous_lease_version=
                        previous_lease_version,
                    current_lease_version=
                        previous_lease_version,
                    previous_heartbeat_version=
                        previous_heartbeat_version,
                    current_heartbeat_version=
                        previous_heartbeat_version,
                    metadata={
                        **metadata,
                        "skip_detail":
                            "worker_not_stale",
                    },
                )

                connection.commit()
                return recovery

            if (
                row["lease_status"]
                != ExecutionLeaseStatus
                .ACTIVE.value
            ):
                recovery = self._insert_completed(
                    connection,
                    recovery_id=recovery_id,
                    row=row,
                    now=now,
                    status=(
                        RecoveryStatus.SKIPPED
                    ),
                    decision=(
                        RecoveryDecision.NO_ACTION
                    ),
                    reason=(
                        RecoveryReason
                        .LEASE_NOT_ACTIVE
                    ),
                    previous_lease_version=
                        previous_lease_version,
                    current_lease_version=
                        previous_lease_version,
                    previous_heartbeat_version=
                        previous_heartbeat_version,
                    current_heartbeat_version=
                        previous_heartbeat_version,
                    metadata=metadata,
                )

                connection.commit()
                return recovery

            if (
                lease_expires_at is None
                or lease_expires_at <= now
            ):
                heartbeat_cursor = connection.execute(
                    """
                    UPDATE execution_heartbeats
                    SET
                        status = ?,
                        heartbeat_version =
                            heartbeat_version + 1,
                        updated_at = ?
                    WHERE worker_id = ?
                      AND heartbeat_version = ?
                    """,
                    (
                        WorkerHeartbeatStatus
                        .STALE.value,
                        now.isoformat(),
                        normalized_worker_id,
                        previous_heartbeat_version,
                    ),
                )

                lease_cursor = connection.execute(
                    """
                    UPDATE execution_leases
                    SET
                        status = ?,
                        lease_version =
                            lease_version + 1,
                        updated_at = ?
                    WHERE lease_id = ?
                      AND status = ?
                      AND lease_version = ?
                    """,
                    (
                        ExecutionLeaseStatus
                        .EXPIRED.value,
                        now.isoformat(),
                        row["lease_id"],
                        ExecutionLeaseStatus
                        .ACTIVE.value,
                        previous_lease_version,
                    ),
                )

                decision = (
                    RecoveryDecision.EXPIRE_LEASE
                )

                reason = (
                    RecoveryReason.LEASE_EXPIRED
                )
            else:
                heartbeat_cursor = connection.execute(
                    """
                    UPDATE execution_heartbeats
                    SET
                        status = ?,
                        heartbeat_version =
                            heartbeat_version + 1,
                        updated_at = ?
                    WHERE worker_id = ?
                      AND heartbeat_version = ?
                    """,
                    (
                        WorkerHeartbeatStatus
                        .STALE.value,
                        now.isoformat(),
                        normalized_worker_id,
                        previous_heartbeat_version,
                    ),
                )

                lease_cursor = connection.execute(
                    """
                    UPDATE execution_leases
                    SET
                        status = ?,
                        lease_version =
                            lease_version + 1,
                        updated_at = ?
                    WHERE lease_id = ?
                      AND status = ?
                      AND lease_version = ?
                    """,
                    (
                        ExecutionLeaseStatus
                        .REVOKED.value,
                        now.isoformat(),
                        row["lease_id"],
                        ExecutionLeaseStatus
                        .ACTIVE.value,
                        previous_lease_version,
                    ),
                )

                decision = (
                    RecoveryDecision.REVOKE_LEASE
                )

                reason = (
                    RecoveryReason.WORKER_STALE
                )

            if (
                heartbeat_cursor.rowcount != 1
                or lease_cursor.rowcount != 1
            ):
                raise RuntimeError(
                    "Atomic stale lease recovery "
                    "lost optimistic update"
                )

            current_heartbeat_version = (
                previous_heartbeat_version + 1
            )

            current_lease_version = (
                previous_lease_version + 1
            )

            recovery = self._insert_completed(
                connection,
                recovery_id=recovery_id,
                row=row,
                now=now,
                status=(
                    RecoveryStatus.RECOVERED
                ),
                decision=decision,
                reason=reason,
                previous_lease_version=
                    previous_lease_version,
                current_lease_version=
                    current_lease_version,
                previous_heartbeat_version=
                    previous_heartbeat_version,
                current_heartbeat_version=
                    current_heartbeat_version,
                metadata=metadata,
            )

            self._event(
                connection,
                recovery_id=recovery_id,
                worker_id=row["worker_id"],
                lease_id=row["lease_id"],
                authorization_id=
                    row["authorization_id"],
                event_type="heartbeat_stale",
                details={
                    "previous_version":
                        previous_heartbeat_version,
                    "current_version":
                        current_heartbeat_version,
                },
            )

            self._event(
                connection,
                recovery_id=recovery_id,
                worker_id=row["worker_id"],
                lease_id=row["lease_id"],
                authorization_id=
                    row["authorization_id"],
                event_type=(
                    "lease_expired"
                    if decision
                    == RecoveryDecision
                    .EXPIRE_LEASE
                    else "lease_revoked"
                ),
                details={
                    "previous_version":
                        previous_lease_version,
                    "current_version":
                        current_lease_version,
                },
            )

            connection.commit()

            return recovery

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

    def _insert_completed(
        self,
        connection: sqlite3.Connection,
        *,
        recovery_id: str,
        row: sqlite3.Row,
        now: datetime,
        status: RecoveryStatus,
        decision: RecoveryDecision,
        reason: RecoveryReason,
        previous_lease_version: int,
        current_lease_version: int,
        previous_heartbeat_version: int,
        current_heartbeat_version: int,
        metadata: dict[str, Any],
    ) -> ExecutionRecovery:
        connection.execute(
            """
            INSERT INTO execution_recoveries (
                recovery_id,
                worker_id,
                lease_id,
                authorization_id,
                status,
                decision,
                reason,
                detected_at,
                completed_at,
                previous_lease_version,
                current_lease_version,
                previous_heartbeat_version,
                current_heartbeat_version,
                recovery_version,
                error_message,
                metadata,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                recovery_id,
                row["worker_id"],
                row["lease_id"],
                row["authorization_id"],
                status.value,
                decision.value,
                reason.value,
                now.isoformat(),
                now.isoformat(),
                previous_lease_version,
                current_lease_version,
                previous_heartbeat_version,
                current_heartbeat_version,
                1,
                None,
                canonical_authorization_json(
                    metadata
                ),
                now.isoformat(),
                now.isoformat(),
            ),
        )

        self._event(
            connection,
            recovery_id=recovery_id,
            worker_id=row["worker_id"],
            lease_id=row["lease_id"],
            authorization_id=
                row["authorization_id"],
            event_type=status.value,
            details={
                "decision":
                    decision.value,
                "reason":
                    reason.value,
            },
        )

        recovery_row = connection.execute(
            """
            SELECT *
            FROM execution_recoveries
            WHERE recovery_id = ?
            """,
            (
                recovery_id,
            ),
        ).fetchone()

        if recovery_row is None:
            raise RuntimeError(
                "Recovery record could not "
                "be loaded"
            )

        return self._record_from_row(
            recovery_row
        )

    def recover_worker(
        self,
        worker_id: str,
    ) -> ExecutionRecovery:
        recovery = (
            self._recover_worker_atomic(
                worker_id
            )
        )

        try:
            from app.services.decision_execution_recovery import (
                reconcile_decision_execution_recovery,
            )

            reconciliation = (
                reconcile_decision_execution_recovery(
                    recovery
                )
            )

            recovery.metadata[
                "decision_runtime_reconciliation"
            ] = reconciliation.to_dict()

        except Exception as exc:
            # Lease and heartbeat recovery has already committed.
            # A secondary Decision Runtime synchronization failure
            # must not roll back or misreport the primary recovery.
            recovery.metadata[
                "decision_runtime_reconciliation"
            ] = {
                "reconciled":
                    False,
                "reason":
                    "reconciliation_error",
                "error_type":
                    type(exc).__name__,
                "error":
                    str(exc),
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            }

        return recovery

    def recover_stale_workers(
        self,
        *,
        limit: int = 100,
    ) -> list[ExecutionRecovery]:
        normalized_limit = max(
            1,
            min(
                int(limit),
                1000,
            ),
        )

        now = datetime.now(
            timezone.utc
        )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT
                    worker_id,
                    last_heartbeat_at,
                    heartbeat_timeout_seconds,
                    status
                FROM execution_heartbeats
                WHERE status != ?
                ORDER BY last_heartbeat_at ASC
                LIMIT ?
                """,
                (
                    WorkerHeartbeatStatus
                    .STOPPED.value,
                    normalized_limit,
                ),
            ).fetchall()

        worker_ids: list[str] = []

        for row in rows:
            last_heartbeat_at = (
                self._parse_datetime(
                    row["last_heartbeat_at"]
                )
            )

            if last_heartbeat_at is None:
                worker_ids.append(
                    row["worker_id"]
                )

                continue

            age_seconds = (
                now
                - last_heartbeat_at
            ).total_seconds()

            if (
                age_seconds
                >= int(
                    row[
                        "heartbeat_timeout_seconds"
                    ]
                )
            ):
                worker_ids.append(
                    row["worker_id"]
                )

        return [
            self.recover_worker(
                worker_id
            )
            for worker_id in worker_ids
        ]

    def get(
        self,
        recovery_id: str,
    ) -> ExecutionRecovery | None:
        normalized = str(
            recovery_id
        ).strip()

        if not normalized:
            raise ValueError(
                "recovery_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM execution_recoveries
                WHERE recovery_id = ?
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

    def list_recoveries(
        self,
        *,
        status: RecoveryStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExecutionRecovery]:
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
                FROM execution_recoveries
                {where}
                ORDER BY detected_at DESC
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

    def events(
        self,
        recovery_id: str,
    ) -> list[dict[str, Any]]:
        normalized = str(
            recovery_id
        ).strip()

        if not normalized:
            raise ValueError(
                "recovery_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_recovery_events
                WHERE recovery_id = ?
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
                "recovery_id":
                    row["recovery_id"],
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
                "details":
                    json.loads(
                        row["details_payload"]
                    ),
            }
            for row in rows
        ]
