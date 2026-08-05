from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.api.v1 import network_intelligence
from app.api.v1.router import api_router


def _service_result() -> dict:
    return {
        "router_ip": "192.168.45.99",
        "generated_at": (
            "2026-08-04T13:00:00+00:00"
        ),
        "status": "excellent",
        "health_score": 100,
        "confidence_percent": 100,
        "collector": {
            "status": "available",
        },
        "analysis": {
            "overall_health_score": 100,
            "overall_health": "excellent",
            "findings": [],
            "recommendations": [],
        },
        "service": {
            "name": (
                "SS4TS Network Intelligence "
                "Service"
            ),
            "version": "1.0.0",
        },
    }


def test_router_is_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/devices/"
        "{router_ip}/network-intelligence"
        in paths
    )


@patch(
    "app.api.v1.network_intelligence."
    "get_network_intelligence"
)
def test_endpoint_returns_service_result(
    service_mock,
) -> None:
    service_mock.return_value = (
        _service_result()
    )

    result = (
        network_intelligence
        .network_intelligence(
            router_ip="192.168.45.99",
            include_history=True,
            history_minutes=15,
            history_window_seconds=10,
        )
    )

    assert result["router_ip"] == (
        "192.168.45.99"
    )
    assert result["status"] == "excellent"
    assert result["health_score"] == 100

    service_mock.assert_called_once_with(
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
            network_intelligence
            .network_intelligence(
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
    "app.api.v1.network_intelligence."
    "get_network_intelligence"
)
def test_service_failure_returns_503(
    service_mock,
) -> None:
    service_mock.side_effect = RuntimeError(
        "collector unavailable"
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        (
            network_intelligence
            .network_intelligence(
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


@patch(
    "app.api.v1.network_intelligence."
    "get_network_intelligence"
)
def test_history_options_are_forwarded(
    service_mock,
) -> None:
    service_mock.return_value = (
        _service_result()
    )

    (
        network_intelligence
        .network_intelligence(
            router_ip="192.168.45.99",
            include_history=False,
            history_minutes=30,
            history_window_seconds=60,
        )
    )

    service_mock.assert_called_once_with(
        router_ip="192.168.45.99",
        include_history=False,
        history_minutes=30,
        history_window_seconds=60,
    )
