from __future__ import annotations

from dataclasses import replace
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
    NotificationType,
)
from app.models.notification_delivery_orchestration import (
    DeliveryExecutionResult,
    DeliveryExecutionStatus,
)
from app.models.notification_retry import (
    NotificationRetryDecisionCode,
    NotificationRetryPolicy,
)
from app.services.notification_retry import (
    NotificationRetryEngine,
    calculate_retry_delay_seconds,
)
from app.services.notification_store import (
    NotificationStore,
    NotificationStoreError,
)


BASE_TIME = datetime(
    2026,
    8,
    2,
    18,
    0,
    tzinfo=timezone.utc,
)


def make_delivery(
    *,
    delivery_id: str = "delivery:001",
    status: NotificationDeliveryStatus = (
        NotificationDeliveryStatus.FAILED
    ),
    attempt_count: int = 1,
    scheduled_at: datetime | None = None,
) -> NotificationDelivery:
    return NotificationDelivery(
        delivery_id=delivery_id,
        incident_id="incident:001",
        channel=(
            NotificationChannel.WHATSAPP
        ),
        notification_type=(
            NotificationType.FIRING
        ),
        status=status,
        destination="966500000000",
        attempt_count=attempt_count,
        error_message=(
            "Provider temporarily unavailable"
        ),
        scheduled_at=scheduled_at,
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
    )


