from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.notification import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationType,
)
from app.models.notification_dispatch import (
    NotificationDispatchRequest,
    NotificationDispatchResult,
    NotificationDispatchStatus,
)
from app.services.notification_dispatcher import (
    InvalidNotificationTransportResult,
    NotificationDispatcher,
    NotificationTransportAlreadyRegistered,
    NotificationTransportExecutionError,
    NotificationTransportNotRegistered,
    dispatch_notification,
)


def make_delivery(
    *,
    channel: NotificationChannel = (
        NotificationChannel.WHATSAPP
    ),
    destination: str = "966500000000",
) -> NotificationDelivery:
    return NotificationDelivery(
        delivery_id="delivery:001",
        incident_id="incident:001",
        channel=channel,
        notification_type=(
            NotificationType.FIRING
        ),
        status=(
            NotificationDeliveryStatus.PENDING
        ),
        destination=destination,
    )


def make_request(
    *,
    channel: NotificationChannel = (
        NotificationChannel.WHATSAPP
    ),
) -> NotificationDispatchRequest:
    return NotificationDispatchRequest(
        delivery=make_delivery(
            channel=channel
        ),
        subject="Device down",
        body="Router 25 is unreachable",
        metadata={
            "severity": "critical",
        },
    )


@dataclass
class SuccessfulTransport:
    provider_message_id: str = "provider:001"
    calls: int = 0
    last_request: (
        NotificationDispatchRequest | None
    ) = None

    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        self.calls += 1
        self.last_request = request

        return NotificationDispatchResult.success(
            provider_message_id=(
                self.provider_message_id
            ),
            metadata={
                "provider": "fake",
            },
        )


@dataclass
class FailedTransport:
    retryable: bool = True

    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        return NotificationDispatchResult.failure(
            "Provider temporarily unavailable",
            retryable=self.retryable,
        )


class RaisingTransport:
    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        raise RuntimeError(
            "Unexpected provider error"
        )


class ControlledErrorTransport:
    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        raise NotificationTransportExecutionError(
            "Provider timeout",
            retryable=True,
        )


class InvalidResultTransport:
    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ):
        return {
            "success": True,
        }


class MissingDispatchMethod:
    pass


def test_request_exposes_delivery_values() -> None:
    request = make_request()

    assert (
        request.channel
        is NotificationChannel.WHATSAPP
    )
    assert (
        request.destination
        == "966500000000"
    )


def test_request_rejects_empty_body() -> None:
    with pytest.raises(
        ValueError,
        match="body",
    ):
        NotificationDispatchRequest(
            delivery=make_delivery(),
            body="   ",
        )


def test_success_result_properties() -> None:
    result = NotificationDispatchResult.success(
        provider_message_id="message:1"
    )

    assert result.successful is True
    assert (
        result.status
        is NotificationDispatchStatus.SUCCESS
    )
    assert (
        result.provider_message_id
        == "message:1"
    )
    assert result.error_message is None
    assert result.retryable is False


def test_failure_result_properties() -> None:
    result = NotificationDispatchResult.failure(
        "Temporary failure",
        retryable=True,
    )

    assert result.successful is False
    assert (
        result.status
        is NotificationDispatchStatus.FAILED
    )
    assert (
        result.error_message
        == "Temporary failure"
    )
    assert result.retryable is True


def test_failed_result_requires_error() -> None:
    with pytest.raises(
        ValueError,
        match="error message",
    ):
        NotificationDispatchResult(
            status=(
                NotificationDispatchStatus.FAILED
            ),
            error_message="",
        )


def test_success_cannot_be_retryable() -> None:
    with pytest.raises(
        ValueError,
        match="retryable",
    ):
        NotificationDispatchResult(
            status=(
                NotificationDispatchStatus.SUCCESS
            ),
            retryable=True,
        )


def test_register_and_dispatch() -> None:
    transport = SuccessfulTransport()
    dispatcher = NotificationDispatcher()

    dispatcher.register(
        NotificationChannel.WHATSAPP,
        transport,
    )

    request = make_request()
    result = dispatcher.dispatch(request)

    assert result.successful is True
    assert transport.calls == 1
    assert transport.last_request == request


def test_constructor_registers_transports() -> None:
    dispatcher = NotificationDispatcher(
        {
            NotificationChannel.EMAIL: (
                SuccessfulTransport()
            ),
        }
    )

    assert dispatcher.has_transport(
        NotificationChannel.EMAIL
    )


def test_string_channel_registration() -> None:
    dispatcher = NotificationDispatcher()

    dispatcher.register(
        "telegram",
        SuccessfulTransport(),
    )

    assert dispatcher.has_transport(
        NotificationChannel.TELEGRAM
    )


