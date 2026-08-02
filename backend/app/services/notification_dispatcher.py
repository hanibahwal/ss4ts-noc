from __future__ import annotations

from collections.abc import Iterable

from app.models.notification import (
    NotificationChannel,
)
from app.models.notification_dispatch import (
    NotificationDispatchRequest,
    NotificationDispatchResult,
    NotificationTransport,
)


class NotificationDispatcherError(RuntimeError):
    pass


class NotificationTransportNotRegistered(
    NotificationDispatcherError
):
    def __init__(
        self,
        channel: NotificationChannel,
    ) -> None:
        self.channel = channel

        super().__init__(
            "No notification transport registered "
            f"for channel: {channel.value}"
        )


class NotificationTransportAlreadyRegistered(
    NotificationDispatcherError
):
    def __init__(
        self,
        channel: NotificationChannel,
    ) -> None:
        self.channel = channel

        super().__init__(
            "Notification transport already "
            f"registered for channel: {channel.value}"
        )


class InvalidNotificationTransportResult(
    NotificationDispatcherError
):
    pass


class NotificationTransportExecutionError(
    NotificationDispatcherError
):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        self.retryable = retryable

        super().__init__(message)


class NotificationDispatcher:
    def __init__(
        self,
        transports: (
            dict[
                NotificationChannel,
                NotificationTransport,
            ]
            | None
        ) = None,
    ) -> None:
        self._transports: dict[
            NotificationChannel,
            NotificationTransport,
        ] = {}

        for channel, transport in (
            transports or {}
        ).items():
            self.register(
                channel,
                transport,
            )

    @staticmethod
    def _normalize_channel(
        channel: NotificationChannel | str,
    ) -> NotificationChannel:
        if isinstance(
            channel,
            NotificationChannel,
        ):
            return channel

        try:
            return NotificationChannel(
                str(channel).strip().lower()
            )
        except ValueError as exc:
            raise ValueError(
                f"Unsupported notification "
                f"channel: {channel}"
            ) from exc

    @staticmethod
    def _validate_transport(
        transport: NotificationTransport,
    ) -> None:
        dispatch_method = getattr(
            transport,
            "dispatch",
            None,
        )

        if not callable(dispatch_method):
            raise TypeError(
                "Notification transport must "
                "provide a callable dispatch()"
            )

    def register(
        self,
        channel: NotificationChannel | str,
        transport: NotificationTransport,
        *,
        replace: bool = False,
    ) -> None:
        normalized_channel = (
            self._normalize_channel(channel)
        )

        self._validate_transport(transport)

        if (
            normalized_channel
            in self._transports
            and not replace
        ):
            raise (
                NotificationTransportAlreadyRegistered(
                    normalized_channel
                )
            )

        self._transports[
            normalized_channel
        ] = transport

    def unregister(
        self,
        channel: NotificationChannel | str,
    ) -> bool:
        normalized_channel = (
            self._normalize_channel(channel)
        )

        return (
            self._transports.pop(
                normalized_channel,
                None,
            )
            is not None
        )

    def has_transport(
        self,
        channel: NotificationChannel | str,
    ) -> bool:
        normalized_channel = (
            self._normalize_channel(channel)
        )

        return (
            normalized_channel
            in self._transports
        )

    def registered_channels(
        self,
    ) -> tuple[NotificationChannel, ...]:
        return tuple(
            sorted(
                self._transports,
                key=lambda item: item.value,
            )
        )

    def register_many(
        self,
        transports: Iterable[
            tuple[
                NotificationChannel | str,
                NotificationTransport,
            ]
        ],
        *,
        replace: bool = False,
    ) -> None:
        for channel, transport in transports:
            self.register(
                channel,
                transport,
                replace=replace,
            )

    def dispatch(
        self,
        request: NotificationDispatchRequest,
    ) -> NotificationDispatchResult:
        if not isinstance(
            request,
            NotificationDispatchRequest,
        ):
            raise TypeError(
                "Dispatcher request must be a "
                "NotificationDispatchRequest"
            )

        transport = self._transports.get(
            request.channel
        )

        if transport is None:
            raise NotificationTransportNotRegistered(
                request.channel
            )

        try:
            result = transport.dispatch(
                request
            )
        except NotificationTransportExecutionError as exc:
            return NotificationDispatchResult.failure(
                str(exc),
                retryable=exc.retryable,
                metadata={
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
                    "exception_type": (
                        type(exc).__name__
                    ),
                },
            )

        if not isinstance(
            result,
            NotificationDispatchResult,
        ):
            raise InvalidNotificationTransportResult(
                "Notification transport dispatch() "
                "must return "
                "NotificationDispatchResult"
            )

        return result


def dispatch_notification(
    request: NotificationDispatchRequest,
    *,
    transports: dict[
        NotificationChannel,
        NotificationTransport,
    ],
) -> NotificationDispatchResult:
    return NotificationDispatcher(
        transports
    ).dispatch(request)
