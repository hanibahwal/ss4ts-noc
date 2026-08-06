from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.autonomous_controlled_authorization_human_decision import (
    AutonomousControlledAuthorizationHumanDecision,
    AutonomousControlledAuthorizationHumanDecisionType,
)
from app.services.autonomous_controlled_authorization_human_decision_store import (
    GENESIS_RECORD_HASH,
    AutonomousControlledAuthorizationHumanDecisionStore,
    AutonomousHumanApprovalDecisionRecord,
)


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousHumanApprovalDecisionAuditReport:
    audit_id: str
    audited_at: datetime

    record_count: int
    first_sequence_number: int | None
    last_sequence_number: int | None

    record_hashes_valid: bool
    hash_chain_valid: bool
    sequence_integrity_valid: bool

    decision_fingerprints_valid: bool
    decision_payloads_valid: bool

    candidate_audits_valid: bool
    human_decisions_valid: bool
    timestamp_consistency_valid: bool

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
                self.decision_fingerprints_valid,
                self.decision_payloads_valid,
                self.candidate_audits_valid,
                self.human_decisions_valid,
                self.timestamp_consistency_valid,
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
                "decision_fingerprints_valid":
                    self.decision_fingerprints_valid,
                "decision_payloads_valid":
                    self.decision_payloads_valid,
                "candidate_audits_valid":
                    self.candidate_audits_valid,
                "human_decisions_valid":
                    self.human_decisions_valid,
                "timestamp_consistency_valid":
                    self.timestamp_consistency_valid,
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
                "human_decision_store_audit_only":
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


