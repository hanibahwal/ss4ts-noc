from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.events import (
    DeviceReference,
    EventSeverity,
    EventSource,
    EventState,
    EventType,
    create_notification_event,
    create_recovery_event,
)
from app.models.notification import (
    NotificationIncidentStatus,
)
from app.models.notification_incident_lifecycle import (
    IncidentLifecycleAction,
    IncidentLifecycleError,
    InvalidIncidentTransition,
)
from app.services.notification_incident_lifecycle import (
    NotificationIncidentLifecycle,
    calculate_incident_downtime_seconds,
)
from app.services.notification_store import (
    NotificationNotFound,
    NotificationStore,
    NotificationVersionConflict,
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
    return NotificationStore(
        tmp_path / "notifications.sqlite3"
    )


def make_lifecycle(
    tmp_path,
) -> NotificationIncidentLifecycle:
    return NotificationIncidentLifecycle(
        make_store(tmp_path)
    )


def make_device() -> DeviceReference:
    return DeviceReference(
        id=25,
        name="AFURAH-CAMP-RTR-01",
        ip="10.10.10.1",
        role="core-router",
        vendor="MikroTik",
        model="CCR2116",
    )


def make_firing_event(
    *,
    occurred_at: datetime = BASE_TIME,
    state: EventState = EventState.FIRING,
):
    return create_notification_event(
        event_type=EventType.DEVICE_DOWN,
        state=state,
        severity=EventSeverity.CRITICAL,
        source=EventSource.PING_MONITOR,
        title="Device unreachable",
        message="Ping failed for 60 seconds",
        device=make_device(),
        labels={
            "environment": "production",
        },
        metadata={
            "failed_probes": 3,
        },
        occurred_at=occurred_at,
    )


def test_firing_event_creates_incident(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    result = lifecycle.process_event(
        make_firing_event()
    )

    assert (
        result.action
        is IncidentLifecycleAction.CREATED
    )
    assert result.created is True
    assert result.changed is True
    assert result.incident is not None
    assert (
        result.incident.status
        is NotificationIncidentStatus.OPEN
    )
    assert result.incident.occurrence_count == 1


def test_created_incident_preserves_event_identity(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)
    event = make_firing_event()

    result = lifecycle.process_event(event)

    assert result.incident is not None
    assert (
        result.incident.fingerprint
        == event.fingerprint
    )
    assert (
        result.incident.correlation_id
        == str(event.correlation_id)
    )
    assert result.incident.device_id == "25"


def test_repeated_event_updates_existing_incident(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    first = make_firing_event()

    second = make_firing_event(
        occurred_at=(
            BASE_TIME
            + timedelta(minutes=2)
        ),
        state=EventState.ACTIVE,
    )

    created = lifecycle.process_event(first)
    observed = lifecycle.process_event(second)

    assert (
        observed.action
        is IncidentLifecycleAction.OBSERVED
    )
    assert observed.created is False
    assert (
        observed.incident.incident_id
        == created.incident.incident_id
    )
    assert (
        observed.incident.occurrence_count
        == 2
    )


def test_repeated_event_does_not_create_duplicate(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    lifecycle.process_event(
        make_firing_event()
    )

    lifecycle.process_event(
        make_firing_event(
            occurred_at=(
                BASE_TIME
                + timedelta(minutes=1)
            )
        )
    )

    open_incident = (
        lifecycle.store
        .get_open_incident_by_fingerprint(
            "device_down:device:25"
        )
    )

    assert open_incident is not None
    assert open_incident.occurrence_count == 2


def test_repeated_event_updates_metadata(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    lifecycle.process_event(
        make_firing_event()
    )

    second = make_firing_event(
        occurred_at=(
            BASE_TIME
            + timedelta(minutes=1)
        )
    )

    result = lifecycle.process_event(second)

    assert (
        result.incident.metadata[
            "last_event_id"
        ]
        == str(second.event_id)
    )


def test_acknowledge_open_incident(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    result = lifecycle.acknowledge(
        created.incident.incident_id,
        acknowledged_by="engineer:hani",
    )

    assert (
        result.action
        is IncidentLifecycleAction
        .ACKNOWLEDGED
    )
    assert (
        result.incident.status
        is NotificationIncidentStatus
        .ACKNOWLEDGED
    )
    assert (
        result.incident.acknowledged_by
        == "engineer:hani"
    )


def test_acknowledge_is_idempotent(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    first = lifecycle.acknowledge(
        created.incident.incident_id,
        acknowledged_by="engineer:hani",
    )

    second = lifecycle.acknowledge(
        first.incident.incident_id,
        acknowledged_by="engineer:other",
    )

    assert (
        second.action
        is IncidentLifecycleAction.IGNORED
    )
    assert second.changed is False
    assert (
        second.incident.acknowledged_by
        == "engineer:hani"
    )


def test_acknowledge_requires_actor(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    with pytest.raises(
        IncidentLifecycleError
    ):
        lifecycle.acknowledge(
            created.incident.incident_id,
            acknowledged_by=" ",
        )


def test_acknowledge_missing_incident_fails(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    with pytest.raises(
        NotificationNotFound
    ):
        lifecycle.acknowledge(
            "incident:missing",
            acknowledged_by="engineer",
        )


def test_manual_resolution(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    result = lifecycle.resolve(
        created.incident.incident_id,
        resolved_by="engineer:hani",
    )

    assert (
        result.action
        is IncidentLifecycleAction.RESOLVED
    )
    assert (
        result.incident.status
        is NotificationIncidentStatus.RESOLVED
    )
    assert (
        result.incident.resolved_by
        == "engineer:hani"
    )


def test_resolution_is_idempotent(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    first = lifecycle.resolve(
        created.incident.incident_id,
        resolved_by="system",
    )

    second = lifecycle.resolve(
        first.incident.incident_id,
        resolved_by="other",
    )

    assert (
        second.action
        is IncidentLifecycleAction.IGNORED
    )
    assert second.changed is False
    assert second.incident.resolved_by == "system"


def test_resolved_incident_cannot_be_acknowledged(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    resolved = lifecycle.resolve(
        created.incident.incident_id,
        resolved_by="system",
    )

    with pytest.raises(
        InvalidIncidentTransition
    ):
        lifecycle.acknowledge(
            resolved.incident.incident_id,
            acknowledged_by="engineer",
        )


def test_recovery_event_resolves_using_incident_id(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)
    firing = make_firing_event()

    created = lifecycle.process_event(firing)

    recovery = create_recovery_event(
        original_event=firing,
        event_type=EventType.DEVICE_UP,
        title="Device recovered",
        message="Device responds again",
        metadata={
            "incident_id": (
                created.incident.incident_id
            ),
        },
        occurred_at=(
            BASE_TIME
            + timedelta(minutes=5)
        ),
    )

    result = lifecycle.process_event(recovery)

    assert (
        result.action
        is IncidentLifecycleAction.RECOVERED
    )
    assert (
        result.incident.status
        is NotificationIncidentStatus.RESOLVED
    )


def test_recovery_event_resolves_using_fingerprint(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)
    firing = make_firing_event()

    created = lifecycle.process_event(firing)

    recovery = create_recovery_event(
        original_event=firing,
        event_type=EventType.DEVICE_UP,
        title="Device recovered",
        message="Device responds again",
        metadata={
            "recovery_fingerprint": (
                firing.fingerprint
            ),
        },
    )

    result = lifecycle.process_event(recovery)

    assert result.incident is not None
    assert (
        result.incident.incident_id
        == created.incident.incident_id
    )


def test_unmatched_recovery_is_ignored(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)
    firing = make_firing_event()

    recovery = create_recovery_event(
        original_event=firing,
        event_type=EventType.DEVICE_UP,
        title="Device recovered",
        message="Device responds again",
    )

    result = lifecycle.process_event(recovery)

    assert (
        result.action
        is IncidentLifecycleAction.IGNORED
    )
    assert result.incident is None


def test_recovery_allows_new_incident_afterwards(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)
    firing = make_firing_event()

    created = lifecycle.process_event(firing)

    recovery = create_recovery_event(
        original_event=firing,
        event_type=EventType.DEVICE_UP,
        title="Device recovered",
        message="Device responds again",
        metadata={
            "incident_id": (
                created.incident.incident_id
            ),
        },
    )

    lifecycle.process_event(recovery)

    new_result = lifecycle.process_event(
        make_firing_event(
            occurred_at=(
                BASE_TIME
                + timedelta(hours=1)
            )
        )
    )

    assert new_result.created is True
    assert (
        new_result.incident.incident_id
        != created.incident.incident_id
    )


def test_suppressed_event_is_ignored(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    event = create_notification_event(
        event_type=EventType.DEVICE_DOWN,
        state=EventState.SUPPRESSED,
        severity=EventSeverity.CRITICAL,
        source=EventSource.PING_MONITOR,
        title="Suppressed",
        message="Maintenance",
        device=make_device(),
    )

    result = lifecycle.process_event(event)

    assert (
        result.action
        is IncidentLifecycleAction.IGNORED
    )
    assert result.incident is None


def test_acknowledged_event_can_acknowledge_incident(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    firing = make_firing_event()
    created = lifecycle.process_event(firing)

    ack_event = create_notification_event(
        event_type=EventType.DEVICE_DOWN,
        state=EventState.ACKNOWLEDGED,
        severity=EventSeverity.CRITICAL,
        source=EventSource.MANUAL,
        title="Acknowledged",
        message="Engineer accepted incident",
        device=make_device(),
        correlation_id=firing.correlation_id,
        metadata={
            "acknowledged_by": (
                "engineer:hani"
            ),
        },
    )

    result = lifecycle.process_event(ack_event)

    assert (
        result.incident.incident_id
        == created.incident.incident_id
    )
    assert (
        result.incident.status
        is NotificationIncidentStatus
        .ACKNOWLEDGED
    )


def test_summary_reports_incident_information(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    summary = lifecycle.summary(
        created.incident.incident_id,
        at=(
            BASE_TIME
            + timedelta(minutes=10)
        ),
    )

    assert (
        summary.incident_id
        == created.incident.incident_id
    )
    assert summary.status == "open"
    assert summary.occurrence_count == 1
    assert summary.downtime_seconds == 600


def test_resolved_summary_uses_resolution_time(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    resolved = lifecycle.resolve(
        created.incident.incident_id,
        resolved_by="system",
    )

    summary = lifecycle.summary(
        resolved.incident.incident_id,
        at=(
            BASE_TIME
            + timedelta(days=1)
        ),
    )

    assert summary.resolved_at is not None
    assert (
        summary.downtime_seconds
        < 86400
    )


def test_downtime_never_becomes_negative(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    downtime = (
        calculate_incident_downtime_seconds(
            created.incident,
            at=(
                BASE_TIME
                - timedelta(minutes=1)
            ),
        )
    )

    assert downtime == 0.0


def test_stale_acknowledgment_version_fails(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    lifecycle.process_event(
        make_firing_event(
            occurred_at=(
                BASE_TIME
                + timedelta(minutes=1)
            )
        )
    )

    with pytest.raises(
        NotificationVersionConflict
    ):
        lifecycle.acknowledge(
            created.incident.incident_id,
            acknowledged_by="engineer",
            expected_version=1,
        )


def test_history_records_lifecycle_changes(
    tmp_path,
) -> None:
    lifecycle = make_lifecycle(tmp_path)

    created = lifecycle.process_event(
        make_firing_event()
    )

    observed = lifecycle.process_event(
        make_firing_event(
            occurred_at=(
                BASE_TIME
                + timedelta(minutes=1)
            )
        )
    )

    acknowledged = lifecycle.acknowledge(
        observed.incident.incident_id,
        acknowledged_by="engineer",
    )

    lifecycle.resolve(
        acknowledged.incident.incident_id,
        resolved_by="system",
    )

    assert lifecycle.store.history_count(
        entity_type="incident",
        entity_id=created.incident.incident_id,
    ) == 4
