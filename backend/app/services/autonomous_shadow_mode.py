from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.shadow_decision import (
    ShadowDecisionRecord,
)
from app.services.shadow_decision_store import (
    ShadowDecisionStore,
)


SERVICE_NAME = "SS4TS Autonomous Shadow Mode"
SERVICE_VERSION = "1.0.0-H32.2"


class AutonomousShadowMode:
    """
    Record what autonomous intelligence would do
    without granting execution authority.

    Shadow mode never performs network I/O and
    never executes commands on managed devices.
    """

    def __init__(
        self,
        store: ShadowDecisionStore,
    ) -> None:
        self.store = store

    def record_decision(
        self,
        *,
        decision: dict[str, Any],
        simulation: dict[str, Any],
        source_node_id: str,
        predicted_outcome: (
            dict[str, Any] | None
        ) = None,
    ) -> ShadowDecisionRecord:
        if not isinstance(decision, dict):
            raise TypeError(
                "decision must be a dictionary"
            )

        if not isinstance(simulation, dict):
            raise TypeError(
                "simulation must be a dictionary"
            )

        decision_id = str(
            decision.get(
                "decision_id",
                "",
            )
        ).strip()

        if not decision_id:
            raise ValueError(
                "decision_id is required"
            )

        source = str(
            source_node_id
        ).strip()

        if not source:
            raise ValueError(
                "source_node_id is required"
            )

        proposed_action = str(
            decision.get(
                "action",
                decision.get(
                    "action_type",
                    "UNKNOWN",
                ),
            )
        ).strip()

        confidence = float(
            simulation.get(
                "confidence",
                decision.get(
                    "confidence",
                    0.0,
                ),
            )
        )

        if not 0 <= confidence <= 100:
            raise ValueError(
                "confidence must be between "
                "0 and 100"
            )

        risk_level = str(
            decision.get(
                "risk_level",
                decision.get(
                    "priority",
                    "UNKNOWN",
                ),
            )
        ).upper()

        simulation_status = str(
            simulation.get(
                "simulation_status",
                simulation.get(
                    "status",
                    "UNKNOWN",
                ),
            )
        ).upper()

        predicted = (
            dict(predicted_outcome)
            if isinstance(
                predicted_outcome,
                dict,
            )
            else {
                "safe_to_execute": bool(
                    simulation.get(
                        "safe_to_execute",
                        False,
                    )
                ),
                "simulation_status":
                    simulation_status,
                "reason":
                    simulation.get("reason"),
                "proposed_action":
                    proposed_action,
            }
        )

        now = datetime.now(timezone.utc)

        record = ShadowDecisionRecord(
            shadow_id=(
                "shadow:"
                f"{now.strftime('%Y%m%dT%H%M%S%fZ')}:"
                f"{uuid4().hex[:12]}"
            ),
            decision_id=decision_id,
            source_node_id=source,
            proposed_action=proposed_action,
            confidence_percent=round(
                confidence,
                2,
            ),
            risk_level=risk_level,
            predicted_outcome=predicted,
            simulation_status=
                simulation_status,
            dry_run_only=True,
            created_at=now,
            metadata={
                "service": {
                    "name": SERVICE_NAME,
                    "version": SERVICE_VERSION,
                },
                "shadow_mode": True,
                "execution_enabled": False,
                "execution_authority": False,
                "dry_run_only": True,
                "network_io_performed": False,
                "device_command_executed": False,
            },
        )

        return self.store.create(record)
