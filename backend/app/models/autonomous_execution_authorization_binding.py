from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from app.models.execution_authorization import (
    AuthorizationDecision,
    AuthorizationStatus,
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


def _require_text(
    field_name: str,
    value: str,
) -> str:
    normalized = str(
        value
    ).strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def _require_hash(
    field_name: str,
    value: str,
) -> str:
    normalized = _require_text(
        field_name,
        value,
    ).lower()

    if (
        len(normalized) != 64
        or any(
            character not in "0123456789abcdef"
            for character in normalized
        )
    ):
        raise ValueError(
            f"{field_name} must be a 64-character "
            "SHA-256 hexadecimal value"
        )

    return normalized


def _require_aware_datetime(
    field_name: str,
    value: datetime,
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
class AutonomousExecutionAuthorizationBinding:
    """
    Immutable non-executable binding between one verified
    autonomous authorization intent and one existing execution
    authorization identity.

    This contract does not create, approve, store, consume, or
    execute an ExecutionAuthorization. It records identity and
    integrity bindings only.
    """

    binding_id: str

    authorization_intent_id: str
    intent_record_hash: str
    intent_bridge_fingerprint: str
    intent_audit_id: str
    intent_audit_valid: bool

    execution_authorization_id: str
    plan_id: str
    decision_id: str

    risk_class: ExecutionRiskClass
    authorization_status: AuthorizationStatus
    authorization_decision: AuthorizationDecision

    created_at: datetime
    expires_at: datetime

    binding_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "binding_id",
            _require_text(
                "binding_id",
                self.binding_id,
            ),
        )

        object.__setattr__(
            self,
            "authorization_intent_id",
            _require_text(
                "authorization_intent_id",
                self.authorization_intent_id,
            ),
        )

        object.__setattr__(
            self,
            "intent_record_hash",
            _require_hash(
                "intent_record_hash",
                self.intent_record_hash,
            ),
        )

        object.__setattr__(
            self,
            "intent_bridge_fingerprint",
            _require_hash(
                "intent_bridge_fingerprint",
                self.intent_bridge_fingerprint,
            ),
        )

        object.__setattr__(
            self,
            "intent_audit_id",
            _require_text(
                "intent_audit_id",
                self.intent_audit_id,
            ),
        )

        if self.intent_audit_valid is not True:
            raise ValueError(
                "intent_audit_valid must be true"
            )

        object.__setattr__(
            self,
            "execution_authorization_id",
            _require_text(
                "execution_authorization_id",
                self.execution_authorization_id,
            ),
        )

        object.__setattr__(
            self,
            "plan_id",
            _require_text(
                "plan_id",
                self.plan_id,
            ),
        )

        object.__setattr__(
            self,
            "decision_id",
            _require_text(
                "decision_id",
                self.decision_id,
            ),
        )

        if not isinstance(
            self.risk_class,
            ExecutionRiskClass,
        ):
            raise TypeError(
                "risk_class must be an ExecutionRiskClass"
            )

        if (
            self.risk_class
            is ExecutionRiskClass.UNKNOWN
        ):
            raise ValueError(
                "risk_class must not be unknown"
            )

        if not isinstance(
            self.authorization_status,
            AuthorizationStatus,
        ):
            raise TypeError(
                "authorization_status must be an "
                "AuthorizationStatus"
            )

        if not isinstance(
            self.authorization_decision,
            AuthorizationDecision,
        ):
            raise TypeError(
                "authorization_decision must be an "
                "AuthorizationDecision"
            )

        # H25.1.1 is binding-only. An already approved or directly
        # allowed authorization must never enter this contract.
        if (
            self.authorization_status
            is not AuthorizationStatus.PENDING
        ):
            raise ValueError(
                "authorization_status must be pending"
            )

        if (
            self.authorization_decision
            is not AuthorizationDecision.REQUIRE_APPROVAL
        ):
            raise ValueError(
                "authorization_decision must require approval"
            )

        normalized_created_at = (
            _require_aware_datetime(
                "created_at",
                self.created_at,
            )
        )

        normalized_expires_at = (
            _require_aware_datetime(
                "expires_at",
                self.expires_at,
            )
        )

        if (
            normalized_expires_at
            <= normalized_created_at
        ):
            raise ValueError(
                "expires_at must be later than created_at"
            )

        object.__setattr__(
            self,
            "created_at",
            normalized_created_at,
        )

        object.__setattr__(
            self,
            "expires_at",
            normalized_expires_at,
        )

        normalized_fingerprint = (
            _require_hash(
                "binding_fingerprint",
                self.binding_fingerprint,
            )
        )

        object.__setattr__(
            self,
            "binding_fingerprint",
            normalized_fingerprint,
        )

        expected = (
            self.calculate_fingerprint()
        )

        if normalized_fingerprint != expected:
            raise ValueError(
                "binding_fingerprint does not match "
                "binding contents"
            )

    @property
    def execution_authorization_created(
        self,
    ) -> bool:
        return True

    @property
    def authorization_binding_created(
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
            "binding_id":
                self.binding_id,
            "authorization_intent_id":
                self.authorization_intent_id,
            "intent_record_hash":
                self.intent_record_hash,
            "intent_bridge_fingerprint":
                self.intent_bridge_fingerprint,
            "intent_audit_id":
                self.intent_audit_id,
            "intent_audit_valid":
                self.intent_audit_valid,
            "execution_authorization_id":
                self.execution_authorization_id,
            "plan_id":
                self.plan_id,
            "decision_id":
                self.decision_id,
            "risk_class":
                self.risk_class.value,
            "authorization_status":
                self.authorization_status.value,
            "authorization_decision":
                self.authorization_decision.value,
            "created_at":
                self.created_at.isoformat(),
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
            "binding_fingerprint":
                self.binding_fingerprint,
            "execution_authorization_created":
                True,
            "authorization_binding_created":
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
                "authorization_binding_only":
                    True,
                "execution_authorization_created":
                    True,
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
