from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

import pytest

from app.api.v1 import (
    decision_intelligence as api_module,
)
from app.services.domain_integration import (
    run_decision_analysis_domain,
    serialize_decision_analysis,
)


ROUTER_IP = "192.168.45.99"
DEVICE_NAME = "HANI-HOME-OFFICE"
INTERFACE_NAME = "ether1-internet"


def build_system_snapshot() -> dict[str, Any]:
    return {
        "router_ip": ROUTER_IP,
        "identity": DEVICE_NAME,
        "board_name": "RB951Ui-2HnD",
        "architecture": "mipsbe",
        "version": "7.23.1",
        "uptime": "4d12h35m",
        "cpu_usage": 23,
        "memory_usage": 66.74,
        "total_memory_bytes": 134_217_728,
        "free_memory_bytes": 44_640_000,
    }


def build_interfaces_snapshot() -> dict[str, Any]:
    return {
        "router_ip": ROUTER_IP,
        "selected_interface": INTERFACE_NAME,
        "summary": {
            "total": 3,
            "up": 2,
            "down": 1,
            "with_errors": 1,
        },
        "interfaces": [
            {
                "if_descr": INTERFACE_NAME,
                "if_index": 3,
                "if_type": "ethernet",
                "admin_status": "up",
                "oper_status": "up",
                "is_admin_up": True,
                "is_oper_up": True,
                "speed_bps": 100_000_000,
                "rx_bps": 22_000_000,
                "tx_bps": 8_000_000,
                "rx_errors": 0,
                "tx_errors": 0,
                "mtu": 1500,
            },
            {
                "if_descr": "wg1",
                "if_index": 38,
                "if_type": "tunnel",
                "admin_status": "up",
                "oper_status": "up",
                "is_admin_up": True,
                "is_oper_up": True,
                "speed_bps": 0,
                "rx_bps": 251_436,
                "tx_bps": 1_399_752,
                "rx_errors": 0,
                "tx_errors": 5,
                "mtu": 1420,
            },
            {
                "if_descr": "ether3",
                "if_index": 5,
                "if_type": "ethernet",
                "admin_status": "up",
                "oper_status": "down",
                "is_admin_up": True,
                "is_oper_up": False,
                "speed_bps": 100_000_000,
                "rx_bps": 0,
                "tx_bps": 0,
                "rx_errors": 0,
                "tx_errors": 0,
                "mtu": 1500,
            },
        ],
    }


def build_traffic_snapshot(
    *,
    interface_name: str = INTERFACE_NAME,
    point_count: int = 90,
    window_seconds: int = 10,
) -> dict[str, Any]:
    now = datetime.now(
        timezone.utc
    )

    points: list[dict[str, Any]] = []

    for index in range(point_count):
        points.append(
            {
                "time": (
                    now
                    - timedelta(
                        seconds=(
                            point_count
                            - index
                            - 1
                        )
                        * window_seconds
                    )
                ).isoformat(),
                "rx_bps": (
                    10_000_000
                    + index
                    * 100_000
                ),
                "tx_bps": (
                    2_000_000
                    + index
                    * 25_000
                ),
            }
        )

    return {
        "router_ip": ROUTER_IP,
        "interface": interface_name,
        "range_minutes": 15,
        "window_seconds": (
            window_seconds
        ),
        "points": points,
    }


def build_data_sources(
    *,
    routeros: bool = True,
    interfaces: bool = True,
    traffic: bool = True,
) -> dict[str, Any]:
    return {
        "routeros": {
            "available": routeros,
            "status": (
                "available"
                if routeros
                else "unavailable"
            ),
            "error": (
                None
                if routeros
                else "RouterOS unavailable"
            ),
        },
        "interfaces": {
            "available": interfaces,
            "status": (
                "available"
                if interfaces
                else "unavailable"
            ),
            "error": (
                None
                if interfaces
                else "Interfaces unavailable"
            ),
        },
        "traffic_history": {
            "available": traffic,
            "status": (
                "available"
                if traffic
                else "unavailable"
            ),
            "error": (
                None
                if traffic
                else "Traffic unavailable"
            ),
        },
    }


