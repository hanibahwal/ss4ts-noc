from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Any


class AuthorizationStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    USED = "used"
    UNKNOWN = "unknown"


class AuthorizationDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_DRY_RUN = "require_dry_run"
    UNKNOWN = "unknown"


class ExecutionRiskClass(StrEnum):
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ApprovalRole(StrEnum):
    REQUESTER = "requester"
    NETWORK_ENGINEER = "network_engineer"
    SENIOR_ENGINEER = "senior_engineer"
    CHANGE_MANAGER = "change_manager"
    ADMINISTRATOR = "administrator"
    UNKNOWN = "unknown"


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _optional_text(
    value: Any,
) -> str | None:
    text = _text(value)

    return text or None


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(number):
        return default

    return number


def _boolean(
    value: Any,
    default: bool = False,
) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    normalized = str(value).strip().lower()

    if normalized in {
        "true",
        "1",
        "yes",
        "on",
        "enabled",
        "approved",
        "allow",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "off",
        "disabled",
        "rejected",
        "deny",
    }:
        return False

    return default


def _datetime(
    value: Any,
) -> datetime:
    if isinstance(value, datetime):
        return value

    text = _text(value)

    if text:
        try:
            parsed = datetime.fromisoformat(
                text.replace(
                    "Z",
                    "+00:00",
                )
            )

            if parsed.tzinfo is None:
                return parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed
        except ValueError:
            pass

    return datetime.now(
        timezone.utc
    )


def _enum_value(
    enum_type,
    value: Any,
    default,
):
    normalized = _text(
        value,
        default.value,
    ).lower().replace(
        "-",
        "_",
    )

    try:
        return enum_type(
            normalized
        )
    except ValueError:
        return default


@dataclass(slots=True)
class ApprovalIdentity:
    identity_id: str
    display_name: str
    role: ApprovalRole

    email: str | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.identity_id = _text(
            self.identity_id
        )

        self.display_name = _text(
            self.display_name
        )

        self.role = _enum_value(
            ApprovalRole,
            self.role,
            ApprovalRole.UNKNOWN,
        )

        self.email = _optional_text(
            self.email
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.identity_id:
            raise ValueError(
                "Approval identity_id must not be empty"
            )

        if not self.display_name:
            raise ValueError(
                "Approval display_name must not be empty"
            )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "identity_id":
                self.identity_id,
            "display_name":
                self.display_name,
            "role":
                self.role.value,
            "email":
                self.email,
            "metadata":
                dict(self.metadata),
        }


