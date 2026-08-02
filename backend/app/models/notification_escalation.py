from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.models.notification import (
    NotificationDelivery,
    NotificationEscalationStep,
    NotificationIncident,
    NotificationRecipient,
)


class NotificationEscalationDecisionCode(
    StrEnum
):
    READY = "ready"
    NOT_DUE = "not_due"
    INCIDENT_INACTIVE = "incident_inactive"
    NO_POLICY = "no_policy"
    NO_STEPS = "no_steps"
    COMPLETE = "complete"
    RECIPIENT_NOT_FOUND = (
        "recipient_not_found"
    )
    RECIPIENT_DISABLED = (
        "recipient_disabled"
    )
    DUPLICATE = "duplicate"


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationEscalationDecision:
    code: NotificationEscalationDecisionCode
    incident: NotificationIncident

    should_escalate: bool

    policy_id: str | None = None

    step: NotificationEscalationStep | None = (
        None
    )

    recipient: NotificationRecipient | None = (
        None
    )

    due_at: datetime | None = None

    existing_delivery: (
        NotificationDelivery | None
    ) = None

    reason: str = ""

    def __post_init__(self) -> None:
        if self.should_escalate:
            if self.policy_id is None:
                raise ValueError(
                    "Escalation decision "
                    "requires a policy"
                )

            if self.step is None:
                raise ValueError(
                    "Escalation decision "
                    "requires a step"
                )

            if self.recipient is None:
                raise ValueError(
                    "Escalation decision "
                    "requires a recipient"
                )

            if self.due_at is None:
                raise ValueError(
                    "Escalation decision "
                    "requires a due time"
                )


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationEscalationExecution:
    decision: NotificationEscalationDecision

    incident: NotificationIncident
    delivery: NotificationDelivery

    @property
    def escalation_level(self) -> int:
        return (
            self.incident
            .current_escalation_level
        )
