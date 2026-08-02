from fastapi import Depends, HTTPException, status

from app.models.notification_identity import (
    NotificationIdentity,
)

from app.models.notification_permission import (
    NotificationPermission,
)

from app.services.notification_authorization import (
    NotificationAuthorizationService,
    NotificationPermissionDenied,
)


def get_current_notification_identity():
    return NotificationIdentity(
        identity_id="api-user",
        username="api-user",
        role="ADMINISTRATOR",
    )


def require_notification_permission(
    permission: NotificationPermission,
):

    def dependency(
        identity: NotificationIdentity = Depends(
            get_current_notification_identity
        ),
    ):

        try:
            return (
                NotificationAuthorizationService()
                .authorize(
                    identity,
                    permission,
                )
            )

        except NotificationPermissionDenied as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

    return dependency