def run_complete_analysis() -> dict[str, Any]:
    result = run_decision_analysis_domain(
        router_ip=ROUTER_IP,
        system_snapshot=(
            build_system_snapshot()
        ),
        interfaces_snapshot=(
            build_interfaces_snapshot()
        ),
        traffic_snapshot=(
            build_traffic_snapshot()
        ),
        selected_interface=(
            INTERFACE_NAME
        ),
        range_minutes=15,
        window_seconds=10,
        data_sources=(
            build_data_sources()
        ),
        system_available=True,
        interfaces_available=True,
    )

    return serialize_decision_analysis(
        result
    )


def test_complete_data_analysis() -> None:
    payload = run_complete_analysis()

    assert payload["router_ip"] == ROUTER_IP
    assert (
        payload["device_name"]
        == DEVICE_NAME
    )

    assert payload["risk"]["level"] in {
        "critical",
        "high",
        "medium",
        "low",
        "healthy",
        "unknown",
    }

    assert isinstance(
        payload["signals"],
        list,
    )

    assert isinstance(
        payload["decisions"],
        list,
    )

    assert (
        payload[
            "domain_integration"
        ]["enabled"]
        is True
    )

    assert (
        payload[
            "domain_integration"
        ]["version"]
        == "1.6.1"
    )

    assert (
        payload[
            "analysis_context"
        ]["traffic_quality"]
        == "excellent"
    )

    assert (
        payload[
            "analysis_context"
        ][
            "traffic_completeness_percent"
        ]
        == 100.0
    )


def test_routeros_unavailable_does_not_crash() -> None:
    result = run_decision_analysis_domain(
        router_ip=ROUTER_IP,
        system_snapshot=None,
        interfaces_snapshot=(
            build_interfaces_snapshot()
        ),
        traffic_snapshot=(
            build_traffic_snapshot()
        ),
        selected_interface=(
            INTERFACE_NAME
        ),
        range_minutes=15,
        window_seconds=10,
        data_sources=(
            build_data_sources(
                routeros=False,
            )
        ),
        system_available=False,
        interfaces_available=True,
    )

    payload = serialize_decision_analysis(
        result
    )

    assert (
        payload[
            "analysis_context"
        ]["device_status"]
        == "offline"
    )

    assert (
        payload[
            "data_sources"
        ]["routeros"]["available"]
        is False
    )

    assert (
        "device_offline"
        in payload[
            "analysis_context"
        ]["device_health_flags"]
    )


def test_interfaces_unavailable_does_not_crash() -> None:
    result = run_decision_analysis_domain(
        router_ip=ROUTER_IP,
        system_snapshot=(
            build_system_snapshot()
        ),
        interfaces_snapshot=None,
        traffic_snapshot=None,
        selected_interface=None,
        range_minutes=15,
        window_seconds=10,
        data_sources=(
            build_data_sources(
                interfaces=False,
                traffic=False,
            )
        ),
        system_available=True,
        interfaces_available=False,
    )

    payload = serialize_decision_analysis(
        result
    )

    assert (
        payload[
            "analysis_context"
        ]["device_status"]
        == "degraded"
    )

    assert (
        payload[
            "analysis_context"
        ]["traffic_sample_count"]
        == 0
    )

    assert (
        "traffic_data_unavailable"
        in payload[
            "analysis_context"
        ]["traffic_health_flags"]
    )


