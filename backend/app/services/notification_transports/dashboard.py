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


class DashboardPublisher(Protocol):
    def publish(
        self,
        *,
        topic: str,
        event: dict[str, Any],
    ) -> ProviderResponse:
        ...


class DashboardNotificationAdapter(
    NotificationChannelAdapter
):
    channel = NotificationChannel.DASHBOARD

    def __init__(
        self,
        publisher: DashboardPublisher,
    ) -> None:
        self._publisher = publisher

    def _send(
        self,
        request: NotificationDispatchRequest,
    ) -> ProviderResponse:
        delivery = request.delivery

        event: dict[str, Any] = {
            "delivery_id": delivery.delivery_id,
            "incident_id": delivery.incident_id,
            "notification_type": (
                delivery.notification_type.value
            ),
            "subject": request.subject,
            "body": request.body,
            "metadata": {
                **delivery.metadata,
                **request.metadata,
            },
        }

        return self._publisher.publish(
            topic=request.destination,
            event=event,
        )
