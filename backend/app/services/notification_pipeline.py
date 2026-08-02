from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from app.models.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    new_notification_id,
)
from app.models.notification_escalation import (
    NotificationEscalationExecution,
)
from app.models.notification_pipeline import (
    NotificationPipelineRequest,
    NotificationPipelineResult,
    NotificationPipelineStatus,
)
from app.models.notification_retry import (
    NotificationRetryDecisionCode,
)
from app.services.notification_deduplication import (
    NotificationDeduplicationEngine,
)
from app.services.notification_delivery_orchestrator import (
    NotificationDeliveryOrchestrator,
)
from app.services.notification_dispatcher import (
    NotificationDispatcher,
)
from app.services.notification_escalation import (
    NotificationEscalationEngine,
)
from app.services.notification_retry import (
    NotificationRetryEngine,
)
from app.services.notification_store import (
    NotificationStore,
)
from app.services.notification_suppression import (
    NotificationSuppressionEngine,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NotificationPipeline:
    def __init__(
        self,
        store: NotificationStore,
        dispatcher: NotificationDispatcher,
        *,
        retry_engine: (
            NotificationRetryEngine | None
        ) = None,
    ) -> None:
        self._store = store

        self._deduplication = (
            NotificationDeduplicationEngine(
                store
            )
        )

        self._suppression = (
            NotificationSuppressionEngine(
                store
            )
        )

        self._orchestrator = (
            NotificationDeliveryOrchestrator(
                store,
                dispatcher,
            )
        )

        self._retry = (
            retry_engine
            or NotificationRetryEngine()
        )

        self._escalation = (
            NotificationEscalationEngine(
                store
            )
        )

    def execute(
        self,
        request: NotificationPipelineRequest,
    ) -> NotificationPipelineResult:
        evaluated_at = (
            request.evaluated_at
            or request
            .suppression_context
            .evaluated_at
        )

        if evaluated_at.tzinfo is None:
            raise ValueError(
                "Pipeline evaluation time must "
                "be timezone-aware"
            )

        deduplication_decision = (
            self._deduplication.evaluate(
                request.deduplication_context,
                evaluated_at=evaluated_at,
            )
        )

        if not deduplication_decision.allowed:
            return NotificationPipelineResult(
                status=(
                    NotificationPipelineStatus
                    .DUPLICATE
                ),
                request=request,
                deduplication_decision=(
                    deduplication_decision
                ),
                reason=(
                    deduplication_decision.reason
                ),
            )

        suppression_decision = (
            self._suppression.evaluate(
                request.suppression_context
            )
        )

        if suppression_decision.suppressed:
            return NotificationPipelineResult(
                status=(
                    NotificationPipelineStatus
                    .SUPPRESSED
                ),
                request=request,
                deduplication_decision=(
                    deduplication_decision
                ),
                suppression_decision=(
                    suppression_decision
                ),
                reason=(
                    suppression_decision.reason
                ),
            )

        delivery = NotificationDelivery(
            delivery_id=(
                request.delivery_id
                or new_notification_id(
                    "delivery"
                )
            ),
            incident_id=request.incident_id,
            policy_id=request.policy_id,
            recipient_id=request.recipient_id,
            channel=request.channel,
            notification_type=(
                request.notification_type
            ),
            status=(
                NotificationDeliveryStatus.PENDING
            ),
            destination=request.destination,
            scheduled_at=evaluated_at,
            metadata={
                **request.metadata,
                "severity": (
                    request
                    .deduplication_context
                    .current_severity
                ),
                "pipeline": True,
            },
            created_at=evaluated_at,
            updated_at=evaluated_at,
        )

        self._store.create_delivery(
            delivery
        )

        execution = self._orchestrator.execute(
            delivery.delivery_id,
            body=request.body,
            subject=request.subject,
            metadata={
                **request.metadata,
                "pipeline": True,
            },
        )

        if execution.successful:
            return NotificationPipelineResult(
                status=(
                    NotificationPipelineStatus
                    .SENT
                ),
                request=request,
                deduplication_decision=(
                    deduplication_decision
                ),
                suppression_decision=(
                    suppression_decision
                ),
                delivery=execution.delivery,
                execution=execution,
                reason=(
                    "Notification delivered "
                    "successfully"
                ),
            )

        retry_decision = (
            self._retry
            .evaluate_and_schedule(
                self._store,
                execution,
                evaluated_at=evaluated_at,
            )
        )

        if retry_decision.should_retry:
            scheduled_delivery = (
                self._store.get_delivery(
                    delivery.delivery_id
                )
            )

            return NotificationPipelineResult(
                status=(
                    NotificationPipelineStatus
                    .RETRY_SCHEDULED
                ),
                request=request,
                deduplication_decision=(
                    deduplication_decision
                ),
                suppression_decision=(
                    suppression_decision
                ),
                delivery=scheduled_delivery,
                execution=execution,
                retry_decision=retry_decision,
                reason=retry_decision.reason,
            )

        escalation_result = None

        if (
            retry_decision.code
            is NotificationRetryDecisionCode
            .MAX_ATTEMPTS_REACHED
            and request.escalation_policy_id
        ):
            escalation_result = (
                self._escalation
                .evaluate_and_execute(
                    request.incident_id,
                    policy_id=(
                        request
                        .escalation_policy_id
                    ),
                    evaluated_at=evaluated_at,
                )
            )

            if isinstance(
                escalation_result,
                NotificationEscalationExecution,
            ):
                return NotificationPipelineResult(
                    status=(
                        NotificationPipelineStatus
                        .ESCALATED
                    ),
                    request=request,
                    deduplication_decision=(
                        deduplication_decision
                    ),
                    suppression_decision=(
                        suppression_decision
                    ),
                    delivery=execution.delivery,
                    execution=execution,
                    retry_decision=retry_decision,
                    escalation_result=(
                        escalation_result
                    ),
                    reason=(
                        "Maximum attempts reached; "
                        "notification escalated"
                    ),
                )

        return NotificationPipelineResult(
            status=(
                NotificationPipelineStatus
                .FAILED
            ),
            request=request,
            deduplication_decision=(
                deduplication_decision
            ),
            suppression_decision=(
                suppression_decision
            ),
            delivery=execution.delivery,
            execution=execution,
            retry_decision=retry_decision,
            escalation_result=escalation_result,
            reason=(
                execution.error_message
                or retry_decision.reason
                or "Notification pipeline failed"
            ),
        )


def execute_notification_pipeline(
    store: NotificationStore,
    dispatcher: NotificationDispatcher,
    request: NotificationPipelineRequest,
    *,
    retry_engine: (
        NotificationRetryEngine | None
    ) = None,
) -> NotificationPipelineResult:
    return NotificationPipeline(
        store,
        dispatcher,
        retry_engine=retry_engine,
    ).execute(request)
