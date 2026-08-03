from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models.notification_identity import (
    NotificationIdentity,
)

from app.models.notification_permission import (
    NotificationPermission,
    has_permission,
)

from app.models.notification_audit import (
    NotificationAuditAction,
    NotificationAuditResult,
)

from app.services.notification_audit import (
    NotificationAuditStore,
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

            "allowed":
                self.allowed,

            "identity_id":
                self.identity_id,

            "permission":
                self.permission.value,

            "reason":
                self.reason,
        }



class NotificationAuthorizationService:


    def __init__(
        self,
        audit_store: NotificationAuditStore | None = None,
    ):

        self.audit_store = (
            audit_store
            or NotificationAuditStore(
                Path(
                    "notifications.sqlite3"
                )
            )
        )


    def _audit(
        self,
        *,
        identity_id: str,
        action: NotificationAuditAction,
        result: NotificationAuditResult,
        message: str,
    ):

        self.audit_store.create_audit(
            identity_id=identity_id,
            action=action,
            result=result,
            resource="notification",
            message=message,
        )



    def authorize(
        self,
        identity: NotificationIdentity,
        permission: NotificationPermission,
    ) -> AuthorizationDecision:


        if not identity.active:

            self._audit(
                identity_id=identity.identity_id,
                action=(
                    NotificationAuditAction
                    .AUTHORIZATION_FAILED
                ),
                result=(
                    NotificationAuditResult
                    .FAILED
                ),
                message=(
                    "Inactive identity"
                ),
            )

            raise NotificationInactiveIdentity(
                f"Identity inactive: "
                f"{identity.identity_id}"
            )


        allowed = has_permission(
            identity.role,
            permission,
        )


        if not allowed:

            self._audit(
                identity_id=identity.identity_id,
                action=(
                    NotificationAuditAction
                    .AUTHORIZATION_FAILED
                ),
                result=(
                    NotificationAuditResult
                    .DENIED
                ),
                message=(
                    f"Permission denied: "
                    f"{permission.value}"
                ),
            )


            raise NotificationPermissionDenied(
                f"Permission denied: "
                f"{permission.value}"
            )


        self._audit(
            identity_id=identity.identity_id,
            action=(
                NotificationAuditAction
                .EXECUTE
                if permission
                == NotificationPermission.EXECUTE
                else NotificationAuditAction.READ
            ),
            result=(
                NotificationAuditResult.SUCCESS
            ),
            message=(
                f"Permission granted: "
                f"{permission.value}"
            ),
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
