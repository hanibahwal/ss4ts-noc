from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.fleet_device_registry import (
    list_devices,
)


ENGINE_NAME = (
    "SS4TS Enterprise Fleet Risk Prediction Engine"
)

ENGINE_VERSION = (
    "1.0.0-production"
)


def _now():
    return datetime.now(
        timezone.utc
    ).isoformat()



def generate_fleet_prediction() -> dict[str, Any]:

    devices = list_devices()

    predictions = []

    critical = 0
    warning = 0
    healthy = 0


    for device in devices:

        score = device.get(
            "health_score",
            0
        )


        if score < 60:

            state = "CRITICAL"
            risk = "HIGH"
            critical += 1


        elif score < 85:

            state = "WARNING"
            risk = "MEDIUM"
            warning += 1


        else:

            state = "HEALTHY"
            risk = "LOW"
            healthy += 1



        predictions.append(

            {

                "router_ip":
                    device["router_ip"],

                "hostname":
                    device["hostname"],

                "site":
                    device["site"],

                "model":
                    device["model"],

                "health_score":
                    score,

                "prediction":
                    state,

                "risk_level":
                    risk,

                "recommendation":
                    (
                        "Immediate investigation required"
                        if risk == "HIGH"
                        else
                        "Continue proactive monitoring"
                    ),

            }

        )



    return {

        "engine":
        {
            "name":
                ENGINE_NAME,

            "version":
                ENGINE_VERSION,

        },


        "fleet_risk_summary":
        {

            "total_devices":
                len(devices),

            "healthy":
                healthy,

            "warning":
                warning,

            "critical":
                critical,

        },


        "predictions":
            predictions,


        "generated_at":
            _now(),

    }
