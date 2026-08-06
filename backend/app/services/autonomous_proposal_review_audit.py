from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.models.autonomous_proposal_review_decision import (
    AutonomousHumanReviewDecisionType,
)
from app.services.autonomous_proposal_review_store import (
    GENESIS_RECORD_HASH,
    AutonomousProposalReviewRecord,
    AutonomousProposalReviewStore,
    _record_hash,
)


SERVICE_NAME = (
    "SS4TS Autonomous Human Review Store "
    "Audit Verification"
)

SERVICE_VERSION = "1.0.0"


def _utc_now_text() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _decision_fingerprint_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "review_decision_id":
            payload.get(
                "review_decision_id"
            ),
        "queue_item_id":
            payload.get(
                "queue_item_id"
            ),
        "proposal_id":
            payload.get(
                "proposal_id"
            ),
        "record_hash":
            payload.get(
                "record_hash"
            ),
        "reviewer_id":
            payload.get(
                "reviewer_id"
            ),
        "reviewer_name":
            payload.get(
                "reviewer_name"
            ),
        "decision":
            payload.get(
                "decision"
            ),
        "reason":
            payload.get(
                "reason"
            ),
        "reviewed_at":
            payload.get(
                "reviewed_at"
            ),
        "proposal_snapshot":
            payload.get(
                "proposal_snapshot"
            ),
        "queue_priority_score":
            payload.get(
                "queue_priority_score"
            ),
        "audit_id":
            payload.get(
                "audit_id"
            ),
        "audit_valid":
            payload.get(
                "audit_valid"
            ),
    }


def _calculate_decision_fingerprint(
    payload: dict[str, Any],
) -> str:
    return hashlib.sha256(
        _canonical_json(
            _decision_fingerprint_payload(
                payload
            )
        ).encode("utf-8")
    ).hexdigest()


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousProposalReviewAuditReport:
    audit_id: str
    generated_at: str
    database_path: str

    record_count: int
    verified_record_count: int

    first_sequence_number: int | None
    last_sequence_number: int | None

    genesis_valid: bool
    sequence_continuous: bool
    hash_chain_valid: bool
    record_hashes_valid: bool
    decision_fingerprints_valid: bool
    payload_bindings_valid: bool
    decision_types_valid: bool

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def audit_valid(
        self,
    ) -> bool:
        return (
            self.genesis_valid
            and self.sequence_continuous
            and self.hash_chain_valid
            and self.record_hashes_valid
            and self.decision_fingerprints_valid
            and self.payload_bindings_valid
            and self.decision_types_valid
            and not self.errors
        )

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "audit_id":
                self.audit_id,
            "generated_at":
                self.generated_at,
            "database_path":
                self.database_path,
            "audit_valid":
                self.audit_valid,
            "record_count":
                self.record_count,
            "verified_record_count":
                self.verified_record_count,
            "first_sequence_number":
                self.first_sequence_number,
            "last_sequence_number":
                self.last_sequence_number,
            "genesis_valid":
                self.genesis_valid,
            "sequence_continuous":
                self.sequence_continuous,
            "hash_chain_valid":
                self.hash_chain_valid,
            "record_hashes_valid":
                self.record_hashes_valid,
            "decision_fingerprints_valid":
                (
                    self
                    .decision_fingerprints_valid
                ),
            "payload_bindings_valid":
                self.payload_bindings_valid,
            "decision_types_valid":
                self.decision_types_valid,
            "errors":
                list(
                    self.errors
                ),
            "warnings":
                list(
                    self.warnings
                ),
            "can_execute":
                False,
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "safety": {
                "read_only_audit":
                    True,
                "database_write_performed":
                    False,
                "review_decision_created":
                    False,
                "review_decision_modified":
                    False,
                "proposal_ledger_modified":
                    False,
                "approval_claim_created":
                    False,
                "authorization_created":
                    False,
                "execution_approved":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        }


