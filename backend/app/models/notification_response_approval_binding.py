from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum



class ApprovalExecutionStatus(
    str,
    Enum,
):

    WAITING = "waiting"

    APPROVED = "approved"

    EXECUTING = "executing"

    COMPLETED = "completed"

    FAILED = "failed"

    REJECTED = "rejected"





@dataclass(
    frozen=True,
    slots=True,
)
class NotificationResponseApprovalBinding:


    binding_id: str


    approval_id: str


    action_id: str


    execution_id: str | None


    status: ApprovalExecutionStatus


    approved_by: str | None


    approved_at: datetime | None


    created_at: datetime



    def to_dict(
        self,
    ) -> dict:


        return {

            "binding_id":
                self.binding_id,


            "approval_id":
                self.approval_id,


            "action_id":
                self.action_id,


            "execution_id":
                self.execution_id,


            "status":
                self.status.value,


            "approved_by":
                self.approved_by,


            "approved_at":
                self.approved_at.isoformat()
                if self.approved_at
                else None,


            "created_at":
                self.created_at.isoformat(),

        }