def test_duplicate_registration_rejected() -> None:
    dispatcher = NotificationDispatcher()

    dispatcher.register(
        NotificationChannel.EMAIL,
        SuccessfulTransport(),
    )

    with pytest.raises(
        NotificationTransportAlreadyRegistered
    ):
        dispatcher.register(
            NotificationChannel.EMAIL,
            SuccessfulTransport(),
        )


def test_registration_can_replace() -> None:
    first = SuccessfulTransport(
        provider_message_id="first"
    )
    second = SuccessfulTransport(
        provider_message_id="second"
    )

    dispatcher = NotificationDispatcher()

    dispatcher.register(
        NotificationChannel.WEBHOOK,
        first,
    )
    dispatcher.register(
        NotificationChannel.WEBHOOK,
        second,
        replace=True,
    )

    result = dispatcher.dispatch(
        make_request(
            channel=(
                NotificationChannel.WEBHOOK
            )
        )
    )

    assert (
        result.provider_message_id
        == "second"
    )
    assert first.calls == 0
    assert second.calls == 1


def test_unregister_transport() -> None:
    dispatcher = NotificationDispatcher(
        {
            NotificationChannel.DASHBOARD: (
                SuccessfulTransport()
            ),
        }
    )

    assert dispatcher.unregister(
        NotificationChannel.DASHBOARD
    )
    assert not dispatcher.has_transport(
        NotificationChannel.DASHBOARD
    )
    assert not dispatcher.unregister(
        NotificationChannel.DASHBOARD
    )


def test_registered_channels_are_sorted() -> None:
    dispatcher = NotificationDispatcher()

    dispatcher.register_many(
        [
            (
                NotificationChannel.WHATSAPP,
                SuccessfulTransport(),
            ),
            (
                NotificationChannel.EMAIL,
                SuccessfulTransport(),
            ),
            (
                NotificationChannel.TELEGRAM,
                SuccessfulTransport(),
            ),
        ]
    )

    assert dispatcher.registered_channels() == (
        NotificationChannel.EMAIL,
        NotificationChannel.TELEGRAM,
        NotificationChannel.WHATSAPP,
    )


def test_missing_transport_rejected() -> None:
    dispatcher = NotificationDispatcher()

    with pytest.raises(
        NotificationTransportNotRegistered
    ):
        dispatcher.dispatch(
            make_request()
        )


def test_failed_transport_result_preserved() -> None:
    dispatcher = NotificationDispatcher(
        {
            NotificationChannel.WHATSAPP: (
                FailedTransport(
                    retryable=True
                )
            ),
        }
    )

    result = dispatcher.dispatch(
        make_request()
    )

    assert result.successful is False
    assert result.retryable is True


def test_controlled_transport_error_converted() -> None:
    dispatcher = NotificationDispatcher(
        {
            NotificationChannel.WHATSAPP: (
                ControlledErrorTransport()
            ),
        }
    )

    result = dispatcher.dispatch(
        make_request()
    )

    assert result.successful is False
    assert result.retryable is True
    assert (
        result.error_message
        == "Provider timeout"
    )


def test_unexpected_transport_error_converted() -> None:
    dispatcher = NotificationDispatcher(
        {
            NotificationChannel.WHATSAPP: (
                RaisingTransport()
            ),
        }
    )

    result = dispatcher.dispatch(
        make_request()
    )

    assert result.successful is False
    assert result.retryable is False
    assert (
        result.error_message
        == "Unexpected provider error"
    )
    assert (
        result.metadata["exception_type"]
        == "RuntimeError"
    )


def test_invalid_transport_result_rejected() -> None:
    dispatcher = NotificationDispatcher(
        {
            NotificationChannel.WHATSAPP: (
                InvalidResultTransport()
            ),
        }
    )

    with pytest.raises(
        InvalidNotificationTransportResult
    ):
        dispatcher.dispatch(
            make_request()
        )


def test_transport_requires_dispatch_method() -> None:
    dispatcher = NotificationDispatcher()

    with pytest.raises(
        TypeError,
        match="dispatch",
    ):
        dispatcher.register(
            NotificationChannel.EMAIL,
            MissingDispatchMethod(),
        )


def test_functional_helper_dispatches() -> None:
    result = dispatch_notification(
        make_request(
            channel=(
                NotificationChannel.TELEGRAM
            )
        ),
        transports={
            NotificationChannel.TELEGRAM: (
                SuccessfulTransport(
                    provider_message_id=(
                        "telegram:001"
                    )
                )
            ),
        },
    )

    assert result.successful is True
    assert (
        result.provider_message_id
        == "telegram:001"
    )


@pytest.mark.parametrize(
    "channel",
    list(NotificationChannel),
)
def test_all_channels_can_be_registered(
    channel: NotificationChannel,
) -> None:
    dispatcher = NotificationDispatcher()

    dispatcher.register(
        channel,
        SuccessfulTransport(),
    )

    result = dispatcher.dispatch(
        make_request(
            channel=channel
        )
    )

    assert result.successful is True
