from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime



@dataclass(
    frozen=True,
    slots=True,
)
class NotificationResponseExecutionHistory:


    execution_id: str


    action_id: str


    action_type: str


    guard_status: str


    approved: bool


    executed: bool


    result: str


    created_at: datetime



    def to_dict(
        self,
    ) -> dict:

        return {

            "execution_id":
                self.execution_id,


            "action_id":
                self.action_id,


            "action_type":
                self.action_type,


            "guard_status":
                self.guard_status,


            "approved":
                self.approved,


            "executed":
                self.executed,


            "result":
                self.result,


            "created_at":
                self.created_at.isoformat(),

        }
