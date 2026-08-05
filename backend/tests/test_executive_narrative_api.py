from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.api.v1 import executive_narrative
from app.api.v1.router import api_router


def _intelligence_result() -> dict:
    return {
        "router_ip": "192.168.45.99",
        "generated_at": (
            "2026-08-04T14:45:00+00:00"
        ),
        "status": "healthy",
        "health_score": 95,
        "confidence_percent": 100,
        "collector": {
            "device": {
                "reachable": True,
                "identity": "HANI-HOME-OFFICE",
                "cpu_usage_percent": 27,
                "memory_usage_percent": 72,
            },
            "traffic": {
                "selected_interface": (
                    "ether1-internet"
                ),
            },
            "ping": {
                "available": True,
                "reachable": True,
                "latency_ms": 1.3,
                "packet_loss_percent": 0,
            },
            "lte": {
                "available": True,
                "operator": "mobily",
                "data_class": "LTE",
                "rsrp_dbm": -71,
                "rsrq_db": -13,
                "sinr_db": 19,
            },
            "summary": {
                "available_sources": 5,
                "total_sources": 5,
                "selected_interface": (
                    "ether1-internet"
                ),
            },
        },
        "analysis": {
            "findings": [],
        },
    }


def test_router_is_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/devices/"
        "{router_ip}/executive-narrative"
        in paths
    )


@patch(
    "app.api.v1.executive_narrative."
    "get_network_intelligence"
)
def test_endpoint_returns_narrative(
    intelligence_mock,
) -> None:
    intelligence_mock.return_value = (
        _intelligence_result()
    )

    result = (
        executive_narrative
        .executive_narrative(
            router_ip="192.168.45.99",
            include_history=True,
            history_minutes=15,
            history_window_seconds=10,
        )
    )

    assert result["router_ip"] == (
        "192.168.45.99"
    )

    assert result["status"] == "healthy"
    assert result["health_score"] == 95

    assert (
        result["headline"]
        == "الشبكة تعمل بصورة جيدة"
    )

    intelligence_mock.assert_called_once_with(
        router_ip="192.168.45.99",
        include_history=True,
        history_minutes=15,
        history_window_seconds=10,
    )


def test_invalid_router_ip_returns_400() -> None:
    with pytest.raises(
        HTTPException
    ) as exc:
        (
            executive_narrative
            .executive_narrative(
                router_ip="invalid-ip",
                include_history=True,
                history_minutes=15,
                history_window_seconds=10,
            )
        )

    assert exc.value.status_code == 400

    assert exc.value.detail == (
        "Invalid IPv4 address"
    )


@patch(
    "app.api.v1.executive_narrative."
    "get_network_intelligence"
)
def test_service_failure_returns_503(
    intelligence_mock,
) -> None:
    intelligence_mock.side_effect = (
        RuntimeError(
            "collector unavailable"
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        (
            executive_narrative
            .executive_narrative(
                router_ip="192.168.45.99",
                include_history=True,
                history_minutes=15,
                history_window_seconds=10,
            )
        )

    assert exc.value.status_code == 503

    assert (
        "collector unavailable"
        in exc.value.detail
    )
