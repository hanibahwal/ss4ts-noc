from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.models.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationIncidentStatus,
    NotificationType,
    new_notification_id,
)
from app.models.notification_escalation import (
    NotificationEscalationDecision,
    NotificationEscalationDecisionCode,
    NotificationEscalationExecution,
)
from app.services.notification_store import (
    NotificationDuplicate,
    NotificationNotFound,
    NotificationStore,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NotificationEscalationEngine:
    def __init__(
        self,
        store: NotificationStore,
    ) -> None:
        self._store = store

    def evaluate(
        self,
        incident_id: str,
        *,
        policy_id: str | None,
        evaluated_at: datetime | None = None,
    ) -> NotificationEscalationDecision:
        check_time = evaluated_at or _utc_now()

        if check_time.tzinfo is None:
            raise ValueError(
                "Escalation evaluation time "
                "must be timezone-aware"
            )

        incident = self._store.get_incident(
            incident_id
        )

        if incident is None:
            raise NotificationNotFound(
                f"Incident not found: {incident_id}"
            )

        if incident.status not in {
            NotificationIncidentStatus.OPEN,
            (
                NotificationIncidentStatus
                .ACKNOWLEDGED
            ),
        }:
            return NotificationEscalationDecision(
                code=(
                    NotificationEscalationDecisionCode
                    .INCIDENT_INACTIVE
                ),
                incident=incident,
                should_escalate=False,
                policy_id=policy_id,
                reason=(
                    "Resolved or suppressed "
                    "incidents cannot escalate"
                ),
            )

        if not policy_id:
            return NotificationEscalationDecision(
                code=(
                    NotificationEscalationDecisionCode
                    .NO_POLICY
                ),
                incident=incident,
                should_escalate=False,
                reason=(
                    "Escalation requires a "
                    "notification policy"
                ),
            )

        steps = self._store.list_escalation_steps(
            policy_id
        )

        if not steps:
            return NotificationEscalationDecision(
                code=(
                    NotificationEscalationDecisionCode
                    .NO_STEPS
                ),
                incident=incident,
                should_escalate=False,
                policy_id=policy_id,
                reason=(
                    "Notification policy has no "
                    "escalation steps"
                ),
            )

        next_level = (
            incident.current_escalation_level
            + 1
        )

        step = next(
            (
                candidate
                for candidate in steps
                if candidate.step_order
                == next_level
            ),
            None,
        )

        if step is None:
            return NotificationEscalationDecision(
                code=(
                    NotificationEscalationDecisionCode
                    .COMPLETE
                ),
                incident=incident,
                should_escalate=False,
                policy_id=policy_id,
                reason=(
                    "No additional escalation "
                    "level is available"
                ),
            )

        due_at = (
            incident.first_seen_at
            + timedelta(
                seconds=step.delay_seconds
            )
        )

        if check_time < due_at:
            return NotificationEscalationDecision(
                code=(
                    NotificationEscalationDecisionCode
                    .NOT_DUE
                ),
                incident=incident,
                should_escalate=False,
                policy_id=policy_id,
                step=step,
                due_at=due_at,
                reason=(
                    "Escalation step is not due"
                ),
            )

        recipient = self._store.get_recipient(
            step.recipient_id
        )

        if recipient is None:
            return NotificationEscalationDecision(
                code=(
                    NotificationEscalationDecisionCode
                    .RECIPIENT_NOT_FOUND
                ),
                incident=incident,
                should_escalate=False,
                policy_id=policy_id,
                step=step,
                due_at=due_at,
                reason=(
                    "Escalation recipient was "
                    "not found"
                ),
            )

        if not recipient.enabled:
            return NotificationEscalationDecision(
                code=(
                    NotificationEscalationDecisionCode
                    .RECIPIENT_DISABLED
                ),
                incident=incident,
                should_escalate=False,
                policy_id=policy_id,
                step=step,
                recipient=recipient,
                due_at=due_at,
                reason=(
                    "Escalation recipient is "
                    "disabled"
                ),
            )

        existing = (
            self._store
            .find_escalation_delivery(
                incident_id=incident_id,
                policy_id=policy_id,
                escalation_step_id=(
                    step.escalation_step_id
                ),
            )
        )

        if existing is not None:
            return NotificationEscalationDecision(
                code=(
                    NotificationEscalationDecisionCode
                    .DUPLICATE
                ),
                incident=incident,
                should_escalate=False,
                policy_id=policy_id,
                step=step,
                recipient=recipient,
                due_at=due_at,
                existing_delivery=existing,
                reason=(
                    "Escalation delivery already "
                    "exists"
                ),
            )

        return NotificationEscalationDecision(
            code=(
                NotificationEscalationDecisionCode
                .READY
            ),
            incident=incident,
            should_escalate=True,
            policy_id=policy_id,
            step=step,
            recipient=recipient,
            due_at=due_at,
            reason=(
                "Escalation step is ready"
            ),
        )

    def execute(
        self,
        decision: NotificationEscalationDecision,
        *,
        delivery_id: str | None = None,
        created_at: datetime | None = None,
    ) -> NotificationEscalationExecution:
        if not decision.should_escalate:
            raise ValueError(
                "Escalation decision is not "
                "executable"
            )

        step = decision.step
        recipient = decision.recipient
        policy_id = decision.policy_id

        if (
            step is None
            or recipient is None
            or policy_id is None
        ):
            raise ValueError(
                "Escalation decision is "
                "incomplete"
            )

        now = created_at or _utc_now()

        if now.tzinfo is None:
            raise ValueError(
                "Escalation creation time must "
                "be timezone-aware"
            )

        generated_delivery_id = (
            delivery_id
            or new_notification_id(
                "delivery"
            )
        )

        delivery = NotificationDelivery(
            delivery_id=generated_delivery_id,
            incident_id=(
                decision.incident.incident_id
            ),
            policy_id=policy_id,
            recipient_id=(
                recipient.recipient_id
            ),
            channel=step.channel,
            notification_type=(
                NotificationType.ESCALATION
            ),
            status=(
                NotificationDeliveryStatus.PENDING
            ),
            destination=recipient.address,
            scheduled_at=now,
            metadata={
                **step.metadata,
                "escalation_step_id": (
                    step.escalation_step_id
                ),
                "escalation_level": (
                    step.step_order
                ),
                "source_incident_id": (
                    decision.incident
                    .incident_id
                ),
            },
            created_at=now,
            updated_at=now,
        )

        try:
            self._store.create_delivery(
                delivery
            )
        except NotificationDuplicate:
            raise
        except Exception:
            existing = (
                self._store
                .find_escalation_delivery(
                    incident_id=(
                        decision.incident
                        .incident_id
                    ),
                    policy_id=policy_id,
                    escalation_step_id=(
                        step.escalation_step_id
                    ),
                )
            )

            if existing is not None:
                raise NotificationDuplicate(
                    "Escalation delivery already "
                    "exists"
                )

            raise

        try:
            updated_incident = (
                self._store
                .update_incident_escalation_level(
                    decision.incident.incident_id,
                    escalation_level=(
                        step.step_order
                    ),
                    expected_version=(
                        decision.incident
                        .record_version
                    ),
                )
            )
        except Exception:
            try:
                self._store.cancel_delivery(
                    delivery.delivery_id,
                    reason=(
                        "Escalation incident "
                        "update failed"
                    ),
                )
            except Exception:
                pass

            raise

        return NotificationEscalationExecution(
            decision=decision,
            incident=updated_incident,
            delivery=delivery,
        )

    def evaluate_and_execute(
        self,
        incident_id: str,
        *,
        policy_id: str | None,
        evaluated_at: datetime | None = None,
        delivery_id: str | None = None,
    ) -> (
        NotificationEscalationExecution
        | NotificationEscalationDecision
    ):
        decision = self.evaluate(
            incident_id,
            policy_id=policy_id,
            evaluated_at=evaluated_at,
        )

        if not decision.should_escalate:
            return decision

        return self.execute(
            decision,
            delivery_id=delivery_id,
            created_at=evaluated_at,
        )


def evaluate_notification_escalation(
    store: NotificationStore,
    incident_id: str,
    *,
    policy_id: str | None,
    evaluated_at: datetime | None = None,
) -> NotificationEscalationDecision:
    return NotificationEscalationEngine(
        store
    ).evaluate(
        incident_id,
        policy_id=policy_id,
        evaluated_at=evaluated_at,
    )
