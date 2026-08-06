from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.autonomous_controlled_authorization_approval_candidate import (
    AutonomousControlledAuthorizationApprovalCandidate,
)
from app.services.autonomous_controlled_authorization_approval_candidate_store import (
    AutonomousApprovalCandidateRecord,
    AutonomousControlledAuthorizationApprovalCandidateStore,
)


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousApprovalCandidateAuditReport:
    audit_id: str
    audited_at: datetime

    record_count: int
    first_sequence_number: int | None
    last_sequence_number: int | None

    record_hashes_valid: bool
    hash_chain_valid: bool
    sequence_integrity_valid: bool

    candidate_fingerprints_valid: bool
    candidate_payloads_valid: bool

    binding_audits_valid: bool
    expiry_consistency_valid: bool
    authorization_states_valid: bool

    duplicate_identities_valid: bool
    safety_claims_valid: bool

    issues: tuple[str, ...]

    @property
    def audit_valid(
        self,
    ) -> bool:
        return all(
            (
                self.record_hashes_valid,
                self.hash_chain_valid,
                self.sequence_integrity_valid,
                self.candidate_fingerprints_valid,
                self.candidate_payloads_valid,
                self.binding_audits_valid,
                self.expiry_consistency_valid,
                self.authorization_states_valid,
                self.duplicate_identities_valid,
                self.safety_claims_valid,
                not self.issues,
            )
        )

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

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "audit_id":
                self.audit_id,
            "audited_at":
                self.audited_at.isoformat(),
            "record_count":
                self.record_count,
            "first_sequence_number":
                self.first_sequence_number,
            "last_sequence_number":
                self.last_sequence_number,
            "checks": {
                "record_hashes_valid":
                    self.record_hashes_valid,
                "hash_chain_valid":
                    self.hash_chain_valid,
                "sequence_integrity_valid":
                    self.sequence_integrity_valid,
                "candidate_fingerprints_valid":
                    self.candidate_fingerprints_valid,
                "candidate_payloads_valid":
                    self.candidate_payloads_valid,
                "binding_audits_valid":
                    self.binding_audits_valid,
                "expiry_consistency_valid":
                    self.expiry_consistency_valid,
                "authorization_states_valid":
                    self.authorization_states_valid,
                "duplicate_identities_valid":
                    self.duplicate_identities_valid,
                "safety_claims_valid":
                    self.safety_claims_valid,
            },
            "issues":
                list(
                    self.issues
                ),
            "audit_valid":
                self.audit_valid,
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
                "read_only_audit":
                    True,
                "approval_candidate_audit_only":
                    True,
                "store_mutated":
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