def make_store(tmp_path) -> NotificationStore:
    store = NotificationStore(
        tmp_path / "notifications.sqlite3"
    )

    store.create_incident(
        NotificationIncident(
            incident_id="incident:001",
            fingerprint=(
                "device_down:device:25"
            ),
            correlation_id="correlation:001",
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

    return store


def make_execution(
    delivery: NotificationDelivery,
    *,
    retryable: bool = True,
) -> DeliveryExecutionResult:
    return DeliveryExecutionResult(
        status=(
            DeliveryExecutionStatus.FAILED
        ),
        delivery=delivery,
        error_message=(
            delivery.error_message
        ),
        retryable=retryable,
    )


def test_default_policy_values() -> None:
    policy = NotificationRetryPolicy()

    assert policy.max_attempts == 5
    assert (
        policy.initial_delay_seconds
        == 30
    )
    assert policy.backoff_multiplier == 2
    assert policy.max_delay_seconds == 900


@pytest.mark.parametrize(
    ("attempt_count", "expected"),
    [
        (1, 30),
        (2, 60),
        (3, 120),
        (4, 240),
        (5, 480),
        (6, 900),
        (7, 900),
    ],
)
def test_exponential_backoff(
    attempt_count,
    expected,
) -> None:
    engine = NotificationRetryEngine()

    assert (
        engine.calculate_delay_seconds(
            attempt_count
        )
        == expected
    )


def test_custom_backoff_policy() -> None:
    engine = NotificationRetryEngine(
        NotificationRetryPolicy(
            max_attempts=6,
            initial_delay_seconds=10,
            backoff_multiplier=3,
            max_delay_seconds=100,
        )
    )

    assert (
        engine.calculate_delay_seconds(1)
        == 10
    )
    assert (
        engine.calculate_delay_seconds(2)
        == 30
    )
    assert (
        engine.calculate_delay_seconds(3)
        == 90
    )
    assert (
        engine.calculate_delay_seconds(4)
        == 100
    )


def test_retryable_failure_is_scheduled() -> None:
    decision = (
        NotificationRetryEngine().evaluate(
            make_delivery(
                attempt_count=1
            ),
            retryable=True,
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.should_retry is True
    assert (
        decision.code
        is NotificationRetryDecisionCode.SCHEDULED
    )
    assert decision.delay_seconds == 30
    assert (
        decision.next_retry_at
        == BASE_TIME
        + timedelta(seconds=30)
    )
    assert decision.attempts_remaining == 4


def test_non_retryable_failure_rejected() -> None:
    decision = (
        NotificationRetryEngine().evaluate(
            make_delivery(),
            retryable=False,
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.should_retry is False
    assert (
        decision.code
        is NotificationRetryDecisionCode
        .NOT_RETRYABLE
    )
    assert decision.next_retry_at is None


def test_max_attempts_rejected() -> None:
    decision = (
        NotificationRetryEngine().evaluate(
            make_delivery(
                attempt_count=5
            ),
            retryable=True,
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.should_retry is False
    assert (
        decision.code
        is NotificationRetryDecisionCode
        .MAX_ATTEMPTS_REACHED
    )
    assert decision.attempts_remaining == 0


def test_non_failed_delivery_rejected() -> None:
    decision = (
        NotificationRetryEngine().evaluate(
            make_delivery(
                status=(
                    NotificationDeliveryStatus
                    .SENT
                )
            ),
            retryable=True,
            evaluated_at=BASE_TIME,
        )
    )

    assert decision.should_retry is False
    assert (
        decision.code
        is NotificationRetryDecisionCode
        .DELIVERY_NOT_FAILED
    )


def test_disabled_policy_rejected() -> None:
    engine = NotificationRetryEngine(
        NotificationRetryPolicy(
            enabled=False
        )
    )

    decision = engine.evaluate(
        make_delivery(),
        retryable=True,
        evaluated_at=BASE_TIME,
    )

    assert decision.should_retry is False
    assert (
        decision.code
        is NotificationRetryDecisionCode.DISABLED
    )


def test_schedule_updates_store(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    delivery = make_delivery()

    store.create_delivery(delivery)

    engine = NotificationRetryEngine()

    decision = engine.evaluate(
        delivery,
        retryable=True,
        evaluated_at=BASE_TIME,
    )

    scheduled = engine.schedule(
        store,
        decision,
    )

    assert (
        scheduled.status
        is NotificationDeliveryStatus.PENDING
    )
    assert scheduled.attempt_count == 1
    assert (
        scheduled.scheduled_at
        == BASE_TIME
        + timedelta(seconds=30)
    )
    assert (
        scheduled.error_message
        == delivery.error_message
    )


def test_evaluate_and_schedule_execution(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    delivery = make_delivery(
        attempt_count=2
    )

    store.create_delivery(delivery)

    decision = (
        NotificationRetryEngine()
        .evaluate_and_schedule(
            store,
            make_execution(delivery),
            evaluated_at=BASE_TIME,
        )
    )

    persisted = store.get_delivery(
        delivery.delivery_id
    )

    assert decision.should_retry is True
    assert decision.delay_seconds == 60
    assert persisted is not None
    assert (
        persisted.status
        is NotificationDeliveryStatus.PENDING
    )
    assert (
        persisted.scheduled_at
        == BASE_TIME
        + timedelta(seconds=60)
    )


def test_non_retryable_execution_not_scheduled(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    delivery = make_delivery()

    store.create_delivery(delivery)

    decision = (
        NotificationRetryEngine()
        .evaluate_and_schedule(
            store,
            make_execution(
                delivery,
                retryable=False,
            ),
            evaluated_at=BASE_TIME,
        )
    )

    persisted = store.get_delivery(
        delivery.delivery_id
    )

    assert decision.should_retry is False
    assert persisted is not None
    assert (
        persisted.status
        is NotificationDeliveryStatus.FAILED
    )


def test_due_deliveries_filter(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    due = make_delivery(
        delivery_id="delivery:due",
        status=(
            NotificationDeliveryStatus.PENDING
        ),
        scheduled_at=(
            BASE_TIME
            - timedelta(seconds=1)
        ),
    )

    future = make_delivery(
        delivery_id="delivery:future",
        status=(
            NotificationDeliveryStatus.PENDING
        ),
        scheduled_at=(
            BASE_TIME
            + timedelta(minutes=5)
        ),
    )

    immediate = make_delivery(
        delivery_id="delivery:immediate",
        status=(
            NotificationDeliveryStatus.PENDING
        ),
        scheduled_at=None,
    )

    failed = make_delivery(
        delivery_id="delivery:failed",
        status=(
            NotificationDeliveryStatus.FAILED
        ),
    )

    for delivery in (
        due,
        future,
        immediate,
        failed,
    ):
        store.create_delivery(delivery)

    deliveries = store.list_due_deliveries(
        at=BASE_TIME
    )

    ids = {
        item.delivery_id
        for item in deliveries
    }

    assert ids == {
        "delivery:due",
        "delivery:immediate",
    }


def test_only_failed_delivery_can_schedule(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    delivery = make_delivery(
        status=(
            NotificationDeliveryStatus.PENDING
        )
    )

    store.create_delivery(delivery)

    with pytest.raises(
        NotificationStoreError,
        match="Only failed",
    ):
        store.schedule_delivery_retry(
            delivery.delivery_id,
            scheduled_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=1)
            ),
        )


def test_retry_policy_validation() -> None:
    with pytest.raises(ValueError):
        NotificationRetryPolicy(
            max_attempts=0
        )

    with pytest.raises(ValueError):
        NotificationRetryPolicy(
            initial_delay_seconds=-1
        )

    with pytest.raises(ValueError):
        NotificationRetryPolicy(
            backoff_multiplier=0.5
        )

    with pytest.raises(ValueError):
        NotificationRetryPolicy(
            initial_delay_seconds=30,
            max_delay_seconds=20,
        )


def test_calculate_retry_delay_helper() -> None:
    assert (
        calculate_retry_delay_seconds(3)
        == 120
    )


def test_attempt_count_zero_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="positive",
    ):
        NotificationRetryEngine(
        ).calculate_delay_seconds(0)


def test_naive_evaluation_time_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        NotificationRetryEngine().evaluate(
            make_delivery(),
            retryable=True,
            evaluated_at=datetime(
                2026,
                8,
                2,
                18,
                0,
            ),
        )


def test_schedule_preserves_attempt_count(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    delivery = make_delivery(
        attempt_count=3
    )

    store.create_delivery(delivery)

    scheduled = (
        NotificationRetryEngine()
        .schedule(
            store,
            NotificationRetryEngine()
            .evaluate(
                delivery,
                retryable=True,
                evaluated_at=BASE_TIME,
            ),
        )
    )

    assert scheduled.attempt_count == 3
