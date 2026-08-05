from __future__ import annotations

import json
from typing import Any

from app.database import (
    SessionLocal,
    init_database,
)

from app.models.prediction_memory import (
    PredictionMemory,
)


# ==========================================================
# SS4TS AI Prediction Memory Store
# H23.4.5.5.12.X.4.3
# AI Prediction Memory Loop
# ==========================================================


SERVICE_NAME = (
    "SS4TS Prediction Memory Store"
)


SERVICE_VERSION = (
    "1.1.0-production"
)


# ==========================================================
# Ensure Database Schema Exists
# ==========================================================

init_database()


# ==========================================================
# Save Prediction Memory
# ==========================================================

def save_prediction_memory(
    *,
    router_ip: str,
    prediction: dict[str, Any],
) -> None:
    """
    Store AI prediction history.

    Flow:

    Network Intelligence
            |
            v
    Prediction Engine
            |
            v
    Prediction Memory
            |
            v
    Learning Loop


    H23.4.5.5.12.X.4.3
    AI Prediction Memory Loop
    """


    events = prediction.get(
        "events",
        [],
    )


    if not events:

        events = [
            {
                "code": "NO_EVENT",

                "metric": None,

                "value": None,

                "confidence_percent":
                    prediction.get(
                        "confidence_percent",
                        0,
                    ),
            }
        ]



    db = SessionLocal()


    try:

        for event in events:


            record = PredictionMemory()


            record.router_ip = (
                router_ip
            )


            record.prediction_status = (
                prediction.get(
                    "prediction_status",
                    "unknown",
                )
            )


            record.risk_level = (
                prediction.get(
                    "risk_level",
                    "unknown",
                )
            )


            record.event_code = (
                event.get(
                    "code"
                )
            )


            record.confidence_percent = (
                event.get(
                    "confidence_percent",
                )
            )


            record.metric = (
                event.get(
                    "metric"
                )
            )


            record.metric_value = json.dumps(
                event.get(
                    "value"
                ),
                default=str,
            )


            db.add(
                record
            )


        db.commit()



    except Exception:

        db.rollback()

        raise



    finally:

        db.close()
