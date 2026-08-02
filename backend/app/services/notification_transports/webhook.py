from __future__ import annotations

from typing import (
    Any,
    Protocol,
)

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


class WebhookClient(Protocol):
    def post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
    ) -> ProviderResponse:
        ...


class WebhookNotificationAdapter(
    NotificationChannelAdapter
):
    channel = NotificationChannel.WEBHOOK

    def __init__(
        self,
        client: WebhookClient,
    ) -> None:
        self._client = client

    def _send(
        self,
        request: NotificationDispatchRequest,
    ) -> ProviderResponse:
        delivery = request.delivery

        payload: dict[str, Any] = {
            "delivery_id": delivery.delivery_id,
            "incident_id": delivery.incident_id,
            "notification_type": (
                delivery.notification_type.value
            ),
            "channel": delivery.channel.value,
            "destination": delivery.destination,
            "subject": request.subject,
            "body": request.body,
            "metadata": {
                **delivery.metadata,
                **request.metadata,
            },
        }

        return self._client.post_json(
            url=request.destination,
            payload=payload,
        )
