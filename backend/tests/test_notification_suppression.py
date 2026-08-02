from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.notification import (
    NotificationSuppression,
    NotificationSuppressionKind,
    NotificationType,
)
from app.models.notification_suppression_engine import (
    NotificationSuppressionContext,
    NotificationSuppressionDecisionCode,
    QuietHoursWindow,
)
from app.services.notification_store import (
    NotificationStore,
)
from app.services.notification_suppression import (
    NotificationSuppressionEngine,
    evaluate_notification_suppression,
)


BASE_TIME = datetime(
    2026,
    8,
    2,
    18,
    0,
    tzinfo=timezone.utc,
)


def make_store(tmp_path) -> NotificationStore:
    return NotificationStore(
        tmp_path / "notifications.sqlite3"
    )


def add_suppression(
    store: NotificationStore,
    *,
    suppression_id: str = "suppression:001",
    kind: NotificationSuppressionKind = (
        NotificationSuppressionKind.MANUAL
    ),
    starts_at: datetime = (
        BASE_TIME - timedelta(hours=1)
    ),
    ends_at: datetime = (
        BASE_TIME + timedelta(hours=8)
    ),
    enabled: bool = True,
    event_types: tuple[str, ...] = (),
    site_ids: tuple[str, ...] = (),
    device_ids: tuple[str, ...] = (),
    metadata: dict | None = None,
    reason: str = "Maintenance",
) -> NotificationSuppression:
    suppression = NotificationSuppression(
        suppression_id=suppression_id,
        name="Test suppression",
        kind=kind,
        enabled=enabled,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
        event_types=event_types,
        site_ids=site_ids,
        device_ids=device_ids,
        metadata=dict(metadata or {}),
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
    )

    store.create_suppression(suppression)

    return suppression


def make_context(
    *,
    at: datetime = BASE_TIME,
    event_type: str = "device_down",
    site_id: str | None = "site:001",
    device_id: str | None = "device:001",
    severity: str | None = "critical",
    notification_type=NotificationType.FIRING,
    force: bool = False,
) -> NotificationSuppressionContext:
    return NotificationSuppressionContext(
        event_type=event_type,
        evaluated_at=at,
        site_id=site_id,
        device_id=device_id,
        severity=severity,
        notification_type=notification_type,
        force=force,
    )


def test_manual_suppression_matches(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    add_suppression(store)

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        )
    )

    assert decision.suppressed is True
    assert (
        decision.code
        is NotificationSuppressionDecisionCode
        .SUPPRESSED
    )
    assert decision.reason == "Maintenance"


def test_maintenance_suppression(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .MAINTENANCE
        ),
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).is_suppressed(
            make_context()
        )
        is True
    )


def test_empty_scope_is_wildcard(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    add_suppression(store)

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context(
                event_type="interface_down",
                site_id="other-site",
                device_id="other-device",
            )
        )
    )

    assert decision.suppressed is True


@pytest.mark.parametrize(
    (
        "event_types",
        "site_ids",
        "device_ids",
        "context_values",
        "expected",
    ),
    [
        (
            ("device_down",),
            (),
            (),
            {
                "event_type": "device_down",
            },
            True,
        ),
        (
            ("device_down",),
            (),
            (),
            {
                "event_type": "interface_down",
            },
            False,
        ),
        (
            (),
            ("site:001",),
            (),
            {
                "site_id": "site:001",
            },
            True,
        ),
        (
            (),
            ("site:001",),
            (),
            {
                "site_id": "site:999",
            },
            False,
        ),
        (
            (),
            (),
            ("device:001",),
            {
                "device_id": "device:001",
            },
            True,
        ),
        (
            (),
            (),
            ("device:001",),
            {
                "device_id": None,
            },
            False,
        ),
    ],
)
def test_scope_filters(
    tmp_path,
    event_types,
    site_ids,
    device_ids,
    context_values,
    expected,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        event_types=event_types,
        site_ids=site_ids,
        device_ids=device_ids,
    )

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context(
                **context_values
            )
        )
    )

    assert decision.suppressed is expected


def test_expired_suppression_ignored(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        starts_at=(
            BASE_TIME - timedelta(hours=2)
        ),
        ends_at=(
            BASE_TIME - timedelta(hours=1)
        ),
    )

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        )
    )

    assert decision.allowed is True


def test_future_suppression_ignored(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        starts_at=(
            BASE_TIME + timedelta(hours=1)
        ),
        ends_at=(
            BASE_TIME + timedelta(hours=2)
        ),
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        ).allowed
        is True
    )


def test_disabled_suppression_ignored(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        enabled=False,
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).is_suppressed(
            make_context()
        )
        is False
    )


