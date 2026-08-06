from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from app.services.autonomous_execution_authorization_binding_audit import (
    AutonomousExecutionAuthorizationBindingAuditReport,
)
from app.services.autonomous_execution_authorization_binding_store import (
    AutonomousExecutionAuthorizationBindingRecord,
)


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _required_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    normalized = str(
        value
    ).strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def _required_sha256(
    value: Any,
    *,
    field_name: str,
) -> str:
    normalized = _required_text(
        value,
        field_name=field_name,
    ).lower()

    if (
        len(normalized) != 64
        or any(
            character not in "0123456789abcdef"
            for character in normalized
        )
    ):
        raise ValueError(
            f"{field_name} must be a SHA-256 hash"
        )

    return normalized


def _normalized_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
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
    )


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousControlledAuthorizationApprovalCandidate:
    approval_candidate_id: str

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

    requested_at: datetime
    expires_at: datetime

    candidate_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        text_fields = (
            "approval_candidate_id",
            "binding_id",
            "binding_audit_id",
            "authorization_intent_id",
            "execution_authorization_id",
            "plan_id",
            "decision_id",
            "risk_class",
            "authorization_status",
            "authorization_decision",
            "requested_by",
            "approval_reason",
        )

        for field_name in text_fields:
            object.__setattr__(
                self,
                field_name,
                _required_text(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        hash_fields = (
            "binding_record_hash",
            "binding_fingerprint",
        )

        for field_name in hash_fields:
            object.__setattr__(
                self,
                field_name,
                _required_sha256(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        object.__setattr__(
            self,
            "requested_at",
            _normalized_datetime(
                self.requested_at,
                field_name="requested_at",
            ),
        )

        object.__setattr__(
            self,
            "expires_at",
            _normalized_datetime(
                self.expires_at,
                field_name="expires_at",
            ),
        )

        if self.binding_audit_valid is not True:
            raise ValueError(
                "binding_audit_valid must be True"
            )

        if (
            self.authorization_status
            != "pending"
        ):
            raise ValueError(
                "authorization_status must be pending"
            )

        if (
            self.authorization_decision
            != "require_approval"
        ):
            raise ValueError(
                "authorization_decision must be "
                "require_approval"
            )

        if self.expires_at <= self.requested_at:
            raise ValueError(
                "expires_at must be later than "
                "requested_at"
            )

        expected = self.calculate_fingerprint()

        if not self.candidate_fingerprint:
            object.__setattr__(
                self,
                "candidate_fingerprint",
                expected,
            )

        else:
            normalized_fingerprint = (
                _required_sha256(
                    self.candidate_fingerprint,
                    field_name=(
                        "candidate_fingerprint"
                    ),
                )
            )

            if normalized_fingerprint != expected:
                raise ValueError(
                    "candidate_fingerprint mismatch"
                )

            object.__setattr__(
                self,
                "candidate_fingerprint",
                normalized_fingerprint,
            )

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

    def fingerprint_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "approval_candidate_id":
                self.approval_candidate_id,
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
                self.requested_at.isoformat(),
            "expires_at":
                self.expires_at.isoformat(),
        }

    def calculate_fingerprint(
        self,
    ) -> str:
        return hashlib.sha256(
            _canonical_json(
                self.fingerprint_payload()
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            **self.fingerprint_payload(),
            "candidate_fingerprint":
                self.candidate_fingerprint,
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
                "approval_candidate_only":
                    True,
                "human_approval_required":
                    True,
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

    @classmethod
    def from_verified_binding(
        cls,
        *,
        approval_candidate_id: str,
        binding_record: (
            AutonomousExecutionAuthorizationBindingRecord
        ),
        binding_audit: (
            AutonomousExecutionAuthorizationBindingAuditReport
        ),
        requested_by: str,
        approval_reason: str,
        requested_at: datetime,
        expires_at: datetime,
    ) -> (
        AutonomousControlledAuthorizationApprovalCandidate
    ):
        if not isinstance(
            binding_record,
            AutonomousExecutionAuthorizationBindingRecord,
        ):
            raise TypeError(
                "binding_record must be an "
                "AutonomousExecutionAuthorizationBindingRecord"
            )

        if not isinstance(
            binding_audit,
            AutonomousExecutionAuthorizationBindingAuditReport,
        ):
            raise TypeError(
                "binding_audit must be an "
                "AutonomousExecutionAuthorizationBindingAuditReport"
            )

        if not binding_record.verify_hash():
            raise ValueError(
                "Binding record hash is invalid"
            )

        if not binding_audit.audit_valid:
            raise ValueError(
                "Binding store audit is invalid"
            )

        if binding_audit.can_execute:
            raise ValueError(
                "Binding audit unexpectedly allows execution"
            )

        if (
            binding_record.sequence_number
            < 1
        ):
            raise ValueError(
                "Binding record sequence is invalid"
            )

        if (
            binding_audit.first_sequence_number
            is not None
            and binding_record.sequence_number
            < binding_audit.first_sequence_number
        ):
            raise ValueError(
                "Binding record is outside audited range"
            )

        if (
            binding_audit.last_sequence_number
            is not None
            and binding_record.sequence_number
            > binding_audit.last_sequence_number
        ):
            raise ValueError(
                "Binding record is outside audited range"
            )

        payload = binding_record.binding_payload

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
            raise ValueError(
                "Binding record contains an unsafe claim"
            )

        return cls(
            approval_candidate_id=(
                approval_candidate_id
            ),
            binding_id=(
                binding_record.binding_id
            ),
            binding_record_hash=(
                binding_record.record_hash
            ),
            binding_fingerprint=(
                binding_record.binding_fingerprint
            ),
            binding_audit_id=(
                binding_audit.audit_id
            ),
            binding_audit_valid=True,
            authorization_intent_id=(
                binding_record.authorization_intent_id
            ),
            execution_authorization_id=(
                binding_record.execution_authorization_id
            ),
            plan_id=(
                binding_record.plan_id
            ),
            decision_id=(
                binding_record.decision_id
            ),
            risk_class=(
                binding_record.risk_class
            ),
            authorization_status=(
                binding_record.authorization_status
            ),
            authorization_decision=(
                binding_record.authorization_decision
            ),
            requested_by=requested_by,
            approval_reason=approval_reason,
            requested_at=requested_at,
            expires_at=expires_at,
            candidate_fingerprint="",
        )
