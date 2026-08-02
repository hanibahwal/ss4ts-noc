from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Final

from app.models.notification import (
    NotificationDelivery,
    NotificationType,
)
from app.models.notification_deduplication import (
    DeduplicationContext,
    DeduplicationDecision,
    DeduplicationDecisionCode,
)
from app.services.notification_delivery_history import (
    NotificationDeliveryHistory,
)
from app.services.notification_store import (
    NotificationNotFound,
    NotificationStore,
)


_SEVERITY_RANK: Final[dict[str, int]] = {
    "info": 10,
    "warning": 20,
    "minor": 30,
    "major": 40,
    "critical": 50,
}


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _normalize_datetime(
    value: datetime,
) -> datetime:
    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _delivery_time(
    delivery: NotificationDelivery,
) -> datetime:
    value = (
        delivery.sent_at
        or delivery.scheduled_at
        or delivery.updated_at
        or delivery.created_at
    )

    return _normalize_datetime(
        value
    )


def _severity_rank(
    severity: str | None,
) -> int:
    if severity is None:
        return 0

    return _SEVERITY_RANK.get(
        str(severity)
        .strip()
        .lower(),
        0,
    )


class NotificationDeduplicationEngine:
    """
    Decide whether a notification may enter the delivery queue.

    The engine performs no delivery creation and sends no
    external messages. It returns an auditable decision only.
    """

    def __init__(
        self,
        store: NotificationStore,
        history: NotificationDeliveryHistory
        | None = None,
    ) -> None:
        self.store = store
        self.history = (
            history
            or NotificationDeliveryHistory(
                store
            )
        )

    def evaluate(
        self,
        context: DeduplicationContext,
        *,
        evaluated_at: datetime | None = None,
    ) -> DeduplicationDecision:
        now = _normalize_datetime(
            evaluated_at
            or _utc_now()
        )

        incident = self.store.get_incident(
            context.incident_id
        )

        if incident is None:
            raise NotificationNotFound(
                "Incident not found: "
                f"{context.incident_id}"
            )

        notification_type = (
            context.notification_type
            .strip()
            .lower()
        )

        current_severity = (
            context.current_severity
            .strip()
            .lower()
        )

        if context.force:
            return self._allowed(
                context=context,
                now=now,
                code=(
                    DeduplicationDecisionCode
                    .ALLOWED_FORCED
                ),
                reason=(
                    "Notification was explicitly forced"
                ),
            )

        if (
            notification_type
            == NotificationType.RECOVERY.value
        ):
            return self._allowed(
                context=context,
                now=now,
                code=(
                    DeduplicationDecisionCode
                    .ALLOWED_RECOVERY
                ),
                reason=(
                    "Recovery notifications bypass cooldown"
                ),
            )

        if (
            notification_type
            == NotificationType.ESCALATION.value
        ):
            return self._allowed(
                context=context,
                now=now,
                code=(
                    DeduplicationDecisionCode
                    .ALLOWED_ESCALATION
                ),
                reason=(
                    "Escalation notifications bypass cooldown"
                ),
            )

        active_delivery = (
            self.history.find_latest_active(
                incident_id=(
                    context.incident_id
                ),
                policy_id=(
                    context.policy_id
                ),
                notification_type=(
                    notification_type
                ),
            )
        )

        if active_delivery is not None:
            return DeduplicationDecision(
                allowed=False,
                code=(
                    DeduplicationDecisionCode
                    .BLOCKED_DUPLICATE_PENDING
                ),
                reason=(
                    "An equivalent delivery is already "
                    "pending or sending"
                ),
                incident_id=(
                    context.incident_id
                ),
                policy_id=context.policy_id,
                notification_type=(
                    notification_type
                ),
                evaluated_at=now,
                cooldown_seconds=(
                    context.cooldown_seconds
                ),
                last_delivery_id=(
                    active_delivery.delivery_id
                ),
                last_delivery_at=(
                    _delivery_time(
                        active_delivery
                    )
                ),
                current_severity=(
                    current_severity
                ),
                metadata=dict(
                    context.metadata
                ),
            )

        if context.cooldown_seconds == 0:
            return self._allowed(
                context=context,
                now=now,
                code=(
                    DeduplicationDecisionCode
                    .ALLOWED_COOLDOWN_DISABLED
                ),
                reason=(
                    "Cooldown is disabled for this policy"
                ),
            )

        last_delivery = (
            self.history.find_latest_sent(
                incident_id=(
                    context.incident_id
                ),
                policy_id=(
                    context.policy_id
                ),
                notification_type=(
                    notification_type
                ),
            )
        )

        if last_delivery is None:
            return self._allowed(
                context=context,
                now=now,
                code=(
                    DeduplicationDecisionCode
                    .ALLOWED_FIRST_NOTIFICATION
                ),
                reason=(
                    "No previous successful delivery exists"
                ),
            )

        last_at = _delivery_time(
            last_delivery
        )

        elapsed = max(
            0.0,
            (
                now - last_at
            ).total_seconds(),
        )

        next_allowed_at = (
            last_at
            + timedelta(
                seconds=(
                    context.cooldown_seconds
                )
            )
        )

        remaining = max(
            0.0,
            (
                next_allowed_at - now
            ).total_seconds(),
        )

        previous_severity = str(
            last_delivery.metadata.get(
                "severity",
                "",
            )
        ).strip().lower() or None

        if (
            _severity_rank(
                current_severity
            )
            > _severity_rank(
                previous_severity
            )
        ):
            return DeduplicationDecision(
                allowed=True,
                code=(
                    DeduplicationDecisionCode
                    .ALLOWED_SEVERITY_INCREASED
                ),
                reason=(
                    "Incident severity increased since "
                    "the previous delivery"
                ),
                incident_id=(
                    context.incident_id
                ),
                policy_id=context.policy_id,
                notification_type=(
                    notification_type
                ),
                evaluated_at=now,
                cooldown_seconds=(
                    context.cooldown_seconds
                ),
                elapsed_seconds=round(
                    elapsed,
                    3,
                ),
                remaining_seconds=round(
                    remaining,
                    3,
                ),
                last_delivery_id=(
                    last_delivery.delivery_id
                ),
                last_delivery_at=last_at,
                next_allowed_at=(
                    next_allowed_at
                ),
                previous_severity=(
                    previous_severity
                ),
                current_severity=(
                    current_severity
                ),
                metadata=dict(
                    context.metadata
                ),
            )

        if (
            elapsed
            >= context.cooldown_seconds
        ):
            return DeduplicationDecision(
                allowed=True,
                code=(
                    DeduplicationDecisionCode
                    .ALLOWED_COOLDOWN_EXPIRED
                ),
                reason=(
                    "Cooldown period has expired"
                ),
                incident_id=(
                    context.incident_id
                ),
                policy_id=context.policy_id,
                notification_type=(
                    notification_type
                ),
                evaluated_at=now,
                cooldown_seconds=(
                    context.cooldown_seconds
                ),
                elapsed_seconds=round(
                    elapsed,
                    3,
                ),
                remaining_seconds=0.0,
                last_delivery_id=(
                    last_delivery.delivery_id
                ),
                last_delivery_at=last_at,
                next_allowed_at=(
                    next_allowed_at
                ),
                previous_severity=(
                    previous_severity
                ),
                current_severity=(
                    current_severity
                ),
                metadata=dict(
                    context.metadata
                ),
            )

        return DeduplicationDecision(
            allowed=False,
            code=(
                DeduplicationDecisionCode
                .BLOCKED_COOLDOWN_ACTIVE
            ),
            reason=(
                "Equivalent notification is inside "
                "the cooldown period"
            ),
            incident_id=(
                context.incident_id
            ),
            policy_id=context.policy_id,
            notification_type=(
                notification_type
            ),
            evaluated_at=now,
            cooldown_seconds=(
                context.cooldown_seconds
            ),
            elapsed_seconds=round(
                elapsed,
                3,
            ),
            remaining_seconds=round(
                remaining,
                3,
            ),
            last_delivery_id=(
                last_delivery.delivery_id
            ),
            last_delivery_at=last_at,
            next_allowed_at=(
                next_allowed_at
            ),
            previous_severity=(
                previous_severity
            ),
            current_severity=(
                current_severity
            ),
            metadata=dict(
                context.metadata
            ),
        )

    @staticmethod
    def _allowed(
        *,
        context: DeduplicationContext,
        now: datetime,
        code: DeduplicationDecisionCode,
        reason: str,
    ) -> DeduplicationDecision:
        return DeduplicationDecision(
            allowed=True,
            code=code,
            reason=reason,
            incident_id=(
                context.incident_id
            ),
            policy_id=context.policy_id,
            notification_type=(
                context.notification_type
                .strip()
                .lower()
            ),
            evaluated_at=now,
            cooldown_seconds=(
                context.cooldown_seconds
            ),
            current_severity=(
                context.current_severity
                .strip()
                .lower()
            ),
            metadata=dict(
                context.metadata
            ),
        )


def evaluate_notification_deduplication(
    *,
    store: NotificationStore,
    context: DeduplicationContext,
    evaluated_at: datetime | None = None,
) -> DeduplicationDecision:
    return NotificationDeduplicationEngine(
        store
    ).evaluate(
        context,
        evaluated_at=evaluated_at,
    )
