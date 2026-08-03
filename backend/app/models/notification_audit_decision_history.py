from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime



@dataclass(
    frozen=True,
    slots=True,
)
class NotificationDecisionHistory:


    decision_id: str


    decision: str


    confidence: int


    risk_level: str


    risk_score: int


    reason: str


    actions: list[str]


    generated_at: datetime



    def to_dict(
        self,
    ) -> dict:


        return {

            "decision_id":
                self.decision_id,


            "decision":
                self.decision,


            "confidence":
                self.confidence,


            "risk_level":
                self.risk_level,


            "risk_score":
                self.risk_score,


            "reason":
                self.reason,


            "actions":
                self.actions,


            "generated_at":
                self.generated_at.isoformat(),

        }
