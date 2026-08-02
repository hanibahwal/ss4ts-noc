from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.notification import (
    NotificationChannel,
    NotificationEscalationStep,
    NotificationIncident,
    NotificationIncidentStatus,
    NotificationPolicy,
    NotificationRecipient,
    NotificationType,
)
from app.models.notification_escalation import (
    NotificationEscalationDecision,
    NotificationEscalationDecisionCode,
    NotificationEscalationExecution,
)
from app.services.notification_escalation import (
    NotificationEscalationEngine,
    evaluate_notification_escalation,
)
from app.services.notification_store import (
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
    *,
    incident_status: (
        NotificationIncidentStatus
    ) = NotificationIncidentStatus.OPEN,
    current_level: int = 0,
    recipient_enabled: bool = True,
) -> NotificationStore:
    store = NotificationStore(
        tmp_path / "notifications.sqlite3"
    )

    store.create_policy(
        NotificationPolicy(
            policy_id="policy:001",
            name="Critical escalation",
            conditions={},
            actions={},
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    store.create_recipient(
        NotificationRecipient(
            recipient_id="recipient:l1",
            name="NOC Level 1",
            channel=(
                NotificationChannel.WHATSAPP
            ),
            address="966500000001",
            enabled=recipient_enabled,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    store.create_recipient(
        NotificationRecipient(
            recipient_id="recipient:l2",
            name="NOC Level 2",
            channel=(
                NotificationChannel.EMAIL
            ),
            address="manager@example.com",
            enabled=True,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    store.add_escalation_step(
        NotificationEscalationStep(
            escalation_step_id="step:001",
            policy_id="policy:001",
            step_order=1,
            delay_seconds=60,
            channel=(
                NotificationChannel.WHATSAPP
            ),
            recipient_id="recipient:l1",
            created_at=BASE_TIME,
        )
    )

    store.add_escalation_step(
        NotificationEscalationStep(
            escalation_step_id="step:002",
            policy_id="policy:001",
            step_order=2,
            delay_seconds=300,
            channel=(
                NotificationChannel.EMAIL
            ),
            recipient_id="recipient:l2",
            created_at=BASE_TIME,
        )
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
            status=incident_status,
            title="Device unreachable",
            message="Router is down",
            device_id="25",
            current_escalation_level=(
                current_level
            ),
            first_seen_at=BASE_TIME,
            last_seen_at=BASE_TIME,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    return store


def test_first_step_not_due(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    decision = (
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id="policy:001",
            evaluated_at=(
                BASE_TIME
                + timedelta(seconds=59)
            ),
        )
    )

    assert decision.should_escalate is False
    assert (
        decision.code
        is NotificationEscalationDecisionCode
        .NOT_DUE
    )


def test_first_step_ready(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    decision = (
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id="policy:001",
            evaluated_at=(
                BASE_TIME
                + timedelta(seconds=60)
            ),
        )
    )

    assert decision.should_escalate is True
    assert (
        decision.code
        is NotificationEscalationDecisionCode
        .READY
    )
    assert decision.step is not None
    assert decision.step.step_order == 1
    assert decision.recipient is not None
    assert (
        decision.recipient.address
        == "966500000001"
    )


def test_execute_creates_escalation_delivery(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    engine = NotificationEscalationEngine(
        store
    )

    decision = engine.evaluate(
        "incident:001",
        policy_id="policy:001",
        evaluated_at=(
            BASE_TIME
            + timedelta(seconds=60)
        ),
    )

    execution = engine.execute(
        decision,
        delivery_id="delivery:escalation:1",
        created_at=(
            BASE_TIME
            + timedelta(seconds=60)
        ),
    )

    assert isinstance(
        execution,
        NotificationEscalationExecution,
    )
    assert (
        execution.delivery.notification_type
        is NotificationType.ESCALATION
    )
    assert (
        execution.delivery.destination
        == "966500000001"
    )
    assert (
        execution.delivery.metadata[
            "escalation_step_id"
        ]
        == "step:001"
    )
    assert execution.escalation_level == 1
    assert execution.incident.record_version == 2


def test_second_level_selected(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path,
        current_level=1,
    )

    decision = (
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id="policy:001",
            evaluated_at=(
                BASE_TIME
                + timedelta(seconds=300)
            ),
        )
    )

    assert decision.should_escalate is True
    assert decision.step is not None
    assert decision.step.step_order == 2
    assert (
        decision.step.channel
        is NotificationChannel.EMAIL
    )


def test_no_step_after_last_level(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path,
        current_level=2,
    )

    decision = (
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id="policy:001",
            evaluated_at=(
                BASE_TIME
                + timedelta(hours=1)
            ),
        )
    )

    assert decision.should_escalate is False
    assert (
        decision.code
        is NotificationEscalationDecisionCode
        .COMPLETE
    )


@pytest.mark.parametrize(
    "status",
    [
        NotificationIncidentStatus.RESOLVED,
        NotificationIncidentStatus.SUPPRESSED,
    ],
)
def test_inactive_incident_not_escalated(
    tmp_path,
    status,
) -> None:
    store = make_store(
        tmp_path,
        incident_status=status,
    )

    decision = (
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id="policy:001",
            evaluated_at=(
                BASE_TIME
                + timedelta(hours=1)
            ),
        )
    )

    assert decision.should_escalate is False
    assert (
        decision.code
        is NotificationEscalationDecisionCode
        .INCIDENT_INACTIVE
    )


def test_acknowledged_incident_can_escalate(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path,
        incident_status=(
            NotificationIncidentStatus
            .ACKNOWLEDGED
        ),
    )

    decision = (
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id="policy:001",
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=2)
            ),
        )
    )

    assert decision.should_escalate is True


def test_disabled_recipient_blocks_step(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path,
        recipient_enabled=False,
    )

    decision = (
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id="policy:001",
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=2)
            ),
        )
    )

    assert decision.should_escalate is False
    assert (
        decision.code
        is NotificationEscalationDecisionCode
        .RECIPIENT_DISABLED
    )


