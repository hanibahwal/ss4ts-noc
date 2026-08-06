from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from app.models.execution_authorization import (
    ExecutionRiskClass,
)


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


def _normalized_datetime(
    value: datetime,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "requested_at must be a datetime"
        )

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def normalize_execution_risk_class(
    value: ExecutionRiskClass | str,
) -> ExecutionRiskClass:
    if isinstance(
        value,
        ExecutionRiskClass,
    ):
        normalized = value

    else:
        try:
            normalized = ExecutionRiskClass(
                str(
                    value
                ).strip().lower()
            )

        except ValueError as exc:
            raise ValueError(
                "risk_class is invalid"
            ) from exc

    if normalized is ExecutionRiskClass.UNKNOWN:
        raise ValueError(
            "risk_class must not be unknown"
        )

    return normalized


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousControlledAuthorizationRequest:
    authorization_request_id: str

    authorization_candidate_id: str
    candidate_record_hash: str
    candidate_fingerprint: str

    review_decision_id: str
    review_record_hash: str

    proposal_id: str
    proposal_record_hash: str

    candidate_audit_id: str
    candidate_audit_valid: bool

    requester_id: str
    requested_at: datetime
    request_reason: str

    risk_class: ExecutionRiskClass

    dry_run_required: bool
    rollback_required: bool
    verification_required: bool

    request_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "authorization_request_id",
            "authorization_candidate_id",
            "candidate_record_hash",
            "candidate_fingerprint",
            "review_decision_id",
            "review_record_hash",
            "proposal_id",
            "proposal_record_hash",
            "candidate_audit_id",
            "requester_id",
            "request_reason",
            "request_fingerprint",
        ):
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

        if self.candidate_audit_valid is not True:
            raise ValueError(
                "Authorization request requires "
                "a valid candidate store audit"
            )

        object.__setattr__(
            self,
            "requested_at",
            _normalized_datetime(
                self.requested_at
            ),
        )

        object.__setattr__(
            self,
            "risk_class",
            normalize_execution_risk_class(
                self.risk_class
            ),
        )

        for field_name in (
            "dry_run_required",
            "rollback_required",
            "verification_required",
        ):
            if not isinstance(
                getattr(
                    self,
                    field_name,
                ),
                bool,
            ):
                raise TypeError(
                    f"{field_name} must be a bool"
                )

        expected = (
            self.calculate_fingerprint()
        )

        if (
            self.request_fingerprint
            != expected
        ):
            raise ValueError(
                "Authorization request "
                "fingerprint mismatch"
            )

    @property
    def authorization_request_created(
        self,
    ) -> bool:
        return True

    @property
    def authorization_created(
        self,
    ) -> bool:
        return False

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
            "authorization_request_id":
                self.authorization_request_id,
            "authorization_candidate_id":
                self.authorization_candidate_id,
            "candidate_record_hash":
                self.candidate_record_hash,
            "candidate_fingerprint":
                self.candidate_fingerprint,
            "review_decision_id":
                self.review_decision_id,
            "review_record_hash":
                self.review_record_hash,
            "proposal_id":
                self.proposal_id,
            "proposal_record_hash":
                self.proposal_record_hash,
            "candidate_audit_id":
                self.candidate_audit_id,
            "candidate_audit_valid":
                self.candidate_audit_valid,
            "requester_id":
                self.requester_id,
            "requested_at":
                self.requested_at.isoformat(),
            "request_reason":
                self.request_reason,
            "risk_class":
                self.risk_class.value,
            "dry_run_required":
                self.dry_run_required,
            "rollback_required":
                self.rollback_required,
            "verification_required":
                self.verification_required,
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
            "request_fingerprint":
                self.request_fingerprint,
            "authorization_request_created":
                True,
            "authorization_created":
                False,
            "authorization_approved":
                False,
            "authorization_token_created":
                False,
            "execution_lease_created":
                False,
            "execution_allowed":
                False,
            "can_execute":
                False,
            "safety": {
                "controlled_authorization_request_only":
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
