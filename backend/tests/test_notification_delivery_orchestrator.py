from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
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
    DeliveryExecutionStatus,
)
from app.models.notification_dispatch import (
    NotificationDispatchRequest,
    NotificationDispatchResult,
)
from app.services.notification_delivery_orchestrator import (
    NotificationDeliveryOrchestrator,
    execute_notification_delivery,
)
from app.services.notification_dispatcher import (
    NotificationDispatcher,
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


def create_delivery(
    store: NotificationStore,
    *,
    delivery_id: str = "delivery:001",
    status: NotificationDeliveryStatus = (
        NotificationDeliveryStatus.PENDING
    ),
    attempt_count: int = 0,
) -> NotificationDelivery:
    delivery = NotificationDelivery(
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
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
    )

    store.create_delivery(delivery)

    return delivery


@dataclass
class SuccessfulTransport:
    calls: int = 0
    request: NotificationDispatchRequest | None = (
        None
    )

    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        self.calls += 1
        self.request = request

        return NotificationDispatchResult.success(
            provider_message_id="wa:001",
            metadata={
                "provider": "fake-whatsapp",
            },
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


class RaisingTransport:
    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        raise RuntimeError(
            "Transport crashed"
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


def test_successful_delivery_is_sent(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    transport = SuccessfulTransport()

    result = (
        NotificationDeliveryOrchestrator(
            store,
            make_dispatcher(transport),
        ).execute(
            "delivery:001",
            body="Router is down",
            subject="Critical alert",
        )
    )

    assert result.successful is True
    assert (
        result.status
        is DeliveryExecutionStatus.SENT
    )
    assert (
        result.delivery.status
        is NotificationDeliveryStatus.SENT
    )
    assert result.delivery.attempt_count == 1
    assert (
        result.delivery.provider_message_id
        == "wa:001"
    )
    assert result.delivery.sent_at is not None
    assert transport.calls == 1


def test_request_contains_sending_delivery(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    transport = SuccessfulTransport()

    NotificationDeliveryOrchestrator(
        store,
        make_dispatcher(transport),
    ).execute(
        "delivery:001",
        body="Router is down",
    )

    assert transport.request is not None
    assert (
        transport.request.delivery.status
        is NotificationDeliveryStatus.SENDING
    )
    assert (
        transport.request
        .delivery.attempt_count
        == 1
    )


def test_failed_delivery_is_persisted(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    result = (
        NotificationDeliveryOrchestrator(
            store,
            make_dispatcher(
                FailedTransport(
                    retryable=True
                )
            ),
        ).execute(
            "delivery:001",
            body="Router is down",
        )
    )

    assert result.successful is False
    assert (
        result.status
        is DeliveryExecutionStatus.FAILED
    )
    assert (
        result.delivery.status
        is NotificationDeliveryStatus.FAILED
    )
    assert result.delivery.attempt_count == 1
    assert (
        result.delivery.error_message
        == "Provider unavailable"
    )
    assert result.retryable is True


def test_retry_increments_attempt_once(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    first = (
        NotificationDeliveryOrchestrator(
            store,
            make_dispatcher(
                FailedTransport()
            ),
        ).execute(
            "delivery:001",
            body="Router is down",
        )
    )

    assert first.delivery.attempt_count == 1

    second = (
        NotificationDeliveryOrchestrator(
            store,
            make_dispatcher(
                SuccessfulTransport()
            ),
        ).execute(
            "delivery:001",
            body="Router is still down",
        )
    )

    assert second.delivery.attempt_count == 2
    assert (
        second.delivery.status
        is NotificationDeliveryStatus.SENT
    )


def test_unexpected_error_marks_failed(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    result = (
        NotificationDeliveryOrchestrator(
            store,
            make_dispatcher(
                RaisingTransport()
            ),
        ).execute(
            "delivery:001",
            body="Router is down",
        )
    )

    assert result.successful is False
    assert (
        result.delivery.status
        is NotificationDeliveryStatus.FAILED
    )
    assert result.delivery.attempt_count == 1
    assert (
        result.error_message
        == "Transport crashed"
    )


def test_missing_transport_marks_failed(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    result = (
        NotificationDeliveryOrchestrator(
            store,
            NotificationDispatcher(),
        ).execute(
            "delivery:001",
            body="Router is down",
        )
    )

    assert result.successful is False
    assert (
        result.delivery.status
        is NotificationDeliveryStatus.FAILED
    )
    assert (
        "No notification transport"
        in (result.error_message or "")
    )


def test_sent_delivery_cannot_restart(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    create_delivery(
        store,
        status=(
            NotificationDeliveryStatus.SENT
        ),
        attempt_count=1,
    )

    orchestrator = (
        NotificationDeliveryOrchestrator(
            store,
            make_dispatcher(
                SuccessfulTransport()
            ),
        )
    )

    with pytest.raises(
        NotificationStoreError,
        match="cannot start",
    ):
        orchestrator.execute(
            "delivery:001",
            body="Router is down",
        )


def test_sending_delivery_cannot_restart(
    tmp_path,
) -> None:
    store = make_store(tmp_path)

    create_delivery(
        store,
        status=(
            NotificationDeliveryStatus.SENDING
        ),
        attempt_count=1,
    )

    with pytest.raises(
        NotificationStoreError,
        match="cannot start",
    ):
        NotificationDeliveryOrchestrator(
            store,
            make_dispatcher(
                SuccessfulTransport()
            ),
        ).execute(
            "delivery:001",
            body="Router is down",
        )


def test_cancel_pending_delivery(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    cancelled = store.cancel_delivery(
        "delivery:001",
        reason="Incident resolved",
    )

    assert (
        cancelled.status
        is NotificationDeliveryStatus.CANCELLED
    )
    assert cancelled.attempt_count == 0
    assert (
        cancelled.error_message
        == "Incident resolved"
    )


def test_cancelled_delivery_cannot_execute(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    store.cancel_delivery(
        "delivery:001"
    )

    with pytest.raises(
        NotificationStoreError,
        match="cannot start",
    ):
        NotificationDeliveryOrchestrator(
            store,
            make_dispatcher(
                SuccessfulTransport()
            ),
        ).execute(
            "delivery:001",
            body="Router is down",
        )


def test_functional_helper(
    tmp_path,
) -> None:
    store = make_store(tmp_path)
    create_delivery(store)

    result = execute_notification_delivery(
        store,
        make_dispatcher(
            SuccessfulTransport()
        ),
        "delivery:001",
        body="Router is down",
    )

    assert result.successful is True
    assert result.delivery.attempt_count == 1
