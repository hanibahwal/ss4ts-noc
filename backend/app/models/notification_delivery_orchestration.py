from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from enum import StrEnum
from typing import Any

from app.models.notification import (
    NotificationDelivery,
)
from app.models.notification_dispatch import (
    NotificationDispatchResult,
)


class DeliveryExecutionStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(
    frozen=True,
    slots=True,
)
class DeliveryExecutionResult:
    status: DeliveryExecutionStatus
    delivery: NotificationDelivery

    dispatch_result: (
        NotificationDispatchResult | None
    ) = None

    error_message: str | None = None
    retryable: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def successful(self) -> bool:
        return (
            self.status
            is DeliveryExecutionStatus.SENT
        )
