from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.notification_audit import (
    NotificationAuditAction,
    NotificationAuditResult,
)


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationAuditQuery:

    identity_id: str | None = None

    action: NotificationAuditAction | None = None

    result: NotificationAuditResult | None = None

    resource: str | None = None

    resource_id: str | None = None

    from_date: datetime | None = None

    to_date: datetime | None = None

    limit: int = 50

    offset: int = 0


    def __post_init__(self) -> None:

        if self.limit < 1:
            raise ValueError(
                "limit must be positive"
            )

        if self.offset < 0:
            raise ValueError(
                "offset must not be negative"
            )


    def to_dict(self) -> dict:

        return {
            "identity_id": self.identity_id,

            "action": (
                self.action.value
                if self.action
                else None
            ),

            "result": (
                self.result.value
                if self.result
                else None
            ),

            "resource": self.resource,

            "resource_id": self.resource_id,

            "from_date": (
                self.from_date.isoformat()
                if self.from_date
                else None
            ),

            "to_date": (
                self.to_date.isoformat()
                if self.to_date
                else None
            ),

            "limit": self.limit,

            "offset": self.offset,
        }
