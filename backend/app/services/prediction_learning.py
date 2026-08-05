from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.database import SessionLocal
from app.models.prediction_memory import (
    PredictionMemory,
)


LEARNING_ENGINE_NAME = (
    "SS4TS AI Prediction Learning Engine"
)

LEARNING_ENGINE_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def analyze_prediction_history(
    router_ip: str,
    days: int = 7,
) -> dict[str, Any]:
    """
    Analyze historical prediction memory.

    H23.4.5.5.12.X.4.3

    Detect:
    - Repeated failures
    - Common events
    - Risk patterns
    - Frequency
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
                "learning_available": False,
                "message": (
                    "No prediction history available"
                ),
                "generated_at": _utc_now(),
            }


        events = [
            record.event_code
            for record in records
            if record.event_code
        ]


        event_counter = Counter(
            events
        )


        most_common = (
            event_counter
            .most_common(5)
        )


        risk_counter = Counter(
            record.risk_level
            for record in records
        )


        return {

            "learning_available": True,

            "router_ip": router_ip,

            "samples": len(
                records
            ),

            "days_analyzed": days,

            "patterns_detected": (
                len(
                    event_counter
                )
            ),

            "top_events": [
                {
                    "event": item[0],
                    "count": item[1],
                }
                for item
                in most_common
            ],

            "risk_distribution": dict(
                risk_counter
            ),

            "pattern_detected": (
                len(
                    most_common
                ) > 0
            ),

            "generated_at": _utc_now(),

            "engine": {
                "name":
                    LEARNING_ENGINE_NAME,

                "version":
                    LEARNING_ENGINE_VERSION,
            },
        }


    finally:

        db.close()
