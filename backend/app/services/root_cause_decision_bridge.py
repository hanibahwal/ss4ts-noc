from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
import uuid


SERVICE_NAME = "SS4TS Root Cause Decision Bridge"
SERVICE_VERSION = "1.0.0-H24.1.3"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_id() -> str:
    return str(uuid.uuid4())


def build_root_cause_decision(
    root_cause: dict[str, Any],
) -> dict[str, Any]:
    """
    H24.1.3

    Converts Root Cause Analysis result
    into Decision Intelligence format.
    """

    status = str(
        root_cause.get(
            "status",
            "unknown",
        )
    ).lower()


    confidence = float(
        root_cause.get(
            "confidence",
            0,
        )
    )


    cause = (
        root_cause.get(
            "primary_root_cause"
        )
        or {}
    )


    cause_code = str(
        cause.get(
            "code",
            "UNKNOWN",
        )
    )


    priority_map = {

        "critical": "CRITICAL",

        "high": "HIGH",

        "medium": "MEDIUM",

        "low": "LOW",

    }


    priority = priority_map.get(
        status,
        "MEDIUM",
    )


    approval_required = (
        priority
        in {
            "CRITICAL",
            "HIGH",
        }
    )


    action_map = {

        "HIGH_CPU":
            "OPTIMIZE_CPU_LOAD",

        "HIGH_MEMORY":
            "OPTIMIZE_MEMORY_USAGE",

        "LINK_FAILURE":
            "CHECK_NETWORK_PATH",

        "PACKET_LOSS":
            "INVESTIGATE_LINK_QUALITY",

    }


    action = action_map.get(
        cause_code,
        "INVESTIGATE_ROOT_CAUSE",
    )


    return {

        "engine": {

            "name":
                SERVICE_NAME,

            "version":
                SERVICE_VERSION,

        },


        "decision_id":
            _decision_id(),


        "decision":
            action,


        "priority":
            priority,


        "confidence_percent":
            confidence,


        "reasoning":
            (
                "Decision generated from "
                "Root Cause Analysis: "
                f"{cause_code}"
            ),


        "recommended_actions":
            [
                action
            ],


        "approval_required":
            approval_required,


        "root_cause":
            cause,


        "created_at":
            _utc_now(),

    }
