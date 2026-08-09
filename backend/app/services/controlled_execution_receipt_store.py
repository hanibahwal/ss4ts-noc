from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from app.models.controlled_execution_receipt import (
    ControlledExecutionReceipt,
    utc_now,
)


DEFAULT_RECEIPT_DATABASE = Path(
    os.getenv(
        "SS4TS_CONTROLLED_EXECUTION_RECEIPT_DB",
        str(
            Path(
                os.getenv(
                    "SS4TS_DATA_DIR",
                    "./data",
                )
            )
            / "controlled-execution-receipts.db"
        ),
    )
)


def _legacy_receipt_checksum(
    row: sqlite3.Row,
) -> str:
    payload = {
        "execution_id":
            row["execution_id"],
        "approval_id":
            row["approval_id"],
        "intent_fingerprint":
            row["intent_fingerprint"],
        "intent_version":
            row["intent_version"],
        "router_ip":
            row["router_ip"],
        "action_type":
            row["action_type"],
        "mode":
            row["mode"],
        "status":
            row["status"],
        "approval_status_before":
            row["approval_status_before"],
        "approval_status_after":
            row["approval_status_after"],
        "verification_status":
            row["verification_status"],
        "failure_reason":
            row["failure_reason"],
        "started_at":
            row["started_at"],
        "completed_at":
            row["completed_at"],
        "network_io_performed":
            bool(
                row[
                    "network_io_performed"
                ]
            ),
        "device_command_executed":
            bool(
                row[
                    "device_command_executed"
                ]
            ),
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


class ControlledExecutionReceiptStore:
    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_RECEIPT_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
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

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        return connection

    def initialize(self) -> None:
        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                controlled_execution_receipts
                (
                    execution_id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL,
                    intent_fingerprint TEXT NOT NULL,
                    intent_version TEXT NOT NULL,
                    router_ip TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    approval_status_before TEXT NOT NULL,
                    approval_status_after TEXT,
                    verification_status TEXT,
                    failure_reason TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    network_io_attempted INTEGER NOT NULL DEFAULT 0,
                    network_io_performed INTEGER NOT NULL,
                    device_command_executed INTEGER NOT NULL,
                    checksum TEXT NOT NULL
                )
                """
            )

            columns = {
                str(row["name"])
                for row in connection.execute(
                    """
                    PRAGMA table_info(
                        controlled_execution_receipts
                    )
                    """
                ).fetchall()
            }

            if (
                "network_io_attempted"
                not in columns
            ):
                legacy_rows = (
                    connection.execute(
                        """
                        SELECT *
                        FROM controlled_execution_receipts
                        """
                    ).fetchall()
                )

                for row in legacy_rows:
                    expected_checksum = (
                        _legacy_receipt_checksum(
                            row
                        )
                    )

                    stored_checksum = str(
                        row["checksum"]
                    ).strip()

                    if (
                        expected_checksum
                        != stored_checksum
                    ):
                        raise ValueError(
                            "Legacy execution receipt "
                            "checksum mismatch during "
                            "migration"
                        )

                connection.execute(
                    """
                    ALTER TABLE
                    controlled_execution_receipts
                    ADD COLUMN
                    network_io_attempted
                    INTEGER NOT NULL DEFAULT 0
                    """
                )

                migrated_rows = (
                    connection.execute(
                        """
                        SELECT *
                        FROM controlled_execution_receipts
                        """
                    ).fetchall()
                )

                for row in migrated_rows:
                    migrated = (
                        self._receipt(
                            row
                        )
                    )

                    connection.execute(
                        """
                        UPDATE
                        controlled_execution_receipts
                        SET checksum=?
                        WHERE execution_id=?
                        """,
                        (
                            migrated.checksum,
                            migrated.execution_id,
                        ),
                    )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_controlled_receipts_approval
                ON controlled_execution_receipts
                (
                    approval_id,
                    started_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_controlled_receipts_status
                ON controlled_execution_receipts
                (
                    status,
                    started_at DESC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _receipt(
        row: sqlite3.Row,
    ) -> ControlledExecutionReceipt:
        return ControlledExecutionReceipt(
            execution_id=
                row["execution_id"],
            approval_id=
                row["approval_id"],
            intent_fingerprint=
                row["intent_fingerprint"],
            intent_version=
                row["intent_version"],
            router_ip=
                row["router_ip"],
            action_type=
                row["action_type"],
            mode=
                row["mode"],
            status=
                row["status"],
            approval_status_before=
                row["approval_status_before"],
            approval_status_after=
                row["approval_status_after"],
            verification_status=
                row["verification_status"],
            failure_reason=
                row["failure_reason"],
            started_at=
                row["started_at"],
            completed_at=
                row["completed_at"],
            network_io_attempted=bool(
                row[
                    "network_io_attempted"
                ]
            ),
            network_io_performed=bool(
                row[
                    "network_io_performed"
                ]
            ),
            device_command_executed=bool(
                row[
                    "device_command_executed"
                ]
            ),
        )

    def create_started(
        self,
        *,
        execution_id: str,
        approval_id: str,
        intent_fingerprint: str,
        intent_version: str,
        router_ip: str,
        action_type: str,
        approval_status_before: str,
        mode: str = "SAFE_SIMULATION",
    ) -> ControlledExecutionReceipt:
        receipt = ControlledExecutionReceipt(
            execution_id=execution_id,
            approval_id=approval_id,
            intent_fingerprint=
                intent_fingerprint,
            intent_version=intent_version,
            router_ip=router_ip,
            action_type=action_type,
            mode=str(mode).strip(),
            status="STARTED",
            approval_status_before=
                approval_status_before,
            approval_status_after=
                "EXECUTING",
            verification_status=None,
            failure_reason=None,
            started_at=utc_now(),
            completed_at=None,
        )

        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                """
                INSERT INTO
                controlled_execution_receipts
                (
                    execution_id,
                    approval_id,
                    intent_fingerprint,
                    intent_version,
                    router_ip,
                    action_type,
                    mode,
                    status,
                    approval_status_before,
                    approval_status_after,
                    verification_status,
                    failure_reason,
                    started_at,
                    completed_at,
                    network_io_attempted,
                    network_io_performed,
                    device_command_executed,
                    checksum
                )
                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                 ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.execution_id,
                    receipt.approval_id,
                    receipt.intent_fingerprint,
                    receipt.intent_version,
                    receipt.router_ip,
                    receipt.action_type,
                    receipt.mode,
                    receipt.status,
                    receipt.approval_status_before,
                    receipt.approval_status_after,
                    receipt.verification_status,
                    receipt.failure_reason,
                    receipt.started_at,
                    receipt.completed_at,
                    0,
                    0,
                    0,
                    receipt.checksum,
                ),
            )

            connection.commit()

        return receipt

    def mark_network_io_attempted(
        self,
        execution_id: str,
    ) -> ControlledExecutionReceipt:
        current = self.get(
            execution_id
        )

        if current is None:
            raise KeyError(
                "Execution receipt not found"
            )

        if current.status != "STARTED":
            raise ValueError(
                "Execution receipt is already finalized"
            )

        if current.mode != "CANARY_READ_ONLY":
            raise ValueError(
                "Network I/O attempt is allowed only "
                "for CANARY_READ_ONLY receipts"
            )

        if current.network_io_attempted:
            return current

        updated = ControlledExecutionReceipt(
            execution_id=
                current.execution_id,
            approval_id=
                current.approval_id,
            intent_fingerprint=
                current.intent_fingerprint,
            intent_version=
                current.intent_version,
            router_ip=
                current.router_ip,
            action_type=
                current.action_type,
            mode=
                current.mode,
            status=
                current.status,
            approval_status_before=
                current.approval_status_before,
            approval_status_after=
                current.approval_status_after,
            verification_status=
                current.verification_status,
            failure_reason=
                current.failure_reason,
            started_at=
                current.started_at,
            completed_at=
                current.completed_at,
            network_io_attempted=True,
            network_io_performed=
                current.network_io_performed,
            device_command_executed=
                current.device_command_executed,
        )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE controlled_execution_receipts
                SET network_io_attempted=1,
                    checksum=?
                WHERE execution_id=?
                  AND status='STARTED'
                  AND network_io_attempted=0
                """,
                (
                    updated.checksum,
                    execution_id,
                ),
            )

            connection.commit()

        if cursor.rowcount == 0:
            latest = self.get(
                execution_id
            )

            if (
                latest is not None
                and latest.status == "STARTED"
                and latest.network_io_attempted
            ):
                return latest

            raise ValueError(
                "Execution receipt network-I/O "
                "attempt update conflict"
            )

        return updated

    def finalize(
        self,
        execution_id: str,
        *,
        status: str,
        approval_status_after: str,
        verification_status: str | None,
        failure_reason: str | None = None,
        network_io_attempted: bool | None = None,
        network_io_performed: bool | None = None,
        device_command_executed: bool | None = None,
    ) -> ControlledExecutionReceipt:
        current = self.get(
            execution_id
        )

        if current is None:
            raise KeyError(
                "Execution receipt not found"
            )

        if current.status != "STARTED":
            raise ValueError(
                "Execution receipt is already finalized"
            )

        completed = ControlledExecutionReceipt(
            execution_id=
                current.execution_id,
            approval_id=
                current.approval_id,
            intent_fingerprint=
                current.intent_fingerprint,
            intent_version=
                current.intent_version,
            router_ip=
                current.router_ip,
            action_type=
                current.action_type,
            mode=
                current.mode,
            status=
                str(status).strip(),
            approval_status_before=
                current.approval_status_before,
            approval_status_after=
                approval_status_after,
            verification_status=
                verification_status,
            failure_reason=
                failure_reason,
            started_at=
                current.started_at,
            completed_at=
                utc_now(),
            network_io_attempted=(
                current.network_io_attempted
                if network_io_attempted is None
                else bool(network_io_attempted)
            ),
            network_io_performed=(
                current.network_io_performed
                if network_io_performed is None
                else bool(network_io_performed)
            ),
            device_command_executed=(
                current.device_command_executed
                if device_command_executed is None
                else bool(device_command_executed)
            ),
        )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE controlled_execution_receipts
                SET status=?,
                    approval_status_after=?,
                    verification_status=?,
                    failure_reason=?,
                    completed_at=?,
                    network_io_attempted=?,
                    network_io_performed=?,
                    device_command_executed=?,
                    checksum=?
                WHERE execution_id=?
                  AND status='STARTED'
                """,
                (
                    completed.status,
                    completed.approval_status_after,
                    completed.verification_status,
                    completed.failure_reason,
                    completed.completed_at,
                    int(
                        completed.network_io_attempted
                    ),
                    int(
                        completed.network_io_performed
                    ),
                    int(
                        completed.device_command_executed
                    ),
                    completed.checksum,
                    execution_id,
                ),
            )

            connection.commit()

        if cursor.rowcount != 1:
            raise ValueError(
                "Execution receipt finalization conflict"
            )

        return completed

    def get(
        self,
        execution_id: str,
    ) -> ControlledExecutionReceipt | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM controlled_execution_receipts
                WHERE execution_id=?
                """,
                (
                    str(
                        execution_id
                    ).strip(),
                ),
            ).fetchone()

        if row is None:
            return None

        receipt = self._receipt(
            row
        )

        if not receipt.verify(
            row["checksum"]
        ):
            raise ValueError(
                "Execution receipt checksum mismatch"
            )

        return receipt

    def by_approval(
        self,
        approval_id: str,
        *,
        limit: int = 50,
    ) -> list[ControlledExecutionReceipt]:
        safe_limit = max(
            1,
            min(
                int(limit),
                200,
            ),
        )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM controlled_execution_receipts
                WHERE approval_id=?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (
                    str(
                        approval_id
                    ).strip(),
                    safe_limit,
                ),
            ).fetchall()

        receipts = []

        for row in rows:
            receipt = self._receipt(
                row
            )

            if not receipt.verify(
                row["checksum"]
            ):
                raise ValueError(
                    "Execution receipt checksum mismatch"
                )

            receipts.append(
                receipt
            )

        return receipts

    def started_before(
        self,
        cutoff_at: str,
        *,
        limit: int = 100,
    ) -> list[ControlledExecutionReceipt]:
        """
        Return STARTED receipts older than the recovery cutoff.
        """
        safe_limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

        normalized_cutoff = str(
            cutoff_at
        ).strip()

        if not normalized_cutoff:
            raise ValueError(
                "cutoff_at is required"
            )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM controlled_execution_receipts
                WHERE status='STARTED'
                  AND started_at<=?
                ORDER BY started_at
                LIMIT ?
                """,
                (
                    normalized_cutoff,
                    safe_limit,
                ),
            ).fetchall()

        receipts = []

        for row in rows:
            receipt = self._receipt(
                row
            )

            if not receipt.verify(
                row["checksum"]
            ):
                raise ValueError(
                    "Execution receipt checksum mismatch"
                )

            receipts.append(
                receipt
            )

        return receipts

    def has_receipt_for_approval(
        self,
        approval_id: str,
    ) -> bool:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM controlled_execution_receipts
                WHERE approval_id=?
                LIMIT 1
                """,
                (
                    str(
                        approval_id
                    ).strip(),
                ),
            ).fetchone()

        return row is not None


receipt_store = (
    ControlledExecutionReceiptStore()
)
