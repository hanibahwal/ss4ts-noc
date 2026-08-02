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


class TelegramClient(Protocol):
    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
    ) -> ProviderResponse:
        ...


class TelegramNotificationAdapter(
    NotificationChannelAdapter
):
    channel = NotificationChannel.TELEGRAM

    def __init__(
        self,
        client: TelegramClient,
    ) -> None:
        self._client = client

    def _send(
        self,
        request: NotificationDispatchRequest,
    ) -> ProviderResponse:
        return self._client.send_message(
            chat_id=request.destination,
            text=request.body,
        )
