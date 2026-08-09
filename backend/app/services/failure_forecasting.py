from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ENGINE_NAME = (
    "SS4TS AI Failure Forecasting Engine"
)

ENGINE_VERSION = (
    "1.1.0-decision-consistency"
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()



def calculate_probability(
    *,
    samples: int,
    occurrences: int,
    confidence: float,
) -> float:

    if samples <= 0:

        return round(
            confidence,
            2,
        )


    frequency = (
        occurrences /
        samples
    ) * 100


    probability = (
        frequency * 0.5
        +
        confidence * 0.5
    )


    if probability > 100:

        probability = 100


    return round(
        probability,
        2,
    )



def forecast_failure(
    *,
    pattern_analysis: dict[str, Any],
    prediction: dict[str, Any],
) -> dict[str, Any]:
    """
    H23.4.5.5.12.X.4.6

    AI Failure Forecasting Engine

    Decision Consistency Layer:

    - Sync prediction with forecasting
    - Detect active critical events
    - Prevent false NO_EVENT decisions
    - Improve executive decision accuracy
    """


    generated_at = _utc_now()


    prediction_status = prediction.get(
        "prediction_status",
        "unknown",
    )


    confidence = prediction.get(
        "confidence_percent",
        0,
    )


    events = prediction.get(
        "events",
        [],
    )


    recommended_action = prediction.get(
        "recommended_action",
        "Continue monitoring",
    )



    # =================================================
    # REAL TIME CRITICAL EVENT OVERRIDE
    # =================================================

    if (
        prediction_status == "risk_detected"
        and events
    ):


        active_event = events[0]


        event_code = active_event.get(
            "code",
            "UNKNOWN",
        )


        severity = active_event.get(
            "severity",
            "unknown",
        )


        event_confidence = active_event.get(
            "confidence_percent",
            confidence,
        )



        if event_code == "CPU_SATURATION":

            return {

                "forecast_available": True,


                "predicted_failure":
                    "CPU_SATURATION",


                "failure_probability_percent":
                    event_confidence,


                "risk_level":
                    "critical",


                "expected_time_window":
                    "0-1 hours",


                "impact":
                    (
                        "Possible service degradation "
                        "affecting network users"
                    ),


                "recommended_action":
                    (
                        "Review CPU processes, "
                        "firewall load and traffic utilization"
                    ),


                "generated_at":
                    generated_at,


                "engine": {

                    "name":
                        ENGINE_NAME,


                    "version":
                        ENGINE_VERSION,

                },

            }



        return {

            "forecast_available": True,


            "predicted_failure":
                event_code,


            "failure_probability_percent":
                event_confidence,


            "risk_level":
                severity,


            "expected_time_window":
                "1-4 hours",


            "impact":
                (
                    "Possible service degradation "
                    "affecting network users"
                ),


            "recommended_action":
                recommended_action,


            "generated_at":
                generated_at,


            "engine": {

                "name":
                    ENGINE_NAME,


                "version":
                    ENGINE_VERSION,

            },

        }



    # =================================================
    # HISTORICAL PATTERN ANALYSIS
    # =================================================


    if not pattern_analysis.get(
        "pattern_available"
    ):

        return {

            "forecast_available": True,


            "predicted_failure":
                "NO_EVENT",


            "failure_probability_percent":
                0,


            "risk_level":
                "low",


            "expected_time_window":
                "none",


            "impact":
                "No abnormal condition detected",


            "recommended_action":
                "Continue monitoring",


            "generated_at":
                generated_at,


            "engine": {

                "name":
                    ENGINE_NAME,


                "version":
                    ENGINE_VERSION,

            },

        }



    dominant_pattern = pattern_analysis.get(
        "dominant_failure_pattern"
    )

    # NO_EVENT means the network is healthy.
    # It must never be treated as a predicted failure.
    if not dominant_pattern or dominant_pattern == "NO_EVENT":
        return {
            "forecast_available": False,
            "predicted_failure": "NO_EVENT",
            "failure_probability_percent": 0,
            "risk_level": "low",
            "expected_time_window": "none",
            "impact": "No abnormal condition detected",
            "recommended_action": "Continue monitoring.",
            "generated_at": generated_at,
            "engine": {
                "name": ENGINE_NAME,
                "version": ENGINE_VERSION,
            },
        }


    samples = pattern_analysis.get(
        "samples_analyzed",
        0,
    )


    occurrences = 0


    for item in pattern_analysis.get(
        "top_patterns",
        [],
    ):

        if item.get(
            "event"
        ) == dominant_pattern:

            occurrences = item.get(
                "occurrences",
                0,
            )



    probability = calculate_probability(
        samples=samples,
        occurrences=occurrences,
        confidence=confidence,
    )



    if probability >= 80:

        risk = "critical"

        window = (
            "30-60 minutes"
        )


    elif probability >= 60:

        risk = "high"

        window = (
            "1-4 hours"
        )


    elif probability >= 40:

        risk = "medium"

        window = (
            "4-24 hours"
        )


    else:

        risk = "low"

        window = (
            "24+ hours"
        )



    return {

        "forecast_available": True,


        "predicted_failure":
            dominant_pattern
            if dominant_pattern
            else
            "NO_EVENT",


        "failure_probability_percent":
            probability,


        "risk_level":
            risk,


        "expected_time_window":
            window,


        "impact":
            (
                "Possible service degradation"
                if dominant_pattern
                else
                "No impact detected"
            ),


        "recommended_action":
            recommended_action,


        "generated_at":
            generated_at,


        "engine": {

            "name":
                ENGINE_NAME,


            "version":
                ENGINE_VERSION,

        },

    }
