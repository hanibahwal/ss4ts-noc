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
    NotificationEscalationStep,
    NotificationIncident,
    NotificationIncidentStatus,
    NotificationPolicy,
    NotificationRecipient,
    NotificationSuppression,
    NotificationSuppressionKind,
    NotificationType,
)
from app.services.notification_store import (
    NotificationDuplicate,
    NotificationStore,
    NotificationStoreError,
    NotificationVersionConflict,
)


def make_store(
    tmp_path,
) -> NotificationStore:
    return NotificationStore(
        tmp_path / "notifications.sqlite3"
    )


def make_policy(
    policy_id: str = "policy:critical-router",
) -> NotificationPolicy:
    return NotificationPolicy(
        policy_id=policy_id,
        name="Critical router policy",
        description=(
            "Notify when a core router is down"
        ),
        priority=10,
        minimum_duration_seconds=60,
        cooldown_seconds=900,
        conditions={
            "event_types": [
                "device_down",
            ],
            "severities": [
                "critical",
            ],
        },
        actions={
            "channels": [
                "whatsapp",
            ],
        },
    )


def make_recipient() -> NotificationRecipient:
    return NotificationRecipient(
        recipient_id="recipient:noc",
        name="NOC Team",
        channel=NotificationChannel.WHATSAPP,
        address="966500000000",
    )


def make_incident(
    *,
    incident_id: str = "incident:001",
    fingerprint: str = "device_down:device:25",
) -> NotificationIncident:
    return NotificationIncident(
        incident_id=incident_id,
        fingerprint=fingerprint,
        correlation_id="correlation:001",
        event_type="device_down",
        severity="critical",
        status=NotificationIncidentStatus.OPEN,
        title="Device unreachable",
        message="Ping failed for 60 seconds",
        device_id="25",
        site_id="4",
    )


