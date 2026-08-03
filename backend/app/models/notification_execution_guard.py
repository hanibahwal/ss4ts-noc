from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum



class ExecutionGuardStatus(
    str,
    Enum,
):

    ALLOWED = "allowed"

    APPROVAL_REQUIRED = "approval_required"

    BLOCKED = "blocked"




@dataclass(
    frozen=True,
    slots=True,
)
class NotificationExecutionGuardResult:


    action_id: str


    status: ExecutionGuardStatus


    allowed: bool


    requires_approval: bool


    reason: str


    checked_at: datetime



    def to_dict(
        self,
    ) -> dict:

        return {

            "action_id":
                self.action_id,


            "status":
                self.status.value,


            "allowed":
                self.allowed,


            "requires_approval":
                self.requires_approval,


            "reason":
                self.reason,


            "checked_at":
                self.checked_at.isoformat(),

        }
