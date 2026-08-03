from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import datetime



class NotificationResponseActionType(
    str,
    Enum,
):

    BLOCK_IDENTITY = "block_identity"

    DISABLE_TOKEN = "disable_token"

    CREATE_INCIDENT = "create_incident"

    SEND_ALERT = "send_alert"

    QUARANTINE_DEVICE = "quarantine_device"

    RESTART_SERVICE = "restart_service"

    CONTINUE_MONITORING = "continue_monitoring"




@dataclass(
    frozen=True,
    slots=True,
)
class NotificationResponseAction:


    action_id: str


    action_type: NotificationResponseActionType


    risk_level: str


    requires_approval: bool


    reversible: bool


    description: str


    created_at: datetime




    def to_dict(
        self,
    ) -> dict:


        return {

            "action_id":
                self.action_id,


            "action_type":
                self.action_type.value,


            "risk_level":
                self.risk_level,


            "requires_approval":
                self.requires_approval,


            "reversible":
                self.reversible,


            "description":
                self.description,


            "created_at":
                self.created_at.isoformat(),

        }
