from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.models.notification import (
    NotificationDelivery,
    NotificationDeliveryStatus,
)
from app.models.notification_delivery_orchestration import (
    DeliveryExecutionResult,
)
from app.models.notification_retry import (
    NotificationRetryDecision,
    NotificationRetryDecisionCode,
    NotificationRetryPolicy,
)
from app.services.notification_store import (
    NotificationStore,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NotificationRetryEngine:
    def __init__(
        self,
        policy: NotificationRetryPolicy
        | None = None,
    ) -> None:
        self.policy = (
            policy
            or NotificationRetryPolicy()
        )

    def calculate_delay_seconds(
        self,
        attempt_count: int,
    ) -> float:
        if attempt_count < 1:
            raise ValueError(
                "Attempt count must be positive "
                "when calculating retry delay"
            )

        calculated = (
            self.policy.initial_delay_seconds
            * (
                self.policy.backoff_multiplier
                ** (attempt_count - 1)
            )
        )

        return min(
            calculated,
            self.policy.max_delay_seconds,
        )

    def evaluate(
        self,
        delivery: NotificationDelivery,
        *,
        retryable: bool,
        evaluated_at: datetime | None = None,
    ) -> NotificationRetryDecision:
        check_time = evaluated_at or _utc_now()

        if check_time.tzinfo is None:
            raise ValueError(
                "Retry evaluation time must be "
                "timezone-aware"
            )

        if not self.policy.enabled:
            return NotificationRetryDecision(
                code=(
                    NotificationRetryDecisionCode
                    .DISABLED
                ),
                delivery=delivery,
                should_retry=False,
                retryable=retryable,
                attempt_count=(
                    delivery.attempt_count
                ),
                max_attempts=(
                    self.policy.max_attempts
                ),
                reason=(
                    "Notification retry policy "
                    "is disabled"
                ),
            )

        if (
            delivery.status
            is not NotificationDeliveryStatus.FAILED
        ):
            return NotificationRetryDecision(
                code=(
                    NotificationRetryDecisionCode
                    .DELIVERY_NOT_FAILED
                ),
                delivery=delivery,
                should_retry=False,
                retryable=retryable,
                attempt_count=(
                    delivery.attempt_count
                ),
                max_attempts=(
                    self.policy.max_attempts
                ),
                reason=(
                    "Only failed deliveries can "
                    "be retried"
                ),
            )

        if not retryable:
            return NotificationRetryDecision(
                code=(
                    NotificationRetryDecisionCode
                    .NOT_RETRYABLE
                ),
                delivery=delivery,
                should_retry=False,
                retryable=False,
                attempt_count=(
                    delivery.attempt_count
                ),
                max_attempts=(
                    self.policy.max_attempts
                ),
                reason=(
                    "Delivery failure is not "
                    "retryable"
                ),
            )

        if (
            delivery.attempt_count
            >= self.policy.max_attempts
        ):
            return NotificationRetryDecision(
                code=(
                    NotificationRetryDecisionCode
                    .MAX_ATTEMPTS_REACHED
                ),
                delivery=delivery,
                should_retry=False,
                retryable=True,
                attempt_count=(
                    delivery.attempt_count
                ),
                max_attempts=(
                    self.policy.max_attempts
                ),
                reason=(
                    "Maximum delivery attempts "
                    "have been reached"
                ),
            )

        delay = self.calculate_delay_seconds(
            delivery.attempt_count
        )

        next_retry_at = (
            check_time
            + timedelta(seconds=delay)
        )

        return NotificationRetryDecision(
            code=(
                NotificationRetryDecisionCode
                .SCHEDULED
            ),
            delivery=delivery,
            should_retry=True,
            retryable=True,
            attempt_count=(
                delivery.attempt_count
            ),
            max_attempts=(
                self.policy.max_attempts
            ),
            delay_seconds=delay,
            next_retry_at=next_retry_at,
            reason=(
                "Delivery is eligible for retry"
            ),
        )

    def evaluate_execution(
        self,
        execution: DeliveryExecutionResult,
        *,
        evaluated_at: datetime | None = None,
    ) -> NotificationRetryDecision:
        return self.evaluate(
            execution.delivery,
            retryable=execution.retryable,
            evaluated_at=evaluated_at,
        )

    def schedule(
        self,
        store: NotificationStore,
        decision: NotificationRetryDecision,
    ) -> NotificationDelivery:
        if (
            not decision.should_retry
            or decision.next_retry_at is None
        ):
            raise ValueError(
                "Retry decision is not "
                "schedulable"
            )

        return store.schedule_delivery_retry(
            decision.delivery.delivery_id,
            scheduled_at=(
                decision.next_retry_at
            ),
        )

    def evaluate_and_schedule(
        self,
        store: NotificationStore,
        execution: DeliveryExecutionResult,
        *,
        evaluated_at: datetime | None = None,
    ) -> NotificationRetryDecision:
        decision = self.evaluate_execution(
            execution,
            evaluated_at=evaluated_at,
        )

        if decision.should_retry:
            self.schedule(
                store,
                decision,
            )

        return decision


def calculate_retry_delay_seconds(
    attempt_count: int,
    *,
    policy: NotificationRetryPolicy | None = None,
) -> float:
    return NotificationRetryEngine(
        policy
    ).calculate_delay_seconds(
        attempt_count
    )
