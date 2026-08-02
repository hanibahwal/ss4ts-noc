from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from enum import StrEnum
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)

from app.models.notification import (
    NotificationChannel,
    NotificationDelivery,
)


class NotificationDispatchStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationDispatchRequest:
    delivery: NotificationDelivery
    body: str

    subject: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.delivery,
            NotificationDelivery,
        ):
            raise TypeError(
                "Dispatch delivery must be a "
                "NotificationDelivery"
            )

        if not self.body.strip():
            raise ValueError(
                "Dispatch body must not be empty"
            )

    @property
    def channel(self) -> NotificationChannel:
        return self.delivery.channel

    @property
    def destination(self) -> str:
        return self.delivery.destination


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationDispatchResult:
    status: NotificationDispatchStatus

    provider_message_id: str | None = None
    error_message: str | None = None

    retryable: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if (
            self.status
            is NotificationDispatchStatus.SUCCESS
        ):
            if self.error_message is not None:
                raise ValueError(
                    "Successful dispatch cannot "
                    "contain an error message"
                )

            if self.retryable:
                raise ValueError(
                    "Successful dispatch cannot "
                    "be retryable"
                )

        if (
            self.status
            is NotificationDispatchStatus.FAILED
            and not (
                self.error_message
                and self.error_message.strip()
            )
        ):
            raise ValueError(
                "Failed dispatch requires an "
                "error message"
            )

    @property
    def successful(self) -> bool:
        return (
            self.status
            is NotificationDispatchStatus.SUCCESS
        )

    @classmethod
    def success(
        cls,
        *,
        provider_message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationDispatchResult:
        return cls(
            status=(
                NotificationDispatchStatus.SUCCESS
            ),
            provider_message_id=(
                provider_message_id
            ),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def failure(
        cls,
        error_message: str,
        *,
        retryable: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationDispatchResult:
        return cls(
            status=(
                NotificationDispatchStatus.FAILED
            ),
            error_message=error_message,
            retryable=retryable,
            metadata=dict(metadata or {}),
        )


@runtime_checkable
class NotificationTransport(Protocol):
    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        ...
