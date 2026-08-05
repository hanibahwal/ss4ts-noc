from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.database import SessionLocal
from app.models.prediction_memory import (
    PredictionMemory,
)


ENGINE_NAME = (
    "SS4TS AI Pattern Recognition Engine"
)

ENGINE_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _trend_direction(
    values: list[float],
) -> str:

    if len(values) < 3:
        return "insufficient_data"

    first = values[: len(values)//2]
    last = values[len(values)//2 :]

    first_avg = sum(first) / len(first)
    last_avg = sum(last) / len(last)

    if last_avg > first_avg:
        return "increasing"

    if last_avg < first_avg:
        return "decreasing"

    return "stable"


def analyze_prediction_patterns(
    router_ip: str,
    days: int = 30,
) -> dict[str, Any]:
    """
    H23.4.5.5.12.X.4.4.1

    AI Pattern Recognition Engine

    Detect:
    - repeated failures
    - frequency
    - risk trend
    - confidence movement
    """

    db = SessionLocal()

    try:

        records = (
            db.query(
                PredictionMemory
            )
            .filter(
                PredictionMemory.router_ip
                == router_ip
            )
            .all()
        )


        if not records:

            return {
                "pattern_available": False,
                "message":
                    "No memory data available",
                "generated_at":
                    _utc_now(),
                "engine": {
                    "name":
                        ENGINE_NAME,
                    "version":
                        ENGINE_VERSION,
                },
            }


        event_counter = Counter(
            r.event_code
            for r in records
            if r.event_code
        )


        risk_counter = Counter(
            r.risk_level
            for r in records
            if r.risk_level
        )


        confidence_values = [
            float(
                r.confidence_percent
            )
            for r in records
            if r.confidence_percent
        ]


        top_patterns = []

        for event, count in (
            event_counter
            .most_common(10)
        ):

            top_patterns.append(
                {
                    "event": event,
                    "occurrences": count,
                    "frequency_percent":
                        round(
                            (
                                count /
                                len(records)
                            )
                            * 100,
                            2,
                        ),
                }
            )


        confidence_trend = (
            _trend_direction(
                confidence_values
            )
        )


        dominant_event = (
            event_counter
            .most_common(1)[0][0]
            if event_counter
            else None
        )


        return {

            "pattern_available": True,

            "router_ip": router_ip,

            "samples_analyzed":
                len(records),

            "days_analyzed":
                days,


            "dominant_failure_pattern":
                dominant_event,


            "patterns_detected":
                len(
                    event_counter
                ),


            "top_patterns":
                top_patterns,


            "risk_distribution":
                dict(
                    risk_counter
                ),


            "confidence_trend":
                confidence_trend,


            "failure_pattern_detected":
                len(
                    event_counter
                ) > 0,


            "generated_at":
                _utc_now(),


            "engine": {
                "name":
                    ENGINE_NAME,

                "version":
                    ENGINE_VERSION,
            },
        }


    finally:

        db.close()
