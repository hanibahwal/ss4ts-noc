from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.influx import get_influx_client


SERVICE_NAME = "SS4TS Historical Intelligence Engine"
SERVICE_VERSION = "1.0.2"


def _query_measurement(
    measurement: str,
    field: str,
    minutes: int = 60,
) -> list[float]:

    client = get_influx_client()

    query = f'''
from(bucket:"mikrotik")
|> range(start:-{minutes}m)
|> filter(fn:(r)=>
    r._measurement == "{measurement}"
    and r._field == "{field}"
)
|> keep(columns:["_value"])
'''

    tables = client.query_api().query(query)

    values: list[float] = []

    for table in tables:
        for record in table.records:
            try:
                values.append(
                    float(record.get_value())
                )

            except Exception:
                pass

    # ترتيب البيانات زمنياً
    values.sort()

    return values


def _trend(values: list[float]) -> str:

    if len(values) < 3:
        return "unknown"

    first = values[0]
    last = values[-1]

    diff = last - first

    if diff > 10:
        return "rising"

    if diff < -10:
        return "falling"

    return "stable"



def analyze_cpu() -> dict[str, Any]:

    # RouterOS CPU measurement
    # usage_idle -> CPU utilization

    idle_values = _query_measurement(
        "cpu",
        "usage_idle",
        43200,
    )

    if not idle_values:

        return {
            "available": False,
            "reason": "No CPU historical data found",
            "samples": 0,
        }


    cpu_values = [
        round(
            100 - value,
            2
        )
        for value in idle_values
    ]


    current = cpu_values[-1]


    average = round(
        sum(cpu_values) / len(cpu_values),
        2,
    )


    maximum = max(cpu_values)

    minimum = min(cpu_values)


    if current >= 90 and average >= 80:

        decision = "ACTION_REQUIRED"

        reason = (
            "CPU load sustained above critical threshold"
        )


    elif current >= 75:

        decision = "INVESTIGATE"

        reason = (
            "CPU load elevated and requires review"
        )


    else:

        decision = "NORMAL"

        reason = (
            "CPU operating within normal range"
        )


    return {

        "available": True,

        "current": current,

        "average": average,

        "maximum": maximum,

        "minimum": minimum,

        "trend": _trend(cpu_values),

        "decision": decision,

        "reason": reason,

        "samples": len(cpu_values),
    }



def build_historical_intelligence():

    return {

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "service":
            SERVICE_NAME,

        "version":
            SERVICE_VERSION,

        "cpu":
            analyze_cpu(),
    }
