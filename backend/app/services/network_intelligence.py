from __future__ import annotations

from typing import Any

from app.services.prediction_memory_store import (
    save_prediction_memory,
)

from app.services.prediction_learning import (
    analyze_prediction_history,
)

from app.services.pattern_recognition import (
    analyze_prediction_patterns,
)

from app.services.failure_forecasting import (
    forecast_failure,
)

from app.services.executive_decision_engine import (
    generate_executive_decision,
)

from app.services.response_action_planner import (
    generate_response_plan,
)

from app.services.autonomous_noc_dashboard import (
    build_autonomous_dashboard,
)

from app.services.network_intelligence_analyzer import (
    analyze_network_intelligence,
)

from app.services.network_intelligence_collector import (
    collect_network_intelligence,
)

from app.services.prediction_engine import (
    generate_prediction,
)

from app.services.routeros_live_metrics import (
    routeros_live_metrics,
)


SERVICE_NAME = (
    "SS4TS Network Intelligence Service"
)

SERVICE_VERSION = (
    "1.7.1-autonomous-ai-noc-live-metrics"
)


def get_network_intelligence(
    *,
    router_ip: str,
    include_history: bool = True,
    history_minutes: int = 15,
    history_window_seconds: int = 10,
) -> dict[str, Any]:
    """
    Unified Network Intelligence Service.

    Includes:
    - Live Collector
    - RouterOS Live Metrics
    - Health Analysis
    - AI Prediction Engine
    - AI Prediction Memory
    - Learning Loop
    - Pattern Recognition Engine
    - Failure Forecasting Engine
    - Executive Decision Engine
    - Response Action Planner
    - Autonomous AI NOC Dashboard
    """

    collector = collect_network_intelligence(
        router_ip=router_ip,
        include_history=include_history,
        history_minutes=history_minutes,
        history_window_seconds=history_window_seconds,
    )

    live_metrics = routeros_live_metrics.collect(
        router_ip=router_ip
    )

    collector["live_metrics"] = live_metrics

    # H30.11 UNIFIED TRAFFIC SOURCE
    # RouterOS live metrics provides device/system metrics only.
    # Current traffic is supplied by the existing traffic collector
    # (InfluxDB/SNMP). Keep both API views synchronized so consumers
    # do not receive zero traffic from live_metrics.

    collector_traffic = collector.get(
        "traffic",
        {},
    )

    if isinstance(
        collector_traffic,
        dict,
    ):
        live_metrics["traffic"] = {
            "rx_bps": float(
                collector_traffic.get(
                    "rx_bps",
                    0,
                )
                or 0
            ),
            "tx_bps": float(
                collector_traffic.get(
                    "tx_bps",
                    0,
                )
                or 0
            ),
            "total_bps": float(
                collector_traffic.get(
                    "total_bps",
                    0,
                )
                or 0
            ),
            "selected_interface":
                collector_traffic.get(
                    "selected_interface"
                ),
        }

        interfaces = collector_traffic.get(
            "interfaces",
            [],
        )

        if isinstance(
            interfaces,
            list,
        ):
            live_metrics["interfaces"] = (
                interfaces
            )

        live_metrics["traffic_source"] = (
            "SS4TS traffic collector "
            "(InfluxDB/SNMP)"
        )

    # H30.6 LIVE METRICS PRIORITY FIX
    # RouterOS REST API live data has priority over cached collector values.
    # Synchronize device metrics with real-time RouterOS metrics.

    if live_metrics.get("available"):

        device = collector.setdefault(
            "device",
            {}
        )

        device["identity"] = live_metrics.get(
            "identity"
        )

        # H30.10 CPU/MEMORY SOURCE PROTECTION
        # RouterOS system snapshot is the trusted source.
        # Live metrics are used only when the collector has no value.

        snapshot_cpu = device.get(
            "cpu_usage_percent"
        )

        snapshot_memory = device.get(
            "memory_usage_percent"
        )

        if snapshot_cpu is None:
            live_cpu = live_metrics.get(
                "cpu_usage_percent"
            )

            if live_cpu is not None:
                device["cpu_usage_percent"] = live_cpu

        if snapshot_memory is None:
            live_memory = live_metrics.get(
                "memory_usage_percent"
            )

            if live_memory is not None:
                device["memory_usage_percent"] = live_memory

        device["board_name"] = live_metrics.get(
            "board_name"
        )

        device["version"] = live_metrics.get(
            "version"
        )

        device["architecture"] = live_metrics.get(
            "architecture"
        )

    analysis = analyze_network_intelligence(
        collector
    )

    prediction = generate_prediction(
        device=collector.get(
            "device",
            {},
        ),
        traffic=collector.get(
            "traffic",
            {},
        ),
        lte=collector.get(
            "lte",
            {},
        ),
        ping=collector.get(
            "ping",
            {},
        ),
    )

    save_prediction_memory(
        router_ip=router_ip,
        prediction=prediction,
    )

    learning = analyze_prediction_history(
        router_ip=router_ip,
    )

    pattern_analysis = analyze_prediction_patterns(
        router_ip=router_ip,
    )

    failure_forecast = forecast_failure(
        pattern_analysis=pattern_analysis,
        prediction=prediction,
    )

    executive_decision = generate_executive_decision(
        prediction=prediction,
        pattern_analysis=pattern_analysis,
        failure_forecast=failure_forecast,
    )

    response_plan = generate_response_plan(
        executive_decision=executive_decision,
        router_ip=router_ip,
    )

    autonomous_dashboard = build_autonomous_dashboard(
        router_ip=router_ip,
        intelligence={
            "health_score": analysis.get(
                "overall_health_score"
            ),
            "status": analysis.get(
                "overall_health"
            ),
            "prediction": prediction,
            "failure_forecast": failure_forecast,
            "executive_decision": executive_decision,
            "response_plan": response_plan,
        },
    )

    return {
        "router_ip": collector.get(
            "router_ip"
        ),
        "generated_at": collector.get(
            "generated_at"
        ),
        "status": analysis.get(
            "overall_health"
        ),
        "health_score": analysis.get(
            "overall_health_score"
        ),
        "confidence_percent": analysis.get(
            "confidence_percent"
        ),
        "collector": collector,
        "live_metrics": live_metrics,
        "analysis": analysis,
        "prediction": prediction,
        "learning": learning,
        "pattern_analysis": pattern_analysis,
        "failure_forecast": failure_forecast,
        "executive_decision": executive_decision,
        "response_plan": response_plan,
        "autonomous_dashboard": autonomous_dashboard,
        "service": {
            "name": SERVICE_NAME,
            "version": SERVICE_VERSION,
        },
    }
