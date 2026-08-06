from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from app.models.autonomous_controlled_authorization_human_decision import (
    AutonomousControlledAuthorizationHumanDecision,
    AutonomousControlledAuthorizationHumanDecisionType,
)


DEFAULT_AUTONOMOUS_HUMAN_APPROVAL_DECISION_DATABASE = Path(
    os.getenv(
        "SS4TS_AUTONOMOUS_HUMAN_APPROVAL_DECISION_DB",
        str(
            Path(
                os.getenv(
                    "SS4TS_DATA_DIR",
                    "./data",
                )
            )
            / (
                "autonomous-controlled-authorization-"
                "human-decisions.db"
            )
        ),
    )
)

GENESIS_RECORD_HASH = "0" * 64


class AutonomousHumanApprovalDecisionStoreError(
    RuntimeError
):
    """Base human approval decision store error."""


class AutonomousHumanApprovalDecisionDuplicate(
    AutonomousHumanApprovalDecisionStoreError
):
    """Decision or protected candidate identity already exists."""


class AutonomousHumanApprovalDecisionIntegrityError(
    AutonomousHumanApprovalDecisionStoreError
):
    """Stored human approval decision failed integrity checks."""


def canonical_human_approval_decision_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _normalized_datetime_text(
    value: datetime,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            f"{field_name} must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    ).isoformat()


def calculate_human_approval_decision_record_hash(
    *,
    sequence_number: int,
    approval_decision_id: str,
    decision_fingerprint: str,
    approval_candidate_id: str,
    candidate_record_hash: str,
    candidate_fingerprint: str,
    candidate_audit_id: str,
    candidate_audit_valid: bool,
    binding_id: str,
    execution_authorization_id: str,
    plan_id: str,
    source_decision_id: str,
    risk_class: str,
    reviewer_id: str,
    human_decision: str,
    decision_reason: str,
    decided_at: str,
    decision_payload: dict[str, Any],
    stored_at: str,
    previous_record_hash: str,
) -> str:
    payload = {
        "sequence_number":
            int(
                sequence_number
            ),
        "approval_decision_id":
            approval_decision_id,
        "decision_fingerprint":
            decision_fingerprint,
        "approval_candidate_id":
            approval_candidate_id,
        "candidate_record_hash":
            candidate_record_hash,
        "candidate_fingerprint":
            candidate_fingerprint,
        "candidate_audit_id":
            candidate_audit_id,
        "candidate_audit_valid":
            bool(
                candidate_audit_valid
            ),
        "binding_id":
            binding_id,
        "execution_authorization_id":
            execution_authorization_id,
        "plan_id":
            plan_id,
        "source_decision_id":
            source_decision_id,
        "risk_class":
            risk_class,
        "reviewer_id":
            reviewer_id,
        "human_decision":
            human_decision,
        "decision_reason":
            decision_reason,
        "decided_at":
            decided_at,
        "decision_payload":
            decision_payload,
        "stored_at":
            stored_at,
        "previous_record_hash":
            previous_record_hash,
    }

    return hashlib.sha256(
        canonical_human_approval_decision_json(
            payload
        ).encode("utf-8")
    ).hexdigest()


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousHumanApprovalDecisionRecord:
    sequence_number: int

    approval_decision_id: str
    decision_fingerprint: str

    approval_candidate_id: str
    candidate_record_hash: str
    candidate_fingerprint: str
    candidate_audit_id: str
    candidate_audit_valid: bool

    binding_id: str
    execution_authorization_id: str
    plan_id: str
    source_decision_id: str
    risk_class: str

    reviewer_id: str
    human_decision: str
    decision_reason: str
    decided_at: str

    decision_payload: dict[str, Any]

    stored_at: str
    previous_record_hash: str
    record_hash: str

    @property
    def human_decision_recorded(
        self,
    ) -> bool:
        return True

    @property
    def approved_by_human(
        self,
    ) -> bool:
        return self.human_decision == "approved"

    @property
    def authorization_approved(
        self,
    ) -> bool:
        return False

    @property
    def authorization_token_created(
        self,
    ) -> bool:
        return False

    @property
    def approval_claim_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_lease_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_allowed(
        self,
    ) -> bool:
        return False

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def verify_hash(
        self,
    ) -> bool:
        expected = (
            calculate_human_approval_decision_record_hash(
                sequence_number=(
                    self.sequence_number
                ),
                approval_decision_id=(
                    self.approval_decision_id
                ),
                decision_fingerprint=(
                    self.decision_fingerprint
                ),
                approval_candidate_id=(
                    self.approval_candidate_id
                ),
                candidate_record_hash=(
                    self.candidate_record_hash
                ),
                candidate_fingerprint=(
                    self.candidate_fingerprint
                ),
                candidate_audit_id=(
                    self.candidate_audit_id
                ),
                candidate_audit_valid=(
                    self.candidate_audit_valid
                ),
                binding_id=(
                    self.binding_id
                ),
                execution_authorization_id=(
                    self.execution_authorization_id
                ),
                plan_id=(
                    self.plan_id
                ),
                source_decision_id=(
                    self.source_decision_id
                ),
                risk_class=(
                    self.risk_class
                ),
                reviewer_id=(
                    self.reviewer_id
                ),
                human_decision=(
                    self.human_decision
                ),
                decision_reason=(
                    self.decision_reason
                ),
                decided_at=(
                    self.decided_at
                ),
                decision_payload=(
                    self.decision_payload
                ),
                stored_at=(
                    self.stored_at
                ),
                previous_record_hash=(
                    self.previous_record_hash
                ),
            )
        )

        return expected == self.record_hash

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "sequence_number":
                self.sequence_number,
            "approval_decision_id":
                self.approval_decision_id,
            "decision_fingerprint":
                self.decision_fingerprint,
            "approval_candidate_id":
                self.approval_candidate_id,
            "candidate_record_hash":
                self.candidate_record_hash,
            "candidate_fingerprint":
                self.candidate_fingerprint,
            "candidate_audit_id":
                self.candidate_audit_id,
            "candidate_audit_valid":
                self.candidate_audit_valid,
            "binding_id":
                self.binding_id,
            "execution_authorization_id":
                self.execution_authorization_id,
            "plan_id":
                self.plan_id,
            "source_decision_id":
                self.source_decision_id,
            "risk_class":
                self.risk_class,
            "reviewer_id":
                self.reviewer_id,
            "human_decision":
                self.human_decision,
            "decision_reason":
                self.decision_reason,
            "decided_at":
                self.decided_at,
            "decision_payload":
                self.decision_payload,
            "stored_at":
                self.stored_at,
            "previous_record_hash":
                self.previous_record_hash,
            "record_hash":
                self.record_hash,
            "human_decision_recorded":
                True,
            "approved_by_human":
                self.approved_by_human,
            "authorization_approved":
                False,
            "authorization_token_created":
                False,
            "approval_claim_created":
                False,
            "execution_lease_created":
                False,
            "execution_allowed":
                False,
            "can_execute":
                False,
            "safety": {
                "immutable_record":
                    True,
                "append_only":
                    True,
                "human_decision_record_only":
                    True,
                "authorization_approved":
                    False,
                "authorization_token_created":
                    False,
                "approval_claim_created":
                    False,
                "execution_lease_created":
                    False,
                "execution_allowed":
                    False,
                "execution_approved":
                    False,
                "authorization_consumed":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_access_performed":
                    False,
                "command_generated":
                    False,
                "device_command_executed":
                    False,
            },
        }


