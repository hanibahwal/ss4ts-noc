from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NotificationAuditAction(StrEnum):

    READ = "read"

    EXECUTE = "execute"

    CREATE = "create"

    UPDATE = "update"

    DELETE = "delete"

    ESCALATE = "escalate"

    SUPPRESS = "suppress"

    AUTHORIZATION_FAILED = (
        "authorization_failed"
    )


class NotificationAuditResult(StrEnum):

    SUCCESS = "success"

    FAILED = "failed"

    DENIED = "denied"


@dataclass(
    frozen=True,
    slots=True,
)
class NotificationAuditRecord:

    audit_id: str

    identity_id: str

    action: NotificationAuditAction

    result: NotificationAuditResult

    resource: str

    resource_id: str | None = None

    message: str = ""

    created_at: datetime = (
        None
    )


    def __post_init__(self):

        if not self.audit_id:
            raise ValueError(
                "audit_id required"
            )

        if not self.identity_id:
            raise ValueError(
                "identity_id required"
            )

        if self.created_at is None:
            object.__setattr__(
                self,
                "created_at",
                utc_now(),
            )


    def to_dict(self) -> dict:

        return {

            "audit_id":
                self.audit_id,

            "identity_id":
                self.identity_id,

            "action":
                self.action.value,

            "result":
                self.result.value,

            "resource":
                self.resource,

            "resource_id":
                self.resource_id,

            "message":
                self.message,

            "created_at":
                self.created_at.isoformat(),
        }