def test_store_creates_database_schema(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    assert store.database_path.exists()


def test_policy_round_trip(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    policy = make_policy()

    store.create_policy(policy)

    stored = store.get_policy(
        policy.policy_id
    )

    assert stored == policy
    assert stored.conditions["event_types"] == [
        "device_down"
    ]


def test_policies_are_sorted_by_priority(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    store.create_policy(
        replace(
            make_policy("policy:low"),
            name="Low priority",
            priority=100,
        )
    )

    store.create_policy(
        replace(
            make_policy("policy:high"),
            name="High priority",
            priority=1,
        )
    )

    policies = store.list_policies()

    assert [
        item.policy_id
        for item in policies
    ] == [
        "policy:high",
        "policy:low",
    ]


def test_policy_update_uses_optimistic_locking(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    policy = make_policy()

    store.create_policy(policy)

    updated = store.update_policy(
        replace(
            policy,
            name="Updated policy",
        ),
        expected_version=1,
    )

    assert updated.name == "Updated policy"
    assert updated.record_version == 2

    with pytest.raises(
        NotificationVersionConflict
    ):
        store.update_policy(
            updated,
            expected_version=1,
        )


def test_policy_history_is_recorded(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    policy = make_policy()

    store.create_policy(policy)

    updated = store.update_policy(
        replace(
            policy,
            description="Updated",
        ),
        expected_version=1,
    )

    store.delete_policy(
        updated.policy_id
    )

    assert store.history_count(
        entity_type="policy",
        entity_id=policy.policy_id,
    ) == 3


def test_duplicate_policy_is_rejected(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    policy = make_policy()

    store.create_policy(policy)

    with pytest.raises(
        NotificationDuplicate
    ):
        store.create_policy(policy)


def test_recipient_round_trip(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    recipient = make_recipient()

    store.create_recipient(recipient)

    assert store.get_recipient(
        recipient.recipient_id
    ) == recipient


def test_duplicate_recipient_address_is_rejected(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    recipient = make_recipient()

    store.create_recipient(recipient)

    with pytest.raises(
        NotificationDuplicate
    ):
        store.create_recipient(
            replace(
                recipient,
                recipient_id="recipient:other",
                name="Other NOC",
            )
        )


def test_escalation_steps_are_ordered(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    policy = make_policy()
    recipient = make_recipient()

    store.create_policy(policy)
    store.create_recipient(recipient)

    store.add_escalation_step(
        NotificationEscalationStep(
            escalation_step_id="step:2",
            policy_id=policy.policy_id,
            step_order=2,
            delay_seconds=600,
            channel=(
                NotificationChannel.WHATSAPP
            ),
            recipient_id=(
                recipient.recipient_id
            ),
        )
    )

    store.add_escalation_step(
        NotificationEscalationStep(
            escalation_step_id="step:1",
            policy_id=policy.policy_id,
            step_order=1,
            delay_seconds=60,
            channel=(
                NotificationChannel.WHATSAPP
            ),
            recipient_id=(
                recipient.recipient_id
            ),
        )
    )

    steps = store.list_escalation_steps(
        policy.policy_id
    )

    assert [
        step.step_order
        for step in steps
    ] == [1, 2]


def test_incident_round_trip(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    incident = make_incident()

    store.create_incident(incident)

    assert store.get_incident(
        incident.incident_id
    ) == incident

    assert (
        store.get_open_incident_by_fingerprint(
            incident.fingerprint
        )
        == incident
    )


def test_only_one_open_incident_per_fingerprint(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    store.create_incident(
        make_incident()
    )

    with pytest.raises(
        NotificationDuplicate
    ):
        store.create_incident(
            make_incident(
                incident_id="incident:002"
            )
        )


def test_incident_touch_increments_occurrence(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    incident = make_incident()

    store.create_incident(incident)

    updated = store.touch_incident(
        incident.incident_id,
        message="Second failed observation",
        metadata={
            "failed_probes": 4,
        },
        expected_version=1,
    )

    assert updated.occurrence_count == 2
    assert updated.record_version == 2
    assert updated.metadata[
        "failed_probes"
    ] == 4


def test_incident_acknowledge_and_resolve(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    incident = make_incident()

    store.create_incident(incident)

    acknowledged = store.acknowledge_incident(
        incident.incident_id,
        acknowledged_by="engineer:hani",
        expected_version=1,
    )

    assert (
        acknowledged.status
        is NotificationIncidentStatus
        .ACKNOWLEDGED
    )
    assert (
        acknowledged.acknowledged_by
        == "engineer:hani"
    )

    resolved = store.resolve_incident(
        incident.incident_id,
        resolved_by="engineer:hani",
        expected_version=2,
    )

    assert (
        resolved.status
        is NotificationIncidentStatus.RESOLVED
    )
    assert resolved.resolved_at is not None

    assert (
        store.get_open_incident_by_fingerprint(
            incident.fingerprint
        )
        is None
    )


def test_new_incident_allowed_after_resolution(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    first = make_incident()

    store.create_incident(first)

    store.resolve_incident(
        first.incident_id,
        resolved_by="system",
        expected_version=1,
    )

    second = make_incident(
        incident_id="incident:002"
    )

    store.create_incident(second)

    assert store.get_incident(
        second.incident_id
    ) == second


def test_delivery_status_lifecycle(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    incident = make_incident()

    store.create_incident(incident)

    delivery = NotificationDelivery(
        delivery_id="delivery:001",
        incident_id=incident.incident_id,
        channel=NotificationChannel.WHATSAPP,
        notification_type=(
            NotificationType.FIRING
        ),
        status=(
            NotificationDeliveryStatus.PENDING
        ),
        destination="966500000000",
    )

    store.create_delivery(delivery)

    sent = store.update_delivery_status(
        delivery.delivery_id,
        status=NotificationDeliveryStatus.SENT,
        provider_message_id="wa-message-1",
    )

    assert (
        sent.status
        is NotificationDeliveryStatus.SENT
    )
    assert sent.attempt_count == 1
    assert sent.sent_at is not None
    assert (
        sent.provider_message_id
        == "wa-message-1"
    )


def test_delivery_requires_existing_incident(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    delivery = NotificationDelivery(
        delivery_id="delivery:missing",
        incident_id="incident:missing",
        channel=NotificationChannel.EMAIL,
        notification_type=(
            NotificationType.FIRING
        ),
        status=(
            NotificationDeliveryStatus.PENDING
        ),
        destination="noc@example.com",
    )

    with pytest.raises(
        NotificationStoreError
    ):
        store.create_delivery(delivery)


def test_active_suppression_filter(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    now = datetime.now(timezone.utc)

    active = NotificationSuppression(
        suppression_id="suppression:active",
        name="Maintenance",
        kind=(
            NotificationSuppressionKind
            .MAINTENANCE
        ),
        enabled=True,
        starts_at=now - timedelta(minutes=10),
        ends_at=now + timedelta(minutes=10),
        reason="Router upgrade",
        event_types=("device_down",),
        device_ids=("25",),
    )

    expired = NotificationSuppression(
        suppression_id="suppression:expired",
        name="Expired maintenance",
        kind=(
            NotificationSuppressionKind
            .MAINTENANCE
        ),
        enabled=True,
        starts_at=now - timedelta(hours=2),
        ends_at=now - timedelta(hours=1),
    )

    store.create_suppression(active)
    store.create_suppression(expired)

    suppressions = (
        store.list_active_suppressions(
            at=now
        )
    )

    assert [
        item.suppression_id
        for item in suppressions
    ] == [
        "suppression:active",
    ]

    assert suppressions[0].device_ids == (
        "25",
    )


def test_resolved_incident_cannot_be_acknowledged(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    incident = make_incident()

    store.create_incident(incident)

    resolved = store.resolve_incident(
        incident.incident_id,
        resolved_by="system",
        expected_version=1,
    )

    with pytest.raises(
        NotificationStoreError,
        match="cannot be acknowledged",
    ):
        store.acknowledge_incident(
            resolved.incident_id,
            acknowledged_by="engineer",
            expected_version=2,
        )
