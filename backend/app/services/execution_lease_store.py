from __future__ import annotations

import json
import secrets
import sqlite3

from contextlib import closing
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.execution_authorization import (
    AuthorizationStatus,
)
from app.models.execution_lease import (
    ExecutionLease,
    ExecutionLeaseStatus,
    LeaseConflict,
    LeaseTokenMismatch,
    LeaseVersionConflict,
)
from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
    canonical_authorization_json,
)


DEFAULT_EXECUTION_LEASE_TTL_SECONDS = 60


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

    return parsed


class ExecutionLeaseStore:
    """
    Persistent atomic execution-lease management.

    Lease data is stored in the execution-authorization database so
    authorization validation and lease acquisition can occur inside
    one SQLite transaction.

    This store does not execute commands or contact managed devices.
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
                "Lease database path "
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
            authorization_table = (
                connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name = (
                        'execution_authorizations'
                      )
                    """
                ).fetchone()
            )

            if authorization_table is None:
                raise RuntimeError(
                    "Execution authorization "
                    "database must be initialized "
                    "before the lease store"
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_leases (
                    lease_id TEXT PRIMARY KEY,
                    authorization_id TEXT NOT NULL,
                    lease_token TEXT NOT NULL,
                    owner_id TEXT NOT NULL,

                    status TEXT NOT NULL,

                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    renewed_at TEXT,
                    released_at TEXT,

                    lease_version INTEGER
                        NOT NULL DEFAULT 1,

                    metadata TEXT NOT NULL,

                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

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
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_execution_leases_active_auth
                ON execution_leases (
                    authorization_id
                )
                WHERE status = 'active'
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_leases_owner
                ON execution_leases (
                    owner_id,
                    status,
                    expires_at
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_leases_expiry
                ON execution_leases (
                    status,
                    expires_at
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_lease_events (
                    event_id INTEGER
                        PRIMARY KEY AUTOINCREMENT,

                    lease_id TEXT NOT NULL,
                    authorization_id TEXT NOT NULL,

                    event_type TEXT NOT NULL,
                    event_at TEXT NOT NULL,

                    owner_id TEXT,
                    details_payload TEXT NOT NULL,

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
                CREATE INDEX IF NOT EXISTS
                idx_execution_lease_events
                ON execution_lease_events (
                    lease_id,
                    event_at ASC,
                    event_id ASC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> ExecutionLease:
        return ExecutionLease(
            lease_id=row["lease_id"],
            authorization_id=
                row["authorization_id"],
            lease_token=
                row["lease_token"],
            owner_id=row["owner_id"],
            status=ExecutionLeaseStatus(
                row["status"]
            ),
            acquired_at=_parse_datetime(
                row["acquired_at"]
            ),
            expires_at=_parse_datetime(
                row["expires_at"]
            ),
            renewed_at=_parse_datetime(
                row["renewed_at"]
            ),
            released_at=_parse_datetime(
                row["released_at"]
            ),
            lease_version=int(
                row["lease_version"]
            ),
            metadata=json.loads(
                row["metadata"]
            ),
        )

    @staticmethod
    def _normalize_ttl(
        ttl_seconds: int,
    ) -> int:
        normalized = int(
            ttl_seconds
        )

        if normalized < 5:
            raise ValueError(
                "ttl_seconds must be at least 5"
            )

        if normalized > 3600:
            raise ValueError(
                "ttl_seconds must not exceed 3600"
            )

        return normalized

    @staticmethod
    def _expire_due_in_connection(
        connection: sqlite3.Connection,
        *,
        now: datetime,
    ) -> int:
        cursor = connection.execute(
            """
            UPDATE execution_leases
            SET
                status = ?,
                lease_version =
                    lease_version + 1,
                updated_at = ?
            WHERE status = ?
              AND expires_at <= ?
            """,
            (
                ExecutionLeaseStatus
                .EXPIRED.value,
                now.isoformat(),
                ExecutionLeaseStatus
                .ACTIVE.value,
                now.isoformat(),
            ),
        )

        return int(
            cursor.rowcount
        )

    @staticmethod
    def _authorization_is_usable(
        row: sqlite3.Row,
        *,
        now: datetime,
    ) -> bool:
        if (
            row["status"]
            != AuthorizationStatus
            .APPROVED.value
        ):
            return False

        if not bool(
            row["execution_allowed"]
        ):
            return False

        if bool(
            row["consumed"]
        ):
            return False

        expires_at = _parse_datetime(
            row["expires_at"]
        )

        if (
            expires_at is not None
            and expires_at <= now
        ):
            return False

        return True

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        *,
        lease_id: str,
        authorization_id: str,
        event_type: str,
        owner_id: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO execution_lease_events (
                lease_id,
                authorization_id,
                event_type,
                event_at,
                owner_id,
                details_payload
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lease_id,
                authorization_id,
                event_type,
                datetime.now(
                    timezone.utc
                ).isoformat(),
                owner_id,
                canonical_authorization_json(
                    details or {}
                ),
            ),
        )

    def acquire(
        self,
        authorization_id: str,
        *,
        owner_id: str,
        ttl_seconds: int = (
            DEFAULT_EXECUTION_LEASE_TTL_SECONDS
        ),
    ) -> ExecutionLease:
        normalized_authorization_id = str(
            authorization_id
        ).strip()

        normalized_owner_id = str(
            owner_id
        ).strip()

        if not normalized_authorization_id:
            raise ValueError(
                "authorization_id must not be empty"
            )

        if not normalized_owner_id:
            raise ValueError(
                "owner_id must not be empty"
            )

        ttl_seconds = self._normalize_ttl(
            ttl_seconds
        )

        now = datetime.now(
            timezone.utc
        )

        expires_at = (
            now
            + timedelta(
                seconds=ttl_seconds
            )
        )

        lease_id = (
            f"lease:"
            f"{now.strftime('%Y%m%dT%H%M%S%fZ')}:"
            f"{uuid4().hex[:12]}"
        )

        lease_token = secrets.token_urlsafe(
            32
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            authorization_row = (
                connection.execute(
                    """
                    SELECT
                        authorization_id,
                        status,
                        execution_allowed,
                        consumed,
                        expires_at
                    FROM execution_authorizations
                    WHERE authorization_id = ?
                    """,
                    (
                        normalized_authorization_id,
                    ),
                ).fetchone()
            )

            if authorization_row is None:
                raise KeyError(
                    "Authorization not found"
                )

            if not self._authorization_is_usable(
                authorization_row,
                now=now,
            ):
                raise ValueError(
                    "Authorization is not usable "
                    "for execution lease"
                )

            self._expire_due_in_connection(
                connection,
                now=now,
            )

            active_row = connection.execute(
                """
                SELECT *
                FROM execution_leases
                WHERE authorization_id = ?
                  AND status = ?
                  AND expires_at > ?
                LIMIT 1
                """,
                (
                    normalized_authorization_id,
                    ExecutionLeaseStatus
                    .ACTIVE.value,
                    now.isoformat(),
                ),
            ).fetchone()

            if active_row is not None:
                raise LeaseConflict(
                    authorization_id=
                        normalized_authorization_id,
                    owner_id=
                        active_row["owner_id"],
                )

            metadata = {
                "execution_enabled":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
                "ttl_seconds":
                    ttl_seconds,
            }

            connection.execute(
                """
                INSERT INTO execution_leases (
                    lease_id,
                    authorization_id,
                    lease_token,
                    owner_id,
                    status,
                    acquired_at,
                    expires_at,
                    renewed_at,
                    released_at,
                    lease_version,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    lease_id,
                    normalized_authorization_id,
                    lease_token,
                    normalized_owner_id,
                    ExecutionLeaseStatus
                    .ACTIVE.value,
                    now.isoformat(),
                    expires_at.isoformat(),
                    None,
                    None,
                    1,
                    canonical_authorization_json(
                        metadata
                    ),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

            self._event(
                connection,
                lease_id=lease_id,
                authorization_id=
                    normalized_authorization_id,
                event_type="acquired",
                owner_id=normalized_owner_id,
                details={
                    "expires_at":
                        expires_at.isoformat(),
                    "lease_version":
                        1,
                },
            )

            connection.commit()

        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise LeaseConflict(
                authorization_id=
                    normalized_authorization_id
            ) from exc

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

        lease = self.get(
            lease_id
        )

        if lease is None:
            raise RuntimeError(
                "Created lease could not be loaded"
            )

        return lease

    def get(
        self,
        lease_id: str,
    ) -> ExecutionLease | None:
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
                FROM execution_leases
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

    def get_active(
        self,
        authorization_id: str,
    ) -> ExecutionLease | None:
        normalized = str(
            authorization_id
        ).strip()

        if not normalized:
            raise ValueError(
                "authorization_id must not be empty"
            )

        self.expire_due()

        now = datetime.now(
            timezone.utc
        )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM execution_leases
                WHERE authorization_id = ?
                  AND status = ?
                  AND expires_at > ?
                ORDER BY acquired_at DESC
                LIMIT 1
                """,
                (
                    normalized,
                    ExecutionLeaseStatus
                    .ACTIVE.value,
                    now.isoformat(),
                ),
            ).fetchone()

        if row is None:
            return None

        return self._record_from_row(
            row
        )

    def list_leases(
        self,
        *,
        authorization_id: str | None = None,
        owner_id: str | None = None,
        status: ExecutionLeaseStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExecutionLease]:
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

        if owner_id:
            clauses.append(
                "owner_id = ?"
            )

            parameters.append(
                str(owner_id).strip()
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
                FROM execution_leases
                {where}
                ORDER BY acquired_at DESC
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

    def verify_token(
        self,
        lease_id: str,
        *,
        lease_token: str,
    ) -> bool:
        lease = self.get(
            lease_id
        )

        if lease is None:
            return False

        return secrets.compare_digest(
            lease.lease_token,
            str(
                lease_token
            ).strip(),
        )

    def renew(
        self,
        lease_id: str,
        *,
        lease_token: str,
        expected_version: int,
        ttl_seconds: int = (
            DEFAULT_EXECUTION_LEASE_TTL_SECONDS
        ),
    ) -> ExecutionLease:
        normalized_lease_id = str(
            lease_id
        ).strip()

        normalized_token = str(
            lease_token
        ).strip()

        expected_version = int(
            expected_version
        )

        if expected_version < 1:
            raise ValueError(
                "expected_version must be at least 1"
            )

        ttl_seconds = self._normalize_ttl(
            ttl_seconds
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
                FROM execution_leases
                WHERE lease_id = ?
                """,
                (
                    normalized_lease_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Execution lease not found"
                )

            actual_version = int(
                row["lease_version"]
            )

            if (
                actual_version
                != expected_version
            ):
                raise LeaseVersionConflict(
                    lease_id=
                        normalized_lease_id,
                    expected_version=
                        expected_version,
                    actual_version=
                        actual_version,
                )

            if not secrets.compare_digest(
                row["lease_token"],
                normalized_token,
            ):
                raise LeaseTokenMismatch(
                    lease_id=
                        normalized_lease_id
                )

            expires_at = _parse_datetime(
                row["expires_at"]
            )

            if (
                row["status"]
                != ExecutionLeaseStatus
                .ACTIVE.value
                or expires_at is None
                or expires_at <= now
            ):
                connection.execute(
                    """
                    UPDATE execution_leases
                    SET
                        status = ?,
                        lease_version =
                            lease_version + 1,
                        updated_at = ?
                    WHERE lease_id = ?
                      AND status = ?
                    """,
                    (
                        ExecutionLeaseStatus
                        .EXPIRED.value,
                        now.isoformat(),
                        normalized_lease_id,
                        ExecutionLeaseStatus
                        .ACTIVE.value,
                    ),
                )

                connection.commit()

                raise ValueError(
                    "Execution lease is not active"
                )

            renewed_expires_at = (
                now
                + timedelta(
                    seconds=ttl_seconds
                )
            )

            cursor = connection.execute(
                """
                UPDATE execution_leases
                SET
                    renewed_at = ?,
                    expires_at = ?,
                    lease_version =
                        lease_version + 1,
                    updated_at = ?
                WHERE lease_id = ?
                  AND status = ?
                  AND lease_version = ?
                """,
                (
                    now.isoformat(),
                    renewed_expires_at.isoformat(),
                    now.isoformat(),
                    normalized_lease_id,
                    ExecutionLeaseStatus
                    .ACTIVE.value,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                current = connection.execute(
                    """
                    SELECT lease_version
                    FROM execution_leases
                    WHERE lease_id = ?
                    """,
                    (
                        normalized_lease_id,
                    ),
                ).fetchone()

                raise LeaseVersionConflict(
                    lease_id=
                        normalized_lease_id,
                    expected_version=
                        expected_version,
                    actual_version=(
                        int(
                            current[
                                "lease_version"
                            ]
                        )
                        if current
                        else actual_version
                    ),
                )

            self._event(
                connection,
                lease_id=
                    normalized_lease_id,
                authorization_id=
                    row["authorization_id"],
                event_type="renewed",
                owner_id=row["owner_id"],
                details={
                    "previous_version":
                        actual_version,
                    "current_version":
                        actual_version + 1,
                    "expires_at":
                        renewed_expires_at
                        .isoformat(),
                },
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        lease = self.get(
            normalized_lease_id
        )

        if lease is None:
            raise RuntimeError(
                "Renewed lease could not be loaded"
            )

        return lease

    def release(
        self,
        lease_id: str,
        *,
        lease_token: str,
        expected_version: int,
    ) -> ExecutionLease:
        normalized_lease_id = str(
            lease_id
        ).strip()

        normalized_token = str(
            lease_token
        ).strip()

        expected_version = int(
            expected_version
        )

        if expected_version < 1:
            raise ValueError(
                "expected_version must be at least 1"
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
                FROM execution_leases
                WHERE lease_id = ?
                """,
                (
                    normalized_lease_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Execution lease not found"
                )

            actual_version = int(
                row["lease_version"]
            )

            if (
                actual_version
                != expected_version
            ):
                raise LeaseVersionConflict(
                    lease_id=
                        normalized_lease_id,
                    expected_version=
                        expected_version,
                    actual_version=
                        actual_version,
                )

            if not secrets.compare_digest(
                row["lease_token"],
                normalized_token,
            ):
                raise LeaseTokenMismatch(
                    lease_id=
                        normalized_lease_id
                )

            if (
                row["status"]
                != ExecutionLeaseStatus
                .ACTIVE.value
            ):
                raise ValueError(
                    "Only active execution lease "
                    "can be released"
                )

            expires_at = _parse_datetime(
                row["expires_at"]
            )

            if (
                expires_at is None
                or expires_at <= now
            ):
                connection.execute(
                    """
                    UPDATE execution_leases
                    SET
                        status = ?,
                        lease_version =
                            lease_version + 1,
                        updated_at = ?
                    WHERE lease_id = ?
                      AND status = ?
                    """,
                    (
                        ExecutionLeaseStatus
                        .EXPIRED.value,
                        now.isoformat(),
                        normalized_lease_id,
                        ExecutionLeaseStatus
                        .ACTIVE.value,
                    ),
                )

                connection.commit()

                raise ValueError(
                    "Execution lease has expired"
                )

            cursor = connection.execute(
                """
                UPDATE execution_leases
                SET
                    status = ?,
                    released_at = ?,
                    lease_version =
                        lease_version + 1,
                    updated_at = ?
                WHERE lease_id = ?
                  AND status = ?
                  AND lease_version = ?
                """,
                (
                    ExecutionLeaseStatus
                    .RELEASED.value,
                    now.isoformat(),
                    now.isoformat(),
                    normalized_lease_id,
                    ExecutionLeaseStatus
                    .ACTIVE.value,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                current = connection.execute(
                    """
                    SELECT lease_version
                    FROM execution_leases
                    WHERE lease_id = ?
                    """,
                    (
                        normalized_lease_id,
                    ),
                ).fetchone()

                raise LeaseVersionConflict(
                    lease_id=
                        normalized_lease_id,
                    expected_version=
                        expected_version,
                    actual_version=(
                        int(
                            current[
                                "lease_version"
                            ]
                        )
                        if current
                        else actual_version
                    ),
                )

            self._event(
                connection,
                lease_id=
                    normalized_lease_id,
                authorization_id=
                    row["authorization_id"],
                event_type="released",
                owner_id=row["owner_id"],
                details={
                    "previous_version":
                        actual_version,
                    "current_version":
                        actual_version + 1,
                },
            )

            connection.commit()

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise

        finally:
            connection.close()

        lease = self.get(
            normalized_lease_id
        )

        if lease is None:
            raise RuntimeError(
                "Released lease could not be loaded"
            )

        return lease

    def expire_due(
        self,
    ) -> int:
        now = datetime.now(
            timezone.utc
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            rows = connection.execute(
                """
                SELECT *
                FROM execution_leases
                WHERE status = ?
                  AND expires_at <= ?
                """,
                (
                    ExecutionLeaseStatus
                    .ACTIVE.value,
                    now.isoformat(),
                ),
            ).fetchall()

            for row in rows:
                connection.execute(
                    """
                    UPDATE execution_leases
                    SET
                        status = ?,
                        lease_version =
                            lease_version + 1,
                        updated_at = ?
                    WHERE lease_id = ?
                      AND status = ?
                    """,
                    (
                        ExecutionLeaseStatus
                        .EXPIRED.value,
                        now.isoformat(),
                        row["lease_id"],
                        ExecutionLeaseStatus
                        .ACTIVE.value,
                    ),
                )

                self._event(
                    connection,
                    lease_id=row["lease_id"],
                    authorization_id=
                        row["authorization_id"],
                    event_type="expired",
                    owner_id=row["owner_id"],
                    details={
                        "previous_version":
                            int(
                                row[
                                    "lease_version"
                                ]
                            ),
                        "current_version":
                            int(
                                row[
                                    "lease_version"
                                ]
                            ) + 1,
                    },
                )

            connection.commit()

            return len(rows)

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def events(
        self,
        lease_id: str,
    ) -> list[dict[str, Any]]:
        normalized = str(
            lease_id
        ).strip()

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_lease_events
                WHERE lease_id = ?
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
                "lease_id":
                    row["lease_id"],
                "authorization_id":
                    row["authorization_id"],
                "event_type":
                    row["event_type"],
                "event_at":
                    row["event_at"],
                "owner_id":
                    row["owner_id"],
                "details":
                    json.loads(
                        row["details_payload"]
                    ),
            }
            for row in rows
        ]
