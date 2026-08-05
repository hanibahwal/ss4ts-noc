from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Any

from app.services.lte_metrics import get_lte_metrics
from app.services.ping_metrics import get_ping_metrics
from app.services.routeros import get_system_snapshot
from app.services.traffic import (
    get_interface_history,
    get_interface_rates,
)

from app.services.prediction_memory_snapshot_writer import (
    save_prediction_snapshot,
)

from app.services.prediction_engine import (
    generate_prediction,
)
from app.services.prediction_engine import (
    generate_prediction,
)


COLLECTOR_NAME = "SS4TS Network Intelligence Collector"
COLLECTOR_VERSION = "1.4.0-live-lte-ai-memory"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_status(
    *,
    available: bool,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "available": available,
        "status": "available" if available else "unavailable",
        "error": error,
    }


def _error_message(exc: Exception) -> str:
    message = str(exc).strip()

    if not message:
        message = exc.__class__.__name__

    return message[:500]


def _empty_device() -> dict[str, Any]:
    return {
        "reachable": False,
        "identity": None,
        "board_name": None,
        "platform": None,
        "architecture": None,
        "routeros_version": None,
        "cpu": None,
        "cpu_count": None,
        "cpu_frequency_mhz": None,
        "cpu_usage_percent": None,
        "total_memory_bytes": None,
        "free_memory_bytes": None,
        "memory_usage_percent": None,
        "uptime": None,
        "temperature_celsius": None,
        "health": {},
    }


def _empty_traffic() -> dict[str, Any]:
    return {
        "selected_interface": None,
        "rx_bps": 0.0,
        "tx_bps": 0.0,
        "total_bps": 0.0,
        "interfaces": [],
        "interface_count": 0,
        "active_interface_count": 0,
        "history": {
            "interface": None,
            "range_minutes": 15,
            "window_seconds": 10,
            "points": [],
        },
    }


def _empty_lte() -> dict[str, Any]:
    return {
        "available": False,
        "rsrp": None,
        "rsrq": None,
        "sinr": None,
        "rssi": None,
        "band": None,
        "cell_id": None,
        "operator": None,
        "data_class": None,
        "source": "not_configured",
    }


def _empty_ping() -> dict[str, Any]:
    return {
        "available": False,
        "reachable": None,
        "latency_ms": None,
        "packet_loss_percent": None,
        "source": "not_configured",
    }


def _normalize_device(
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "reachable": True,
        "identity": snapshot.get("identity"),
        "board_name": snapshot.get("board_name"),
        "platform": snapshot.get("platform"),
        "architecture": snapshot.get("architecture"),
        "routeros_version": snapshot.get("version"),
        "cpu": snapshot.get("cpu"),
        "cpu_count": snapshot.get("cpu_count"),
        "cpu_frequency_mhz": snapshot.get(
            "cpu_frequency_mhz"
        ),
        "cpu_usage_percent": snapshot.get("cpu_usage"),
        "total_memory_bytes": snapshot.get(
            "total_memory_bytes"
        ),
        "free_memory_bytes": snapshot.get(
            "free_memory_bytes"
        ),
        "memory_usage_percent": snapshot.get(
            "memory_usage"
        ),
        "uptime": snapshot.get("uptime"),
        "temperature_celsius": snapshot.get(
            "temperature"
        ),
        "health": snapshot.get("health") or {},
    }


def _normalize_traffic(
    rates: dict[str, Any],
    history: dict[str, Any] | None,
) -> dict[str, Any]:
    interfaces = rates.get("interfaces")

    if not isinstance(interfaces, list):
        interfaces = []

    active_interfaces = [
        interface
        for interface in interfaces
        if isinstance(interface, dict)
        and float(interface.get("total_bps") or 0.0) > 0
    ]

    history_data = history or {}

    points = history_data.get("points")

    if not isinstance(points, list):
        points = []

    return {
        "selected_interface": rates.get(
            "selected_interface"
        ),
        "rx_bps": float(rates.get("rx_bps") or 0.0),
        "tx_bps": float(rates.get("tx_bps") or 0.0),
        "total_bps": float(
            rates.get("total_bps") or 0.0
        ),
        "interfaces": interfaces,
        "interface_count": len(interfaces),
        "active_interface_count": len(
            active_interfaces
        ),
        "history": {
            "interface": history_data.get("interface"),
            "range_minutes": history_data.get(
                "range_minutes",
                15,
            ),
            "window_seconds": history_data.get(
                "window_seconds",
                10,
            ),
            "points": points,
        },
    }


