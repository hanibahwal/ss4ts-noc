from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationType,
)
from app.models.notification_deduplication import (
    DeduplicationContext,
    DeduplicationDecision,
)
from app.models.notification_delivery_orchestration import (
    DeliveryExecutionResult,
)
from app.models.notification_escalation import (
    NotificationEscalationDecision,
    NotificationEscalationExecution,
)
from app.models.notification_retry import (
    NotificationRetryDecision,
)
from app.models.notification_suppression_engine import (
    NotificationSuppressionContext,
    NotificationSuppressionDecision,
)


class NotificationPipelineStatus(StrEnum):
    SENT = "sent"
    RETRY_SCHEDULED = "retry_scheduled"
    ESCALATED = "escalated"
    FAILED = "failed"

    DUPLICATE = "duplicate"
    SUPPRESSED = "suppressed"


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationPipelineRequest:
    incident_id: str

    policy_id: str | None

    channel: NotificationChannel
    destination: str

    subject: str
    body: str

    deduplication_context: DeduplicationContext
    suppression_context: NotificationSuppressionContext

    notification_type: NotificationType = (
        NotificationType.FIRING
    )

    recipient_id: str | None = None

    delivery_id: str | None = None

    escalation_policy_id: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    evaluated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.incident_id.strip():
            raise ValueError(
                "Pipeline incident ID must not "
                "be empty"
            )

        if not self.destination.strip():
            raise ValueError(
                "Pipeline destination must not "
                "be empty"
            )

        if not self.body.strip():
            raise ValueError(
                "Pipeline body must not be empty"
            )

        if (
            self.deduplication_context.incident_id
            != self.incident_id
        ):
            raise ValueError(
                "Deduplication incident does not "
                "match pipeline incident"
            )

        if (
            self.policy_id
            != self.deduplication_context.policy_id
        ):
            raise ValueError(
                "Deduplication policy does not "
                "match pipeline policy"
            )

        if (
            self.evaluated_at is not None
            and self.evaluated_at.tzinfo is None
        ):
            raise ValueError(
                "Pipeline evaluation time must "
                "be timezone-aware"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationPipelineResult:
    status: NotificationPipelineStatus
    request: NotificationPipelineRequest

    deduplication_decision: DeduplicationDecision

    suppression_decision: (
        NotificationSuppressionDecision | None
    ) = None

    delivery: NotificationDelivery | None = None

    execution: DeliveryExecutionResult | None = (
        None
    )

    retry_decision: (
        NotificationRetryDecision | None
    ) = None

    escalation_result: (
        NotificationEscalationDecision
        | NotificationEscalationExecution
        | None
    ) = None

    reason: str = ""

    @property
    def successful(self) -> bool:
        return (
            self.status
            is NotificationPipelineStatus.SENT
        )

    @property
    def stopped(self) -> bool:
        return self.status in {
            NotificationPipelineStatus.DUPLICATE,
            NotificationPipelineStatus.SUPPRESSED,
        }
