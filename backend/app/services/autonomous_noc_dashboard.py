from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ENGINE_NAME = (
    "SS4TS Autonomous AI NOC Dashboard Engine"
)

ENGINE_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def build_autonomous_dashboard(
    *,
    router_ip: str,
    intelligence: dict[str, Any],
) -> dict[str, Any]:
    """
    H23.4.5.5.12.X.4.6

    Autonomous AI NOC Dashboard

    Combines:

    - Prediction
    - Learning
    - Pattern Recognition
    - Failure Forecast
    - Executive Decision
    - Response Plan
    - Remediation Status
    """


    prediction = intelligence.get(
        "prediction",
        {},
    )


    failure_forecast = intelligence.get(
        "failure_forecast",
        {},
    )


    executive_decision = intelligence.get(
        "executive_decision",
        {},
    )


    response_plan = intelligence.get(
        "response_plan",
        {},
    )


    risk_level = (
        prediction.get(
            "risk_level",
            "unknown",
        )
    )


    health_score = intelligence.get(
        "health_score",
        0,
    )


    return {

        "engine": {

            "name": ENGINE_NAME,

            "version": ENGINE_VERSION,

        },


        "router_ip": router_ip,


        "generated_at": _utc_now(),



        "system_health": {

            "score": health_score,

            "status":
                intelligence.get(
                    "status",
                    "unknown",
                ),

        },


        "ai_intelligence": {

            "risk_level": risk_level,

            "prediction_status":
                prediction.get(
                    "prediction_status"
                ),

            "confidence":
                prediction.get(
                    "confidence_percent",
                    0,
                ),


            "failure_forecast": {

                "failure":
                    failure_forecast.get(
                        "predicted_failure"
                    ),

                "probability":
                    failure_forecast.get(
                        "failure_probability_percent",
                        0,
                    ),

                "time_window":
                    failure_forecast.get(
                        "expected_time_window"
                    ),

            },

        },


        "executive_action": {

            "decision":
                executive_decision.get(
                    "decision",
                    {},
                ).get(
                    "decision"
                ),

            "priority":
                executive_decision.get(
                    "decision",
                    {},
                ).get(
                    "priority"
                ),

            "approval_required":
                executive_decision.get(
                    "decision",
                    {},
                ).get(
                    "approval_required",
                    False,
                ),

        },


        "automation": {

            "response_actions":
                response_plan.get(
                    "action_count",
                    0,
                ),

            "status":
                response_plan.get(
                    "status",
                    "UNKNOWN",
                ),

        },


        "summary":

            _generate_summary(
                risk_level,
                failure_forecast,
                executive_decision,
            ),

    }



def _generate_summary(
    risk_level: str,
    failure_forecast: dict[str, Any],
    executive_decision: dict[str, Any],
) -> str:


    failure = failure_forecast.get(
        "predicted_failure",
        "NONE",
    )


    decision = (
        executive_decision
        .get(
            "decision",
            {},
        )
        .get(
            "decision",
            "MONITOR",
        )
    )


    if risk_level in (
        "critical",
        "high",
    ):

        return (
            f"AI detected {failure}. "
            f"Recommended executive action: "
            f"{decision}"
        )


    return (
        "Network operating normally. "
        "Continue monitoring."
    )
