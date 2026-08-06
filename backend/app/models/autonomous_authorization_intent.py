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
            "created_at must be a datetime"
        )

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _normalize_risk_class(
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

    if (
        normalized
        is ExecutionRiskClass.UNKNOWN
    ):
        raise ValueError(
            "risk_class must not be unknown"
        )

    return normalized


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousAuthorizationIntent:
    authorization_intent_id: str

    authorization_request_id: str
    request_record_hash: str
    request_fingerprint: str

    request_audit_id: str
    request_audit_valid: bool

    authorization_candidate_id: str
    candidate_record_hash: str
    candidate_fingerprint: str

    proposal_id: str
    proposal_record_hash: str

    requester_id: str
    requested_at: str
    request_reason: str

    risk_class: ExecutionRiskClass

    dry_run_required: bool
    rollback_required: bool
    verification_required: bool

    created_at: datetime
    bridge_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "authorization_intent_id",
            "authorization_request_id",
            "request_record_hash",
            "request_fingerprint",
            "request_audit_id",
            "authorization_candidate_id",
            "candidate_record_hash",
            "candidate_fingerprint",
            "proposal_id",
            "proposal_record_hash",
            "requester_id",
            "requested_at",
            "request_reason",
            "bridge_fingerprint",
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

        if (
            self.request_audit_valid
            is not True
        ):
            raise ValueError(
                "request_audit_valid must be true"
            )

        object.__setattr__(
            self,
            "risk_class",
            _normalize_risk_class(
                self.risk_class
            ),
        )

        object.__setattr__(
            self,
            "dry_run_required",
            bool(
                self.dry_run_required
            ),
        )

        object.__setattr__(
            self,
            "rollback_required",
            bool(
                self.rollback_required
            ),
        )

        object.__setattr__(
            self,
            "verification_required",
            bool(
                self.verification_required
            ),
        )

        object.__setattr__(
            self,
            "created_at",
            _normalized_datetime(
                self.created_at
            ),
        )

        expected = (
            self.calculate_fingerprint()
        )

        if (
            self.bridge_fingerprint
            != expected
        ):
            raise ValueError(
                "bridge_fingerprint does not "
                "match intent contents"
            )

    @property
    def authorization_request_verified(
        self,
    ) -> bool:
        return True

    @property
    def authorization_intent_created(
        self,
    ) -> bool:
        return True

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
            "authorization_intent_id":
                self.authorization_intent_id,
            "authorization_request_id":
                self.authorization_request_id,
            "request_record_hash":
                self.request_record_hash,
            "request_fingerprint":
                self.request_fingerprint,
            "request_audit_id":
                self.request_audit_id,
            "request_audit_valid":
                self.request_audit_valid,
            "authorization_candidate_id":
                self.authorization_candidate_id,
            "candidate_record_hash":
                self.candidate_record_hash,
            "candidate_fingerprint":
                self.candidate_fingerprint,
            "proposal_id":
                self.proposal_id,
            "proposal_record_hash":
                self.proposal_record_hash,
            "requester_id":
                self.requester_id,
            "requested_at":
                self.requested_at,
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
            "created_at":
                self.created_at.isoformat(),
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
            "bridge_fingerprint":
                self.bridge_fingerprint,
            "authorization_request_verified":
                True,
            "authorization_intent_created":
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
            "can_execute":
                False,
            "safety": {
                "authorization_intent_only":
                    True,
                "request_store_read_only":
                    True,
                "execution_authorization_created":
                    False,
                "execution_authorization_stored":
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