@dataclass(slots=True)
class ExecutionAuthorization:
    authorization_id: str
    plan_id: str
    decision_id: str
    source_node_id: str

    requester: ApprovalIdentity

    risk_class: ExecutionRiskClass

    status: AuthorizationStatus = (
        AuthorizationStatus.PENDING
    )

    decision: AuthorizationDecision = (
        AuthorizationDecision.REQUIRE_APPROVAL
    )

    requested_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    expires_at: datetime | None = None

    approver: ApprovalIdentity | None = None
    approved_at: datetime | None = None

    rejection_reason: str | None = None
    revocation_reason: str | None = None

    dry_run_required: bool = True
    rollback_required: bool = True
    verification_required: bool = True

    execution_allowed: bool = False
    one_time_use: bool = True
    consumed: bool = False

    confidence_percent: float = 0.0

    policy_reasons: list[
        str
    ] = field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.authorization_id = _text(
            self.authorization_id
        )

        self.plan_id = _text(
            self.plan_id
        )

        self.decision_id = _text(
            self.decision_id
        )

        self.source_node_id = _text(
            self.source_node_id
        )

        if not isinstance(
            self.requester,
            ApprovalIdentity,
        ):
            raise TypeError(
                "requester must be an ApprovalIdentity"
            )

        self.risk_class = _enum_value(
            ExecutionRiskClass,
            self.risk_class,
            ExecutionRiskClass.UNKNOWN,
        )

        self.status = _enum_value(
            AuthorizationStatus,
            self.status,
            AuthorizationStatus.UNKNOWN,
        )

        self.decision = _enum_value(
            AuthorizationDecision,
            self.decision,
            AuthorizationDecision.UNKNOWN,
        )

        self.requested_at = _datetime(
            self.requested_at
        )

        if self.expires_at is not None:
            self.expires_at = _datetime(
                self.expires_at
            )

        if (
            self.approver is not None
            and not isinstance(
                self.approver,
                ApprovalIdentity,
            )
        ):
            raise TypeError(
                "approver must be an ApprovalIdentity"
            )

        if self.approved_at is not None:
            self.approved_at = _datetime(
                self.approved_at
            )

        self.rejection_reason = _optional_text(
            self.rejection_reason
        )

        self.revocation_reason = _optional_text(
            self.revocation_reason
        )

        self.dry_run_required = _boolean(
            self.dry_run_required,
            True,
        )

        self.rollback_required = _boolean(
            self.rollback_required,
            True,
        )

        self.verification_required = _boolean(
            self.verification_required,
            True,
        )

        self.execution_allowed = _boolean(
            self.execution_allowed
        )

        self.one_time_use = _boolean(
            self.one_time_use,
            True,
        )

        self.consumed = _boolean(
            self.consumed
        )

        self.confidence_percent = round(
            max(
                0.0,
                min(
                    _number(
                        self.confidence_percent
                    ),
                    100.0,
                ),
            ),
            2,
        )

        self.policy_reasons = list(
            dict.fromkeys(
                _text(item)
                for item in self.policy_reasons
                if _text(item)
            )
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.authorization_id:
            raise ValueError(
                "authorization_id must not be empty"
            )

        if not self.plan_id:
            raise ValueError(
                "authorization plan_id must not be empty"
            )

        if not self.decision_id:
            raise ValueError(
                "authorization decision_id must not be empty"
            )

        if not self.source_node_id:
            raise ValueError(
                "authorization source_node_id must not be empty"
            )

        if (
            self.status
            == AuthorizationStatus.APPROVED
            and self.approver is None
        ):
            raise ValueError(
                "Approved authorization requires an approver"
            )

        if (
            self.status
            == AuthorizationStatus.APPROVED
            and self.approved_at is None
        ):
            raise ValueError(
                "Approved authorization requires approved_at"
            )

        if (
            self.status
            == AuthorizationStatus.REJECTED
            and not self.rejection_reason
        ):
            raise ValueError(
                "Rejected authorization requires a reason"
            )

        if (
            self.status
            == AuthorizationStatus.REVOKED
            and not self.revocation_reason
        ):
            raise ValueError(
                "Revoked authorization requires a reason"
            )

        if (
            self.execution_allowed
            and self.status
            != AuthorizationStatus.APPROVED
        ):
            raise ValueError(
                "Execution cannot be allowed without approval"
            )

        if (
            self.consumed
            and self.status
            not in {
                AuthorizationStatus.USED,
                AuthorizationStatus.REVOKED,
            }
        ):
            raise ValueError(
                "Consumed authorization must be used or revoked"
            )

        if (
            self.risk_class
            in {
                ExecutionRiskClass.HIGH,
                ExecutionRiskClass.CRITICAL,
            }
            and not self.rollback_required
        ):
            raise ValueError(
                "High-risk authorization requires rollback"
            )

        if (
            self.risk_class
            in {
                ExecutionRiskClass.HIGH,
                ExecutionRiskClass.CRITICAL,
            }
            and not self.verification_required
        ):
            raise ValueError(
                "High-risk authorization requires verification"
            )

    @property
    def is_expired(
        self,
    ) -> bool:
        if self.expires_at is None:
            return False

        return (
            datetime.now(
                timezone.utc
            )
            >= self.expires_at
        )

    @property
    def is_usable(
        self,
    ) -> bool:
        return (
            self.status
            == AuthorizationStatus.APPROVED
            and self.decision
            == AuthorizationDecision.ALLOW
            and self.execution_allowed
            and not self.is_expired
            and not self.consumed
        )

    @property
    def requires_human_approval(
        self,
    ) -> bool:
        return (
            self.decision
            == AuthorizationDecision.REQUIRE_APPROVAL
            or self.status
            == AuthorizationStatus.PENDING
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "authorization_id":
                self.authorization_id,
            "plan_id":
                self.plan_id,
            "decision_id":
                self.decision_id,
            "source_node_id":
                self.source_node_id,
            "requester":
                self.requester.to_dict(),
            "approver": (
                self.approver.to_dict()
                if self.approver
                else None
            ),
            "risk_class":
                self.risk_class.value,
            "status":
                self.status.value,
            "decision":
                self.decision.value,
            "requested_at":
                self.requested_at.isoformat(),
            "approved_at": (
                self.approved_at.isoformat()
                if self.approved_at
                else None
            ),
            "expires_at": (
                self.expires_at.isoformat()
                if self.expires_at
                else None
            ),
            "rejection_reason":
                self.rejection_reason,
            "revocation_reason":
                self.revocation_reason,
            "dry_run_required":
                self.dry_run_required,
            "rollback_required":
                self.rollback_required,
            "verification_required":
                self.verification_required,
            "execution_allowed":
                self.execution_allowed,
            "one_time_use":
                self.one_time_use,
            "consumed":
                self.consumed,
            "confidence_percent":
                self.confidence_percent,
            "policy_reasons":
                list(self.policy_reasons),
            "is_expired":
                self.is_expired,
            "is_usable":
                self.is_usable,
            "requires_human_approval":
                self.requires_human_approval,
            "metadata":
                dict(self.metadata),
        }
