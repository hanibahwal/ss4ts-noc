from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import autonomous_shadow
from app.api.v1.router import api_router
from app.services.autonomous_shadow_mode import (
    AutonomousShadowMode,
)
from app.services.shadow_decision_store import (
    ShadowDecisionStore,
)


def run(coroutine):
    return asyncio.run(coroutine)


def build_store(tmp_path):
    return ShadowDecisionStore(
        tmp_path / "shadow-api.db"
    )


def seed_record(store):
    service = AutonomousShadowMode(store)

    return service.record_decision(
        decision={
            "decision_id": "decision-api-1",
            "action": "SAFE_OPTIMIZATION",
            "risk_level": "LOW",
        },
        simulation={
            "safe_to_execute": True,
            "simulation_status": "PASSED",
            "confidence": 95,
        },
        source_node_id="router-api-1",
    )


def test_router_is_registered():
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/autonomous-shadow"
        in paths
    )

    assert (
        "/api/v1/autonomous-shadow/"
        "{shadow_id}"
        in paths
    )


def test_list_shadow_decisions(
    tmp_path,
    monkeypatch,
):
    store = build_store(tmp_path)
    seed_record(store)

    monkeypatch.setattr(
        autonomous_shadow,
        "get_shadow_store",
        lambda: store,
    )

    result = run(
        autonomous_shadow
        .list_shadow_decisions(
            limit=100
        )
    )

    assert result["count"] == 1

    record = result["records"][0]

    assert (
        record["decision_id"]
        == "decision-api-1"
    )
    assert record["dry_run_only"] is True

    assert (
        result["safety"][
            "execution_enabled"
        ]
        is False
    )
    assert (
        result["safety"][
            "device_command_executed"
        ]
        is False
    )


def test_get_shadow_decision(
    tmp_path,
    monkeypatch,
):
    store = build_store(tmp_path)
    record = seed_record(store)

    monkeypatch.setattr(
        autonomous_shadow,
        "get_shadow_store",
        lambda: store,
    )

    result = run(
        autonomous_shadow
        .get_shadow_decision(
            record.shadow_id
        )
    )

    assert (
        result["shadow_id"]
        == record.shadow_id
    )

    assert (
        result["safety"][
            "execution_authority"
        ]
        is False
    )

    assert (
        result["safety"][
            "network_io_performed"
        ]
        is False
    )


def test_missing_shadow_returns_404(
    tmp_path,
    monkeypatch,
):
    store = build_store(tmp_path)

    monkeypatch.setattr(
        autonomous_shadow,
        "get_shadow_store",
        lambda: store,
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        run(
            autonomous_shadow
            .get_shadow_decision(
                "shadow:missing"
            )
        )

    assert exc_info.value.status_code == 404


def test_api_has_no_execution_routes():
    shadow_routes = [
        route
        for route in api_router.routes
        if route.path.startswith(
            "/api/v1/autonomous-shadow"
        )
    ]

    methods = {
        method
        for route in shadow_routes
        for method in getattr(
            route,
            "methods",
            set(),
        )
    }

    assert methods == {"GET"}
