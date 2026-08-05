from __future__ import annotations

from unittest.mock import patch

from app.services.network_intelligence import (
    get_network_intelligence,
)


def _collector_result() -> dict:
    return {
        "router_ip": "192.168.45.99",
        "generated_at": "2026-08-04T13:00:00+00:00",
        "device": {
            "reachable": True,
            "cpu_usage_percent": 20.0,
            "memory_usage_percent": 40.0,
            "temperature_celsius": 45.0,
        },
        "traffic": {
            "selected_interface": "ether1",
            "total_bps": 1_000_000.0,
            "history": {
                "points": [
                    {"total_bps": 1_000_000.0}
                    for _ in range(6)
                ],
            },
        },
        "ping": {
            "available": True,
            "reachable": True,
            "latency_ms": 1.0,
            "packet_loss_percent": 0.0,
        },
        "lte": {
            "available": True,
            "running": True,
            "rsrp_dbm": -70,
            "rsrq_db": -10,
            "sinr_db": 20,
            "rssi_dbm": -40,
        },
    }


@patch(
    "app.services.network_intelligence."
    "collect_network_intelligence"
)
def test_unified_service_returns_result(
    collector_mock,
) -> None:
    collector_mock.return_value = (
        _collector_result()
    )

    result = get_network_intelligence(
        router_ip="192.168.45.99"
    )

    assert result["router_ip"] == "192.168.45.99"
    assert result["status"] == "excellent"
    assert result["health_score"] == 100
    assert result["confidence_percent"] == 100

    assert "collector" in result
    assert "analysis" in result
    assert "service" in result

    assert (
        result["service"]["name"]
        == "SS4TS Network Intelligence Service"
    )


@patch(
    "app.services.network_intelligence."
    "collect_network_intelligence"
)
def test_service_passes_collector_options(
    collector_mock,
) -> None:
    collector_mock.return_value = (
        _collector_result()
    )

    get_network_intelligence(
        router_ip="192.168.45.99",
        include_history=False,
        history_minutes=30,
        history_window_seconds=60,
    )

    collector_mock.assert_called_once_with(
        router_ip="192.168.45.99",
        include_history=False,
        history_minutes=30,
        history_window_seconds=60,
    )
