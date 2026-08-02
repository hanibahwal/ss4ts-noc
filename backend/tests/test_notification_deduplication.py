from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationIncident,
    NotificationIncidentStatus,
    NotificationPolicy,
    NotificationType,
)
from app.models.notification_deduplication import (
    DeduplicationContext,
    DeduplicationDecisionCode,
)
from app.services.notification_deduplication import (
    NotificationDeduplicationEngine,
    evaluate_notification_deduplication,
)
from app.services.notification_delivery_history import (
    NotificationDeliveryHistory,
)
from app.services.notification_store import (
    NotificationNotFound,
    NotificationStore,
)


BASE_TIME = datetime(
    2026,
    8,
    2,
    18,
    0,
    tzinfo=timezone.utc,
)


def make_store(
    tmp_path,
) -> NotificationStore:
    store = NotificationStore(
        tmp_path
        / "notifications.sqlite3"
    )

    store.create_incident(
        NotificationIncident(
            incident_id="incident:001",
            fingerprint=(
                "device_down:device:25"
            ),
            correlation_id=(
                "correlation:001"
            ),
            event_type="device_down",
            severity="critical",
            status=(
                NotificationIncidentStatus.OPEN
            ),
            title="Device unreachable",
            message="Device is down",
            device_id="25",
            first_seen_at=BASE_TIME,
            last_seen_at=BASE_TIME,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    store.create_policy(
        NotificationPolicy(
            policy_id="policy:001",
            name="Deduplication test policy",
            description=(
                "Policy used by notification "
                "deduplication tests"
            ),
            enabled=True,
            priority=100,
            minimum_duration_seconds=0,
            cooldown_seconds=900,
            send_recovery=True,
            stop_processing=False,
            conditions={},
            actions={},
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    return store


def make_context(
    *,
    notification_type: str = "firing",
    severity: str = "critical",
    cooldown_seconds: int = 900,
    force: bool = False,
    policy_id: str | None = "policy:001",
) -> DeduplicationContext:
    return DeduplicationContext(
        incident_id="incident:001",
        policy_id=policy_id,
        notification_type=(
            notification_type
        ),
        current_severity=severity,
        cooldown_seconds=(
            cooldown_seconds
        ),
        force=force,
    )


def save_delivery(
    store: NotificationStore,
    *,
    delivery_id: str = "delivery:001",
    status: NotificationDeliveryStatus = (
        NotificationDeliveryStatus.SENT
    ),
    notification_type: NotificationType = (
        NotificationType.FIRING
    ),
    severity: str = "critical",
    at: datetime = BASE_TIME,
    policy_id: str | None = "policy:001",
) -> NotificationDelivery:
    delivery = NotificationDelivery(
        delivery_id=delivery_id,
        incident_id="incident:001",
        policy_id=policy_id,
        channel=(
            NotificationChannel.WHATSAPP
        ),
        notification_type=(
            notification_type
        ),
        status=status,
        destination="966500000000",
        scheduled_at=at,
        sent_at=(
            at
            if status
            is NotificationDeliveryStatus.SENT
            else None
        ),
        metadata={
            "severity": severity,
        },
        created_at=at,
        updated_at=at,
    )

    store.create_delivery(
        delivery
    )

    return delivery


def test_first_notification_is_allowed(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True
    assert (
        decision.code
        is DeduplicationDecisionCode
        .ALLOWED_FIRST_NOTIFICATION
    )


def test_active_cooldown_blocks_duplicate(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        at=BASE_TIME,
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                cooldown_seconds=900
            ),
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=5)
            ),
        )
    )

    assert decision.allowed is False
    assert (
        decision.code
        is DeduplicationDecisionCode
        .BLOCKED_COOLDOWN_ACTIVE
    )
    assert (
        decision.remaining_seconds
        == 600
    )


def test_cooldown_expiry_allows_notification(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        at=BASE_TIME,
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                cooldown_seconds=900
            ),
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=15)
            ),
        )
    )

    assert decision.allowed is True
    assert (
        decision.code
        is DeduplicationDecisionCode
        .ALLOWED_COOLDOWN_EXPIRED
    )


def test_zero_cooldown_always_allows(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                cooldown_seconds=0
            ),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True
    assert (
        decision.code
        is DeduplicationDecisionCode
        .ALLOWED_COOLDOWN_DISABLED
    )