class AutonomousControlledAuthorizationHumanDecisionStore:
    """
    Immutable append-only human approval decision ledger.

    Recording an approved human decision does not approve an
    execution authorization and does not create a token, claim,
    lease, simulation, device operation, or command execution.
    """

    TABLE_NAME = (
        "autonomous_controlled_authorization_"
        "human_decision_records"
    )

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTONOMOUS_HUMAN_APPROVAL_DECISION_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Human approval decision database "
                "path must not be empty"
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
            "PRAGMA busy_timeout = 30000"
        )
        connection.execute(
            "PRAGMA journal_mode = WAL"
        )
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        return connection

    def initialize(
        self,
    ) -> None:
        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS
                {self.TABLE_NAME}
                (
                    sequence_number
                        INTEGER PRIMARY KEY AUTOINCREMENT,

                    approval_decision_id
                        TEXT NOT NULL UNIQUE,

                    decision_fingerprint
                        TEXT NOT NULL UNIQUE,

                    approval_candidate_id
                        TEXT NOT NULL UNIQUE,

                    candidate_record_hash
                        TEXT NOT NULL UNIQUE,

                    candidate_fingerprint
                        TEXT NOT NULL UNIQUE,

                    candidate_audit_id
                        TEXT NOT NULL,

                    candidate_audit_valid
                        INTEGER NOT NULL,

                    binding_id
                        TEXT NOT NULL,

                    execution_authorization_id
                        TEXT NOT NULL UNIQUE,

                    plan_id
                        TEXT NOT NULL,

                    source_decision_id
                        TEXT NOT NULL,

                    risk_class
                        TEXT NOT NULL,

                    reviewer_id
                        TEXT NOT NULL,

                    human_decision
                        TEXT NOT NULL,

                    decision_reason
                        TEXT NOT NULL,

                    decided_at
                        TEXT NOT NULL,

                    decision_payload
                        TEXT NOT NULL,

                    stored_at
                        TEXT NOT NULL,

                    previous_record_hash
                        TEXT NOT NULL,

                    record_hash
                        TEXT NOT NULL UNIQUE
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_human_approval_decision_stored
                ON {self.TABLE_NAME}
                (
                    stored_at DESC,
                    sequence_number DESC
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_human_approval_decision_reviewer
                ON {self.TABLE_NAME}
                (
                    reviewer_id,
                    decided_at DESC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_decision(
        decision: (
            AutonomousControlledAuthorizationHumanDecision
        ),
    ) -> None:
        if not isinstance(
            decision,
            AutonomousControlledAuthorizationHumanDecision,
        ):
            raise TypeError(
                "decision must be an "
                "AutonomousControlledAuthorizationHumanDecision"
            )

        if (
            decision.calculate_fingerprint()
            != decision.decision_fingerprint
        ):
            raise AutonomousHumanApprovalDecisionIntegrityError(
                "Human approval decision fingerprint mismatch"
            )

        if decision.candidate_audit_valid is not True:
            raise AutonomousHumanApprovalDecisionIntegrityError(
                "Human approval decision requires "
                "a valid candidate audit"
            )

        if (
            decision.human_decision
            not in set(
                AutonomousControlledAuthorizationHumanDecisionType
            )
        ):
            raise AutonomousHumanApprovalDecisionIntegrityError(
                "Human approval decision is unsupported"
            )

        if decision.human_decision_recorded is not True:
            raise AutonomousHumanApprovalDecisionIntegrityError(
                "Human approval decision was not recorded"
            )

        if (
            decision.authorization_approved
            or decision.authorization_token_created
            or decision.approval_claim_created
            or decision.execution_lease_created
            or decision.execution_allowed
            or decision.can_execute
        ):
            raise AutonomousHumanApprovalDecisionIntegrityError(
                "Human approval decision unexpectedly "
                "contains execution authority"
            )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> AutonomousHumanApprovalDecisionRecord:
        try:
            decision_payload = json.loads(
                row[
                    "decision_payload"
                ]
            )
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AutonomousHumanApprovalDecisionIntegrityError(
                "Human approval decision record "
                "contains invalid JSON"
            ) from exc

        if not isinstance(
            decision_payload,
            dict,
        ):
            raise AutonomousHumanApprovalDecisionIntegrityError(
                "Human approval decision payload "
                "must be an object"
            )

        return AutonomousHumanApprovalDecisionRecord(
            sequence_number=int(
                row[
                    "sequence_number"
                ]
            ),
            approval_decision_id=str(
                row[
                    "approval_decision_id"
                ]
            ),
            decision_fingerprint=str(
                row[
                    "decision_fingerprint"
                ]
            ),
            approval_candidate_id=str(
                row[
                    "approval_candidate_id"
                ]
            ),
            candidate_record_hash=str(
                row[
                    "candidate_record_hash"
                ]
            ),
            candidate_fingerprint=str(
                row[
                    "candidate_fingerprint"
                ]
            ),
            candidate_audit_id=str(
                row[
                    "candidate_audit_id"
                ]
            ),
            candidate_audit_valid=bool(
                row[
                    "candidate_audit_valid"
                ]
            ),
            binding_id=str(
                row[
                    "binding_id"
                ]
            ),
            execution_authorization_id=str(
                row[
                    "execution_authorization_id"
                ]
            ),
            plan_id=str(
                row[
                    "plan_id"
                ]
            ),
            source_decision_id=str(
                row[
                    "source_decision_id"
                ]
            ),
            risk_class=str(
                row[
                    "risk_class"
                ]
            ),
            reviewer_id=str(
                row[
                    "reviewer_id"
                ]
            ),
            human_decision=str(
                row[
                    "human_decision"
                ]
            ),
            decision_reason=str(
                row[
                    "decision_reason"
                ]
            ),
            decided_at=str(
                row[
                    "decided_at"
                ]
            ),
            decision_payload=(
                decision_payload
            ),
            stored_at=str(
                row[
                    "stored_at"
                ]
            ),
            previous_record_hash=str(
                row[
                    "previous_record_hash"
                ]
            ),
            record_hash=str(
                row[
                    "record_hash"
                ]
            ),
        )

    def append(
        self,
        *,
        decision: (
            AutonomousControlledAuthorizationHumanDecision
        ),
        stored_at: datetime | None = None,
    ) -> AutonomousHumanApprovalDecisionRecord:
        self._validate_decision(
            decision
        )

        resolved_stored_at = (
            stored_at
            or datetime.now(
                timezone.utc
            )
        )

        stored_at_text = (
            _normalized_datetime_text(
                resolved_stored_at,
                field_name="stored_at",
            )
        )

        decided_at_text = (
            decision.decided_at.isoformat()
        )

        resolved_stored_datetime = (
            datetime.fromisoformat(
                stored_at_text
            )
        )

        if (
            resolved_stored_datetime
            < decision.decided_at
        ):
            raise ValueError(
                "stored_at must not be earlier "
                "than decided_at"
            )

        decision_payload = (
            decision.to_dict()
        )

        for field_name in (
            "authorization_approved",
            "authorization_token_created",
            "approval_claim_created",
            "execution_lease_created",
            "execution_allowed",
            "can_execute",
        ):
            if (
                decision_payload.get(
                    field_name
                )
                is not False
            ):
                raise AutonomousHumanApprovalDecisionIntegrityError(
                    "Human approval decision payload "
                    f"contains unsafe claim: {field_name}"
                )

        decision_payload_json = (
            canonical_human_approval_decision_json(
                decision_payload
            )
        )

        try:
            with closing(
                self._connect()
            ) as connection:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                last_row = connection.execute(
                    f"""
                    SELECT
                        sequence_number,
                        record_hash
                    FROM {self.TABLE_NAME}
                    ORDER BY sequence_number DESC
                    LIMIT 1
                    """
                ).fetchone()

                if last_row is None:
                    sequence_number = 1
                    previous_record_hash = (
                        GENESIS_RECORD_HASH
                    )
                else:
                    sequence_number = (
                        int(
                            last_row[
                                "sequence_number"
                            ]
                        )
                        + 1
                    )
                    previous_record_hash = str(
                        last_row[
                            "record_hash"
                        ]
                    )

                record_hash = (
                    calculate_human_approval_decision_record_hash(
                        sequence_number=(
                            sequence_number
                        ),
                        approval_decision_id=(
                            decision.approval_decision_id
                        ),
                        decision_fingerprint=(
                            decision.decision_fingerprint
                        ),
                        approval_candidate_id=(
                            decision.approval_candidate_id
                        ),
                        candidate_record_hash=(
                            decision.candidate_record_hash
                        ),
                        candidate_fingerprint=(
                            decision.candidate_fingerprint
                        ),
                        candidate_audit_id=(
                            decision.candidate_audit_id
                        ),
                        candidate_audit_valid=(
                            decision.candidate_audit_valid
                        ),
                        binding_id=(
                            decision.binding_id
                        ),
                        execution_authorization_id=(
                            decision.execution_authorization_id
                        ),
                        plan_id=(
                            decision.plan_id
                        ),
                        source_decision_id=(
                            decision.source_decision_id
                        ),
                        risk_class=(
                            decision.risk_class
                        ),
                        reviewer_id=(
                            decision.reviewer_id
                        ),
                        human_decision=(
                            decision.human_decision.value
                        ),
                        decision_reason=(
                            decision.decision_reason
                        ),
                        decided_at=(
                            decided_at_text
                        ),
                        decision_payload=(
                            decision_payload
                        ),
                        stored_at=(
                            stored_at_text
                        ),
                        previous_record_hash=(
                            previous_record_hash
                        ),
                    )
                )

                connection.execute(
                    f"""
                    INSERT INTO {self.TABLE_NAME}
                    (
                        sequence_number,
                        approval_decision_id,
                        decision_fingerprint,
                        approval_candidate_id,
                        candidate_record_hash,
                        candidate_fingerprint,
                        candidate_audit_id,
                        candidate_audit_valid,
                        binding_id,
                        execution_authorization_id,
                        plan_id,
                        source_decision_id,
                        risk_class,
                        reviewer_id,
                        human_decision,
                        decision_reason,
                        decided_at,
                        decision_payload,
                        stored_at,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES
                    (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        sequence_number,
                        decision.approval_decision_id,
                        decision.decision_fingerprint,
                        decision.approval_candidate_id,
                        decision.candidate_record_hash,
                        decision.candidate_fingerprint,
                        decision.candidate_audit_id,
                        int(
                            decision.candidate_audit_valid
                        ),
                        decision.binding_id,
                        decision.execution_authorization_id,
                        decision.plan_id,
                        decision.source_decision_id,
                        decision.risk_class,
                        decision.reviewer_id,
                        decision.human_decision.value,
                        decision.decision_reason,
                        decided_at_text,
                        decision_payload_json,
                        stored_at_text,
                        previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

        except sqlite3.IntegrityError as exc:
            raise AutonomousHumanApprovalDecisionDuplicate(
                "Human approval decision protected "
                "identity already exists"
            ) from exc

        record = self.get(
            sequence_number
        )

        if record is None:
            raise AutonomousHumanApprovalDecisionStoreError(
                "Stored human approval decision "
                "could not be reloaded"
            )

        if not record.verify_hash():
            raise AutonomousHumanApprovalDecisionIntegrityError(
                "Stored human approval decision "
                "record hash mismatch"
            )

        return record

    def get(
        self,
        sequence_number: int,
    ) -> AutonomousHumanApprovalDecisionRecord | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE sequence_number = ?
                """,
                (
                    int(
                        sequence_number
                    ),
                ),
            ).fetchone()

        if row is None:
            return None

        return self._record_from_row(
            row
        )

    def _get_by_field(
        self,
        *,
        field_name: str,
        value: str,
    ) -> AutonomousHumanApprovalDecisionRecord | None:
        allowed_fields = {
            "approval_decision_id",
            "approval_candidate_id",
            "execution_authorization_id",
        }

        if field_name not in allowed_fields:
            raise ValueError(
                "Unsupported lookup field"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE {field_name} = ?
                """,
                (
                    str(
                        value
                    ),
                ),
            ).fetchone()

        if row is None:
            return None

        return self._record_from_row(
            row
        )

    def get_by_approval_decision_id(
        self,
        approval_decision_id: str,
    ) -> AutonomousHumanApprovalDecisionRecord | None:
        return self._get_by_field(
            field_name="approval_decision_id",
            value=approval_decision_id,
        )

    def get_by_approval_candidate_id(
        self,
        approval_candidate_id: str,
    ) -> AutonomousHumanApprovalDecisionRecord | None:
        return self._get_by_field(
            field_name="approval_candidate_id",
            value=approval_candidate_id,
        )

    def get_by_execution_authorization_id(
        self,
        execution_authorization_id: str,
    ) -> AutonomousHumanApprovalDecisionRecord | None:
        return self._get_by_field(
            field_name="execution_authorization_id",
            value=execution_authorization_id,
        )

    def list_records(
        self,
        *,
        limit: int = 1000,
    ) -> list[
        AutonomousHumanApprovalDecisionRecord
    ]:
        resolved_limit = int(
            limit
        )

        if resolved_limit <= 0:
            raise ValueError(
                "limit must be greater than zero"
            )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                ORDER BY sequence_number ASC
                LIMIT ?
                """,
                (
                    resolved_limit,
                ),
            ).fetchall()

        return [
            self._record_from_row(
                row
            )
            for row in rows
        ]

    def count(
        self,
    ) -> int:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM {self.TABLE_NAME}
                """
            ).fetchone()

        return int(
            row[
                "count"
            ]
        )

    def verify_chain(
        self,
    ) -> bool:
        records = self.list_records(
            limit=1_000_000
        )

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        seen: dict[
            str,
            set[str],
        ] = {
            "approval_decision_id": set(),
            "decision_fingerprint": set(),
            "approval_candidate_id": set(),
            "candidate_record_hash": set(),
            "candidate_fingerprint": set(),
            "execution_authorization_id": set(),
            "record_hash": set(),
        }

        for record in records:
            if (
                record.sequence_number
                != expected_sequence
            ):
                return False

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                return False

            if not record.verify_hash():
                return False

            if record.candidate_audit_valid is not True:
                return False

            if record.human_decision not in {
                item.value
                for item in (
                    AutonomousControlledAuthorizationHumanDecisionType
                )
            }:
                return False

            payload_bindings = {
                "approval_decision_id":
                    record.approval_decision_id,
                "decision_fingerprint":
                    record.decision_fingerprint,
                "approval_candidate_id":
                    record.approval_candidate_id,
                "candidate_record_hash":
                    record.candidate_record_hash,
                "candidate_fingerprint":
                    record.candidate_fingerprint,
                "candidate_audit_id":
                    record.candidate_audit_id,
                "candidate_audit_valid":
                    record.candidate_audit_valid,
                "binding_id":
                    record.binding_id,
                "execution_authorization_id":
                    record.execution_authorization_id,
                "plan_id":
                    record.plan_id,
                "source_decision_id":
                    record.source_decision_id,
                "risk_class":
                    record.risk_class,
                "reviewer_id":
                    record.reviewer_id,
                "human_decision":
                    record.human_decision,
                "decision_reason":
                    record.decision_reason,
                "decided_at":
                    record.decided_at,
            }

            for (
                field_name,
                expected_value,
            ) in payload_bindings.items():
                if (
                    record.decision_payload.get(
                        field_name
                    )
                    != expected_value
                ):
                    return False

            for field_name in (
                "authorization_approved",
                "authorization_token_created",
                "approval_claim_created",
                "execution_lease_created",
                "execution_allowed",
                "can_execute",
            ):
                if (
                    record.decision_payload.get(
                        field_name
                    )
                    is not False
                ):
                    return False

            if (
                record.authorization_approved
                or record.authorization_token_created
                or record.approval_claim_created
                or record.execution_lease_created
                or record.execution_allowed
                or record.can_execute
            ):
                return False

            for field_name in seen:
                value = str(
                    getattr(
                        record,
                        field_name,
                    )
                )

                if value in seen[
                    field_name
                ]:
                    return False

                seen[
                    field_name
                ].add(
                    value
                )

            expected_sequence += 1
            expected_previous_hash = (
                record.record_hash
            )

        return True
