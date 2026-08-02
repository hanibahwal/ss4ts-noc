from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class DeduplicationDecisionCode(StrEnum):
    ALLOWED_FIRST_NOTIFICATION = "allowed_first_notification"
    ALLOWED_COOLDOWN_EXPIRED = "allowed_cooldown_expired"
    ALLOWED_COOLDOWN_DISABLED = "allowed_cooldown_disabled"
    ALLOWED_SEVERITY_INCREASED = "allowed_severity_increased"
    ALLOWED_RECOVERY = "allowed_recovery"
    ALLOWED_ESCALATION = "allowed_escalation"
    ALLOWED_FORCED = "allowed_forced"

    BLOCKED_COOLDOWN_ACTIVE = "blocked_cooldown_active"
    BLOCKED_DUPLICATE_PENDING = "blocked_duplicate_pending"

    INVALID_REQUEST = "invalid_request"


@dataclass(
    frozen=True,
    slots=True,
)
class DeduplicationDecision:
    allowed: bool
    code: DeduplicationDecisionCode
    reason: str

    incident_id: str
    policy_id: str | None
    notification_type: str
    evaluated_at: datetime

    cooldown_seconds: int = 0
    elapsed_seconds: float | None = None
    remaining_seconds: float | None = None

    last_delivery_id: str | None = None
    last_delivery_at: datetime | None = None
    next_allowed_at: datetime | None = None

    previous_severity: str | None = None
    current_severity: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(
    frozen=True,
    slots=True,
)
class DeduplicationContext:
    incident_id: str
    notification_type: str
    current_severity: str

    policy_id: str | None = None
    cooldown_seconds: int = 0
    force: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        incident_id = self.incident_id.strip()
        notification_type = self.notification_type.strip()
        current_severity = self.current_severity.strip()

        if not incident_id:
            raise ValueError(
                "Deduplication incident ID must not be empty"
            )

        if not notification_type:
            raise ValueError(
                "Notification type must not be empty"
            )

        if not current_severity:
            raise ValueError(
                "Current severity must not be empty"
            )

        if self.cooldown_seconds < 0:
            raise ValueError(
                "Cooldown seconds must be non-negative"
            )
