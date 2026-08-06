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

from app.services.autonomous_authorization_candidate_store import (
    GENESIS_RECORD_HASH,
    AutonomousAuthorizationCandidateRecord,
    AutonomousAuthorizationCandidateStore,
    _record_hash,
)


SERVICE_NAME = (
    "SS4TS Autonomous Authorization Candidate "
    "Store Audit Verification"
)

SERVICE_VERSION = "1.0.0"

TABLE_NAME = (
    "autonomous_authorization_candidate_records"
)

APPROVED_DECISION = (
    "approved_for_authorization_review"
)


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


def _candidate_fingerprint_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "authorization_candidate_id":
            payload.get(
                "authorization_candidate_id"
            ),
        "review_decision_id":
            payload.get(
                "review_decision_id"
            ),
        "review_record_hash":
            payload.get(
                "review_record_hash"
            ),
        "decision_fingerprint":
            payload.get(
                "decision_fingerprint"
            ),
        "proposal_id":
            payload.get(
                "proposal_id"
            ),
        "proposal_record_hash":
            payload.get(
                "proposal_record_hash"
            ),
        "queue_item_id":
            payload.get(
                "queue_item_id"
            ),
        "reviewer_id":
            payload.get(
                "reviewer_id"
            ),
        "human_decision":
            payload.get(
                "human_decision"
            ),
        "review_audit_id":
            payload.get(
                "review_audit_id"
            ),
        "review_audit_valid":
            payload.get(
                "review_audit_valid"
            ),
        "created_at":
            payload.get(
                "created_at"
            ),
    }


def _calculate_candidate_fingerprint(
    payload: dict[str, Any],
) -> str:
    return hashlib.sha256(
        _canonical_json(
            _candidate_fingerprint_payload(
                payload
            )
        ).encode("utf-8")
    ).hexdigest()


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousAuthorizationCandidateAuditReport:
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
    candidate_fingerprints_valid: bool
    payload_bindings_valid: bool
    candidate_eligibility_valid: bool
    safety_contracts_valid: bool

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
            and self.candidate_fingerprints_valid
            and self.payload_bindings_valid
            and self.candidate_eligibility_valid
            and self.safety_contracts_valid
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
            "candidate_fingerprints_valid":
                self.candidate_fingerprints_valid,
            "payload_bindings_valid":
                self.payload_bindings_valid,
            "candidate_eligibility_valid":
                self.candidate_eligibility_valid,
            "safety_contracts_valid":
                self.safety_contracts_valid,
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
                "candidate_created":
                    False,
                "candidate_modified":
                    False,
                "authorization_created":
                    False,
                "authorization_token_created":
                    False,
                "approval_claim_created":
                    False,
                "execution_lease_created":
                    False,
                "execution_approved":
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


