from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationType,
)
from app.models.notification_dispatch import (
    NotificationDispatchRequest,
)
from app.services.notification_dispatcher import (
    NotificationDispatcher,
)
from app.services.notification_transports import (
    DashboardNotificationAdapter,
    EmailNotificationAdapter,
    PermanentNotificationProviderError,
    ProviderResponse,
    TelegramNotificationAdapter,
    TemporaryNotificationProviderError,
    WebhookNotificationAdapter,
    WhatsAppNotificationAdapter,
)


def make_request(
    channel: NotificationChannel,
    *,
    destination: str,
    subject: str = "Device down",
) -> NotificationDispatchRequest:
    delivery = NotificationDelivery(
        delivery_id="delivery:001",
        incident_id="incident:001",
        channel=channel,
        notification_type=(
            NotificationType.FIRING
        ),
        status=(
            NotificationDeliveryStatus.SENDING
        ),
        destination=destination,
        metadata={
            "severity": "critical",
        },
    )

    return NotificationDispatchRequest(
        delivery=delivery,
        subject=subject,
        body="Router 25 is unreachable",
        metadata={
            "site_id": "site:001",
        },
    )


@dataclass
class FakeWhatsAppClient:
    response: ProviderResponse
    destination: str | None = None
    text: str | None = None

    def send_text(
        self,
        *,
        destination: str,
        text: str,
    ) -> ProviderResponse:
        self.destination = destination
        self.text = text
        return self.response


@dataclass
class FakeEmailClient:
    response: ProviderResponse
    recipient: str | None = None
    subject: str | None = None
    body: str | None = None

    def send_email(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
    ) -> ProviderResponse:
        self.recipient = recipient
        self.subject = subject
        self.body = body
        return self.response


@dataclass
class FakeTelegramClient:
    response: ProviderResponse
    chat_id: str | None = None
    text: str | None = None

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
    ) -> ProviderResponse:
        self.chat_id = chat_id
        self.text = text
        return self.response


@dataclass
class FakeWebhookClient:
    response: ProviderResponse
    url: str | None = None
    payload: dict[str, Any] | None = None

    def post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
    ) -> ProviderResponse:
        self.url = url
        self.payload = payload
        return self.response


@dataclass
class FakeDashboardPublisher:
    response: ProviderResponse
    topic: str | None = None
    event: dict[str, Any] | None = None

    def publish(
        self,
        *,
        topic: str,
        event: dict[str, Any],
    ) -> ProviderResponse:
        self.topic = topic
        self.event = event
        return self.response


class TemporaryFailureClient:
    def send_text(
        self,
        *,
        destination: str,
        text: str,
    ) -> ProviderResponse:
        raise TemporaryNotificationProviderError(
            "Provider timeout"
        )


class PermanentFailureClient:
    def send_text(
        self,
        *,
        destination: str,
        text: str,
    ) -> ProviderResponse:
        raise PermanentNotificationProviderError(
            "Invalid destination"
        )


class UnexpectedFailureClient:
    def send_text(
        self,
        *,
        destination: str,
        text: str,
    ) -> ProviderResponse:
        raise RuntimeError("Unexpected failure")


class InvalidResponseClient:
    def send_text(
        self,
        *,
        destination: str,
        text: str,
    ):
        return {"ok": True}


def test_provider_success_response() -> None:
    response = ProviderResponse.success(
        message_id="message:1"
    )

    assert response.successful is True
    assert response.message_id == "message:1"


def test_provider_failure_response() -> None:
    response = ProviderResponse.failure(
        "Temporary failure",
        retryable=True,
    )

    assert response.successful is False
    assert response.retryable is True


def test_provider_failure_requires_error() -> None:
    with pytest.raises(ValueError):
        ProviderResponse(
            successful=False,
            error_message="",
        )


def test_whatsapp_adapter_success() -> None:
    client = FakeWhatsAppClient(
        ProviderResponse.success(
            message_id="wa:001"
        )
    )

    adapter = WhatsAppNotificationAdapter(
        client
    )

    result = adapter.dispatch(
        make_request(
            NotificationChannel.WHATSAPP,
            destination="966500000000",
        )
    )

    assert result.successful is True
    assert result.provider_message_id == "wa:001"
    assert client.destination == "966500000000"
    assert client.text == "Router 25 is unreachable"


def test_email_adapter_success() -> None:
    client = FakeEmailClient(
        ProviderResponse.success(
            message_id="email:001"
        )
    )

    adapter = EmailNotificationAdapter(client)

    result = adapter.dispatch(
        make_request(
            NotificationChannel.EMAIL,
            destination="noc@example.com",
            subject="Critical alarm",
        )
    )

    assert result.successful is True
    assert client.recipient == "noc@example.com"
    assert client.subject == "Critical alarm"
    assert client.body == "Router 25 is unreachable"


def test_email_adapter_default_subject() -> None:
    client = FakeEmailClient(
        ProviderResponse.success()
    )

    adapter = EmailNotificationAdapter(
        client,
        default_subject="Default subject",
    )

    adapter.dispatch(
        make_request(
            NotificationChannel.EMAIL,
            destination="noc@example.com",
            subject="",
        )
    )

    assert client.subject == "Default subject"


def test_telegram_adapter_success() -> None:
    client = FakeTelegramClient(
        ProviderResponse.success(
            message_id="tg:001"
        )
    )

    result = TelegramNotificationAdapter(
        client
    ).dispatch(
        make_request(
            NotificationChannel.TELEGRAM,
            destination="-100123456",
        )
    )

    assert result.successful is True
    assert client.chat_id == "-100123456"


