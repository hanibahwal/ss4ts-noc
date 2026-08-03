from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum



class ApprovalStatus(
    str,
    Enum,
):

    PENDING = "pending"

    APPROVED = "approved"

    REJECTED = "rejected"

    EXPIRED = "expired"





@dataclass(
    frozen=True,
    slots=True,
)
class NotificationResponseApproval:


    approval_id: str


    execution_id: str


    action_id: str


    action_type: str


    requested_reason: str


    status: ApprovalStatus


    approved_by: str | None


    requested_at: datetime


    approved_at: datetime | None



    def to_dict(
        self,
    ) -> dict:

        return {

            "approval_id":
                self.approval_id,


            "execution_id":
                self.execution_id,


            "action_id":
                self.action_id,


            "action_type":
                self.action_type,


            "requested_reason":
                self.requested_reason,


            "status":
                self.status.value,


            "approved_by":
                self.approved_by,


            "requested_at":
                self.requested_at.isoformat(),


            "approved_at":
                (
                    self.approved_at.isoformat()
                    if self.approved_at
                    else None
                ),

        }
