from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.models.notification import (
    NotificationDelivery,
)


class NotificationRetryDecisionCode(StrEnum):
    SCHEDULED = "scheduled"
    DISABLED = "disabled"
    NOT_RETRYABLE = "not_retryable"
    DELIVERY_NOT_FAILED = "delivery_not_failed"
    MAX_ATTEMPTS_REACHED = (
        "max_attempts_reached"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationRetryPolicy:
    max_attempts: int = 5

    initial_delay_seconds: float = 30.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 900.0

    enabled: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(
                "Retry max attempts must be "
                "positive"
            )

        if self.initial_delay_seconds < 0:
            raise ValueError(
                "Initial retry delay must be "
                "non-negative"
            )

        if self.backoff_multiplier < 1:
            raise ValueError(
                "Retry backoff multiplier must "
                "be at least 1"
            )

        if self.max_delay_seconds < 0:
            raise ValueError(
                "Maximum retry delay must be "
                "non-negative"
            )

        if (
            self.max_delay_seconds
            < self.initial_delay_seconds
        ):
            raise ValueError(
                "Maximum retry delay cannot be "
                "less than initial retry delay"
            )


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationRetryDecision:
    code: NotificationRetryDecisionCode

    delivery: NotificationDelivery

    should_retry: bool
    retryable: bool

    attempt_count: int
    max_attempts: int

    delay_seconds: float | None = None
    next_retry_at: datetime | None = None

    reason: str = ""

    def __post_init__(self) -> None:
        if self.should_retry:
            if self.delay_seconds is None:
                raise ValueError(
                    "Retry decision requires a "
                    "delay"
                )

            if self.next_retry_at is None:
                raise ValueError(
                    "Retry decision requires the "
                    "next retry time"
                )

        if not self.should_retry:
            if self.next_retry_at is not None:
                raise ValueError(
                    "Rejected retry decision "
                    "cannot have a retry time"
                )

    @property
    def attempts_remaining(self) -> int:
        return max(
            self.max_attempts
            - self.attempt_count,
            0,
        )
