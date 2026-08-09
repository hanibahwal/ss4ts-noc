from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ShadowDecisionRecord:
    shadow_id: str
    decision_id: str
    source_node_id: str
    proposed_action: str
    confidence_percent: float
    risk_level: str
    predicted_outcome: dict[str, Any]
    simulation_status: str
    dry_run_only: bool
    created_at: datetime
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "shadow_id": self.shadow_id,
            "decision_id": self.decision_id,
            "source_node_id": self.source_node_id,
            "proposed_action": self.proposed_action,
            "confidence_percent": self.confidence_percent,
            "risk_level": self.risk_level,
            "predicted_outcome": dict(
                self.predicted_outcome
            ),
            "simulation_status":
                self.simulation_status,
            "dry_run_only": self.dry_run_only,
            "created_at":
                self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }
