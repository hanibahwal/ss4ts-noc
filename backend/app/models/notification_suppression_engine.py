from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    time,
)
from enum import StrEnum

from app.models.notification import (
    NotificationSuppression,
    NotificationType,
)


class NotificationSuppressionDecisionCode(
    StrEnum
):
    ALLOWED = "allowed"
    SUPPRESSED = "suppressed"
    BYPASSED = "bypassed"


@dataclass(
    frozen=True,
    slots=True,
)
class QuietHoursWindow:
    start_time: time
    end_time: time

    timezone_name: str = "UTC"

    weekdays: tuple[int, ...] = (
        0,
        1,
        2,
        3,
        4,
        5,
        6,
    )

    def __post_init__(self) -> None:
        if any(
            day < 0 or day > 6
            for day in self.weekdays
        ):
            raise ValueError(
                "Quiet-hours weekdays must be "
                "between 0 and 6"
            )

        if len(set(self.weekdays)) != len(
            self.weekdays
        ):
            raise ValueError(
                "Quiet-hours weekdays must be "
                "unique"
            )

    @property
    def overnight(self) -> bool:
        return self.start_time > self.end_time

    @property
    def full_day(self) -> bool:
        return self.start_time == self.end_time


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationSuppressionContext:
    event_type: str
    evaluated_at: datetime

    site_id: str | None = None
    device_id: str | None = None

    severity: str | None = None

    notification_type: (
        NotificationType | str | None
    ) = None

    force: bool = False

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError(
                "Suppression event type must "
                "not be empty"
            )

        if self.evaluated_at.tzinfo is None:
            raise ValueError(
                "Suppression evaluation time "
                "must be timezone-aware"
            )

    @property
    def notification_type_value(
        self,
    ) -> str | None:
        if self.notification_type is None:
            return None

        if isinstance(
            self.notification_type,
            NotificationType,
        ):
            return self.notification_type.value

        return str(
            self.notification_type
        ).strip().lower()


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationSuppressionDecision:
    code: NotificationSuppressionDecisionCode

    context: NotificationSuppressionContext

    suppressed: bool

    suppression: (
        NotificationSuppression | None
    ) = None

    quiet_hours_window: (
        QuietHoursWindow | None
    ) = None

    reason: str = ""

    @property
    def allowed(self) -> bool:
        return not self.suppressed
