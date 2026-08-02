from __future__ import annotations

from typing import Protocol

from app.models.notification import (
    NotificationChannel,
)
from app.models.notification_dispatch import (
    NotificationDispatchRequest,
)
from app.services.notification_transports.base import (
    NotificationChannelAdapter,
)
from app.services.notification_transports.common import (
    ProviderResponse,
)


class WhatsAppClient(Protocol):
    def send_text(
        self,
        *,
        destination: str,
        text: str,
    ) -> ProviderResponse:
        ...


class WhatsAppNotificationAdapter(
    NotificationChannelAdapter
):
    channel = NotificationChannel.WHATSAPP

    def __init__(
        self,
        client: WhatsAppClient,
    ) -> None:
        self._client = client

    def _send(
        self,
        request: NotificationDispatchRequest,
    ) -> ProviderResponse:
        return self._client.send_text(
            destination=request.destination,
            text=request.body,
        )
