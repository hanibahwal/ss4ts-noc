from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationAuditStats:

    total_events: int

    success_count: int

    failed_count: int

    denied_count: int

    action_distribution: dict[str, int]

    top_identities: list[dict[str, int | str]]

    generated_at: datetime


    def to_dict(self) -> dict:

        return {
            "total_events":
                self.total_events,

            "success_count":
                self.success_count,

            "failed_count":
                self.failed_count,

            "denied_count":
                self.denied_count,

            "action_distribution":
                self.action_distribution,

            "top_identities":
                self.top_identities,

            "generated_at":
                self.generated_at.isoformat(),
        }
