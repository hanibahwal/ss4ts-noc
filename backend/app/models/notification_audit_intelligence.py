from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum



class AuditRiskLevel(str, Enum):

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"

    CRITICAL = "critical"




@dataclass(
    frozen=True,
    slots=True,
)
class NotificationAuditRisk:


    risk_score: int


    risk_level: AuditRiskLevel


    total_events: int


    failed_events: int


    denied_events: int


    success_events: int


    top_identity: str | None


    recommendations: list[str]


    generated_at: datetime



    def to_dict(
        self,
    ) -> dict:


        return {

            "risk_score":
                self.risk_score,


            "risk_level":
                self.risk_level.value,


            "total_events":
                self.total_events,


            "failed_events":
                self.failed_events,


            "denied_events":
                self.denied_events,


            "success_events":
                self.success_events,


            "top_identity":
                self.top_identity,


            "recommendations":
                self.recommendations,


            "generated_at":
                self.generated_at.isoformat(),

        }