def test_force_bypasses_suppression(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    add_suppression(store)

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context(force=True)
        )
    )

    assert decision.suppressed is False
    assert (
        decision.code
        is NotificationSuppressionDecisionCode
        .BYPASSED
    )


def test_severity_bypass(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        metadata={
            "bypass_severities": [
                "critical",
            ],
        },
    )

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context(
                severity="CRITICAL"
            )
        )
    )

    assert decision.suppressed is False
    assert (
        decision.code
        is NotificationSuppressionDecisionCode
        .BYPASSED
    )


def test_notification_type_bypass(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        metadata={
            "bypass_notification_types": [
                "recovery",
                "escalation",
            ],
        },
    )

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context(
                notification_type=(
                    NotificationType.RECOVERY
                )
            )
        )
    )

    assert decision.suppressed is False


def test_daytime_quiet_hours(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        metadata={
            "timezone": "UTC",
            "start_time": "17:00",
            "end_time": "20:00",
        },
    )

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        )
    )

    assert decision.suppressed is True
    assert (
        decision.quiet_hours_window
        is not None
    )


def test_outside_daytime_quiet_hours(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        metadata={
            "timezone": "UTC",
            "start_time": "08:00",
            "end_time": "12:00",
        },
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        ).allowed
        is True
    )


@pytest.mark.parametrize(
    "at",
    [
        datetime(
            2026,
            8,
            2,
            23,
            0,
            tzinfo=timezone.utc,
        ),
        datetime(
            2026,
            8,
            3,
            5,
            30,
            tzinfo=timezone.utc,
        ),
    ],
)
def test_overnight_quiet_hours(
    tmp_path,
    at,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        starts_at=(
            BASE_TIME - timedelta(days=1)
        ),
        ends_at=(
            BASE_TIME + timedelta(days=2)
        ),
        metadata={
            "timezone": "UTC",
            "start_time": "22:00",
            "end_time": "06:00",
        },
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).is_suppressed(
            make_context(at=at)
        )
        is True
    )


def test_overnight_midday_allowed(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        metadata={
            "timezone": "UTC",
            "start_time": "22:00",
            "end_time": "06:00",
        },
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        ).allowed
        is True
    )


def test_riyadh_timezone_conversion(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    # 18:00 UTC = 21:00 Asia/Riyadh
    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        metadata={
            "timezone": "Asia/Riyadh",
            "start_time": "20:00",
            "end_time": "23:00",
        },
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).is_suppressed(
            make_context()
        )
        is True
    )


def test_weekday_filter(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    # 2026-08-02 is Sunday.
    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        metadata={
            "timezone": "UTC",
            "start_time": "17:00",
            "end_time": "20:00",
            "weekdays": ["Sunday"],
        },
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).is_suppressed(
            make_context()
        )
        is True
    )


def test_non_matching_weekday_allowed(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        metadata={
            "timezone": "UTC",
            "start_time": "17:00",
            "end_time": "20:00",
            "weekdays": ["Monday"],
        },
    )

    assert (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        ).allowed
        is True
    )


def test_invalid_timezone_rejected(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        metadata={
            "timezone": "Invalid/Timezone",
            "start_time": "22:00",
            "end_time": "06:00",
        },
    )

    with pytest.raises(
        ValueError,
        match="Unknown quiet-hours timezone",
    ):
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        )


def test_invalid_clock_rejected(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        kind=(
            NotificationSuppressionKind
            .QUIET_HOURS
        ),
        metadata={
            "start_time": "25:00",
            "end_time": "06:00",
        },
    )

    with pytest.raises(
        ValueError,
        match="start time",
    ):
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        )


def test_first_matching_suppression_used(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    add_suppression(
        store,
        suppression_id="suppression:first",
        reason="First match",
    )

    add_suppression(
        store,
        suppression_id="suppression:second",
        starts_at=(
            BASE_TIME - timedelta(minutes=30)
        ),
        reason="Second match",
    )

    decision = (
        NotificationSuppressionEngine(
            store
        ).evaluate(
            make_context()
        )
    )

    assert decision.suppression is not None
    assert (
        decision.suppression.suppression_id
        == "suppression:first"
    )


def test_functional_helper(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    add_suppression(store)

    decision = (
        evaluate_notification_suppression(
            store,
            make_context(),
        )
    )

    assert decision.suppressed is True


def test_naive_datetime_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        NotificationSuppressionContext(
            event_type="device_down",
            evaluated_at=datetime(
                2026,
                8,
                2,
                18,
                0,
            ),
        )


def test_quiet_window_validation() -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 6",
    ):
        QuietHoursWindow(
            start_time=datetime.strptime(
                "22:00",
                "%H:%M",
            ).time(),
            end_time=datetime.strptime(
                "06:00",
                "%H:%M",
            ).time(),
            weekdays=(7,),
        )
