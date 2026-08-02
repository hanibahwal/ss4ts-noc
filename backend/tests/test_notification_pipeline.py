from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.models.notification import (
    NotificationChannel,
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
from app.models.notification_deduplication import (
    DeduplicationContext,
)
from app.models.notification_dispatch import (
    NotificationDispatchRequest,
    NotificationDispatchResult,
)
from app.models.notification_pipeline import (
    NotificationPipelineRequest,
    NotificationPipelineStatus,
)
from app.models.notification_retry import (
    NotificationRetryPolicy,
)
from app.models.notification_suppression_engine import (
    NotificationSuppressionContext,
)
from app.services.notification_dispatcher import (
    NotificationDispatcher,
)
from app.services.notification_pipeline import (
    NotificationPipeline,
    execute_notification_pipeline,
)
from app.services.notification_retry import (
    NotificationRetryEngine,
)
from app.services.notification_store import (
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


@dataclass
class SuccessfulTransport:
    calls: int = 0

    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        self.calls += 1

        return NotificationDispatchResult.success(
            provider_message_id="provider:001"
        )


@dataclass
class FailedTransport:
    retryable: bool = True
    calls: int = 0

    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        self.calls += 1

        return NotificationDispatchResult.failure(
            "Provider unavailable",
            retryable=self.retryable,
        )


def make_store(
    tmp_path,
) -> NotificationStore:
    store = NotificationStore(
        tmp_path / "notifications.sqlite3"
    )

    store.create_policy(
        NotificationPolicy(
            policy_id="policy:001",
            name="Pipeline policy",
            cooldown_seconds=900,
            conditions={},
            actions={},
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
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
            status=(
                NotificationIncidentStatus.OPEN
            ),
            title="Device unreachable",
            message="Router is down",
            device_id="device:001",
            site_id="site:001",
            first_seen_at=BASE_TIME,
            last_seen_at=BASE_TIME,
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    return store


def make_request(
    *,
    force: bool = False,
    delivery_id: str = "delivery:pipeline:001",
    evaluated_at: datetime = BASE_TIME,
    escalation_policy_id: str | None = None,
) -> NotificationPipelineRequest:
    return NotificationPipelineRequest(
        incident_id="incident:001",
        policy_id="policy:001",
        channel=(
            NotificationChannel.WHATSAPP
        ),
        destination="966500000000",
        subject="Critical alert",
        body="Router is unreachable",
        notification_type=(
            NotificationType.FIRING
        ),
        delivery_id=delivery_id,
        escalation_policy_id=(
            escalation_policy_id
        ),
        deduplication_context=(
            DeduplicationContext(
                incident_id="incident:001",
                policy_id="policy:001",
                notification_type="firing",
                current_severity="critical",
                cooldown_seconds=900,
                force=force,
            )
        ),
        suppression_context=(
            NotificationSuppressionContext(
                event_type="device_down",
                evaluated_at=evaluated_at,
                site_id="site:001",
                device_id="device:001",
                severity="critical",
                notification_type=(
                    NotificationType.FIRING
                ),
                force=force,
            )
        ),
        metadata={
            "site_name": "Test site",
        },
        evaluated_at=evaluated_at,
    )


def make_dispatcher(
    transport,
) -> NotificationDispatcher:
    return NotificationDispatcher(
        {
            NotificationChannel.WHATSAPP: (
                transport
            ),
        }
    )


def test_successful_pipeline(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    transport = SuccessfulTransport()

    result = NotificationPipeline(
        store,
        make_dispatcher(transport),
    ).execute(
        make_request()
    )

    assert (
        result.status
        is NotificationPipelineStatus.SENT
    )
    assert result.successful is True
    assert result.execution is not None
    assert (
        result.execution.delivery.status
        is NotificationDeliveryStatus.SENT
    )
    assert (
        result.execution
        .delivery.attempt_count
        == 1
    )
    assert transport.calls == 1


def test_pipeline_creates_delivery_metadata(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    result = NotificationPipeline(
        store,
        make_dispatcher(
            SuccessfulTransport()
        ),
    ).execute(
        make_request()
    )

    assert result.delivery is not None
    assert result.delivery.metadata["pipeline"] is True
    assert (
        result.delivery.metadata["severity"]
        == "critical"
    )
    assert (
        result.delivery.metadata["site_name"]
        == "Test site"
    )


def test_duplicate_stops_pipeline(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    first = NotificationPipeline(
        store,
        make_dispatcher(
            SuccessfulTransport()
        ),
    )

    first.execute(
        make_request()
    )

    second_transport = SuccessfulTransport()

    result = NotificationPipeline(
        store,
        make_dispatcher(
            second_transport
        ),
    ).execute(
        make_request(
            delivery_id="delivery:pipeline:002",
            evaluated_at=(
                BASE_TIME
                + timedelta(seconds=30)
            ),
        )
    )

    assert (
        result.status
        is NotificationPipelineStatus.DUPLICATE
    )
    assert result.stopped is True
    assert second_transport.calls == 0
    assert (
        store.get_delivery(
            "delivery:pipeline:002"
        )
        is None
    )


def test_suppression_stops_pipeline(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    store.create_suppression(
        NotificationSuppression(
            suppression_id="suppression:001",
            name="Maintenance",
            kind=(
                NotificationSuppressionKind
                .MAINTENANCE
            ),
            enabled=True,
            starts_at=(
                BASE_TIME - timedelta(hours=1)
            ),
            ends_at=(
                BASE_TIME + timedelta(hours=1)
            ),
            reason="Scheduled maintenance",
            site_ids=("site:001",),
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    transport = SuccessfulTransport()

    result = NotificationPipeline(
        store,
        make_dispatcher(transport),
    ).execute(
        make_request()
    )

    assert (
        result.status
        is NotificationPipelineStatus.SUPPRESSED
    )
    assert transport.calls == 0
    assert result.suppression_decision is not None
    assert (
        result.reason
        == "Scheduled maintenance"
    )


def test_force_bypasses_suppression(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    store.create_suppression(
        NotificationSuppression(
            suppression_id="suppression:001",
            name="Maintenance",
            kind=(
                NotificationSuppressionKind
                .MAINTENANCE
            ),
            enabled=True,
            starts_at=(
                BASE_TIME - timedelta(hours=1)
            ),
            ends_at=(
                BASE_TIME + timedelta(hours=1)
            ),
            reason="Scheduled maintenance",
            created_at=BASE_TIME,
            updated_at=BASE_TIME,
        )
    )

    result = NotificationPipeline(
        store,
        make_dispatcher(
            SuccessfulTransport()
        ),
    ).execute(
        make_request(force=True)
    )

    assert (
        result.status
        is NotificationPipelineStatus.SENT
    )


def test_retryable_failure_schedules_retry(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    result = NotificationPipeline(
        store,
        make_dispatcher(
            FailedTransport(
                retryable=True
            )
        ),
    ).execute(
        make_request()
    )

    assert (
        result.status
        is NotificationPipelineStatus
        .RETRY_SCHEDULED
    )
    assert result.retry_decision is not None
    assert result.retry_decision.should_retry is True
    assert result.delivery is not None
    assert (
        result.delivery.status
        is NotificationDeliveryStatus.PENDING
    )
    assert (
        result.delivery.scheduled_at
        == BASE_TIME
        + timedelta(seconds=30)
    )


def test_permanent_failure_not_retried(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    result = NotificationPipeline(
        store,
        make_dispatcher(
            FailedTransport(
                retryable=False
            )
        ),
    ).execute(
        make_request()
    )

    assert (
        result.status
        is NotificationPipelineStatus.FAILED
    )
    assert result.retry_decision is not None
    assert result.retry_decision.should_retry is False
    assert result.delivery is not None
    assert (
        result.delivery.status
        is NotificationDeliveryStatus.FAILED
    )


def test_max_attempts_triggers_escalation(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    store.create_recipient(
        NotificationRecipient(
            recipient_id="recipient:manager",
            name="Manager",
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
            delay_seconds=0,
            channel=(
                NotificationChannel.EMAIL
            ),
            recipient_id="recipient:manager",
            created_at=BASE_TIME,
        )
    )

    retry_engine = NotificationRetryEngine(
        NotificationRetryPolicy(
            max_attempts=1,
            initial_delay_seconds=30,
            backoff_multiplier=2,
            max_delay_seconds=300,
        )
    )

    result = NotificationPipeline(
        store,
        make_dispatcher(
            FailedTransport(
                retryable=True
            )
        ),
        retry_engine=retry_engine,
    ).execute(
        make_request(
            escalation_policy_id="policy:001"
        )
    )

    assert (
        result.status
        is NotificationPipelineStatus.ESCALATED
    )
    assert result.escalation_result is not None

    escalation_delivery = (
        store.find_escalation_delivery(
            incident_id="incident:001",
            policy_id="policy:001",
            escalation_step_id="step:001",
        )
    )

    assert escalation_delivery is not None
    assert (
        escalation_delivery.notification_type
        is NotificationType.ESCALATION
    )


def test_functional_helper(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    result = execute_notification_pipeline(
        store,
        make_dispatcher(
            SuccessfulTransport()
        ),
        make_request(),
    )

    assert result.successful is True