class AutonomousHumanApprovalDecisionAuditVerifier:
    """
    Read-only verifier for the immutable human decision ledger.

    It never appends, updates, deletes, approves an execution
    authorization, creates a claim or lease, or executes anything.
    """

    PROTECTED_IDENTITY_FIELDS = (
        "approval_decision_id",
        "decision_fingerprint",
        "approval_candidate_id",
        "candidate_record_hash",
        "candidate_fingerprint",
        "execution_authorization_id",
        "record_hash",
    )

    PAYLOAD_BINDING_FIELDS = (
        "approval_decision_id",
        "decision_fingerprint",
        "approval_candidate_id",
        "candidate_record_hash",
        "candidate_fingerprint",
        "candidate_audit_id",
        "candidate_audit_valid",
        "binding_id",
        "execution_authorization_id",
        "plan_id",
        "source_decision_id",
        "risk_class",
        "reviewer_id",
        "human_decision",
        "decision_reason",
        "decided_at",
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
    def _decision_from_record(
        record: AutonomousHumanApprovalDecisionRecord,
    ) -> AutonomousControlledAuthorizationHumanDecision:
        decided_at = (
            AutonomousHumanApprovalDecisionAuditVerifier
            ._parse_datetime(
                record.decided_at
            )
        )

        if decided_at is None:
            raise ValueError(
                "Decision decided_at is invalid"
            )

        return AutonomousControlledAuthorizationHumanDecision(
            approval_decision_id=(
                record.approval_decision_id
            ),
            approval_candidate_id=(
                record.approval_candidate_id
            ),
            candidate_record_hash=(
                record.candidate_record_hash
            ),
            candidate_fingerprint=(
                record.candidate_fingerprint
            ),
            candidate_audit_id=(
                record.candidate_audit_id
            ),
            candidate_audit_valid=(
                record.candidate_audit_valid
            ),
            binding_id=(
                record.binding_id
            ),
            execution_authorization_id=(
                record.execution_authorization_id
            ),
            plan_id=(
                record.plan_id
            ),
            source_decision_id=(
                record.source_decision_id
            ),
            risk_class=(
                record.risk_class
            ),
            reviewer_id=(
                record.reviewer_id
            ),
            human_decision=(
                record.human_decision
            ),
            decision_reason=(
                record.decision_reason
            ),
            decided_at=decided_at,
            decision_fingerprint=(
                record.decision_fingerprint
            ),
        )

    def verify(
        self,
        *,
        store: (
            AutonomousControlledAuthorizationHumanDecisionStore
        ),
        audited_at: datetime | None = None,
    ) -> AutonomousHumanApprovalDecisionAuditReport:
        if not isinstance(
            store,
            AutonomousControlledAuthorizationHumanDecisionStore,
        ):
            raise TypeError(
                "store must be an "
                "AutonomousControlledAuthorizationHumanDecisionStore"
            )

        resolved_audited_at = (
            self._normalize_audited_at(
                audited_at
            )
        )

        records = store.list_records(
            limit=1_000_000
        )

        issues: list[str] = []

        record_hashes_valid = True
        hash_chain_valid = True
        sequence_integrity_valid = True

        decision_fingerprints_valid = True
        decision_payloads_valid = True

        candidate_audits_valid = True
        human_decisions_valid = True
        timestamp_consistency_valid = True

        duplicate_identities_valid = True
        safety_claims_valid = True

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        allowed_decisions = {
            item.value
            for item in (
                AutonomousControlledAuthorizationHumanDecisionType
            )
        }

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

            payload = record.decision_payload

            if not isinstance(
                payload,
                dict,
            ):
                decision_payloads_valid = False
                issues.append(
                    "Decision payload is not an object "
                    f"at sequence {sequence}"
                )
                payload = {}

            for field_name in (
                self.PAYLOAD_BINDING_FIELDS
            ):
                expected_value = getattr(
                    record,
                    field_name,
                )

                if (
                    payload.get(
                        field_name
                    )
                    != expected_value
                ):
                    decision_payloads_valid = False
                    issues.append(
                        "Decision payload binding mismatch "
                        f"for {field_name} at sequence "
                        f"{sequence}"
                    )

            try:
                reconstructed = (
                    self._decision_from_record(
                        record
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                decision_fingerprints_valid = False
                issues.append(
                    "Decision reconstruction failed at "
                    f"sequence {sequence}: {exc}"
                )

            else:
                if (
                    reconstructed.decision_fingerprint
                    != record.decision_fingerprint
                    or
                    reconstructed.calculate_fingerprint()
                    != record.decision_fingerprint
                ):
                    decision_fingerprints_valid = False
                    issues.append(
                        "Decision fingerprint mismatch at "
                        f"sequence {sequence}"
                    )

            if record.candidate_audit_valid is not True:
                candidate_audits_valid = False
                issues.append(
                    "Candidate audit is not valid at "
                    f"sequence {sequence}"
                )

            if (
                record.human_decision
                not in allowed_decisions
            ):
                human_decisions_valid = False
                issues.append(
                    "Unsupported human decision at "
                    f"sequence {sequence}"
                )

            decided_at = self._parse_datetime(
                record.decided_at
            )
            stored_at = self._parse_datetime(
                record.stored_at
            )

            if (
                decided_at is None
                or stored_at is None
                or stored_at < decided_at
            ):
                timestamp_consistency_valid = False
                issues.append(
                    "Decision timestamp consistency "
                    f"failed at sequence {sequence}"
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
                        "Unsafe decision claim "
                        f"{field_name} at sequence "
                        f"{sequence}"
                    )

            if (
                record.authorization_approved
                or record.authorization_token_created
                or record.approval_claim_created
                or record.execution_lease_created
                or record.execution_allowed
                or record.can_execute
            ):
                safety_claims_valid = False
                issues.append(
                    "Stored human decision unexpectedly "
                    "grants authorization or execution at "
                    f"sequence {sequence}"
                )

            expected_sequence += 1
            expected_previous_hash = (
                record.record_hash
            )

        return AutonomousHumanApprovalDecisionAuditReport(
            audit_id=(
                "human-approval-decision-audit:"
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
            decision_fingerprints_valid=(
                decision_fingerprints_valid
            ),
            decision_payloads_valid=(
                decision_payloads_valid
            ),
            candidate_audits_valid=(
                candidate_audits_valid
            ),
            human_decisions_valid=(
                human_decisions_valid
            ),
            timestamp_consistency_valid=(
                timestamp_consistency_valid
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


def verify_autonomous_controlled_authorization_human_decision_store(
    store: (
        AutonomousControlledAuthorizationHumanDecisionStore
    ),
    *,
    audited_at: datetime | None = None,
) -> AutonomousHumanApprovalDecisionAuditReport:
    return (
        AutonomousHumanApprovalDecisionAuditVerifier()
        .verify(
            store=store,
            audited_at=audited_at,
        )
    )
