from __future__ import annotations

from abc import (
    ABC,
    abstractmethod,
)

from app.models.notification import (
    NotificationChannel,
)
from app.models.notification_dispatch import (
    NotificationDispatchRequest,
    NotificationDispatchResult,
)
from app.services.notification_transports.common import (
    NotificationProviderError,
    ProviderResponse,
)


class NotificationChannelAdapter(ABC):
    channel: NotificationChannel

    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        if request.channel is not self.channel:
            return NotificationDispatchResult.failure(
                "Notification channel mismatch: "
                f"expected {self.channel.value}, "
                f"received {request.channel.value}",
                retryable=False,
            )

        try:
            response = self._send(request)
        except NotificationProviderError as exc:
            return NotificationDispatchResult.failure(
                str(exc),
                retryable=exc.retryable,
                metadata={
                    "channel": self.channel.value,
                    "exception_type": (
                        type(exc).__name__
                    ),
                },
            )
        except Exception as exc:
            return NotificationDispatchResult.failure(
                str(exc)
                or type(exc).__name__,
                retryable=False,
                metadata={
                    "channel": self.channel.value,
                    "exception_type": (
                        type(exc).__name__
                    ),
                },
            )

        if not isinstance(
            response,
            ProviderResponse,
        ):
            return NotificationDispatchResult.failure(
                "Notification provider returned "
                "an invalid response",
                retryable=False,
                metadata={
                    "channel": self.channel.value,
                },
            )

        metadata = {
            "channel": self.channel.value,
            **response.metadata,
        }

        if response.successful:
            return NotificationDispatchResult.success(
                provider_message_id=(
                    response.message_id
                ),
                metadata=metadata,
            )

        return NotificationDispatchResult.failure(
            response.error_message
            or "Notification provider failed",
            retryable=response.retryable,
            metadata=metadata,
        )

    @abstractmethod
    def _send(
        self,
        request: NotificationDispatchRequest,
    ) -> ProviderResponse:
        ...
