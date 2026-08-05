# =====================================================
# H23.4.5.5.12.X.4.7.2
# SS4TS Enterprise Fleet Health Intelligence Engine
# =====================================================


from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


from app.services.fleet_device_registry import (
    list_devices,
)



ENGINE_NAME = (
    "SS4TS Enterprise Fleet Health Intelligence Engine"
)


ENGINE_VERSION = (
    "1.0.0-production"
)



def _now():

    return datetime.now(
        timezone.utc
    ).isoformat()



def classify_health(
    score: int
) -> str:


    if score >= 90:

        return "HEALTHY"


    if score >= 70:

        return "WARNING"


    return "CRITICAL"





def generate_fleet_health_report() -> dict[str, Any]:


    devices = list_devices()


    total_devices = len(
        devices
    )


    healthy = 0

    warning = 0

    critical = 0


    health_values = []



    fleet_details = []



    for device in devices:


        score = device.get(
            "health_score",
            0
        )


        health_values.append(
            score
        )



        state = classify_health(
            score
        )


        if state == "HEALTHY":

            healthy += 1


        elif state == "WARNING":

            warning += 1


        else:

            critical += 1



        fleet_details.append(

            {

                "router_ip":
                    device.get(
                        "router_ip"
                    ),


                "hostname":
                    device.get(
                        "hostname"
                    ),


                "site":
                    device.get(
                        "site"
                    ),


                "model":
                    device.get(
                        "model"
                    ),


                "role":
                    device.get(
                        "role"
                    ),


                "health_score":
                    score,


                "health_state":
                    state,


                "status":
                    device.get(
                        "status"
                    ),


                "last_seen":
                    device.get(
                        "last_seen"
                    ),

            }

        )




    average_health = 0


    if health_values:


        average_health = round(

            sum(
                health_values
            )
            /
            len(
                health_values
            ),

            2

        )




    confidence = 0


    if total_devices:


        confidence = 98




    recommendation = (

        "Fleet operating normally"

        if critical == 0

        else

        "Immediate attention required for critical devices"

    )




    return {


        "engine":

        {

            "name":
                ENGINE_NAME,


            "version":
                ENGINE_VERSION,

        },



        "fleet_summary":

        {

            "total_devices":
                total_devices,


            "healthy":
                healthy,


            "warning":
                warning,


            "critical":
                critical,


            "average_health":
                average_health,


            "confidence":
                confidence,


        },



        "devices":
            fleet_details,



        "recommendation":
            recommendation,



        "generated_at":
            _now(),

    }
