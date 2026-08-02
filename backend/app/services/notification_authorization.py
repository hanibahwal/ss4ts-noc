from __future__ import annotations

from dataclasses import dataclass

from app.models.notification_identity import (
    NotificationIdentity,
)

from app.models.notification_permission import (
    NotificationPermission,
    has_permission,
)


class NotificationAuthorizationError(
    Exception
):
    pass


class NotificationInactiveIdentity(
    NotificationAuthorizationError
):
    pass


class NotificationPermissionDenied(
    NotificationAuthorizationError
):
    pass


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    identity_id: str
    permission: NotificationPermission
    reason: str

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "identity_id": self.identity_id,
            "permission": (
                self.permission.value
            ),
            "reason": self.reason,
        }


class NotificationAuthorizationService:

    def authorize(
        self,
        identity: NotificationIdentity,
        permission: NotificationPermission,
    ) -> AuthorizationDecision:

        if not identity.active:
            raise NotificationInactiveIdentity(
                f"Identity inactive: "
                f"{identity.identity_id}"
            )

        allowed = has_permission(
            identity.role,
            permission,
        )

        if not allowed:
            raise NotificationPermissionDenied(
                f"Permission denied: "
                f"{permission.value}"
            )

        return AuthorizationDecision(
            allowed=True,
            identity_id=(
                identity.identity_id
            ),
            permission=permission,
            reason="Permission granted",
        )


    def authorize_read(
        self,
        identity: NotificationIdentity,
    ) -> AuthorizationDecision:

        return self.authorize(
            identity,
            NotificationPermission.READ,
        )


    def authorize_execute(
        self,
        identity: NotificationIdentity,
    ) -> AuthorizationDecision:

        return self.authorize(
            identity,
            NotificationPermission.EXECUTE,
        )


    def authorize_manage(
        self,
        identity: NotificationIdentity,
    ) -> AuthorizationDecision:

        return self.authorize(
            identity,
            NotificationPermission.MANAGE,
        )


    def authorize_suppression(
        self,
        identity: NotificationIdentity,
    ) -> AuthorizationDecision:

        return self.authorize(
            identity,
            NotificationPermission.SUPPRESS,
        )


    def authorize_escalation(
        self,
        identity: NotificationIdentity,
    ) -> AuthorizationDecision:

        return self.authorize(
            identity,
            NotificationPermission.ESCALATE,
        )
