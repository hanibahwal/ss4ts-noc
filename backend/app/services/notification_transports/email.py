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


class EmailClient(Protocol):
    def send_email(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
    ) -> ProviderResponse:
        ...


class EmailNotificationAdapter(
    NotificationChannelAdapter
):
    channel = NotificationChannel.EMAIL

    def __init__(
        self,
        client: EmailClient,
        *,
        default_subject: str = "SS4TS Notification",
    ) -> None:
        self._client = client
        self._default_subject = default_subject

    def _send(
        self,
        request: NotificationDispatchRequest,
    ) -> ProviderResponse:
        subject = (
            request.subject.strip()
            or self._default_subject
        )

        return self._client.send_email(
            recipient=request.destination,
            subject=subject,
            body=request.body,
        )
