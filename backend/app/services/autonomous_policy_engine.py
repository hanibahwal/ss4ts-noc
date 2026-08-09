from __future__ import annotations

from typing import Any


SERVICE_NAME = "SS4TS Autonomous Policy Engine"
SERVICE_VERSION = "1.0.0-H24.1.5"


POLICY_RULES = {
    "CRITICAL": {
        "mode": "HUMAN_APPROVAL_REQUIRED",
        "auto_execute": False,
    },
    "HIGH": {
        "mode": "HUMAN_APPROVAL_REQUIRED",
        "auto_execute": False,
    },
    "MEDIUM": {
        "mode": "SAFE_AUTONOMOUS_REVIEW",
        "auto_execute": False,
    },
    "LOW": {
        "mode": "AUTO_ALLOWED",
        "auto_execute": True,
    },
}


def evaluate_autonomous_policy(
    decision: dict[str, Any],
) -> dict[str, Any]:
    """
    H24.1.5

    Evaluates whether a decision can proceed
    automatically or requires approval.
    """

    priority = str(
        decision.get(
            "priority",
            "MEDIUM",
        )
    ).upper()

    rule = POLICY_RULES.get(
        priority,
        POLICY_RULES["MEDIUM"],
    )

    return {
        "engine": {
            "name": SERVICE_NAME,
            "version": SERVICE_VERSION,
        },

        "decision_id": decision.get(
            "decision_id"
        ),

        "priority": priority,

        "execution_mode": rule["mode"],

        "auto_execute": rule["auto_execute"],

        "approval_required": (
            not rule["auto_execute"]
        ),

        "policy_source": "H24.1.5_AUTONOMOUS_POLICY",
    }
