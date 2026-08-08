from __future__ import annotations

from typing import Any


SERVICE_NAME = (
    "SS4TS Root Cause Autonomous Orchestrator"
)

SERVICE_VERSION = "1.0.0-H24.1.4"


def orchestrate_root_cause_decision(
    decision: dict[str, Any],
) -> dict[str, Any]:
    """
    H24.1.4

    Connect Root Cause Decision
    with Autonomous Operations workflow.
    """

    priority = str(
        decision.get(
            "priority",
            "MEDIUM",
        )
    ).upper()


    approval_required = (
        decision.get(
            "approval_required",
            True,
        )
    )


    if priority in {
        "CRITICAL",
        "HIGH",
    }:

        execution_mode = (
            "HUMAN_APPROVAL_REQUIRED"
        )

    else:

        execution_mode = (
            "SAFE_AUTONOMOUS_REVIEW"
        )


    return {

        "orchestrator": {

            "name":
                SERVICE_NAME,

            "version":
                SERVICE_VERSION,

        },


        "decision_id":
            decision.get(
                "decision_id"
            ),


        "execution_mode":
            execution_mode,


        "approval_required":
            approval_required,


        "priority":
            priority,


        "next_stage":
            (
                "decision_approval_gateway"
                if approval_required
                else
                "safe_decision_execution_bridge"
            ),


        "source":
            "root_cause_analysis",

    }
