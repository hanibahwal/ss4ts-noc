from __future__ import annotations

from typing import Any

from app.models.notification import (
    NotificationDeliveryStatus,
)
from app.models.notification_delivery_orchestration import (
    DeliveryExecutionResult,
    DeliveryExecutionStatus,
)
from app.models.notification_dispatch import (
    NotificationDispatchRequest,
    NotificationDispatchResult,
)
from app.services.notification_dispatcher import (
    NotificationDispatcher,
)
from app.services.notification_store import (
    NotificationStore,
)


class NotificationDeliveryOrchestrator:
    def __init__(
        self,
        store: NotificationStore,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher

    def execute(
        self,
        delivery_id: str,
        *,
        body: str,
        subject: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> DeliveryExecutionResult:
        delivery = self._store.begin_delivery_attempt(
            delivery_id
        )

        request = NotificationDispatchRequest(
            delivery=delivery,
            body=body,
            subject=subject,
            metadata=dict(metadata or {}),
        )

        try:
            dispatch_result = (
                self._dispatcher.dispatch(request)
            )
        except Exception as exc:
            error_message = (
                str(exc)
                or type(exc).__name__
            )

            failed = (
                self._store
                .complete_delivery_attempt(
                    delivery_id,
                    status=(
                        NotificationDeliveryStatus
                        .FAILED
                    ),
                    error_message=error_message,
                )
            )

            return DeliveryExecutionResult(
                status=(
                    DeliveryExecutionStatus.FAILED
                ),
                delivery=failed,
                error_message=error_message,
                retryable=False,
                metadata={
                    "exception_type": (
                        type(exc).__name__
                    ),
                },
            )

        return self._complete_from_dispatch_result(
            delivery_id,
            dispatch_result,
        )

    def _complete_from_dispatch_result(
        self,
        delivery_id: str,
        dispatch_result: NotificationDispatchResult,
    ) -> DeliveryExecutionResult:
        if dispatch_result.successful:
            sent = (
                self._store
                .complete_delivery_attempt(
                    delivery_id,
                    status=(
                        NotificationDeliveryStatus
                        .SENT
                    ),
                    provider_message_id=(
                        dispatch_result
                        .provider_message_id
                    ),
                )
            )

            return DeliveryExecutionResult(
                status=(
                    DeliveryExecutionStatus.SENT
                ),
                delivery=sent,
                dispatch_result=dispatch_result,
                retryable=False,
                metadata=dict(
                    dispatch_result.metadata
                ),
            )

        failed = (
            self._store
            .complete_delivery_attempt(
                delivery_id,
                status=(
                    NotificationDeliveryStatus
                    .FAILED
                ),
                error_message=(
                    dispatch_result.error_message
                    or "Notification delivery failed"
                ),
            )
        )

        return DeliveryExecutionResult(
            status=(
                DeliveryExecutionStatus.FAILED
            ),
            delivery=failed,
            dispatch_result=dispatch_result,
            error_message=(
                dispatch_result.error_message
            ),
            retryable=(
                dispatch_result.retryable
            ),
            metadata=dict(
                dispatch_result.metadata
            ),
        )


def execute_notification_delivery(
    store: NotificationStore,
    dispatcher: NotificationDispatcher,
    delivery_id: str,
    *,
    body: str,
    subject: str = "",
    metadata: dict[str, Any] | None = None,
) -> DeliveryExecutionResult:
    return NotificationDeliveryOrchestrator(
        store,
        dispatcher,
    ).execute(
        delivery_id,
        body=body,
        subject=subject,
        metadata=metadata,
    )
