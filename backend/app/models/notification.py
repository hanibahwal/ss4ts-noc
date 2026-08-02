from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_notification_id(prefix: str) -> str:
    normalized_prefix = str(prefix).strip().lower()

    if not normalized_prefix:
        raise ValueError(
            "Notification ID prefix must not be empty"
        )

    return f"{normalized_prefix}:{uuid4()}"


class NotificationChannel(StrEnum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    TELEGRAM = "telegram"
    DASHBOARD = "dashboard"
    WEBHOOK = "webhook"


class NotificationIncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class NotificationDeliveryStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(StrEnum):
    FIRING = "firing"
    REMINDER = "reminder"
    ESCALATION = "escalation"
    RECOVERY = "recovery"


class NotificationSuppressionKind(StrEnum):
    MANUAL = "manual"
    MAINTENANCE = "maintenance"
    QUIET_HOURS = "quiet_hours"


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationPolicy:
    policy_id: str
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = 100

    minimum_duration_seconds: int = 0
    cooldown_seconds: int = 900

    send_recovery: bool = True
    stop_processing: bool = False

    conditions: dict[str, Any] = field(
        default_factory=dict
    )
    actions: dict[str, Any] = field(
        default_factory=dict
    )

    record_version: int = 1

    created_at: datetime = field(
        default_factory=utc_now
    )
    updated_at: datetime = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError(
                "Policy ID must not be empty"
            )

        if not self.name.strip():
            raise ValueError(
                "Policy name must not be empty"
            )

        if self.priority < 0:
            raise ValueError(
                "Policy priority must be non-negative"
            )

        if self.minimum_duration_seconds < 0:
            raise ValueError(
                "Minimum duration must be non-negative"
            )

        if self.cooldown_seconds < 0:
            raise ValueError(
                "Cooldown must be non-negative"
            )

        if self.record_version < 1:
            raise ValueError(
                "Policy record version must be positive"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationRecipient:
    recipient_id: str
    name: str
    channel: NotificationChannel
    address: str
    enabled: bool = True

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=utc_now
    )
    updated_at: datetime = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.recipient_id.strip():
            raise ValueError(
                "Recipient ID must not be empty"
            )

        if not self.name.strip():
            raise ValueError(
                "Recipient name must not be empty"
            )

        if not self.address.strip():
            raise ValueError(
                "Recipient address must not be empty"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationEscalationStep:
    escalation_step_id: str
    policy_id: str

    step_order: int
    delay_seconds: int

    channel: NotificationChannel
    recipient_id: str

    repeat_interval_seconds: int | None = None
    max_repeats: int = 0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.escalation_step_id.strip():
            raise ValueError(
                "Escalation step ID must not be empty"
            )

        if not self.policy_id.strip():
            raise ValueError(
                "Escalation policy ID must not be empty"
            )

        if self.step_order < 1:
            raise ValueError(
                "Escalation step order must be positive"
            )

        if self.delay_seconds < 0:
            raise ValueError(
                "Escalation delay must be non-negative"
            )

        if (
            self.repeat_interval_seconds is not None
            and self.repeat_interval_seconds < 1
        ):
            raise ValueError(
                "Repeat interval must be positive"
            )

        if self.max_repeats < 0:
            raise ValueError(
                "Maximum repeats must be non-negative"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationIncident:
    incident_id: str
    fingerprint: str
    correlation_id: str

    event_type: str
    severity: str
    status: NotificationIncidentStatus

    title: str
    message: str

    device_id: str | None = None
    site_id: str | None = None
    interface_id: str | None = None

    occurrence_count: int = 1
    current_escalation_level: int = 0

    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None

    resolved_by: str | None = None
    resolved_at: datetime | None = None

    first_seen_at: datetime = field(
        default_factory=utc_now
    )
    last_seen_at: datetime = field(
        default_factory=utc_now
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    record_version: int = 1

    created_at: datetime = field(
        default_factory=utc_now
    )
    updated_at: datetime = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.incident_id.strip():
            raise ValueError(
                "Incident ID must not be empty"
            )

        if not self.fingerprint.strip():
            raise ValueError(
                "Incident fingerprint must not be empty"
            )

        if not self.correlation_id.strip():
            raise ValueError(
                "Correlation ID must not be empty"
            )

        if not self.event_type.strip():
            raise ValueError(
                "Incident event type must not be empty"
            )

        if not self.severity.strip():
            raise ValueError(
                "Incident severity must not be empty"
            )

        if not self.title.strip():
            raise ValueError(
                "Incident title must not be empty"
            )

        if not self.message.strip():
            raise ValueError(
                "Incident message must not be empty"
            )

        if self.occurrence_count < 1:
            raise ValueError(
                "Occurrence count must be positive"
            )

        if self.current_escalation_level < 0:
            raise ValueError(
                "Escalation level must be non-negative"
            )

        if self.record_version < 1:
            raise ValueError(
                "Incident record version must be positive"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationDelivery:
    delivery_id: str
    incident_id: str

    channel: NotificationChannel
    notification_type: NotificationType
    status: NotificationDeliveryStatus

    destination: str

    policy_id: str | None = None
    recipient_id: str | None = None

    attempt_count: int = 0

    provider_message_id: str | None = None
    error_message: str | None = None

    scheduled_at: datetime | None = None
    sent_at: datetime | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=utc_now
    )
    updated_at: datetime = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.delivery_id.strip():
            raise ValueError(
                "Delivery ID must not be empty"
            )

        if not self.incident_id.strip():
            raise ValueError(
                "Delivery incident ID must not be empty"
            )

        if not self.destination.strip():
            raise ValueError(
                "Delivery destination must not be empty"
            )

        if self.attempt_count < 0:
            raise ValueError(
                "Delivery attempt count must be non-negative"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationSuppression:
    suppression_id: str
    name: str
    kind: NotificationSuppressionKind

    enabled: bool
    starts_at: datetime
    ends_at: datetime

    reason: str = ""

    event_types: tuple[str, ...] = ()
    site_ids: tuple[str, ...] = ()
    device_ids: tuple[str, ...] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=utc_now
    )
    updated_at: datetime = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.suppression_id.strip():
            raise ValueError(
                "Suppression ID must not be empty"
            )

        if not self.name.strip():
            raise ValueError(
                "Suppression name must not be empty"
            )

        if self.ends_at <= self.starts_at:
            raise ValueError(
                "Suppression end time must be after start time"
            )
