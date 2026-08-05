from __future__ import annotations

from typing import Any

from app.services.decision_engine import (
    analyze_decision_intelligence,
)


ENGINE_COLLECTOR_VERSION = "1.0.0"


def collect_decision_data(
    *,
    router_ip: str,
    device_name: str | None = None,
    cpu_usage: float = 0,
    memory_usage: float = 0,
    interfaces: list[dict[str, Any]] | None = None,
    traffic_history: list[dict[str, Any]] | None = None,
    selected_interface: str | None = None,
) -> dict[str, Any]:
    """
    Decision Intelligence Data Collector

    تجمع بيانات الشبكة وتغذي Decision Engine
    """

    decision = analyze_decision_intelligence(
        router_ip=router_ip,
        device_name=device_name,

        cpu_usage=cpu_usage,
        memory_usage=memory_usage,

        interfaces=interfaces or [],

        traffic_history=
            traffic_history or [],

        selected_interface=
            selected_interface,

        sample_seconds=10,
    )


    return {

        "collector": {
            "name":
                "SS4TS Decision Data Collector",

            "version":
                ENGINE_COLLECTOR_VERSION,
        },


        "decision": decision,

    }
