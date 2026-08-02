from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NotificationPermission(str, Enum):
    READ = (
        "notification.read"
    )

    EXECUTE = (
        "notification.execute"
    )

    MANAGE = (
        "notification.manage"
    )

    SUPPRESS = (
        "notification.suppress"
    )

    ESCALATE = (
        "notification.escalate"
    )


ROLE_PERMISSIONS: dict[str, set[NotificationPermission]] = {
    "ADMINISTRATOR": {
        NotificationPermission.READ,
        NotificationPermission.EXECUTE,
        NotificationPermission.MANAGE,
        NotificationPermission.SUPPRESS,
        NotificationPermission.ESCALATE,
    },

    "NETWORK_ENGINEER": {
        NotificationPermission.READ,
        NotificationPermission.EXECUTE,
        NotificationPermission.SUPPRESS,
    },

    "SENIOR_ENGINEER": {
        NotificationPermission.READ,
        NotificationPermission.EXECUTE,
        NotificationPermission.ESCALATE,
    },

    "CHANGE_MANAGER": {
        NotificationPermission.READ,
        NotificationPermission.MANAGE,
    },

    "REQUESTER": {
        NotificationPermission.READ,
    },
}


@dataclass(frozen=True)
class NotificationPermissionGrant:
    identity_id: str
    permission: NotificationPermission

    def __post_init__(self) -> None:
        if not self.identity_id:
            raise ValueError(
                "identity_id must not be empty"
            )

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "permission": (
                self.permission.value
            ),
        }


def permissions_for_role(
    role: str,
) -> set[NotificationPermission]:

    return set(
        ROLE_PERMISSIONS.get(
            role.upper(),
            set(),
        )
    )


def has_permission(
    role: str,
    permission: NotificationPermission,
) -> bool:

    return permission in permissions_for_role(
        role
    )