def collect_network_intelligence(
    router_ip: str = "192.168.45.99",
    *,
    include_history: bool = True,
    history_minutes: int = 15,
    history_window_seconds: int = 10,
) -> dict[str, Any]:
    """
    Collect live network intelligence from the existing SS4TS services.

    Sources:
    - RouterOS REST API for system information.
    - InfluxDB/SNMP for current interface traffic.
    - InfluxDB/SNMP for interface traffic history.

    Every source is isolated so a failure in one source does not stop
    the complete collector response.
    """

    validated_ip = str(IPv4Address(router_ip))

    device = _empty_device()
    traffic = _empty_traffic()
    lte = _empty_lte()
    ping = _empty_ping()

    source_states: dict[str, dict[str, Any]] = {
        "routeros": _source_status(available=False),
        "traffic": _source_status(available=False),
        "traffic_history": _source_status(
            available=False
        ),
        "lte": _source_status(
            available=False,
            error="LTE collector is not configured",
        ),
        "ping": _source_status(
            available=False,
            error="Ping collector is not configured",
        ),
    }

    try:
        routeros_snapshot = get_system_snapshot(
            validated_ip
        )
        device = _normalize_device(routeros_snapshot)

        source_states["routeros"] = _source_status(
            available=True
        )

    except Exception as exc:
        source_states["routeros"] = _source_status(
            available=False,
            error=_error_message(exc),
        )

    rates: dict[str, Any] | None = None

    try:
        rates = get_interface_rates(
            router_ip=validated_ip,
            range_minutes=5,
        )

        traffic = _normalize_traffic(
            rates=rates,
            history=None,
        )

        source_states["traffic"] = _source_status(
            available=True
        )

    except Exception as exc:
        source_states["traffic"] = _source_status(
            available=False,
            error=_error_message(exc),
        )

    if include_history and rates is not None:
        selected_interface = rates.get(
            "selected_interface"
        )

        try:
            history = get_interface_history(
                router_ip=validated_ip,
                interface_name=selected_interface,
                range_minutes=history_minutes,
                window_seconds=history_window_seconds,
            )

            traffic = _normalize_traffic(
                rates=rates,
                history=history,
            )

            source_states[
                "traffic_history"
            ] = _source_status(available=True)

        except Exception as exc:
            source_states[
                "traffic_history"
            ] = _source_status(
                available=False,
                error=_error_message(exc),
            )

    elif not include_history:
        source_states[
            "traffic_history"
        ] = _source_status(
            available=False,
            error="Traffic history was disabled",
        )

    try:
        ping = get_ping_metrics(
            target=validated_ip,
            range_minutes=5,
        )

        source_states["ping"] = _source_status(
            available=True
        )

    except Exception as exc:
        source_states["ping"] = _source_status(
            available=False,
            error=_error_message(exc),
        )


    try:
        lte = get_lte_metrics()

        source_states["lte"] = _source_status(
            available=True
        )

    except Exception as exc:
        source_states["lte"] = _source_status(
            available=False,
            error=_error_message(exc),
        )


    # =====================================================
    # H23.4.5.5.12.X.4.2.2
    # AI Prediction Engine
    # =====================================================

    try:
        prediction = generate_prediction(
            device=device,
            traffic=traffic,
            lte=lte,
            ping=ping,
        )
    except Exception:
        prediction = {
            "status": "unavailable",
            "reason": "Prediction engine error",
        }

    # =====================================================
    # H23.4.5.5.12.X.4.2.2
    # AI Prediction Engine
    # =====================================================

    try:
        prediction = generate_prediction(
            device=device,
            traffic=traffic,
            lte=lte,
            ping=ping,
        )
    except Exception as exc:
        prediction = {
            "status": "unavailable",
            "error": str(exc),
        }


    available_sources = sum(
        1
        for state in source_states.values()
        if state.get("available") is True
    )

    total_sources = len(source_states)


    # =====================================================
    # H23.4.5.5.12.X.4.3.1
    # AI Prediction Memory Snapshot
    # =====================================================

    try:
        save_prediction_snapshot(
            validated_ip=validated_ip,
            device=device,
            lte=lte,
        )

    except Exception:
        # AI memory failure must not stop collector
        pass


    return {
        "router_ip": validated_ip,
        "generated_at": _utc_now(),
        "mode": "live",
        "status": (
            "available"
            if available_sources == total_sources
            else "partial"
            if available_sources > 0
            else "unavailable"
        ),
        "device": device,
        "traffic": traffic,
        "lte": lte,
        "ping": ping,
        "prediction": prediction,
        "sources": source_states,
        "summary": {
            "available_sources": available_sources,
            "unavailable_sources": (
                total_sources - available_sources
            ),
            "total_sources": total_sources,
            "router_reachable": device["reachable"],
            "selected_interface": traffic[
                "selected_interface"
            ],
            "current_total_bps": traffic["total_bps"],
            "active_interface_count": traffic[
                "active_interface_count"
            ],
        },
        "collector": {
            "name": COLLECTOR_NAME,
            "version": COLLECTOR_VERSION,
        },
    }
