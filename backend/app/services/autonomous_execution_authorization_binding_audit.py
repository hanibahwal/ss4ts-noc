from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.autonomous_execution_authorization_binding import (
    AutonomousExecutionAuthorizationBinding,
)
from app.models.execution_authorization import (
    AuthorizationDecision,
    AuthorizationStatus,
    ExecutionRiskClass,
)
from app.services.autonomous_execution_authorization_binding_store import (
    AutonomousExecutionAuthorizationBindingIntegrityError,
    AutonomousExecutionAuthorizationBindingRecord,
    AutonomousExecutionAuthorizationBindingStore,
)


SERVICE_NAME = (
    "SS4TS Autonomous Execution Authorization "
    "Binding Store Audit"
)

SERVICE_VERSION = "1.0.0"


def _utc_now(
) -> datetime:
    return datetime.now(
        timezone.utc
    )


def _normalize_datetime(
    value: datetime | None,
) -> datetime:
    resolved = (
        value
        if value is not None
        else _utc_now()
    )

    if not isinstance(
        resolved,
        datetime,
    ):
        raise TypeError(
            "audited_at must be a datetime"
        )

    if (
        resolved.tzinfo is None
        or resolved.utcoffset() is None
    ):
        raise ValueError(
            "audited_at must be timezone-aware"
        )

    return resolved.astimezone(
        timezone.utc
    )


