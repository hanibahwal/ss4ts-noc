from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum



class NotificationDecisionType(str, Enum):

    MONITOR = "monitor"

    INVESTIGATE = "investigate"

    ESCALATE = "escalate"

    BLOCK = "block"




@dataclass(
    frozen=True,
    slots=True,
)
class NotificationAuditDecision:


    decision: NotificationDecisionType


    confidence: int


    reason: str


    risk_level: str


    risk_score: int


    actions: list[str]


    generated_at: datetime



    def to_dict(
        self,
    ) -> dict:


        return {

            "decision":
                self.decision.value,


            "confidence":
                self.confidence,


            "reason":
                self.reason,


            "risk_level":
                self.risk_level,


            "risk_score":
                self.risk_score,


            "actions":
                self.actions,


            "generated_at":
                self.generated_at.isoformat(),

        }
