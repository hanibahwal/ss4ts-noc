from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from app.services.data_directory import data_path
from typing import Any, Iterable
from uuid import uuid4

from app.models.decision_audit import (
    DecisionAuditRecord,
    DecisionAuditStatus,
)
from app.models.decision_explanation import (
    DecisionExplanation,
)
from app.models.decision_trace import (
    DecisionTrace,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.models.execution_simulation import (
    ExecutionSimulationResult,
)


DEFAULT_AUDIT_DATABASE = data_path(
    "decision-audit.db"
)


def canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def calculate_audit_checksum(
    *,
    trace_payload: dict[str, Any],
    explanation_payload: dict[str, Any],
    execution_plan_payload: dict[str, Any],
    simulation_payload: dict[str, Any],
) -> str:
    content = {
        "trace_payload":
            trace_payload,
        "explanation_payload":
            explanation_payload,
        "execution_plan_payload":
            execution_plan_payload,
        "simulation_payload":
            simulation_payload,
    }

    return hashlib.sha256(
        canonical_json(
            content
        ).encode("utf-8")
    ).hexdigest()


class DecisionAuditStore:
    """
    Persist immutable decision-audit snapshots in SQLite.

    The store performs local database I/O only. It does not contact
    managed devices and does not execute network commands.
    """

    def __init__(
        self,
        database_path: (
            str
            | Path
        ) = DEFAULT_AUDIT_DATABASE,
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if str(self.database_path).strip() == "":
            raise ValueError(
                "Audit database path must not be empty"
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
            self.database_path
        )

        connection.row_factory = (
            sqlite3.Row
        )

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
                decision_audit_records (
                    audit_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    source_node_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    primary_cause_id TEXT,
                    trace_payload TEXT NOT NULL,
                    explanation_payload TEXT NOT NULL,
                    execution_plan_payload TEXT NOT NULL,
                    simulation_payload TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_decision_audit_source_created
                ON decision_audit_records (
                    source_node_id,
                    created_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_decision_audit_decision
                ON decision_audit_records (
                    decision_id
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_decision_audit_trace
                ON decision_audit_records (
                    trace_id
                )
                """
            )

            connection.commit()

    @staticmethod
    def _payload(
        value: Any,
    ) -> dict[str, Any]:
        if value is None:
            return {}

        if isinstance(
            value,
            dict,
        ):
            return dict(value)

        to_dict = getattr(
            value,
            "to_dict",
            None,
        )

        if callable(to_dict):
            payload = to_dict()

            if isinstance(
                payload,
                dict,
            ):
                return payload

        raise TypeError(
            "Audit payload must be a dictionary "
            "or expose to_dict()"
        )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> DecisionAuditRecord:
        return DecisionAuditRecord(
            audit_id=row["audit_id"],
            trace_id=row["trace_id"],
            decision_id=
                row["decision_id"],
            source_node_id=
                row["source_node_id"],
            created_at=
                row["created_at"],
            status=row["status"],
            risk_level=
                row["risk_level"],
            risk_score=
                row["risk_score"],
            primary_cause_id=
                row["primary_cause_id"],
            trace_payload=json.loads(
                row["trace_payload"]
            ),
            explanation_payload=json.loads(
                row[
                    "explanation_payload"
                ]
            ),
            execution_plan_payload=json.loads(
                row[
                    "execution_plan_payload"
                ]
            ),
            simulation_payload=json.loads(
                row[
                    "simulation_payload"
                ]
            ),
            checksum=row["checksum"],
            metadata=json.loads(
                row["metadata"]
            ),
        )

    def create_record(
        self,
        *,
        trace: (
            DecisionTrace
            | dict[str, Any]
        ),
        explanation: (
            DecisionExplanation
            | dict[str, Any]
            | None
        ) = None,
        execution_plan: (
            ExecutionPlan
            | dict[str, Any]
            | None
        ) = None,
        simulation: (
            ExecutionSimulationResult
            | dict[str, Any]
            | None
        ) = None,
        metadata: (
            dict[str, Any]
            | None
        ) = None,
        audit_id: str | None = None,
    ) -> DecisionAuditRecord:
        trace_payload = self._payload(
            trace
        )

        explanation_payload = (
            self._payload(
                explanation
            )
            if explanation is not None
            else {}
        )

        execution_plan_payload = (
            self._payload(
                execution_plan
            )
            if execution_plan is not None
            else {}
        )

        simulation_payload = (
            self._payload(
                simulation
            )
            if simulation is not None
            else {}
        )

        trace_id = str(
            trace_payload.get(
                "trace_id",
                "",
            )
        ).strip()

        decision_id = str(
            trace_payload.get(
                "decision_id",
                "",
            )
        ).strip()

        source_node_id = str(
            trace_payload.get(
                "source_node_id",
                "",
            )
        ).strip()

        if not trace_id:
            raise ValueError(
                "Trace payload has no trace_id"
            )

        if not decision_id:
            raise ValueError(
                "Trace payload has no decision_id"
            )

        if not source_node_id:
            raise ValueError(
                "Trace payload has no source_node_id"
            )

        trace_metadata = (
            trace_payload.get(
                "metadata",
                {},
            )
        )

        if not isinstance(
            trace_metadata,
            dict,
        ):
            trace_metadata = {}

        checksum = calculate_audit_checksum(
            trace_payload=
                trace_payload,
            explanation_payload=
                explanation_payload,
            execution_plan_payload=
                execution_plan_payload,
            simulation_payload=
                simulation_payload,
        )

        created_at = datetime.now(
            timezone.utc
        )

        record = DecisionAuditRecord(
            audit_id=(
                audit_id
                or (
                    f"audit:"
                    f"{created_at.strftime('%Y%m%dT%H%M%S%fZ')}:"
                    f"{uuid4().hex[:12]}"
                )
            ),
            trace_id=trace_id,
            decision_id=decision_id,
            source_node_id=
                source_node_id,
            created_at=created_at,
            status=(
                DecisionAuditStatus
                .RECORDED
            ),
            risk_level=str(
                trace_metadata.get(
                    "risk_level",
                    "unknown",
                )
            ),
            risk_score=float(
                trace_metadata.get(
                    "risk_score",
                    0.0,
                )
            ),
            primary_cause_id=(
                trace_metadata.get(
                    "primary_cause_id"
                )
            ),
            trace_payload=
                trace_payload,
            explanation_payload=
                explanation_payload,
            execution_plan_payload=
                execution_plan_payload,
            simulation_payload=
                simulation_payload,
            checksum=checksum,
            metadata={
                **(
                    metadata
                    if isinstance(
                        metadata,
                        dict,
                    )
                    else {}
                ),
                "storage_engine":
                    "sqlite",
                "checksum_algorithm":
                    "sha256",
                "read_only_snapshot":
                    True,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        )

        with closing(
            self._connect()
        ) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO
                    decision_audit_records (
                        audit_id,
                        trace_id,
                        decision_id,
                        source_node_id,
                        created_at,
                        status,
                        risk_level,
                        risk_score,
                        primary_cause_id,
                        trace_payload,
                        explanation_payload,
                        execution_plan_payload,
                        simulation_payload,
                        checksum,
                        metadata
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?
                    )
                    """,
                    (
                        record.audit_id,
                        record.trace_id,
                        record.decision_id,
                        record.source_node_id,
                        record.created_at
                        .isoformat(),
                        record.status.value,
                        record.risk_level,
                        record.risk_score,
                        record.primary_cause_id,
                        canonical_json(
                            record.trace_payload
                        ),
                        canonical_json(
                            record
                            .explanation_payload
                        ),
                        canonical_json(
                            record
                            .execution_plan_payload
                        ),
                        canonical_json(
                            record
                            .simulation_payload
                        ),
                        record.checksum,
                        canonical_json(
                            record.metadata
                        ),
                    ),
                )

                connection.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    "Decision audit_id already exists"
                ) from exc

        return record

    def get(
        self,
        audit_id: str,
    ) -> DecisionAuditRecord | None:
        normalized = str(
            audit_id
        ).strip()

        if not normalized:
            raise ValueError(
                "audit_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM decision_audit_records
                WHERE audit_id = ?
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

    def list_records(
        self,
        *,
        source_node_id: str | None = None,
        decision_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DecisionAuditRecord]:
        limit = max(
            1,
            min(
                int(limit),
                1000,
            ),
        )

        offset = max(
            int(offset),
            0,
        )

        clauses: list[str] = []
        parameters: list[Any] = []

        if source_node_id:
            clauses.append(
                "source_node_id = ?"
            )
            parameters.append(
                str(
                    source_node_id
                ).strip()
            )

        if decision_id:
            clauses.append(
                "decision_id = ?"
            )
            parameters.append(
                str(
                    decision_id
                ).strip()
            )

        where = (
            " WHERE "
            + " AND ".join(
                clauses
            )
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
                FROM decision_audit_records
                {where}
                ORDER BY created_at DESC
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

    def count(
        self,
        *,
        source_node_id: str | None = None,
    ) -> int:
        if source_node_id:
            query = """
                SELECT COUNT(*) AS total
                FROM decision_audit_records
                WHERE source_node_id = ?
            """

            parameters: Iterable[Any] = (
                str(
                    source_node_id
                ).strip(),
            )
        else:
            query = """
                SELECT COUNT(*) AS total
                FROM decision_audit_records
            """

            parameters = ()

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                query,
                parameters,
            ).fetchone()

        return int(
            row["total"]
            if row is not None
            else 0
        )

    def verify(
        self,
        audit_id: str,
    ) -> bool:
        record = self.get(
            audit_id
        )

        if record is None:
            return False

        calculated = (
            calculate_audit_checksum(
                trace_payload=
                    record.trace_payload,
                explanation_payload=
                    record
                    .explanation_payload,
                execution_plan_payload=
                    record
                    .execution_plan_payload,
                simulation_payload=
                    record
                    .simulation_payload,
            )
        )

        return (
            calculated
            == record.checksum
        )

    def delete(
        self,
        audit_id: str,
    ) -> bool:
        """
        Delete is provided for tests and administrative retention only.
        Production APIs should not expose this operation directly.
        """

        normalized = str(
            audit_id
        ).strip()

        if not normalized:
            raise ValueError(
                "audit_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            cursor = connection.execute(
                """
                DELETE FROM decision_audit_records
                WHERE audit_id = ?
                """,
                (
                    normalized,
                ),
            )

            connection.commit()

        return cursor.rowcount > 0