def test_traffic_history_unavailable() -> None:
    result = run_decision_analysis_domain(
        router_ip=ROUTER_IP,
        system_snapshot=(
            build_system_snapshot()
        ),
        interfaces_snapshot=(
            build_interfaces_snapshot()
        ),
        traffic_snapshot=None,
        selected_interface=(
            INTERFACE_NAME
        ),
        range_minutes=15,
        window_seconds=10,
        data_sources=(
            build_data_sources(
                traffic=False,
            )
        ),
        system_available=True,
        interfaces_available=True,
    )

    payload = serialize_decision_analysis(
        result
    )

    assert (
        payload[
            "data_sources"
        ][
            "traffic_history"
        ]["available"]
        is False
    )

    assert (
        payload[
            "analysis_context"
        ]["traffic_quality"]
        == "empty"
    )

    assert (
        payload[
            "analysis_context"
        ]["traffic_sample_count"]
        == 0
    )


def test_unknown_interface_does_not_crash() -> None:
    result = run_decision_analysis_domain(
        router_ip=ROUTER_IP,
        system_snapshot=(
            build_system_snapshot()
        ),
        interfaces_snapshot=(
            build_interfaces_snapshot()
        ),
        traffic_snapshot=(
            build_traffic_snapshot(
                interface_name=(
                    "missing-interface"
                ),
            )
        ),
        selected_interface=(
            "missing-interface"
        ),
        range_minutes=15,
        window_seconds=10,
        data_sources=(
            build_data_sources()
        ),
        system_available=True,
        interfaces_available=True,
    )

    payload = serialize_decision_analysis(
        result
    )

    assert (
        payload[
            "analysis_context"
        ]["selected_interface"]
        == "missing-interface"
    )

    assert (
        payload[
            "analysis_context"
        ]["interface_speed_bps"]
        == 0.0
    )

    assert (
        payload[
            "domain_integration"
        ]["enabled"]
        is True
    )


def test_json_backward_compatibility() -> None:
    payload = run_complete_analysis()

    required_fields = {
        "router_ip",
        "device_name",
        "generated_at",
        "engine",
        "risk",
        "executive_summary",
        "top_signal",
        "signals",
        "root_causes",
        "recommendations",
        "decisions",
        "statistics",
        "explainability",
        "analysis_context",
        "data_sources",
        "domain_integration",
    }

    assert required_fields.issubset(
        payload.keys()
    )

    assert {
        "level",
        "score",
    }.issubset(
        payload["risk"].keys()
    )

    assert {
        "signal_count",
        "root_cause_count",
        "recommendation_count",
        "decision_count",
    }.issubset(
        payload["statistics"].keys()
    )


def test_api_endpoint_with_complete_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_module,
        "get_system_snapshot",
        lambda router_ip: (
            build_system_snapshot()
        ),
    )

    monkeypatch.setattr(
        api_module,
        "get_interfaces_snapshot",
        lambda router_ip, range_minutes: (
            build_interfaces_snapshot()
        ),
    )

    monkeypatch.setattr(
        api_module,
        "get_interface_history",
        lambda **kwargs: (
            build_traffic_snapshot()
        ),
    )

    payload = (
        api_module
        .device_decision_intelligence(
            router_ip=ROUTER_IP,
            interface=INTERFACE_NAME,
            minutes=15,
            window=10,
        )
    )

    assert (
        payload[
            "request_context"
        ]["partial_data"]
        is False
    )

    assert (
        payload[
            "request_context"
        ][
            "domain_integration_enabled"
        ]
        is True
    )

    assert (
        payload[
            "domain_integration"
        ]["enabled"]
        is True
    )


def test_primary_root_cause_matches_top_signal() -> None:
    payload = run_complete_analysis()

    top_signal = payload.get(
        "top_signal"
    )

    root_causes = payload.get(
        "root_causes",
        [],
    )

    assert top_signal is not None
    assert root_causes

    top_signal_id = (
        top_signal["id"]
    )

    primary_root_cause = (
        root_causes[0]
    )

    assert (
        top_signal_id
        in primary_root_cause[
            "supporting_signal_ids"
        ]
    )
