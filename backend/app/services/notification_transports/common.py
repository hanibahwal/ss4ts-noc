from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from typing import Any


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderResponse:
    successful: bool

    message_id: str | None = None
    error_message: str | None = None

    retryable: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if self.successful:
            if self.error_message is not None:
                raise ValueError(
                    "Successful provider response "
                    "cannot contain an error"
                )

            if self.retryable:
                raise ValueError(
                    "Successful provider response "
                    "cannot be retryable"
                )

        if (
            not self.successful
            and not (
                self.error_message
                and self.error_message.strip()
            )
        ):
            raise ValueError(
                "Failed provider response requires "
                "an error message"
            )

    @classmethod
    def success(
        cls,
        *,
        message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        return cls(
            successful=True,
            message_id=message_id,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def failure(
        cls,
        error_message: str,
        *,
        retryable: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        return cls(
            successful=False,
            error_message=error_message,
            retryable=retryable,
            metadata=dict(metadata or {}),
        )


class NotificationProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        self.retryable = retryable
        super().__init__(message)


class TemporaryNotificationProviderError(
    NotificationProviderError
):
    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            retryable=True,
        )


class PermanentNotificationProviderError(
    NotificationProviderError
):
    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            retryable=False,
        )