class AutonomousAuthorizationCandidateAuditVerifier:
    """
    Read-only verification of the immutable authorization
    candidate ledger.

    This verifier does not use the writable store connection and
    does not create or modify candidates, authorizations, tokens,
    claims, leases, simulations, or executions.
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
                row["candidate_payload"]
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "candidate_payload contains "
                "invalid JSON"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "candidate_payload must be "
                "a JSON object"
            )

        return payload

    @classmethod
    def _record_from_row(
        cls,
        row: sqlite3.Row,
    ) -> AutonomousAuthorizationCandidateRecord:
        return AutonomousAuthorizationCandidateRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            authorization_candidate_id=str(
                row["authorization_candidate_id"]
            ),
            candidate_fingerprint=str(
                row["candidate_fingerprint"]
            ),
            review_decision_id=str(
                row["review_decision_id"]
            ),
            review_record_hash=str(
                row["review_record_hash"]
            ),
            decision_fingerprint=str(
                row["decision_fingerprint"]
            ),
            proposal_id=str(
                row["proposal_id"]
            ),
            proposal_record_hash=str(
                row["proposal_record_hash"]
            ),
            queue_item_id=str(
                row["queue_item_id"]
            ),
            reviewer_id=str(
                row["reviewer_id"]
            ),
            human_decision=str(
                row["human_decision"]
            ),
            review_audit_id=str(
                row["review_audit_id"]
            ),
            candidate_payload=(
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

    def _invalid_report(
        self,
        message: str,
    ) -> AutonomousAuthorizationCandidateAuditReport:
        return AutonomousAuthorizationCandidateAuditReport(
            audit_id=(
                "autonomous-authorization-"
                f"candidate-audit:{uuid4()}"
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
            candidate_fingerprints_valid=False,
            payload_bindings_valid=False,
            candidate_eligibility_valid=False,
            safety_contracts_valid=False,
            errors=(
                message,
            ),
            warnings=(),
        )

    def verify(
        self,
    ) -> AutonomousAuthorizationCandidateAuditReport:
        if not self.database_path.exists():
            return self._invalid_report(
                "Authorization candidate database "
                "does not exist"
            )

        try:
            with closing(
                self._connect_read_only()
            ) as connection:
                table = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name = ?
                    """,
                    (
                        TABLE_NAME,
                    ),
                ).fetchone()

                if table is None:
                    return self._invalid_report(
                        "Authorization candidate ledger "
                        "table does not exist"
                    )

                rows = connection.execute(
                    f"""
                    SELECT *
                    FROM {TABLE_NAME}
                    ORDER BY sequence_number ASC
                    """
                ).fetchall()

        except sqlite3.Error as exc:
            return self._invalid_report(
                "Authorization candidate database "
                f"could not be read: {exc}"
            )

        errors: list[str] = []
        warnings: list[str] = []

        records: list[
            AutonomousAuthorizationCandidateRecord
        ] = []

        genesis_valid = True
        sequence_continuous = True
        hash_chain_valid = True
        record_hashes_valid = True
        candidate_fingerprints_valid = True
        payload_bindings_valid = True
        candidate_eligibility_valid = True
        safety_contracts_valid = True

        verified_record_count = 0

        for row in rows:
            try:
                records.append(
                    self._record_from_row(
                        row
                    )
                )

            except (
                TypeError,
                ValueError,
                KeyError,
            ) as exc:
                record_hashes_valid = False
                candidate_fingerprints_valid = False
                payload_bindings_valid = False
                candidate_eligibility_valid = False
                safety_contracts_valid = False

                errors.append(
                    "Unable to decode candidate "
                    "record at sequence "
                    f"{row['sequence_number']}: {exc}"
                )

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        for index, record in enumerate(
            records
        ):
            sequence = (
                record.sequence_number
            )

            record_valid = True

            if sequence != expected_sequence:
                sequence_continuous = False
                record_valid = False

                errors.append(
                    "Authorization candidate sequence "
                    "is not continuous at sequence "
                    f"{sequence}; expected "
                    f"{expected_sequence}"
                )

            if index == 0:
                if (
                    sequence != 1
                    or record.previous_record_hash
                    != GENESIS_RECORD_HASH
                ):
                    genesis_valid = False
                    record_valid = False

                    errors.append(
                        "Authorization candidate genesis "
                        "is invalid"
                    )

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                hash_chain_valid = False
                record_valid = False

                errors.append(
                    "Authorization candidate hash "
                    "chain is broken at sequence "
                    f"{sequence}"
                )

            expected_record_hash = _record_hash(
                sequence_number=(
                    record.sequence_number
                ),
                authorization_candidate_id=(
                    record.authorization_candidate_id
                ),
                candidate_fingerprint=(
                    record.candidate_fingerprint
                ),
                review_decision_id=(
                    record.review_decision_id
                ),
                review_record_hash=(
                    record.review_record_hash
                ),
                decision_fingerprint=(
                    record.decision_fingerprint
                ),
                proposal_id=(
                    record.proposal_id
                ),
                proposal_record_hash=(
                    record.proposal_record_hash
                ),
                queue_item_id=(
                    record.queue_item_id
                ),
                reviewer_id=(
                    record.reviewer_id
                ),
                human_decision=(
                    record.human_decision
                ),
                review_audit_id=(
                    record.review_audit_id
                ),
                candidate_payload=(
                    record.candidate_payload
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
                record_valid = False

                errors.append(
                    "Authorization candidate record "
                    "hash mismatch at sequence "
                    f"{sequence}"
                )

            payload = (
                record.candidate_payload
            )

            payload_fingerprint = str(
                payload.get(
                    "candidate_fingerprint",
                    "",
                )
            )

            calculated_fingerprint = (
                _calculate_candidate_fingerprint(
                    payload
                )
            )

            if (
                payload_fingerprint
                != record.candidate_fingerprint
                or calculated_fingerprint
                != record.candidate_fingerprint
            ):
                candidate_fingerprints_valid = False
                record_valid = False

                errors.append(
                    "Authorization candidate "
                    "fingerprint mismatch at sequence "
                    f"{sequence}"
                )

            bindings = {
                "authorization_candidate_id": (
                    record.authorization_candidate_id
                ),
                "candidate_fingerprint": (
                    record.candidate_fingerprint
                ),
                "review_decision_id": (
                    record.review_decision_id
                ),
                "review_record_hash": (
                    record.review_record_hash
                ),
                "decision_fingerprint": (
                    record.decision_fingerprint
                ),
                "proposal_id": (
                    record.proposal_id
                ),
                "proposal_record_hash": (
                    record.proposal_record_hash
                ),
                "queue_item_id": (
                    record.queue_item_id
                ),
                "reviewer_id": (
                    record.reviewer_id
                ),
                "human_decision": (
                    record.human_decision
                ),
                "review_audit_id": (
                    record.review_audit_id
                ),
            }

            for field, expected_value in (
                bindings.items()
            ):
                if (
                    payload.get(
                        field
                    )
                    != expected_value
                ):
                    payload_bindings_valid = False
                    record_valid = False

                    errors.append(
                        "Authorization candidate payload "
                        f"binding mismatch for {field} "
                        "at sequence "
                        f"{sequence}"
                    )

            if (
                payload.get(
                    "review_audit_valid"
                )
                is not True
            ):
                candidate_eligibility_valid = False
                record_valid = False

                errors.append(
                    "Authorization candidate review "
                    "audit is not valid at sequence "
                    f"{sequence}"
                )

            if (
                payload.get(
                    "eligible_for_authorization_review"
                )
                is not True
            ):
                candidate_eligibility_valid = False
                record_valid = False

                errors.append(
                    "Authorization candidate is not "
                    "eligible for authorization review "
                    "at sequence "
                    f"{sequence}"
                )

            if (
                record.human_decision
                != APPROVED_DECISION
                or payload.get(
                    "human_decision"
                )
                != APPROVED_DECISION
            ):
                candidate_eligibility_valid = False
                record_valid = False

                errors.append(
                    "Unsupported authorization "
                    "candidate human decision at "
                    "sequence "
                    f"{sequence}"
                )

            safety_checks = {
                "authorization_created":
                    False,
                "approval_claim_created":
                    False,
                "can_execute":
                    False,
            }

            for field, expected_value in (
                safety_checks.items()
            ):
                if (
                    payload.get(
                        field
                    )
                    is not expected_value
                ):
                    safety_contracts_valid = False
                    record_valid = False

                    errors.append(
                        "Authorization candidate safety "
                        f"contract failed for {field} "
                        "at sequence "
                        f"{sequence}"
                    )

            safety = payload.get(
                "safety"
            )

            if not isinstance(
                safety,
                dict,
            ):
                safety_contracts_valid = False
                record_valid = False

                errors.append(
                    "Authorization candidate safety "
                    "payload is missing at sequence "
                    f"{sequence}"
                )

            else:
                required_safety = {
                    "authorization_candidate_only":
                        True,
                    "authorization_token_created":
                        False,
                    "authorization_created":
                        False,
                    "approval_claim_created":
                        False,
                    "execution_lease_created":
                        False,
                    "execution_approved":
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
                }

                for field, expected_value in (
                    required_safety.items()
                ):
                    if (
                        safety.get(
                            field
                        )
                        is not expected_value
                    ):
                        safety_contracts_valid = False
                        record_valid = False

                        errors.append(
                            "Authorization candidate "
                            "safety metadata mismatch "
                            f"for {field} at sequence "
                            f"{sequence}"
                        )

            if record_valid:
                verified_record_count += 1

            expected_sequence = (
                sequence + 1
            )

            expected_previous_hash = (
                record.record_hash
            )

        if not rows:
            warnings.append(
                "Autonomous authorization candidate "
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

        return AutonomousAuthorizationCandidateAuditReport(
            audit_id=(
                "autonomous-authorization-"
                f"candidate-audit:{uuid4()}"
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
            candidate_fingerprints_valid=(
                candidate_fingerprints_valid
            ),
            payload_bindings_valid=(
                payload_bindings_valid
            ),
            candidate_eligibility_valid=(
                candidate_eligibility_valid
            ),
            safety_contracts_valid=(
                safety_contracts_valid
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


def verify_autonomous_authorization_candidate_store(
    store: AutonomousAuthorizationCandidateStore,
) -> AutonomousAuthorizationCandidateAuditReport:
    if not isinstance(
        store,
        AutonomousAuthorizationCandidateStore,
    ):
        raise TypeError(
            "store must be an "
            "AutonomousAuthorizationCandidateStore"
        )

    return (
        AutonomousAuthorizationCandidateAuditVerifier(
            store.database_path
        ).verify()
    )