def _parse_datetime(
    field_name: str,
    value: Any,
) -> datetime:
    if isinstance(
        value,
        datetime,
    ):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(
                str(
                    value
                ).replace(
                    "Z",
                    "+00:00",
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{field_name} is invalid"
            ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return parsed.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousExecutionAuthorizationBindingAuditReport:
    audit_id: str
    database_path: str
    audited_at: str

    record_count: int
    verified_record_count: int

    first_sequence_number: int | None
    last_sequence_number: int | None

    first_record_hash: str | None
    last_record_hash: str | None

    record_hashes_valid: bool
    hash_chain_valid: bool
    sequence_integrity_valid: bool

    binding_fingerprints_valid: bool
    binding_payloads_valid: bool

    intent_bindings_valid: bool
    authorization_bindings_valid: bool
    duplicate_identities_valid: bool

    safety_claims_valid: bool

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def audit_valid(
        self,
    ) -> bool:
        return all(
            (
                self.record_hashes_valid,
                self.hash_chain_valid,
                self.sequence_integrity_valid,
                self.binding_fingerprints_valid,
                self.binding_payloads_valid,
                self.intent_bindings_valid,
                self.authorization_bindings_valid,
                self.duplicate_identities_valid,
                self.safety_claims_valid,
                not self.errors,
            )
        )

    @property
    def execution_authorization_created(
        self,
    ) -> bool:
        return False

    @property
    def authorization_approved(
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

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "audit_id":
                self.audit_id,
            "database_path":
                self.database_path,
            "audited_at":
                self.audited_at,
            "record_count":
                self.record_count,
            "verified_record_count":
                self.verified_record_count,
            "first_sequence_number":
                self.first_sequence_number,
            "last_sequence_number":
                self.last_sequence_number,
            "first_record_hash":
                self.first_record_hash,
            "last_record_hash":
                self.last_record_hash,
            "audit_valid":
                self.audit_valid,
            "checks": {
                "record_hashes_valid":
                    self.record_hashes_valid,
                "hash_chain_valid":
                    self.hash_chain_valid,
                "sequence_integrity_valid":
                    self.sequence_integrity_valid,
                "binding_fingerprints_valid":
                    self.binding_fingerprints_valid,
                "binding_payloads_valid":
                    self.binding_payloads_valid,
                "intent_bindings_valid":
                    self.intent_bindings_valid,
                "authorization_bindings_valid":
                    self.authorization_bindings_valid,
                "duplicate_identities_valid":
                    self.duplicate_identities_valid,
                "safety_claims_valid":
                    self.safety_claims_valid,
            },
            "errors":
                list(
                    self.errors
                ),
            "warnings":
                list(
                    self.warnings
                ),
            "execution_authorization_created":
                False,
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
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "safety": {
                "audit_only":
                    True,
                "read_only":
                    True,
                "database_mutated":
                    False,
                "execution_authorization_created":
                    False,
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


class AutonomousExecutionAuthorizationBindingAuditVerifier:
    """
    Read-only integrity audit for the immutable autonomous
    execution authorization binding ledger.

    This verifier never writes records, approves authorizations,
    creates tokens or leases, or executes device operations.
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Binding audit database path "
                "must not be empty"
            )

    @staticmethod
    def _validate_binding_fingerprint(
        record: AutonomousExecutionAuthorizationBindingRecord,
    ) -> bool:
        payload = record.binding_payload

        try:
            binding = (
                AutonomousExecutionAuthorizationBinding(
                    binding_id=str(
                        payload["binding_id"]
                    ),
                    authorization_intent_id=str(
                        payload[
                            "authorization_intent_id"
                        ]
                    ),
                    intent_record_hash=str(
                        payload[
                            "intent_record_hash"
                        ]
                    ),
                    intent_bridge_fingerprint=str(
                        payload[
                            "intent_bridge_fingerprint"
                        ]
                    ),
                    intent_audit_id=str(
                        payload[
                            "intent_audit_id"
                        ]
                    ),
                    intent_audit_valid=bool(
                        payload[
                            "intent_audit_valid"
                        ]
                    ),
                    execution_authorization_id=str(
                        payload[
                            "execution_authorization_id"
                        ]
                    ),
                    plan_id=str(
                        payload["plan_id"]
                    ),
                    decision_id=str(
                        payload["decision_id"]
                    ),
                    risk_class=ExecutionRiskClass(
                        payload["risk_class"]
                    ),
                    authorization_status=(
                        AuthorizationStatus(
                            payload[
                                "authorization_status"
                            ]
                        )
                    ),
                    authorization_decision=(
                        AuthorizationDecision(
                            payload[
                                "authorization_decision"
                            ]
                        )
                    ),
                    created_at=_parse_datetime(
                        "created_at",
                        payload["created_at"],
                    ),
                    expires_at=_parse_datetime(
                        "expires_at",
                        payload["expires_at"],
                    ),
                    binding_fingerprint=str(
                        payload[
                            "binding_fingerprint"
                        ]
                    ),
                )
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return False

        return (
            binding.binding_fingerprint
            == record.binding_fingerprint
            == binding.calculate_fingerprint()
        )

    @staticmethod
    def _payload_matches_record(
        record: AutonomousExecutionAuthorizationBindingRecord,
    ) -> bool:
        payload = record.binding_payload

        expected = {
            "binding_id":
                record.binding_id,
            "authorization_intent_id":
                record.authorization_intent_id,
            "intent_record_hash":
                record.intent_record_hash,
            "intent_bridge_fingerprint":
                record.intent_bridge_fingerprint,
            "intent_audit_id":
                record.intent_audit_id,
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
            "binding_fingerprint":
                record.binding_fingerprint,
        }

        return all(
            payload.get(
                field
            ) == value
            for field, value in expected.items()
        )

    @staticmethod
    def _safety_claims_valid(
        record: AutonomousExecutionAuthorizationBindingRecord,
    ) -> bool:
        payload = record.binding_payload

        false_claims = (
            "authorization_approved",
            "authorization_token_created",
            "approval_claim_created",
            "execution_lease_created",
            "execution_allowed",
            "can_execute",
        )

        if any(
            payload.get(
                field
            ) is not False
            for field in false_claims
        ):
            return False

        safety = payload.get(
            "safety"
        )

        if not isinstance(
            safety,
            dict,
        ):
            return False

        safety_false_claims = (
            "authorization_approved",
            "authorization_token_created",
            "approval_claim_created",
            "execution_lease_created",
            "execution_allowed",
            "execution_approved",
            "authorization_consumed",
            "simulation_started",
            "network_io_performed",
            "device_access_performed",
            "command_generated",
            "device_command_executed",
        )

        return all(
            safety.get(
                field
            ) is False
            for field in safety_false_claims
        )

    @staticmethod
    def _intent_binding_valid(
        record: AutonomousExecutionAuthorizationBindingRecord,
    ) -> bool:
        payload = record.binding_payload

        return (
            bool(
                record.authorization_intent_id
            )
            and bool(
                record.intent_record_hash
            )
            and len(
                record.intent_record_hash
            ) == 64
            and bool(
                record.intent_bridge_fingerprint
            )
            and len(
                record.intent_bridge_fingerprint
            ) == 64
            and bool(
                record.intent_audit_id
            )
            and payload.get(
                "intent_audit_valid"
            ) is True
        )

    @staticmethod
    def _authorization_binding_valid(
        record: AutonomousExecutionAuthorizationBindingRecord,
    ) -> bool:
        return (
            bool(
                record.execution_authorization_id
            )
            and bool(
                record.plan_id
            )
            and bool(
                record.decision_id
            )
            and record.authorization_status
            == AuthorizationStatus.PENDING.value
            and record.authorization_decision
            == (
                AuthorizationDecision
                .REQUIRE_APPROVAL
                .value
            )
        )

    def verify(
        self,
        *,
        audited_at: datetime | None = None,
    ) -> AutonomousExecutionAuthorizationBindingAuditReport:
        resolved_audited_at = (
            _normalize_datetime(
                audited_at
            )
        )

        store = (
            AutonomousExecutionAuthorizationBindingStore(
                self.database_path
            )
        )

        errors: list[str] = []
        warnings: list[str] = []

        try:
            records = store.list_records(
                limit=1000
            )

        except (
            AutonomousExecutionAuthorizationBindingIntegrityError,
            TypeError,
            ValueError,
        ) as exc:
            return (
                AutonomousExecutionAuthorizationBindingAuditReport(
                    audit_id=(
                        "autonomous-execution-"
                        "authorization-binding-audit:"
                        f"{uuid4()}"
                    ),
                    database_path=str(
                        self.database_path
                    ),
                    audited_at=(
                        resolved_audited_at
                        .isoformat()
                    ),
                    record_count=0,
                    verified_record_count=0,
                    first_sequence_number=None,
                    last_sequence_number=None,
                    first_record_hash=None,
                    last_record_hash=None,
                    record_hashes_valid=False,
                    hash_chain_valid=False,
                    sequence_integrity_valid=False,
                    binding_fingerprints_valid=False,
                    binding_payloads_valid=False,
                    intent_bindings_valid=False,
                    authorization_bindings_valid=False,
                    duplicate_identities_valid=False,
                    safety_claims_valid=False,
                    errors=(
                        f"Binding ledger could not be read: {exc}",
                    ),
                    warnings=(),
                )
            )

        record_hashes_valid = True
        hash_chain_valid = True
        sequence_integrity_valid = True

        binding_fingerprints_valid = True
        binding_payloads_valid = True

        intent_bindings_valid = True
        authorization_bindings_valid = True
        duplicate_identities_valid = True

        safety_claims_valid = True

        verified_record_count = 0
        expected_sequence = 1
        expected_previous_hash: str | None = None

        binding_ids: set[str] = set()
        intent_ids: set[str] = set()
        intent_record_hashes: set[str] = set()
        execution_authorization_ids: set[str] = set()
        fingerprints: set[str] = set()

        for record in records:
            record_valid = True

            if (
                record.sequence_number
                != expected_sequence
            ):
                sequence_integrity_valid = False
                record_valid = False

                errors.append(
                    "Sequence mismatch at record "
                    f"{record.sequence_number}; "
                    f"expected {expected_sequence}"
                )

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                hash_chain_valid = False
                record_valid = False

                errors.append(
                    "Previous record hash mismatch "
                    f"at sequence {record.sequence_number}"
                )

            if not record.verify_hash():
                record_hashes_valid = False
                record_valid = False

                errors.append(
                    "Record hash mismatch at sequence "
                    f"{record.sequence_number}"
                )

            if not self._payload_matches_record(
                record
            ):
                binding_payloads_valid = False
                record_valid = False

                errors.append(
                    "Binding payload mismatch at sequence "
                    f"{record.sequence_number}"
                )

            if not self._validate_binding_fingerprint(
                record
            ):
                binding_fingerprints_valid = False
                record_valid = False

                errors.append(
                    "Binding fingerprint mismatch "
                    f"at sequence {record.sequence_number}"
                )

            if not self._intent_binding_valid(
                record
            ):
                intent_bindings_valid = False
                record_valid = False

                errors.append(
                    "Intent binding is invalid "
                    f"at sequence {record.sequence_number}"
                )

            if not self._authorization_binding_valid(
                record
            ):
                authorization_bindings_valid = False
                record_valid = False

                errors.append(
                    "Execution authorization binding "
                    "is invalid at sequence "
                    f"{record.sequence_number}"
                )

            if not self._safety_claims_valid(
                record
            ):
                safety_claims_valid = False
                record_valid = False

                errors.append(
                    "Unsafe execution claim detected "
                    f"at sequence {record.sequence_number}"
                )

            identities = (
                (
                    "binding_id",
                    record.binding_id,
                    binding_ids,
                ),
                (
                    "authorization_intent_id",
                    record.authorization_intent_id,
                    intent_ids,
                ),
                (
                    "intent_record_hash",
                    record.intent_record_hash,
                    intent_record_hashes,
                ),
                (
                    "execution_authorization_id",
                    record.execution_authorization_id,
                    execution_authorization_ids,
                ),
                (
                    "binding_fingerprint",
                    record.binding_fingerprint,
                    fingerprints,
                ),
            )

            for (
                identity_name,
                identity_value,
                seen,
            ) in identities:
                if identity_value in seen:
                    duplicate_identities_valid = False
                    record_valid = False

                    errors.append(
                        "Duplicate "
                        f"{identity_name} detected "
                        f"at sequence {record.sequence_number}"
                    )

                seen.add(
                    identity_value
                )

            if record_valid:
                verified_record_count += 1

            expected_sequence = (
                record.sequence_number + 1
            )

            expected_previous_hash = (
                record.record_hash
            )

        if not records:
            warnings.append(
                "Execution authorization binding "
                "ledger is empty"
            )

        hash_chain_valid = (
            hash_chain_valid
            and sequence_integrity_valid
            and record_hashes_valid
        )

        first_record = (
            records[0]
            if records
            else None
        )

        last_record = (
            records[-1]
            if records
            else None
        )

        return AutonomousExecutionAuthorizationBindingAuditReport(
            audit_id=(
                "autonomous-execution-authorization-"
                f"binding-audit:{uuid4()}"
            ),
            database_path=str(
                self.database_path
            ),
            audited_at=(
                resolved_audited_at
                .isoformat()
            ),
            record_count=len(
                records
            ),
            verified_record_count=(
                verified_record_count
            ),
            first_sequence_number=(
                first_record.sequence_number
                if first_record
                else None
            ),
            last_sequence_number=(
                last_record.sequence_number
                if last_record
                else None
            ),
            first_record_hash=(
                first_record.record_hash
                if first_record
                else None
            ),
            last_record_hash=(
                last_record.record_hash
                if last_record
                else None
            ),
            record_hashes_valid=(
                record_hashes_valid
            ),
            hash_chain_valid=(
                hash_chain_valid
            ),
            sequence_integrity_valid=(
                sequence_integrity_valid
            ),
            binding_fingerprints_valid=(
                binding_fingerprints_valid
            ),
            binding_payloads_valid=(
                binding_payloads_valid
            ),
            intent_bindings_valid=(
                intent_bindings_valid
            ),
            authorization_bindings_valid=(
                authorization_bindings_valid
            ),
            duplicate_identities_valid=(
                duplicate_identities_valid
            ),
            safety_claims_valid=(
                safety_claims_valid
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


def verify_autonomous_execution_authorization_binding_store(
    store: AutonomousExecutionAuthorizationBindingStore,
    *,
    audited_at: datetime | None = None,
) -> AutonomousExecutionAuthorizationBindingAuditReport:
    if not isinstance(
        store,
        AutonomousExecutionAuthorizationBindingStore,
    ):
        raise TypeError(
            "store must be an "
            "AutonomousExecutionAuthorizationBindingStore"
        )

    return (
        AutonomousExecutionAuthorizationBindingAuditVerifier(
            store.database_path
        ).verify(
            audited_at=audited_at
        )
    )
