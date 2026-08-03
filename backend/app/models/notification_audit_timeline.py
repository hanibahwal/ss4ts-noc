from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationAuditTimelinePoint:

    timestamp: datetime

    total: int

    success: int

    failed: int

    denied: int


    def to_dict(self) -> dict:

        return {
            "timestamp":
                self.timestamp.isoformat(),

            "total":
                self.total,

            "success":
                self.success,

            "failed":
                self.failed,

            "denied":
                self.denied,
        }



@dataclass(
    frozen=True,
    slots=True,
)
class NotificationAuditTimeline:

    period: str

    points: list[
        NotificationAuditTimelinePoint
    ]

    generated_at: datetime


    def to_dict(self) -> dict:

        return {
            "period":
                self.period,

            "timeline": [
                point.to_dict()
                for point in self.points
            ],

            "generated_at":
                self.generated_at.isoformat(),
        }