def test_webhook_adapter_payload() -> None:
    client = FakeWebhookClient(
        ProviderResponse.success(
            message_id="webhook:001"
        )
    )

    result = WebhookNotificationAdapter(
        client
    ).dispatch(
        make_request(
            NotificationChannel.WEBHOOK,
            destination=(
                "https://example.test/hook"
            ),
        )
    )

    assert result.successful is True
    assert (
        client.url
        == "https://example.test/hook"
    )
    assert client.payload is not None
    assert (
        client.payload["delivery_id"]
        == "delivery:001"
    )
    assert (
        client.payload["metadata"]["severity"]
        == "critical"
    )
    assert (
        client.payload["metadata"]["site_id"]
        == "site:001"
    )


def test_dashboard_adapter_event() -> None:
    publisher = FakeDashboardPublisher(
        ProviderResponse.success(
            message_id="dashboard:001"
        )
    )

    result = DashboardNotificationAdapter(
        publisher
    ).dispatch(
        make_request(
            NotificationChannel.DASHBOARD,
            destination="noc-alerts",
        )
    )

    assert result.successful is True
    assert publisher.topic == "noc-alerts"
    assert publisher.event is not None
    assert (
        publisher.event["incident_id"]
        == "incident:001"
    )


def test_channel_mismatch_fails() -> None:
    adapter = WhatsAppNotificationAdapter(
        FakeWhatsAppClient(
            ProviderResponse.success()
        )
    )

    result = adapter.dispatch(
        make_request(
            NotificationChannel.EMAIL,
            destination="noc@example.com",
        )
    )

    assert result.successful is False
    assert result.retryable is False
    assert "channel mismatch" in (
        result.error_message or ""
    ).lower()


def test_provider_failure_preserved() -> None:
    adapter = WhatsAppNotificationAdapter(
        FakeWhatsAppClient(
            ProviderResponse.failure(
                "Provider unavailable",
                retryable=True,
            )
        )
    )

    result = adapter.dispatch(
        make_request(
            NotificationChannel.WHATSAPP,
            destination="966500000000",
        )
    )

    assert result.successful is False
    assert result.retryable is True
    assert (
        result.error_message
        == "Provider unavailable"
    )


def test_temporary_exception_is_retryable() -> None:
    result = WhatsAppNotificationAdapter(
        TemporaryFailureClient()
    ).dispatch(
        make_request(
            NotificationChannel.WHATSAPP,
            destination="966500000000",
        )
    )

    assert result.successful is False
    assert result.retryable is True
    assert result.error_message == "Provider timeout"


def test_permanent_exception_not_retryable() -> None:
    result = WhatsAppNotificationAdapter(
        PermanentFailureClient()
    ).dispatch(
        make_request(
            NotificationChannel.WHATSAPP,
            destination="invalid",
        )
    )

    assert result.successful is False
    assert result.retryable is False
    assert (
        result.error_message
        == "Invalid destination"
    )


def test_unexpected_exception_not_retryable() -> None:
    result = WhatsAppNotificationAdapter(
        UnexpectedFailureClient()
    ).dispatch(
        make_request(
            NotificationChannel.WHATSAPP,
            destination="966500000000",
        )
    )

    assert result.successful is False
    assert result.retryable is False
    assert (
        result.metadata["exception_type"]
        == "RuntimeError"
    )


def test_invalid_provider_response_fails() -> None:
    result = WhatsAppNotificationAdapter(
        InvalidResponseClient()
    ).dispatch(
        make_request(
            NotificationChannel.WHATSAPP,
            destination="966500000000",
        )
    )

    assert result.successful is False
    assert "invalid response" in (
        result.error_message or ""
    ).lower()


def test_adapter_works_with_dispatcher() -> None:
    adapter = WhatsAppNotificationAdapter(
        FakeWhatsAppClient(
            ProviderResponse.success(
                message_id="wa:dispatcher"
            )
        )
    )

    dispatcher = NotificationDispatcher(
        {
            NotificationChannel.WHATSAPP: (
                adapter
            ),
        }
    )

    result = dispatcher.dispatch(
        make_request(
            NotificationChannel.WHATSAPP,
            destination="966500000000",
        )
    )

    assert result.successful is True
    assert (
        result.provider_message_id
        == "wa:dispatcher"
    )


@pytest.mark.parametrize(
    ("channel", "adapter", "destination"),
    [
        (
            NotificationChannel.WHATSAPP,
            WhatsAppNotificationAdapter(
                FakeWhatsAppClient(
                    ProviderResponse.success()
                )
            ),
            "966500000000",
        ),
        (
            NotificationChannel.EMAIL,
            EmailNotificationAdapter(
                FakeEmailClient(
                    ProviderResponse.success()
                )
            ),
            "noc@example.com",
        ),
        (
            NotificationChannel.TELEGRAM,
            TelegramNotificationAdapter(
                FakeTelegramClient(
                    ProviderResponse.success()
                )
            ),
            "-100123456",
        ),
        (
            NotificationChannel.WEBHOOK,
            WebhookNotificationAdapter(
                FakeWebhookClient(
                    ProviderResponse.success()
                )
            ),
            "https://example.test/hook",
        ),
        (
            NotificationChannel.DASHBOARD,
            DashboardNotificationAdapter(
                FakeDashboardPublisher(
                    ProviderResponse.success()
                )
            ),
            "noc-alerts",
        ),
    ],
)
def test_all_adapters_dispatch(
    channel,
    adapter,
    destination,
) -> None:
    result = adapter.dispatch(
        make_request(
            channel,
            destination=destination,
        )
    )

    assert result.successful is True
    assert (
        result.metadata["channel"]
        == channel.value
    )