def test_recovery_bypasses_cooldown(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                notification_type=(
                    "recovery"
                )
            ),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True
    assert (
        decision.code
        is DeduplicationDecisionCode
        .ALLOWED_RECOVERY
    )


def test_escalation_bypasses_cooldown(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                notification_type=(
                    "escalation"
                )
            ),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True
    assert (
        decision.code
        is DeduplicationDecisionCode
        .ALLOWED_ESCALATION
    )


def test_forced_notification_bypasses_rules(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                force=True
            ),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True
    assert (
        decision.code
        is DeduplicationDecisionCode
        .ALLOWED_FORCED
    )


@pytest.mark.parametrize(
    "status",
    [
        NotificationDeliveryStatus.PENDING,
        NotificationDeliveryStatus.SENDING,
    ],
)
def test_active_delivery_blocks_duplicate(
    tmp_path,
    status,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        status=status,
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is False
    assert (
        decision.code
        is DeduplicationDecisionCode
        .BLOCKED_DUPLICATE_PENDING
    )


def test_failed_delivery_does_not_start_cooldown(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        status=(
            NotificationDeliveryStatus.FAILED
        ),
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True


def test_severity_increase_bypasses_cooldown(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        severity="major",
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                severity="critical"
            ),
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=1)
            ),
        )
    )

    assert decision.allowed is True
    assert (
        decision.code
        is DeduplicationDecisionCode
        .ALLOWED_SEVERITY_INCREASED
    )
    assert (
        decision.previous_severity
        == "major"
    )


@pytest.mark.parametrize(
    "severity",
    [
        "critical",
        "major",
        "warning",
    ],
)
def test_same_or_lower_severity_remains_blocked(
    tmp_path,
    severity,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        severity="critical",
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                severity=severity
            ),
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=1)
            ),
        )
    )

    assert decision.allowed is False


def test_different_policy_has_independent_cooldown(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        policy_id="policy:001",
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                policy_id="policy:002"
            ),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True


def test_different_type_has_independent_history(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        notification_type=(
            NotificationType.REMINDER
        ),
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                notification_type="firing"
            ),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True


def test_latest_delivery_is_used(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        delivery_id="delivery:old",
        at=BASE_TIME,
    )

    save_delivery(
        store,
        delivery_id="delivery:new",
        at=(
            BASE_TIME
            + timedelta(minutes=10)
        ),
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                cooldown_seconds=900
            ),
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=12)
            ),
        )
    )

    assert decision.allowed is False
    assert (
        decision.last_delivery_id
        == "delivery:new"
    )
    assert (
        decision.remaining_seconds
        == 780
    )


def test_next_allowed_at_is_calculated(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        at=BASE_TIME,
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                cooldown_seconds=300
            ),
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=1)
            ),
        )
    )

    assert (
        decision.next_allowed_at
        == BASE_TIME
        + timedelta(minutes=5)
    )

    assert (
        decision.remaining_seconds
        == 240
    )


def test_missing_incident_is_rejected(
    tmp_path,
) -> None:
    store = NotificationStore(
        tmp_path
        / "notifications.sqlite3"
    )

    engine = (
        NotificationDeduplicationEngine(
            store
        )
    )

    with pytest.raises(
        NotificationNotFound
    ):
        engine.evaluate(
            make_context(),
            evaluated_at=BASE_TIME,
        )


def test_negative_cooldown_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="non-negative",
    ):
        make_context(
            cooldown_seconds=-1
        )


def test_functional_helper_matches_engine(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    decision = (
        evaluate_notification_deduplication(
            store=store,
            context=make_context(),
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.allowed is True


def test_history_repository_returns_latest(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        delivery_id="delivery:1",
        at=BASE_TIME,
    )

    save_delivery(
        store,
        delivery_id="delivery:2",
        at=(
            BASE_TIME
            + timedelta(minutes=1)
        ),
    )

    history = (
        NotificationDeliveryHistory(
            store
        )
    )

    delivery = history.find_latest_sent(
        incident_id="incident:001",
        policy_id="policy:001",
        notification_type=(
            NotificationType.FIRING
        ),
    )

    assert delivery is not None
    assert (
        delivery.delivery_id
        == "delivery:2"
    )


def test_null_policy_delivery_is_supported(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    save_delivery(
        store,
        policy_id=None,
    )

    decision = (
        NotificationDeduplicationEngine(
            store
        ).evaluate(
            make_context(
                policy_id=None
            ),
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=1)
            ),
        )
    )

    assert decision.allowed is False
