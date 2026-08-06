from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any

from app.services.autonomous_controlled_authorization_approval_candidate_audit import (
    AutonomousApprovalCandidateAuditReport,
)
from app.services.autonomous_controlled_authorization_approval_candidate_store import (
    AutonomousApprovalCandidateRecord,
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


class AutonomousControlledAuthorizationHumanDecisionType(
    str,
    Enum,
):
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousControlledAuthorizationHumanDecision:
    approval_decision_id: str

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
    human_decision: (
        AutonomousControlledAuthorizationHumanDecisionType
    )
    decision_reason: str
    decided_at: datetime

    decision_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        text_fields = (
            "approval_decision_id",
            "approval_candidate_id",
            "candidate_audit_id",
            "binding_id",
            "execution_authorization_id",
            "plan_id",
            "source_decision_id",
            "risk_class",
            "reviewer_id",
            "decision_reason",
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

        for field_name in (
            "candidate_record_hash",
            "candidate_fingerprint",
        ):
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

        if not isinstance(
            self.human_decision,
            AutonomousControlledAuthorizationHumanDecisionType,
        ):
            try:
                normalized_decision = (
                    AutonomousControlledAuthorizationHumanDecisionType(
                        str(
                            self.human_decision
                        ).strip().lower()
                    )
                )
            except ValueError as exc:
                raise ValueError(
                    "human_decision is unsupported"
                ) from exc

            object.__setattr__(
                self,
                "human_decision",
                normalized_decision,
            )

        object.__setattr__(
            self,
            "decided_at",
            _normalized_datetime(
                self.decided_at,
                field_name="decided_at",
            ),
        )

        if self.candidate_audit_valid is not True:
            raise ValueError(
                "candidate_audit_valid must be True"
            )

        expected_fingerprint = (
            self.calculate_fingerprint()
        )

        if not self.decision_fingerprint:
            object.__setattr__(
                self,
                "decision_fingerprint",
                expected_fingerprint,
            )

        else:
            normalized_fingerprint = (
                _required_sha256(
                    self.decision_fingerprint,
                    field_name="decision_fingerprint",
                )
            )

            if (
                normalized_fingerprint
                != expected_fingerprint
            ):
                raise ValueError(
                    "decision_fingerprint mismatch"
                )

            object.__setattr__(
                self,
                "decision_fingerprint",
                normalized_fingerprint,
            )

    @property
    def human_decision_recorded(
        self,
    ) -> bool:
        return True

    @property
    def approved_by_human(
        self,
    ) -> bool:
        return (
            self.human_decision
            is
            AutonomousControlledAuthorizationHumanDecisionType.APPROVED
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

    def fingerprint_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "approval_decision_id":
                self.approval_decision_id,
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
                self.human_decision.value,
            "decision_reason":
                self.decision_reason,
            "decided_at":
                self.decided_at.isoformat(),
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
            "decision_fingerprint":
                self.decision_fingerprint,
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
                "human_decision_record_only":
                    True,
                "human_decision_recorded":
                    True,
                "approved_by_human":
                    self.approved_by_human,
                "execution_authorization_approved":
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
    def from_verified_candidate(
        cls,
        *,
        approval_decision_id: str,
        candidate_record: AutonomousApprovalCandidateRecord,
        candidate_audit: AutonomousApprovalCandidateAuditReport,
        reviewer_id: str,
        human_decision: (
            AutonomousControlledAuthorizationHumanDecisionType
            | str
        ),
        decision_reason: str,
        decided_at: datetime,
    ) -> (
        AutonomousControlledAuthorizationHumanDecision
    ):
        if not isinstance(
            candidate_record,
            AutonomousApprovalCandidateRecord,
        ):
            raise TypeError(
                "candidate_record must be an "
                "AutonomousApprovalCandidateRecord"
            )

        if not isinstance(
            candidate_audit,
            AutonomousApprovalCandidateAuditReport,
        ):
            raise TypeError(
                "candidate_audit must be an "
                "AutonomousApprovalCandidateAuditReport"
            )

        if not candidate_record.verify_hash():
            raise ValueError(
                "Approval candidate record hash is invalid"
            )

        if not candidate_audit.audit_valid:
            raise ValueError(
                "Approval candidate audit is invalid"
            )

        if candidate_audit.can_execute:
            raise ValueError(
                "Approval candidate audit unexpectedly "
                "allows execution"
            )

        if (
            candidate_audit.first_sequence_number
            is not None
            and candidate_record.sequence_number
            < candidate_audit.first_sequence_number
        ):
            raise ValueError(
                "Approval candidate record is outside "
                "the audited sequence range"
            )

        if (
            candidate_audit.last_sequence_number
            is not None
            and candidate_record.sequence_number
            > candidate_audit.last_sequence_number
        ):
            raise ValueError(
                "Approval candidate record is outside "
                "the audited sequence range"
            )

        resolved_decided_at = _normalized_datetime(
            decided_at,
            field_name="decided_at",
        )

        try:
            resolved_decision = (
                human_decision
                if isinstance(
                    human_decision,
                    AutonomousControlledAuthorizationHumanDecisionType,
                )
                else (
                    AutonomousControlledAuthorizationHumanDecisionType(
                        str(
                            human_decision
                        ).strip().lower()
                    )
                )
            )
        except ValueError as exc:
            raise ValueError(
                "human_decision is unsupported"
            ) from exc

        candidate_expires_at = (
            datetime.fromisoformat(
                candidate_record.expires_at
            )
        )

        if (
            candidate_expires_at.tzinfo is None
            or candidate_expires_at.utcoffset() is None
        ):
            raise ValueError(
                "Approval candidate expiry is invalid"
            )

        candidate_expires_at = (
            candidate_expires_at.astimezone(
                timezone.utc
            )
        )

        if (
            resolved_decision
            is
            AutonomousControlledAuthorizationHumanDecisionType.APPROVED
            and resolved_decided_at
            >= candidate_expires_at
        ):
            raise ValueError(
                "Expired approval candidate cannot "
                "receive an approved decision"
            )

        payload = candidate_record.candidate_payload

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
                raise ValueError(
                    "Approval candidate contains "
                    f"unsafe claim: {field_name}"
                )

        return cls(
            approval_decision_id=(
                approval_decision_id
            ),
            approval_candidate_id=(
                candidate_record.approval_candidate_id
            ),
            candidate_record_hash=(
                candidate_record.record_hash
            ),
            candidate_fingerprint=(
                candidate_record.candidate_fingerprint
            ),
            candidate_audit_id=(
                candidate_audit.audit_id
            ),
            candidate_audit_valid=True,
            binding_id=(
                candidate_record.binding_id
            ),
            execution_authorization_id=(
                candidate_record.execution_authorization_id
            ),
            plan_id=(
                candidate_record.plan_id
            ),
            source_decision_id=(
                candidate_record.decision_id
            ),
            risk_class=(
                candidate_record.risk_class
            ),
            reviewer_id=reviewer_id,
            human_decision=resolved_decision,
            decision_reason=decision_reason,
            decided_at=resolved_decided_at,
            decision_fingerprint="",
        )
