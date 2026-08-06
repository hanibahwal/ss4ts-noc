from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from app.models.autonomous_controlled_authorization_approval_candidate import (
    AutonomousControlledAuthorizationApprovalCandidate,
)


DEFAULT_AUTONOMOUS_APPROVAL_CANDIDATE_DATABASE = Path(
    "backend/data/"
    "autonomous-controlled-authorization-approval-candidates.db"
)


class AutonomousApprovalCandidateStoreError(
    RuntimeError
):
    """Base immutable approval candidate store error."""


class AutonomousApprovalCandidateDuplicate(
    AutonomousApprovalCandidateStoreError
):
    """Approval candidate protected identity already exists."""


class AutonomousApprovalCandidateIntegrityError(
    AutonomousApprovalCandidateStoreError
):
    """Approval candidate integrity verification failed."""


def canonical_approval_candidate_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def calculate_approval_candidate_record_hash(
    *,
    sequence_number: int,
    approval_candidate_id: str,
    candidate_fingerprint: str,
    binding_id: str,
    binding_record_hash: str,
    binding_fingerprint: str,
    binding_audit_id: str,
    binding_audit_valid: bool,
    authorization_intent_id: str,
    execution_authorization_id: str,
    plan_id: str,
    decision_id: str,
    risk_class: str,
    authorization_status: str,
    authorization_decision: str,
    requested_by: str,
    approval_reason: str,
    requested_at: str,
    expires_at: str,
    candidate_payload: dict[str, Any],
    stored_at: str,
    previous_record_hash: str | None,
) -> str:
    payload = {
        "sequence_number":
            sequence_number,
        "approval_candidate_id":
            approval_candidate_id,
        "candidate_fingerprint":
            candidate_fingerprint,
        "binding_id":
            binding_id,
        "binding_record_hash":
            binding_record_hash,
        "binding_fingerprint":
            binding_fingerprint,
        "binding_audit_id":
            binding_audit_id,
        "binding_audit_valid":
            binding_audit_valid,
        "authorization_intent_id":
            authorization_intent_id,
        "execution_authorization_id":
            execution_authorization_id,
        "plan_id":
            plan_id,
        "decision_id":
            decision_id,
        "risk_class":
            risk_class,
        "authorization_status":
            authorization_status,
        "authorization_decision":
            authorization_decision,
        "requested_by":
            requested_by,
        "approval_reason":
            approval_reason,
        "requested_at":
            requested_at,
        "expires_at":
            expires_at,
        "candidate_payload":
            candidate_payload,
        "stored_at":
            stored_at,
        "previous_record_hash":
            previous_record_hash,
    }

    return hashlib.sha256(
        canonical_approval_candidate_json(
            payload
        ).encode("utf-8")
    ).hexdigest()


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousApprovalCandidateRecord:
    sequence_number: int

    approval_candidate_id: str
    candidate_fingerprint: str

    binding_id: str
    binding_record_hash: str
    binding_fingerprint: str
    binding_audit_id: str
    binding_audit_valid: bool

    authorization_intent_id: str
    execution_authorization_id: str

    plan_id: str
    decision_id: str
    risk_class: str

    authorization_status: str
    authorization_decision: str

    requested_by: str
    approval_reason: str
    requested_at: str
    expires_at: str

    candidate_payload: dict[str, Any]

    stored_at: str
    previous_record_hash: str | None
    record_hash: str

    @property
    def approval_candidate_created(
        self,
    ) -> bool:
        return True

    @property
    def authorization_approved(
        self,
    ) -> bool:
        return False

    @property
    def approval_claim_created(
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
        expected = calculate_approval_candidate_record_hash(
            sequence_number=self.sequence_number,
            approval_candidate_id=(
                self.approval_candidate_id
            ),
            candidate_fingerprint=(
                self.candidate_fingerprint
            ),
            binding_id=self.binding_id,
            binding_record_hash=(
                self.binding_record_hash
            ),
            binding_fingerprint=(
                self.binding_fingerprint
            ),
            binding_audit_id=(
                self.binding_audit_id
            ),
            binding_audit_valid=(
                self.binding_audit_valid
            ),
            authorization_intent_id=(
                self.authorization_intent_id
            ),
            execution_authorization_id=(
                self.execution_authorization_id
            ),
            plan_id=self.plan_id,
            decision_id=self.decision_id,
            risk_class=self.risk_class,
            authorization_status=(
                self.authorization_status
            ),
            authorization_decision=(
                self.authorization_decision
            ),
            requested_by=self.requested_by,
            approval_reason=self.approval_reason,
            requested_at=self.requested_at,
            expires_at=self.expires_at,
            candidate_payload=(
                self.candidate_payload
            ),
            stored_at=self.stored_at,
            previous_record_hash=(
                self.previous_record_hash
            ),
        )

        return expected == self.record_hash

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "sequence_number":
                self.sequence_number,
            "approval_candidate_id":
                self.approval_candidate_id,
            "candidate_fingerprint":
                self.candidate_fingerprint,
            "binding_id":
                self.binding_id,
            "binding_record_hash":
                self.binding_record_hash,
            "binding_fingerprint":
                self.binding_fingerprint,
            "binding_audit_id":
                self.binding_audit_id,
            "binding_audit_valid":
                self.binding_audit_valid,
            "authorization_intent_id":
                self.authorization_intent_id,
            "execution_authorization_id":
                self.execution_authorization_id,
            "plan_id":
                self.plan_id,
            "decision_id":
                self.decision_id,
            "risk_class":
                self.risk_class,
            "authorization_status":
                self.authorization_status,
            "authorization_decision":
                self.authorization_decision,
            "requested_by":
                self.requested_by,
            "approval_reason":
                self.approval_reason,
            "requested_at":
                self.requested_at,
            "expires_at":
                self.expires_at,
            "candidate_payload":
                dict(
                    self.candidate_payload
                ),
            "stored_at":
                self.stored_at,
            "previous_record_hash":
                self.previous_record_hash,
            "record_hash":
                self.record_hash,
            "approval_candidate_created":
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
            "can_execute":
                False,
            "safety": {
                "immutable_record":
                    True,
                "append_only":
                    True,
                "approval_candidate_only":
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


class AutonomousControlledAuthorizationApprovalCandidateStore:
    """
    Immutable append-only approval candidate ledger.

    This store records approval candidates only. It never approves
    an authorization, creates an approval claim, acquires a lease,
    consumes an authorization, or executes an operation.
    """

    TABLE_NAME = (
        "autonomous_controlled_authorization_"
        "approval_candidate_records"
    )

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTONOMOUS_APPROVAL_CANDIDATE_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Approval candidate database path "
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

                    approval_candidate_id
                        TEXT NOT NULL UNIQUE,

                    candidate_fingerprint
                        TEXT NOT NULL UNIQUE,

                    binding_id
                        TEXT NOT NULL UNIQUE,

                    binding_record_hash
                        TEXT NOT NULL UNIQUE,

                    binding_fingerprint
                        TEXT NOT NULL UNIQUE,

                    binding_audit_id
                        TEXT NOT NULL,

                    binding_audit_valid
                        INTEGER NOT NULL,

                    authorization_intent_id
                        TEXT NOT NULL UNIQUE,

                    execution_authorization_id
                        TEXT NOT NULL UNIQUE,

                    plan_id
                        TEXT NOT NULL,

                    decision_id
                        TEXT NOT NULL,

                    risk_class
                        TEXT NOT NULL,

                    authorization_status
                        TEXT NOT NULL,

                    authorization_decision
                        TEXT NOT NULL,

                    requested_by
                        TEXT NOT NULL,

                    approval_reason
                        TEXT NOT NULL,

                    requested_at
                        TEXT NOT NULL,

                    expires_at
                        TEXT NOT NULL,

                    candidate_payload
                        TEXT NOT NULL,

                    stored_at
                        TEXT NOT NULL,

                    previous_record_hash
                        TEXT,

                    record_hash
                        TEXT NOT NULL UNIQUE
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_autonomous_approval_candidate_authorization
                ON {self.TABLE_NAME}
                (
                    execution_authorization_id
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_candidate(
        candidate: (
            AutonomousControlledAuthorizationApprovalCandidate
        ),
        *,
        stored_at: datetime,
    ) -> None:
        if not isinstance(
            candidate,
            AutonomousControlledAuthorizationApprovalCandidate,
        ):
            raise TypeError(
                "candidate must be an "
                "AutonomousControlledAuthorizationApprovalCandidate"
            )

        if (
            candidate.calculate_fingerprint()
            != candidate.candidate_fingerprint
        ):
            raise AutonomousApprovalCandidateIntegrityError(
                "Approval candidate fingerprint mismatch"
            )

        if candidate.binding_audit_valid is not True:
            raise AutonomousApprovalCandidateIntegrityError(
                "Approval candidate binding audit is invalid"
            )

        if (
            candidate.authorization_status
            != "pending"
        ):
            raise AutonomousApprovalCandidateIntegrityError(
                "Approval candidate authorization "
                "status must be pending"
            )

        if (
            candidate.authorization_decision
            != "require_approval"
        ):
            raise AutonomousApprovalCandidateIntegrityError(
                "Approval candidate must require approval"
            )

        if candidate.expires_at <= stored_at:
            raise AutonomousApprovalCandidateIntegrityError(
                "Expired approval candidate cannot be stored"
            )

        if candidate.authorization_approved:
            raise AutonomousApprovalCandidateIntegrityError(
                "Approved candidate cannot be stored"
            )

        if candidate.approval_claim_created:
            raise AutonomousApprovalCandidateIntegrityError(
                "Candidate containing approval claim "
                "cannot be stored"
            )

        if (
            candidate.execution_allowed
            or candidate.can_execute
        ):
            raise AutonomousApprovalCandidateIntegrityError(
                "Executable candidate cannot be stored"
            )

        payload = candidate.to_dict()

        for field_name in (
            "authorization_approved",
            "authorization_token_created",
            "approval_claim_created",
            "execution_lease_created",
            "execution_allowed",
            "can_execute",
        ):
            if payload.get(
                field_name
            ) is not False:
                raise AutonomousApprovalCandidateIntegrityError(
                    "Candidate contains unsafe claim: "
                    f"{field_name}"
                )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> AutonomousApprovalCandidateRecord:
        try:
            payload = json.loads(
                row["candidate_payload"]
            )
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AutonomousApprovalCandidateIntegrityError(
                "Stored candidate payload is invalid"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise AutonomousApprovalCandidateIntegrityError(
                "Stored candidate payload must be an object"
            )

        return AutonomousApprovalCandidateRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            approval_candidate_id=str(
                row["approval_candidate_id"]
            ),
            candidate_fingerprint=str(
                row["candidate_fingerprint"]
            ),
            binding_id=str(
                row["binding_id"]
            ),
            binding_record_hash=str(
                row["binding_record_hash"]
            ),
            binding_fingerprint=str(
                row["binding_fingerprint"]
            ),
            binding_audit_id=str(
                row["binding_audit_id"]
            ),
            binding_audit_valid=bool(
                row["binding_audit_valid"]
            ),
            authorization_intent_id=str(
                row["authorization_intent_id"]
            ),
            execution_authorization_id=str(
                row["execution_authorization_id"]
            ),
            plan_id=str(
                row["plan_id"]
            ),
            decision_id=str(
                row["decision_id"]
            ),
            risk_class=str(
                row["risk_class"]
            ),
            authorization_status=str(
                row["authorization_status"]
            ),
            authorization_decision=str(
                row["authorization_decision"]
            ),
            requested_by=str(
                row["requested_by"]
            ),
            approval_reason=str(
                row["approval_reason"]
            ),
            requested_at=str(
                row["requested_at"]
            ),
            expires_at=str(
                row["expires_at"]
            ),
            candidate_payload=payload,
            stored_at=str(
                row["stored_at"]
            ),
            previous_record_hash=(
                str(
                    row["previous_record_hash"]
                )
                if row["previous_record_hash"]
                is not None
                else None
            ),
            record_hash=str(
                row["record_hash"]
            ),
        )

    def append(
        self,
        *,
        candidate: (
            AutonomousControlledAuthorizationApprovalCandidate
        ),
        stored_at: datetime | None = None,
    ) -> AutonomousApprovalCandidateRecord:
        resolved_stored_at = (
            stored_at
            or datetime.now(
                timezone.utc
            )
        )

        if not isinstance(
            resolved_stored_at,
            datetime,
        ):
            raise TypeError(
                "stored_at must be a datetime"
            )

        if (
            resolved_stored_at.tzinfo is None
            or resolved_stored_at.utcoffset() is None
        ):
            raise ValueError(
                "stored_at must be timezone-aware"
            )

        resolved_stored_at = (
            resolved_stored_at
            .astimezone(
                timezone.utc
            )
        )

        self._validate_candidate(
            candidate,
            stored_at=resolved_stored_at,
        )

        stored_at_text = (
            resolved_stored_at.isoformat()
        )

        candidate_payload = (
            candidate.to_dict()
        )

        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            latest = connection.execute(
                f"""
                SELECT
                    sequence_number,
                    record_hash
                FROM {self.TABLE_NAME}
                ORDER BY sequence_number DESC
                LIMIT 1
                """
            ).fetchone()

            sequence_number = (
                int(
                    latest["sequence_number"]
                ) + 1
                if latest is not None
                else 1
            )

            previous_record_hash = (
                str(
                    latest["record_hash"]
                )
                if latest is not None
                else None
            )

            record_hash = (
                calculate_approval_candidate_record_hash(
                    sequence_number=sequence_number,
                    approval_candidate_id=(
                        candidate.approval_candidate_id
                    ),
                    candidate_fingerprint=(
                        candidate.candidate_fingerprint
                    ),
                    binding_id=candidate.binding_id,
                    binding_record_hash=(
                        candidate.binding_record_hash
                    ),
                    binding_fingerprint=(
                        candidate.binding_fingerprint
                    ),
                    binding_audit_id=(
                        candidate.binding_audit_id
                    ),
                    binding_audit_valid=(
                        candidate.binding_audit_valid
                    ),
                    authorization_intent_id=(
                        candidate.authorization_intent_id
                    ),
                    execution_authorization_id=(
                        candidate.execution_authorization_id
                    ),
                    plan_id=candidate.plan_id,
                    decision_id=candidate.decision_id,
                    risk_class=candidate.risk_class,
                    authorization_status=(
                        candidate.authorization_status
                    ),
                    authorization_decision=(
                        candidate.authorization_decision
                    ),
                    requested_by=(
                        candidate.requested_by
                    ),
                    approval_reason=(
                        candidate.approval_reason
                    ),
                    requested_at=(
                        candidate.requested_at.isoformat()
                    ),
                    expires_at=(
                        candidate.expires_at.isoformat()
                    ),
                    candidate_payload=(
                        candidate_payload
                    ),
                    stored_at=stored_at_text,
                    previous_record_hash=(
                        previous_record_hash
                    ),
                )
            )

            try:
                connection.execute(
                    f"""
                    INSERT INTO {self.TABLE_NAME}
                    (
                        sequence_number,
                        approval_candidate_id,
                        candidate_fingerprint,
                        binding_id,
                        binding_record_hash,
                        binding_fingerprint,
                        binding_audit_id,
                        binding_audit_valid,
                        authorization_intent_id,
                        execution_authorization_id,
                        plan_id,
                        decision_id,
                        risk_class,
                        authorization_status,
                        authorization_decision,
                        requested_by,
                        approval_reason,
                        requested_at,
                        expires_at,
                        candidate_payload,
                        stored_at,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        sequence_number,
                        candidate.approval_candidate_id,
                        candidate.candidate_fingerprint,
                        candidate.binding_id,
                        candidate.binding_record_hash,
                        candidate.binding_fingerprint,
                        candidate.binding_audit_id,
                        int(
                            candidate.binding_audit_valid
                        ),
                        candidate.authorization_intent_id,
                        candidate.execution_authorization_id,
                        candidate.plan_id,
                        candidate.decision_id,
                        candidate.risk_class,
                        candidate.authorization_status,
                        candidate.authorization_decision,
                        candidate.requested_by,
                        candidate.approval_reason,
                        candidate.requested_at.isoformat(),
                        candidate.expires_at.isoformat(),
                        canonical_approval_candidate_json(
                            candidate_payload
                        ),
                        stored_at_text,
                        previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                connection.rollback()

                raise AutonomousApprovalCandidateDuplicate(
                    "Approval candidate protected "
                    "identity already exists"
                ) from exc

            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE sequence_number = ?
                """,
                (
                    sequence_number,
                ),
            ).fetchone()

        if row is None:
            raise AutonomousApprovalCandidateStoreError(
                "Stored approval candidate "
                "could not be read"
            )

        record = self._record_from_row(
            row
        )

        if not record.verify_hash():
            raise AutonomousApprovalCandidateIntegrityError(
                "Stored approval candidate hash "
                "is invalid"
            )

        return record

    def _get_by(
        self,
        column: str,
        value: Any,
    ) -> AutonomousApprovalCandidateRecord | None:
        allowed_columns = {
            "sequence_number",
            "approval_candidate_id",
            "binding_id",
            "execution_authorization_id",
        }

        if column not in allowed_columns:
            raise ValueError(
                "Unsupported approval candidate lookup"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE {column} = ?
                """,
                (
                    value,
                ),
            ).fetchone()

        return (
            self._record_from_row(
                row
            )
            if row is not None
            else None
        )

    def get(
        self,
        sequence_number: int,
    ) -> AutonomousApprovalCandidateRecord | None:
        return self._get_by(
            "sequence_number",
            int(
                sequence_number
            ),
        )

    def get_by_candidate_id(
        self,
        approval_candidate_id: str,
    ) -> AutonomousApprovalCandidateRecord | None:
        return self._get_by(
            "approval_candidate_id",
            str(
                approval_candidate_id
            ).strip(),
        )

    def get_by_binding_id(
        self,
        binding_id: str,
    ) -> AutonomousApprovalCandidateRecord | None:
        return self._get_by(
            "binding_id",
            str(
                binding_id
            ).strip(),
        )

    def get_by_execution_authorization_id(
        self,
        execution_authorization_id: str,
    ) -> AutonomousApprovalCandidateRecord | None:
        return self._get_by(
            "execution_authorization_id",
            str(
                execution_authorization_id
            ).strip(),
        )

    def list_records(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[
        AutonomousApprovalCandidateRecord
    ]:
        normalized_limit = max(
            1,
            min(
                int(
                    limit
                ),
                1000,
            ),
        )

        normalized_offset = max(
            0,
            int(
                offset
            ),
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
                OFFSET ?
                """,
                (
                    normalized_limit,
                    normalized_offset,
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
                SELECT COUNT(*) AS record_count
                FROM {self.TABLE_NAME}
                """
            ).fetchone()

        return int(
            row["record_count"]
            if row is not None
            else 0
        )

    def verify_chain(
        self,
    ) -> bool:
        records = self.list_records(
            limit=1000
        )

        expected_sequence = 1
        previous_hash: str | None = None

        for record in records:
            if (
                record.sequence_number
                != expected_sequence
            ):
                return False

            if (
                record.previous_record_hash
                != previous_hash
            ):
                return False

            if not record.verify_hash():
                return False

            payload = record.candidate_payload

            bindings = {
                "approval_candidate_id":
                    record.approval_candidate_id,
                "candidate_fingerprint":
                    record.candidate_fingerprint,
                "binding_id":
                    record.binding_id,
                "binding_record_hash":
                    record.binding_record_hash,
                "binding_fingerprint":
                    record.binding_fingerprint,
                "binding_audit_id":
                    record.binding_audit_id,
                "binding_audit_valid":
                    record.binding_audit_valid,
                "authorization_intent_id":
                    record.authorization_intent_id,
                "execution_authorization_id":
                    record.execution_authorization_id,
                "plan_id":
                    record.plan_id,
                "decision_id":
                    record.decision_id,
                "risk_class":
                    record.risk_class,
                "authorization_status":
                    record.authorization_status,
                "authorization_decision":
                    record.authorization_decision,
                "requested_by":
                    record.requested_by,
                "approval_reason":
                    record.approval_reason,
                "requested_at":
                    record.requested_at,
                "expires_at":
                    record.expires_at,
            }

            if any(
                payload.get(
                    field_name
                ) != field_value
                for (
                    field_name,
                    field_value,
                ) in bindings.items()
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
                if payload.get(
                    field_name
                ) is not False:
                    return False

            previous_hash = (
                record.record_hash
            )
            expected_sequence += 1

        return True