def test_duplicate_escalation_detected(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    engine = NotificationEscalationEngine(
        store
    )

    at = BASE_TIME + timedelta(minutes=2)

    first = engine.evaluate(
        "incident:001",
        policy_id="policy:001",
        evaluated_at=at,
    )

    engine.execute(
        first,
        delivery_id="delivery:escalation:1",
        created_at=at,
    )

    existing = (
        store.find_escalation_delivery(
            incident_id="incident:001",
            policy_id="policy:001",
            escalation_step_id="step:001",
        )
    )

    assert existing is not None
    assert (
        existing.delivery_id
        == "delivery:escalation:1"
    )


def test_duplicate_found_before_execution(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    engine = NotificationEscalationEngine(
        store
    )

    at = BASE_TIME + timedelta(minutes=2)

    decision = engine.evaluate(
        "incident:001",
        policy_id="policy:001",
        evaluated_at=at,
    )

    engine.execute(
        decision,
        delivery_id="delivery:escalation:1",
        created_at=at,
    )

    existing = store.find_escalation_delivery(
        incident_id="incident:001",
        policy_id="policy:001",
        escalation_step_id="step:001",
    )

    assert existing is not None


def test_escalation_level_version_conflict(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    with pytest.raises(
        NotificationVersionConflict
    ):
        store.update_incident_escalation_level(
            "incident:001",
            escalation_level=1,
            expected_version=999,
        )


def test_escalation_level_cannot_decrease(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path,
        current_level=1,
    )

    incident = store.get_incident(
        "incident:001"
    )

    assert incident is not None

    with pytest.raises(
        ValueError,
        match="cannot decrease",
    ):
        store.update_incident_escalation_level(
            "incident:001",
            escalation_level=0,
            expected_version=(
                incident.record_version
            ),
        )


def test_missing_policy_rejected(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    decision = (
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id=None,
            evaluated_at=(
                BASE_TIME
                + timedelta(hours=1)
            ),
        )
    )

    assert decision.should_escalate is False
    assert (
        decision.code
        is NotificationEscalationDecisionCode
        .NO_POLICY
    )


def test_functional_helper(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    decision = (
        evaluate_notification_escalation(
            store,
            "incident:001",
            policy_id="policy:001",
            evaluated_at=(
                BASE_TIME
                + timedelta(minutes=2)
            ),
        )
    )

    assert decision.should_escalate is True


def test_naive_time_rejected(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        NotificationEscalationEngine(
            store
        ).evaluate(
            "incident:001",
            policy_id="policy:001",
            evaluated_at=datetime(
                2026,
                8,
                2,
                18,
                1,
            ),
        )


def test_non_executable_decision_rejected(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    engine = NotificationEscalationEngine(
        store
    )

    decision = engine.evaluate(
        "incident:001",
        policy_id="policy:001",
        evaluated_at=BASE_TIME,
    )

    with pytest.raises(
        ValueError,
        match="not executable",
    ):
        engine.execute(decision)