class AutonomousApprovalCandidateAuditVerifier:
    """
    Read-only verifier for the immutable approval candidate store.

    This verifier does not append, update, delete, approve, claim,
    lease, consume, simulate, access a device, or execute anything.
    """

    PROTECTED_IDENTITY_FIELDS = (
        "approval_candidate_id",
        "candidate_fingerprint",
        "binding_id",
        "binding_record_hash",
        "binding_fingerprint",
        "authorization_intent_id",
        "execution_authorization_id",
        "record_hash",
    )

    PAYLOAD_BINDING_FIELDS = (
        "approval_candidate_id",
        "candidate_fingerprint",
        "binding_id",
        "binding_record_hash",
        "binding_fingerprint",
        "binding_audit_id",
        "binding_audit_valid",
        "authorization_intent_id",
        "execution_authorization_id",
        "plan_id",
        "decision_id",
        "risk_class",
        "authorization_status",
        "authorization_decision",
        "requested_by",
        "approval_reason",
        "requested_at",
        "expires_at",
    )

    UNSAFE_FALSE_FIELDS = (
        "authorization_approved",
        "authorization_token_created",
        "approval_claim_created",
        "execution_lease_created",
        "execution_allowed",
        "can_execute",
    )

    @staticmethod
    def _normalize_audited_at(
        audited_at: datetime | None,
    ) -> datetime:
        value = (
            audited_at
            or datetime.now(
                timezone.utc
            )
        )

        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                "audited_at must be a datetime"
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "audited_at must be timezone-aware"
            )

        return value.astimezone(
            timezone.utc
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(
                str(
                    value
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            return None

        return parsed.astimezone(
            timezone.utc
        )

    @staticmethod
    def _candidate_from_record(
        record: AutonomousApprovalCandidateRecord,
    ) -> AutonomousControlledAuthorizationApprovalCandidate:
        payload = record.candidate_payload

        requested_at = (
            AutonomousApprovalCandidateAuditVerifier
            ._parse_datetime(
                payload.get(
                    "requested_at"
                )
            )
        )

        expires_at = (
            AutonomousApprovalCandidateAuditVerifier
            ._parse_datetime(
                payload.get(
                    "expires_at"
                )
            )
        )

        if requested_at is None:
            raise ValueError(
                "Candidate requested_at is invalid"
            )

        if expires_at is None:
            raise ValueError(
                "Candidate expires_at is invalid"
            )

        return AutonomousControlledAuthorizationApprovalCandidate(
            approval_candidate_id=(
                str(
                    payload.get(
                        "approval_candidate_id",
                        "",
                    )
                )
            ),
            binding_id=(
                str(
                    payload.get(
                        "binding_id",
                        "",
                    )
                )
            ),
            binding_record_hash=(
                str(
                    payload.get(
                        "binding_record_hash",
                        "",
                    )
                )
            ),
            binding_fingerprint=(
                str(
                    payload.get(
                        "binding_fingerprint",
                        "",
                    )
                )
            ),
            binding_audit_id=(
                str(
                    payload.get(
                        "binding_audit_id",
                        "",
                    )
                )
            ),
            binding_audit_valid=(
                payload.get(
                    "binding_audit_valid"
                )
                is True
            ),
            authorization_intent_id=(
                str(
                    payload.get(
                        "authorization_intent_id",
                        "",
                    )
                )
            ),
            execution_authorization_id=(
                str(
                    payload.get(
                        "execution_authorization_id",
                        "",
                    )
                )
            ),
            plan_id=(
                str(
                    payload.get(
                        "plan_id",
                        "",
                    )
                )
            ),
            decision_id=(
                str(
                    payload.get(
                        "decision_id",
                        "",
                    )
                )
            ),
            risk_class=(
                str(
                    payload.get(
                        "risk_class",
                        "",
                    )
                )
            ),
            authorization_status=(
                str(
                    payload.get(
                        "authorization_status",
                        "",
                    )
                )
            ),
            authorization_decision=(
                str(
                    payload.get(
                        "authorization_decision",
                        "",
                    )
                )
            ),
            requested_by=(
                str(
                    payload.get(
                        "requested_by",
                        "",
                    )
                )
            ),
            approval_reason=(
                str(
                    payload.get(
                        "approval_reason",
                        "",
                    )
                )
            ),
            requested_at=requested_at,
            expires_at=expires_at,
            candidate_fingerprint=(
                str(
                    payload.get(
                        "candidate_fingerprint",
                        "",
                    )
                )
            ),
        )

    def verify(
        self,
        *,
        store: (
            AutonomousControlledAuthorizationApprovalCandidateStore
        ),
        audited_at: datetime | None = None,
    ) -> AutonomousApprovalCandidateAuditReport:
        if not isinstance(
            store,
            AutonomousControlledAuthorizationApprovalCandidateStore,
        ):
            raise TypeError(
                "store must be an "
                "AutonomousControlledAuthorizationApprovalCandidateStore"
            )

        resolved_audited_at = (
            self._normalize_audited_at(
                audited_at
            )
        )

        records = store.list_records(
            limit=1000
        )

        issues: list[str] = []

        record_hashes_valid = True
        hash_chain_valid = True
        sequence_integrity_valid = True

        candidate_fingerprints_valid = True
        candidate_payloads_valid = True

        binding_audits_valid = True
        expiry_consistency_valid = True
        authorization_states_valid = True

        duplicate_identities_valid = True
        safety_claims_valid = True

        expected_sequence = 1
        expected_previous_hash: str | None = None

        seen: dict[
            str,
            set[Any],
        ] = {
            field_name: set()
            for field_name
            in self.PROTECTED_IDENTITY_FIELDS
        }

        for record in records:
            sequence = (
                record.sequence_number
            )

            if sequence != expected_sequence:
                sequence_integrity_valid = False
                issues.append(
                    "Sequence integrity mismatch at "
                    f"record {sequence}: expected "
                    f"{expected_sequence}"
                )

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                hash_chain_valid = False
                issues.append(
                    "Previous record hash mismatch at "
                    f"sequence {sequence}"
                )

            if not record.verify_hash():
                record_hashes_valid = False
                issues.append(
                    "Record hash mismatch at "
                    f"sequence {sequence}"
                )

            payload = record.candidate_payload

            if not isinstance(
                payload,
                dict,
            ):
                candidate_payloads_valid = False
                issues.append(
                    "Candidate payload is not an object "
                    f"at sequence {sequence}"
                )

                payload = {}

            bindings = {
                field_name:
                    getattr(
                        record,
                        field_name,
                    )
                for field_name
                in self.PAYLOAD_BINDING_FIELDS
            }

            for (
                field_name,
                expected_value,
            ) in bindings.items():
                if (
                    payload.get(
                        field_name
                    )
                    != expected_value
                ):
                    candidate_payloads_valid = False
                    issues.append(
                        "Candidate payload binding mismatch "
                        f"for {field_name} at sequence "
                        f"{sequence}"
                    )

            try:
                candidate = (
                    self._candidate_from_record(
                        record
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                candidate_fingerprints_valid = False
                issues.append(
                    "Candidate reconstruction failed at "
                    f"sequence {sequence}: {exc}"
                )

            else:
                if (
                    candidate.candidate_fingerprint
                    != record.candidate_fingerprint
                    or
                    candidate.calculate_fingerprint()
                    != record.candidate_fingerprint
                ):
                    candidate_fingerprints_valid = False
                    issues.append(
                        "Candidate fingerprint mismatch at "
                        f"sequence {sequence}"
                    )

            if record.binding_audit_valid is not True:
                binding_audits_valid = False
                issues.append(
                    "Binding audit is not valid at "
                    f"sequence {sequence}"
                )

            requested_at = self._parse_datetime(
                record.requested_at
            )
            expires_at = self._parse_datetime(
                record.expires_at
            )
            stored_at = self._parse_datetime(
                record.stored_at
            )

            if (
                requested_at is None
                or expires_at is None
                or stored_at is None
                or expires_at <= requested_at
                or expires_at <= stored_at
            ):
                expiry_consistency_valid = False
                issues.append(
                    "Candidate expiry consistency failed "
                    f"at sequence {sequence}"
                )

            if (
                record.authorization_status
                != "pending"
                or
                record.authorization_decision
                != "require_approval"
            ):
                authorization_states_valid = False
                issues.append(
                    "Authorization state is invalid at "
                    f"sequence {sequence}"
                )

            for field_name in (
                self.PROTECTED_IDENTITY_FIELDS
            ):
                value = getattr(
                    record,
                    field_name,
                )

                if value in seen[
                    field_name
                ]:
                    duplicate_identities_valid = False
                    issues.append(
                        "Duplicate protected identity "
                        f"{field_name} at sequence "
                        f"{sequence}"
                    )

                seen[
                    field_name
                ].add(
                    value
                )

            for field_name in (
                self.UNSAFE_FALSE_FIELDS
            ):
                if (
                    payload.get(
                        field_name
                    )
                    is not False
                ):
                    safety_claims_valid = False
                    issues.append(
                        "Unsafe candidate claim "
                        f"{field_name} at sequence "
                        f"{sequence}"
                    )

            if (
                record.authorization_approved
                or record.approval_claim_created
                or record.execution_allowed
                or record.can_execute
            ):
                safety_claims_valid = False
                issues.append(
                    "Stored record unexpectedly grants "
                    "authorization or execution at "
                    f"sequence {sequence}"
                )

            expected_previous_hash = (
                record.record_hash
            )
            expected_sequence += 1

        report = AutonomousApprovalCandidateAuditReport(
            audit_id=(
                "approval-candidate-audit:"
                f"{uuid4()}"
            ),
            audited_at=resolved_audited_at,
            record_count=len(
                records
            ),
            first_sequence_number=(
                records[0].sequence_number
                if records
                else None
            ),
            last_sequence_number=(
                records[-1].sequence_number
                if records
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
            candidate_fingerprints_valid=(
                candidate_fingerprints_valid
            ),
            candidate_payloads_valid=(
                candidate_payloads_valid
            ),
            binding_audits_valid=(
                binding_audits_valid
            ),
            expiry_consistency_valid=(
                expiry_consistency_valid
            ),
            authorization_states_valid=(
                authorization_states_valid
            ),
            duplicate_identities_valid=(
                duplicate_identities_valid
            ),
            safety_claims_valid=(
                safety_claims_valid
            ),
            issues=tuple(
                issues
            ),
        )

        return report


def verify_autonomous_controlled_authorization_approval_candidate_store(
    store: (
        AutonomousControlledAuthorizationApprovalCandidateStore
    ),
    *,
    audited_at: datetime | None = None,
) -> AutonomousApprovalCandidateAuditReport:
    return (
        AutonomousApprovalCandidateAuditVerifier()
        .verify(
            store=store,
            audited_at=audited_at,
        )
    )