class AutonomousProposalReviewAuditVerifier:
    """
    Perform a read-only integrity audit of the immutable human
    review decision ledger.

    The verifier does not use the store's normal writable SQLite
    connection and does not create, modify, authorize, claim, or
    execute any decision.
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database_path = Path(
            database_path
        )

    def _connect_read_only(
        self,
    ) -> sqlite3.Connection:
        uri = (
            f"{self.database_path.resolve().as_uri()}"
            "?mode=ro"
        )

        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=30,
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA query_only = ON"
        )

        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        return connection

    @staticmethod
    def _decode_payload(
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        try:
            payload = json.loads(
                row["decision_payload"]
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "decision_payload contains "
                "invalid JSON"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "decision_payload must contain "
                "a JSON object"
            )

        return payload

    @classmethod
    def _record_from_row(
        cls,
        row: sqlite3.Row,
    ) -> AutonomousProposalReviewRecord:
        return AutonomousProposalReviewRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            review_decision_id=str(
                row["review_decision_id"]
            ),
            decision_fingerprint=str(
                row["decision_fingerprint"]
            ),
            queue_item_id=str(
                row["queue_item_id"]
            ),
            proposal_id=str(
                row["proposal_id"]
            ),
            proposal_record_hash=str(
                row["proposal_record_hash"]
            ),
            reviewer_id=str(
                row["reviewer_id"]
            ),
            decision=str(
                row["decision"]
            ),
            decision_payload=(
                cls._decode_payload(
                    row
                )
            ),
            created_at=str(
                row["created_at"]
            ),
            previous_record_hash=str(
                row["previous_record_hash"]
            ),
            record_hash=str(
                row["record_hash"]
            ),
        )

    def _failed_report(
        self,
        *errors: str,
    ) -> AutonomousProposalReviewAuditReport:
        return AutonomousProposalReviewAuditReport(
            audit_id=(
                f"autonomous-review-audit:"
                f"{uuid4()}"
            ),
            generated_at=_utc_now_text(),
            database_path=str(
                self.database_path
            ),
            record_count=0,
            verified_record_count=0,
            first_sequence_number=None,
            last_sequence_number=None,
            genesis_valid=False,
            sequence_continuous=False,
            hash_chain_valid=False,
            record_hashes_valid=False,
            decision_fingerprints_valid=False,
            payload_bindings_valid=False,
            decision_types_valid=False,
            errors=tuple(
                errors
            ),
            warnings=(),
        )

    def verify(
        self,
    ) -> AutonomousProposalReviewAuditReport:
        if not self.database_path.exists():
            return self._failed_report(
                "Autonomous review database "
                "does not exist"
            )

        try:
            with closing(
                self._connect_read_only()
            ) as connection:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM
                        autonomous_proposal_review_records
                    ORDER BY sequence_number ASC
                    """
                ).fetchall()

        except sqlite3.Error as exc:
            return self._failed_report(
                "Unable to read autonomous "
                f"review database: {exc}"
            )

        errors: list[str] = []
        warnings: list[str] = []

        genesis_valid = True
        sequence_continuous = True
        hash_chain_valid = True
        record_hashes_valid = True
        decision_fingerprints_valid = True
        payload_bindings_valid = True
        decision_types_valid = True

        records: list[
            AutonomousProposalReviewRecord
        ] = []

        verified_record_count = 0

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        supported_decisions = {
            item.value
            for item in (
                AutonomousHumanReviewDecisionType
            )
        }

        for row in rows:
            try:
                record = (
                    self._record_from_row(
                        row
                    )
                )

            except (
                TypeError,
                ValueError,
                KeyError,
            ) as exc:
                payload_bindings_valid = False
                record_hashes_valid = False
                decision_fingerprints_valid = False

                sequence = row[
                    "sequence_number"
                ]

                errors.append(
                    "Invalid review record at "
                    f"sequence {sequence}: {exc}"
                )

                continue

            records.append(
                record
            )

            if (
                record.sequence_number
                != expected_sequence
            ):
                sequence_continuous = False

                errors.append(
                    "Review sequence is not "
                    "continuous at sequence "
                    f"{record.sequence_number}; "
                    f"expected {expected_sequence}"
                )

            if (
                record.sequence_number == 1
                and record.previous_record_hash
                != GENESIS_RECORD_HASH
            ):
                genesis_valid = False

                errors.append(
                    "Review genesis hash is invalid"
                )

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                hash_chain_valid = False

                errors.append(
                    "Review hash chain is broken "
                    "at sequence "
                    f"{record.sequence_number}"
                )

            expected_record_hash = _record_hash(
                sequence_number=(
                    record.sequence_number
                ),
                review_decision_id=(
                    record.review_decision_id
                ),
                decision_fingerprint=(
                    record.decision_fingerprint
                ),
                queue_item_id=(
                    record.queue_item_id
                ),
                proposal_id=(
                    record.proposal_id
                ),
                proposal_record_hash=(
                    record.proposal_record_hash
                ),
                reviewer_id=(
                    record.reviewer_id
                ),
                decision=(
                    record.decision
                ),
                decision_payload=(
                    record.decision_payload
                ),
                created_at=(
                    record.created_at
                ),
                previous_record_hash=(
                    record.previous_record_hash
                ),
            )

            if (
                expected_record_hash
                != record.record_hash
            ):
                record_hashes_valid = False

                errors.append(
                    "Review record hash mismatch "
                    "at sequence "
                    f"{record.sequence_number}"
                )

            payload = (
                record.decision_payload
            )

            calculated_fingerprint = (
                _calculate_decision_fingerprint(
                    payload
                )
            )

            payload_fingerprint = str(
                payload.get(
                    "decision_fingerprint",
                    "",
                )
            )

            if (
                payload_fingerprint
                != record.decision_fingerprint
                or calculated_fingerprint
                != record.decision_fingerprint
            ):
                decision_fingerprints_valid = False

                errors.append(
                    "Review decision fingerprint "
                    "mismatch at sequence "
                    f"{record.sequence_number}"
                )

            bindings = {
                "review_decision_id": (
                    record.review_decision_id
                ),
                "queue_item_id": (
                    record.queue_item_id
                ),
                "proposal_id": (
                    record.proposal_id
                ),
                "record_hash": (
                    record.proposal_record_hash
                ),
                "reviewer_id": (
                    record.reviewer_id
                ),
                "decision": (
                    record.decision
                ),
            }

            for field, expected_value in (
                bindings.items()
            ):
                actual_value = payload.get(
                    field
                )

                if (
                    actual_value
                    != expected_value
                ):
                    payload_bindings_valid = False

                    errors.append(
                        "Review payload binding "
                        f"mismatch for {field} "
                        "at sequence "
                        f"{record.sequence_number}"
                    )

            if (
                payload.get(
                    "audit_valid"
                )
                is not True
            ):
                payload_bindings_valid = False

                errors.append(
                    "Review payload audit_valid "
                    "is not true at sequence "
                    f"{record.sequence_number}"
                )

            if (
                payload.get(
                    "authorization_created"
                )
                is not False
            ):
                payload_bindings_valid = False

                errors.append(
                    "Review payload unexpectedly "
                    "contains authorization at "
                    "sequence "
                    f"{record.sequence_number}"
                )

            if (
                payload.get(
                    "can_execute"
                )
                is not False
            ):
                payload_bindings_valid = False

                errors.append(
                    "Review payload unexpectedly "
                    "allows execution at sequence "
                    f"{record.sequence_number}"
                )

            if (
                record.decision
                not in supported_decisions
            ):
                decision_types_valid = False

                errors.append(
                    "Unsupported review decision "
                    "type at sequence "
                    f"{record.sequence_number}"
                )

            else:
                verified_record_count += 1

            expected_sequence = (
                record.sequence_number
                + 1
            )

            expected_previous_hash = (
                record.record_hash
            )

        if not rows:
            warnings.append(
                "Autonomous review decision "
                "ledger is empty"
            )

        if rows and not records:
            genesis_valid = False
            sequence_continuous = False
            hash_chain_valid = False

        first_sequence = (
            records[0].sequence_number
            if records
            else None
        )

        last_sequence = (
            records[-1].sequence_number
            if records
            else None
        )

        return AutonomousProposalReviewAuditReport(
            audit_id=(
                f"autonomous-review-audit:"
                f"{uuid4()}"
            ),
            generated_at=_utc_now_text(),
            database_path=str(
                self.database_path
            ),
            record_count=len(
                rows
            ),
            verified_record_count=(
                verified_record_count
            ),
            first_sequence_number=(
                first_sequence
            ),
            last_sequence_number=(
                last_sequence
            ),
            genesis_valid=genesis_valid,
            sequence_continuous=(
                sequence_continuous
            ),
            hash_chain_valid=(
                hash_chain_valid
            ),
            record_hashes_valid=(
                record_hashes_valid
            ),
            decision_fingerprints_valid=(
                decision_fingerprints_valid
            ),
            payload_bindings_valid=(
                payload_bindings_valid
            ),
            decision_types_valid=(
                decision_types_valid
            ),
            errors=tuple(
                dict.fromkeys(
                    errors
                )
            ),
            warnings=tuple(
                dict.fromkeys(
                    warnings
                )
            ),
        )


def verify_autonomous_proposal_review_store(
    store: AutonomousProposalReviewStore,
) -> AutonomousProposalReviewAuditReport:
    if not isinstance(
        store,
        AutonomousProposalReviewStore,
    ):
        raise TypeError(
            "store must be an "
            "AutonomousProposalReviewStore"
        )

    return AutonomousProposalReviewAuditVerifier(
        store.database_path
    ).verify()
